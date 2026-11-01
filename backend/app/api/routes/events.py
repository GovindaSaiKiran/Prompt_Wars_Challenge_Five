"""FastAPI endpoints for Event and EventRequirement management."""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.event import Event, EventRequirement
from app.schemas.event import (
    EventCreate,
    EventDetailResponse,
    EventListResponse,
    EventRequirementCreate,
    EventRequirementResponse,
    EventRequirementUpdate,
    EventResponse,
    EventStatus,
    EventUpdate,
)

logger = logging.getLogger("eventprice.events")
router = APIRouter(prefix="/events", tags=["Events"])


# ============================================================================
# Event Endpoints
# ============================================================================


@router.post(
    "/",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new event",
    description="Creates a new event record with initial details.",
)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
) -> Event:
    """Create and persist a new event."""
    event_data = payload.model_dump()
    # Normalize enum to string for database storage
    if isinstance(event_data.get("status"), EventStatus):
        event_data["status"] = event_data["status"].value

    new_event = Event(**event_data)
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    logger.info("Created event id=%s name='%s'", new_event.id, new_event.name)
    return new_event


@router.get(
    "/",
    response_model=EventListResponse,
    status_code=status.HTTP_200_OK,
    summary="List events with pagination",
    description="Returns a paginated list of events with optional filtering.",
)
def list_events(
    skip: int = Query(0, ge=0, description="Records to skip for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return (max 100)"),
    status_filter: Optional[EventStatus] = Query(None, alias="status", description="Filter by event status"),
    city: Optional[str] = Query(None, description="Filter by city name (case-insensitive substring)"),
    db: Session = Depends(get_db),
) -> EventListResponse:
    """List events matching query filters with pagination."""
    query = select(Event)
    count_query = select(func.count(Event.id))

    if status_filter is not None:
        query = query.where(Event.status == status_filter.value)
        count_query = count_query.where(Event.status == status_filter.value)

    if city:
        query = query.where(Event.city.ilike(f"%{city}%"))
        count_query = count_query.where(Event.city.ilike(f"%{city}%"))

    total = db.execute(count_query).scalar_one()

    # Order by event_date, then created_at desc
    events_stmt = (
        query.order_by(Event.event_date.asc().nulls_last(), Event.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = db.execute(events_stmt).scalars().all()

    return EventListResponse(
        items=list(items),
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{event_id}",
    response_model=EventDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve event details and requirements",
    description="Fetches an event along with all associated service requirements, using eager loading to prevent N+1 queries.",
)
def get_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Event:
    """Retrieve single event with requirements via selectinload."""
    stmt = (
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.requirements))
    )
    event = db.execute(stmt).scalars().first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id '{event_id}' not found",
        )

    return event


@router.patch(
    "/{event_id}",
    response_model=EventResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an event",
    description="Partially updates an existing event's attributes.",
)
def update_event(
    event_id: uuid.UUID,
    payload: EventUpdate,
    db: Session = Depends(get_db),
) -> Event:
    """Partially update event fields."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id '{event_id}' not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if "status" in update_data and isinstance(update_data["status"], EventStatus):
        update_data["status"] = update_data["status"].value

    for field, value in update_data.items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)
    logger.info("Updated event id=%s fields=%s", event_id, list(update_data.keys()))
    return event


@router.delete(
    "/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an event",
    description="Deletes an event and cascades deletion to all child requirements.",
)
def delete_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Delete an event and its associated requirements."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id '{event_id}' not found",
        )

    db.delete(event)
    db.commit()
    logger.info("Deleted event id=%s and cascaded requirements", event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Event Requirement Endpoints
# ============================================================================


@router.post(
    "/{event_id}/requirements",
    response_model=EventRequirementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add requirement to an event",
    description="Adds a new service or logistics requirement item to an existing event.",
)
def create_event_requirement(
    event_id: uuid.UUID,
    payload: EventRequirementCreate,
    db: Session = Depends(get_db),
) -> EventRequirement:
    """Create a new requirement associated with the given event."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id '{event_id}' not found",
        )

    req_data = payload.model_dump()
    if hasattr(req_data.get("category"), "value"):
        req_data["category"] = req_data["category"].value
    if hasattr(req_data.get("priority"), "value"):
        req_data["priority"] = req_data["priority"].value

    new_requirement = EventRequirement(event_id=event_id, **req_data)
    db.add(new_requirement)
    db.commit()
    db.refresh(new_requirement)
    logger.info(
        "Created requirement id=%s for event id=%s (category='%s', title='%s')",
        new_requirement.id,
        event_id,
        new_requirement.category,
        new_requirement.title,
    )
    return new_requirement


@router.patch(
    "/{event_id}/requirements/{requirement_id}",
    response_model=EventRequirementResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a requirement",
    description="Partially updates an existing requirement. Enforces that the requirement belongs to the specified parent event.",
)
def update_event_requirement(
    event_id: uuid.UUID,
    requirement_id: uuid.UUID,
    payload: EventRequirementUpdate,
    db: Session = Depends(get_db),
) -> EventRequirement:
    """Update requirement ensuring strict event ownership."""
    stmt = select(EventRequirement).where(
        EventRequirement.id == requirement_id,
        EventRequirement.event_id == event_id,
    )
    requirement = db.execute(stmt).scalars().first()

    if not requirement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement with id '{requirement_id}' not found under event '{event_id}'",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if "category" in update_data and hasattr(update_data["category"], "value"):
        update_data["category"] = update_data["category"].value
    if "priority" in update_data and hasattr(update_data["priority"], "value"):
        update_data["priority"] = update_data["priority"].value

    for field, value in update_data.items():
        setattr(requirement, field, value)

    db.commit()
    db.refresh(requirement)
    logger.info("Updated requirement id=%s for event id=%s", requirement_id, event_id)
    return requirement


@router.delete(
    "/{event_id}/requirements/{requirement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a requirement",
    description="Deletes a requirement line item. Enforces that the requirement belongs to the specified parent event.",
)
def delete_event_requirement(
    event_id: uuid.UUID,
    requirement_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Delete requirement ensuring strict event ownership."""
    stmt = select(EventRequirement).where(
        EventRequirement.id == requirement_id,
        EventRequirement.event_id == event_id,
    )
    requirement = db.execute(stmt).scalars().first()

    if not requirement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement with id '{requirement_id}' not found under event '{event_id}'",
        )

    db.delete(requirement)
    db.commit()
    logger.info("Deleted requirement id=%s from event id=%s", requirement_id, event_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

