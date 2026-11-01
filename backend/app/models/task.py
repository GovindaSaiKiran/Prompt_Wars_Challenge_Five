"""SQLAlchemy 2.x data models for Event Tasks, Task Dependencies, and Append-Only Activity Log."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EventTask(Base):
    """SQLAlchemy model representing an Event Task with scheduling, cost estimates, and assignments."""

    __tablename__ = "event_tasks"

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
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
        index=True,
    )
    start_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    due_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    estimated_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    actual_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )
    assigned_to: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
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
    event = relationship("Event", back_populates="tasks")

    # Dependencies where this task is the successor (depends on predecessors)
    predecessor_dependencies: Mapped[List["TaskDependency"]] = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.successor_task_id",
        back_populates="successor_task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Dependencies where this task is the predecessor (blocks successors)
    successor_dependencies: Mapped[List["TaskDependency"]] = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.predecessor_task_id",
        back_populates="predecessor_task",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Append-only chronological activity log (preserved across task soft deletion)
    activity_history: Mapped[List["TaskActivity"]] = relationship(
        "TaskActivity",
        back_populates="task",
        order_by="TaskActivity.created_at.asc()",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'blocked', 'completed', 'cancelled')",
            name="chk_task_status_valid",
        ),
        CheckConstraint(
            "priority IN ('low', 'medium', 'high', 'critical')",
            name="chk_task_priority_valid",
        ),
        CheckConstraint(
            "category IN ('planning', 'venue', 'catering', 'photography', 'decoration', "
            "'entertainment', 'transport', 'accommodation', 'finance', 'invitations', "
            "'logistics', 'other')",
            name="chk_task_category_valid",
        ),
        CheckConstraint(
            "estimated_cost IS NULL OR estimated_cost >= 0",
            name="chk_task_estimated_cost_positive",
        ),
        CheckConstraint(
            "actual_cost IS NULL OR actual_cost >= 0",
            name="chk_task_actual_cost_positive",
        ),
        CheckConstraint(
            "start_date IS NULL OR due_date IS NULL OR due_date >= start_date",
            name="chk_task_date_order",
        ),
        Index("ix_task_event_status", "event_id", "status"),
        Index("ix_task_event_category", "event_id", "category"),
        Index("ix_task_event_due_date", "event_id", "due_date"),
        Index("ix_task_event_is_deleted", "event_id", "is_deleted"),
    )

    def __repr__(self) -> str:
        return f"<EventTask id={self.id} event_id={self.event_id} title='{self.title}' status='{self.status}'>"


class TaskDependency(Base):
    """SQLAlchemy model representing a directed dependency relationship between two event tasks."""

    __tablename__ = "task_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    predecessor_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("event_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    successor_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("event_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dependency_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="finish_to_start",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    predecessor_task: Mapped["EventTask"] = relationship(
        "EventTask",
        foreign_keys=[predecessor_task_id],
        back_populates="successor_dependencies",
    )
    successor_task: Mapped["EventTask"] = relationship(
        "EventTask",
        foreign_keys=[successor_task_id],
        back_populates="predecessor_dependencies",
    )

    __table_args__ = (
        CheckConstraint(
            "dependency_type IN ('finish_to_start', 'start_to_start', 'finish_to_finish', 'start_to_finish')",
            name="chk_dep_type_valid",
        ),
        CheckConstraint(
            "predecessor_task_id != successor_task_id",
            name="chk_dep_no_self",
        ),
        UniqueConstraint(
            "predecessor_task_id",
            "successor_task_id",
            name="uq_task_dependency_pair",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<TaskDependency pred={self.predecessor_task_id} "
            f"succ={self.successor_task_id} type='{self.dependency_type}'>"
        )


class TaskActivity(Base):
    """SQLAlchemy model representing an append-only audit activity log entry for a task."""

    __tablename__ = "task_activities"

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
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("event_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    action_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    previous_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    new_value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Relationships
    task: Mapped[Optional["EventTask"]] = relationship(
        "EventTask",
        back_populates="activity_history",
    )
    event: Mapped["Event"] = relationship(
        "Event",
    )

    __table_args__ = (
        Index("ix_task_activity_event_task", "event_id", "task_id"),
    )

    def __repr__(self) -> str:
        return f"<TaskActivity id={self.id} event_id={self.event_id} task_id={self.task_id} action='{self.action_type}'>"

