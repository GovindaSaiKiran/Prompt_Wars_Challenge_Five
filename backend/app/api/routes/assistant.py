"""FastAPI endpoints for the GenAI Event Planning Assistant."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.planning import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantStatusResponse,
    ConversationMemorySchema,
    ConversationMemoryUpdateRequest,
    ConversationSessionResponse,
    GeneratedEventPlan,
    PlanApprovalRequest,
    PlanApprovalResponse,
    PlanGenerationRequest,
    PlanRefinementRequest,
)
from app.services.conversation_service import ConversationService
from app.services.plan_approval_service import approve_and_commit_plan
from app.services.planning_engine import PlanningEngineService

logger = logging.getLogger("eventprice.assistant")

router = APIRouter(
    prefix="/assistant",
    tags=["GenAI Planning Assistant"],
)


def get_planning_service() -> PlanningEngineService:
    """Dependency provider for planning engine service."""
    return PlanningEngineService()


def get_conversation_service() -> ConversationService:
    """Dependency provider for stateful conversational discovery service."""
    return ConversationService()


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Multi-turn conversational discovery & stateful planning turn",
    description=(
        "Handles conversational turns with the planning assistant, extracts structured facts, "
        "persists context in database memory, selects single natural discovery questions, "
        "and gates full plan generation until sufficient details exist or user explicitly requests it."
    ),
)
def assistant_chat(
    payload: AssistantChatRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> AssistantChatResponse:
    """Process a conversational chat turn with persistent memory."""
    return service.process_chat_message(db=db, request=payload)


@router.get(
    "/sessions/{session_id}",
    response_model=ConversationSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get conversation session history and structured memory",
    description="Restores conversation history, confirmed facts, and memory across page reloads.",
)
def get_session_history(
    session_id: str,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationSessionResponse:
    """Retrieve full conversation history and memory for a session."""
    try:
        return service.get_session_history(db=db, session_id=session_id)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/sessions/{session_id}/memory/update",
    response_model=ConversationMemorySchema,
    status_code=status.HTTP_200_OK,
    summary="Update structured memory directly",
    description="Allows direct corrections or additions to confirmed event details in memory.",
)
def update_session_memory(
    session_id: str,
    payload: ConversationMemoryUpdateRequest,
    db: Session = Depends(get_db),
    service: ConversationService = Depends(get_conversation_service),
) -> ConversationMemorySchema:
    """Update event memory facts directly."""
    try:
        return service.update_memory_directly(db=db, session_id=session_id, update_req=payload)
    except KeyError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/status",
    response_model=AssistantStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get planning assistant operational readiness",
    description="Returns current AI provider status, model configuration, and capabilities.",
)
def get_assistant_readiness(
    service: PlanningEngineService = Depends(get_planning_service),
) -> AssistantStatusResponse:
    """Retrieve assistant configuration and readiness status."""
    return service.get_status()


@router.post(
    "/plan/generate",
    response_model=GeneratedEventPlan,
    status_code=status.HTTP_200_OK,
    summary="Generate structured event plan from natural language description",
    description=(
        "Converts natural-language event descriptions into a comprehensive structured plan "
        "containing event brief, personalized ideas, budget allocations, vendor checklist, "
        "and staged timeline. Generated plans are uncommitted drafts; no database writes occur."
    ),
)
def generate_event_plan(
    payload: PlanGenerationRequest,
    service: PlanningEngineService = Depends(get_planning_service),
) -> GeneratedEventPlan:
    """Generate structured event plan draft."""
    return service.generate_plan(payload)


@router.post(
    "/plan/refine",
    response_model=GeneratedEventPlan,
    status_code=status.HTTP_200_OK,
    summary="Refine an existing event plan draft",
    description=(
        "Adjusts an existing plan draft based on user refinement instructions (e.g. budget tightening, "
        "theme modifications, headcount shifts) with deterministic financial recalculation."
    ),
)
def refine_event_plan(
    payload: PlanRefinementRequest,
    service: PlanningEngineService = Depends(get_planning_service),
) -> GeneratedEventPlan:
    """Refine existing event plan draft."""
    return service.refine_plan(payload)


@router.post(
    "/plan/approve",
    response_model=PlanApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Approve and atomically commit plan draft to database records",
    description=(
        "Converts a user-approved structured event plan draft into persistent database records "
        "(Event, EventRequirement, EventBudget, BudgetLineItem, EventTask, TaskDependency, TaskActivity). "
        "Validates data independently, enforces financial bounds, checks for dependency cycles, "
        "and uses an idempotency key to prevent duplicate commitments."
    ),
)
def approve_event_plan(
    payload: PlanApprovalRequest,
    db: Session = Depends(get_db),
) -> PlanApprovalResponse:
    """Approve and atomically persist structured event plan."""
    return approve_and_commit_plan(db=db, request=payload)


