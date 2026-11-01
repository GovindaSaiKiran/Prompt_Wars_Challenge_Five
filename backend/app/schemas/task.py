"""Pydantic validation schemas for Event Tasks, Dependencies, Activities, and Timeline."""

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


CURRENCY_REGEX = re.compile(r"^[A-Z]{3}$")


class TaskCategory(str, Enum):
    """Permitted task categories."""
    PLANNING = "planning"
    VENUE = "venue"
    CATERING = "catering"
    PHOTOGRAPHY = "photography"
    DECORATION = "decoration"
    ENTERTAINMENT = "entertainment"
    TRANSPORT = "transport"
    ACCOMMODATION = "accommodation"
    FINANCE = "finance"
    INVITATIONS = "invitations"
    LOGISTICS = "logistics"
    OTHER = "other"


class TaskStatus(str, Enum):
    """Permitted task lifecycle statuses."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    """Permitted task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DependencyType(str, Enum):
    """Standard project management dependency types."""
    FINISH_TO_START = "finish_to_start"
    START_TO_START = "start_to_start"
    FINISH_TO_FINISH = "finish_to_finish"
    START_TO_FINISH = "start_to_finish"


# ============================================================================
# Task Schemas
# ============================================================================


class EventTaskBase(BaseModel):
    """Base fields for an Event Task."""

    title: str = Field(..., min_length=1, max_length=255, description="Task title")
    description: Optional[str] = Field(None, description="Detailed instructions or specifications")
    category: TaskCategory = Field(default=TaskCategory.PLANNING, description="Task domain category")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current workflow status")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task urgency and priority")
    start_date: Optional[date] = Field(None, description="Planned initiation date")
    due_date: Optional[date] = Field(None, description="Required target completion deadline")
    estimated_cost: Optional[Decimal] = Field(None, ge=0, description="Projected financial cost")
    actual_cost: Optional[Decimal] = Field(None, ge=0, description="Incurred actual expense")
    currency: str = Field(default="INR", description="ISO 4217 3-letter currency code")
    assigned_to: Optional[str] = Field(None, max_length=255, description="Designated coordinator or team member")
    notes: Optional[str] = Field(None, description="Supplementary coordination notes")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        v = v.strip().upper()
        if not CURRENCY_REGEX.match(v):
            raise ValueError(f"Invalid currency code: '{v}'. Must be a 3-letter uppercase ISO code.")
        return v

    @model_validator(mode="after")
    def validate_date_order(self) -> "EventTaskBase":
        if self.start_date is not None and self.due_date is not None:
            if self.due_date < self.start_date:
                raise ValueError("due_date cannot be earlier than start_date")
        return self


class EventTaskCreate(EventTaskBase):
    """Schema for creating a new Event Task."""
    pass


class EventTaskUpdate(BaseModel):
    """Schema for modifying an existing Event Task."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    category: Optional[TaskCategory] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    estimated_cost: Optional[Decimal] = Field(None, ge=0)
    actual_cost: Optional[Decimal] = Field(None, ge=0)
    currency: Optional[str] = None
    assigned_to: Optional[str] = Field(None, max_length=255)
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

    @model_validator(mode="after")
    def validate_date_order(self) -> "EventTaskUpdate":
        if self.start_date is not None and self.due_date is not None:
            if self.due_date < self.start_date:
                raise ValueError("due_date cannot be earlier than start_date")
        return self


class EventTaskResponse(EventTaskBase):
    """Summary response representation for an Event Task."""

    id: uuid.UUID
    event_id: uuid.UUID
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    is_dependency_blocked: bool = False
    dependency_block_reasons: List[str] = Field(default_factory=list)
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskListResponse(BaseModel):
    """Paginated list envelope for tasks."""

    items: List[EventTaskResponse]
    total: int
    skip: int
    limit: int


# ============================================================================
# Dependency Schemas
# ============================================================================


class TaskDependencyCreate(BaseModel):
    """Schema for creating a directed task dependency."""

    predecessor_task_id: uuid.UUID = Field(
        ...,
        description="UUID of the predecessor task that must satisfy constraints first",
    )
    dependency_type: DependencyType = Field(
        default=DependencyType.FINISH_TO_START,
        description="Relationship type: finish_to_start, start_to_start, finish_to_finish, start_to_finish",
    )


class TaskDependencyResponse(BaseModel):
    """Response representation for a task dependency."""

    id: uuid.UUID
    predecessor_task_id: uuid.UUID
    successor_task_id: uuid.UUID
    dependency_type: DependencyType
    created_at: datetime
    predecessor_task_title: Optional[str] = None
    successor_task_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Activity Log Schemas
# ============================================================================


class TaskActivityResponse(BaseModel):
    """Append-only audit record of a modification to an event task."""

    id: uuid.UUID
    event_id: uuid.UUID
    task_id: Optional[uuid.UUID] = None
    task_title: Optional[str] = None
    action_type: str
    previous_value: Optional[str] = None
    new_value: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EventTaskDetailResponse(EventTaskResponse):
    """Comprehensive detail representation of an Event Task including dependencies and audit log."""

    predecessor_dependencies: List[TaskDependencyResponse] = Field(default_factory=list)
    successor_dependencies: List[TaskDependencyResponse] = Field(default_factory=list)
    activity_history: List[TaskActivityResponse] = Field(default_factory=list)


# ============================================================================
# Timeline & Progress Summary Schemas
# ============================================================================


class TimelineTaskItem(BaseModel):
    """Task item formatted for chronological timeline visualization."""

    id: uuid.UUID
    title: str
    category: str
    status: str
    priority: str
    start_date: Optional[date] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    estimated_cost: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None
    currency: str
    is_overdue: bool
    is_dependency_blocked: bool = False
    dependency_block_reasons: List[str] = Field(default_factory=list)
    predecessor_count: int
    successor_count: int


class TimelineGroup(BaseModel):
    """Group of tasks sharing a specific chronological due date."""

    due_date: str
    task_count: int
    tasks: List[TimelineTaskItem]


class TimelineResponse(BaseModel):
    """Event timeline response structured chronologically with scheduled and unscheduled buckets."""

    scheduled_groups: List[TimelineGroup]
    unscheduled_tasks: List[TimelineTaskItem]
    total_scheduled_tasks: int
    total_unscheduled_tasks: int


class TaskProgressSummaryResponse(BaseModel):
    """Comprehensive progress analytics for an event's task set."""

    total_tasks: int
    pending_tasks: int
    in_progress_tasks: int
    blocked_tasks: int
    completed_tasks: int
    cancelled_tasks: int
    active_tasks: int
    completion_percentage: Decimal
    overdue_tasks: int
    tasks_by_category: Dict[str, int]
    tasks_by_priority: Dict[str, int]
    total_estimated_cost: Decimal
    total_actual_cost: Decimal

