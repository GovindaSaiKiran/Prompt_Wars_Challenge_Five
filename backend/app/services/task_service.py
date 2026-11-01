"""Deterministic Event Task and Timeline Business Logic Service.

Provides deterministic dependency validation, cycle detection, status transition enforcement,
progress metrics, and chronological timeline generation without probabilistic or AI heuristics.
"""

from collections import defaultdict, deque
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import uuid

from sqlalchemy.orm import Session

from app.models.task import EventTask, TaskActivity, TaskDependency


TWO_PLACES = Decimal("0.01")


def quantize_currency(amount: Optional[Decimal]) -> Decimal:
    """Quantize decimal currency value to two decimal places."""
    if amount is None:
        return Decimal("0.00")
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ============================================================================
# Dependency Graph Validation & Cycle Detection
# ============================================================================


def would_create_cycle(
    existing_edges: Sequence[Tuple[uuid.UUID, uuid.UUID]],
    new_predecessor_id: uuid.UUID,
    new_successor_id: uuid.UUID,
) -> bool:
    """Determine if adding directed edge `new_predecessor_id -> new_successor_id` introduces a cycle.

    In a directed dependency graph, adding u -> v creates a cycle if and only if
    there is already a directed path from v to u (i.e. v can reach u).
    """
    if new_predecessor_id == new_successor_id:
        return True

    # Build adjacency list: node -> outgoing successors
    adj: Dict[uuid.UUID, List[uuid.UUID]] = defaultdict(list)
    for pred, succ in existing_edges:
        adj[pred].append(succ)

    # Search for path from new_successor_id to new_predecessor_id using BFS
    visited: Set[uuid.UUID] = set()
    queue = deque([new_successor_id])
    visited.add(new_successor_id)

    while queue:
        curr = queue.popleft()
        if curr == new_predecessor_id:
            return True
        for nxt in adj.get(curr, []):
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)

    return False


# ============================================================================
# Dependency Constraint Satisfaction
# ============================================================================


def evaluate_dependency_satisfaction(
    target_status: str,
    predecessor_dependencies: Sequence[TaskDependency],
) -> Tuple[bool, Optional[str]]:
    """Verify whether transitioning a task to `target_status` violates any dependency constraints.

    Dependency Rules:
    - finish_to_start: Predecessor must be 'completed' before successor can start ('in_progress' or 'completed').
    - start_to_start: Predecessor must be at least 'in_progress' or 'completed' before successor can start.
    - finish_to_finish: Predecessor must be 'completed' before successor can finish ('completed').
    - start_to_finish: Predecessor must be at least 'in_progress' or 'completed' before successor can finish.
    """
    is_starting = target_status in ("in_progress", "completed")
    is_completing = target_status == "completed"

    for dep in predecessor_dependencies:
        pred_task = dep.predecessor_task
        if not pred_task:
            continue
        if getattr(pred_task, "is_deleted", False):
            continue

        pred_title = pred_task.title
        pred_status = pred_task.status
        dep_type = dep.dependency_type

        if dep_type == "finish_to_start":
            if is_starting and pred_status != "completed":
                return (
                    False,
                    f"Cannot start task: predecessor '{pred_title}' ({pred_status}) "
                    f"must be completed (finish_to_start dependency).",
                )

        elif dep_type == "start_to_start":
            if is_starting and pred_status not in ("in_progress", "completed"):
                return (
                    False,
                    f"Cannot start task: predecessor '{pred_title}' ({pred_status}) "
                    f"has not started yet (start_to_start dependency).",
                )

        elif dep_type == "finish_to_finish":
            if is_completing and pred_status != "completed":
                return (
                    False,
                    f"Cannot complete task: predecessor '{pred_title}' ({pred_status}) "
                    f"must be completed first (finish_to_finish dependency).",
                )

        elif dep_type == "start_to_finish":
            if is_completing and pred_status not in ("in_progress", "completed"):
                return (
                    False,
                    f"Cannot complete task: predecessor '{pred_title}' ({pred_status}) "
                    f"has not started yet (start_to_finish dependency).",
                )

    return (True, None)


def check_task_dependency_status(
    task: EventTask,
) -> Tuple[bool, List[str]]:
    """Determine whether a task is currently blocked by unsatisfied incoming dependencies.

    Preserves the architectural distinction between:
    1. Manually blocked task: User explicitly set `task.status = 'blocked'`.
    2. Dependency-blocked task: Incoming predecessor dependencies are unsatisfied for its workflow state.
    """
    block_reasons: List[str] = []
    if not hasattr(task, "predecessor_dependencies") or not task.predecessor_dependencies:
        return False, block_reasons

    # Completed or cancelled tasks are no longer blocked by predecessors
    if task.status in ("completed", "cancelled"):
        return False, block_reasons

    for dep in task.predecessor_dependencies:
        pred_task = dep.predecessor_task
        if not pred_task:
            continue
        if getattr(pred_task, "is_deleted", False):
            continue

        pred_title = pred_task.title
        pred_status = pred_task.status
        dep_type = dep.dependency_type

        if dep_type == "finish_to_start":
            if pred_status != "completed":
                block_reasons.append(
                    f"Predecessor '{pred_title}' ({pred_status}) must be completed before this task can start (finish_to_start)."
                )

        elif dep_type == "start_to_start":
            if pred_status not in ("in_progress", "completed"):
                block_reasons.append(
                    f"Predecessor '{pred_title}' ({pred_status}) has not started yet (start_to_start)."
                )

        elif dep_type == "finish_to_finish":
            if task.status == "in_progress" and pred_status != "completed":
                block_reasons.append(
                    f"Predecessor '{pred_title}' ({pred_status}) must be completed before this task can finish (finish_to_finish)."
                )

        elif dep_type == "start_to_finish":
            if task.status == "in_progress" and pred_status not in ("in_progress", "completed"):
                block_reasons.append(
                    f"Predecessor '{pred_title}' ({pred_status}) has not started yet (start_to_finish)."
                )

    return (len(block_reasons) > 0, block_reasons)


# ============================================================================
# Activity Logging Helper
# ============================================================================


def record_task_activity(
    db: Session,
    event_id: uuid.UUID,
    task_id: Optional[uuid.UUID] = None,
    task_title: Optional[str] = None,
    action_type: str = "created",
    previous_value: Optional[str] = None,
    new_value: Optional[str] = None,
    description: Optional[str] = None,
) -> TaskActivity:
    """Append a new activity history record to the event's immutable audit log."""
    activity = TaskActivity(
        event_id=event_id,
        task_id=task_id,
        task_title=task_title,
        action_type=action_type,
        previous_value=previous_value,
        new_value=new_value,
        description=description,
    )
    db.add(activity)
    return activity


# ============================================================================
# Progress Summary & Metrics
# ============================================================================


def compute_progress_summary(
    tasks: Sequence[EventTask],
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Compute deterministic progress metrics for an event's active task set."""
    if today is None:
        today = datetime.now(timezone.utc).date()

    # Filter out soft-deleted tasks
    active_pool = [t for t in tasks if not getattr(t, "is_deleted", False)]
    total_tasks = len(active_pool)
    pending_count = 0
    in_progress_count = 0
    blocked_count = 0
    completed_count = 0
    cancelled_count = 0
    overdue_count = 0

    category_counts: Dict[str, int] = defaultdict(int)
    priority_counts: Dict[str, int] = defaultdict(int)
    total_estimated = Decimal("0.00")
    total_actual = Decimal("0.00")

    for task in active_pool:
        st = task.status
        if st == "pending":
            pending_count += 1
        elif st == "in_progress":
            in_progress_count += 1
        elif st == "blocked":
            blocked_count += 1
        elif st == "completed":
            completed_count += 1
        elif st == "cancelled":
            cancelled_count += 1

        category_counts[task.category] += 1
        priority_counts[task.priority] += 1

        if task.estimated_cost is not None:
            total_estimated += task.estimated_cost
        if task.actual_cost is not None:
            total_actual += task.actual_cost

        # Overdue: Incomplete and non-cancelled task where due_date < today
        if st not in ("completed", "cancelled") and task.due_date is not None:
            if task.due_date < today:
                overdue_count += 1

    # Active tasks = total minus cancelled
    active_tasks = total_tasks - cancelled_count
    if active_tasks > 0:
        completion_pct = Decimal(
            str(round((completed_count / active_tasks) * 100, 2))
        ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    else:
        completion_pct = Decimal("0.00")

    return {
        "total_tasks": total_tasks,
        "pending_tasks": pending_count,
        "in_progress_tasks": in_progress_count,
        "blocked_tasks": blocked_count,
        "completed_tasks": completed_count,
        "cancelled_tasks": cancelled_count,
        "active_tasks": active_tasks,
        "completion_percentage": completion_pct,
        "overdue_tasks": overdue_count,
        "tasks_by_category": dict(category_counts),
        "tasks_by_priority": dict(priority_counts),
        "total_estimated_cost": quantize_currency(total_estimated),
        "total_actual_cost": quantize_currency(total_actual),
    }


# ============================================================================
# Chronological Timeline Builder
# ============================================================================


def build_timeline_schedule(
    tasks: Sequence[EventTask],
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """Group tasks into chronological timeline slots and an unscheduled section."""
    if today is None:
        today = datetime.now(timezone.utc).date()

    date_buckets: Dict[date, List[Dict[str, Any]]] = defaultdict(list)
    unscheduled: List[Dict[str, Any]] = []

    for task in tasks:
        if getattr(task, "is_deleted", False):
            continue

        is_overdue = (
            task.status not in ("completed", "cancelled")
            and task.due_date is not None
            and task.due_date < today
        )
        is_dep_blocked, block_reasons = check_task_dependency_status(task)
        pred_count = len(task.predecessor_dependencies) if hasattr(task, "predecessor_dependencies") else 0
        succ_count = len(task.successor_dependencies) if hasattr(task, "successor_dependencies") else 0

        item_repr = {
            "id": task.id,
            "title": task.title,
            "category": task.category,
            "status": task.status,
            "priority": task.priority,
            "start_date": task.start_date,
            "due_date": task.due_date,
            "completed_at": task.completed_at,
            "assigned_to": task.assigned_to,
            "estimated_cost": task.estimated_cost,
            "actual_cost": task.actual_cost,
            "currency": task.currency,
            "is_overdue": is_overdue,
            "is_dependency_blocked": is_dep_blocked,
            "dependency_block_reasons": block_reasons,
            "predecessor_count": pred_count,
            "successor_count": succ_count,
        }

        if task.due_date is not None:
            date_buckets[task.due_date].append(item_repr)
        else:
            unscheduled.append(item_repr)

    # Sort chronological date buckets
    sorted_buckets = []
    for due_d in sorted(date_buckets.keys()):
        sorted_buckets.append({
            "due_date": due_d.isoformat(),
            "task_count": len(date_buckets[due_d]),
            "tasks": date_buckets[due_d],
        })

    return {
        "scheduled_groups": sorted_buckets,
        "unscheduled_tasks": unscheduled,
        "total_scheduled_tasks": sum(b["task_count"] for b in sorted_buckets),
        "total_unscheduled_tasks": len(unscheduled),
    }

