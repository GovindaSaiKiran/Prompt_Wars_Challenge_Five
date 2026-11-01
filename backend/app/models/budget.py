"""SQLAlchemy 2.x models for Event Budget, Line Items, Scenarios, and Scenario Line Items."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EventBudget(Base):
    """SQLAlchemy model representing an Event Budget."""

    __tablename__ = "event_budgets"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        index=True,
    )
    allocated_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2),
        nullable=True,
    )
    contingency_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("10.00"),
    )
    tax_calculation_policy: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="standard",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    event = relationship("Event", back_populates="budgets")
    line_items: Mapped[List["BudgetLineItem"]] = relationship(
        back_populates="budget",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BudgetLineItem.created_at.asc()",
    )
    scenarios: Mapped[List["BudgetScenario"]] = relationship(
        back_populates="budget",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BudgetScenario.created_at.asc()",
    )

    __table_args__ = (
        CheckConstraint(
            "allocated_amount IS NULL OR allocated_amount >= 0",
            name="chk_budget_allocated_nonnegative",
        ),
        CheckConstraint(
            "contingency_percentage >= 0 AND contingency_percentage <= 100",
            name="chk_budget_contingency_range",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="chk_budget_status_valid",
        ),
        CheckConstraint(
            "tax_calculation_policy IN ('standard', 'exclusive', 'inclusive')",
            name="chk_budget_tax_policy_valid",
        ),
        Index("ix_budget_event_status", "event_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<EventBudget id={self.id} event_id={self.event_id} name='{self.name}' status='{self.status}'>"


class BudgetLineItem(Base):
    """SQLAlchemy model representing an individual budget line item.

    Captures snapshotted financial figures so future updates to linked vendor price
    observations do not retroactively alter the budget.
    """

    __tablename__ = "budget_line_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    budget_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("event_budgets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_requirement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("event_requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    vendor_price_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("vendor_price_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("1.00"),
    )
    unit: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="item",
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )
    tax_included: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    budget: Mapped["EventBudget"] = relationship(
        back_populates="line_items",
    )
    event_requirement = relationship("EventRequirement")
    vendor_price_record = relationship("VendorPriceRecord")

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="chk_line_item_quantity_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="chk_line_item_unit_price_nonnegative",
        ),
        CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 100",
            name="chk_line_item_tax_rate_range",
        ),
        CheckConstraint(
            "discount_amount >= 0",
            name="chk_line_item_discount_nonnegative",
        ),
        CheckConstraint(
            "category IN ('venue', 'catering', 'photography', 'decoration', 'entertainment', "
            "'transport', 'accommodation', 'equipment', 'security', 'other')",
            name="chk_line_item_category_valid",
        ),
        Index("ix_line_items_budget_category", "budget_id", "category"),
    )

    def __repr__(self) -> str:
        return f"<BudgetLineItem id={self.id} budget_id={self.budget_id} category='{self.category}' description='{self.description}'>"


class BudgetScenario(Base):
    """SQLAlchemy model representing a deterministic Budget Scenario."""

    __tablename__ = "budget_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    budget_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("event_budgets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    contingency_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("10.00"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    budget: Mapped["EventBudget"] = relationship(
        back_populates="scenarios",
    )
    line_items: Mapped[List["BudgetScenarioLineItem"]] = relationship(
        back_populates="scenario",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BudgetScenarioLineItem.created_at.asc()",
    )

    __table_args__ = (
        CheckConstraint(
            "contingency_percentage >= 0 AND contingency_percentage <= 100",
            name="chk_scenario_contingency_range",
        ),
        Index("ix_scenario_budget_name", "budget_id", "name"),
    )

    def __repr__(self) -> str:
        return f"<BudgetScenario id={self.id} budget_id={self.budget_id} name='{self.name}'>"


class BudgetScenarioLineItem(Base):
    """SQLAlchemy model representing a line item in a budget scenario."""

    __tablename__ = "budget_scenario_line_items"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("budget_scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("1.00"),
    )
    unit: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="item",
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    tax_included: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationship
    scenario: Mapped["BudgetScenario"] = relationship(
        back_populates="line_items",
    )

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="chk_scen_item_quantity_positive",
        ),
        CheckConstraint(
            "unit_price >= 0",
            name="chk_scen_item_unit_price_nonnegative",
        ),
        CheckConstraint(
            "tax_rate >= 0 AND tax_rate <= 100",
            name="chk_scen_item_tax_rate_range",
        ),
        CheckConstraint(
            "discount_amount >= 0",
            name="chk_scen_item_discount_nonnegative",
        ),
        CheckConstraint(
            "category IN ('venue', 'catering', 'photography', 'decoration', 'entertainment', "
            "'transport', 'accommodation', 'equipment', 'security', 'other')",
            name="chk_scen_item_category_valid",
        ),
        Index("ix_scen_items_scenario_category", "scenario_id", "category"),
    )

    def __repr__(self) -> str:
        return f"<BudgetScenarioLineItem id={self.id} scenario_id={self.scenario_id} category='{self.category}'>"

