"""Pydantic schemas for VendorPriceRecord, PriceEvidence, and Price Comparison."""

import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PriceType(str, Enum):
    """Pricing structure types."""

    FIXED = "fixed"
    STARTING_FROM = "starting_from"
    RANGE = "range"
    PER_UNIT = "per_unit"
    PACKAGE = "package"


class AvailabilityStatus(str, Enum):
    """Availability status for a vendor service at this price."""

    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    LIMITED = "limited"


class EvidenceType(str, Enum):
    """Classification of verification source for a price observation."""

    PUBLISHED = "published"
    VENDOR_QUOTED = "vendor_quoted"
    VENDOR_CONFIRMED = "vendor_confirmed"
    ESTIMATED = "estimated"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


# URL regex for evidence sources
URL_REGEX = re.compile(r"^https?://[a-zA-Z0-9\-]+(\.[a-zA-Z0-9\-]+)+([/?#].*)?$")
CURRENCY_REGEX = re.compile(r"^[A-Z]{3}$")


# ============================================================================
# Price Evidence Schemas
# ============================================================================


class PriceEvidenceBase(BaseModel):
    """Base schema for price evidence."""

    evidence_type: EvidenceType = Field(
        default=EvidenceType.UNKNOWN,
        description="Type/provenance of this price evidence",
    )
    source_url: Optional[str] = Field(None, max_length=500, description="Web source or public catalog link")
    source_name: Optional[str] = Field(None, max_length=255, description="Publication, website, or document name")
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when price was captured or observed",
    )
    quoted_by: Optional[str] = Field(None, max_length=255, description="Vendor representative name or email who provided quote")
    valid_until: Optional[datetime] = Field(None, description="Expiry date/time of this quote or published rate")
    inclusions: Optional[str] = Field(None, description="Scope of services covered in this rate")
    exclusions: Optional[str] = Field(None, description="Excluded costs, surcharges, or caveats")
    notes: Optional[str] = Field(None, description="Auditor or researcher notes")

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not URL_REGEX.match(v):
                raise ValueError(f"Invalid source_url: '{v}'. URL must start with http:// or https://")
        return v

    @model_validator(mode="after")
    def validate_evidence_timestamps(self) -> "PriceEvidenceBase":
        if self.valid_until is not None and self.captured_at is not None:
            if self.valid_until < self.captured_at:
                raise ValueError("valid_until timestamp cannot be earlier than captured_at")
        return self


class PriceEvidenceCreate(PriceEvidenceBase):
    """Schema for attaching evidence to a price record."""

    pass


class PriceEvidenceResponse(PriceEvidenceBase):
    """Public schema for price evidence."""

    id: uuid.UUID
    price_record_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Vendor Price Record Schemas
# ============================================================================


class VendorPriceRecordBase(BaseModel):
    """Base schema holding common vendor price record attributes."""

    amount: Decimal = Field(..., gt=0, description="Observed price amount")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="ISO 4217 currency code")
    unit: str = Field(..., min_length=1, max_length=50, description="Billing unit (e.g. per plate, per event, per hour)")
    minimum_quantity: Optional[Decimal] = Field(None, gt=0, description="Minimum order quantity for this rate")
    maximum_quantity: Optional[Decimal] = Field(None, gt=0, description="Maximum order quantity for this rate")
    price_type: PriceType = Field(default=PriceType.FIXED, description="Pricing structure")
    tax_included: Optional[bool] = Field(None, description="Whether statutory GST/tax is already included in amount")
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=100, description="Statutory tax percentage (e.g. 18.00)")
    valid_from: Optional[date] = Field(None, description="Commencement date for this rate")
    valid_until: Optional[date] = Field(None, description="Expiration date for this rate")
    availability_status: AvailabilityStatus = Field(default=AvailabilityStatus.UNKNOWN, description="Availability status")
    availability_checked_at: Optional[datetime] = Field(None, description="When availability was verified")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        v = v.strip().upper()
        if not CURRENCY_REGEX.match(v):
            raise ValueError(f"Invalid currency code: '{v}'. Must be a 3-letter uppercase ISO code (e.g. INR, USD).")
        return v

    @model_validator(mode="after")
    def validate_quantities_and_dates(self) -> "VendorPriceRecordBase":
        if self.minimum_quantity is not None and self.maximum_quantity is not None:
            if self.maximum_quantity < self.minimum_quantity:
                raise ValueError("maximum_quantity cannot be less than minimum_quantity")
        if self.valid_from is not None and self.valid_until is not None:
            if self.valid_until < self.valid_from:
                raise ValueError("valid_until date cannot be earlier than valid_from date")
        return self


class VendorPriceRecordCreate(VendorPriceRecordBase):
    """Schema for recording a new price observation."""

    vendor_id: uuid.UUID = Field(..., description="Target vendor UUID")
    vendor_service_id: uuid.UUID = Field(..., description="Target service UUID belonging to vendor")
    event_id: Optional[uuid.UUID] = Field(None, description="Optional associated event UUID")
    initial_evidence: Optional[PriceEvidenceCreate] = Field(
        None,
        description="Optional initial verification evidence attached to this price observation",
    )


class VendorPriceRecordUpdate(BaseModel):
    """Schema for updating permitted descriptive/status fields only. Historical price observations cannot be overwritten."""

    minimum_quantity: Optional[Decimal] = Field(None, gt=0, description="Minimum order quantity")
    maximum_quantity: Optional[Decimal] = Field(None, gt=0, description="Maximum order quantity")
    tax_included: Optional[bool] = Field(None, description="Whether amount includes applicable tax")
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=100, description="Statutory tax percentage")
    valid_from: Optional[date] = Field(None, description="Commencement date for this rate")
    valid_until: Optional[date] = Field(None, description="Expiration date for this rate")
    availability_status: Optional[AvailabilityStatus] = Field(None, description="Availability status")
    availability_checked_at: Optional[datetime] = Field(None, description="When availability was verified")

    @model_validator(mode="after")
    def validate_quantities_and_dates(self) -> "VendorPriceRecordUpdate":
        if self.minimum_quantity is not None and self.maximum_quantity is not None:
            if self.maximum_quantity < self.minimum_quantity:
                raise ValueError("maximum_quantity cannot be less than minimum_quantity")
        if self.valid_from is not None and self.valid_until is not None:
            if self.valid_until < self.valid_from:
                raise ValueError("valid_until date cannot be earlier than valid_from date")
        return self


class VendorPriceRecordResponse(VendorPriceRecordBase):
    """Summary response schema for a price observation."""

    id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_service_id: uuid.UUID
    event_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VendorPriceRecordDetailResponse(VendorPriceRecordResponse):
    """Detailed response schema including historical evidence records."""

    vendor_business_name: Optional[str] = Field(None, description="Name of the vendor business")
    service_name: Optional[str] = Field(None, description="Name of the service")
    evidence_records: List[PriceEvidenceResponse] = Field(
        default_factory=list,
        description="Historical and current evidence sources for this price observation",
    )


class PriceRecordListResponse(BaseModel):
    """Paginated list envelope for price records."""

    items: List[VendorPriceRecordResponse]
    total: int
    skip: int
    limit: int


# ============================================================================
# Price Comparison Schemas
# ============================================================================


class PriceComparisonItem(BaseModel):
    """Structured price observation summary for service comparison."""

    price_record_id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str
    service_id: uuid.UUID
    service_name: str
    amount: Decimal
    currency: str
    unit: str
    price_type: PriceType
    evidence_type: EvidenceType
    is_confirmed: bool = Field(
        description="Strictly True ONLY if supported by vendor_confirmed evidence. Never True for estimated/unknown.",
    )
    is_expired: bool = Field(
        description="True if evidence or rate is past its valid_until date",
    )
    captured_at: Optional[datetime]
    source_name: Optional[str]
    source_url: Optional[str]


class ServicePriceComparisonResponse(BaseModel):
    """Comprehensive multi-source price comparison for a service offering."""

    service_id: uuid.UUID
    service_name: str
    category: str
    total_observations: int
    published_prices: List[PriceComparisonItem] = Field(default_factory=list)
    vendor_quotations: List[PriceComparisonItem] = Field(default_factory=list)
    vendor_confirmed: List[PriceComparisonItem] = Field(default_factory=list)
    estimates: List[PriceComparisonItem] = Field(default_factory=list)
    expired: List[PriceComparisonItem] = Field(default_factory=list)
    unknown: List[PriceComparisonItem] = Field(default_factory=list)


# ============================================================================
# Multi-Vendor Comparison Schemas
# ============================================================================


class VendorComparisonRequest(BaseModel):
    """Request payload for comparing multiple vendors across a category or specific offerings."""

    category: Optional[str] = Field(None, description="Category of service to compare (e.g. catering, venue)")
    quantity: Decimal = Field(default=Decimal("1.00"), gt=0, description="Requested quantity for total cost calculation")
    unit: Optional[str] = Field(None, description="Requested unit of measurement (e.g. per_person, plate, hour, event)")
    vendor_ids: Optional[List[uuid.UUID]] = Field(None, description="Filter comparison to specific vendors")
    vendor_service_ids: Optional[List[uuid.UUID]] = Field(None, description="Filter comparison to specific vendor services")
    price_record_ids: Optional[List[uuid.UUID]] = Field(None, description="Filter comparison to specific price observations")
    target_city: Optional[str] = Field(None, description="Target city for proximity/location matching")
    currency: str = Field(default="INR", min_length=3, max_length=3, description="Target ISO 4217 currency code")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        v = v.strip().upper()
        if not CURRENCY_REGEX.match(v):
            raise ValueError(f"Invalid currency code: '{v}'. Must be a 3-letter uppercase ISO code.")
        return v


class MultiVendorComparisonItem(BaseModel):
    """Normalized price and vendor intelligence comparison row."""

    price_record_id: uuid.UUID
    vendor_id: uuid.UUID
    vendor_name: str
    vendor_city: Optional[str]
    verification_status: str
    service_id: uuid.UUID
    service_name: str
    category: str
    base_amount: Decimal
    currency: str
    unit: str
    price_type: PriceType
    tax_included: Optional[bool]
    tax_rate: Optional[Decimal]
    tax_status: str = Field(
        default="unknown",
        description="Tax treatment classification: 'inclusive', 'exclusive', or 'unknown'",
    )
    tax_notes: Optional[str] = Field(
        None,
        description="Explicit disclosure of tax treatment. Unknown tax is never presented as confirmed zero.",
    )
    is_compatible: bool
    compatibility_reason: Optional[str]
    normalized_quantity: Optional[Decimal]
    subtotal: Optional[Decimal]
    tax_amount: Optional[Decimal] = Field(
        None,
        description="Calculated statutory tax amount, or None if tax rate is unknown/unspecified.",
    )
    total_cost: Optional[Decimal]
    inclusions: Optional[str]
    exclusions: Optional[str]
    evidence_type: EvidenceType
    evidence_grade: str
    is_confirmed: bool = Field(
        default=False,
        description="Strictly True ONLY if supported by unexpired vendor_confirmed evidence. Never True for estimated/unknown.",
    )
    is_estimated: bool = Field(
        default=False,
        description="True if the observation is an unverified market benchmark or estimate, not an official quotation.",
    )
    source_name: Optional[str]
    source_url: Optional[str]
    captured_at: Optional[datetime]
    is_expired: bool
    valid_until: Optional[date]
    availability_status: AvailabilityStatus
    availability_checked_at: Optional[datetime]
    availability_notes: Optional[str] = Field(
        None,
        description="Explicit explanation of availability status without conflating it with evidence quality.",
    )
    location_match: Optional[bool] = Field(
        None,
        description="Administrative city name match (True/False/None).",
    )
    city_match: Optional[bool] = Field(
        None,
        description="Explicit administrative city match, not physical distance.",
    )
    location_notes: Optional[str]


class MultiVendorComparisonResponse(BaseModel):
    """Result of comparing multiple vendors for a specific service requirement."""

    requested_category: Optional[str]
    requested_quantity: Decimal
    requested_unit: Optional[str]
    requested_currency: str
    total_compared: int
    compatible_count: int
    items: List[MultiVendorComparisonItem]
    best_value_price_record_id: Optional[uuid.UUID]
    best_value_rationale: Optional[str] = None
    comparison_notes: List[str]


