"""FastAPI endpoints for Deterministic Event Budgets, Line Items, and Scenarios."""

import logging
import uuid
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.budget import (
    BudgetLineItem,
    BudgetScenario,
    BudgetScenarioLineItem,
    EventBudget,
)
from app.models.event import Event, EventRequirement
from app.models.price import PriceEvidence, VendorPriceRecord
from app.schemas.budget import (
    BudgetLineItemCreate,
    BudgetLineItemResponse,
    BudgetLineItemUpdate,
    BudgetScenarioCompareResponse,
    BudgetScenarioCreate,
    BudgetScenarioResponse,
    BudgetSummaryResponse,
    CalculatedLineItemSchema,
    CategorySummarySchema,
    EventBudgetCreate,
    EventBudgetDetailResponse,
    EventBudgetResponse,
    EventBudgetUpdate,
    ScenarioComparisonItem,
)
from app.services.budget_engine import (
    BudgetEngineError,
    CurrencyMismatchError,
    InvalidFinancialInputError,
    calculate_budget,
)

logger = logging.getLogger("eventprice.budgets")

router = APIRouter(
    prefix="/events/{event_id}/budgets",
    tags=["Event Budgets & Scenarios"],
)


# ============================================================================
# Helpers
# ============================================================================


def get_event_or_404(event_id: uuid.UUID, db: Session) -> Event:
    """Verify that parent event exists."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id '{event_id}' not found",
        )
    return event


def get_budget_or_404(
    event_id: uuid.UUID,
    budget_id: uuid.UUID,
    db: Session,
    eager_load_items: bool = False,
    eager_load_scenarios: bool = False,
) -> EventBudget:
    """Retrieve budget and verify strict parent event scoping."""
    get_event_or_404(event_id, db)

    stmt = select(EventBudget).where(EventBudget.id == budget_id)
    if eager_load_items:
        stmt = stmt.options(selectinload(EventBudget.line_items))
    if eager_load_scenarios:
        stmt = stmt.options(
            selectinload(EventBudget.scenarios).selectinload(BudgetScenario.line_items)
        )

    budget = db.execute(stmt).scalars().first()
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget with id '{budget_id}' not found",
        )
    if budget.event_id != event_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget with id '{budget_id}' does not belong to event '{event_id}'",
        )
    return budget


def get_line_item_or_404(
    budget_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session,
) -> BudgetLineItem:
    """Retrieve budget line item and verify budget scoping."""
    item = db.get(BudgetLineItem, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget line item with id '{item_id}' not found",
        )
    if item.budget_id != budget_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Budget line item '{item_id}' does not belong to budget '{budget_id}'",
        )
    return item


# ============================================================================
# Budget CRUD Endpoints
# ============================================================================


@router.post(
    "/",
    response_model=EventBudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create event budget",
    description="Creates a new budget scoped to the specified event with deterministic financial settings.",
)
def create_event_budget(
    event_id: uuid.UUID,
    payload: EventBudgetCreate,
    db: Session = Depends(get_db),
) -> EventBudget:
    """Create a new EventBudget."""
    get_event_or_404(event_id, db)

    budget = EventBudget(
        event_id=event_id,
        name=payload.name,
        currency=payload.currency,
        allocated_amount=payload.allocated_amount,
        contingency_percentage=payload.contingency_percentage,
        tax_calculation_policy=payload.tax_calculation_policy.value,
        status=payload.status.value,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)

    logger.info("Created budget id=%s for event id=%s name='%s'", budget.id, event_id, budget.name)
    return budget


@router.get(
    "/",
    response_model=List[EventBudgetResponse],
    status_code=status.HTTP_200_OK,
    summary="List event budgets",
    description="Retrieves all budgets associated with the specified event.",
)
def list_event_budgets(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[EventBudget]:
    """List all budgets for an event."""
    get_event_or_404(event_id, db)

    stmt = select(EventBudget).where(EventBudget.event_id == event_id).order_by(EventBudget.created_at.desc())
    return list(db.execute(stmt).scalars().all())


@router.get(
    "/{budget_id}",
    response_model=EventBudgetDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve budget and line items",
    description="Retrieves an event budget along with all attached line items.",
)
def get_event_budget(
    event_id: uuid.UUID,
    budget_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> EventBudget:
    """Retrieve single budget with eager-loaded line items."""
    return get_budget_or_404(event_id, budget_id, db, eager_load_items=True)


@router.patch(
    "/{budget_id}",
    response_model=EventBudgetResponse,
    status_code=status.HTTP_200_OK,
    summary="Update budget configuration",
    description="Updates configuration parameters (name, currency, allocated_amount, contingency, status).",
)
def update_event_budget(
    event_id: uuid.UUID,
    budget_id: uuid.UUID,
    payload: EventBudgetUpdate,
    db: Session = Depends(get_db),
) -> EventBudget:
    """Partially update an EventBudget."""
    budget = get_budget_or_404(event_id, budget_id, db)

    update_data = payload.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        if hasattr(value, "value"):
            setattr(budget, field_name, value.value)
        else:
            setattr(budget, field_name, value)

    db.commit()
    db.refresh(budget)
    logger.info("Updated budget id=%s for event id=%s", budget.id, event_id)
    return budget


@router.delete(
    "/{budget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete budget",
    description="Deletes a budget and cascades removal to all attached line items and scenarios.",
)
def delete_event_budget(
    event_id: uuid.UUID,
    budget_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> None:
    """Delete an EventBudget and cascade to children."""
    budget = get_budget_or_404(event_id, budget_id, db)
    db.delete(budget)
    db.commit()
    logger.info("Deleted budget id=%s for event id=%s", budget_id, event_id)


# ============================================================================
# Line Item Endpoints
# ============================================================================


@router.post(
    "/{budget_id}/items",
    response_model=BudgetLineItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add line item to budget",
    description=(
        "Adds a line item. When linked to a vendor_price_record_id, price fields are "
        "automatically snapshotted into the line item so later vendor price changes cannot alter the budget."
    ),
)
def add_budget_line_item(
    event_id: uuid.UUID,
    budget_id: uuid.UUID,
    payload: BudgetLineItemCreate,
    db: Session = Depends(get_db),
) -> BudgetLineItem:
    """Add a new line item to the budget with snapshotting support."""
    budget = get_budget_or_404(event_id, budget_id, db)

    unit_price = payload.unit_price
    unit = payload.unit or "item"
    currency = payload.currency or budget.currency
    tax_included = payload.tax_included if payload.tax_included is not None else False
    tax_rate = payload.tax_rate if payload.tax_rate is not None else Decimal("0.00")

    notes = payload.notes
    # 1. Snapshot from VendorPriceRecord if linked
    if payload.vendor_price_record_id:
        price_rec = db.get(VendorPriceRecord, payload.vendor_price_record_id)
        if not price_rec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"VendorPriceRecord with id '{payload.vendor_price_record_id}' not found",
            )
        # Snapshot price record fields when not explicitly overridden
        if unit_price is None:
            unit_price = price_rec.amount
        if payload.unit is None:
            unit = price_rec.unit
        if payload.currency is None:
            currency = price_rec.currency
        if payload.tax_included is None and price_rec.tax_included is not None:
            tax_included = price_rec.tax_included
        if payload.tax_rate is None and price_rec.tax_rate is not None:
            tax_rate = price_rec.tax_rate

        # Auto-attach evidence source provenance into notes if notes omitted
        if notes is None:
            ev_stmt = (
                select(PriceEvidence)
                .where(PriceEvidence.price_record_id == price_rec.id)
                .order_by(PriceEvidence.captured_at.desc())
            )
            latest_ev = db.execute(ev_stmt).scalars().first()
            if latest_ev:
                src_label = latest_ev.source_name or "Vendor Quote"
                notes = f"Sourced from {src_label} [{latest_ev.evidence_type}]"
                if latest_ev.source_url:
                    notes += f" ({latest_ev.source_url})"
            else:
                notes = f"Linked to vendor price record {price_rec.id}"

    # If unit_price is still None, fail validation
    if unit_price is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="unit_price is required when not linking to a valid vendor price record",
        )

    # 2. Verify optional event requirement link
    if payload.event_requirement_id:
        req = db.get(EventRequirement, payload.event_requirement_id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"EventRequirement with id '{payload.event_requirement_id}' not found",
            )
        if req.event_id != event_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"EventRequirement '{req.id}' belongs to event '{req.event_id}', not this event '{event_id}'",
            )

    # 3. Currency compatibility check
    if currency.strip().upper() != budget.currency.strip().upper():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Currency mismatch: line item currency '{currency}' does not match "
                f"budget currency '{budget.currency}'"
            ),
        )

    line_item = BudgetLineItem(
        budget_id=budget.id,
        event_requirement_id=payload.event_requirement_id,
        vendor_price_record_id=payload.vendor_price_record_id,
        category=payload.category,
        description=payload.description,
        quantity=payload.quantity,
        unit=unit,
        unit_price=unit_price,
        currency=currency,
        tax_included=tax_included,
        tax_rate=tax_rate,
        discount_amount=payload.discount_amount,
        notes=notes,
    )
    db.add(line_item)
    db.commit()
    db.refresh(line_item)

    logger.info("Added line item id=%s to budget id=%s (category='%s')", line_item.id, budget.id, line_item.category)
    return line_item


@router.patch(
    "/{budget_id}/items/{item_id}",
    response_model=BudgetLineItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update budget line item",
    description="Updates descriptive or financial figures of an existing line item.",
)
def update_budget_line_item(
    event_id: uuid.UUID,
    budget_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: BudgetLineItemUpdate,
    db: Session = Depends(get_db),
) -> BudgetLineItem:
    """Update an existing BudgetLineItem."""
    budget = get_budget_or_404(event_id, budget_id, db)
    item = get_line_item_or_404(budget_id, item_id, db)

    update_data = payload.model_dump(exclude_unset=True)

    # Currency validation if being updated
    if "currency" in update_data and update_data["currency"]:
        if update_data["currency"].strip().upper() != budget.currency.strip().upper():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Currency mismatch: line item currency '{update_data['currency']}' "
                    f"does not match budget currency '{budget.currency}'"
                ),
            )

    for field_name, value in update_data.items():
        setattr(item, field_name, value)

    db.commit()
    db.refresh(item)
    logger.info("Updated line item id=%s in budget id=%s", item.id, budget.id)
    return item


@router.delete(
    "/{budget_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete budget line item",
    description="Removes a line item from the specified budget.",
)
def delete_budget_line_item(
    event_id: uuid.UUID,
    budget_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> None:
    """Delete a BudgetLineItem."""
    get_budget_or_404(event_id, budget_id, db)
    item = get_line_item_or_404(budget_id, item_id, db)
    db.delete(item)
    db.commit()
    logger.info("Deleted line item id=%s from budget id=%s", item_id, budget_id)


# ============================================================================
# Deterministic Budget Summary Calculation
# ============================================================================


@router.get(
    "/{budget_id}/summary",
    response_model=BudgetSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate deterministic budget summary",
    description=(
        "Executes server-side deterministic Decimal calculation for all line subtotals, "
        "inclusive/exclusive tax breakdown, discounts, contingency, category totals, and budget utilization."
    ),
)
def get_budget_summary(
    event_id: uuid.UUID,
    budget_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> BudgetSummaryResponse:
    """Calculate deterministic financial breakdown for the budget."""
    budget = get_budget_or_404(event_id, budget_id, db, eager_load_items=True)

    try:
        calc_result = calculate_budget(
            items=budget.line_items,
            budget_currency=budget.currency,
            contingency_percentage=budget.contingency_percentage,
            allocated_amount=budget.allocated_amount,
            tax_policy=budget.tax_calculation_policy,
        )
    except CurrencyMismatchError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except InvalidFinancialInputError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except BudgetEngineError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    category_summaries_payload = {
        cat: CategorySummarySchema(
            category=c.category,
            raw_subtotal=c.raw_subtotal,
            discount_total=c.discount_total,
            taxable_amount=c.taxable_amount,
            tax_amount=c.tax_amount,
            total_amount=c.total_amount,
            item_count=c.item_count,
        )
        for cat, c in calc_result.category_summaries.items()
    }

    line_items_payload = [
        CalculatedLineItemSchema(
            category=li.category,
            description=li.description,
            quantity=li.quantity,
            unit_price=li.unit_price,
            raw_subtotal=li.raw_subtotal,
            discount_amount=li.discount_amount,
            discounted_base=li.discounted_base,
            tax_included=li.tax_included,
            tax_rate=li.tax_rate,
            taxable_amount=li.taxable_amount,
            tax_amount=li.tax_amount,
            line_total=li.line_total,
        )
        for li in calc_result.line_items
    ]

    return BudgetSummaryResponse(
        budget_id=budget.id,
        budget_name=budget.name,
        currency=calc_result.currency,
        item_count=calc_result.item_count,
        raw_subtotal=calc_result.raw_subtotal,
        total_discount=calc_result.total_discount,
        subtotal_before_tax=calc_result.subtotal_before_tax,
        total_tax=calc_result.total_tax,
        subtotal_with_tax=calc_result.subtotal_with_tax,
        contingency_percentage=calc_result.contingency_percentage,
        contingency_amount=calc_result.contingency_amount,
        grand_total=calc_result.grand_total,
        allocated_amount=calc_result.allocated_amount,
        remaining_budget=calc_result.remaining_budget,
        is_over_budget=calc_result.is_over_budget,
        budget_utilization_percentage=calc_result.budget_utilization_percentage,
        category_summaries=category_summaries_payload,
        line_items=line_items_payload,
    )


# ============================================================================
# Scenario Endpoints
# ============================================================================


@router.post(
    "/{budget_id}/scenarios",
    response_model=BudgetScenarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create budget scenario",
    description="Creates a budget scenario with options to clone current budget items or define custom scenario items.",
)
def create_budget_scenario(
    event_id: uuid.UUID,
    budget_id: uuid.UUID,
    payload: BudgetScenarioCreate,
    db: Session = Depends(get_db),
) -> BudgetScenario:
    """Create a new deterministic budget scenario."""
    budget = get_budget_or_404(event_id, budget_id, db, eager_load_items=True)

    contingency = (
        payload.contingency_percentage
        if payload.contingency_percentage is not None
        else budget.contingency_percentage
    )

    scenario = BudgetScenario(
        budget_id=budget.id,
        name=payload.name,
        description=payload.description,
        contingency_percentage=contingency,
    )
    db.add(scenario)
    db.flush()

    # 1. Clone from existing budget line items if requested
    if payload.clone_from_budget_items:
        for item in budget.line_items:
            scen_item = BudgetScenarioLineItem(
                scenario_id=scenario.id,
                category=item.category,
                description=item.description,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                tax_included=item.tax_included,
                tax_rate=item.tax_rate,
                discount_amount=item.discount_amount,
            )
            db.add(scen_item)

    # 2. Add explicit items if provided
    if payload.items:
        for it in payload.items:
            scen_item = BudgetScenarioLineItem(
                scenario_id=scenario.id,
                category=it.category,
                description=it.description,
                quantity=it.quantity,
                unit=it.unit,
                unit_price=it.unit_price,
                tax_included=it.tax_included,
                tax_rate=it.tax_rate,
                discount_amount=it.discount_amount,
            )
            db.add(scen_item)

    db.commit()
    db.refresh(scenario)

    logger.info("Created budget scenario id=%s for budget id=%s name='%s'", scenario.id, budget.id, scenario.name)
    return scenario


@router.get(
    "/{budget_id}/scenarios",
    response_model=List[BudgetScenarioResponse],
    status_code=status.HTTP_200_OK,
    summary="List budget scenarios",
    description="Retrieves all scenarios created for the specified budget.",
)
def list_budget_scenarios(
    event_id: uuid.UUID,
    budget_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[BudgetScenario]:
    """List scenarios for a budget."""
    budget = get_budget_or_404(event_id, budget_id, db, eager_load_scenarios=True)
    return budget.scenarios


@router.get(
    "/{budget_id}/scenarios/compare",
    response_model=BudgetScenarioCompareResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare budget scenarios",
    description=(
        "Executes multi-scenario deterministic comparisons side-by-side, analyzing total cost, "
        "category distribution, tax, contingency, and variances against allocated budget."
    ),
)
def compare_budget_scenarios(
    event_id: uuid.UUID,
    budget_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> BudgetScenarioCompareResponse:
    """Compare baseline budget against all created scenarios."""
    budget = get_budget_or_404(event_id, budget_id, db, eager_load_items=True, eager_load_scenarios=True)

    # 1. Calculate baseline budget
    base_calc = calculate_budget(
        items=budget.line_items,
        budget_currency=budget.currency,
        contingency_percentage=budget.contingency_percentage,
        allocated_amount=budget.allocated_amount,
        tax_policy=budget.tax_calculation_policy,
    )

    scenarios_list: List[ScenarioComparisonItem] = [
        ScenarioComparisonItem(
            scenario_id=None,
            scenario_name="Baseline (Current Budget)",
            description="Active line items and baseline contingency",
            total_estimated_cost=base_calc.grand_total,
            subtotal_before_tax=base_calc.subtotal_before_tax,
            total_tax=base_calc.total_tax,
            contingency_percentage=base_calc.contingency_percentage,
            contingency_amount=base_calc.contingency_amount,
            category_totals={
                cat: sum_obj.total_amount for cat, sum_obj in base_calc.category_summaries.items()
            },
            difference_from_allocated=base_calc.remaining_budget,
            is_over_budget=base_calc.is_over_budget,
        )
    ]

    # 2. Calculate each scenario
    for scen in budget.scenarios:
        scen_calc = calculate_budget(
            items=scen.line_items,
            budget_currency=budget.currency,
            contingency_percentage=scen.contingency_percentage,
            allocated_amount=budget.allocated_amount,
            tax_policy=budget.tax_calculation_policy,
        )
        scenarios_list.append(
            ScenarioComparisonItem(
                scenario_id=scen.id,
                scenario_name=scen.name,
                description=scen.description,
                total_estimated_cost=scen_calc.grand_total,
                subtotal_before_tax=scen_calc.subtotal_before_tax,
                total_tax=scen_calc.total_tax,
                contingency_percentage=scen_calc.contingency_percentage,
                contingency_amount=scen_calc.contingency_amount,
                category_totals={
                    cat: sum_obj.total_amount for cat, sum_obj in scen_calc.category_summaries.items()
                },
                difference_from_allocated=scen_calc.remaining_budget,
                is_over_budget=scen_calc.is_over_budget,
            )
        )

    return BudgetScenarioCompareResponse(
        budget_id=budget.id,
        budget_name=budget.name,
        currency=budget.currency,
        allocated_amount=budget.allocated_amount,
        scenarios=scenarios_list,
    )

