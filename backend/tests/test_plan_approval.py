"""Automated tests for Plan Approval and Database Persistence (Phase 8D).

Verifies transactional atomicity, independent backend validation, idempotency protection,
task dependency cycle detection, rollback on errors, and non-fabrication of missing dates/budgets.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from decimal import Decimal
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.models.approval import PlanApproval
from app.models.budget import BudgetLineItem, EventBudget
from app.models.event import Event, EventRequirement
from app.models.task import EventTask, TaskActivity, TaskDependency
from app.schemas.planning import (
    BudgetCategoryAllocation,
    GeneratedEventPlan,
    PlanBudgetProposal,
    PlanEventBrief,
    PlanPersonalizedIdeas,
    PlanTimelineTask,
    TaskDependencySpec,
    VendorChecklistItem,
)
from app.services.budget_engine import calculate_budget
from app.services.planning_engine import generate_deterministic_plan
from app.schemas.planning import PlanGenerationRequest


def _build_test_plan(
    event_name: str = "Priya & Rahul Wedding",
    event_type: str = "wedding",
    event_date: str = "2026-11-20",
    guest_count: int = 150,
    target_budget: Decimal = Decimal("500000.00"),
    currency: str = "INR",
) -> GeneratedEventPlan:
    """Helper to construct a fully valid structured plan for test approval."""
    brief = PlanEventBrief(
        event_name=event_name,
        event_type=event_type,
        location="Bengaluru",
        event_date=event_date,
        expected_guest_count=guest_count,
        target_budget=target_budget,
        currency=currency,
        description=f"Grand {event_type} celebration in Bengaluru",
    )

    budget_proposal = PlanBudgetProposal(
        allocations=[
            BudgetCategoryAllocation(
                category="venue",
                suggested_amount=Decimal("150000.00"),
                currency=currency,
                rationale="Banquet hall rental",
                source_type="market_estimate",
            ),
            BudgetCategoryAllocation(
                category="catering",
                suggested_amount=Decimal("200000.00"),
                currency=currency,
                rationale="Buffet catering for guests",
                source_type="market_estimate",
            ),
            BudgetCategoryAllocation(
                category="contingency",
                suggested_amount=Decimal("50000.00"),
                currency=currency,
                rationale="10% unforeseen reserve buffer",
                source_type="contingency",
            ),
        ],
        total_allocated=Decimal("400000.00"),
        contingency_amount=Decimal("50000.00"),
        target_budget=target_budget,
        remaining_budget=Decimal("100000.00"),
        is_within_budget=True,
        currency=currency,
    )

    vendor_checklist = [
        VendorChecklistItem(
            category="venue",
            requirement_title="Banquet Hall Booking",
            description="Book banquet hall for 150 attendees",
            suggested_quantity_or_capacity="150 guests capacity",
            priority="high",
            important_questions_to_ask=["Does it include parking?", "What is curfew time?"],
            selection_considerations=["Air conditioning", "In-house power backup"],
        ),
        VendorChecklistItem(
            category="catering",
            requirement_title="Catering Package Selection",
            description="Multi-cuisine lunch and dinner menu",
            suggested_quantity_or_capacity="150 pax buffet",
            priority="high",
            important_questions_to_ask=["Do you offer tasting sessions?", "Is service staff included?"],
            selection_considerations=["Live counters", "Mineral water bottles"],
        ),
    ]

    timeline = [
        PlanTimelineTask(
            stage="initial_planning",
            task_title="Confirm Venue Booking",
            description="Finalize contract and pay advance for banquet hall",
            relative_timing="6 months before event",
            suggested_due_date=date(2026, 5, 20) if event_date else None,
            category="venue",
            priority="high",
            why_it_matters="Venue anchors all downstream vendor coordination",
            dependencies=[],
        ),
        PlanTimelineTask(
            stage="vendor_booking",
            task_title="Finalize Catering Menu",
            description="Lock menu choices and dietary options",
            relative_timing="4 months before event",
            suggested_due_date=date(2026, 7, 20) if event_date else None,
            category="catering",
            priority="high",
            why_it_matters="Caterer needs final headcount and menu selection",
            dependencies=["Confirm Venue Booking"],
        ),
    ]

    ideas = PlanPersonalizedIdeas(
        theme="Modern Minimalist",
        creative_touches=["Live calligraphy placecards"],
        cost_saving_tips=["Use seasonal flowers"],
        guest_experience_ideas=["Signature welcome mocktails"],
    )

    return GeneratedEventPlan(
        brief=brief,
        budget_proposal=budget_proposal,
        vendor_checklist=vendor_checklist,
        timeline=timeline,
        personalized_ideas=ideas,
        provider="deterministic_fallback",
        model="deterministic-v1",
        is_live_ai=False,
        status="draft",
        disclaimer="AI-generated plan.",
    )


def test_approve_plan_success(client: TestClient, db_session: Session):
    """Verify successful approval commits Event, Requirements, Budget, LineItems, Tasks, Dependencies, and Activities."""
    plan = _build_test_plan()
    idempotency_key = f"test-key-{uuid.uuid4()}"

    payload = {
        "plan": plan.model_dump(mode="json"),
        "idempotency_key": idempotency_key,
        "confirm_approval": True,
        "initial_event_status": "planning",
    }

    response = client.post("/api/v1/assistant/plan/approve", json=payload)
    assert response.status_code == 201, response.text
    data = response.json()

    assert data["success"] is True
    assert data["idempotency_key"] == idempotency_key
    assert data["event_name"] == "Priya & Rahul Wedding"
    assert data["event_type"] == "wedding"
    assert data["created_requirements_count"] == 2
    assert data["created_line_items_count"] == 3
    assert data["created_tasks_count"] == 2
    assert data["created_dependencies_count"] == 1
    assert data["financial_summary"]["total_allocated"] == "400000.00"
    assert data["financial_summary"]["currency"] == "INR"

    event_id = uuid.UUID(data["event_id"])
    budget_id = uuid.UUID(data["budget_id"])

    # Directly verify database persistence
    db_event = db_session.query(Event).filter(Event.id == event_id).first()
    assert db_event is not None
    assert db_event.name == "Priya & Rahul Wedding"
    assert db_event.expected_attendees == 150
    assert db_event.event_date == date(2026, 11, 20)
    assert db_event.city == "Bengaluru"

    # Verify requirements
    requirements = db_session.query(EventRequirement).filter(EventRequirement.event_id == event_id).all()
    assert len(requirements) == 2
    req_titles = {r.title for r in requirements}
    assert "Banquet Hall Booking" in req_titles
    assert "Catering Package Selection" in req_titles

    # Verify budget and line items
    db_budget = db_session.query(EventBudget).filter(EventBudget.id == budget_id).first()
    assert db_budget is not None
    assert db_budget.allocated_amount == Decimal("500000.00")
    assert db_budget.status == "active"

    line_items = db_session.query(BudgetLineItem).filter(BudgetLineItem.budget_id == budget_id).all()
    assert len(line_items) == 3
    line_cats = {li.category for li in line_items}
    assert "venue" in line_cats
    assert "catering" in line_cats

    # Verify tasks, dependencies, and audit activity
    tasks = db_session.query(EventTask).filter(EventTask.event_id == event_id).all()
    assert len(tasks) == 2
    task_map = {t.title: t for t in tasks}
    assert "Confirm Venue Booking" in task_map
    assert "Finalize Catering Menu" in task_map

    venue_task = task_map["Confirm Venue Booking"]
    catering_task = task_map["Finalize Catering Menu"]

    deps = db_session.query(TaskDependency).filter(TaskDependency.successor_task_id == catering_task.id).all()
    assert len(deps) == 1
    assert deps[0].predecessor_task_id == venue_task.id

    # Verify TaskActivity audit records
    activities = db_session.query(TaskActivity).filter(TaskActivity.event_id == event_id).all()
    assert len(activities) == 2
    for act in activities:
        assert act.action_type == "created"
        assert "plan commitment" in act.description

    # Verify PlanApproval record
    approval = db_session.query(PlanApproval).filter(PlanApproval.idempotency_key == idempotency_key).first()
    assert approval is not None
    assert approval.event_id == event_id
    assert approval.approval_confirmed is True


def test_approve_plan_rejects_without_explicit_confirmation(client: TestClient, db_session: Session):
    """Verify that approval is strictly rejected when confirm_approval is False."""
    plan = _build_test_plan()
    idempotency_key = f"test-unconfirmed-{uuid.uuid4()}"

    payload = {
        "plan": plan.model_dump(mode="json"),
        "idempotency_key": idempotency_key,
        "confirm_approval": False,
    }

    response = client.post("/api/v1/assistant/plan/approve", json=payload)
    assert response.status_code == 400
    assert "Explicit approval confirmation" in response.json()["detail"]

    # Verify zero database records created
    assert db_session.query(Event).count() == 0
    assert db_session.query(EventBudget).count() == 0
    assert db_session.query(PlanApproval).count() == 0


def test_approve_plan_idempotency(client: TestClient, db_session: Session):
    """Verify submitting the same idempotency key twice returns cached response with no duplicate rows."""
    plan = _build_test_plan()
    idempotency_key = f"idempotent-key-{uuid.uuid4()}"

    payload = {
        "plan": plan.model_dump(mode="json"),
        "idempotency_key": idempotency_key,
        "confirm_approval": True,
    }

    # First submission
    res1 = client.post("/api/v1/assistant/plan/approve", json=payload)
    assert res1.status_code == 201
    data1 = res1.json()

    # Second submission with EXACT same key
    res2 = client.post("/api/v1/assistant/plan/approve", json=payload)
    assert res2.status_code == 201
    data2 = res2.json()

    # Verify identical IDs
    assert data1["event_id"] == data2["event_id"]
    assert data1["budget_id"] == data2["budget_id"]
    assert data1["idempotency_key"] == data2["idempotency_key"]

    # Verify row counts in database: exactly 1 event, not 2!
    events = db_session.query(Event).all()
    assert len(events) == 1
    budgets = db_session.query(EventBudget).all()
    assert len(budgets) == 1
    approvals = db_session.query(PlanApproval).all()
    assert len(approvals) == 1


def test_approve_plan_validation_failures(client: TestClient):
    """Verify independent backend validation blocks invalid plan payloads."""
    # 1. Missing event name
    plan = _build_test_plan()
    plan.brief.event_name = ""
    res = client.post(
        "/api/v1/assistant/plan/approve",
        json={"plan": plan.model_dump(mode="json"), "idempotency_key": "k1", "confirm_approval": True},
    )
    assert res.status_code == 422
    assert "Event name is required" in res.json()["detail"]

    # 2. Negative target budget
    plan = _build_test_plan()
    raw_payload = {
        "plan": plan.model_dump(mode="json"),
        "idempotency_key": "k2",
        "confirm_approval": True,
    }
    raw_payload["plan"]["brief"]["target_budget"] = -500.00
    res = client.post("/api/v1/assistant/plan/approve", json=raw_payload)
    assert res.status_code == 422

    # 3. Currency mismatch
    plan = _build_test_plan(currency="INR")
    plan.budget_proposal.allocations[0].currency = "USD"
    res = client.post(
        "/api/v1/assistant/plan/approve",
        json={"plan": plan.model_dump(mode="json"), "idempotency_key": "k3", "confirm_approval": True},
    )
    assert res.status_code == 422
    assert "Currency mismatch" in res.json()["detail"]

    # 4. Empty idempotency key
    plan = _build_test_plan()
    res = client.post(
        "/api/v1/assistant/plan/approve",
        json={"plan": plan.model_dump(mode="json"), "idempotency_key": "   ", "confirm_approval": True},
    )
    assert res.status_code == 422
    assert "Idempotency key is required" in res.json()["detail"]


def test_approve_plan_task_dependency_validation(client: TestClient):
    """Verify task dependency validation rejects unknown predecessors, self-dependencies, and cycles."""
    # 1. Unknown predecessor
    plan = _build_test_plan()
    plan.timeline[1].dependencies = ["Non-existent Task Name"]
    res1 = client.post(
        "/api/v1/assistant/plan/approve",
        json={"plan": plan.model_dump(mode="json"), "idempotency_key": f"dep1-{uuid.uuid4()}", "confirm_approval": True},
    )
    assert res1.status_code == 422
    assert "unknown predecessor" in res1.json()["detail"]

    # 2. Self-dependency
    plan = _build_test_plan()
    plan.timeline[0].dependencies = [plan.timeline[0].task_title]
    res2 = client.post(
        "/api/v1/assistant/plan/approve",
        json={"plan": plan.model_dump(mode="json"), "idempotency_key": f"dep2-{uuid.uuid4()}", "confirm_approval": True},
    )
    assert res2.status_code == 422
    assert "Self-dependency detected" in res2.json()["detail"]

    # 3. Cycle dependency (Task A -> Task B and Task B -> Task A)
    plan = _build_test_plan()
    plan.timeline[0].dependencies = [plan.timeline[1].task_title]
    plan.timeline[1].dependencies = [plan.timeline[0].task_title]
    res3 = client.post(
        "/api/v1/assistant/plan/approve",
        json={"plan": plan.model_dump(mode="json"), "idempotency_key": f"dep3-{uuid.uuid4()}", "confirm_approval": True},
    )
    assert res3.status_code == 422
    assert "Cyclic task dependency detected" in res3.json()["detail"]


def test_approve_plan_transactional_rollback_on_failure(client: TestClient, db_session: Session):
    """Verify that an unexpected error during commitment cleanly rolls back all created records."""
    plan = _build_test_plan()
    idempotency_key = f"rollback-key-{uuid.uuid4()}"

    # Inject a failure during EventBudget creation
    with patch("app.services.plan_approval_service.EventBudget", side_effect=RuntimeError("Simulated database failure")):
        res = client.post(
            "/api/v1/assistant/plan/approve",
            json={"plan": plan.model_dump(mode="json"), "idempotency_key": idempotency_key, "confirm_approval": True},
        )
        assert res.status_code == 500
        assert "Database transaction failed" in res.json()["detail"]

    # Verify that the entire transaction was rolled back: ZERO events, ZERO budgets, ZERO approvals
    assert db_session.query(Event).count() == 0
    assert db_session.query(EventRequirement).count() == 0
    assert db_session.query(EventBudget).count() == 0
    assert db_session.query(BudgetLineItem).count() == 0
    assert db_session.query(EventTask).count() == 0
    assert db_session.query(TaskActivity).count() == 0
    assert db_session.query(PlanApproval).count() == 0


def test_approve_plan_preserves_missing_date_and_budget(client: TestClient, db_session: Session):
    """Verify that when event_date and budget are omitted, they are preserved as None without fabrication."""
    plan = _build_test_plan(event_date=None, target_budget=None)
    # Ensure timeline tasks have None due_date
    for t in plan.timeline:
        t.suggested_due_date = None

    idempotency_key = f"missing-date-budget-{uuid.uuid4()}"
    res = client.post(
        "/api/v1/assistant/plan/approve",
        json={"plan": plan.model_dump(mode="json"), "idempotency_key": idempotency_key, "confirm_approval": True},
    )
    assert res.status_code == 201
    data = res.json()

    assert data["event_date"] is None
    assert data["financial_summary"]["target_budget"] is None

    event_id = uuid.UUID(data["event_id"])
    budget_id = uuid.UUID(data["budget_id"])

    # Directly verify database record
    db_event = db_session.query(Event).filter(Event.id == event_id).first()
    assert db_event.event_date is None

    # Check tasks: due dates must be None
    tasks = db_session.query(EventTask).filter(EventTask.event_id == event_id).all()
    for t in tasks:
        assert t.due_date is None

    # Check budget: allocated amount must be None
    db_budget = db_session.query(EventBudget).filter(EventBudget.id == budget_id).first()
    assert db_budget.allocated_amount is None


# ============================================================================
# Phase 8D.1 Audit Verification Tests: Tax, Contingency, Idempotency & Types
# ============================================================================


def test_tax_unspecified_preserves_without_inferring_category_rate(client: TestClient, db_session: Session):
    """Verify that when tax is unspecified, tax_rate is 0.00 and notes indicate unspecified (never inferring 18%)."""
    plan = _build_test_plan()
    # Explicitly verify tax_rate is None (unspecified) for venue, catering, decoration
    for alloc in plan.budget_proposal.allocations:
        alloc.tax_rate = None
        alloc.tax_included = None

    idempotency_key = f"unspecified-tax-{uuid.uuid4()}"
    res = client.post(
        "/api/v1/assistant/plan/approve",
        json={"plan": plan.model_dump(mode="json"), "idempotency_key": idempotency_key, "confirm_approval": True},
    )
    assert res.status_code == 201
    data = res.json()

    budget_id = uuid.UUID(data["budget_id"])
    line_items = db_session.query(BudgetLineItem).filter(BudgetLineItem.budget_id == budget_id).all()

    for li in line_items:
        # Crucial check: tax_rate MUST NOT be 18.00! It must be 0.00 because tax was unspecified
        assert li.tax_rate == Decimal("0.00")
        assert "Tax: unspecified" in li.notes

    # Financial summary tax must be 0.00
    assert Decimal(str(data["financial_summary"]["total_tax"])) == Decimal("0.00")


def test_tax_explicit_preservation(client: TestClient, db_session: Session):
    """Verify that explicitly reviewed and approved tax rates and inclusion flags are preserved."""
    plan = _build_test_plan()
    # Set explicit tax rates
    plan.budget_proposal.allocations[0].tax_rate = Decimal("12.00")
    plan.budget_proposal.allocations[0].tax_included = True

    plan.budget_proposal.allocations[1].tax_rate = Decimal("5.00")
    plan.budget_proposal.allocations[1].tax_included = False

    idempotency_key = f"explicit-tax-{uuid.uuid4()}"
    res = client.post(
        "/api/v1/assistant/plan/approve",
        json={"plan": plan.model_dump(mode="json"), "idempotency_key": idempotency_key, "confirm_approval": True},
    )
    assert res.status_code == 201
    data = res.json()

    budget_id = uuid.UUID(data["budget_id"])
    line_items = db_session.query(BudgetLineItem).filter(BudgetLineItem.budget_id == budget_id).all()
    li_map = {li.category: li for li in line_items}

    # Venue was 12.00% inclusive
    assert li_map["venue"].tax_rate == Decimal("12.00")
    assert li_map["venue"].tax_included is True
    assert "Tax: 12.00% (inc)" in li_map["venue"].notes

    # Catering was 5.00% exclusive
    assert li_map["catering"].tax_rate == Decimal("5.00")
    assert li_map["catering"].tax_included is False
    assert "Tax: 5.00% (exc)" in li_map["catering"].notes

    # Total tax in summary must be > 0 and accurately calculated
    assert Decimal(str(data["financial_summary"]["total_tax"])) > Decimal("0.00")


def test_contingency_user_approved_preservation(client: TestClient, db_session: Session):
    """Verify that user-approved contingency percentage (e.g. 15%) is persisted, not replaced by 10%."""
    plan = _build_test_plan()
    plan.budget_proposal.contingency_percentage = Decimal("15.00")

    idempotency_key = f"user-contingency-{uuid.uuid4()}"
    res = client.post(
        "/api/v1/assistant/plan/approve",
        json={
            "plan": plan.model_dump(mode="json"),
            "idempotency_key": idempotency_key,
            "confirm_approval": True,
            "contingency_percentage": 15.00,
        },
    )
    assert res.status_code == 201
    data = res.json()

    budget_id = uuid.UUID(data["budget_id"])
    db_budget = db_session.query(EventBudget).filter(EventBudget.id == budget_id).first()

    assert db_budget.contingency_percentage == Decimal("15.00")
    assert Decimal(str(data["financial_summary"]["contingency_percentage"])) == Decimal("15.00")


def test_contingency_explicit_default_handling(client: TestClient, db_session: Session):
    """Verify default contingency percentage (10.00%) is explicitly persisted when not overridden."""
    plan = _build_test_plan()

    idempotency_key = f"default-contingency-{uuid.uuid4()}"
    res = client.post(
        "/api/v1/assistant/plan/approve",
        json={"plan": plan.model_dump(mode="json"), "idempotency_key": idempotency_key, "confirm_approval": True},
    )
    assert res.status_code == 201
    data = res.json()

    budget_id = uuid.UUID(data["budget_id"])
    db_budget = db_session.query(EventBudget).filter(EventBudget.id == budget_id).first()

    assert db_budget.contingency_percentage == Decimal("10.00")
    assert Decimal(str(data["financial_summary"]["contingency_percentage"])) == Decimal("10.00")


def test_budget_summary_and_saved_line_items_consistency(client: TestClient, db_session: Session):
    """Verify that calculate_budget on saved line items deterministically matches the returned financial summary."""
    plan = _build_test_plan()
    plan.budget_proposal.allocations[0].tax_rate = Decimal("18.00")
    plan.budget_proposal.allocations[0].tax_included = False

    idempotency_key = f"consistency-test-{uuid.uuid4()}"
    res = client.post(
        "/api/v1/assistant/plan/approve",
        json={"plan": plan.model_dump(mode="json"), "idempotency_key": idempotency_key, "confirm_approval": True},
    )
    assert res.status_code == 201
    data = res.json()

    budget_id = uuid.UUID(data["budget_id"])
    db_budget = db_session.query(EventBudget).filter(EventBudget.id == budget_id).first()
    saved_line_items = db_session.query(BudgetLineItem).filter(BudgetLineItem.budget_id == budget_id).all()

    # Recalculate using authoritative budget engine directly on database records
    calc = calculate_budget(
        items=saved_line_items,
        budget_currency=db_budget.currency,
        contingency_percentage=db_budget.contingency_percentage,
        allocated_amount=db_budget.allocated_amount,
        tax_policy=db_budget.tax_calculation_policy,
    )

    fin = data["financial_summary"]
    assert calc.raw_subtotal == Decimal(str(fin["total_allocated"]))
    assert calc.total_tax == Decimal(str(fin["total_tax"]))
    assert calc.contingency_amount == Decimal(str(fin["contingency_amount"]))
    assert calc.grand_total == Decimal(str(fin["grand_total"]))


def test_simultaneous_duplicate_approval_concurrency(client: TestClient, db_session: Session):
    """Verify that two simultaneous identical approval requests create only 1 event and return matching responses."""
    plan = _build_test_plan()
    shared_key = f"concurrent-key-{uuid.uuid4()}"

    payload = {
        "plan": plan.model_dump(mode="json"),
        "idempotency_key": shared_key,
        "confirm_approval": True,
    }

    def execute_post():
        return client.post("/api/v1/assistant/plan/approve", json=payload)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(execute_post)
        f2 = executor.submit(execute_post)
        res1 = f1.result()
        res2 = f2.result()

    assert res1.status_code == 201, res1.text
    assert res2.status_code == 201, res2.text

    data1 = res1.json()
    data2 = res2.json()

    # Both must reference the exact same event and budget
    assert data1["event_id"] == data2["event_id"]
    assert data1["budget_id"] == data2["budget_id"]
    assert data1["idempotency_key"] == shared_key

    # Database records must strictly not be duplicated
    assert db_session.query(Event).count() == 1
    assert db_session.query(EventBudget).count() == 1
    assert db_session.query(PlanApproval).count() == 1


def test_dependency_type_preservation(client: TestClient, db_session: Session):
    """Verify that supported dependency types (start_to_start, finish_to_finish, start_to_finish) are preserved."""
    plan = _build_test_plan()

    # Define 4 tasks with all 4 dependency types
    plan.timeline = [
        PlanTimelineTask(
            stage="initial",
            task_title="Book Venue",
            description="Secure banquet hall",
            relative_timing="6 months before",
            category="venue",
            priority="high",
            why_it_matters="Anchor venue",
            dependencies=[],
        ),
        PlanTimelineTask(
            stage="vendor",
            task_title="Coordinate Decor",
            description="Align theme with hall layout",
            relative_timing="5 months before",
            category="decoration",
            priority="medium",
            why_it_matters="Visual ambiance",
            dependencies=[
                TaskDependencySpec(predecessor_title="Book Venue", dependency_type="start_to_start")
            ],
        ),
        PlanTimelineTask(
            stage="vendor",
            task_title="Catering Tasting",
            description="Sample wedding menu",
            relative_timing="4 months before",
            category="catering",
            priority="high",
            why_it_matters="Food quality",
            dependencies=[
                TaskDependencySpec(predecessor_title="Coordinate Decor", dependency_type="finish_to_finish")
            ],
        ),
        PlanTimelineTask(
            stage="final",
            task_title="Final Walkthrough",
            description="Rehearse day-of schedule",
            relative_timing="1 week before",
            category="planning",
            priority="critical",
            why_it_matters="Execution readiness",
            dependencies=[
                TaskDependencySpec(predecessor_title="Catering Tasting", dependency_type="start_to_finish")
            ],
        ),
    ]

    idempotency_key = f"dep-types-{uuid.uuid4()}"
    res = client.post(
        "/api/v1/assistant/plan/approve",
        json={"plan": plan.model_dump(mode="json"), "idempotency_key": idempotency_key, "confirm_approval": True},
    )
    assert res.status_code == 201

    dependencies = db_session.query(TaskDependency).all()
    assert len(dependencies) == 3

    dep_types = {d.dependency_type for d in dependencies}
    assert "start_to_start" in dep_types
    assert "finish_to_finish" in dep_types
    assert "start_to_finish" in dep_types


def test_unsupported_dependency_type_rejected(client: TestClient):
    """Verify that invalid/unsupported dependency types are rejected with HTTP 422."""
    plan = _build_test_plan()
    raw_payload = {
        "plan": plan.model_dump(mode="json"),
        "idempotency_key": f"bad-dep-{uuid.uuid4()}",
        "confirm_approval": True,
    }
    # Inject unsupported dependency type
    raw_payload["plan"]["timeline"][1]["dependencies"] = [
        {"predecessor_title": plan.timeline[0].task_title, "dependency_type": "finish_to_middle"}
    ]

    res = client.post("/api/v1/assistant/plan/approve", json=raw_payload)
    assert res.status_code == 422
    assert "Unsupported dependency type 'finish_to_middle'" in res.json()["detail"]


def test_unsupported_tax_policy_rejected(client: TestClient):
    """Verify that invalid tax calculation policy is rejected with HTTP 422."""
    plan = _build_test_plan()
    res = client.post(
        "/api/v1/assistant/plan/approve",
        json={
            "plan": plan.model_dump(mode="json"),
            "idempotency_key": f"bad-tax-policy-{uuid.uuid4()}",
            "confirm_approval": True,
            "tax_calculation_policy": "arbitrary_tax_policy",
        },
    )
    assert res.status_code == 422
    assert "Unsupported tax calculation policy" in res.json()["detail"]

