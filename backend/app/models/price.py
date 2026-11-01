"""SQLAlchemy 2.x data models for Vendor Price Records and Price Evidence."""

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
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class VendorPriceRecord(Base):
    """SQLAlchemy model representing an observed vendor price point."""

    __tablename__ = "vendor_price_records"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("vendors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vendor_service_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("vendor_services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        index=True,
    )
    unit: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    minimum_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    maximum_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    price_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="fixed",
        index=True,
    )
    tax_included: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    tax_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    valid_from: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    valid_until: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    availability_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="unknown",
        index=True,
    )
    availability_checked_at: Mapped[Optional[datetime]] = mapped_column(
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
    vendor = relationship("Vendor")
    vendor_service = relationship("VendorService")
    event = relationship("Event")

    @property
    def vendor_business_name(self) -> Optional[str]:
        """Convenience property for vendor business name."""
        return self.vendor.business_name if self.vendor else None

    @property
    def service_name(self) -> Optional[str]:
        """Convenience property for service name."""
        return self.vendor_service.service_name if self.vendor_service else None

    evidence_records: Mapped[List["PriceEvidence"]] = relationship(
        back_populates="price_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PriceEvidence.captured_at.desc()",
    )

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="chk_price_amount_positive",
        ),
        CheckConstraint(
            "minimum_quantity IS NULL OR minimum_quantity > 0",
            name="chk_price_min_quantity_positive",
        ),
        CheckConstraint(
            "maximum_quantity IS NULL OR maximum_quantity > 0",
            name="chk_price_max_quantity_positive",
        ),
        CheckConstraint(
            "minimum_quantity IS NULL OR maximum_quantity IS NULL OR maximum_quantity >= minimum_quantity",
            name="chk_price_quantity_range_valid",
        ),
        CheckConstraint(
            "tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 100)",
            name="chk_price_tax_rate_range",
        ),
        CheckConstraint(
            "valid_from IS NULL OR valid_until IS NULL OR valid_until >= valid_from",
            name="chk_price_date_order_valid",
        ),
        CheckConstraint(
            "price_type IN ('fixed', 'starting_from', 'range', 'per_unit', 'package')",
            name="chk_price_type_valid",
        ),
        CheckConstraint(
            "availability_status IN ('unknown', 'available', 'unavailable', 'limited')",
            name="chk_price_availability_valid",
        ),
        Index("ix_price_vendor_service", "vendor_id", "vendor_service_id"),
        Index("ix_price_currency_type", "currency", "price_type"),
    )

    def __repr__(self) -> str:
        return f"<VendorPriceRecord id={self.id} amount={self.amount} currency='{self.currency}' type='{self.price_type}'>"


class PriceEvidence(Base):
    """SQLAlchemy model representing an audit source or proof for a price record."""

    __tablename__ = "price_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    price_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("vendor_price_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="unknown",
        index=True,
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    source_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    quoted_by: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    inclusions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    exclusions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
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

    # Relationship back to price record
    price_record: Mapped["VendorPriceRecord"] = relationship(
        back_populates="evidence_records",
    )

    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('published', 'vendor_quoted', 'vendor_confirmed', 'estimated', 'expired', 'unknown')",
            name="chk_evidence_type_valid",
        ),
    )

    def __repr__(self) -> str:
        return f"<PriceEvidence id={self.id} record_id={self.price_record_id} type='{self.evidence_type}'>"

