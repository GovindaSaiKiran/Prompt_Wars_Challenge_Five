"""Pydantic schemas for Event and EventRequirement validation and serialization."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventStatus(str, Enum):
    """Lifecycle statuses for an event."""

    DRAFT = "draft"
    PLANNING = "planning"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RequirementCategory(str, Enum):
    """Standard requirement service categories."""

    VENUE = "venue"
    CATERING = "catering"
    PHOTOGRAPHY = "photography"
    DECORATION = "decoration"
    ENTERTAINMENT = "entertainment"
    TRANSPORT = "transport"
    ACCOMMODATION = "accommodation"
    EQUIPMENT = "equipment"
    SECURITY = "security"
    OTHER = "other"


class RequirementPriority(str, Enum):
    """Requirement priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# Event Requirement Schemas
# ============================================================================


class EventRequirementBase(BaseModel):
    """Base requirement schema holding common attributes."""

    category: RequirementCategory
    title: str = Field(..., min_length=1, max_length=255, description="Brief title of the requirement")
    description: Optional[str] = Field(None, description="Detailed requirement specification")
    quantity: Optional[Decimal] = Field(None, gt=0, description="Optional positive quantity needed")
    unit: Optional[str] = Field(None, max_length=50, description="Unit of measurement (e.g. guests, hours, rooms)")
    priority: RequirementPriority = Field(default=RequirementPriority.MEDIUM, description="Priority level")
    notes: Optional[str] = Field(None, description="Internal coordinator notes or vendor instructions")


class EventRequirementCreate(EventRequirementBase):
    """Schema for creating a new requirement under an event."""

    pass


class EventRequirementUpdate(BaseModel):
    """Schema for updating an existing requirement."""

    category: Optional[RequirementCategory] = None
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    quantity: Optional[Decimal] = Field(None, gt=0)
    unit: Optional[str] = Field(None, max_length=50)
    priority: Optional[RequirementPriority] = None
    notes: Optional[str] = None


class EventRequirementResponse(EventRequirementBase):
    """Public requirement response schema with server-managed identifiers and timestamps."""

    id: uuid.UUID
    event_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Event Schemas
# ============================================================================


class EventBase(BaseModel):
    """Base event schema holding core properties."""

    name: str = Field(..., min_length=1, max_length=255, description="Event title or celebration name")
    event_type: str = Field(..., min_length=1, max_length=100, description="Category of event (e.g. Wedding, Baby Shower)")
    description: Optional[str] = Field(None, description="Detailed event narrative")
    event_date: Optional[date] = Field(None, description="Calendar date of the event")
    start_time: Optional[time] = Field(None, description="Scheduled start time")
    end_time: Optional[time] = Field(None, description="Scheduled conclusion time")
    timezone: Optional[str] = Field("Asia/Kolkata", max_length=50, description="IANA timezone name")
    expected_attendees: Optional[int] = Field(None, gt=0, description="Expected guest count")
    location_name: Optional[str] = Field(None, max_length=255, description="Venue or property name")
    address: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, max_length=100, description="City")
    state: Optional[str] = Field(None, max_length=100, description="State or province")
    country: str = Field("India", max_length=100, description="Country")
    status: EventStatus = Field(default=EventStatus.DRAFT, description="Current planning status")

    @model_validator(mode="after")
    def validate_times(self) -> "EventBase":
        """Verify that end_time is chronologically after start_time if both are supplied."""
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be strictly after start_time")
        return self


class EventCreate(EventBase):
    """Schema for creating a new Event."""

    pass


class EventUpdate(BaseModel):
    """Schema for partially updating an existing Event."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    event_type: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    event_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    timezone: Optional[str] = Field(None, max_length=50)
    expected_attendees: Optional[int] = Field(None, gt=0)
    location_name: Optional[str] = Field(None, max_length=255)
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    status: Optional[EventStatus] = None

    @model_validator(mode="after")
    def validate_times(self) -> "EventUpdate":
        """Verify that end_time is after start_time if both are updated."""
        if self.start_time is not None and self.end_time is not None:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be strictly after start_time")
        return self


class EventResponse(EventBase):
    """Public summary response schema for an Event."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventDetailResponse(EventResponse):
    """Detailed response schema for an Event including all child requirements."""

    requirements: List[EventRequirementResponse] = Field(
        default_factory=list,
        description="List of service requirements for this event",
    )


class EventListResponse(BaseModel):
    """Paginated list envelope for events."""

    items: List[EventResponse]
    total: int
    skip: int
    limit: int

