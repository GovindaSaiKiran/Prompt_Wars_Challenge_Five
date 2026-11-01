"""Pydantic schemas for Vendor and VendorService validation and serialization."""

import re
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VerificationStatus(str, Enum):
    """Lifecycle verification status of a vendor."""

    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


# Regex for basic RFC-compliant email validation
EMAIL_REGEX = re.compile(r"^[\w\.\+\-]+@[a-zA-Z0-9\-]+(\.[a-zA-Z0-9\-]+)+$")
# Regex for HTTP/HTTPS URLs
URL_REGEX = re.compile(r"^https?://[a-zA-Z0-9\-]+(\.[a-zA-Z0-9\-]+)+([/?#].*)?$")


# ============================================================================
# Vendor Service Schemas
# ============================================================================


class VendorServiceBase(BaseModel):
    """Base schema holding common vendor service attributes."""

    service_name: str = Field(..., min_length=1, max_length=255, description="Name or title of the service")
    category: str = Field(..., min_length=1, max_length=50, description="Service classification (e.g. catering, venue)")
    description: Optional[str] = Field(None, description="Detailed service description")
    unit: Optional[str] = Field(None, max_length=50, description="Pricing unit (e.g. per plate, per hour, per event)")
    minimum_quantity: Optional[Decimal] = Field(None, gt=0, description="Minimum order quantity if applicable")
    maximum_capacity: Optional[int] = Field(None, gt=0, description="Maximum attendee capacity or units servable")
    service_area: Optional[str] = Field(None, description="Geographical coverage details")
    is_active: bool = Field(default=True, description="Whether the service is currently offered")


class VendorServiceCreate(VendorServiceBase):
    """Schema for creating a new vendor service."""

    pass


class VendorServiceUpdate(BaseModel):
    """Schema for partially updating a vendor service."""

    service_name: Optional[str] = Field(None, min_length=1, max_length=255)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    unit: Optional[str] = Field(None, max_length=50)
    minimum_quantity: Optional[Decimal] = Field(None, gt=0)
    maximum_capacity: Optional[int] = Field(None, gt=0)
    service_area: Optional[str] = None
    is_active: Optional[bool] = None


class VendorServiceResponse(VendorServiceBase):
    """Public response schema for a vendor service."""

    id: uuid.UUID
    vendor_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Vendor Schemas
# ============================================================================


class VendorBase(BaseModel):
    """Base schema holding common vendor profile attributes."""

    business_name: str = Field(..., min_length=1, max_length=255, description="Registered or operating business name")
    description: Optional[str] = Field(None, description="Business profile summary")
    vendor_type: str = Field(..., min_length=1, max_length=100, description="Primary trade (e.g. Caterer, Venue, Florist)")
    contact_person: Optional[str] = Field(None, max_length=255, description="Name of representative or point of contact")
    email: Optional[str] = Field(None, max_length=255, description="Contact email address")
    phone: Optional[str] = Field(None, max_length=50, description="Contact telephone or mobile number")
    website_url: Optional[str] = Field(None, max_length=500, description="Business website or portfolio URL")
    address: Optional[str] = Field(None, description="Physical office or facility street address")
    city: Optional[str] = Field(None, max_length=100, description="Operating city")
    state: Optional[str] = Field(None, max_length=100, description="State or province")
    country: str = Field("India", max_length=100, description="Country of operation")
    postal_code: Optional[str] = Field(None, max_length=20, description="Postal code or PIN")
    verification_status: VerificationStatus = Field(default=VerificationStatus.UNVERIFIED, description="Current verification state")
    is_active: bool = Field(default=True, description="Whether vendor is currently active in directory")

    @field_validator("verification_status")
    @classmethod
    def validate_verification_status(cls, v: VerificationStatus) -> VerificationStatus:
        """Prevent public registration from setting status to verified or rejected."""
        if v in (VerificationStatus.VERIFIED, VerificationStatus.REJECTED):
            raise ValueError("Public registration cannot set verification_status to verified or rejected.")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Verify email structure if provided."""
        if v is not None:
            v = v.strip()
            if not EMAIL_REGEX.match(v):
                raise ValueError(f"Invalid email address format: '{v}'")
        return v

    @field_validator("website_url")
    @classmethod
    def validate_website_url(cls, v: Optional[str]) -> Optional[str]:
        """Verify website URL starts with http:// or https:// and contains a valid host."""
        if v is not None:
            v = v.strip()
            if not URL_REGEX.match(v):
                raise ValueError(f"Invalid URL format: '{v}'. URL must start with http:// or https://")
        return v


class VendorCreate(VendorBase):
    """Schema for registering a new vendor."""

    pass


class VendorUpdate(BaseModel):
    """Schema for partially updating an existing vendor."""

    business_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    vendor_type: Optional[str] = Field(None, min_length=1, max_length=100)
    contact_person: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    website_url: Optional[str] = Field(None, max_length=500)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, max_length=20)
    verification_status: Optional[VerificationStatus] = None
    is_active: Optional[bool] = None

    @field_validator("verification_status")
    @classmethod
    def validate_verification_status(cls, v: Optional[VerificationStatus]) -> Optional[VerificationStatus]:
        """Prevent public clients from self-verifying."""
        if v in (VerificationStatus.VERIFIED, VerificationStatus.REJECTED):
            raise ValueError("Public clients cannot set verification_status to verified or rejected.")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Verify email structure if updated."""
        if v is not None:
            v = v.strip()
            if not EMAIL_REGEX.match(v):
                raise ValueError(f"Invalid email address format: '{v}'")
        return v

    @field_validator("website_url")
    @classmethod
    def validate_website_url(cls, v: Optional[str]) -> Optional[str]:
        """Verify website URL if updated."""
        if v is not None:
            v = v.strip()
            if not URL_REGEX.match(v):
                raise ValueError(f"Invalid URL format: '{v}'. URL must start with http:// or https://")
        return v


class VendorResponse(VendorBase):
    """Public summary response schema for a vendor."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VendorDetailResponse(VendorResponse):
    """Detailed response schema for a vendor including all service offerings."""

    services: List[VendorServiceResponse] = Field(
        default_factory=list,
        description="Catalog of services offered by this vendor",
    )


class VendorListResponse(BaseModel):
    """Paginated list envelope for vendors."""

    items: List[VendorResponse]
    total: int
    skip: int
    limit: int

