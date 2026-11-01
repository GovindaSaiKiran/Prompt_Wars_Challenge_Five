"""Service for Human Approval, Plan Commitment, and Atomic Database Persistence.

Implements rigorous server-side validation, idempotency key verification,
dependency cycle detection, and transactional atomicity across Event, EventRequirement,
EventBudget, BudgetLineItem, EventTask, TaskDependency, and TaskActivity records.
"""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.approval import PlanApproval
from app.models.budget import BudgetLineItem, EventBudget
from app.models.event import Event, EventRequirement
from app.models.task import EventTask, TaskActivity, TaskDependency
from app.schemas.planning import (
    GeneratedEventPlan,
    PlanApprovalFinancialSummary,
    PlanApprovalRequest,
    PlanApprovalResponse,
    TaskDependencySpec,
)
from app.services.budget_engine import calculate_budget, quantize_money

logger = logging.getLogger("eventprice.plan_approval")

_approval_lock = threading.Lock()

VALID_REQUIREMENT_CATEGORIES = {
    "venue", "catering", "photography", "decoration", "entertainment",
    "transport", "accommodation", "equipment", "security", "other"
}

VALID_BUDGET_CATEGORIES = {
    "venue", "catering", "photography", "decoration", "entertainment",
    "transport", "accommodation", "equipment", "security", "other"
}

VALID_TASK_CATEGORIES = {
    "planning", "venue", "catering", "photography", "decoration",
    "entertainment", "transport", "accommodation", "finance",
    "invitations", "logistics", "other"
}

SUPPORTED_DEPENDENCY_TYPES = {
    "finish_to_start",
    "start_to_start",
    "finish_to_finish",
    "start_to_finish",
}


def parse_dependency_item(dep: Any) -> Tuple[str, str]:
    """Extracts (predecessor_title, dependency_type) from a string or dependency object.

    Validates that dependency_type is one of the supported types.
    """
    if isinstance(dep, dict):
        pred_title = str(dep.get("predecessor_title", "")).strip()
        dep_type = str(dep.get("dependency_type", "finish_to_start")).strip().lower()
    elif hasattr(dep, "predecessor_title"):
        pred_title = str(dep.predecessor_title).strip()
        dep_type = str(getattr(dep, "dependency_type", "finish_to_start")).strip().lower()
    elif isinstance(dep, str):
        raw = dep.strip()
        if raw.endswith(")") and "(" in raw:
            title_part, type_part = raw[:-1].rsplit("(", 1)
            candidate_type = type_part.strip().lower()
            if candidate_type in SUPPORTED_DEPENDENCY_TYPES or "_" in candidate_type:
                pred_title = title_part.strip()
                dep_type = candidate_type
            else:
                pred_title = raw
                dep_type = "finish_to_start"
        elif ":" in raw:
            title_part, type_part = raw.rsplit(":", 1)
            candidate_type = type_part.strip().lower()
            if candidate_type in SUPPORTED_DEPENDENCY_TYPES or "_" in candidate_type:
                pred_title = title_part.strip()
                dep_type = candidate_type
            else:
                pred_title = raw
                dep_type = "finish_to_start"
        else:
            pred_title = raw
            dep_type = "finish_to_start"
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid dependency specification: expected string or object, got {type(dep).__name__}",
        )

    if not pred_title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Dependency predecessor task title cannot be empty.",
        )

    if dep_type not in SUPPORTED_DEPENDENCY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported dependency type '{dep_type}'. "
                f"Supported types are: {', '.join(sorted(SUPPORTED_DEPENDENCY_TYPES))}."
            ),
        )

    return pred_title, dep_type


def normalize_category(cat: str, valid_set: Set[str]) -> str:
    """Maps diverse input category strings cleanly into valid database check constraints."""
    lower = cat.strip().lower()
    if lower in valid_set:
        return lower
    if lower in ("decor", "floral", "lighting", "styling"):
        return "decoration" if "decoration" in valid_set else "other"
    if lower in ("food", "beverage", "drinks", "dining"):
        return "catering" if "catering" in valid_set else "other"
    if lower in ("logistics", "audio_visual", "av", "sound"):
        return "equipment" if "equipment" in valid_set else "logistics" if "logistics" in valid_set else "other"
    if lower in ("buffer", "contingency", "reserve", "misc", "miscellaneous"):
        return "other"
    return "other"


def detect_task_dependency_cycles(timeline_tasks: list) -> None:
    """Validates task dependencies and verifies absence of self-dependencies and graph cycles."""
    task_titles = set()
    normalized_title_map = {}

    for t in timeline_tasks:
        title_clean = t.task_title.strip()
        if not title_clean:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="All timeline tasks must have a non-empty task_title.",
            )
        norm = title_clean.lower()
        task_titles.add(norm)
        normalized_title_map[norm] = title_clean

    # Graph adjacency: predecessor -> list of successors
    graph = defaultdict(list)
    in_degree = defaultdict(int)

    for norm in task_titles:
        in_degree[norm] = 0

    for t in timeline_tasks:
        succ_norm = t.task_title.strip().lower()
        for dep in t.dependencies:
            pred_title, _ = parse_dependency_item(dep)
            pred_norm = pred_title.strip().lower()
            if not pred_norm:
                continue

            # 1. Unknown task dependency check
            if pred_norm not in task_titles:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Task dependency error: '{t.task_title}' references unknown predecessor task '{pred_title}'.",
                )

            # 2. Self-dependency check
            if pred_norm == succ_norm:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Self-dependency detected: Task '{t.task_title}' cannot depend on itself.",
                )

            graph[pred_norm].append(succ_norm)
            in_degree[succ_norm] += 1

    # 3. Cycle Detection via Kahn's Algorithm
    queue = [node for node in task_titles if in_degree[node] == 0]
    visited_count = 0

    while queue:
        curr = queue.pop(0)
        visited_count += 1
        for neighbor in graph[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited_count != len(task_titles):
        # Cycle detected
        cycle_candidates = [normalized_title_map[node] for node in task_titles if in_degree[node] > 0]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cyclic task dependency detected involving milestones: {', '.join(cycle_candidates[:3])}.",
        )


def validate_plan_for_approval(request: PlanApprovalRequest) -> None:
    """Independently verifies plan parameters, bounds, currencies, and explicit confirmation."""
    # 1. Explicit human approval confirmation
    if not request.confirm_approval:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit approval confirmation ('confirm_approval=true') is required to commit the plan to the database.",
        )

    # 2. Idempotency Key validation
    key = request.idempotency_key.strip()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency key is required and cannot be empty.",
        )

    # 3. Tax policy and contingency overrides validation
    if request.tax_calculation_policy is not None:
        pol = request.tax_calculation_policy.strip().lower()
        if pol not in ("standard", "inclusive", "exclusive"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported tax calculation policy: '{request.tax_calculation_policy}'. Must be 'standard', 'inclusive', or 'exclusive'.",
            )

    if request.contingency_percentage is not None:
        if request.contingency_percentage < Decimal("0.00") or request.contingency_percentage > Decimal("100.00"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Contingency percentage must be between 0% and 100%.",
            )

    plan = request.plan
    brief = plan.brief

    # 4. Event Brief core field validation
    if not brief.event_name or not brief.event_name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Event name is required.",
        )

    if not brief.event_type or not brief.event_type.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Event type is required.",
        )

    if brief.expected_guest_count is not None and brief.expected_guest_count <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Expected guest count must be greater than zero.",
        )

    if brief.target_budget is not None and brief.target_budget < Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Target budget cannot be negative.",
        )

    brief_currency = (brief.currency or "INR").strip().upper()
    if len(brief_currency) != 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Currency must be a valid 3-letter ISO code.",
        )

    # 5. Budget allocations validation
    for alloc in plan.budget_proposal.allocations:
        if alloc.suggested_amount < Decimal("0.00"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Budget allocation for '{alloc.category}' cannot be negative.",
            )
        alloc_curr = (alloc.currency or brief_currency).strip().upper()
        if alloc_curr != brief_currency:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Currency mismatch in allocation '{alloc.category}': expected '{brief_currency}', got '{alloc_curr}'.",
            )

    # 6. Task dependencies validation & cycle check
    if plan.timeline:
        detect_task_dependency_cycles(plan.timeline)


def approve_and_commit_plan(db: Session, request: PlanApprovalRequest) -> PlanApprovalResponse:
    """Atomically commits an approved structured plan into database entities with idempotency."""
    # Step 1: Pre-validation
    validate_plan_for_approval(request)

    idempotency_key = request.idempotency_key.strip()

    with _approval_lock:
        # Step 2: Idempotency Check
        existing_approval = (
            db.query(PlanApproval)
            .filter(PlanApproval.idempotency_key == idempotency_key)
            .first()
        )
        if existing_approval:
            logger.info("Returning cached response for idempotency key: %s", idempotency_key)
            try:
                cached_data = json.loads(existing_approval.response_payload)
                return PlanApprovalResponse(**cached_data)
            except Exception as e:
                logger.warning("Failed to deserialize cached response: %s; re-querying event.", str(e))

        plan = request.plan
        brief = plan.brief
        clean_currency = (brief.currency or "INR").strip().upper()

        try:
            # Step 3: Transactional Persistence
            # A. Create Event
            new_event = Event(
                name=brief.event_name.strip(),
                event_type=brief.event_type.strip(),
                description=brief.description or f"AI-assisted planning for {brief.event_name}",
                event_date=brief.event_date,  # None if missing, NEVER fabricated!
                timezone="Asia/Kolkata",
                expected_attendees=brief.expected_guest_count,
                location_name=brief.location,
                city=brief.location,
                country="India",
                status=request.initial_event_status or "planning",
            )
            db.add(new_event)
            db.flush()  # Generates new_event.id

            # B. Create Event Requirements from Vendor Checklist
            created_requirements_count = 0
            for item in plan.vendor_checklist:
                req_cat = normalize_category(item.category, VALID_REQUIREMENT_CATEGORIES)
                prio = item.priority.lower() if item.priority.lower() in ("low", "medium", "high", "critical") else "medium"
                notes_str = "; ".join(item.important_questions_to_ask) if item.important_questions_to_ask else None

                requirement = EventRequirement(
                    event_id=new_event.id,
                    category=req_cat,
                    title=item.requirement_title.strip()[:255],
                    description=item.description,
                    quantity=Decimal("1.00"),
                    unit="service",
                    priority=prio,
                    notes=notes_str,
                )
                db.add(requirement)
                created_requirements_count += 1

            # C. Create Event Budget
            # Resolve approved contingency percentage and tax calculation policy
            approved_contingency_pct = Decimal("10.00")
            if request.contingency_percentage is not None:
                approved_contingency_pct = quantize_money(request.contingency_percentage)
            elif getattr(plan.budget_proposal, "contingency_percentage", None) is not None:
                approved_contingency_pct = quantize_money(plan.budget_proposal.contingency_percentage)

            resolved_tax_policy = "standard"
            if request.tax_calculation_policy is not None:
                cand = request.tax_calculation_policy.strip().lower()
                if cand in ("standard", "inclusive", "exclusive"):
                    resolved_tax_policy = cand
            elif getattr(plan.budget_proposal, "tax_calculation_policy", None) in ("standard", "inclusive", "exclusive"):
                resolved_tax_policy = plan.budget_proposal.tax_calculation_policy

            target_budget = quantize_money(brief.target_budget) if brief.target_budget is not None else None

            new_budget = EventBudget(
                event_id=new_event.id,
                name=f"{brief.event_name} Baseline Budget",
                currency=clean_currency,
                allocated_amount=target_budget,  # None if client did not supply budget ceiling!
                contingency_percentage=approved_contingency_pct,
                tax_calculation_policy=resolved_tax_policy,
                status="active",
            )
            db.add(new_budget)
            db.flush()  # Generates new_budget.id

            # D. Create Budget Line Items
            created_line_items: List[BudgetLineItem] = []
            created_line_items_count = 0
            for alloc in plan.budget_proposal.allocations:
                line_cat = normalize_category(alloc.category, VALID_BUDGET_CATEGORIES)
                alloc_amt = quantize_money(alloc.suggested_amount)

                # TAX HANDLING: Never invent or infer a tax rate from a vendor category!
                # Preserve explicitly reviewed and approved tax values; if unspecified, represent as unspecified.
                is_tax_unspecified = alloc.tax_rate is None
                line_tax_rate = quantize_money(alloc.tax_rate) if alloc.tax_rate is not None else Decimal("0.00")
                line_tax_included = bool(alloc.tax_included) if alloc.tax_included is not None else False

                tax_provenance = "unspecified" if is_tax_unspecified else f"{line_tax_rate}% ({'inc' if line_tax_included else 'exc'})"
                notes_str = f"Source: {alloc.source_type} | Tax: {tax_provenance}"

                line_item = BudgetLineItem(
                    budget_id=new_budget.id,
                    category=line_cat,
                    description=(alloc.rationale or f"{alloc.category.title()} Allocation")[:255],
                    quantity=Decimal("1.00"),
                    unit="package",
                    unit_price=alloc_amt,
                    currency=clean_currency,
                    tax_included=line_tax_included,
                    tax_rate=line_tax_rate,
                    discount_amount=Decimal("0.00"),
                    notes=notes_str,
                )
                db.add(line_item)
                created_line_items.append(line_item)
                created_line_items_count += 1

            # Calculate authoritative budget totals deterministically using existing budget engine
            calc_result = calculate_budget(
                items=created_line_items,
                budget_currency=clean_currency,
                contingency_percentage=approved_contingency_pct,
                allocated_amount=target_budget,
                tax_policy=resolved_tax_policy,
            )

            # E. Create Event Tasks & Activity Log
            created_tasks_count = 0
            title_to_task_map: Dict[str, EventTask] = {}

            for t in plan.timeline:
                task_cat = normalize_category(t.category, VALID_TASK_CATEGORIES)
                prio = t.priority.lower() if t.priority.lower() in ("low", "medium", "high", "critical") else "medium"

                new_task = EventTask(
                    event_id=new_event.id,
                    title=t.task_title.strip()[:255],
                    description=t.description,
                    category=task_cat,
                    status="pending",
                    priority=prio,
                    due_date=t.suggested_due_date,  # None if event_date is missing!
                    notes=f"Stage: {t.stage} ({t.relative_timing}). Context: {t.why_it_matters}",
                    currency=clean_currency,
                )
                db.add(new_task)
                db.flush()

                clean_title = t.task_title.strip().lower()
                title_to_task_map[clean_title] = new_task
                created_tasks_count += 1

                # Append initial activity audit entry
                activity = TaskActivity(
                    event_id=new_event.id,
                    task_id=new_task.id,
                    task_title=new_task.title,
                    action_type="created",
                    description="Task created via approved plan commitment",
                )
                db.add(activity)

            # F. Create Task Dependencies
            created_dependencies_count = 0
            for t in plan.timeline:
                succ_key = t.task_title.strip().lower()
                succ_task = title_to_task_map.get(succ_key)
                if not succ_task:
                    continue

                for dep_item in t.dependencies:
                    pred_title, dep_type = parse_dependency_item(dep_item)
                    pred_key = pred_title.strip().lower()
                    pred_task = title_to_task_map.get(pred_key)
                    if pred_task and pred_task.id != succ_task.id:
                        dependency = TaskDependency(
                            predecessor_task_id=pred_task.id,
                            successor_task_id=succ_task.id,
                            dependency_type=dep_type,
                        )
                        db.add(dependency)
                        created_dependencies_count += 1

            # G. Build Response & Save Idempotency Record
            fin_summary = PlanApprovalFinancialSummary(
                total_allocated=calc_result.raw_subtotal,
                contingency_amount=calc_result.contingency_amount,
                contingency_percentage=approved_contingency_pct,
                tax_calculation_policy=resolved_tax_policy,
                total_tax=calc_result.total_tax,
                grand_total=calc_result.grand_total,
                target_budget=target_budget,
                budget_provenance="user_approved",
                remaining_budget=calc_result.remaining_budget,
                is_within_budget=(not calc_result.is_over_budget) if target_budget is not None else None,
                currency=clean_currency,
            )

            response_obj = PlanApprovalResponse(
                success=True,
                event_id=new_event.id,
                event_name=new_event.name,
                event_type=new_event.event_type,
                status=new_event.status,
                location=new_event.location_name,
                expected_attendees=new_event.expected_attendees,
                event_date=new_event.event_date,
                created_requirements_count=created_requirements_count,
                budget_id=new_budget.id,
                created_line_items_count=created_line_items_count,
                created_tasks_count=created_tasks_count,
                created_dependencies_count=created_dependencies_count,
                financial_summary=fin_summary,
                message="Plan approved and successfully committed to database.",
                idempotency_key=idempotency_key,
                committed_at=datetime.now(timezone.utc),
            )

            # Save idempotency record
            approval_rec = PlanApproval(
                idempotency_key=idempotency_key,
                event_id=new_event.id,
                plan_id=plan.id,
                approval_confirmed=True,
                response_payload=response_obj.model_dump_json(),
            )
            db.add(approval_rec)

            # Commit transaction atomically
            db.commit()

            logger.info(
                "Successfully committed plan '%s' as Event %s with budget %s, %d tasks, %d dependencies.",
                plan.id, new_event.id, new_budget.id, created_tasks_count, created_dependencies_count,
            )

            return response_obj

        except (IntegrityError, OperationalError) as exc:
            db.rollback()
            logger.warning(
                "Conflict (%s) during plan approval commit (checking concurrent idempotency race): %s",
                type(exc).__name__,
                str(exc),
            )
            # Attempt recovery if a competing concurrent request already committed with this key
            for _ in range(5):
                concurrent_approval = (
                    db.query(PlanApproval)
                    .filter(PlanApproval.idempotency_key == idempotency_key)
                    .first()
                )
                if concurrent_approval:
                    logger.info("Successfully recovered concurrent idempotency record for key: %s", idempotency_key)
                    try:
                        cached_data = json.loads(concurrent_approval.response_payload)
                        return PlanApprovalResponse(**cached_data)
                    except Exception as parse_err:
                        logger.error("Failed to deserialize concurrent approval payload: %s", str(parse_err))
                        break
                time.sleep(0.05)

            if isinstance(exc, IntegrityError):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Database integrity conflict occurred during plan commitment.",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database operational error during plan commitment: {type(exc).__name__}",
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            logger.error("Transaction failed during plan approval: %s", str(exc), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database transaction failed during plan commitment: {type(exc).__name__}",
            )

