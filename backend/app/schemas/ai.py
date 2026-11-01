"""Pydantic validation schemas for backend Gemini AI planning advice."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AIEventAdviceRequest(BaseModel):
    """Request payload for event planning advice."""

    user_query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User question, theme preference, or guidance request",
    )
    event_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Event name (overrides DB value if provided)",
    )
    location: Optional[str] = Field(
        None,
        max_length=255,
        description="Event location / city",
    )
    guest_count: Optional[int] = Field(
        None,
        ge=1,
        le=500000,
        description="Expected attendee count",
    )
    target_budget: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Target event budget",
    )
    category_summary: Optional[str] = Field(
        None,
        max_length=2000,
        description="Summary of allocated budget categories and vendor assignments",
    )


class AIEventAdviceResponse(BaseModel):
    """Validated response containing AI advice or deterministic fallback."""

    success: bool = Field(
        ...,
        description="Whether a live AI response was successfully synthesized",
    )
    advice: str = Field(
        ...,
        description="Synthesized event planning advice or fallback guidance",
    )
    provider: str = Field(
        ...,
        description="AI provider identifier ('gemini' or 'deterministic_fallback')",
    )
    model: Optional[str] = Field(
        None,
        description="Model identifier utilized (e.g. 'gemini-2.5-flash')",
    )
    status: str = Field(
        ...,
        description="Execution status ('success', 'fallback_missing_key', 'fallback_disabled', 'fallback_error', 'fallback_timeout')",
    )
    disclaimer: str = Field(
        default="AI-generated event advice is advisory. Financial ledger totals and vendor quotes are computed deterministically.",
        description="Mandatory advisory disclaimer",
    )

    model_config = ConfigDict(from_attributes=True)

