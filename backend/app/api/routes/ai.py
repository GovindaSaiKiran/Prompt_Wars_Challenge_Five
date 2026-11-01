"""FastAPI endpoints for secure server-side Gemini AI planning advice."""

from decimal import Decimal
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.models.budget import EventBudget
from app.models.event import Event
from app.schemas.ai import AIEventAdviceRequest, AIEventAdviceResponse
from app.services.gemini_service import GeminiService

logger = logging.getLogger("eventprice.ai")

router = APIRouter(
    tags=["AI Planning Intelligence"],
)


@router.post(
    "/events/{event_id}/ai-advice",
    response_model=AIEventAdviceResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate AI event planning advice with authoritative database grounding",
    description=(
        "Retrieves authoritative event parameters and budget allocations from the database, "
        "and securely queries Gemini server-side. Financial figures are grounded in authoritative backend records."
    ),
)
def get_event_ai_advice(
    event_id: uuid.UUID,
    payload: AIEventAdviceRequest,
    db: Session = Depends(get_db),
) -> AIEventAdviceResponse:
    """Generate event advice grounded in database records."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id '{event_id}' not found",
        )

    # 1. Resolve authoritative event details
    event_name = event.name
    location = f"{event.city or ''}, {event.state or ''}, {event.country or ''}".strip(", ") or "India"
    guest_count = event.expected_attendees or 100

    # 2. Check for active or latest budget in database
    budget_stmt = (
        select(EventBudget)
        .where(EventBudget.event_id == event_id)
        .options(selectinload(EventBudget.line_items))
        .order_by(EventBudget.created_at.desc())
    )
    budget = db.execute(budget_stmt).scalars().first()

    target_budget: Decimal = Decimal("0.00")
    category_summary_parts = []

    if budget:
        target_budget = budget.allocated_amount or Decimal("0.00")
        for item in budget.line_items:
            category_summary_parts.append(f"{item.category} ({item.description}): ₹{item.total_cost:,.2f}")
    elif payload.target_budget is not None:
        target_budget = payload.target_budget

    category_summary = "; ".join(category_summary_parts) if category_summary_parts else payload.category_summary

    # 3. Call server-side Gemini service
    service = GeminiService()
    return service.generate_event_advice(
        user_query=payload.user_query,
        event_name=event_name,
        location=location,
        guest_count=guest_count,
        target_budget=target_budget,
        category_summary=category_summary,
    )


@router.post(
    "/ai/event-advice",
    response_model=AIEventAdviceResponse,
    status_code=status.HTTP_200_OK,
    summary="Ad-hoc AI event advice endpoint",
    description="Generates server-side Gemini event advice for ad-hoc prompts and simulations.",
)
def get_adhoc_ai_advice(
    payload: AIEventAdviceRequest,
) -> AIEventAdviceResponse:
    """Generate server-side Gemini event advice using validated client context."""
    service = GeminiService()
    return service.generate_event_advice(
        user_query=payload.user_query,
        event_name=payload.event_name,
        location=payload.location,
        guest_count=payload.guest_count,
        target_budget=payload.target_budget,
        category_summary=payload.category_summary,
    )

