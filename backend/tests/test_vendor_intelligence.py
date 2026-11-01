"""Tests for Phase 9: Vendor Price Intelligence.

Covers:
- Vendor CRUD, active toggle, and search & filters.
- Price record creation and validation.
- All 6 evidence classifications (published, vendor_quoted, vendor_confirmed, estimated, expired, unknown).
- Expired price detection.
- Availability independence from price evidence.
- Multi-vendor comparison: unit compatibility, unit mismatch rejection, currency mismatch rejection.
- Location and proximity notes.
- Historical price observation preservation.
- Budget line item integration from vendor price record.
- Non-fabrication assertions.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.event import Event
from app.models.budget import EventBudget, BudgetLineItem
from app.models.vendor import Vendor, VendorService
from app.models.price import VendorPriceRecord, PriceEvidence
from app.schemas.price import AvailabilityStatus, EvidenceType, PriceType


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ============================================================================
# 1. Vendor CRUD, Active Toggle, and Search/Filters
# ============================================================================


def test_vendor_crud_and_filters(client: TestClient):
    """Test full vendor profile lifecycle, toggling active status, and search/filters."""
    # 1. Create Vendor
    create_payload = {
        "business_name": "Royal Feast Catering & Hospitality",
        "description": "Premium catering service specializing in authentic Indian delicacies.",
        "vendor_type": "Caterer",
        "contact_person": "Vikram Malhotra",
        "email": "vikram@royalfeast.com",
        "phone": "+91 98765 43210",
        "city": "Mumbai",
        "state": "Maharashtra",
        "country": "India",
        "verification_status": "pending",
        "is_active": True,
    }
    create_res = client.post("/api/v1/vendors/", json=create_payload)
    assert create_res.status_code == 201
    vendor_data = create_res.json()
    vendor_id = vendor_data["id"]
    assert vendor_data["business_name"] == "Royal Feast Catering & Hospitality"
    assert vendor_data["verification_status"] == "pending"
    assert vendor_data["is_active"] is True

    # Upgrade to verified via patch
    client.patch(f"/api/v1/vendors/{vendor_id}", json={"verification_status": "verified"})

    # 2. Add Service
    service_payload = {
        "service_name": "Silver Wedding Buffet",
        "category": "catering",
        "unit": "per_plate",
        "description": "3-course gourmet dinner with live chaat counter",
        "minimum_quantity": 100,
        "is_active": True,
    }
    svc_res = client.post(f"/api/v1/vendors/{vendor_id}/services", json=service_payload)
    assert svc_res.status_code == 201
    svc_id = svc_res.json()["id"]

    # 3. Create a second vendor in Delhi
    v2_res = client.post(
        "/api/v1/vendors/",
        json={
            "business_name": "Delhi Sound & Lights",
            "vendor_type": "AV & Production",
            "city": "New Delhi",
            "is_active": True,
        },
    )
    assert v2_res.status_code == 201
    v2_id = v2_res.json()["id"]

    # 4. Filter by search query (name/description substring)
    search_res = client.get("/api/v1/vendors/?search=Royal Feast")
    assert search_res.status_code == 200
    items = search_res.json()["items"]
    assert any(v["id"] == vendor_id for v in items)
    assert not any(v["id"] == v2_id for v in items)

    # 5. Filter by city
    city_res = client.get("/api/v1/vendors/?city=Mumbai")
    assert city_res.status_code == 200
    assert any(v["id"] == vendor_id for v in city_res.json()["items"])
    assert not any(v["id"] == v2_id for v in city_res.json()["items"])

    # 6. Filter by category
    cat_res = client.get("/api/v1/vendors/?category=catering&limit=100")
    assert cat_res.status_code == 200
    assert any(v["id"] == vendor_id for v in cat_res.json()["items"])

    # 7. Filter by service_name
    svc_name_res = client.get("/api/v1/vendors/?service_name=Buffet&limit=100")
    assert svc_name_res.status_code == 200
    assert any(v["id"] == vendor_id for v in svc_name_res.json()["items"])

    # 8. Deactivate vendor listing
    patch_res = client.patch(f"/api/v1/vendors/{vendor_id}", json={"is_active": False})
    assert patch_res.status_code == 200
    assert patch_res.json()["is_active"] is False

    # 9. Filter by active status
    active_res = client.get("/api/v1/vendors/?is_active=true&limit=100")
    assert not any(v["id"] == vendor_id for v in active_res.json()["items"])
    assert any(v["id"] == v2_id for v in active_res.json()["items"])

    # Reactivate vendor
    client.patch(f"/api/v1/vendors/{vendor_id}", json={"is_active": True})


# ============================================================================
# 2. All 6 Evidence Classifications & Expired Handling
# ============================================================================


def test_price_evidence_six_classifications_and_expiry(client: TestClient):
    """Verify published, vendor_quoted, vendor_confirmed, estimated, expired, and unknown classifications."""
    # Create vendor and service
    v_res = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Evidence Testing Vendor", "vendor_type": "Florist", "city": "Bangalore"},
    )
    vendor_id = v_res.json()["id"]

    svc_res = client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "Floral Stage Setup", "category": "decoration", "unit": "per_event"},
    )
    svc_id = svc_res.json()["id"]

    today = date.today()
    past_date = today - timedelta(days=10)
    future_date = today + timedelta(days=30)

    # 1. Vendor Confirmed Price
    p_confirmed = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "45000.00",
            "currency": "INR",
            "unit": "per_event",
            "price_type": "package",
            "tax_included": True,
            "tax_rate": "18.00",
            "valid_until": str(future_date),
            "availability_status": "available",
            "initial_evidence": {
                "evidence_type": "vendor_confirmed",
                "source_name": "Signed Contract Quotation #8841",
                "quoted_by": "Rohit Verma (Manager)",
                "inclusions": "Stage backdrop, lighting accents, floral chandelier",
                "exclusions": "Custom neon signboards",
            },
        },
    )
    assert p_confirmed.status_code == 201

    # 2. Vendor Quoted Price
    p_quoted = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "40000.00",
            "currency": "INR",
            "unit": "per_event",
            "price_type": "package",
            "initial_evidence": {
                "evidence_type": "vendor_quoted",
                "source_name": "WhatsApp Quote",
                "quoted_by": "Rohit",
            },
        },
    )
    assert p_quoted.status_code == 201

    # 3. Published Price
    p_published = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "50000.00",
            "currency": "INR",
            "unit": "per_event",
            "initial_evidence": {
                "evidence_type": "published",
                "source_name": "Website Catalog 2026",
                "source_url": "https://example.com/floral-packages",
            },
        },
    )
    assert p_published.status_code == 201

    # 4. Estimated Benchmark Price
    p_estimated = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "38000.00",
            "currency": "INR",
            "unit": "per_event",
            "initial_evidence": {
                "evidence_type": "estimated",
                "notes": "City average for 40ft stage setup",
            },
        },
    )
    assert p_estimated.status_code == 201

    # 5. Expired Price (past valid_until)
    p_expired = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "32000.00",
            "currency": "INR",
            "unit": "per_event",
            "valid_until": str(past_date),
            "initial_evidence": {
                "evidence_type": "vendor_confirmed",
                "source_name": "2025 Seasonal Promo",
            },
        },
    )
    assert p_expired.status_code == 201

    # 6. Unknown Evidence Price
    p_unknown = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "35000.00",
            "currency": "INR",
            "unit": "per_event",
        },
    )
    assert p_unknown.status_code == 201

    # Call service comparison endpoint
    comp_res = client.get(f"/api/v1/prices/services/{svc_id}/comparison")
    assert comp_res.status_code == 200
    data = comp_res.json()

    assert len(data["vendor_confirmed"]) >= 1
    assert len(data["vendor_quotations"]) >= 1
    assert len(data["published_prices"]) >= 1
    assert len(data["estimates"]) >= 1
    assert len(data["expired"]) >= 1
    assert len(data["unknown"]) >= 1

    # Strictly verify that confirmed is ONLY true for unexpired vendor_confirmed evidence
    for item in data["vendor_confirmed"]:
        assert item["is_confirmed"] is True
        assert item["is_expired"] is False

    for item in data["estimates"]:
        assert item["is_confirmed"] is False

    for item in data["expired"]:
        assert item["is_expired"] is True
        assert item["is_confirmed"] is False


# ============================================================================
# 3. Availability Independence from Price Evidence
# ============================================================================


def test_availability_independent_from_price_evidence(client: TestClient):
    """Ensure availability status is NEVER inferred from price evidence and can be set independently."""
    v_res = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Independent Avail Vendor", "vendor_type": "Photographer", "city": "Goa"},
    )
    vendor_id = v_res.json()["id"]

    svc_res = client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "Candid Photography", "category": "photography", "unit": "per_day"},
    )
    svc_id = svc_res.json()["id"]

    # Observation A: Vendor Confirmed evidence, but availability is strictly UNAVAILABLE (e.g. booked out)
    res_a = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "50000.00",
            "currency": "INR",
            "unit": "per_day",
            "availability_status": "unavailable",
            "initial_evidence": {
                "evidence_type": "vendor_confirmed",
                "source_name": "Direct Call confirmation",
            },
        },
    )
    assert res_a.status_code == 201
    item_a = res_a.json()
    assert item_a["availability_status"] == "unavailable"

    # Observation B: Estimated evidence, but availability is marked AVAILABLE
    res_b = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "40000.00",
            "currency": "INR",
            "unit": "per_day",
            "availability_status": "available",
            "initial_evidence": {
                "evidence_type": "estimated",
            },
        },
    )
    assert res_b.status_code == 201
    item_b = res_b.json()
    assert item_b["availability_status"] == "available"

    # Verify updating availability status does not mutate evidence or prices
    patch_res = client.patch(
        f"/api/v1/prices/{item_a['id']}",
        json={"availability_status": "limited"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["availability_status"] == "limited"
    assert patch_res.json()["amount"] == "50000.00"


# ============================================================================
# 4. Multi-Vendor Comparison Service: Unit Compatibility, Mismatch & Currencies
# ============================================================================


def test_multi_vendor_comparison_service(client: TestClient):
    """Test multi-vendor comparison across quantity, unit normalization, incompatibility explanations, and currency mismatches."""
    # Create two catering vendors in Pune
    v1_res = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Pune Feast Caterers", "vendor_type": "Caterer", "city": "Pune"},
    )
    v1_id = v1_res.json()["id"]

    v2_res = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Deccan Gourmet", "vendor_type": "Caterer", "city": "Pune"},
    )
    v2_id = v2_res.json()["id"]

    # V1 service: per_plate rate INR 1,200 + 5% GST
    s1_res = client.post(
        f"/api/v1/vendors/{v1_id}/services",
        json={"service_name": "Gold Dinner Buffet", "category": "catering", "unit": "per_plate"},
    )
    s1_id = s1_res.json()["id"]

    p1_res = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": v1_id,
            "vendor_service_id": s1_id,
            "amount": "1200.00",
            "currency": "INR",
            "unit": "per_plate",
            "tax_included": False,
            "tax_rate": "5.00",
            "availability_status": "available",
            "initial_evidence": {
                "evidence_type": "vendor_confirmed",
                "source_name": "Official Quote #101",
                "inclusions": "Welcome drinks, soup, 4 mains, 3 desserts",
                "exclusions": "Mineral water jars",
            },
        },
    )
    p1_id = p1_res.json()["id"]

    # V2 service: per_person rate INR 1,300 (tax inclusive 5%)
    s2_res = client.post(
        f"/api/v1/vendors/{v2_id}/services",
        json={"service_name": "Royal Feast Dining", "category": "catering", "unit": "per_person"},
    )
    s2_id = s2_res.json()["id"]

    p2_res = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": v2_id,
            "vendor_service_id": s2_id,
            "amount": "1300.00",
            "currency": "INR",
            "unit": "per_person",
            "tax_included": True,
            "tax_rate": "5.00",
            "availability_status": "available",
            "initial_evidence": {
                "evidence_type": "published",
                "source_name": "Online Menu Card",
                "inclusions": "All inclusive dining",
            },
        },
    )
    p2_id = p2_res.json()["id"]

    # V3: Incompatible Unit Vendor (hourly DJ rate in catering category for edge testing)
    s3_res = client.post(
        f"/api/v1/vendors/{v1_id}/services",
        json={"service_name": "Live Kitchen Counter Hourly", "category": "catering", "unit": "per_hour"},
    )
    s3_id = s3_res.json()["id"]
    p3_res = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": v1_id,
            "vendor_service_id": s3_id,
            "amount": "5000.00",
            "currency": "INR",
            "unit": "per_hour",
        },
    )
    p3_id = p3_res.json()["id"]

    # V4: Currency Mismatch Vendor (quoted in USD)
    s4_res = client.post(
        f"/api/v1/vendors/{v2_id}/services",
        json={"service_name": "Imported Chef Menu", "category": "catering", "unit": "per_plate"},
    )
    s4_id = s4_res.json()["id"]
    p4_res = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": v2_id,
            "vendor_service_id": s4_id,
            "amount": "25.00",
            "currency": "USD",
            "unit": "per_plate",
        },
    )
    p4_id = p4_res.json()["id"]

    # Perform Multi-Vendor Comparison for 150 guests (requested_unit: "person")
    comp_req = {
        "category": "catering",
        "quantity": "150.00",
        "unit": "person",
        "currency": "INR",
        "target_city": "Pune",
        "price_record_ids": [p1_id, p2_id, p3_id, p4_id],
    }
    comp_res = client.post("/api/v1/prices/compare", json=comp_req)
    assert comp_res.status_code == 200
    data = comp_res.json()

    assert data["total_compared"] == 4
    assert data["compatible_count"] == 2

    items = {item["price_record_id"]: item for item in data["items"]}

    # Check V1: 150 * 1200 = 180,000 subtotal, 5% tax = 9,000, total = 189,000
    item1 = items[p1_id]
    assert item1["is_compatible"] is True
    assert Decimal(str(item1["subtotal"])) == Decimal("180000.00")
    assert Decimal(str(item1["tax_amount"])) == Decimal("9000.00")
    assert Decimal(str(item1["total_cost"])) == Decimal("189000.00")
    assert item1["evidence_type"] == "vendor_confirmed"
    assert "Grade A" in item1["evidence_grade"]
    assert item1["location_match"] is True

    # Check V2: 150 * 1300 = 195,000 total (tax inclusive)
    item2 = items[p2_id]
    assert item2["is_compatible"] is True
    assert Decimal(str(item2["total_cost"])) == Decimal("195000.00")
    assert item2["location_match"] is True

    # Best value recommendation should be V1 (189,000 < 195,000)
    assert data["best_value_price_record_id"] == p1_id

    # Check V3: Incompatible unit
    item3 = items[p3_id]
    assert item3["is_compatible"] is False
    assert "Incompatible unit" in item3["compatibility_reason"]
    assert item3["total_cost"] is None

    # Check V4: Currency mismatch
    item4 = items[p4_id]
    assert item4["is_compatible"] is False
    assert "Currency mismatch" in item4["compatibility_reason"]
    assert item4["total_cost"] is None


# ============================================================================
# 5. Historical Price Preservation
# ============================================================================


def test_historical_price_preservation(client: TestClient):
    """Ensure submitting a new price observation does not overwrite historical records."""
    v_res = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Heritage Banquet Palace", "vendor_type": "Venue", "city": "Jaipur"},
    )
    vendor_id = v_res.json()["id"]

    svc_res = client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "Royal Ballroom Rental", "category": "venue", "unit": "per_event"},
    )
    svc_id = svc_res.json()["id"]

    # 1st observation in 2025: INR 200,000
    p1 = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "200000.00",
            "currency": "INR",
            "unit": "per_event",
            "initial_evidence": {"evidence_type": "published", "source_name": "2025 Rate Card"},
        },
    ).json()

    # 2nd observation in 2026: INR 250,000
    p2 = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "250000.00",
            "currency": "INR",
            "unit": "per_event",
            "initial_evidence": {"evidence_type": "vendor_quoted", "source_name": "2026 Quote"},
        },
    ).json()

    # Retrieve history
    hist_res = client.get(f"/api/v1/prices/vendors/{vendor_id}/history")
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) == 2

    amounts = [h["amount"] for h in history]
    assert "200000.00" in amounts
    assert "250000.00" in amounts

    # Attempting to mutate financial amount via PATCH must be rejected or not permitted
    patch_try = client.patch(f"/api/v1/prices/{p1['id']}", json={"amount": "100000.00"})
    assert patch_try.status_code == 200
    # Amount remains 200,000.00
    check_p1 = client.get(f"/api/v1/prices/{p1['id']}").json()
    assert check_p1["amount"] == "200000.00"


# ============================================================================
# 6. Budget Line Item Integration from Vendor Price Record
# ============================================================================


def test_budget_line_item_integration(client: TestClient):
    """Test creating an event budget line item from a vendor price record with full snapshotting and provenance."""
    # 1. Create Event & Budget
    ev_res = client.post(
        "/api/v1/events/",
        json={"name": "Phase 9 Test Gala", "event_type": "gala", "city": "Hyderabad"},
    )
    assert ev_res.status_code == 201
    event_id = ev_res.json()["id"]

    bg_res = client.post(
        f"/api/v1/events/{event_id}/budgets",
        json={"name": "Gala Master Budget", "allocated_amount": "500000.00", "currency": "INR"},
    )
    budget_id = bg_res.json()["id"]

    # 2. Create Vendor, Service and Price Record
    v_res = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Star Sound Systems", "vendor_type": "AV", "city": "Hyderabad"},
    )
    vendor_id = v_res.json()["id"]

    svc_res = client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "Concert Audio Setup", "category": "equipment", "unit": "per_event"},
    )
    svc_id = svc_res.json()["id"]

    p_res = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "75000.00",
            "currency": "INR",
            "unit": "per_event",
            "tax_included": False,
            "tax_rate": "18.00",
            "initial_evidence": {
                "evidence_type": "vendor_confirmed",
                "source_name": "Official Quote Ref #5521",
                "source_url": "https://starsound.example.com/quotes/5521",
            },
        },
    )
    price_id = p_res.json()["id"]

    # 3. Add line item referencing vendor_price_record_id WITHOUT supplying unit_price or tax
    line_item_payload = {
        "category": "equipment",
        "description": "Main Concert Audio Setup",
        "quantity": "1.00",
        "vendor_price_record_id": price_id,
    }
    li_res = client.post(
        f"/api/v1/events/{event_id}/budgets/{budget_id}/items",
        json=line_item_payload,
    )
    assert li_res.status_code == 201
    li_data = li_res.json()

    # Snapshotted fields
    assert Decimal(str(li_data["unit_price"])) == Decimal("75000.00")
    assert li_data["unit"] == "per_event"
    assert li_data["currency"] == "INR"
    assert li_data["tax_included"] is False
    assert Decimal(str(li_data["tax_rate"])) == Decimal("18.00")
    assert li_data["vendor_price_record_id"] == price_id
    assert "Official Quote Ref #5521" in li_data["notes"]
    assert "vendor_confirmed" in li_data["notes"]

    # 4. Check deterministic budget summary
    summary_res = client.get(f"/api/v1/events/{event_id}/budgets/{budget_id}/summary")
    assert summary_res.status_code == 200
    s_data = summary_res.json()
    assert Decimal(str(s_data["subtotal_before_tax"])) == Decimal("75000.00")
    assert Decimal(str(s_data["total_tax"])) == Decimal("13500.00")  # 18% of 75000
    assert Decimal(str(s_data["subtotal_with_tax"])) == Decimal("88500.00")
    assert Decimal(str(s_data["contingency_amount"])) == Decimal("8850.00")  # 10% default contingency
    assert Decimal(str(s_data["grand_total"])) == Decimal("97350.00")


# ============================================================================
# 7. Non-Fabrication Assertion
# ============================================================================


def test_no_fabricated_vendor_or_pricing_data(client: TestClient):
    """Verify system strictly preserves real vendor data and never fabricates prices, ratings, or contacts."""
    v_res = client.post(
        "/api/v1/vendors/",
        json={
            "business_name": "Authentic Organic Florals",
            "vendor_type": "Florist",
            "city": "Chennai",
            # No phone or website provided
        },
    )
    vendor = v_res.json()
    assert vendor["phone"] is None
    assert vendor["website_url"] is None
    # No star rating or fabricated review fields
    assert "rating" not in vendor
    assert "reviews_count" not in vendor


# ============================================================================
# 8. Phase 9.1 Integrity Audit: Tax Integrity & Unknown Tax Handling
# ============================================================================


def test_tax_integrity_unknown_tax_not_treated_as_zero(client: TestClient):
    """Verify unknown tax is clearly represented as unknown and never confirmed zero."""
    v_res = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Tax Audit Caterer", "vendor_type": "Caterer", "city": "Bengaluru"},
    )
    vendor_id = v_res.json()["id"]

    svc_res = client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "Wedding Thali Buffet", "category": "catering", "unit": "per_plate"},
    )
    svc_id = svc_res.json()["id"]

    # 1. Price record with unknown tax (tax_rate=None, tax_included=False)
    p_unspecified = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "800.00",
            "currency": "INR",
            "unit": "per_plate",
            "tax_included": False,
            "availability_status": "available",
            "initial_evidence": {"evidence_type": "published", "source_name": "Rate Sheet"},
        },
    ).json()

    # 2. Price record with all-inclusive rate, but unspecified tax breakdown percentage
    p_inclusive_unspec = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "1000.00",
            "currency": "INR",
            "unit": "per_plate",
            "tax_included": True,
            "availability_status": "available",
            "initial_evidence": {"evidence_type": "vendor_quoted", "source_name": "All-in Quote"},
        },
    ).json()

    # 3. Price record with explicit exclusive tax (18%)
    p_exclusive_explicit = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "900.00",
            "currency": "INR",
            "unit": "per_plate",
            "tax_included": False,
            "tax_rate": "18.00",
            "availability_status": "available",
            "initial_evidence": {"evidence_type": "vendor_confirmed", "source_name": "Contract"},
        },
    ).json()

    # Run multi-vendor comparison
    res = client.post(
        "/api/v1/prices/compare",
        json={
            "category": "catering",
            "quantity": "100.00",
            "unit": "plate",
            "currency": "INR",
            "price_record_ids": [p_unspecified["id"], p_inclusive_unspec["id"], p_exclusive_explicit["id"]],
        },
    )
    assert res.status_code == 200
    data = res.json()
    items = {item["price_record_id"]: item for item in data["items"]}

    # Check 1: Unspecified tax rate MUST have tax_amount=None and tax_status='unknown'
    item1 = items[p_unspecified["id"]]
    assert item1["tax_status"] == "unknown"
    assert item1["tax_amount"] is None  # NOT Decimal('0.00')!
    assert "Statutory tax rate is unspecified" in item1["tax_notes"]
    assert Decimal(str(item1["subtotal"])) == Decimal("80000.00")

    # Check 2: Inclusive unspec tax has tax_amount=None, but tax_status='inclusive'
    item2 = items[p_inclusive_unspec["id"]]
    assert item2["tax_status"] == "inclusive"
    assert item2["tax_amount"] is None
    assert Decimal(str(item2["total_cost"])) == Decimal("100000.00")

    # Check 3: Explicit exclusive tax has calculated tax_amount
    item3 = items[p_exclusive_explicit["id"]]
    assert item3["tax_status"] == "exclusive"
    assert Decimal(str(item3["tax_amount"])) == Decimal("16200.00")  # 18% of 90,000
    assert Decimal(str(item3["total_cost"])) == Decimal("106200.00")

    # Verification of comparison notes for unknown tax
    assert any("unspecified tax rates" in note for note in data["comparison_notes"])


# ============================================================================
# 9. Phase 9.1 Integrity Audit: Best-Value Recommendation Rigorous Guards
# ============================================================================


def test_best_value_integrity_disqualifications(client: TestClient):
    """Verify expired, unavailable, unknown availability, and estimated rates cannot win best value."""
    v_res = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Selection Integrity Vendor", "vendor_type": "AV", "city": "Mumbai"},
    )
    vendor_id = v_res.json()["id"]

    svc_res = client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "LED Video Wall", "category": "equipment", "unit": "per_event"},
    )
    svc_id = svc_res.json()["id"]

    today = date.today()
    past_date = today - timedelta(days=5)
    future_date = today + timedelta(days=30)

    # Candidate 1: Cheapest rate (10,000), but EXPIRED -> Disqualified
    p_expired = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "10000.00",
            "currency": "INR",
            "unit": "per_event",
            "valid_until": str(past_date),
            "availability_status": "available",
            "initial_evidence": {"evidence_type": "published"},
        },
    ).json()

    # Candidate 2: Cheap rate (15,000), but UNAVAILABLE -> Disqualified
    p_unavailable = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "15000.00",
            "currency": "INR",
            "unit": "per_event",
            "valid_until": str(future_date),
            "availability_status": "unavailable",
            "initial_evidence": {"evidence_type": "vendor_confirmed"},
        },
    ).json()

    # Candidate 3: Cheap rate (18,000), but UNKNOWN availability -> Disqualified (must not be treated as available)
    p_unknown_avail = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "18000.00",
            "currency": "INR",
            "unit": "per_event",
            "valid_until": str(future_date),
            "availability_status": "unknown",
            "initial_evidence": {"evidence_type": "vendor_quoted"},
        },
    ).json()

    # Candidate 4: Cheap rate (20,000), but ESTIMATED benchmark -> Disqualified
    p_estimated = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "20000.00",
            "currency": "INR",
            "unit": "per_event",
            "valid_until": str(future_date),
            "availability_status": "available",
            "initial_evidence": {"evidence_type": "estimated"},
        },
    ).json()

    # Candidate 5: Valid rate (25,000), AVAILABLE, VENDOR_QUOTED, UNEXPIRED -> Wins!
    p_valid_winner = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "25000.00",
            "currency": "INR",
            "unit": "per_event",
            "valid_until": str(future_date),
            "availability_status": "available",
            "initial_evidence": {"evidence_type": "vendor_quoted", "source_name": "Official Quote #9921"},
        },
    ).json()

    # Run Comparison
    res = client.post(
        "/api/v1/prices/compare",
        json={
            "category": "equipment",
            "quantity": "1.00",
            "unit": "event",
            "currency": "INR",
            "price_record_ids": [
                p_expired["id"],
                p_unavailable["id"],
                p_unknown_avail["id"],
                p_estimated["id"],
                p_valid_winner["id"],
            ],
        },
    )
    assert res.status_code == 200
    data = res.json()

    # Candidate 5 MUST win because candidates 1-4 are disqualified under strict integrity rules
    assert data["best_value_price_record_id"] == p_valid_winner["id"]
    assert "25000" in data["best_value_rationale"]

    # Verify comparison notes explicitly warn that low price is not automatically the superior overall choice
    assert any("not automatically the superior overall choice" in note for note in data["comparison_notes"])


# ============================================================================
# 10. Phase 9.1 Integrity Audit: Location Matching Disclosures
# ============================================================================


def test_location_integrity_administrative_city_matching(client: TestClient):
    """Verify city matching is presented strictly as administrative match without claiming transit duration or GPS distance."""
    v_res = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Jaipur Royal Decor", "vendor_type": "Decorator", "city": "Jaipur"},
    )
    vendor_id = v_res.json()["id"]

    svc_res = client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "Mandap Decor", "category": "decoration", "unit": "per_event"},
    )
    svc_id = svc_res.json()["id"]

    p_res = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "50000.00",
            "currency": "INR",
            "unit": "per_event",
            "availability_status": "available",
            "initial_evidence": {"evidence_type": "published"},
        },
    ).json()

    # Query with target_city = "Jaipur" (same city)
    res_same = client.post(
        "/api/v1/prices/compare",
        json={
            "category": "decoration",
            "quantity": "1.00",
            "target_city": "Jaipur",
            "price_record_ids": [p_res["id"]],
        },
    ).json()
    item_same = res_same["items"][0]
    assert item_same["city_match"] is True
    assert item_same["location_match"] is True
    assert "Administrative city match: Jaipur" in item_same["location_notes"]
    assert "Precise geographic distance, transit duration, and travel times are not calculated" in item_same["location_notes"]

    # Query with target_city = "Udaipur" (different city)
    res_diff = client.post(
        "/api/v1/prices/compare",
        json={
            "category": "decoration",
            "quantity": "1.00",
            "target_city": "Udaipur",
            "price_record_ids": [p_res["id"]],
        },
    ).json()
    item_diff = res_diff["items"][0]
    assert item_diff["city_match"] is False
    assert item_diff["location_match"] is False
    assert "Operating in Jaipur (Target: Udaipur)" in item_diff["location_notes"]
    assert "outstation travel fees may apply" in item_diff["location_notes"]


# ============================================================================
# 11. Phase 9.1 Integrity Audit: Comparison vs Budget Calculation Consistency
# ============================================================================


def test_comparison_versus_budget_calculation_consistency(client: TestClient):
    """Verify that vendor comparison calculations and budget engine line items produce identical results."""
    # 1. Create Event & Budget
    ev_res = client.post(
        "/api/v1/events/",
        json={"name": "Audit Math Consistency Event", "event_type": "conference", "city": "Ahmedabad"},
    )
    event_id = ev_res.json()["id"]

    bg_res = client.post(
        f"/api/v1/events/{event_id}/budgets",
        json={"name": "Consistency Budget", "currency": "INR", "tax_calculation_policy": "standard"},
    )
    budget_id = bg_res.json()["id"]

    # 2. Create Vendor, Service and Price Record with explicit tax
    v_res = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Ahmedabad Banquet Hall", "vendor_type": "Venue", "city": "Ahmedabad"},
    )
    vendor_id = v_res.json()["id"]

    svc_res = client.post(
        f"/api/v1/vendors/{vendor_id}/services",
        json={"service_name": "Main Convention Hall", "category": "venue", "unit": "per_day"},
    )
    svc_id = svc_res.json()["id"]

    p_res = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor_id,
            "vendor_service_id": svc_id,
            "amount": "125000.00",
            "currency": "INR",
            "unit": "per_day",
            "tax_included": False,
            "tax_rate": "18.00",
            "availability_status": "available",
            "initial_evidence": {"evidence_type": "vendor_confirmed", "source_name": "Official Contract"},
        },
    ).json()
    price_id = p_res["id"]

    # 3. Perform comparison for 2 days
    comp_res = client.post(
        "/api/v1/prices/compare",
        json={
            "category": "venue",
            "quantity": "2.00",
            "unit": "day",
            "currency": "INR",
            "price_record_ids": [price_id],
        },
    ).json()
    comp_item = comp_res["items"][0]

    # Expected math: 2 * 125,000 = 250,000 base; 18% tax = 45,000; total = 295,000
    assert Decimal(str(comp_item["subtotal"])) == Decimal("250000.00")
    assert Decimal(str(comp_item["tax_amount"])) == Decimal("45000.00")
    assert Decimal(str(comp_item["total_cost"])) == Decimal("295000.00")

    # 4. Add to budget line items
    li_res = client.post(
        f"/api/v1/events/{event_id}/budgets/{budget_id}/items",
        json={
            "category": "venue",
            "description": "Main Convention Hall 2 Days",
            "quantity": "2.00",
            "vendor_price_record_id": price_id,
        },
    )
    assert li_res.status_code == 201

    # 5. Fetch deterministic budget summary
    bg_summary = client.get(f"/api/v1/events/{event_id}/budgets/{budget_id}/summary").json()
    calc_line = bg_summary["line_items"][0]

    # Verify bit-for-bit calculation consistency
    assert Decimal(str(calc_line["taxable_amount"])) == Decimal(str(comp_item["subtotal"]))
    assert Decimal(str(calc_line["tax_amount"])) == Decimal(str(comp_item["tax_amount"]))
    assert Decimal(str(calc_line["line_total"])) == Decimal(str(comp_item["total_cost"]))

