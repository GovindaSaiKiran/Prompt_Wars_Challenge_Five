"""FastAPI endpoints for Event Timeline, Tasks, Dependencies, and Progress Tracking."""

import logging
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.event import Event
from app.models.task import EventTask, TaskActivity, TaskDependency
from app.schemas.task import (
    DependencyType,
    EventTaskCreate,
    EventTaskDetailResponse,
    EventTaskResponse,
    EventTaskUpdate,
    TaskActivityResponse,
    TaskCategory,
    TaskDependencyCreate,
    TaskDependencyResponse,
    TaskListResponse,
    TaskPriority,
    TaskProgressSummaryResponse,
    TaskStatus,
    TimelineResponse,
)
from app.services.task_service import (
    build_timeline_schedule,
    check_task_dependency_status,
    compute_progress_summary,
    evaluate_dependency_satisfaction,
    record_task_activity,
    would_create_cycle,
)

logger = logging.getLogger("eventprice.tasks")

router = APIRouter(
    prefix="/events/{event_id}/tasks",
    tags=["Event Tasks & Timeline"],
)


# ============================================================================
# Helpers
# ============================================================================


def get_event_or_404(event_id: uuid.UUID, db: Session) -> Event:
    """Verify that the parent event exists."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id '{event_id}' not found",
        )
    return event


def get_task_or_404(
    event_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session,
    include_deleted: bool = False,
    eager_load_deps: bool = False,
    eager_load_activity: bool = False,
) -> EventTask:
    """Retrieve task and verify strict parent event scoping and soft-deletion status."""
    get_event_or_404(event_id, db)

    stmt = select(EventTask).where(EventTask.id == task_id)
    if not include_deleted:
        stmt = stmt.where(EventTask.is_deleted == False)

    if eager_load_deps:
        stmt = stmt.options(
            selectinload(EventTask.predecessor_dependencies).selectinload(TaskDependency.predecessor_task),
            selectinload(EventTask.successor_dependencies).selectinload(TaskDependency.successor_task),
        )
    if eager_load_activity:
        stmt = stmt.options(selectinload(EventTask.activity_history))

    task = db.execute(stmt).scalars().first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id '{task_id}' not found",
        )
    if task.event_id != event_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id '{task_id}' does not belong to event '{event_id}'",
        )
    return task


def enrich_task_response(task: EventTask) -> EventTask:
    """Dynamically populate is_dependency_blocked and dependency_block_reasons attributes on model."""
    is_blocked, reasons = check_task_dependency_status(task)
    setattr(task, "is_dependency_blocked", is_blocked)
    setattr(task, "dependency_block_reasons", reasons)
    return task


# ============================================================================
# Task CRUD Endpoints
# ============================================================================


@router.post(
    "/",
    response_model=EventTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create event task",
    description="Creates a new task scoped to the event and logs an initial creation activity.",
)
def create_event_task(
    event_id: uuid.UUID,
    payload: EventTaskCreate,
    db: Session = Depends(get_db),
) -> EventTask:
    """Create a new task with initial activity log entry."""
    get_event_or_404(event_id, db)

    completed_at = None
    if payload.status == TaskStatus.COMPLETED:
        completed_at = datetime.now(timezone.utc)

    task = EventTask(
        event_id=event_id,
        title=payload.title,
        description=payload.description,
        category=payload.category.value,
        status=payload.status.value,
        priority=payload.priority.value,
        start_date=payload.start_date,
        due_date=payload.due_date,
        completed_at=completed_at,
        estimated_cost=payload.estimated_cost,
        actual_cost=payload.actual_cost,
        currency=payload.currency,
        assigned_to=payload.assigned_to,
        notes=payload.notes,
        is_deleted=False,
    )
    db.add(task)
    db.flush()

    # Append-only creation activity log
    record_task_activity(
        db=db,
        event_id=event_id,
        task_id=task.id,
        task_title=task.title,
        action_type="created",
        new_value=task.status,
        description=f"Task '{task.title}' created with status '{task.status}' and priority '{task.priority}'",
    )

    db.commit()
    db.refresh(task)

    enrich_task_response(task)
    logger.info("Created task id=%s title='%s' for event id=%s", task.id, task.title, event_id)
    return task


@router.get(
    "/",
    response_model=TaskListResponse,
    status_code=status.HTTP_200_OK,
    summary="List event tasks",
    description="Lists active tasks for an event with multi-field filtering, due date range, and pagination.",
)
def list_event_tasks(
    event_id: uuid.UUID,
    status_filter: Optional[TaskStatus] = Query(None, alias="status", description="Filter by status"),
    priority: Optional[TaskPriority] = Query(None, description="Filter by priority"),
    category: Optional[TaskCategory] = Query(None, description="Filter by category"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee"),
    due_date_from: Optional[date] = Query(None, description="Filter due date on or after (inclusive)"),
    due_date_to: Optional[date] = Query(None, description="Filter due date on or before (inclusive)"),
    overdue_only: bool = Query(False, description="Filter strictly overdue tasks"),
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    db: Session = Depends(get_db),
) -> TaskListResponse:
    """List event tasks with filtering, date bounds, and pagination."""
    get_event_or_404(event_id, db)

    # Validate date range
    if due_date_from is not None and due_date_to is not None and due_date_from > due_date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="due_date_from cannot be later than due_date_to",
        )

    stmt = select(EventTask).where(
        EventTask.event_id == event_id,
        EventTask.is_deleted == False,
    )

    if status_filter is not None:
        stmt = stmt.where(EventTask.status == status_filter.value)
    if priority is not None:
        stmt = stmt.where(EventTask.priority == priority.value)
    if category is not None:
        stmt = stmt.where(EventTask.category == category.value)
    if assigned_to is not None:
        stmt = stmt.where(EventTask.assigned_to.ilike(f"%{assigned_to.strip()}%"))
    if due_date_from is not None:
        stmt = stmt.where(EventTask.due_date >= due_date_from)
    if due_date_to is not None:
        stmt = stmt.where(EventTask.due_date <= due_date_to)
    if overdue_only:
        today = datetime.now(timezone.utc).date()
        stmt = stmt.where(
            EventTask.due_date.is_not(None),
            EventTask.due_date < today,
            EventTask.status.not_in(["completed", "cancelled"]),
        )

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    # Paginate and eager load predecessor dependencies to check dependency block status
    paged_stmt = (
        stmt.options(
            selectinload(EventTask.predecessor_dependencies).selectinload(TaskDependency.predecessor_task),
        )
        .order_by(EventTask.due_date.asc().nulls_last(), EventTask.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    items = list(db.execute(paged_stmt).scalars().all())

    for item in items:
        enrich_task_response(item)

    return TaskListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/timeline",
    response_model=TimelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve event timeline",
    description="Retrieves active tasks organized chronologically by target due date.",
)
def get_event_timeline(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> TimelineResponse:
    """Build chronological timeline breakdown for active tasks in the event."""
    get_event_or_404(event_id, db)

    stmt = (
        select(EventTask)
        .where(
            EventTask.event_id == event_id,
            EventTask.is_deleted == False,
        )
        .options(
            selectinload(EventTask.predecessor_dependencies).selectinload(TaskDependency.predecessor_task),
            selectinload(EventTask.successor_dependencies).selectinload(TaskDependency.successor_task),
        )
    )
    tasks = list(db.execute(stmt).scalars().all())
    schedule = build_timeline_schedule(tasks)
    return TimelineResponse(**schedule)


@router.get(
    "/progress",
    response_model=TaskProgressSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve event task progress metrics",
    description="Computes completion percentage, status breakdown, cost totals, and overdue count.",
)
def get_event_task_progress(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> TaskProgressSummaryResponse:
    """Compute deterministic progress metrics across all active tasks in the event."""
    get_event_or_404(event_id, db)

    stmt = select(EventTask).where(
        EventTask.event_id == event_id,
        EventTask.is_deleted == False,
    )
    tasks = list(db.execute(stmt).scalars().all())
    summary = compute_progress_summary(tasks)
    return TaskProgressSummaryResponse(**summary)


@router.get(
    "/activity",
    response_model=List[TaskActivityResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve event task activity audit trail",
    description="Returns the append-only chronological audit log across all tasks for the event.",
)
def get_event_task_activity_history(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[TaskActivity]:
    """Retrieve event-wide task activity audit log."""
    get_event_or_404(event_id, db)

    stmt = (
        select(TaskActivity)
        .where(TaskActivity.event_id == event_id)
        .order_by(TaskActivity.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())


@router.get(
    "/{task_id}",
    response_model=EventTaskDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve task details",
    description="Retrieves an active event task with eager-loaded dependencies and append-only activity history.",
)
def get_event_task(
    event_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EventTask:
    """Retrieve detailed task representation."""
    task = get_task_or_404(
        event_id=event_id,
        task_id=task_id,
        db=db,
        include_deleted=False,
        eager_load_deps=True,
        eager_load_activity=True,
    )
    return enrich_task_response(task)


@router.patch(
    "/{task_id}",
    response_model=EventTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Update event task",
    description=(
        "Updates task attributes with dependency satisfaction enforcement, "
        "completion timestamp consistency, and automatic activity history logging."
    ),
)
def update_event_task(
    event_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: EventTaskUpdate,
    db: Session = Depends(get_db),
) -> EventTask:
    """Update task with dependency satisfaction checks and audit trail."""
    task = get_task_or_404(
        event_id=event_id,
        task_id=task_id,
        db=db,
        include_deleted=False,
        eager_load_deps=True,
    )

    update_data = payload.model_dump(exclude_unset=True)

    # 1. Dependency constraint enforcement on status change
    if "status" in update_data and update_data["status"] is not None:
        new_status = update_data["status"].value if hasattr(update_data["status"], "value") else str(update_data["status"])
        old_status = task.status

        if new_status != old_status:
            # Check predecessor dependencies satisfaction
            is_satisfied, reason = evaluate_dependency_satisfaction(
                target_status=new_status,
                predecessor_dependencies=task.predecessor_dependencies,
            )
            if not is_satisfied:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=reason,
                )

            # Completion timestamp consistency rules
            if new_status == "completed":
                task.completed_at = datetime.now(timezone.utc)
            elif old_status == "completed" and new_status != "completed":
                # Reopening task clears completion timestamp
                task.completed_at = None

            # Record status change activity
            record_task_activity(
                db=db,
                event_id=event_id,
                task_id=task.id,
                task_title=task.title,
                action_type="status_changed",
                previous_value=old_status,
                new_value=new_status,
                description=f"Status changed from '{old_status}' to '{new_status}'",
            )
            task.status = new_status

    # 2. Track other field changes for audit log
    if "priority" in update_data and update_data["priority"] is not None:
        new_priority = update_data["priority"].value if hasattr(update_data["priority"], "value") else str(update_data["priority"])
        if new_priority != task.priority:
            record_task_activity(
                db=db,
                event_id=event_id,
                task_id=task.id,
                task_title=task.title,
                action_type="priority_changed",
                previous_value=task.priority,
                new_value=new_priority,
                description=f"Priority updated from '{task.priority}' to '{new_priority}'",
            )
            task.priority = new_priority

    if "assigned_to" in update_data:
        new_assignee = update_data["assigned_to"]
        if new_assignee != task.assigned_to:
            record_task_activity(
                db=db,
                event_id=event_id,
                task_id=task.id,
                task_title=task.title,
                action_type="assignment_changed",
                previous_value=task.assigned_to,
                new_value=new_assignee,
                description=f"Assignment changed from '{task.assigned_to}' to '{new_assignee}'",
            )
            task.assigned_to = new_assignee

    if "due_date" in update_data:
        new_due = update_data["due_date"]
        if new_due != task.due_date:
            record_task_activity(
                db=db,
                event_id=event_id,
                task_id=task.id,
                task_title=task.title,
                action_type="due_date_changed",
                previous_value=task.due_date.isoformat() if task.due_date else None,
                new_value=new_due.isoformat() if new_due else None,
                description=f"Due date changed from '{task.due_date}' to '{new_due}'",
            )
            task.due_date = new_due

    # Update remaining attributes
    for field_name in ("title", "description", "start_date", "estimated_cost", "actual_cost", "currency", "notes"):
        if field_name in update_data:
            setattr(task, field_name, update_data[field_name])

    if "category" in update_data and update_data["category"] is not None:
        cat_val = update_data["category"].value if hasattr(update_data["category"], "value") else str(update_data["category"])
        task.category = cat_val

    db.commit()
    db.refresh(task)

    enrich_task_response(task)
    logger.info("Updated task id=%s title='%s'", task.id, task.title)
    return task


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete event task (soft delete with audit history preservation)",
    description=(
        "Soft-deletes an event task, cleans up active dependency constraints, "
        "and appends a deletion record to the immutable activity history."
    ),
)
def delete_event_task(
    event_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> None:
    """Soft delete task while preserving audit history."""
    task = get_task_or_404(event_id=event_id, task_id=task_id, db=db, include_deleted=False)

    task.is_deleted = True
    task.deleted_at = datetime.now(timezone.utc)

    # Clean up active dependency links involving this task so active tasks are not blocked
    dep_stmt = select(TaskDependency).where(
        (TaskDependency.predecessor_task_id == task_id) | (TaskDependency.successor_task_id == task_id)
    )
    deps_to_remove = list(db.execute(dep_stmt).scalars().all())
    for dep in deps_to_remove:
        db.delete(dep)

    # Append-only deletion activity log (preserves task audit trail)
    record_task_activity(
        db=db,
        event_id=event_id,
        task_id=task.id,
        task_title=task.title,
        action_type="deleted",
        previous_value=task.status,
        new_value="deleted",
        description=f"Task '{task.title}' was deleted",
    )

    db.commit()
    logger.info("Soft-deleted task id=%s from event id=%s with audit history preserved", task_id, event_id)


# ============================================================================
# Task Dependency Endpoints
# ============================================================================


@router.post(
    "/{task_id}/dependencies",
    response_model=TaskDependencyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add task dependency",
    description=(
        "Adds a directed dependency constraint (predecessor -> successor). "
        "Validates same-event ownership, rejects self-dependencies and duplicate pairs, "
        "and executes cycle detection across the dependency DAG."
    ),
)
def add_task_dependency(
    event_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: TaskDependencyCreate,
    db: Session = Depends(get_db),
) -> TaskDependency:
    """Add a directed task dependency with cycle detection and status validation."""
    successor = get_task_or_404(event_id=event_id, task_id=task_id, db=db, include_deleted=False)

    # 1. Reject self-dependency
    if payload.predecessor_task_id == task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A task cannot depend on itself (self-dependency rejected).",
        )

    # 2. Verify predecessor exists, is not deleted, and belongs to the same event
    predecessor = db.get(EventTask, payload.predecessor_task_id)
    if not predecessor or predecessor.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Predecessor task with id '{payload.predecessor_task_id}' not found",
        )
    if predecessor.event_id != event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Predecessor task belongs to a different event. Both tasks must belong to the same event.",
        )

    # 3. Reject duplicate dependency pair
    dup_stmt = select(TaskDependency).where(
        TaskDependency.predecessor_task_id == payload.predecessor_task_id,
        TaskDependency.successor_task_id == task_id,
    )
    if db.execute(dup_stmt).scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A dependency between this predecessor and successor already exists.",
        )

    # 4. Cycle detection across the event dependency DAG
    existing_edges_stmt = (
        select(TaskDependency.predecessor_task_id, TaskDependency.successor_task_id)
        .join(EventTask, TaskDependency.successor_task_id == EventTask.id)
        .where(
            EventTask.event_id == event_id,
            EventTask.is_deleted == False,
        )
    )
    existing_edges = list(db.execute(existing_edges_stmt).all())

    if would_create_cycle(
        existing_edges=existing_edges,
        new_predecessor_id=payload.predecessor_task_id,
        new_successor_id=task_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Circular dependency detected: adding predecessor '{predecessor.title}' to "
                f"successor '{successor.title}' would introduce a circular dependency loop."
            ),
        )

    # 5. Check if successor's current status violates the newly requested dependency constraint
    dep_type = payload.dependency_type.value
    succ_status = successor.status
    pred_status = predecessor.status
    is_starting = succ_status in ("in_progress", "completed")
    is_completing = succ_status == "completed"

    if dep_type == "finish_to_start" and is_starting and pred_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add finish_to_start dependency: successor task is already {succ_status} while predecessor '{predecessor.title}' ({pred_status}) is not completed.",
        )
    elif dep_type == "start_to_start" and is_starting and pred_status not in ("in_progress", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add start_to_start dependency: successor task is already {succ_status} while predecessor '{predecessor.title}' ({pred_status}) has not started.",
        )
    elif dep_type == "finish_to_finish" and is_completing and pred_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add finish_to_finish dependency: successor task is already completed while predecessor '{predecessor.title}' ({pred_status}) is not completed.",
        )
    elif dep_type == "start_to_finish" and is_completing and pred_status not in ("in_progress", "completed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot add start_to_finish dependency: successor task is already completed while predecessor '{predecessor.title}' ({pred_status}) has not started.",
        )

    dep = TaskDependency(
        predecessor_task_id=payload.predecessor_task_id,
        successor_task_id=task_id,
        dependency_type=payload.dependency_type.value,
    )
    db.add(dep)
    db.flush()

    # Log activity on successor task
    record_task_activity(
        db=db,
        event_id=event_id,
        task_id=task_id,
        task_title=successor.title,
        action_type="dependency_added",
        new_value=str(dep.id),
        description=(
            f"Added {payload.dependency_type.value} dependency: requires predecessor "
            f"'{predecessor.title}' ({payload.predecessor_task_id})"
        ),
    )

    db.commit()
    db.refresh(dep)

    dep.predecessor_task_title = predecessor.title
    dep.successor_task_title = successor.title

    logger.info(
        "Added dependency id=%s pred=%s succ=%s type='%s'",
        dep.id,
        payload.predecessor_task_id,
        task_id,
        dep.dependency_type,
    )
    return dep


@router.delete(
    "/{task_id}/dependencies/{dependency_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove task dependency",
    description="Deletes a directed dependency constraint from a task.",
)
def remove_task_dependency(
    event_id: uuid.UUID,
    task_id: uuid.UUID,
    dependency_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> None:
    """Remove task dependency."""
    task = get_task_or_404(event_id=event_id, task_id=task_id, db=db, include_deleted=False)

    dep = db.get(TaskDependency, dependency_id)
    if not dep:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task dependency with id '{dependency_id}' not found",
        )
    if dep.successor_task_id != task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Dependency '{dependency_id}' does not apply to task '{task_id}'",
        )

    # Log activity before deletion
    record_task_activity(
        db=db,
        event_id=event_id,
        task_id=task_id,
        task_title=task.title,
        action_type="dependency_removed",
        previous_value=str(dependency_id),
        description=f"Removed {dep.dependency_type} dependency constraint",
    )

    db.delete(dep)
    db.commit()
    logger.info("Removed dependency id=%s from task id=%s", dependency_id, task_id)


# ============================================================================
# Task Activity History Endpoint (Append-Only & Retained across Deletions)
# ============================================================================


@router.get(
    "/{task_id}/activity",
    response_model=List[TaskActivityResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve task activity audit trail",
    description="Returns the append-only chronological activity history for a task, preserved even after soft deletion.",
)
def get_task_activity_history(
    event_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[TaskActivity]:
    """Retrieve chronological activity log for a task (works for both active and soft-deleted tasks)."""
    # Verify task exists and belongs to this event (include soft-deleted tasks)
    get_task_or_404(event_id=event_id, task_id=task_id, db=db, include_deleted=True)

    stmt = (
        select(TaskActivity)
        .where(
            TaskActivity.event_id == event_id,
            TaskActivity.task_id == task_id,
        )
        .order_by(TaskActivity.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())
