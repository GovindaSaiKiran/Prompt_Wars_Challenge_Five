"""SQLAlchemy 2.x data models for Events and Event Requirements."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Event(Base):
    """SQLAlchemy model representing an Event entity."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    event_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    start_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    end_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    timezone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="Asia/Kolkata",
    )
    expected_attendees: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    location_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    city: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    state: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    country: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="India",
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

    # 1-to-many relationship with EventRequirement, cascade delete when Event is removed
    requirements: Mapped[List["EventRequirement"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="EventRequirement.created_at",
    )

    # 1-to-many relationship with EventBudget, cascade delete when Event is removed
    budgets: Mapped[List["EventBudget"]] = relationship(
        "EventBudget",
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="EventBudget.created_at",
    )

    # 1-to-many relationship with EventTask, cascade delete when Event is removed
    tasks: Mapped[List["EventTask"]] = relationship(
        "EventTask",
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="EventTask.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            "expected_attendees IS NULL OR expected_attendees > 0",
            name="chk_event_attendees_positive",
        ),
        CheckConstraint(
            "status IN ('draft', 'planning', 'confirmed', 'completed', 'cancelled')",
            name="chk_event_status_valid",
        ),
        Index("ix_events_date_city", "event_date", "city"),
    )

    def __repr__(self) -> str:
        return f"<Event id={self.id} name='{self.name}' status='{self.status}'>"


class EventRequirement(Base):
    """SQLAlchemy model representing an Event Requirement line item."""

    __tablename__ = "event_requirements"

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
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    unit: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        index=True,
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

    # Relationship back to Event
    event: Mapped["Event"] = relationship(
        back_populates="requirements",
    )

    __table_args__ = (
        CheckConstraint(
            "quantity IS NULL OR quantity > 0",
            name="chk_req_quantity_positive",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="chk_req_priority_valid",
        ),
        CheckConstraint(
            "category IN ('venue', 'catering', 'photography', 'decoration', 'entertainment', "
            "'transport', 'accommodation', 'equipment', 'security', 'other')",
            name="chk_req_category_valid",
        ),
        Index("ix_requirements_event_category", "event_id", "category"),
    )

    def __repr__(self) -> str:
        return f"<EventRequirement id={self.id} event_id={self.event_id} title='{self.title}'>"

