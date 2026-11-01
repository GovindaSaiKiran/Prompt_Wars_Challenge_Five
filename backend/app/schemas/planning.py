"""Pydantic validation schemas for Structured GenAI Event Planning Engine.

Supports weddings, birthdays, community events, conferences, and celebrations.
Enforces strict typing, financial bounds, and transparent separation between
AI-generated proposals and authoritative deterministic figures.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.external_data import NormalizedPlace, WeatherResponse


class PlanningEventType(str, Enum):
    """Supported event categories."""
    WEDDING = "wedding"
    BIRTHDAY = "birthday"
    COMMUNITY = "community"
    CORPORATE = "corporate"
    CONFERENCE = "conference"
    ANNIVERSARY = "anniversary"
    HACKATHON = "hackathon"
    ROBOTICS_COMPETITION = "robotics-competition"
    TECH_FEST = "tech-fest"
    WORKSHOP = "workshop"
    SEMINAR = "seminar"
    MEETUP = "meetup"
    NETWORKING = "networking"
    EXHIBITION = "exhibition"
    PRODUCT_LAUNCH = "product-launch"
    GET_TOGETHER = "get-together"
    CUSTOM = "custom"
    OTHER = "other"


# ============================================================================
# A. Event Brief Schemas
# ============================================================================


class PlanEventBrief(BaseModel):
    """High-level summary of the event specifications and boundary conditions."""

    event_type: str = Field(..., description="Classification of the event")
    event_name: str = Field(..., description="Working title or name of the event")
    occasion: Optional[str] = Field(None, description="Specific occasion or gathering purpose")
    theme: Optional[str] = Field(None, description="Topic, academic/technical focus, or theme")
    scale: Optional[str] = Field(None, description="Scale or tier (e.g. small, medium, large)")
    duration: Optional[str] = Field(None, description="Event duration (e.g. 24-hour, 1-day, weekend)")
    format_type: Optional[str] = Field(None, description="Format (in-person, virtual, hybrid)")
    location: Optional[str] = Field(None, description="City, region, or venue destination")
    expected_guest_count: Optional[int] = Field(None, ge=1, le=500000, description="Estimated attendee count")
    event_date: Optional[date] = Field(None, description="Target calendar date if specified")
    event_time: Optional[str] = Field(None, description="Target time of day if specified")
    target_budget: Optional[Decimal] = Field(None, ge=0, description="User's ceiling or target budget")
    budget_provenance: str = Field(
        default="unknown",
        description="Provenance of target budget: 'user_provided', 'user_approved', 'ai_suggested', 'benchmark_estimate', 'unknown'",
    )
    currency: str = Field(default="INR", max_length=3, description="ISO 4217 currency code")
    description: Optional[str] = Field(None, description="Detailed concept narrative")
    confirmed_information: List[str] = Field(default_factory=list, description="Facts explicitly confirmed by user")
    missing_information: List[str] = Field(default_factory=list, description="Critical planning data still required")
    explicit_assumptions: List[str] = Field(default_factory=list, description="Assumptions made to unblock initial drafting")

    @field_validator("event_type", mode="before")
    @classmethod
    def validate_event_type(cls, v: Any) -> str:
        if not v or not isinstance(v, str):
            return "other"
        v_clean = v.strip().lower()
        if "wedding" in v_clean or "marriage" in v_clean:
            return "wedding"
        if "birthday" in v_clean or "bday" in v_clean:
            return "birthday"
        if "community" in v_clean or "festival" in v_clean or "cultural" in v_clean:
            return "community"
        if "corporate" in v_clean or "business" in v_clean or "company" in v_clean:
            return "corporate"
        if "conference" in v_clean or "summit" in v_clean or "keynote" in v_clean:
            return "conference"
        if "anniversary" in v_clean:
            return "anniversary"
        for t in ["wedding", "birthday", "community", "corporate", "conference", "anniversary", "other"]:
            if t in v_clean:
                return t
        return v_clean

    @field_validator("expected_guest_count", mode="before")
    @classmethod
    def validate_guest_count(cls, v: Any) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            val = int(v)
            return val if val >= 1 else None
        except (ValueError, TypeError):
            return None

    @field_validator("target_budget", mode="before")
    @classmethod
    def validate_target_budget(cls, v: Any) -> Optional[Decimal]:
        if v is None or v == "":
            return None
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if v_clean in ("tbd", "none", "null", "unknown", "n/a", "not provided", "not specified"):
                return None
        try:
            val = Decimal(str(v).strip())
            if val < 0:
                raise ValueError("Target budget cannot be negative.")
            return val
        except (ValueError, ArithmeticError) as e:
            if "Target budget cannot be negative" in str(e):
                raise
            return None

    @field_validator("event_date", mode="before")
    @classmethod
    def validate_event_date(cls, v: Any) -> Optional[date]:
        if v is None or v == "":
            return None
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if v_clean in ("tbd", "none", "null", "unscheduled", "n/a", "tba", "not specified"):
                return None
            try:
                return date.fromisoformat(v.strip())
            except ValueError:
                return None
        return v

    @field_validator(
        "confirmed_information",
        "missing_information",
        "explicit_assumptions",
        mode="before",
    )
    @classmethod
    def coerce_brief_lists(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            if "\n" in v:
                lines = [line.strip().lstrip("•-*0123456789. ") for line in v.split("\n") if line.strip()]
                return lines if lines else [v]
            return [v]
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
        return [str(v)]

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.strip().upper()


# ============================================================================
# B. Personalized Ideas Schemas
# ============================================================================


class PlanPersonalizedIdeas(BaseModel):
    """Creative, aesthetic, and experiential concept recommendations."""

    theme_and_concept: List[str] = Field(default_factory=list, description="Theme name, palette, and stylistic direction")
    decoration_ideas: List[str] = Field(default_factory=list, description="Floral, lighting, stage, and spatial design elements")
    catering_ideas: List[str] = Field(default_factory=list, description="Menu styles, live counters, welcome drinks, and dining formats")
    entertainment_ideas: List[str] = Field(default_factory=list, description="Music, performances, emcee, and interactive activities")
    guest_experience_suggestions: List[str] = Field(default_factory=list, description="Favors, welcome kits, photo-ops, and guest hospitality")
    practical_recommendations: List[str] = Field(default_factory=list, description="Logistics, weather contingencies, and local site tips")

    @field_validator(
        "theme_and_concept",
        "decoration_ideas",
        "catering_ideas",
        "entertainment_ideas",
        "guest_experience_suggestions",
        "practical_recommendations",
        mode="before",
    )
    @classmethod
    def coerce_ideas_lists(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            if "\n" in v:
                lines = [line.strip().lstrip("•-*0123456789. ") for line in v.split("\n") if line.strip()]
                return lines if lines else [v]
            return [v]
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
        return [str(v)]


# ============================================================================
# C. Budget Proposal Schemas (Deterministic Financial Recalculation)
# ============================================================================


class BudgetCategoryAllocation(BaseModel):
    """Proposed allocation for a specific spending category."""

    category: str = Field(..., description="Spending category (e.g. venue, catering, decoration)")
    suggested_amount: Decimal = Field(..., ge=0, description="Proposed allocation amount")
    currency: str = Field(default="INR", max_length=3)
    rationale: str = Field(..., description="Explanation for this suggested allocation")
    source_type: str = Field(
        default="illustrative_estimate",
        description="'illustrative_estimate', 'user_provided', or 'vendor_quote'",
    )
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=100, description="Explicit tax rate percentage if known/specified")
    tax_included: Optional[bool] = Field(None, description="Whether tax is included in suggested amount")

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        return v.strip().upper()


class PlanBudgetProposal(BaseModel):
    """Comprehensive budget breakdown with authoritative Python Decimal totals."""

    allocations: List[BudgetCategoryAllocation] = Field(default_factory=list)
    total_allocated: Decimal = Field(default=Decimal("0.00"), description="Sum of all category allocations (authoritative)")
    target_budget: Optional[Decimal] = Field(None, description="User target budget ceiling if provided")
    budget_provenance: str = Field(
        default="unknown",
        description="Provenance of target budget: 'user_provided', 'user_approved', 'ai_suggested', 'benchmark_estimate', 'unknown'",
    )
    currency: str = Field(default="INR", max_length=3)
    remaining_budget: Optional[Decimal] = Field(None, description="Target budget minus total allocated")
    variance_amount: Optional[Decimal] = Field(None, description="Variance between target budget and total allocated")
    contingency_amount: Decimal = Field(default=Decimal("0.00"), description="Emergency financial buffer")
    contingency_percentage: Optional[Decimal] = Field(default=None, ge=0, le=100, description="Contingency buffer percentage")
    contingency_calculation_basis: Optional[str] = Field(
        default=None,
        description="Explicit calculation basis and rationale for contingency",
    )
    tax_calculation_policy: str = Field(default="standard", description="Tax policy: standard, inclusive, exclusive")
    is_within_budget: Optional[bool] = Field(
        default=None,
        description="Whether total allocated is <= target budget (None if budget not provided)",
    )
    financial_alerts: List[str] = Field(default_factory=list, description="Deterministic financial warnings or budget notices")
    budget_assumptions: List[str] = Field(
        default_factory=list,
        description="Explicit assumptions when AI suggests or benchmarks an estimate",
    )
    estimate_provenance_notice: str = Field(
        default=(
            "All category budget figures are illustrative planning assumptions calculated deterministically. "
            "They are neither verified local market prices nor binding vendor quotes."
        ),
        description="Clear statement on budget estimate provenance and non-binding nature",
    )


# ============================================================================
# D. Vendor Checklist Schemas
# ============================================================================


class VendorChecklistItem(BaseModel):
    """Actionable vendor procurement checklist item (no fabricated real businesses)."""

    category: str = Field(..., description="Vendor category required")
    requirement_title: str = Field(..., description="Name of the service or equipment deliverable")
    description: str = Field(..., description="Scope of services needed")
    suggested_quantity_or_capacity: Optional[str] = Field(None, description="Capacity or headcount sizing guide")
    important_questions_to_ask: List[str] = Field(default_factory=list, description="Critical vetting questions for vendor calls")
    priority: str = Field(default="medium", description="Priority level: low, medium, high, critical")
    selection_considerations: List[str] = Field(default_factory=list, description="Key quality or contract terms to verify")

    @field_validator("suggested_quantity_or_capacity", mode="before")
    @classmethod
    def coerce_quantity_str(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)

    @field_validator("important_questions_to_ask", "selection_considerations", mode="before")
    @classmethod
    def coerce_checklist_lists(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            if "\n" in v:
                lines = [line.strip().lstrip("•-*0123456789. ") for line in v.split("\n") if line.strip()]
                return lines if lines else [v]
            return [v]
        if isinstance(v, list):
            return [str(x) for x in v if x is not None]
        return [str(v)]


# ============================================================================
# E. Timeline Schemas
# ============================================================================


class TaskDependencySpec(BaseModel):
    """Specification of a task dependency with explicit dependency type."""

    predecessor_title: str = Field(..., min_length=1, description="Title of the predecessor task")
    dependency_type: str = Field(
        default="finish_to_start",
        description="Dependency type: finish_to_start, start_to_start, finish_to_finish, start_to_finish",
    )


class PlanTimelineTask(BaseModel):
    """Chronological milestone or task with relative timing stages."""

    task_title: str = Field(..., description="Milestone title")
    description: str = Field(..., description="Actionable execution description")
    category: str = Field(..., description="Domain category")
    priority: str = Field(default="medium", description="Priority: low, medium, high, critical")
    stage: str = Field(..., description="Planning stage (e.g. early_planning, vendor_booking, final_prep, event_week)")
    suggested_due_date: Optional[date] = Field(None, description="Calculated target due date if event date is known")
    relative_timing: str = Field(..., description="Relative timing indicator (e.g. '8-10 weeks before event')")
    dependencies: List[Union[str, TaskDependencySpec]] = Field(
        default_factory=list, description="Predecessor milestone titles or structured dependency specifications"
    )
    why_it_matters: str = Field(..., description="Strategic context for why this milestone is vital")

    @field_validator("suggested_due_date", mode="before")
    @classmethod
    def validate_due_date(cls, v: Any) -> Optional[date]:
        if v is None or v == "":
            return None
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if v_clean in ("tbd", "none", "null", "unscheduled", "n/a", "tba", "not specified"):
                return None
            try:
                return date.fromisoformat(v.strip())
            except ValueError:
                return None
        return v

    @field_validator("dependencies", mode="before")
    @classmethod
    def coerce_dependencies(cls, v: Any) -> List[Any]:
        if v is None:
            return []
        if isinstance(v, str):
            v_clean = v.strip().lower()
            if v_clean in ("none", "null", "no dependencies", "n/a", ""):
                return []
            return [v.strip()]
        if isinstance(v, list):
            return v
        return [v]


# ============================================================================
# Complete Structured Event Plan
# ============================================================================


class GeneratedEventPlan(BaseModel):
    """Comprehensive generated event plan draft."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique draft identifier")
    brief: PlanEventBrief
    personalized_ideas: PlanPersonalizedIdeas
    budget_proposal: PlanBudgetProposal
    vendor_checklist: List[VendorChecklistItem] = Field(default_factory=list)
    timeline: List[PlanTimelineTask] = Field(default_factory=list)
    provider: str = Field(..., description="'gemini' or 'deterministic_fallback'")
    model: Optional[str] = Field(None, description="Model identifier if generated via live LLM")
    is_live_ai: bool = Field(default=False, description="True if synthesized via live LLM; False if deterministic engine")
    status: str = Field(default="draft", description="Plan status: 'draft', 'refined'")
    disclaimer: str = Field(
        default=(
            "AI-generated plan is an uncommitted advisory draft. Budget allocations are proposals and not verified vendor quotes. "
            "No database changes, vendor commitments, or financial transactions have been executed."
        )
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Request / Refinement / Status Payloads
# ============================================================================


class PlanGenerationRequest(BaseModel):
    """Payload to generate a plan from natural language or guided brief."""

    user_prompt: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Natural language event description, instructions, or theme preferences",
    )
    event_type: Optional[str] = Field(None, description="Optional override: wedding, birthday, community, corporate, etc.")
    event_name: Optional[str] = Field(None, description="Optional override for event title")
    location: Optional[str] = Field(None, description="Optional location / city")
    guest_count: Optional[int] = Field(None, ge=1, le=500000, description="Optional guest count")
    target_budget: Optional[Decimal] = Field(None, ge=0, description="Optional target budget amount")
    budget_provenance: Optional[str] = Field(None, description="Optional explicit budget provenance ('user_provided', 'user_approved', 'ai_suggested', 'benchmark_estimate', 'unknown')")
    currency: Optional[str] = Field(default="INR", max_length=3)
    event_date: Optional[date] = Field(None, description="Optional calendar date")
    external_weather: Optional[WeatherResponse] = Field(
        None, description="Optional verified real weather data & risk assessment"
    )
    nearby_places: Optional[List[NormalizedPlace]] = Field(
        default_factory=list, description="Optional verified OpenStreetMap nearby venues & facilities"
    )


class PlanRefinementRequest(BaseModel):
    """Payload to modify an existing generated plan draft."""

    existing_plan: GeneratedEventPlan = Field(..., description="The current draft plan to be modified")
    refinement_instructions: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Specific user adjustments (e.g. 'Reduce decoration budget by 20%', 'Switch to vintage Bollywood theme')",
    )


class AssistantStatusResponse(BaseModel):
    """Readiness status of the GenAI Planning Assistant."""

    ai_enabled: bool
    ai_provider: str
    configured_model: str
    is_live_key_configured: bool
    service_status: str  # "ready_live", "ready_fallback", "disabled"
    supported_event_types: List[str]
    disclaimer: str


# ============================================================================
# Plan Approval & Persistence Schemas
# ============================================================================


class PlanApprovalRequest(BaseModel):
    """Payload to explicitly approve and atomically commit a plan draft into database records."""

    plan: GeneratedEventPlan = Field(..., description="The reviewed and approved structured event plan draft")
    confirm_approval: bool = Field(
        ...,
        description="Explicit confirmation flag. Must be True to authoritatively commit records.",
    )
    idempotency_key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Client-generated unique key (e.g. UUID) preventing duplicate submissions",
    )
    initial_event_status: Optional[str] = Field(
        default="planning",
        description="Initial status for the created Event entity: 'planning', 'confirmed', or 'draft'",
    )
    tax_calculation_policy: Optional[str] = Field(
        default=None,
        description="Optional tax calculation policy override ('standard', 'inclusive', 'exclusive')",
    )
    contingency_percentage: Optional[Decimal] = Field(
        default=None,
        ge=0,
        le=100,
        description="Optional approved contingency percentage override (e.g. 15.00)",
    )


class PlanApprovalFinancialSummary(BaseModel):
    """Authoritative summary of persisted budget figures."""

    total_allocated: Decimal
    contingency_amount: Decimal
    contingency_percentage: Decimal = Field(default=Decimal("10.00"), description="Contingency percentage applied")
    tax_calculation_policy: str = Field(default="standard", description="Tax calculation policy: standard, inclusive, exclusive")
    total_tax: Decimal = Field(default=Decimal("0.00"), description="Calculated tax total across all line items")
    grand_total: Optional[Decimal] = Field(None, description="Total allocated including tax and contingency")
    target_budget: Optional[Decimal] = None
    budget_provenance: str = Field(default="user_approved")
    remaining_budget: Optional[Decimal] = None
    is_within_budget: Optional[bool] = None
    currency: str


class PlanApprovalResponse(BaseModel):
    """Authoritative database commitment response returned upon successful plan approval."""

    success: bool = True
    event_id: uuid.UUID
    event_name: str
    event_type: str
    status: str
    location: Optional[str] = None
    expected_attendees: Optional[int] = None
    event_date: Optional[date] = None
    created_requirements_count: int
    budget_id: uuid.UUID
    created_line_items_count: int
    created_tasks_count: int
    created_dependencies_count: int
    financial_summary: PlanApprovalFinancialSummary
    message: str
    idempotency_key: str
    committed_at: datetime


# ============================================================================
# Conversational Discovery & Persistent Memory Schemas
# ============================================================================


class ConversationMemorySchema(BaseModel):
    """Structured event memory extracted and tracked across conversation turns."""

    event_type: Optional[str] = None
    event_name: Optional[str] = None
    occasion: Optional[str] = None
    theme: Optional[str] = None
    scale: Optional[str] = None
    duration: Optional[str] = None
    format_type: Optional[str] = None
    location: Optional[str] = None
    expected_guest_count: Optional[int] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    target_budget: Optional[Decimal] = None
    budget_provenance: str = "unknown"
    currency: str = "INR"
    venue_preferences: Optional[str] = None
    food_preferences: Optional[str] = None
    dietary_requirements: Optional[str] = None
    entertainment_preferences: Optional[str] = None
    decoration_preferences: Optional[str] = None
    other_instructions: Optional[str] = None
    confirmed_fields: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    last_question_asked: Optional[str] = None
    plan_generated: bool = False
    ready_for_plan: bool = False


class ChatMessageSchema(BaseModel):
    """Serialized chat message within a session."""

    id: str
    sender: str
    content: str
    reply_type: str = "general"
    current_question: Optional[str] = None
    structured_plan: Optional[GeneratedEventPlan] = None
    suggested_prompts: List[str] = Field(default_factory=list)
    created_at: datetime


class AssistantChatRequest(BaseModel):
    """Payload to send a message to the conversational assistant."""

    message: str = Field(..., min_length=1, description="User's conversational message or instruction")
    session_id: Optional[str] = Field(None, description="UUID of existing conversation session; null creates a new one")
    event_id: Optional[str] = Field(None, description="Optional linked Event ID")
    request_plan_generation: bool = Field(False, description="Flag to explicitly request plan generation now")


class AssistantChatResponse(BaseModel):
    """Response returned by the conversational planning assistant."""

    session_id: str
    message: str
    reply_type: str = Field("general", description="'greeting', 'discovery_question', 'plan_generated', 'plan_refined', 'general'")
    current_question: Optional[str] = None
    structured_plan: Optional[GeneratedEventPlan] = None
    memory: ConversationMemorySchema
    suggested_prompts: List[str] = Field(default_factory=list)


class ConversationSessionResponse(BaseModel):
    """Full session history and structured memory for restoring context across page reloads."""

    session_id: str
    title: str
    event_id: Optional[str] = None
    messages: List[ChatMessageSchema] = Field(default_factory=list)
    memory: ConversationMemorySchema
    created_at: datetime
    updated_at: datetime


class ConversationMemoryUpdateRequest(BaseModel):
    """Direct user edits to structured event memory attributes."""

    event_type: Optional[str] = None
    event_name: Optional[str] = None
    occasion: Optional[str] = None
    theme: Optional[str] = None
    scale: Optional[str] = None
    duration: Optional[str] = None
    format_type: Optional[str] = None
    location: Optional[str] = None
    expected_guest_count: Optional[int] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    target_budget: Optional[Decimal] = None
    budget_provenance: Optional[str] = None
    venue_preferences: Optional[str] = None
    food_preferences: Optional[str] = None
    dietary_requirements: Optional[str] = None
    entertainment_preferences: Optional[str] = None
    decoration_preferences: Optional[str] = None
    other_instructions: Optional[str] = None


