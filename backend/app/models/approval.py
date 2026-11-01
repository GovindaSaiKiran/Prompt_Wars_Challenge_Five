"""SQLAlchemy 2.x data model for Plan Approvals and Idempotency tracking."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PlanApproval(Base):
    """SQLAlchemy model representing an approved and committed event plan with idempotency tracking."""

    __tablename__ = "plan_approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    approval_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    response_payload: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationship to Event
    event = relationship("Event")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_plan_approval_idempotency_key"),
        Index("ix_plan_approvals_event_plan", "event_id", "plan_id"),
    )

    def __repr__(self) -> str:
        return f"<PlanApproval id={self.id} key='{self.idempotency_key}' event_id={self.event_id}>"

