"""Automated tests for Vendor and VendorService API endpoints, validation, and relationships."""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


# ============================================================================
# Vendor CRUD Tests
# ============================================================================


def test_create_and_retrieve_vendor(client: TestClient):
    """Verify vendor creation and retrieval with detailed response schema."""
    payload = {
        "business_name": "Royal Feast Caterers",
        "description": "Premium multi-cuisine wedding and corporate catering specialist.",
        "vendor_type": "Caterer",
        "contact_person": "Chef Rajesh Khanna",
        "email": "rajesh@royalfeast.com",
        "phone": "+91 98860 41209",
        "website_url": "https://www.royalfeast.com",
        "address": "12 Catering Hub Road, Sector 4",
        "city": "Bengaluru",
        "state": "Karnataka",
        "country": "India",
        "postal_code": "560034",
        "verification_status": "unverified",
        "is_active": True,
    }

    # 1. Create vendor
    response = client.post("/api/v1/vendors/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["business_name"] == payload["business_name"]
    assert data["vendor_type"] == payload["vendor_type"]
    assert data["verification_status"] == "unverified"
    assert data["email"] == "rajesh@royalfeast.com"
    assert data["is_active"] is True
    assert "created_at" in data
    assert "updated_at" in data

    vendor_id = data["id"]

    # 2. Retrieve vendor detail
    get_res = client.get(f"/api/v1/vendors/{vendor_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["id"] == vendor_id
    assert detail["business_name"] == payload["business_name"]
    assert detail["services"] == []


def test_list_vendors_pagination_and_filters(client: TestClient):
    """Verify vendor listing, pagination, and multi-field filtering."""
    # Create test vendors
    v1 = client.post(
        "/api/v1/vendors/",
        json={
            "business_name": "Bengaluru Floral Elegance",
            "vendor_type": "Decorator",
            "city": "Bengaluru",
            "verification_status": "pending",
            "is_active": True,
        },
    ).json()

    v2 = client.post(
        "/api/v1/vendors/",
        json={
            "business_name": "Mumbai Soundwaves",
            "vendor_type": "Audio Visual",
            "city": "Mumbai",
            "verification_status": "pending",
            "is_active": True,
        },
    ).json()

    v3 = client.post(
        "/api/v1/vendors/",
        json={
            "business_name": "Bengaluru Shutter Magic",
            "vendor_type": "Photographer",
            "city": "Bengaluru",
            "verification_status": "unverified",
            "is_active": False,
        },
    ).json()

    # Add service to v1 for category filter test
    client.post(
        f"/api/v1/vendors/{v1['id']}/services",
        json={"service_name": "Mandap Decor", "category": "decoration"},
    )

    # 1. Test pagination
    page = client.get("/api/v1/vendors/?skip=0&limit=2")
    assert page.status_code == 200
    p_data = page.json()
    assert p_data["total"] == 3
    assert len(p_data["items"]) == 2

    # 2. Filter by city
    city_res = client.get("/api/v1/vendors/?city=Bengaluru")
    assert city_res.status_code == 200
    assert city_res.json()["total"] == 2

    # 3. Filter by vendor_type
    type_res = client.get("/api/v1/vendors/?vendor_type=Audio")
    assert type_res.status_code == 200
    assert type_res.json()["total"] == 1
    assert type_res.json()["items"][0]["business_name"] == "Mumbai Soundwaves"

    # 4. Filter by verification_status
    status_res = client.get("/api/v1/vendors/?verification_status=pending")
    assert status_res.status_code == 200
    assert status_res.json()["total"] == 2

    # 5. Filter by is_active
    active_res = client.get("/api/v1/vendors/?is_active=false")
    assert active_res.status_code == 200
    assert active_res.json()["total"] == 1
    assert active_res.json()["items"][0]["business_name"] == "Bengaluru Shutter Magic"

    # 6. Filter by service category
    cat_res = client.get("/api/v1/vendors/?category=decoration")
    assert cat_res.status_code == 200
    assert cat_res.json()["total"] == 1
    assert cat_res.json()["items"][0]["id"] == v1["id"]

    # 7. Invalid pagination limits
    assert client.get("/api/v1/vendors/?limit=0").status_code == 422
    assert client.get("/api/v1/vendors/?limit=101").status_code == 422
    assert client.get("/api/v1/vendors/?skip=-1").status_code == 422


def test_update_and_delete_vendor(client: TestClient):
    """Verify vendor partial update and deletion."""
    create_res = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Apex Lighting", "vendor_type": "Lighting"},
    )
    vendor_id = create_res.json()["id"]

    # PATCH update
    update_res = client.patch(
        f"/api/v1/vendors/{vendor_id}",
        json={
            "business_name": "Apex Stage & Concert Lighting",
            "verification_status": "pending",
            "contact_person": "Vikram Verma",
        },
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["business_name"] == "Apex Stage & Concert Lighting"
    assert updated["verification_status"] == "pending"
    assert updated["contact_person"] == "Vikram Verma"

    # DELETE vendor
    del_res = client.delete(f"/api/v1/vendors/{vendor_id}")
    assert del_res.status_code == 204

    # Verify 404
    assert client.get(f"/api/v1/vendors/{vendor_id}").status_code == 404


# ============================================================================
# Vendor Service & Cascade Tests
# ============================================================================


def test_vendor_services_crud_and_cascade_deletion(client: TestClient):
    """Verify service offering creation, update, retrieval, and cascade deletion when vendor is removed."""
    # 1. Create vendor
    vendor_res = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Palace Grounds Convention", "vendor_type": "Venue"},
    )
    vendor_id = vendor_res.json()["id"]

    # 2. Add service
    service_payload = {
        "service_name": "Grand Ballroom Banquet Space",
        "category": "venue",
        "description": "Air-conditioned 10,000 sq ft hall with stage and backup generator.",
        "unit": "per day",
        "minimum_quantity": "1.00",
        "maximum_capacity": 600,
        "service_area": "Greater Bengaluru",
        "is_active": True,
    }
    svc_res = client.post(f"/api/v1/vendors/{vendor_id}/services", json=service_payload)
    assert svc_res.status_code == 201
    svc_data = svc_res.json()
    assert svc_data["service_name"] == service_payload["service_name"]
    assert svc_data["category"] == "venue"
    assert svc_data["vendor_id"] == vendor_id
    assert Decimal(str(svc_data["minimum_quantity"])) == Decimal("1.00")
    assert svc_data["maximum_capacity"] == 600
    svc_id = svc_data["id"]

    # 3. Retrieve vendor with eager loaded services
    detail = client.get(f"/api/v1/vendors/{vendor_id}").json()
    assert len(detail["services"]) == 1
    assert detail["services"][0]["id"] == svc_id

    # 4. PATCH service
    update_res = client.patch(
        f"/api/v1/vendors/{vendor_id}/services/{svc_id}",
        json={"maximum_capacity": 800, "is_active": False},
    )
    assert update_res.status_code == 200
    assert update_res.json()["maximum_capacity"] == 800
    assert update_res.json()["is_active"] is False

    # 5. Delete parent vendor and verify cascade deletion of service
    del_res = client.delete(f"/api/v1/vendors/{vendor_id}")
    assert del_res.status_code == 204

    # Ensure vendor is deleted
    assert client.get(f"/api/v1/vendors/{vendor_id}").status_code == 404

    # Ensure service is also deleted
    assert client.delete(f"/api/v1/vendors/{vendor_id}/services/{svc_id}").status_code == 404


def test_service_individual_deletion(client: TestClient):
    """Verify deleting a service individually leaves the vendor intact."""
    vendor_id = client.post(
        "/api/v1/vendors/",
        json={"business_name": "LensCraft Studios", "vendor_type": "Photography"},
    ).json()["id"]

    svc_id = client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "Drone 4K Teaser", "category": "photography"},
    ).json()["id"]

    # Delete service
    del_svc = client.delete(f"/api/v1/vendors/{vendor_id}/services/{svc_id}")
    assert del_svc.status_code == 204

    # Vendor still exists with empty services
    vendor_detail = client.get(f"/api/v1/vendors/{vendor_id}").json()
    assert vendor_detail["services"] == []


# ============================================================================
# Validation & Scoping Tests
# ============================================================================


def test_invalid_email_and_url_validation(client: TestClient):
    """Verify validation errors for malformed email addresses and website URLs."""
    # Invalid email
    bad_email = client.post(
        "/api/v1/vendors/",
        json={
            "business_name": "Bad Email Vendor",
            "vendor_type": "General",
            "email": "not-an-email-at-all",
        },
    )
    assert bad_email.status_code == 422
    assert "Invalid email address format" in str(bad_email.json())

    # Invalid URL (missing scheme)
    bad_url = client.post(
        "/api/v1/vendors/",
        json={
            "business_name": "Bad URL Vendor",
            "vendor_type": "General",
            "website_url": "ftp://unsupported.com",
        },
    )
    assert bad_url.status_code == 422
    assert "URL must start with http:// or https://" in str(bad_url.json())


def test_invalid_verification_status(client: TestClient):
    """Verify validation error when providing an invalid verification status or attempting self-verification."""
    # Unknown string
    res = client.post(
        "/api/v1/vendors/",
        json={
            "business_name": "Status Test",
            "vendor_type": "General",
            "verification_status": "super_verified",
        },
    )
    assert res.status_code == 422

    # Attempting to self-verify on create
    self_verify_create = client.post(
        "/api/v1/vendors/",
        json={
            "business_name": "Self Verify Co",
            "vendor_type": "General",
            "verification_status": "verified",
        },
    )
    assert self_verify_create.status_code == 422
    assert "Public registration cannot set verification_status" in str(self_verify_create.json())

    # Create valid vendor
    v = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Patch Status Vendor", "vendor_type": "General"},
    ).json()

    # Attempting to self-verify on patch
    self_verify_patch = client.patch(
        f"/api/v1/vendors/{v['id']}",
        json={"verification_status": "verified"},
    )
    assert self_verify_patch.status_code == 422
    assert "Public clients cannot set verification_status to verified" in str(self_verify_patch.json())


def test_invalid_service_numeric_values(client: TestClient):
    """Verify validation errors for zero or negative minimum_quantity and maximum_capacity."""
    vendor_id = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Numeric Test", "vendor_type": "General"},
    ).json()["id"]

    # Zero minimum quantity
    assert client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "Test", "category": "catering", "minimum_quantity": 0},
    ).status_code == 422

    # Negative minimum quantity
    assert client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "Test", "category": "catering", "minimum_quantity": -5.5},
    ).status_code == 422

    # Zero maximum capacity
    assert client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "Test", "category": "venue", "maximum_capacity": 0},
    ).status_code == 422

    # Negative maximum capacity
    assert client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "Test", "category": "venue", "maximum_capacity": -50},
    ).status_code == 422


def test_missing_vendor_and_service_responses(client: TestClient):
    """Verify structured 404 responses for non-existent vendors."""
    random_id = uuid.uuid4()

    assert client.get(f"/api/v1/vendors/{random_id}").status_code == 404
    assert client.patch(f"/api/v1/vendors/{random_id}", json={"business_name": "New"}).status_code == 404
    assert client.delete(f"/api/v1/vendors/{random_id}").status_code == 404
    assert client.post(
        f"/api/v1/vendors/{random_id}/services",
        json={"service_name": "S1", "category": "venue"},
    ).status_code == 404


def test_service_ownership_under_correct_vendor(client: TestClient):
    """Verify a service can only be updated or deleted through its actual parent vendor."""
    # Create Vendor 1 and service
    v1 = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Vendor One", "vendor_type": "Florist"},
    ).json()

    svc = client.post(
        f"/api/v1/vendors/{v1['id']}/services",
        json={"service_name": "Flower Garlands", "category": "decoration"},
    ).json()

    # Create Vendor 2
    v2 = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Vendor Two", "vendor_type": "Caterer"},
    ).json()

    # Cross-vendor PATCH -> 404
    cross_patch = client.patch(
        f"/api/v1/vendors/{v2['id']}/services/{svc['id']}",
        json={"service_name": "Hijacked Service"},
    )
    assert cross_patch.status_code == 404
    assert f"not found under vendor '{v2['id']}'" in cross_patch.json()["detail"]

    # Cross-vendor DELETE -> 404
    cross_delete = client.delete(
        f"/api/v1/vendors/{v2['id']}/services/{svc['id']}"
    )
    assert cross_delete.status_code == 404

    # Service remains intact under Vendor 1
    v1_check = client.get(f"/api/v1/vendors/{v1['id']}").json()
    assert len(v1_check["services"]) == 1
    assert v1_check["services"][0]["service_name"] == "Flower Garlands"
