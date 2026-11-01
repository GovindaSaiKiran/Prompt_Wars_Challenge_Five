"""Pydantic schemas for Event Budgets, Line Items, Scenarios, and Financial Summaries."""

import re
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CURRENCY_REGEX = re.compile(r"^[A-Z]{3}$")

VALID_CATEGORIES = {
    "venue",
    "catering",
    "photography",
    "decoration",
    "entertainment",
    "transport",
    "accommodation",
    "equipment",
    "security",
    "other",
}


class BudgetStatus(str, Enum):
    """Budget lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class TaxCalculationPolicy(str, Enum):
    """Tax calculation policy."""
    STANDARD = "standard"    # Respect individual line item tax_included flag
    EXCLUSIVE = "exclusive"  # Force all line items as tax exclusive
    INCLUSIVE = "inclusive"  # Force all line items as tax inclusive


# ============================================================================
# Line Item Schemas
# ============================================================================


class BudgetLineItemBase(BaseModel):
    """Base fields for a budget line item."""

    category: str = Field(..., description="Service or expenditure category")
    description: str = Field(..., min_length=1, max_length=255, description="Item description")
    quantity: Decimal = Field(default=Decimal("1.00"), gt=0, description="Required quantity")
    unit: str = Field(default="item", max_length=50, description="Unit of measurement")
    unit_price: Decimal = Field(..., ge=0, description="Price per unit (snapshotted from observation or manually entered)")
    currency: str = Field(default="INR", description="ISO 4217 3-letter currency code")
    tax_included: bool = Field(default=False, description="Whether unit_price includes tax")
    tax_rate: Decimal = Field(default=Decimal("0.00"), ge=0, le=100, description="Tax rate percentage (0-100)")
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0, description="Deduction or discount amount")
    notes: Optional[str] = Field(None, description="Optional annotations")
    event_requirement_id: Optional[uuid.UUID] = Field(None, description="Optional linked requirement ID")
    vendor_price_record_id: Optional[uuid.UUID] = Field(None, description="Optional linked vendor price record ID")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        v = v.strip().upper()
        if not CURRENCY_REGEX.match(v):
            raise ValueError(f"Invalid currency code: '{v}'. Must be a 3-letter uppercase ISO code.")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: '{v}'. Must be one of: {sorted(VALID_CATEGORIES)}")
        return clean


class BudgetLineItemCreate(BaseModel):
    """Creation payload for budget line item.

    If vendor_price_record_id is supplied, unit_price, unit, currency, tax_included,
    and tax_rate can be omitted and will be populated automatically as a snapshot.
    """

    category: str = Field(..., description="Service or expenditure category")
    description: str = Field(..., min_length=1, max_length=255, description="Item description")
    quantity: Decimal = Field(default=Decimal("1.00"), gt=0, description="Required quantity")
    unit: Optional[str] = Field(None, max_length=50, description="Unit of measurement")
    unit_price: Optional[Decimal] = Field(None, ge=0, description="Unit price")
    currency: Optional[str] = Field(None, description="ISO currency code")
    tax_included: Optional[bool] = Field(None, description="Whether unit price includes tax")
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=100, description="Tax rate percentage")
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0, description="Discount deduction")
    notes: Optional[str] = Field(None, description="Optional annotations")
    event_requirement_id: Optional[uuid.UUID] = Field(None, description="Linked requirement ID")
    vendor_price_record_id: Optional[uuid.UUID] = Field(None, description="Linked vendor price record ID")

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: '{v}'. Must be one of: {sorted(VALID_CATEGORIES)}")
        return clean


class BudgetLineItemUpdate(BaseModel):
    """Schema for updating a budget line item."""

    category: Optional[str] = None
    description: Optional[str] = Field(None, min_length=1, max_length=255)
    quantity: Optional[Decimal] = Field(None, gt=0)
    unit: Optional[str] = Field(None, max_length=50)
    unit_price: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = None
    tax_included: Optional[bool] = None
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    discount_amount: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().upper()
        if not CURRENCY_REGEX.match(v):
            raise ValueError(f"Invalid currency code: '{v}'. Must be a 3-letter uppercase ISO code.")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip().lower()
        if clean not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: '{v}'. Must be one of: {sorted(VALID_CATEGORIES)}")
        return clean


class BudgetLineItemResponse(BudgetLineItemBase):
    """Response schema for a budget line item with snapshotted fields."""

    id: uuid.UUID
    budget_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Budget Schemas
# ============================================================================


class EventBudgetBase(BaseModel):
    """Base fields for an Event Budget."""

    name: str = Field(..., min_length=1, max_length=255, description="Budget name")
    currency: str = Field(default="INR", description="ISO 4217 3-letter currency code")
    allocated_amount: Optional[Decimal] = Field(None, ge=0, description="Total budget ceiling allocated")
    contingency_percentage: Decimal = Field(
        default=Decimal("10.00"),
        ge=0,
        le=100,
        description="Contingency buffer percentage",
    )
    tax_calculation_policy: TaxCalculationPolicy = Field(
        default=TaxCalculationPolicy.STANDARD,
        description="Tax policy: standard, exclusive, or inclusive",
    )
    status: BudgetStatus = Field(default=BudgetStatus.DRAFT, description="Budget status")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        v = v.strip().upper()
        if not CURRENCY_REGEX.match(v):
            raise ValueError(f"Invalid currency code: '{v}'. Must be a 3-letter uppercase ISO code.")
        return v


class EventBudgetCreate(EventBudgetBase):
    """Schema for creating a new Event Budget."""
    pass


class EventBudgetUpdate(BaseModel):
    """Schema for updating an Event Budget."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    currency: Optional[str] = None
    allocated_amount: Optional[Decimal] = Field(None, ge=0)
    contingency_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    tax_calculation_policy: Optional[TaxCalculationPolicy] = None
    status: Optional[BudgetStatus] = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip().upper()
        if not CURRENCY_REGEX.match(v):
            raise ValueError(f"Invalid currency code: '{v}'. Must be a 3-letter uppercase ISO code.")
        return v


class EventBudgetResponse(EventBudgetBase):
    """Response schema for an Event Budget."""

    id: uuid.UUID
    event_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventBudgetDetailResponse(EventBudgetResponse):
    """Detailed response schema for an Event Budget including line items."""

    line_items: List[BudgetLineItemResponse] = Field(default_factory=list)


# ============================================================================
# Summary & Calculation Schemas
# ============================================================================


class CalculatedLineItemSchema(BaseModel):
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
    taxable_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal


class CategorySummarySchema(BaseModel):
    """Category-level aggregation of costs and statutory tax."""

    category: str
    raw_subtotal: Decimal
    discount_total: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    item_count: int


class BudgetSummaryResponse(BaseModel):
    """Structured deterministic financial calculation summary for an Event Budget."""

    budget_id: uuid.UUID
    budget_name: str
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
    category_summaries: Dict[str, CategorySummarySchema]
    line_items: List[CalculatedLineItemSchema]


# ============================================================================
# Scenario Schemas
# ============================================================================


class BudgetScenarioLineItemCreate(BaseModel):
    """Schema for adding a line item to a scenario."""

    category: str = Field(..., description="Service or expenditure category")
    description: str = Field(..., min_length=1, max_length=255)
    quantity: Decimal = Field(default=Decimal("1.00"), gt=0)
    unit: str = Field(default="item", max_length=50)
    unit_price: Decimal = Field(..., ge=0)
    tax_included: bool = Field(default=False)
    tax_rate: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        clean = v.strip().lower()
        if clean not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category: '{v}'. Must be one of: {sorted(VALID_CATEGORIES)}")
        return clean


class BudgetScenarioLineItemResponse(BaseModel):
    """Response schema for a scenario line item."""

    id: uuid.UUID
    scenario_id: uuid.UUID
    category: str
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    tax_included: bool
    tax_rate: Decimal
    discount_amount: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BudgetScenarioCreate(BaseModel):
    """Schema for creating a budget scenario."""

    name: str = Field(..., min_length=1, max_length=100, description="Scenario name (e.g., Low-cost, Recommended, Premium)")
    description: Optional[str] = Field(None, description="Scenario assumptions and source description")
    contingency_percentage: Optional[Decimal] = Field(None, ge=0, le=100, description="Contingency buffer percentage")
    clone_from_budget_items: bool = Field(
        default=False,
        description="Whether to clone all current budget line items into this scenario",
    )
    items: Optional[List[BudgetScenarioLineItemCreate]] = Field(
        None,
        description="Explicit scenario line items",
    )


class BudgetScenarioResponse(BaseModel):
    """Response schema for a budget scenario."""

    id: uuid.UUID
    budget_id: uuid.UUID
    name: str
    description: Optional[str]
    contingency_percentage: Decimal
    created_at: datetime
    updated_at: datetime
    line_items: List[BudgetScenarioLineItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ScenarioComparisonItem(BaseModel):
    """Individual scenario row in a comparison breakdown."""

    scenario_id: Optional[uuid.UUID] = Field(None, description="UUID or None for baseline budget")
    scenario_name: str
    description: Optional[str]
    total_estimated_cost: Decimal
    subtotal_before_tax: Decimal
    total_tax: Decimal
    contingency_percentage: Decimal
    contingency_amount: Decimal
    category_totals: Dict[str, Decimal]
    difference_from_allocated: Optional[Decimal]
    is_over_budget: bool


class BudgetScenarioCompareResponse(BaseModel):
    """Comprehensive comparison of budget scenarios against baseline and allocated budget."""

    budget_id: uuid.UUID
    budget_name: str
    currency: str
    allocated_amount: Optional[Decimal]
    scenarios: List[ScenarioComparisonItem]

