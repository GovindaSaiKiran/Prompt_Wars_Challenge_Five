"""Automated tests for Event Tasks, Timeline, Dependencies, Progress, and Activity Audit Log."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import uuid

import pytest
from fastapi.testclient import TestClient


# ============================================================================
# Helpers
# ============================================================================


def create_sample_event(client: TestClient, name: str = "Annual Tech Summit") -> dict:
    """Helper to create a test event."""
    res = client.post(
        "/api/v1/events/",
        json={"name": name, "event_type": "conference", "city": "Bengaluru"},
    )
    assert res.status_code == 201
    return res.json()


def create_sample_task(
    client: TestClient,
    event_id: str,
    title: str = "Book Venue",
    category: str = "venue",
    status: str = "pending",
    priority: str = "high",
    start_date: str = None,
    due_date: str = None,
    estimated_cost: float = None,
    assigned_to: str = None,
) -> dict:
    """Helper to create a test task."""
    payload = {
        "title": title,
        "category": category,
        "status": status,
        "priority": priority,
    }
    if start_date:
        payload["start_date"] = start_date
    if due_date:
        payload["due_date"] = due_date
    if estimated_cost is not None:
        payload["estimated_cost"] = estimated_cost
    if assigned_to:
        payload["assigned_to"] = assigned_to

    res = client.post(f"/api/v1/events/{event_id}/tasks/", json=payload)
    assert res.status_code == 201
    return res.json()


# ============================================================================
# 1. Category, Status, and Priority Exhaustive Tests
# ============================================================================


def test_task_all_categories_supported(client: TestClient):
    """Verify all 12 required categories are accepted and persisted, and invalid categories rejected."""
    event = create_sample_event(client, "Category Test Event")
    event_id = event["id"]

    required_categories = [
        "planning",
        "venue",
        "catering",
        "photography",
        "decoration",
        "entertainment",
        "transport",
        "accommodation",
        "finance",
        "invitations",
        "logistics",
        "other",
    ]

    for cat in required_categories:
        task = create_sample_task(
            client=client,
            event_id=event_id,
            title=f"Task for {cat}",
            category=cat,
        )
        assert task["category"] == cat

    # Reject invalid category
    bad_res = client.post(
        f"/api/v1/events/{event_id}/tasks/",
        json={"title": "Invalid Cat", "category": "invalid_cat"},
    )
    assert bad_res.status_code == 422


def test_task_all_statuses_and_priorities_supported(client: TestClient):
    """Verify all 5 required statuses and 4 required priorities are accepted, and deprecated values rejected."""
    event = create_sample_event(client, "Status Priority Event")
    event_id = event["id"]

    required_statuses = ["pending", "in_progress", "blocked", "completed", "cancelled"]
    required_priorities = ["low", "medium", "high", "critical"]

    for st in required_statuses:
        for pr in required_priorities:
            task = create_sample_task(
                client=client,
                event_id=event_id,
                title=f"Task {st}-{pr}",
                category="planning",
                status=st,
                priority=pr,
            )
            assert task["status"] == st
            assert task["priority"] == pr

    # Reject deprecated/unsupported statuses and priorities
    bad_status = client.post(
        f"/api/v1/events/{event_id}/tasks/",
        json={"title": "Bad Status", "status": "not_started"},
    )
    assert bad_status.status_code == 422

    bad_priority = client.post(
        f"/api/v1/events/{event_id}/tasks/",
        json={"title": "Bad Priority", "priority": "urgent"},
    )
    assert bad_priority.status_code == 422


# ============================================================================
# 2. Date Range, Overdue, and Pagination Filters
# ============================================================================


def test_task_due_date_range_and_overdue_filters(client: TestClient):
    """Verify inclusive due_date_from and due_date_to filters, invalid date bounds, and overdue_only."""
    event = create_sample_event(client, "Date Filter Event")
    event_id = event["id"]

    today = datetime.now(timezone.utc).date()
    d_past = today - timedelta(days=5)
    d_near = today + timedelta(days=3)
    d_far = today + timedelta(days=15)

    # Task 1: Overdue (due 5 days ago, status pending)
    t1 = create_sample_task(client, event_id, "Past Task", due_date=d_past.isoformat(), status="pending")
    # Task 2: Near future (due in 3 days)
    t2 = create_sample_task(client, event_id, "Near Task", due_date=d_near.isoformat(), status="pending")
    # Task 3: Far future (due in 15 days)
    t3 = create_sample_task(client, event_id, "Far Task", due_date=d_far.isoformat(), status="pending")
    # Task 4: Unscheduled (no due date)
    t4 = create_sample_task(client, event_id, "Unscheduled Task", status="pending")

    # 1. Filter: due_date_from and due_date_to covering past to near future
    res_range = client.get(
        f"/api/v1/events/{event_id}/tasks/",
        params={"due_date_from": d_past.isoformat(), "due_date_to": d_near.isoformat()},
    )
    assert res_range.status_code == 200
    ids_range = [t["id"] for t in res_range.json()["items"]]
    assert t1["id"] in ids_range
    assert t2["id"] in ids_range
    assert t3["id"] not in ids_range
    assert t4["id"] not in ids_range

    # 2. Invalid range: due_date_from > due_date_to -> 422
    res_invalid = client.get(
        f"/api/v1/events/{event_id}/tasks/",
        params={"due_date_from": d_far.isoformat(), "due_date_to": d_past.isoformat()},
    )
    assert res_invalid.status_code == 422

    # 3. Filter: overdue_only=true
    res_overdue = client.get(
        f"/api/v1/events/{event_id}/tasks/",
        params={"overdue_only": "true"},
    )
    assert res_overdue.status_code == 200
    overdue_items = res_overdue.json()["items"]
    assert len(overdue_items) == 1
    assert overdue_items[0]["id"] == t1["id"]


# ============================================================================
# 3. Validation Constraints (Negative Costs, Date Inversion)
# ============================================================================


def test_task_cost_and_date_order_validations(client: TestClient):
    """Verify rejection of negative costs and inverted dates (due_date < start_date)."""
    event = create_sample_event(client, "Validation Event")
    event_id = event["id"]

    # Inverted dates: due_date earlier than start_date -> 422
    res_inv_dates = client.post(
        f"/api/v1/events/{event_id}/tasks/",
        json={"title": "Inverted", "start_date": "2026-12-10", "due_date": "2026-12-01"},
    )
    assert res_inv_dates.status_code == 422

    # Negative estimated cost -> 422
    res_neg_est = client.post(
        f"/api/v1/events/{event_id}/tasks/",
        json={"title": "Negative Est", "estimated_cost": -50.0},
    )
    assert res_neg_est.status_code == 422

    # Negative actual cost -> 422
    res_neg_act = client.post(
        f"/api/v1/events/{event_id}/tasks/",
        json={"title": "Negative Act", "actual_cost": -10.0},
    )
    assert res_neg_act.status_code == 422


# ============================================================================
# 4. Task Completion, Reopening, and Timestamps
# ============================================================================


def test_task_completion_timestamp_consistency_and_reopening(client: TestClient):
    """Verify setting status to 'completed' sets completed_at, and reopening clears it."""
    event = create_sample_event(client, "Completion Event")
    event_id = event["id"]

    task = create_sample_task(client, event_id, "Key Task", status="pending")
    task_id = task["id"]
    assert task["completed_at"] is None

    # Complete task
    res_comp = client.patch(f"/api/v1/events/{event_id}/tasks/{task_id}", json={"status": "completed"})
    assert res_comp.status_code == 200
    completed_task = res_comp.json()
    assert completed_task["status"] == "completed"
    assert completed_task["completed_at"] is not None

    # Reopen task to in_progress
    res_reopen = client.patch(f"/api/v1/events/{event_id}/tasks/{task_id}", json={"status": "in_progress"})
    assert res_reopen.status_code == 200
    reopened_task = res_reopen.json()
    assert reopened_task["status"] == "in_progress"
    assert reopened_task["completed_at"] is None


# ============================================================================
# 5. Soft Deletion & Audit History Preservation
# ============================================================================


def test_activity_history_preserved_after_soft_deletion(client: TestClient):
    """Verify task deletion soft-deletes the task while preserving the immutable activity history."""
    event = create_sample_event(client, "Audit Trail Event")
    event_id = event["id"]

    task = create_sample_task(client, event_id, "Catering Setup", category="catering", priority="medium")
    task_id = task["id"]

    # Perform updates
    client.patch(f"/api/v1/events/{event_id}/tasks/{task_id}", json={"priority": "critical"})
    client.patch(f"/api/v1/events/{event_id}/tasks/{task_id}", json={"assigned_to": "Chef Raman"})
    client.patch(f"/api/v1/events/{event_id}/tasks/{task_id}", json={"due_date": "2026-11-20"})

    # Delete task
    del_res = client.delete(f"/api/v1/events/{event_id}/tasks/{task_id}")
    assert del_res.status_code == 204

    # Subsequent GET on task returns 404 (soft-deleted)
    get_res = client.get(f"/api/v1/events/{event_id}/tasks/{task_id}")
    assert get_res.status_code == 404

    # Task is excluded from active task list
    list_res = client.get(f"/api/v1/events/{event_id}/tasks/")
    assert list_res.status_code == 200
    assert task_id not in [t["id"] for t in list_res.json()["items"]]

    # Audit history is 100% PRESERVED and accessible
    act_res = client.get(f"/api/v1/events/{event_id}/tasks/{task_id}/activity")
    assert act_res.status_code == 200
    activities = act_res.json()

    assert len(activities) == 5
    action_types = [a["action_type"] for a in activities]
    assert action_types == [
        "created",
        "priority_changed",
        "assignment_changed",
        "due_date_changed",
        "deleted",
    ]

    # Modification/deletion of activity records is strictly rejected
    act_id = activities[0]["id"]
    assert client.put(f"/api/v1/events/{event_id}/tasks/{task_id}/activity/{act_id}").status_code in (404, 405)
    assert client.delete(f"/api/v1/events/{event_id}/tasks/{task_id}/activity/{act_id}").status_code in (404, 405)


# ============================================================================
# 6. Dependency Graph Integrity (Same-Event, Self-Dep, Duplicate, Cycle)
# ============================================================================


def test_same_event_self_dependency_and_duplicate_rejection(client: TestClient):
    """Verify dependencies enforce same-event membership, reject self-dependency and duplicates."""
    e1 = create_sample_event(client, "Event 1")
    e2 = create_sample_event(client, "Event 2")

    t1 = create_sample_task(client, e1["id"], "Task 1")
    t2 = create_sample_task(client, e1["id"], "Task 2")
    t_other = create_sample_task(client, e2["id"], "Task in Event 2")

    # 1. Self-dependency rejected -> 400
    res_self = client.post(
        f"/api/v1/events/{e1['id']}/tasks/{t1['id']}/dependencies",
        json={"predecessor_task_id": t1["id"], "dependency_type": "finish_to_start"},
    )
    assert res_self.status_code == 400
    assert "self-dependency" in res_self.json()["detail"].lower()

    # 2. Cross-event dependency rejected -> 400
    res_cross = client.post(
        f"/api/v1/events/{e1['id']}/tasks/{t1['id']}/dependencies",
        json={"predecessor_task_id": t_other["id"], "dependency_type": "finish_to_start"},
    )
    assert res_cross.status_code == 400
    assert "different event" in res_cross.json()["detail"].lower()

    # 3. Add valid dependency
    res_ok = client.post(
        f"/api/v1/events/{e1['id']}/tasks/{t2['id']}/dependencies",
        json={"predecessor_task_id": t1["id"], "dependency_type": "finish_to_start"},
    )
    assert res_ok.status_code == 201

    # 4. Duplicate dependency rejected -> 400
    res_dup = client.post(
        f"/api/v1/events/{e1['id']}/tasks/{t2['id']}/dependencies",
        json={"predecessor_task_id": t1["id"], "dependency_type": "finish_to_start"},
    )
    assert res_dup.status_code == 400
    assert "already exists" in res_dup.json()["detail"].lower()


def test_circular_dependency_cycle_detection(client: TestClient):
    """Verify DAG cycle detection prevents circular dependencies (2-node and 3-node loops)."""
    event = create_sample_event(client, "Cycle Test Event")
    event_id = event["id"]

    tA = create_sample_task(client, event_id, "Task A")
    tB = create_sample_task(client, event_id, "Task B")
    tC = create_sample_task(client, event_id, "Task C")

    # A -> B
    res_ab = client.post(
        f"/api/v1/events/{event_id}/tasks/{tB['id']}/dependencies",
        json={"predecessor_task_id": tA["id"], "dependency_type": "finish_to_start"},
    )
    assert res_ab.status_code == 201

    # B -> A creates 2-node cycle -> 400
    res_ba = client.post(
        f"/api/v1/events/{event_id}/tasks/{tA['id']}/dependencies",
        json={"predecessor_task_id": tB["id"], "dependency_type": "finish_to_start"},
    )
    assert res_ba.status_code == 400
    assert "circular dependency" in res_ba.json()["detail"].lower()

    # B -> C
    res_bc = client.post(
        f"/api/v1/events/{event_id}/tasks/{tC['id']}/dependencies",
        json={"predecessor_task_id": tB["id"], "dependency_type": "finish_to_start"},
    )
    assert res_bc.status_code == 201

    # C -> A creates 3-node cycle -> 400
    res_ca = client.post(
        f"/api/v1/events/{event_id}/tasks/{tA['id']}/dependencies",
        json={"predecessor_task_id": tC["id"], "dependency_type": "finish_to_start"},
    )
    assert res_ca.status_code == 400
    assert "circular dependency" in res_ca.json()["detail"].lower()


# ============================================================================
# 7. Independent Verification of All 4 Dependency Types
# ============================================================================


def test_dependency_type_finish_to_start(client: TestClient):
    """finish_to_start: Predecessor must be 'completed' before successor can start."""
    event = create_sample_event(client, "FS Event")
    event_id = event["id"]

    pred = create_sample_task(client, event_id, "Design Specs", status="pending")
    succ = create_sample_task(client, event_id, "Develop Code", status="pending")

    client.post(
        f"/api/v1/events/{event_id}/tasks/{succ['id']}/dependencies",
        json={"predecessor_task_id": pred["id"], "dependency_type": "finish_to_start"},
    )

    # 1. Predecessor is pending -> successor cannot start (in_progress)
    res_start_fail = client.patch(f"/api/v1/events/{event_id}/tasks/{succ['id']}", json={"status": "in_progress"})
    assert res_start_fail.status_code == 400
    assert "finish_to_start" in res_start_fail.json()["detail"]

    # 2. Predecessor moves to in_progress -> successor still cannot start
    client.patch(f"/api/v1/events/{event_id}/tasks/{pred['id']}", json={"status": "in_progress"})
    res_start_fail2 = client.patch(f"/api/v1/events/{event_id}/tasks/{succ['id']}", json={"status": "in_progress"})
    assert res_start_fail2.status_code == 400

    # 3. Predecessor completes -> successor can now start
    client.patch(f"/api/v1/events/{event_id}/tasks/{pred['id']}", json={"status": "completed"})
    res_start_ok = client.patch(f"/api/v1/events/{event_id}/tasks/{succ['id']}", json={"status": "in_progress"})
    assert res_start_ok.status_code == 200
    assert res_start_ok.json()["status"] == "in_progress"


def test_dependency_type_start_to_start(client: TestClient):
    """start_to_start: Predecessor must be at least 'in_progress' or 'completed' before successor can start."""
    event = create_sample_event(client, "SS Event")
    event_id = event["id"]

    pred = create_sample_task(client, event_id, "Stage Setup", status="pending")
    succ = create_sample_task(client, event_id, "Audio Check", status="pending")

    client.post(
        f"/api/v1/events/{event_id}/tasks/{succ['id']}/dependencies",
        json={"predecessor_task_id": pred["id"], "dependency_type": "start_to_start"},
    )

    # 1. Predecessor is pending -> successor cannot start
    res_fail = client.patch(f"/api/v1/events/{event_id}/tasks/{succ['id']}", json={"status": "in_progress"})
    assert res_fail.status_code == 400
    assert "start_to_start" in res_fail.json()["detail"]

    # 2. Predecessor starts (in_progress) -> successor can now start
    client.patch(f"/api/v1/events/{event_id}/tasks/{pred['id']}", json={"status": "in_progress"})
    res_ok = client.patch(f"/api/v1/events/{event_id}/tasks/{succ['id']}", json={"status": "in_progress"})
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "in_progress"


def test_dependency_type_finish_to_finish(client: TestClient):
    """finish_to_finish: Successor can start independently, but cannot 'completed' until predecessor is 'completed'."""
    event = create_sample_event(client, "FF Event")
    event_id = event["id"]

    pred = create_sample_task(client, event_id, "Filming Video", status="in_progress")
    succ = create_sample_task(client, event_id, "Editing Video", status="pending")

    client.post(
        f"/api/v1/events/{event_id}/tasks/{succ['id']}/dependencies",
        json={"predecessor_task_id": pred["id"], "dependency_type": "finish_to_finish"},
    )

    # 1. Successor can start even while predecessor is in_progress
    res_start = client.patch(f"/api/v1/events/{event_id}/tasks/{succ['id']}", json={"status": "in_progress"})
    assert res_start.status_code == 200

    # 2. Successor cannot complete while predecessor is incomplete
    res_finish_fail = client.patch(f"/api/v1/events/{event_id}/tasks/{succ['id']}", json={"status": "completed"})
    assert res_finish_fail.status_code == 400
    assert "finish_to_finish" in res_finish_fail.json()["detail"]

    # 3. Predecessor completes -> successor can now complete
    client.patch(f"/api/v1/events/{event_id}/tasks/{pred['id']}", json={"status": "completed"})
    res_finish_ok = client.patch(f"/api/v1/events/{event_id}/tasks/{succ['id']}", json={"status": "completed"})
    assert res_finish_ok.status_code == 200
    assert res_finish_ok.json()["status"] == "completed"


def test_dependency_type_start_to_finish(client: TestClient):
    """start_to_finish: Successor can start independently, but cannot 'completed' until predecessor starts."""
    event = create_sample_event(client, "SF Event")
    event_id = event["id"]

    pred = create_sample_task(client, event_id, "New Guard Shift", status="pending")
    succ = create_sample_task(client, event_id, "Old Guard Shift", status="in_progress")

    client.post(
        f"/api/v1/events/{event_id}/tasks/{succ['id']}/dependencies",
        json={"predecessor_task_id": pred["id"], "dependency_type": "start_to_finish"},
    )

    # 1. Successor cannot finish until predecessor starts
    res_finish_fail = client.patch(f"/api/v1/events/{event_id}/tasks/{succ['id']}", json={"status": "completed"})
    assert res_finish_fail.status_code == 400
    assert "start_to_finish" in res_finish_fail.json()["detail"]

    # 2. Predecessor starts (in_progress) -> successor can now finish
    client.patch(f"/api/v1/events/{event_id}/tasks/{pred['id']}", json={"status": "in_progress"})
    res_finish_ok = client.patch(f"/api/v1/events/{event_id}/tasks/{succ['id']}", json={"status": "completed"})
    assert res_finish_ok.status_code == 200
    assert res_finish_ok.json()["status"] == "completed"


# ============================================================================
# 8. Dependency Blocked vs. Manually Blocked Distinction
# ============================================================================


def test_dependency_blocked_vs_manually_blocked_distinction(client: TestClient):
    """Verify distinct representation of manual block (status='blocked') vs dependency block (is_dependency_blocked=True)."""
    event = create_sample_event(client, "Distinction Event")
    event_id = event["id"]

    t_pred = create_sample_task(client, event_id, "Predecessor Task", status="pending")
    t_succ = create_sample_task(client, event_id, "Successor Task", status="pending")

    client.post(
        f"/api/v1/events/{event_id}/tasks/{t_succ['id']}/dependencies",
        json={"predecessor_task_id": t_pred["id"], "dependency_type": "finish_to_start"},
    )

    # 1. Check t_succ status and flags: status is 'pending', is_dependency_blocked is True
    res_succ = client.get(f"/api/v1/events/{event_id}/tasks/{t_succ['id']}")
    assert res_succ.status_code == 200
    succ_data = res_succ.json()
    assert succ_data["status"] == "pending"  # NEVER silently overwritten!
    assert succ_data["is_dependency_blocked"] is True
    assert len(succ_data["dependency_block_reasons"]) > 0

    # 2. Manually block a different task
    t_manual = create_sample_task(client, event_id, "Manual Block Task", status="blocked")
    res_manual = client.get(f"/api/v1/events/{event_id}/tasks/{t_manual['id']}")
    assert res_manual.status_code == 200
    manual_data = res_manual.json()
    assert manual_data["status"] == "blocked"  # Manually blocked
    assert manual_data["is_dependency_blocked"] is False  # No dependency blocking it


# ============================================================================
# 9. Timeline & Progress with Missing / Incomplete Dates
# ============================================================================


def test_timeline_and_progress_with_incomplete_dates(client: TestClient):
    """Verify chronological timeline properly handles tasks without dates (backlog bucket)."""
    event = create_sample_event(client, "Timeline Test Event")
    event_id = event["id"]

    # Scheduled task with due date
    t_sched = create_sample_task(client, event_id, "Scheduled Task", due_date="2026-12-01", status="pending")
    # Backlog task without due date
    t_backlog = create_sample_task(client, event_id, "Backlog Task", status="pending")

    # 1. Timeline request
    res_tl = client.get(f"/api/v1/events/{event_id}/tasks/timeline")
    assert res_tl.status_code == 200
    tl = res_tl.json()

    assert tl["total_scheduled_tasks"] == 1
    assert tl["total_unscheduled_tasks"] == 1
    assert len(tl["scheduled_groups"]) == 1
    assert tl["scheduled_groups"][0]["tasks"][0]["id"] == t_sched["id"]
    assert tl["unscheduled_tasks"][0]["id"] == t_backlog["id"]

    # 2. Progress summary request
    res_prog = client.get(f"/api/v1/events/{event_id}/tasks/progress")
    assert res_prog.status_code == 200
    prog = res_prog.json()
    assert prog["total_tasks"] == 2
    assert prog["pending_tasks"] == 2
    assert Decimal(str(prog["completion_percentage"])) == Decimal("0.00")
