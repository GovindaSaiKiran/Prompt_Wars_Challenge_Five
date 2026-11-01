"""Deterministic Event Budget Calculation Engine.

Implements financial arithmetic using strictly Python Decimal (never binary floating-point)
with ROUND_HALF_UP precision. Calculates line subtotals, inclusive/exclusive tax breakdown,
discounts, contingencies, category aggregates, budget utilization, and scenario variances.
"""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Protocol, Sequence


# Currency precision standard (2 decimal places)
TWO_PLACES = Decimal("0.01")


def quantize_money(amount: Decimal) -> Decimal:
    """Quantize a Decimal amount to 2 decimal places using standard ROUND_HALF_UP."""
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


class BudgetEngineError(ValueError):
    """Base exception for budget calculation engine errors."""
    pass


class CurrencyMismatchError(BudgetEngineError):
    """Raised when line items have mismatched currencies within a single budget."""
    pass


class InvalidFinancialInputError(BudgetEngineError):
    """Raised when quantity, price, tax rate, or discount fails business validation."""
    pass


class LineItemProtocol(Protocol):
    """Protocol defining the required properties of a line item for budget calculations."""
    category: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    currency: Optional[str]
    tax_included: bool
    tax_rate: Decimal
    discount_amount: Decimal


@dataclass(frozen=True)
class CalculatedLineItem:
    """Detailed deterministic breakdown for an individual line item."""
    category: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    raw_subtotal: Decimal
    discount_amount: Decimal
    discounted_base: Decimal
    tax_included: bool
    tax_rate: Decimal
    taxable_amount: Decimal  # Net base amount before tax
    tax_amount: Decimal       # Calculated statutory tax
    line_total: Decimal       # Final total payable for this line (base + tax or inclusive)


@dataclass(frozen=True)
class CategorySummary:
    """Category-level aggregation of costs and statutory tax."""
    category: str
    raw_subtotal: Decimal
    discount_total: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    item_count: int


@dataclass(frozen=True)
class BudgetCalculationResult:
    """Complete deterministic breakdown of budget totals, tax, contingency, and utilization."""
    currency: str
    item_count: int
    raw_subtotal: Decimal
    total_discount: Decimal
    subtotal_before_tax: Decimal
    total_tax: Decimal
    subtotal_with_tax: Decimal
    contingency_percentage: Decimal
    contingency_amount: Decimal
    grand_total: Decimal
    allocated_amount: Optional[Decimal]
    remaining_budget: Optional[Decimal]
    is_over_budget: bool
    budget_utilization_percentage: Optional[Decimal]
    category_summaries: Dict[str, CategorySummary]
    line_items: List[CalculatedLineItem]


def calculate_line_item(
    quantity: Decimal,
    unit_price: Decimal,
    tax_included: bool,
    tax_rate: Decimal,
    discount_amount: Decimal = Decimal("0.00"),
    tax_policy: str = "standard",
    category: str = "other",
    description: str = "",
) -> CalculatedLineItem:
    """Deterministically calculate a single line item's taxes, discounts, and total.

    Tax Treatment Rules:
    - Policy 'standard': respects line item's own tax_included flag.
    - Policy 'inclusive': forces tax_included=True (rate quoted includes all taxes).
    - Policy 'exclusive': forces tax_included=False (tax calculated on top of net base).

    Calculations:
    - raw_subtotal = quantize(quantity * unit_price)
    - discount = min(discount_amount, raw_subtotal)
    - discounted_base = raw_subtotal - discount
    - If tax_included:
        taxable_amount = quantize(discounted_base / (1 + tax_rate/100))
        tax_amount = discounted_base - taxable_amount
        line_total = discounted_base
    - If tax_excluded:
        taxable_amount = discounted_base
        tax_amount = quantize(taxable_amount * (tax_rate/100))
        line_total = taxable_amount + tax_amount
    """
    if quantity <= Decimal("0"):
        raise InvalidFinancialInputError(f"Quantity must be positive (> 0), got {quantity}")
    if unit_price < Decimal("0"):
        raise InvalidFinancialInputError(f"Unit price cannot be negative, got {unit_price}")
    if discount_amount < Decimal("0"):
        raise InvalidFinancialInputError(f"Discount amount cannot be negative, got {discount_amount}")
    if tax_rate < Decimal("0") or tax_rate > Decimal("100"):
        raise InvalidFinancialInputError(f"Tax rate must be between 0% and 100%, got {tax_rate}")

    # 1. Base subtotal and capped discount
    raw_subtotal = quantize_money(quantity * unit_price)
    effective_discount = quantize_money(min(discount_amount, raw_subtotal))
    discounted_base = raw_subtotal - effective_discount

    # 2. Determine tax policy
    is_inclusive = tax_included
    if tax_policy == "inclusive":
        is_inclusive = True
    elif tax_policy == "exclusive":
        is_inclusive = False

    # 3. Calculate tax breakdown
    if tax_rate == Decimal("0"):
        taxable_amount = discounted_base
        tax_amount = Decimal("0.00")
        line_total = discounted_base
    elif is_inclusive:
        # Price includes tax: base = total / (1 + r)
        divisor = Decimal("1") + (tax_rate / Decimal("100"))
        taxable_amount = quantize_money(discounted_base / divisor)
        tax_amount = discounted_base - taxable_amount
        line_total = discounted_base
    else:
        # Price excludes tax: tax = base * r
        taxable_amount = discounted_base
        tax_amount = quantize_money(taxable_amount * (tax_rate / Decimal("100")))
        line_total = taxable_amount + tax_amount

    return CalculatedLineItem(
        category=category,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        raw_subtotal=raw_subtotal,
        discount_amount=effective_discount,
        discounted_base=discounted_base,
        tax_included=is_inclusive,
        tax_rate=tax_rate,
        taxable_amount=taxable_amount,
        tax_amount=tax_amount,
        line_total=line_total,
    )


def calculate_budget(
    items: Sequence[LineItemProtocol],
    budget_currency: str = "INR",
    contingency_percentage: Decimal = Decimal("10.00"),
    allocated_amount: Optional[Decimal] = None,
    tax_policy: str = "standard",
) -> BudgetCalculationResult:
    """Calculate deterministic budget totals, category summaries, taxes, and contingency.

    Validates:
    - Consistent currencies across all line items
    - Non-negative allocated budget
    - Valid contingency percentage (0-100)
    """
    if contingency_percentage < Decimal("0") or contingency_percentage > Decimal("100"):
        raise InvalidFinancialInputError(
            f"Contingency percentage must be between 0% and 100%, got {contingency_percentage}"
        )
    if allocated_amount is not None and allocated_amount < Decimal("0"):
        raise InvalidFinancialInputError(
            f"Allocated budget amount cannot be negative, got {allocated_amount}"
        )

    calculated_items: List[CalculatedLineItem] = []
    category_accum: Dict[str, Dict[str, Decimal]] = {}

    total_raw_subtotal = Decimal("0.00")
    total_discount = Decimal("0.00")
    subtotal_before_tax = Decimal("0.00")
    total_tax = Decimal("0.00")
    subtotal_with_tax = Decimal("0.00")

    for item in items:
        # Validate currency consistency
        item_cur = getattr(item, "currency", None)
        if item_cur and item_cur.strip().upper() != budget_currency.strip().upper():
            raise CurrencyMismatchError(
                f"Currency mismatch: line item '{item.description}' has currency '{item_cur}', "
                f"which does not match budget currency '{budget_currency}'"
            )

        calc_line = calculate_line_item(
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax_included=item.tax_included,
            tax_rate=item.tax_rate,
            discount_amount=item.discount_amount,
            tax_policy=tax_policy,
            category=item.category,
            description=item.description,
        )
        calculated_items.append(calc_line)

        # Accumulate totals
        total_raw_subtotal += calc_line.raw_subtotal
        total_discount += calc_line.discount_amount
        subtotal_before_tax += calc_line.taxable_amount
        total_tax += calc_line.tax_amount
        subtotal_with_tax += calc_line.line_total

        # Category accumulation
        cat = calc_line.category
        if cat not in category_accum:
            category_accum[cat] = {
                "raw_subtotal": Decimal("0.00"),
                "discount_total": Decimal("0.00"),
                "taxable_amount": Decimal("0.00"),
                "tax_amount": Decimal("0.00"),
                "total_amount": Decimal("0.00"),
                "count": Decimal("0"),
            }
        category_accum[cat]["raw_subtotal"] += calc_line.raw_subtotal
        category_accum[cat]["discount_total"] += calc_line.discount_amount
        category_accum[cat]["taxable_amount"] += calc_line.taxable_amount
        category_accum[cat]["tax_amount"] += calc_line.tax_amount
        category_accum[cat]["total_amount"] += calc_line.line_total
        category_accum[cat]["count"] += Decimal("1")

    # Build category summaries
    category_summaries: Dict[str, CategorySummary] = {}
    for cat, accum in sorted(category_accum.items()):
        category_summaries[cat] = CategorySummary(
            category=cat,
            raw_subtotal=accum["raw_subtotal"],
            discount_total=accum["discount_total"],
            taxable_amount=accum["taxable_amount"],
            tax_amount=accum["tax_amount"],
            total_amount=accum["total_amount"],
            item_count=int(accum["count"]),
        )

    # Contingency and grand total
    contingency_factor = contingency_percentage / Decimal("100")
    contingency_amount = quantize_money(subtotal_with_tax * contingency_factor)
    grand_total = subtotal_with_tax + contingency_amount

    # Budget allocation metrics
    remaining_budget: Optional[Decimal] = None
    is_over_budget = False
    utilization_percentage: Optional[Decimal] = None

    if allocated_amount is not None:
        remaining_budget = allocated_amount - grand_total
        is_over_budget = grand_total > allocated_amount
        if allocated_amount > Decimal("0"):
            utilization_percentage = quantize_money((grand_total / allocated_amount) * Decimal("100"))
        else:
            utilization_percentage = Decimal("0.00")

    return BudgetCalculationResult(
        currency=budget_currency.strip().upper(),
        item_count=len(calculated_items),
        raw_subtotal=total_raw_subtotal,
        total_discount=total_discount,
        subtotal_before_tax=subtotal_before_tax,
        total_tax=total_tax,
        subtotal_with_tax=subtotal_with_tax,
        contingency_percentage=contingency_percentage,
        contingency_amount=contingency_amount,
        grand_total=grand_total,
        allocated_amount=allocated_amount,
        remaining_budget=remaining_budget,
        is_over_budget=is_over_budget,
        budget_utilization_percentage=utilization_percentage,
        category_summaries=category_summaries,
        line_items=calculated_items,
    )

