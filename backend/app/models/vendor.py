"""SQLAlchemy 2.x data models for Vendors and Vendor Services."""

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
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Vendor(Base):
    """SQLAlchemy model representing a Vendor business entity."""

    __tablename__ = "vendors"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    business_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    vendor_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    contact_person: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    website_url: Mapped[Optional[str]] = mapped_column(
        String(500),
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
    postal_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    verification_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="unverified",
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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

    # 1-to-many relationship with VendorService, with cascade deletion
    services: Mapped[List["VendorService"]] = relationship(
        back_populates="vendor",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="VendorService.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('unverified', 'pending', 'verified', 'rejected')",
            name="chk_vendor_verification_status_valid",
        ),
        Index("ix_vendors_city_type", "city", "vendor_type"),
    )

    def __repr__(self) -> str:
        return f"<Vendor id={self.id} business_name='{self.business_name}' status='{self.verification_status}'>"


class VendorService(Base):
    """SQLAlchemy model representing a specific service offering by a Vendor."""

    __tablename__ = "vendor_services"

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
    service_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    unit: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    minimum_quantity: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    maximum_capacity: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    service_area: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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

    # Relationship back to Vendor
    vendor: Mapped["Vendor"] = relationship(
        back_populates="services",
    )

    __table_args__ = (
        CheckConstraint(
            "minimum_quantity IS NULL OR minimum_quantity > 0",
            name="chk_service_min_quantity_positive",
        ),
        CheckConstraint(
            "maximum_capacity IS NULL OR maximum_capacity > 0",
            name="chk_service_max_capacity_positive",
        ),
        Index("ix_services_vendor_category", "vendor_id", "category"),
    )

    def __repr__(self) -> str:
        return f"<VendorService id={self.id} vendor_id={self.vendor_id} service_name='{self.service_name}'>"

