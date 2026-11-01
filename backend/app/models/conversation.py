"""SQLAlchemy 2.x data models for Conversational Discovery and Persistent Memory."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ConversationSession(Base):
    """Represents a persistent multi-turn conversational planning session."""

    __tablename__ = "conversation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="New Event Plan",
    )
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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

    # Relationships
    messages: Mapped[List["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )
    memory: Mapped[Optional["ConversationMemory"]] = relationship(
        "ConversationMemory",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ConversationMessage(Base):
    """Represents an individual message in a conversation session."""

    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("conversation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender: Mapped[str] = mapped_column(
        String(20),  # 'user', 'assistant', 'system'
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    reply_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="general",  # 'greeting', 'discovery_question', 'plan_generated', 'plan_refined', 'general'
    )
    current_question: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    structured_plan_payload: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,  # JSON serialized GeneratedEventPlan if generated on this turn
    )
    suggested_prompts: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    session: Mapped["ConversationSession"] = relationship(
        "ConversationSession",
        back_populates="messages",
    )


class ConversationMemory(Base):
    """Persistent structured event memory extracted across turns."""

    __tablename__ = "conversation_memories"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("conversation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Core event attributes
    event_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    event_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    occasion: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    theme: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    scale: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    duration: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    format_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expected_guest_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    event_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    event_time: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Financial bounds
    target_budget: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    budget_provenance: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    # Granular user preferences
    venue_preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    food_preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dietary_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entertainment_preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decoration_preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    other_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Tracking & State
    confirmed_fields: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_fields: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    last_question_asked: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    plan_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    current_plan_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    session: Mapped["ConversationSession"] = relationship(
        "ConversationSession",
        back_populates="memory",
    )

