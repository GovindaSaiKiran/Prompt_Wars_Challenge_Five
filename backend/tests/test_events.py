"""Automated tests for Event and EventRequirement API endpoints, validation, and relationships."""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


# ============================================================================
# Event CRUD Tests
# ============================================================================


def test_create_and_retrieve_event(client: TestClient):
    """Verify event creation and retrieval with detailed response schema."""
    payload = {
        "name": "Emerald Jubilee Gala",
        "event_type": "Anniversary Gala",
        "description": "50th Anniversary grand celebration with dinner and live jazz.",
        "event_date": "2026-12-15",
        "start_time": "18:00:00",
        "end_time": "23:00:00",
        "timezone": "Asia/Kolkata",
        "expected_attendees": 200,
        "location_name": "Grand Palace Ballroom",
        "address": "42 Heritage Boulevard",
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "India",
        "status": "planning",
    }

    # 1. Create event
    response = client.post("/api/v1/events/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == payload["name"]
    assert data["event_type"] == payload["event_type"]
    assert data["status"] == "planning"
    assert data["expected_attendees"] == 200
    assert "created_at" in data
    assert "updated_at" in data

    event_id = data["id"]

    # 2. Retrieve event
    get_response = client.get(f"/api/v1/events/{event_id}")
    assert get_response.status_code == 200
    detail = get_response.json()
    assert detail["id"] == event_id
    assert detail["name"] == payload["name"]
    assert detail["requirements"] == []


def test_list_events_and_pagination(client: TestClient):
    """Verify pagination skip, limit bounds, and filtering."""
    # Create 5 events
    created_ids = []
    for i in range(5):
        res = client.post(
            "/api/v1/events/",
            json={
                "name": f"Conference Tech Wave {i}",
                "event_type": "Tech Summit",
                "city": "Bengaluru" if i % 2 == 0 else "Mumbai",
                "status": "confirmed" if i < 3 else "draft",
            },
        )
        assert res.status_code == 201
        created_ids.append(res.json()["id"])

    # Test pagination page 1
    page1 = client.get("/api/v1/events/?skip=0&limit=3")
    assert page1.status_code == 200
    p1_data = page1.json()
    assert p1_data["total"] == 5
    assert len(p1_data["items"]) == 3
    assert p1_data["skip"] == 0
    assert p1_data["limit"] == 3

    # Test pagination page 2
    page2 = client.get("/api/v1/events/?skip=3&limit=3")
    assert page2.status_code == 200
    p2_data = page2.json()
    assert p2_data["total"] == 5
    assert len(p2_data["items"]) == 2

    # Test status filter
    filter_res = client.get("/api/v1/events/?status=confirmed")
    assert filter_res.status_code == 200
    assert filter_res.json()["total"] == 3

    # Test city filter
    city_res = client.get("/api/v1/events/?city=Bengaluru")
    assert city_res.status_code == 200
    assert city_res.json()["total"] == 3

    # Test invalid pagination parameters
    assert client.get("/api/v1/events/?limit=0").status_code == 422
    assert client.get("/api/v1/events/?limit=101").status_code == 422
    assert client.get("/api/v1/events/?skip=-1").status_code == 422


def test_update_and_delete_event(client: TestClient):
    """Verify partial updates via PATCH and deletion via DELETE."""
    # Create event
    create_res = client.post(
        "/api/v1/events/",
        json={
            "name": "Design Sprint Kickoff",
            "event_type": "Workshop",
            "status": "draft",
        },
    )
    event_id = create_res.json()["id"]

    # PATCH partial update
    update_res = client.patch(
        f"/api/v1/events/{event_id}",
        json={
            "name": "Design Sprint Global Kickoff",
            "status": "confirmed",
            "expected_attendees": 45,
        },
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["name"] == "Design Sprint Global Kickoff"
    assert updated_data["status"] == "confirmed"
    assert updated_data["expected_attendees"] == 45

    # DELETE event
    del_res = client.delete(f"/api/v1/events/{event_id}")
    assert del_res.status_code == 204

    # Verify 404 upon subsequent retrieval
    get_res = client.get(f"/api/v1/events/{event_id}")
    assert get_res.status_code == 404
    assert "not found" in get_res.json()["detail"].lower()


# ============================================================================
# Event Requirement & Cascade Tests
# ============================================================================


def test_requirements_crud_and_cascade_deletion(client: TestClient):
    """Verify requirement creation, update, retrieval, and cascade deletion when parent event is deleted."""
    # 1. Create parent event
    event_res = client.post(
        "/api/v1/events/",
        json={"name": "Annual Founders Retreat", "event_type": "Retreat"},
    )
    event_id = event_res.json()["id"]

    # 2. Add requirement
    req_payload = {
        "category": "catering",
        "title": "Gourmet High-Tea Buffet",
        "description": "Artisanal pastries, sandwiches, and premium single-origin tea station.",
        "quantity": "75.00",
        "unit": "guests",
        "priority": "high",
        "notes": "Ensure dairy-free and gluten-free platters are clearly marked.",
    }
    req_res = client.post(f"/api/v1/events/{event_id}/requirements", json=req_payload)
    assert req_res.status_code == 201
    req_data = req_res.json()
    assert req_data["category"] == "catering"
    assert req_data["title"] == req_payload["title"]
    assert req_data["event_id"] == event_id
    assert Decimal(str(req_data["quantity"])) == Decimal("75.00")
    req_id = req_data["id"]

    # 3. Retrieve event with eager loaded requirements
    detail_res = client.get(f"/api/v1/events/{event_id}")
    assert detail_res.status_code == 200
    event_detail = detail_res.json()
    assert len(event_detail["requirements"]) == 1
    assert event_detail["requirements"][0]["id"] == req_id

    # 4. PATCH requirement
    update_res = client.patch(
        f"/api/v1/events/{event_id}/requirements/{req_id}",
        json={"priority": "critical", "quantity": "85.00"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["priority"] == "critical"
    assert Decimal(str(update_res.json()["quantity"])) == Decimal("85.00")

    # 5. Delete parent event and verify cascade deletion of requirement
    del_event_res = client.delete(f"/api/v1/events/{event_id}")
    assert del_event_res.status_code == 204

    # Ensure event is gone
    assert client.get(f"/api/v1/events/{event_id}").status_code == 404

    # Ensure requirement is not found
    assert client.delete(f"/api/v1/events/{event_id}/requirements/{req_id}").status_code == 404


def test_requirement_individual_deletion(client: TestClient):
    """Verify deleting a requirement individually does not delete the parent event."""
    event_res = client.post(
        "/api/v1/events/",
        json={"name": "Winter Hackathon", "event_type": "Hackathon"},
    )
    event_id = event_res.json()["id"]

    req_res = client.post(
        f"/api/v1/events/{event_id}/requirements",
        json={"category": "equipment", "title": "Gigabit Network Switches", "quantity": "4"},
    )
    req_id = req_res.json()["id"]

    # Delete requirement
    del_req = client.delete(f"/api/v1/events/{event_id}/requirements/{req_id}")
    assert del_req.status_code == 204

    # Event remains intact with 0 requirements
    detail = client.get(f"/api/v1/events/{event_id}").json()
    assert detail["requirements"] == []


# ============================================================================
# Validation & Error Handling Tests
# ============================================================================


def test_invalid_status_and_priority_values(client: TestClient):
    """Verify validation errors on invalid enum values."""
    # Invalid event status
    res = client.post(
        "/api/v1/events/",
        json={"name": "Bad Event", "event_type": "Test", "status": "unknown_status"},
    )
    assert res.status_code == 422

    # Create valid event
    event = client.post(
        "/api/v1/events/",
        json={"name": "Valid Event", "event_type": "Test"},
    ).json()

    # Invalid requirement priority
    bad_priority = client.post(
        f"/api/v1/events/{event['id']}/requirements",
        json={"category": "venue", "title": "Main Stage", "priority": "urgent"},
    )
    assert bad_priority.status_code == 422

    # Invalid requirement category
    bad_cat = client.post(
        f"/api/v1/events/{event['id']}/requirements",
        json={"category": "space_travel", "title": "Rocket"},
    )
    assert bad_cat.status_code == 422


def test_invalid_attendees_and_quantity_values(client: TestClient):
    """Verify validation errors for zero or negative attendees and quantities."""
    # Zero attendees
    assert client.post(
        "/api/v1/events/",
        json={"name": "Zero Guests", "event_type": "Test", "expected_attendees": 0},
    ).status_code == 422

    # Negative attendees
    assert client.post(
        "/api/v1/events/",
        json={"name": "Negative Guests", "event_type": "Test", "expected_attendees": -10},
    ).status_code == 422

    # Valid event
    event_id = client.post(
        "/api/v1/events/",
        json={"name": "Test Event", "event_type": "Test"},
    ).json()["id"]

    # Zero requirement quantity
    assert client.post(
        f"/api/v1/events/{event_id}/requirements",
        json={"category": "venue", "title": "Hall", "quantity": 0},
    ).status_code == 422

    # Negative requirement quantity
    assert client.post(
        f"/api/v1/events/{event_id}/requirements",
        json={"category": "venue", "title": "Hall", "quantity": -5.5},
    ).status_code == 422


def test_invalid_event_time_range(client: TestClient):
    """Verify validation when end_time is chronologically before start_time."""
    res = client.post(
        "/api/v1/events/",
        json={
            "name": "Time Travel Event",
            "event_type": "SciFi",
            "start_time": "18:00:00",
            "end_time": "12:00:00",
        },
    )
    assert res.status_code == 422
    assert "end_time must be strictly after start_time" in str(res.json())


def test_missing_event_and_requirement_responses(client: TestClient):
    """Verify structured 404 responses for non-existent entities."""
    random_id = uuid.uuid4()

    # Missing event GET / PATCH / DELETE
    assert client.get(f"/api/v1/events/{random_id}").status_code == 404
    assert client.patch(f"/api/v1/events/{random_id}", json={"name": "New"}).status_code == 404
    assert client.delete(f"/api/v1/events/{random_id}").status_code == 404

    # Missing event on requirement creation
    assert client.post(
        f"/api/v1/events/{random_id}/requirements",
        json={"category": "venue", "title": "Ballroom"},
    ).status_code == 404


def test_requirement_ownership_under_correct_parent_event(client: TestClient):
    """Verify a requirement can only be modified or deleted through its actual parent event."""
    # Create Event 1 and requirement under Event 1
    event1 = client.post(
        "/api/v1/events/",
        json={"name": "Event One", "event_type": "Type 1"},
    ).json()

    req = client.post(
        f"/api/v1/events/{event1['id']}/requirements",
        json={"category": "catering", "title": "Buffet 1"},
    ).json()

    # Create Event 2
    event2 = client.post(
        "/api/v1/events/",
        json={"name": "Event Two", "event_type": "Type 2"},
    ).json()

    # Attempt to update Event 1's requirement via Event 2's route -> 404
    cross_patch = client.patch(
        f"/api/v1/events/{event2['id']}/requirements/{req['id']}",
        json={"title": "Unauthorized Modification"},
    )
    assert cross_patch.status_code == 404
    assert f"not found under event '{event2['id']}'" in cross_patch.json()["detail"]

    # Attempt to delete Event 1's requirement via Event 2's route -> 404
    cross_delete = client.delete(
        f"/api/v1/events/{event2['id']}/requirements/{req['id']}"
    )
    assert cross_delete.status_code == 404

    # Requirement remains intact under Event 1
    event1_check = client.get(f"/api/v1/events/{event1['id']}").json()
    assert len(event1_check["requirements"]) == 1
    assert event1_check["requirements"][0]["title"] == "Buffet 1"

