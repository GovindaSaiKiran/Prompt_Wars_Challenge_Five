"""Automated tests for Event Budget, Line Items, Deterministic Engine, and Scenarios."""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.services.budget_engine import (
    CalculatedLineItem,
    CurrencyMismatchError,
    InvalidFinancialInputError,
    calculate_budget,
    calculate_line_item,
    quantize_money,
)


# ============================================================================
# 1. Pure Unit Tests for Deterministic Calculation Engine
# ============================================================================


class SimpleLineItem:
    """Mock line item protocol for unit testing calculation engine."""

    def __init__(
        self,
        category: str,
        description: str,
        quantity: Decimal,
        unit_price: Decimal,
        tax_included: bool = False,
        tax_rate: Decimal = Decimal("0.00"),
        discount_amount: Decimal = Decimal("0.00"),
        currency: str = "INR",
    ):
        self.category = category
        self.description = description
        self.quantity = quantity
        self.unit_price = unit_price
        self.tax_included = tax_included
        self.tax_rate = tax_rate
        self.discount_amount = discount_amount
        self.currency = currency


def test_engine_exact_decimal_arithmetic_and_rounding():
    """Verify that calculations avoid floating-point inaccuracies and use ROUND_HALF_UP."""
    # Floating point: 0.1 + 0.2 != 0.3, but Decimal is exact
    item = calculate_line_item(
        quantity=Decimal("3.333"),
        unit_price=Decimal("10.00"),
        tax_included=False,
        tax_rate=Decimal("18.00"),
    )
    # 3.333 * 10 = 33.33 (quantized to 2 decimal places)
    assert item.raw_subtotal == Decimal("33.33")
    # Tax: 33.33 * 0.18 = 5.9994 -> 6.00
    assert item.tax_amount == Decimal("6.00")
    # Total: 33.33 + 6.00 = 39.33
    assert item.line_total == Decimal("39.33")


def test_engine_tax_inclusive_vs_tax_exclusive():
    """Verify statutory tax breakdown under tax-inclusive and tax-exclusive treatments."""
    # 1. Tax-exclusive: Rate 1000 + 18% tax
    item_ex = calculate_line_item(
        quantity=Decimal("1.00"),
        unit_price=Decimal("1000.00"),
        tax_included=False,
        tax_rate=Decimal("18.00"),
    )
    assert item_ex.taxable_amount == Decimal("1000.00")
    assert item_ex.tax_amount == Decimal("180.00")
    assert item_ex.line_total == Decimal("1180.00")

    # 2. Tax-inclusive: Rate 1180 inclusive of 18% tax
    item_inc = calculate_line_item(
        quantity=Decimal("1.00"),
        unit_price=Decimal("1180.00"),
        tax_included=True,
        tax_rate=Decimal("18.00"),
    )
    # Base: 1180 / 1.18 = 1000.00
    assert item_inc.taxable_amount == Decimal("1000.00")
    # Tax: 1180 - 1000 = 180.00
    assert item_inc.tax_amount == Decimal("180.00")
    # Total stays 1180.00 (no double counting)
    assert item_inc.line_total == Decimal("1180.00")


def test_engine_discounts_and_contingency():
    """Verify discount deductions before tax and contingency buffer calculations."""
    items = [
        SimpleLineItem(
            category="venue",
            description="Main Hall",
            quantity=Decimal("1.00"),
            unit_price=Decimal("50000.00"),
            tax_included=False,
            tax_rate=Decimal("18.00"),
            discount_amount=Decimal("5000.00"),  # 45,000 discounted base
        ),
        SimpleLineItem(
            category="catering",
            description="Dinner Buffet",
            quantity=Decimal("100.00"),
            unit_price=Decimal("500.00"),
            tax_included=True,
            tax_rate=Decimal("5.00"),
            discount_amount=Decimal("0.00"),  # 50,000 inclusive
        ),
    ]

    result = calculate_budget(
        items=items,
        budget_currency="INR",
        contingency_percentage=Decimal("10.00"),
        allocated_amount=Decimal("120000.00"),
    )

    # Item 1: raw 50k - 5k disc = 45,000 base; tax 18% = 8,100; total = 53,100
    # Item 2: raw 50k, tax-inclusive 5%: base = 50k / 1.05 = 47,619.05; tax = 2,380.95; total = 50,000
    assert result.raw_subtotal == Decimal("100000.00")
    assert result.total_discount == Decimal("5000.00")
    assert result.subtotal_before_tax == Decimal("45000.00") + Decimal("47619.05")
    assert result.total_tax == Decimal("8100.00") + Decimal("2380.95")
    assert result.subtotal_with_tax == Decimal("53100.00") + Decimal("50000.00")  # 103,100.00

    # Contingency 10% of 103,100 = 10,310.00
    assert result.contingency_amount == Decimal("10310.00")
    # Grand total: 103,100 + 10,310 = 113,410.00
    assert result.grand_total == Decimal("113410.00")

    # Allocation & utilization
    assert result.remaining_budget == Decimal("120000.00") - Decimal("113410.00")  # 6,590.00
    assert result.is_over_budget is False
    # Utilization: 113,410 / 120,000 * 100 = 94.51%
    assert result.budget_utilization_percentage == Decimal("94.51")


def test_engine_currency_mismatch_raises_error():
    """Verify that mixing currencies within a budget raises CurrencyMismatchError."""
    items = [
        SimpleLineItem("venue", "Hall", Decimal("1"), Decimal("1000"), currency="INR"),
        SimpleLineItem("catering", "Food", Decimal("1"), Decimal("200"), currency="USD"),
    ]
    with pytest.raises(CurrencyMismatchError) as exc_info:
        calculate_budget(items, budget_currency="INR")
    assert "Currency mismatch" in str(exc_info.value)


def test_engine_invalid_financial_inputs():
    """Verify that invalid financial numbers are deterministically rejected."""
    # Zero or negative quantity
    with pytest.raises(InvalidFinancialInputError):
        calculate_line_item(Decimal("0.00"), Decimal("100"), False, Decimal("0"))
    with pytest.raises(InvalidFinancialInputError):
        calculate_line_item(Decimal("-2.00"), Decimal("100"), False, Decimal("0"))

    # Negative unit price
    with pytest.raises(InvalidFinancialInputError):
        calculate_line_item(Decimal("1.00"), Decimal("-50"), False, Decimal("0"))

    # Negative discount
    with pytest.raises(InvalidFinancialInputError):
        calculate_line_item(Decimal("1.00"), Decimal("50"), False, Decimal("0"), discount_amount=Decimal("-10"))

    # Invalid tax rate (>100 or <0)
    with pytest.raises(InvalidFinancialInputError):
        calculate_line_item(Decimal("1.00"), Decimal("50"), False, Decimal("105"))


# ============================================================================
# 2. API Integration Tests (Event Budgets, Items, Snapshotting, Scenarios)
# ============================================================================


def create_test_event(client: TestClient, name: str = "Grand Wedding") -> dict:
    """Helper to create an event."""
    res = client.post(
        "/api/v1/events/",
        json={"name": name, "event_type": "wedding", "city": "Bengaluru"},
    )
    assert res.status_code == 201
    return res.json()


def create_test_vendor_with_price(client: TestClient) -> tuple[dict, dict, dict]:
    """Helper to create a vendor, service, and observed price record."""
    vendor = client.post(
        "/api/v1/vendors/",
        json={"business_name": "Sound King AV", "vendor_type": "AV Equipment", "city": "Bengaluru"},
    ).json()

    service = client.post(
        f"/api/v1/vendors/{vendor['id']}/services",
        json={"service_name": "Stage Rigging", "category": "equipment", "unit": "per event"},
    ).json()

    price = client.post(
        "/api/v1/prices/",
        json={
            "vendor_id": vendor["id"],
            "vendor_service_id": service["id"],
            "amount": 20000.00,
            "currency": "INR",
            "unit": "per event",
            "tax_included": False,
            "tax_rate": 18.00,
        },
    ).json()

    return vendor, service, price


def test_budget_crud_lifecycle(client: TestClient):
    """Verify budget creation, listing, detail retrieval, updating, and deletion."""
    event = create_test_event(client, "Corporate Gala 2026")
    event_id = event["id"]

    # 1. Create budget
    budget_payload = {
        "name": "Master Operating Budget",
        "currency": "INR",
        "allocated_amount": 500000.00,
        "contingency_percentage": 10.00,
        "tax_calculation_policy": "standard",
        "status": "draft",
    }
    create_res = client.post(f"/api/v1/events/{event_id}/budgets/", json=budget_payload)
    assert create_res.status_code == 201
    budget = create_res.json()
    assert budget["name"] == "Master Operating Budget"
    assert budget["currency"] == "INR"
    assert float(budget["allocated_amount"]) == 500000.00
    assert float(budget["contingency_percentage"]) == 10.00
    assert budget["status"] == "draft"
    budget_id = budget["id"]

    # 2. List event budgets
    list_res = client.get(f"/api/v1/events/{event_id}/budgets/")
    assert list_res.status_code == 200
    budgets = list_res.json()
    assert len(budgets) >= 1
    assert any(b["id"] == budget_id for b in budgets)

    # 3. Retrieve detail
    detail_res = client.get(f"/api/v1/events/{event_id}/budgets/{budget_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == budget_id
    assert detail["line_items"] == []

    # 4. Patch update
    patch_res = client.patch(
        f"/api/v1/events/{event_id}/budgets/{budget_id}",
        json={"status": "active", "contingency_percentage": 12.50},
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["status"] == "active"
    assert float(updated["contingency_percentage"]) == 12.50

    # 5. Delete budget
    del_res = client.delete(f"/api/v1/events/{event_id}/budgets/{budget_id}")
    assert del_res.status_code == 204

    # Verify 404
    assert client.get(f"/api/v1/events/{event_id}/budgets/{budget_id}").status_code == 404


def test_line_item_price_snapshotting_and_immutability(client: TestClient):
    """Verify that linking a line item to a vendor price record snapshots values and preserves them."""
    event = create_test_event(client, "Snapshot Test Event")
    event_id = event["id"]
    _, _, price_rec = create_test_vendor_with_price(client)

    # Create budget
    budget = client.post(
        f"/api/v1/events/{event_id}/budgets/",
        json={"name": "Production Budget", "currency": "INR", "allocated_amount": 100000.00},
    ).json()
    budget_id = budget["id"]

    # 1. Add line item linking to vendor_price_record_id (without specifying unit_price)
    item_payload = {
        "category": "equipment",
        "description": "Rigging Setup",
        "quantity": 2.0,
        "vendor_price_record_id": price_rec["id"],
    }
    item_res = client.post(f"/api/v1/events/{event_id}/budgets/{budget_id}/items", json=item_payload)
    assert item_res.status_code == 201
    item = item_res.json()

    # Verify that unit_price and tax were copied from price record snapshot
    assert float(item["unit_price"]) == 20000.00
    assert item["currency"] == "INR"
    assert item["unit"] == "per event"
    assert item["tax_included"] is False
    assert float(item["tax_rate"]) == 18.00
    item_id = item["id"]

    # 2. Modify vendor price record (e.g. descriptive patch)
    client.patch(
        f"/api/v1/prices/{price_rec['id']}",
        json={"tax_rate": 28.00},  # tax rate updated in pricing observation
    )

    # 3. Retrieve budget item — SNAPSHOT MUST REMAIN UNCHANGED at 18.00%!
    budget_detail = client.get(f"/api/v1/events/{event_id}/budgets/{budget_id}").json()
    line_item_snap = next(li for li in budget_detail["line_items"] if li["id"] == item_id)
    assert float(line_item_snap["unit_price"]) == 20000.00
    assert float(line_item_snap["tax_rate"]) == 18.00  # Preserved original snapshot!


def test_deterministic_budget_summary_endpoint(client: TestClient):
    """Verify the /summary endpoint returns comprehensive deterministic figures."""
    event = create_test_event(client, "Summary Test Event")
    event_id = event["id"]

    budget = client.post(
        f"/api/v1/events/{event_id}/budgets/",
        json={
            "name": "Reception Budget",
            "currency": "INR",
            "allocated_amount": 250000.00,
            "contingency_percentage": 10.00,
        },
    ).json()
    budget_id = budget["id"]

    # Add 2 items
    client.post(
        f"/api/v1/events/{event_id}/budgets/{budget_id}/items",
        json={
            "category": "venue",
            "description": "Banquet Hall Hire",
            "quantity": 1.0,
            "unit_price": 100000.00,
            "tax_included": False,
            "tax_rate": 18.0,
            "discount_amount": 10000.00,  # 90,000 + 18% (16,200) = 106,200
        },
    )
    client.post(
        f"/api/v1/events/{event_id}/budgets/{budget_id}/items",
        json={
            "category": "catering",
            "description": "Buffet",
            "quantity": 100.0,
            "unit_price": 1000.00,
            "tax_included": True,
            "tax_rate": 5.0,  # 100,000 inclusive of 5% tax
        },
    )

    summary_res = client.get(f"/api/v1/events/{event_id}/budgets/{budget_id}/summary")
    assert summary_res.status_code == 200
    s = summary_res.json()

    assert s["currency"] == "INR"
    assert s["item_count"] == 2
    assert float(s["raw_subtotal"]) == 200000.00
    assert float(s["total_discount"]) == 10000.00
    assert float(s["subtotal_with_tax"]) == 206200.00  # 106,200 + 100,000
    assert float(s["contingency_amount"]) == 20620.00  # 10% of 206,200
    assert float(s["grand_total"]) == 226820.00        # 206,200 + 20,620
    assert float(s["allocated_amount"]) == 250000.00
    assert float(s["remaining_budget"]) == 23180.00    # 250,000 - 226,820
    assert s["is_over_budget"] is False
    assert float(s["budget_utilization_percentage"]) == 90.73  # (226,820 / 250,000) * 100

    # Category summaries verification
    assert "venue" in s["category_summaries"]
    assert "catering" in s["category_summaries"]
    assert float(s["category_summaries"]["venue"]["total_amount"]) == 106200.00
    assert float(s["category_summaries"]["catering"]["total_amount"]) == 100000.00


def test_budget_scenarios_and_comparison(client: TestClient):
    """Verify creating scenarios (cloning vs custom) and side-by-side comparison."""
    event = create_test_event(client, "Scenario Test Event")
    event_id = event["id"]

    budget = client.post(
        f"/api/v1/events/{event_id}/budgets/",
        json={"name": "Summit Budget", "currency": "INR", "allocated_amount": 100000.00, "contingency_percentage": 10.0},
    ).json()
    budget_id = budget["id"]

    # Baseline item: 50,000
    client.post(
        f"/api/v1/events/{event_id}/budgets/{budget_id}/items",
        json={
            "category": "venue",
            "description": "Standard Hall",
            "quantity": 1.0,
            "unit_price": 50000.00,
            "tax_included": False,
            "tax_rate": 18.0,
        },
    )

    # 1. Scenario: Recommended (Cloned from budget items)
    scen_rec = client.post(
        f"/api/v1/events/{event_id}/budgets/{budget_id}/scenarios",
        json={
            "name": "Recommended Plan",
            "description": "Baseline setup with 5% contingency",
            "contingency_percentage": 5.0,
            "clone_from_budget_items": True,
        },
    )
    assert scen_rec.status_code == 201
    rec_data = scen_rec.json()
    assert len(rec_data["line_items"]) == 1
    assert float(rec_data["contingency_percentage"]) == 5.0

    # 2. Scenario: Premium (Custom items)
    scen_prem = client.post(
        f"/api/v1/events/{event_id}/budgets/{budget_id}/scenarios",
        json={
            "name": "Premium Plan",
            "description": "5-star luxury ballroom setup",
            "contingency_percentage": 15.0,
            "items": [
                {
                    "category": "venue",
                    "description": "5-Star Grand Ballroom",
                    "quantity": 1.0,
                    "unit_price": 90000.00,
                    "tax_included": False,
                    "tax_rate": 18.0,
                }
            ],
        },
    )
    assert scen_prem.status_code == 201

    # 3. Compare scenarios
    comp_res = client.get(f"/api/v1/events/{event_id}/budgets/{budget_id}/scenarios/compare")
    assert comp_res.status_code == 200
    comp = comp_res.json()

    assert comp["budget_id"] == budget_id
    assert comp["currency"] == "INR"
    assert len(comp["scenarios"]) == 3  # Baseline + Recommended + Premium

    # Baseline: 50k + 18% (9k) = 59k + 10% contingency (5.9k) = 64,900
    baseline = comp["scenarios"][0]
    assert baseline["scenario_id"] is None
    assert float(baseline["total_estimated_cost"]) == 64900.00
    assert baseline["is_over_budget"] is False

    # Recommended: 59k + 5% contingency (2.95k) = 61,950
    recommended = comp["scenarios"][1]
    assert recommended["scenario_name"] == "Recommended Plan"
    assert float(recommended["total_estimated_cost"]) == 61950.00
    assert recommended["is_over_budget"] is False

    # Premium: 90k + 18% (16.2k) = 106.2k + 15% contingency (15.93k) = 122,130 (Over 100k budget!)
    premium = comp["scenarios"][2]
    assert premium["scenario_name"] == "Premium Plan"
    assert float(premium["total_estimated_cost"]) == 122130.00
    assert premium["is_over_budget"] is True
    assert float(premium["difference_from_allocated"]) == -22130.00


def test_cross_event_resource_isolation(client: TestClient):
    """Verify that budgets and items cannot be accessed or manipulated across different events."""
    event1 = create_test_event(client, "Event One")
    event2 = create_test_event(client, "Event Two")

    # Create budget under Event 1
    b1 = client.post(
        f"/api/v1/events/{event1['id']}/budgets/",
        json={"name": "Event 1 Budget", "currency": "INR"},
    ).json()

    # Attempt to retrieve b1 under Event 2
    res_cross = client.get(f"/api/v1/events/{event2['id']}/budgets/{b1['id']}")
    assert res_cross.status_code == 404

    # Attempt to add line item to b1 under Event 2
    res_cross_item = client.post(
        f"/api/v1/events/{event2['id']}/budgets/{b1['id']}/items",
        json={"category": "venue", "description": "Cross item", "unit_price": 100.0},
    )
    assert res_cross_item.status_code == 404


def test_api_currency_mismatch_rejection(client: TestClient):
    """Verify that the API rejects adding a line item with a mismatched currency."""
    event = create_test_event(client, "Currency Test Event")
    budget = client.post(
        f"/api/v1/events/{event['id']}/budgets/",
        json={"name": "INR Budget", "currency": "INR"},
    ).json()

    # Attempt to add a USD item to an INR budget
    res = client.post(
        f"/api/v1/events/{event['id']}/budgets/{budget['id']}/items",
        json={
            "category": "catering",
            "description": "Foreign Import",
            "unit_price": 50.0,
            "currency": "USD",
        },
    )
    assert res.status_code == 400
    assert "Currency mismatch" in res.json()["detail"]

