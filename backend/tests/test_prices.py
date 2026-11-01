"""Automated tests for Vendor Price Records, Price Evidence, and Price History API endpoints."""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


# ============================================================================
# Helpers
# ============================================================================


def create_sample_vendor(client: TestClient, name: str = "Grand Banquet Hall") -> dict:
    """Helper to create a test vendor."""
    res = client.post(
        "/api/v1/vendors/",
        json={
            "business_name": name,
            "vendor_type": "Venue",
            "city": "Mumbai",
            "state": "Maharashtra",
        },
    )
    assert res.status_code == 201
    return res.json()


def create_sample_service(
    client: TestClient, vendor_id: str, name: str = "Main Ballroom", category: str = "venue"
) -> dict:
    """Helper to create a test vendor service."""
    res = client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={
            "service_name": name,
            "category": category,
            "unit": "per day",
            "is_active": True,
        },
    )
    assert res.status_code == 201
    return res.json()


def create_sample_event(client: TestClient, name: str = "Annual Gala") -> dict:
    """Helper to create a test event."""
    res = client.post(
        "/api/v1/events/",
        json={
            "name": name,
            "event_type": "corporate",
            "city": "Mumbai",
        },
    )
    assert res.status_code == 201
    return res.json()


# ============================================================================
# Price Observation Creation Tests
# ============================================================================


def test_create_and_retrieve_price_record(client: TestClient):
    """Verify price record observation creation and retrieval with eager-loaded evidence."""
    vendor = create_sample_vendor(client, "Royal Palace Hall")
    service = create_sample_service(client, vendor["id"], "Emerald Ballroom")

    payload = {
        "vendor_id": vendor["id"],
        "vendor_service_id": service["id"],
        "amount": 75000.00,
        "currency": "INR",
        "unit": "per day",
        "price_type": "fixed",
        "minimum_quantity": 1,
        "maximum_quantity": 5,
        "tax_included": False,
        "tax_rate": 18.0,
        "valid_from": "2026-11-01",
        "valid_until": "2026-12-31",
        "availability_status": "available",
    }

    # 1. Create price observation
    create_res = client.post("/api/v1/prices/", json=payload)
    assert create_res.status_code == 201
    price_data = create_res.json()

    assert "id" in price_data
    assert price_data["vendor_id"] == vendor["id"]
    assert price_data["vendor_service_id"] == service["id"]
    assert float(price_data["amount"]) == 75000.00
    assert price_data["currency"] == "INR"
    assert price_data["unit"] == "per day"
    assert price_data["price_type"] == "fixed"
    assert price_data["availability_status"] == "available"
    assert price_data["tax_included"] is False
    assert float(price_data["tax_rate"]) == 18.0
    assert price_data["valid_from"] == "2026-11-01"
    assert price_data["valid_until"] == "2026-12-31"

    price_id = price_data["id"]

    # 2. Retrieve price record detail
    detail_res = client.get(f"/api/v1/prices/{price_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == price_id
    assert detail["vendor_business_name"] == "Royal Palace Hall"
    assert detail["service_name"] == "Emerald Ballroom"
    assert "evidence_records" in detail
    assert detail["evidence_records"] == []


def test_create_price_record_with_event_association(client: TestClient):
    """Verify price record can optionally link to an event."""
    vendor = create_sample_vendor(client, "Catering Masters")
    service = create_sample_service(client, vendor["id"], "Buffet Dinner")
    event = create_sample_event(client, "Tech Summit 2026")

    payload = {
        "vendor_id": vendor["id"],
        "vendor_service_id": service["id"],
        "event_id": event["id"],
        "amount": 1200.50,
        "currency": "INR",
        "unit": "per plate",
        "price_type": "per_unit",
    }

    res = client.post("/api/v1/prices/", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["event_id"] == event["id"]


def test_create_price_record_service_mismatch_fails(client: TestClient):
    """Verify that price creation fails with 400 if the service does not belong to the vendor."""
    vendor_a = create_sample_vendor(client, "Vendor A")
    vendor_b = create_sample_vendor(client, "Vendor B")
    service_a = create_sample_service(client, vendor_a["id"], "Service A")

    # Attempt to link vendor_b with service_a (which belongs to vendor_a)
    payload = {
        "vendor_id": vendor_b["id"],
        "vendor_service_id": service_a["id"],
        "amount": 50000.00,
        "currency": "INR",
        "unit": "per event",
    }

    res = client.post("/api/v1/prices/", json=payload)
    assert res.status_code == 400
    assert "not the specified vendor" in res.json()["detail"]


def test_create_price_record_nonexistent_foreign_keys_fail(client: TestClient):
    """Verify 404 errors when vendor, service, or event foreign keys do not exist."""
    vendor = create_sample_vendor(client, "Valid Vendor")
    service = create_sample_service(client, vendor["id"], "Valid Service")
    random_uuid = str(uuid.uuid4())

    # Non-existent vendor
    res_vendor = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": random_uuid,
            "vendor_service_id": service["id"],
            "amount": 1000.0,
            "currency": "INR",
            "unit": "per day",
        },
    )
    assert res_vendor.status_code == 404
    assert "Vendor" in res_vendor.json()["detail"]

    # Non-existent service
    res_service = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": random_uuid,
            "amount": 1000.0,
            "currency": "INR",
            "unit": "per day",
        },
    )
    assert res_service.status_code == 404
    assert "VendorService" in res_service.json()["detail"]

    # Non-existent event
    res_event = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "event_id": random_uuid,
            "amount": 1000.0,
            "currency": "INR",
            "unit": "per day",
        },
    )
    assert res_event.status_code == 404
    assert "Event" in res_event.json()["detail"]


# ============================================================================
# Validation Tests
# ============================================================================


def test_price_validation_negative_or_zero_amount(client: TestClient):
    """Verify validation error when amount is <= 0."""
    vendor = create_sample_vendor(client, "Vendor")
    service = create_sample_service(client, vendor["id"], "Service")

    for invalid_amt in [0, -500]:
        res = client.post(
            "/api/v1/prices/",
            json={
                "vendor_id": vendor["id"],
                "vendor_service_id": service["id"],
                "amount": invalid_amt,
                "currency": "INR",
                "unit": "per day",
            },
        )
        assert res.status_code == 422


def test_price_validation_currency_code(client: TestClient):
    """Verify validation error when currency code is not 3 uppercase characters."""
    vendor = create_sample_vendor(client, "Vendor")
    service = create_sample_service(client, vendor["id"], "Service")

    for invalid_cur in ["INDIA", "12", "IN", "INR1", ""]:
        res = client.post(
            "/api/v1/prices/",
            json={
                "vendor_id": vendor["id"],
                "vendor_service_id": service["id"],
                "amount": 500,
                "currency": invalid_cur,
                "unit": "per day",
            },
        )
        assert res.status_code == 422


def test_price_validation_quantity_range(client: TestClient):
    """Verify validation error when min_quantity > max_quantity."""
    vendor = create_sample_vendor(client, "Vendor")
    service = create_sample_service(client, vendor["id"], "Service")

    res = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 500,
            "currency": "INR",
            "unit": "per plate",
            "minimum_quantity": 200,
            "maximum_quantity": 50,  # min > max
        },
    )
    assert res.status_code == 422


def test_price_validation_date_order(client: TestClient):
    """Verify validation error when valid_until is before valid_from."""
    vendor = create_sample_vendor(client, "Vendor")
    service = create_sample_service(client, vendor["id"], "Service")

    res = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 500,
            "currency": "INR",
            "unit": "per plate",
            "valid_from": "2026-12-31",
            "valid_until": "2026-01-01",  # until < from
        },
    )
    assert res.status_code == 422


def test_price_validation_tax_rate_range(client: TestClient):
    """Verify validation error when tax_rate is outside 0-100%."""
    vendor = create_sample_vendor(client, "Vendor")
    service = create_sample_service(client, vendor["id"], "Service")

    for invalid_tax in [-5.0, 105.0]:
        res = client.post(
            "/api/v1/prices/",
            json={
                "vendor_id": vendor["id"],
                "vendor_service_id": service["id"],
                "amount": 500,
                "currency": "INR",
                "unit": "per plate",
                "tax_rate": invalid_tax,
            },
        )
        assert res.status_code == 422


# ============================================================================
# Price Immutability & PATCH Update Tests
# ============================================================================


def test_price_immutability_and_patch_update(client: TestClient):
    """Verify that financial values are immutable and only descriptive/status fields can be updated."""
    vendor = create_sample_vendor(client, "Immutable Sound")
    service = create_sample_service(client, vendor["id"], "Concert Speaker Rig")

    # 1. Create original price
    create_res = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 40000.00,
            "currency": "INR",
            "unit": "per day",
            "availability_status": "unknown",
        },
    )
    assert create_res.status_code == 201
    price_id = create_res.json()["id"]

    # 2. Update descriptive and status fields
    patch_payload = {
        "availability_status": "available",
        "tax_included": True,
        "tax_rate": 18.0,
        "valid_from": "2026-11-01",
        "valid_until": "2026-11-30",
        "minimum_quantity": 1,
        "maximum_quantity": 10,
        # Attempt to tamper with financial and identity fields
        "amount": 10.00,
        "currency": "USD",
        "unit": "per hour",
        "vendor_id": str(uuid.uuid4()),
        "vendor_service_id": str(uuid.uuid4()),
    }

    patch_res = client.patch(f"/api/v1/prices/{price_id}", json=patch_payload)
    assert patch_res.status_code == 200
    updated_data = patch_res.json()

    # Descriptive/status fields must be updated
    assert updated_data["availability_status"] == "available"
    assert updated_data["tax_included"] is True
    assert float(updated_data["tax_rate"]) == 18.0
    assert updated_data["valid_from"] == "2026-11-01"
    assert updated_data["valid_until"] == "2026-11-30"

    # Core financial and relationship fields MUST REMAIN IMMUTABLE
    assert float(updated_data["amount"]) == 40000.00  # Not 10.00
    assert updated_data["currency"] == "INR"  # Not USD
    assert updated_data["unit"] == "per day"  # Not per hour
    assert updated_data["vendor_id"] == vendor["id"]  # Unchanged
    assert updated_data["vendor_service_id"] == service["id"]  # Unchanged


# ============================================================================
# Price Listing & Filtering Tests
# ============================================================================


def test_list_prices_pagination_and_filters(client: TestClient):
    """Verify price list filtering and pagination."""
    vendor = create_sample_vendor(client, "Listing Test Vendor")
    service1 = create_sample_service(client, vendor["id"], "Service 1")
    service2 = create_sample_service(client, vendor["id"], "Service 2")

    # Create 3 price observations
    p1 = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service1["id"],
            "amount": 10000.0,
            "currency": "INR",
            "unit": "per day",
            "price_type": "fixed",
            "availability_status": "available",
        },
    ).json()

    p2 = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service1["id"],
            "amount": 12000.0,
            "currency": "INR",
            "unit": "per day",
            "price_type": "range",
            "availability_status": "limited",
        },
    ).json()

    p3 = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service2["id"],
            "amount": 250.0,
            "currency": "USD",
            "unit": "per hour",
            "price_type": "fixed",
            "availability_status": "available",
        },
    ).json()

    # Filter by service1
    res_svc = client.get(f"/api/v1/prices/?vendor_service_id={service1['id']}")
    assert res_svc.status_code == 200
    data_svc = res_svc.json()
    assert data_svc["total"] == 2
    ids_svc = [item["id"] for item in data_svc["items"]]
    assert p1["id"] in ids_svc
    assert p2["id"] in ids_svc
    assert p3["id"] not in ids_svc

    # Filter by currency=USD
    res_cur = client.get("/api/v1/prices/?currency=USD")
    assert res_cur.status_code == 200
    data_cur = res_cur.json()
    assert data_cur["total"] == 1
    assert data_cur["items"][0]["id"] == p3["id"]

    # Filter by price_type=range
    res_type = client.get("/api/v1/prices/?price_type=range")
    assert res_type.status_code == 200
    data_type = res_type.json()
    assert data_type["total"] == 1
    assert data_type["items"][0]["id"] == p2["id"]


# ============================================================================
# Price Evidence Tests
# ============================================================================


def test_attach_and_list_price_evidence(client: TestClient):
    """Verify attaching multiple evidence items to a price record."""
    vendor = create_sample_vendor(client, "Evidence Test Vendor")
    service = create_sample_service(client, vendor["id"], "Catering Service")

    price = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 1500.0,
            "currency": "INR",
            "unit": "per person",
        },
    ).json()
    price_id = price["id"]

    # 1. Attach published rate evidence
    ev1_payload = {
        "evidence_type": "published",
        "source_url": "https://www.vendorcatering.com/tariffs",
        "source_name": "Official 2026 Tariff PDF",
        "inclusions": "Three courses, welcome drink, cutlery",
        "exclusions": "Dessert counter, alcoholic beverages",
        "notes": "Extracted from public tariff card dated Jan 2026.",
    }
    ev1_res = client.post(f"/api/v1/prices/{price_id}/evidence", json=ev1_payload)
    assert ev1_res.status_code == 201
    ev1_data = ev1_res.json()
    assert ev1_data["price_record_id"] == price_id
    assert ev1_data["evidence_type"] == "published"
    assert ev1_data["source_url"] == "https://www.vendorcatering.com/tariffs"
    assert "captured_at" in ev1_data

    # 2. Attach vendor quoted rate evidence
    ev2_payload = {
        "evidence_type": "vendor_quoted",
        "quoted_by": "Sunil Verma (Sales Manager)",
        "inclusions": "Complete buffet",
        "notes": "Received quote via official email proposal.",
    }
    ev2_res = client.post(f"/api/v1/prices/{price_id}/evidence", json=ev2_payload)
    assert ev2_res.status_code == 201
    ev2_data = ev2_res.json()
    assert ev2_data["evidence_type"] == "vendor_quoted"
    assert ev2_data["quoted_by"] == "Sunil Verma (Sales Manager)"

    # 3. Retrieve list of evidence for this price record
    ev_list_res = client.get(f"/api/v1/prices/{price_id}/evidence")
    assert ev_list_res.status_code == 200
    ev_list = ev_list_res.json()
    assert len(ev_list) == 2
    assert any(e["id"] == ev1_data["id"] for e in ev_list)
    assert any(e["id"] == ev2_data["id"] for e in ev_list)

    # 4. Check eager-loaded evidence in price detail
    detail_res = client.get(f"/api/v1/prices/{price_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert "evidence_records" in detail
    assert len(detail["evidence_records"]) == 2


def test_evidence_invalid_source_url_fails(client: TestClient):
    """Verify validation error when source_url is not a valid HTTP/HTTPS URL."""
    vendor = create_sample_vendor(client, "URL Test Vendor")
    service = create_sample_service(client, vendor["id"], "Service")

    price = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 1000.0,
            "currency": "INR",
            "unit": "per day",
        },
    ).json()

    res = client.post(
        f"/api/v1/prices/{price['id']}/evidence",
        json={
            "evidence_type": "published",
            "source_url": "ftp://not-an-http-link.com",
        },
    )
    assert res.status_code == 422


# ============================================================================
# Vendor Price History Tests
# ============================================================================


def test_vendor_price_history(client: TestClient):
    """Verify vendor price history returns all historical observations in chronological order."""
    vendor = create_sample_vendor(client, "History Vendor")
    service1 = create_sample_service(client, vendor["id"], "Photography Basic")
    service2 = create_sample_service(client, vendor["id"], "Photography Drone")

    # Add 3 observations across services
    res1 = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service1["id"],
            "amount": 25000.0,
            "currency": "INR",
            "unit": "per day",
        },
    ).json()

    res2 = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service1["id"],
            "amount": 28000.0,
            "currency": "INR",
            "unit": "per day",
        },
    ).json()

    res3 = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service2["id"],
            "amount": 15000.0,
            "currency": "INR",
            "unit": "per event",
        },
    ).json()

    history_res = client.get(f"/api/v1/prices/vendors/{vendor['id']}/history")
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) == 3
    history_ids = [item["id"] for item in history]
    assert res1["id"] in history_ids
    assert res2["id"] in history_ids
    assert res3["id"] in history_ids

    # 404 for non-existent vendor
    non_existent = str(uuid.uuid4())
    res_404 = client.get(f"/api/v1/prices/vendors/{non_existent}/history")
    assert res_404.status_code == 404


# ============================================================================
# Service Price Comparison & Classification Tests
# ============================================================================


def test_service_price_comparison_classification_and_confirmed_rules(client: TestClient):
    """Verify classification into published, vendor_quoted, vendor_confirmed, estimates, expired, unknown.

    STRICT RULE: Confirmed rates strictly require vendor_confirmed evidence.
    """
    vendor = create_sample_vendor(client, "Comparison Caterer")
    service = create_sample_service(client, vendor["id"], "Silver Buffet")

    # 1. Price record with published evidence
    p_pub = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 900.0,
            "currency": "INR",
            "unit": "per plate",
        },
    ).json()
    client.post(
        f"/api/v1/prices/{p_pub['id']}/evidence",
        json={"evidence_type": "published", "source_name": "Brochure"},
    )

    # 2. Price record with vendor_quoted evidence
    p_quoted = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 850.0,
            "currency": "INR",
            "unit": "per plate",
        },
    ).json()
    client.post(
        f"/api/v1/prices/{p_quoted['id']}/evidence",
        json={"evidence_type": "vendor_quoted", "quoted_by": "Sales Rep"},
    )

    # 3. Price record with vendor_confirmed evidence
    p_conf = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 820.0,
            "currency": "INR",
            "unit": "per plate",
        },
    ).json()
    client.post(
        f"/api/v1/prices/{p_conf['id']}/evidence",
        json={"evidence_type": "vendor_confirmed", "quoted_by": "Managing Director"},
    )

    # 4. Price record with estimated evidence
    p_est = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 950.0,
            "currency": "INR",
            "unit": "per plate",
        },
    ).json()
    client.post(
        f"/api/v1/prices/{p_est['id']}/evidence",
        json={"evidence_type": "estimated", "notes": "Market benchmark estimate"},
    )

    # 5. Price record that has expired valid_until date
    p_exp = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 700.0,
            "currency": "INR",
            "unit": "per plate",
            "valid_from": "2024-01-01",
            "valid_until": "2024-06-30",  # Expired date in the past
        },
    ).json()
    client.post(
        f"/api/v1/prices/{p_exp['id']}/evidence",
        json={"evidence_type": "published", "source_name": "Old 2024 Tariff"},
    )

    # 6. Price record with no evidence (unknown)
    p_unk = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 1000.0,
            "currency": "INR",
            "unit": "per plate",
        },
    ).json()

    # Query comparison endpoint
    comp_res = client.get(f"/api/v1/prices/services/{service['id']}/comparison")
    assert comp_res.status_code == 200
    comp = comp_res.json()

    assert comp["service_id"] == service["id"]
    assert comp["service_name"] == "Silver Buffet"
    assert comp["total_observations"] == 6

    # Verify classification buckets
    published_ids = [item["price_record_id"] for item in comp["published_prices"]]
    assert p_pub["id"] in published_ids

    quoted_ids = [item["price_record_id"] for item in comp["vendor_quotations"]]
    assert p_quoted["id"] in quoted_ids

    confirmed_ids = [item["price_record_id"] for item in comp["vendor_confirmed"]]
    assert p_conf["id"] in confirmed_ids

    estimate_ids = [item["price_record_id"] for item in comp["estimates"]]
    assert p_est["id"] in estimate_ids

    expired_ids = [item["price_record_id"] for item in comp["expired"]]
    assert p_exp["id"] in expired_ids

    unknown_ids = [item["price_record_id"] for item in comp["unknown"]]
    assert p_unk["id"] in unknown_ids

    # STRICT ASSERTION: is_confirmed must be True ONLY for vendor_confirmed items!
    for bucket_name, items in [
        ("published", comp["published_prices"]),
        ("vendor_quotations", comp["vendor_quotations"]),
        ("estimates", comp["estimates"]),
        ("expired", comp["expired"]),
        ("unknown", comp["unknown"]),
    ]:
        for item in items:
            assert item["is_confirmed"] is False, f"Expected is_confirmed=False for bucket {bucket_name}"

    for item in comp["vendor_confirmed"]:
        assert item["is_confirmed"] is True, "Expected is_confirmed=True for vendor_confirmed bucket"


# ============================================================================
# Cascade Deletion Tests
# ============================================================================


def test_cascade_deletion_on_vendor_removal(client: TestClient):
    """Verify that deleting a vendor cascades and deletes associated price records and evidence."""
    vendor = create_sample_vendor(client, "Cascade Vendor")
    service = create_sample_service(client, vendor["id"], "Cascade Service")

    price = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 5000.0,
            "currency": "INR",
            "unit": "per day",
        },
    ).json()

    client.post(
        f"/api/v1/prices/{price['id']}/evidence",
        json={"evidence_type": "vendor_quoted"},
    )

    # Delete vendor
    del_res = client.delete(f"/api/v1/vendors/{vendor['id']}")
    assert del_res.status_code == 204

    # Verify price record is gone
    price_get = client.get(f"/api/v1/prices/{price['id']}")
    assert price_get.status_code == 404
