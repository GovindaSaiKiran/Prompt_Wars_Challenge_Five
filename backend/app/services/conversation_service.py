"""Stateful Conversational Event-Planning Service with Persistent Memory.

Implements multi-turn discovery, intelligent single-question selection,
fact extraction with deterministic guards, planning generation gates,
and memory-aware refinement across sessions.
"""

from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy.orm import Session

from app.models.conversation import (
    ConversationMemory,
    ConversationMessage,
    ConversationSession,
)
from app.schemas.planning import (
    AssistantChatRequest,
    AssistantChatResponse,
    ChatMessageSchema,
    ConversationMemorySchema,
    ConversationMemoryUpdateRequest,
    ConversationSessionResponse,
    GeneratedEventPlan,
    PlanGenerationRequest,
    PlanRefinementRequest,
)
from app.services.gemini_service import GeminiService
from app.services.planning_engine import PlanningEngineService, parse_prompt_intent

logger = logging.getLogger("eventprice.conversation")


class ConversationService:
    """Manages multi-turn event discovery sessions and persistent structured memory."""

    def __init__(self, planning_service: Optional[PlanningEngineService] = None):
        self.planning_service = planning_service or PlanningEngineService()
        self.gemini_service = GeminiService()

    # =========================================================================
    # Session & Memory Lifecycle
    # =========================================================================

    def get_or_create_session(
        self,
        db: Session,
        session_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> Tuple[ConversationSession, ConversationMemory]:
        """Loads an existing conversation session or initializes a new one with structured memory."""
        session_obj: Optional[ConversationSession] = None

        if session_id:
            try:
                parsed_id = uuid.UUID(session_id)
                session_obj = (
                    db.query(ConversationSession)
                    .filter(ConversationSession.id == parsed_id)
                    .first()
                )
            except (ValueError, TypeError):
                session_obj = None

        if not session_obj:
            parsed_event_id = None
            if event_id:
                try:
                    parsed_event_id = uuid.UUID(event_id)
                except (ValueError, TypeError):
                    parsed_event_id = None

            session_obj = ConversationSession(
                title="New Event Consultation",
                event_id=parsed_event_id,
            )
            db.add(session_obj)
            db.flush()

            # Initialize structured memory
            memory_obj = ConversationMemory(
                session_id=session_obj.id,
                currency="INR",
                budget_provenance="unknown",
                confirmed_fields=[],
                missing_fields=[
                    "event_type",
                    "occasion",
                    "expected_guest_count",
                    "location",
                    "event_date",
                    "preferences",
                ],
                plan_generated=False,
            )
            db.add(memory_obj)
            db.commit()
            db.refresh(session_obj)
            db.refresh(memory_obj)
            return session_obj, memory_obj

        memory_obj = (
            db.query(ConversationMemory)
            .filter(ConversationMemory.session_id == session_obj.id)
            .first()
        )
        if not memory_obj:
            memory_obj = ConversationMemory(
                session_id=session_obj.id,
                currency="INR",
                budget_provenance="unknown",
                confirmed_fields=[],
                missing_fields=["event_type", "expected_guest_count", "location"],
                plan_generated=False,
            )
            db.add(memory_obj)
            db.commit()
            db.refresh(memory_obj)

        return session_obj, memory_obj

    # =========================================================================
    # Fact Extraction & Memory Updating
    # =========================================================================

    def extract_and_update_facts(
        self,
        user_message: str,
        memory: ConversationMemory,
    ) -> List[str]:
        """Extracts facts from user message in context of previous question and updates memory.
        
        Returns a list of newly extracted or updated field names.
        """
        clean_msg = user_message.strip()
        lower_msg = clean_msg.lower()
        last_q = (memory.last_question_asked or "").lower()
        updated_fields: List[str] = []

        # 1. Flexible Event Type Extraction
        event_types = {
            "robotics-competition": [
                "robotics competition", "robotics challenge", "robotics contest", "robotics tournament",
                "bot brawl", "robot fight", "autonomous robotics", "robotics battle"
            ],
            "hackathon": [
                "hackathon", "hack-a-thon", "codefest", "coding marathon", "buildathon",
                "datathon", "ideathon", "devfest", "hack day"
            ],
            "tech-fest": [
                "technical fest", "tech fest", "college tech fest", "college technical fest",
                "science fest", "annual tech fest"
            ],
            "workshop": [
                "workshop", "hands-on workshop", "bootcamp", "training session", "masterclass"
            ],
            "seminar": [
                "seminar", "webinar", "colloquium", "panel discussion"
            ],
            "meetup": [
                "meetup", "user group meet", "developers meetup", "founders meetup", "community meetup"
            ],
            "networking": [
                "networking event", "networking session", "business mixer", "speed networking"
            ],
            "exhibition": [
                "exhibition", "trade show", "product showcase", "art exhibition", "science fair"
            ],
            "product-launch": [
                "product launch", "launch party", "app launch", "book launch", "brand launch"
            ],
            "wedding": [
                "wedding", "marriage", "shaadi", "reception", "sangeet", "mehendi", "nikah", "haldi", "roka"
            ],
            "birthday": [
                "birthday", "bday", "turning 1", "turning 18", "turning 21", "turning 30", "turning 50", "kids party"
            ],
            "anniversary": [
                "anniversary", "silver jubilee", "golden jubilee", "work anniversary"
            ],
            "get-together": [
                "get-together", "get together", "get to gether", "get-to-gether", "gettogether",
                "reunion", "hangout", "party with friends", "gathering", "alumni meet"
            ],
            "conference": [
                "conference", "summit", "symposium", "congress", "convention"
            ],
            "corporate": [
                "corporate event", "company offsite", "team outing", "company party", "townhall", "annual meet", "corporate retreat"
            ],
            "community": [
                "community event", "festival", "cultural fest", "pooja", "puja", "celebration", "society", "carnival"
            ],
            "dinner": [
                "dinner party", "gala dinner", "cocktail dinner", "lunch party", "brunch"
            ],
        }

        etype_found = False
        for etype, kws in event_types.items():
            if any(kw in lower_msg for kw in kws):
                if memory.event_type != etype:
                    memory.event_type = etype
                    updated_fields.append("event_type")
                etype_found = True
                break

        # If last question was asking about event type and user gave a short answer
        if not etype_found and ("what kind of event" in last_q or "what event" in last_q):
            clean_token = lower_msg.replace("a ", "").replace("an ", "").strip()
            for etype, kws in event_types.items():
                if clean_token == etype or clean_token in kws:
                    memory.event_type = etype
                    updated_fields.append("event_type")
                    etype_found = True
                    break
            if not etype_found and 2 <= len(clean_token) <= 40:
                memory.event_type = clean_token.replace(" ", "-").lower()
                updated_fields.append("event_type")
                etype_found = True

        # Custom event extraction from intent patterns: e.g. "plan a photography exhibition", "organize an esports tournament"
        if not etype_found and not memory.event_type:
            custom_match = re.search(
                r"\b(?:plan|organize|host|arrange|conduct|holding|setting up)\s+(?:a|an)\s+([a-zA-Z0-9\-\s]{3,35}?)(?:\s+(?:about|on|for|with|in|at|around)\b|[.,!?]|$)",
                lower_msg
            )
            if custom_match:
                cand = custom_match.group(1).strip()
                cand_clean = cand.replace("small ", "").replace("large ", "").replace("medium ", "").replace("mini ", "").strip()
                if cand_clean and not any(w in cand_clean.lower() for w in ["event", "something", "party", "get together", "trip"]):
                    custom_type = cand_clean.replace(" ", "-").lower()
                    memory.event_type = custom_type
                    updated_fields.append("event_type")
                    etype_found = True

        # 2. Scale Extraction ("small", "medium", "large", "mini", "massive", "grand", "mega", "intimate")
        scale_match = re.search(r"\b(small|mini|medium|large|massive|grand|mega|intimate|boutique)\b", lower_msg)
        if scale_match:
            scale_val = scale_match.group(1).lower()
            if memory.scale != scale_val:
                memory.scale = scale_val
                updated_fields.append("scale")

        # 3. Theme / Subject Extraction ("about robotics", "themed retro")
        date_words = {
            "january", "february", "march", "april", "may", "june", "july", "august",
            "september", "october", "november", "december", "jan", "feb", "mar", "apr",
            "jun", "jul", "aug", "sep", "oct", "nov", "dec", "monday", "tuesday",
            "wednesday", "thursday", "friday", "saturday", "sunday", "weekend", "week",
            "tomorrow", "today", "tonight", "next month", "next week"
        }
        theme_match = re.search(
            r"\b(?:about|themed|theme|topic|focusing on|centered on|dedicated to)\s+([a-zA-Z0-9\-\s]{2,40}?)(?:\s+(?:for|with|in|at|around|\d)|[.,!?]|$)",
            lower_msg
        )
        if theme_match:
            clean_theme = theme_match.group(1).strip().title()
            if (
                clean_theme.lower() not in ("a", "an", "the", "it", "this", "that", "friends", "next month", "weekend", "guests", "participants", "people", "budget")
                and not any(dw in clean_theme.lower() for dw in date_words)
                and not re.search(r"\d", clean_theme)
            ):
                if memory.theme != clean_theme:
                    memory.theme = clean_theme
                    updated_fields.append("theme")

        # 4. Duration Extraction ("24-hour", "36-hour", "one-day", "weekend", "2 days")
        duration_match = re.search(
            r"\b(\d+\s*(?:hours?|hrs?|days?)|24-hour|36-hour|48-hour|one-day|single-day|half-day|weekend|week-long)\b",
            lower_msg
        )
        if duration_match:
            dur_val = duration_match.group(1).lower()
            if memory.duration != dur_val:
                memory.duration = dur_val
                updated_fields.append("duration")

        # 5. Format Type Extraction ("in-person", "online", "virtual", "hybrid")
        format_match = re.search(r"\b(in-person|in person|offline|online|virtual|hybrid)\b", lower_msg)
        if format_match:
            raw_fmt = format_match.group(1).lower()
            fmt_val = "in-person" if "in" in raw_fmt or "off" in raw_fmt else raw_fmt.replace(" ", "-")
            if memory.format_type != fmt_val:
                memory.format_type = fmt_val
                updated_fields.append("format_type")

        # Synthesize working title / event name
        if memory.event_type:
            parts = []
            if memory.scale:
                parts.append(memory.scale.title())
            if memory.theme:
                parts.append(memory.theme)
            elif memory.occasion:
                parts.append(memory.occasion.title())
            parts.append(memory.event_type.replace("-", " ").title())
            memory.event_name = " ".join(parts)

        # 2. Occasion & Invitees Extraction
        if "who are you planning to invite" in last_q or "who is attending" in last_q or "what's the occasion" in last_q or "what is the occasion" in last_q:
            if clean_msg:
                memory.occasion = clean_msg
                updated_fields.append("occasion")
                if memory.event_type:
                    memory.event_name = f"{clean_msg.title()} {memory.event_type.replace('-', ' ').title()}"
        elif any(phrase in lower_msg for phrase in ["friends", "family", "colleagues", "relatives", "students", "team", "batchmates"]):
            # Match audience
            match = re.search(r"(college friends|school friends|family members|colleagues|office team|batchmates|relatives|close friends)", lower_msg)
            if match and memory.occasion != match.group(1):
                memory.occasion = match.group(1).title()
                updated_fields.append("occasion")

        # 3. Headcount / Guest Count Extraction
        # Priority A: Explicit mention with noun like "20 guests", "50 pax", "for 100 people"
        explicit_count_match = re.search(
            r"\b(\d{1,5})\s*(?:guests?|people|pax|attendees?|participants?|persons?|members?|invitees?)\b",
            lower_msg
        )
        if explicit_count_match:
            try:
                count_val = int(explicit_count_match.group(1))
                if 1 <= count_val <= 500000:
                    if memory.expected_guest_count != count_val:
                        memory.expected_guest_count = count_val
                        updated_fields.append("expected_guest_count")
            except (ValueError, TypeError):
                pass
        elif "how many" in last_q or "guest count" in last_q or "headcount" in last_q or "participants are you expecting" in last_q:
            # Priority B: Answering a direct headcount question with just a number (e.g. "around 30", "50")
            isolated_match = re.search(r"\b(?:around|approx|approximately|about|expecting|for)?\s*(\d{1,5})\b", lower_msg)
            if isolated_match:
                try:
                    count_val = int(isolated_match.group(1))
                    if 1 <= count_val <= 500000:
                        if memory.expected_guest_count != count_val:
                            memory.expected_guest_count = count_val
                            updated_fields.append("expected_guest_count")
                except (ValueError, TypeError):
                    pass

        # 4. Location Extraction
        # Check standard Indian locations
        cities = [
            "hyderabad", "bengaluru", "bangalore", "mumbai", "delhi", "new delhi",
            "goa", "pune", "chennai", "kolkata", "jaipur", "udaipur", "ahmedabad",
            "kochi", "chandigarh", "lucknow", "gurugram", "gurgaon", "noida"
        ]
        loc_matched = False
        for c in cities:
            if c in lower_msg:
                clean_city = "Bengaluru" if c in ("bengaluru", "bangalore") else c.title()
                if memory.location != clean_city:
                    memory.location = clean_city
                    updated_fields.append("location")
                loc_matched = True
                break

        if not loc_matched and ("where would you like to host" in last_q or "which city" in last_q or "location" in last_q):
            # Take user's short input as location if < 40 chars
            clean_loc = clean_msg.strip().replace("in ", "").replace("at ", "").strip()
            if 2 <= len(clean_loc) <= 40 and not any(w in clean_loc.lower() for w in ["yes", "no", "maybe", "idk"]):
                memory.location = clean_loc.title()
                updated_fields.append("location")

        # 5. Budget Extraction
        intent = parse_prompt_intent(clean_msg)
        if intent["target_budget"] is not None:
            # User explicitly provided a budget ceiling
            if memory.target_budget != intent["target_budget"] or memory.budget_provenance != "user_provided":
                memory.target_budget = intent["target_budget"]
                memory.budget_provenance = "user_provided"
                updated_fields.append("target_budget")
        elif intent["budget_provenance"] == "benchmark_estimate":
            if memory.budget_provenance != "user_provided":
                memory.budget_provenance = "benchmark_estimate"
                updated_fields.append("budget_provenance")

        # 6. Date / Time Extraction
        date_match = re.search(r"\b(202\d-\d{2}-\d{2})\b", clean_msg)
        if date_match:
            memory.event_date = date_match.group(1)
            updated_fields.append("event_date")
        else:
            day_month_match = re.search(
                r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)(?:\s+\d{4})?)\b",
                lower_msg,
            )
            month_day_match = re.search(
                r"\b((?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+\d{4})?)\b",
                lower_msg,
            )
            if day_month_match:
                memory.event_date = day_month_match.group(1).title()
                updated_fields.append("event_date")
            elif month_day_match:
                memory.event_date = month_day_match.group(1).title()
                updated_fields.append("event_date")
            elif any(w in lower_msg for w in ["next month", "this weekend", "in 2 weeks", "december", "january", "november", "saturday", "sunday"]):
                for phrase in ["next month", "this weekend", "in 2 weeks", "next weekend", "december", "november"]:
                    if phrase in lower_msg:
                        memory.event_date = phrase.title()
                        updated_fields.append("event_date")
                        break

        # 7. Granular Preferences (Venue, Food, Entertainment, Decor)
        if any(w in lower_msg for w in ["rooftop", "banquet", "resort", "beach", "hotel", "outdoor", "lawn", "hall", "farmhouse"]):
            for v in ["rooftop", "banquet hall", "resort", "beach", "luxury hotel", "outdoor lawn", "farmhouse"]:
                if v in lower_msg:
                    memory.venue_preferences = v.title()
                    updated_fields.append("venue_preferences")
                    break

        if any(w in lower_msg for w in ["vegan", "vegetarian", "jain", "halal", "non-veg", "buffet", "finger food", "bbq", "biryani"]):
            food_items = [w for w in ["vegan", "vegetarian", "jain", "buffet", "finger food", "bbq", "biryani", "north indian", "south indian"] if w in lower_msg]
            if food_items:
                memory.food_preferences = ", ".join(food_items).title()
                updated_fields.append("food_preferences")

        if any(w in lower_msg for w in ["live band", "dj", "acoustic", "karaoke", "games", "emcee", "music"]):
            for ent in ["live band", "dj", "acoustic music", "karaoke", "party games", "emcee"]:
                if ent in lower_msg:
                    memory.entertainment_preferences = ent.title()
                    updated_fields.append("entertainment_preferences")
                    break

        # Update confirmed & missing field lists
        confirmed = []
        if memory.event_type: confirmed.append("event_type")
        if memory.theme: confirmed.append("theme")
        if memory.scale: confirmed.append("scale")
        if memory.duration: confirmed.append("duration")
        if memory.format_type: confirmed.append("format_type")
        if memory.occasion: confirmed.append("occasion")
        if memory.expected_guest_count: confirmed.append("expected_guest_count")
        if memory.location: confirmed.append("location")
        if memory.event_date: confirmed.append("event_date")
        if memory.target_budget and memory.budget_provenance == "user_provided": confirmed.append("target_budget")
        if memory.venue_preferences: confirmed.append("venue_preferences")
        if memory.food_preferences: confirmed.append("food_preferences")
        if memory.entertainment_preferences: confirmed.append("entertainment_preferences")

        all_needed = ["event_type", "expected_guest_count", "location", "event_date", "target_budget"]
        missing = [f for f in all_needed if f not in confirmed]

        memory.confirmed_fields = confirmed
        memory.missing_fields = missing

        return updated_fields

    # =========================================================================
    # Intelligent Single-Question Selection
    # =========================================================================

    def select_next_question(self, memory: ConversationMemory) -> Tuple[str, List[str]]:
        """Selects exactly ONE natural next question based on what is missing.
        
        Returns (question_text, suggested_quick_replies).
        """
        # Priority 1: Event Type
        if not memory.event_type:
            q = "What type of event are you looking to plan? (e.g. Wedding, Birthday Party, Get-Together, Corporate Offsite)"
            prompts = ["Get-Together with friends", "Birthday Party", "Traditional Wedding", "Corporate Event"]
            return q, prompts

        # Priority 2: Hackathons, Robotics Competitions, Tech Fests, Competitions
        if memory.event_type in ("hackathon", "robotics-competition", "tech-fest", "competition"):
            if not memory.expected_guest_count:
                q = "How many participants are you expecting?"
                prompts = ["50 participants", "One-day event", "College campus venue", "Team-based competition"]
                return q, prompts

            if not memory.duration:
                q = "What will be the duration and format of the hackathon? (e.g., 24-hour sprint, one-day event, or weekend competition)"
                prompts = ["24-hour sprint", "One-day event", "Weekend competition", "48-hour buildathon"]
                return q, prompts

            if not memory.location:
                q = "Where will the hackathon take place? (e.g., college campus, tech hub, or coworking space)"
                prompts = ["College campus venue", "Bengaluru Tech Hub", "Hyderabad Innovation Center", "Online / Virtual"]
                return q, prompts

            if not memory.venue_preferences and not memory.other_instructions:
                q = "Do you have specific hardware, power, or robotics arena requirements for the teams?"
                prompts = ["Dedicated robotics test arena", "High-speed LAN & power strips", "Standard team workstations", "Decide hardware later"]
                return q, prompts

            if not memory.food_preferences:
                q = "What are your catering plans for the participants? (e.g. continuous coffee/caffeine bar, midnight pizza, or buffet meals)"
                prompts = ["Continuous coffee & snack bar", "Midnight pizza & energy drinks", "Buffet lunch & dinner", "Decide catering later"]
                return q, prompts

            if not memory.target_budget:
                q = "Do you have a target budget ceiling for prizes, venue, and catering, or would you like me to suggest an estimate?"
                prompts = ["Suggest a reasonable budget", "Budget is flexible", "Generate plan now"]
                return q, prompts

            q = "We have all the key details! Would you like me to generate your complete structured hackathon plan now?"
            prompts = ["Generate event plan now", "Add live mentor sessions", "Review details"]
            return q, prompts

        # Priority 3: Workshops & Seminars
        if memory.event_type in ("workshop", "seminar"):
            if not memory.expected_guest_count:
                q = f"How many attendees or participants are you expecting for the {memory.event_type}?"
                prompts = ["Around 30 attendees", "Around 50 participants", "100+ attendees", "Decide count later"]
                return q, prompts

            if not memory.location:
                q = "Where would you like to host it? (e.g. city or training venue)"
                prompts = ["Bengaluru", "Hyderabad", "Mumbai", "Online / Webinar"]
                return q, prompts

            if not memory.duration:
                q = "What is the planned duration for the session? (e.g. half-day, full-day, 2 days)"
                prompts = ["Half-day session", "Full-day hands-on workshop", "2-day bootcamp", "Decide duration later"]
                return q, prompts

            if not memory.target_budget:
                q = "Do you have a target budget in mind, or would you like me to suggest an estimate?"
                prompts = ["Suggest a reasonable budget", "Budget is flexible", "Generate plan now"]
                return q, prompts

            q = f"We have all the key details! Would you like me to generate your structured {memory.event_type} plan now?"
            prompts = ["Generate event plan now", "Add hands-on lab exercises", "Review details"]
            return q, prompts

        # Priority 4: Occasion / Audience for Social Events
        if not memory.occasion and memory.event_type in ("get-together", "dinner", "party"):
            q = f"Awesome! Who are you planning to invite, or what is the special occasion for this {memory.event_type.replace('-', ' ')}?"
            prompts = ["College friends reunion", "Close family & relatives", "Work colleagues", "School batchmates"]
            return q, prompts

        # Priority 5: Expected Guest Count
        if not memory.expected_guest_count:
            noun = "guests" if memory.event_type in ("wedding", "birthday", "dinner", "get-together") else "attendees"
            q = f"Approximately how many {noun} are you expecting for the {memory.event_type.replace('-', ' ')}?"
            prompts = ["Around 25–30 guests", "Around 50 people", "100 attendees", "200+ guests"]
            return q, prompts

        # Priority 6: Location / City
        if not memory.location:
            q = "Where would you like to host it? (e.g. city or preferred area)"
            prompts = ["Hyderabad", "Bengaluru", "Goa", "Mumbai", "Delhi"]
            return q, prompts

        # Priority 7: Event Date / Timeframe
        if not memory.event_date:
            q = "Do you have a target date or timeframe in mind for the event?"
            prompts = ["Next month on a weekend", "In about 2–3 months", "Date is flexible", "Decide date later"]
            return q, prompts

        # Priority 8: Specific Vibe / Venue or Food Preferences
        if not memory.venue_preferences and not memory.food_preferences:
            q = "What kind of vibe or venue are you envisioning? (e.g. cozy rooftop, outdoor lawn, private banquet, or cafe)"
            prompts = ["Cozy rooftop / cafe", "Outdoor lawn / garden", "Banquet hall", "Generate initial plan now"]
            return q, prompts

        # Priority 9: Budget (Optional)
        if not memory.target_budget:
            q = "Do you have a target budget ceiling in mind, or would you like me to suggest an estimated market benchmark?"
            prompts = ["Suggest a reasonable budget", "Budget is flexible", "Generate plan now"]
            return q, prompts

        # All major attributes collected
        q = "We have all the key details! Would you like me to generate your complete structured event plan now?"
        prompts = ["Generate event plan now", "Add live acoustic music", "Review details"]
        return q, prompts

    # =========================================================================
    # Conversational Chat Entrypoint
    # =========================================================================

    def process_chat_message(
        self,
        db: Session,
        request: AssistantChatRequest,
    ) -> AssistantChatResponse:
        """Processes a conversational user message, extracts facts, manages memory,
        and conditionally triggers single questions or plan generation."""
        session_obj, memory = self.get_or_create_session(
            db=db,
            session_id=request.session_id,
            event_id=request.event_id,
        )

        user_text = request.message.strip()

        # 1. Record User Message
        user_msg = ConversationMessage(
            session_id=session_obj.id,
            sender="user",
            content=user_text,
            reply_type="user_turn",
            suggested_prompts=[],
        )
        db.add(user_msg)
        db.flush()

        # 2. Check for Greetings / General Openers without prior context
        lower_user = user_text.lower()
        is_greeting = lower_user in (
            "hi", "hello", "hey", "hi there", "hello there", "namaste", "good morning", "good evening", "howdy"
        )

        # 3. Extract Facts & Update Memory
        newly_updated = self.extract_and_update_facts(user_text, memory)

        # 4. Check if Plan Generation is requested
        wants_plan_now = (
            request.request_plan_generation
            or any(phrase in lower_user for phrase in [
                "generate a plan", "generate plan", "give me a plan", "give me plan",
                "create a plan", "create plan", "show me a plan", "show the plan",
                "build the plan", "plan this now", "i'm ready for the plan", "generate event plan",
                "give plan", "generate the plan", "make a plan", "suggest a plan",
                "preliminary plan", "initial plan", "generate plan now", "generate the plan now",
                "please generate the plan", "give me complete plan", "give me a complete plan",
                "give complete plan", "complete plan", "full plan", "give me full plan"
            ])
            or (
                memory.last_question_asked
                and "structured event plan" in memory.last_question_asked.lower()
                and any(lower_user.strip().startswith(aff) for aff in ["yes", "sure", "ok", "okay", "yep", "yeah", "please do", "go ahead"])
            )
        )

        # Check if this is a refinement to an existing generated plan
        is_refinement = memory.plan_generated and memory.current_plan_payload is not None

        # ---------------------------------------------------------------------
        # Case A: User sent a pure greeting
        # ---------------------------------------------------------------------
        if is_greeting and not memory.event_type:
            reply_text = (
                "👋 **Hello! I'm your AI Event Planning Concierge.**\n\n"
                "I help you design, budget, and organize complete events step-by-step. "
                "Let's start from the beginning: **What type of event are you looking to plan?** "
                "(e.g. Wedding, Birthday, College Reunion, Get-Together, Conference)"
            )
            prompts = [
                "Plan a Get-Together",
                "Plan a Birthday Party",
                "Plan a Wedding in Hyderabad",
                "Corporate Team Offsite",
            ]
            next_q = "What type of event are you looking to plan?"
            memory.last_question_asked = next_q

            agent_msg = ConversationMessage(
                session_id=session_obj.id,
                sender="assistant",
                content=reply_text,
                reply_type="greeting",
                current_question=next_q,
                suggested_prompts=prompts,
            )
            db.add(agent_msg)
            db.commit()

            return AssistantChatResponse(
                session_id=str(session_obj.id),
                message=reply_text,
                reply_type="greeting",
                current_question=next_q,
                structured_plan=None,
                memory=self._build_memory_schema(memory),
                suggested_prompts=prompts,
            )

        # ---------------------------------------------------------------------
        # Case B: Memory-Aware Refinement of an Existing Plan
        # ---------------------------------------------------------------------
        if is_refinement and not wants_plan_now:
            # User wants to adjust existing plan
            try:
                cached_plan_dict = json.loads(memory.current_plan_payload)
                existing_plan = GeneratedEventPlan(**cached_plan_dict)

                # If user updated guest count, location, or budget in this turn, synchronize plan brief
                if "expected_guest_count" in newly_updated and memory.expected_guest_count:
                    existing_plan.brief.expected_guest_count = memory.expected_guest_count
                if "location" in newly_updated and memory.location:
                    existing_plan.brief.location = memory.location
                if "target_budget" in newly_updated and memory.target_budget:
                    existing_plan.brief.target_budget = memory.target_budget
                    existing_plan.brief.budget_provenance = memory.budget_provenance

                # Run refinement engine
                refined_plan = self.planning_service.refine_plan(
                    PlanRefinementRequest(
                        existing_plan=existing_plan,
                        refinement_instructions=user_text,
                    )
                )

                memory.current_plan_payload = refined_plan.model_dump_json()
                db.commit()

                reply_text = (
                    f"✨ **Plan Updated for \"{refined_plan.brief.event_name}\"**\n\n"
                    f"I've updated your plan based on: *\"{user_text}\"*.\n"
                    f"• **Location:** {refined_plan.brief.location or 'Flexible'}\n"
                    f"• **Attendees:** {refined_plan.brief.expected_guest_count or 'TBD'} guests\n"
                    f"• **Total Allocation:** INR {refined_plan.budget_proposal.total_allocated:,.2f} "
                    f"({len(refined_plan.budget_proposal.allocations)} category line items)\n\n"
                    "You can continue chatting to make further refinements, adjust line items, or review the vendor checklist!"
                )
                prompts = [
                    "Reduce catering budget by 10%",
                    "Add acoustic live music band",
                    "Make it eco-friendly decor",
                    "Review vendor procurement checklist",
                ]

                agent_msg = ConversationMessage(
                    session_id=session_obj.id,
                    sender="assistant",
                    content=reply_text,
                    reply_type="plan_refined",
                    structured_plan_payload=refined_plan.model_dump_json(),
                    suggested_prompts=prompts,
                )
                db.add(agent_msg)
                db.commit()

                return AssistantChatResponse(
                    session_id=str(session_obj.id),
                    message=reply_text,
                    reply_type="plan_refined",
                    current_question=None,
                    structured_plan=refined_plan,
                    memory=self._build_memory_schema(memory),
                    suggested_prompts=prompts,
                )
            except Exception as e:
                logger.error("Failed to refine plan: %s", str(e), exc_info=True)

        # ---------------------------------------------------------------------
        # Case C: Planning Generation Gate
        # ---------------------------------------------------------------------
        # Generate complete structured plan only if user explicitly requested it or confirmed generation
        if wants_plan_now:
            # Synthesize accumulated prompt from memory
            accumulated_prompt = self._build_synthesis_prompt(memory, user_text)

            plan_req = PlanGenerationRequest(
                user_prompt=accumulated_prompt,
                event_type=memory.event_type or "other",
                event_name=memory.event_name or f"{memory.event_type or 'Event'} Plan",
                location=memory.location,
                guest_count=memory.expected_guest_count,
                target_budget=memory.target_budget,
                budget_provenance=memory.budget_provenance,
                currency=memory.currency or "INR",
                event_date=memory.event_date if memory.event_date and "-" in memory.event_date else None,
            )

            generated_plan = self.planning_service.generate_plan(plan_req)

            memory.plan_generated = True
            memory.current_plan_payload = generated_plan.model_dump_json()
            session_obj.title = generated_plan.brief.event_name
            db.commit()

            bp = generated_plan.budget_proposal
            budget_str = f"INR {bp.total_allocated:,.2f}" if bp.total_allocated > 0 else "Budget Not Provided"
            reply_text = (
                f"🎉 **Structured Event Plan Generated for \"{generated_plan.brief.event_name}\"!**\n\n"
                f"Based on our conversation, I've synthesized a complete initial draft:\n"
                f"• **Format:** {generated_plan.brief.event_type.title()} ({generated_plan.brief.expected_guest_count or 'TBD'} guests)\n"
                f"• **Location:** {generated_plan.brief.location or 'Flexible'}\n"
                f"• **Budget Status:** {budget_str} (includes INR {bp.contingency_amount:,.2f} emergency buffer)\n"
                f"• **Vendors & Timeline:** {len(generated_plan.vendor_checklist)} procurement categories, {len(generated_plan.timeline)} staged milestones.\n\n"
                "You can now inspect the full plan below, or ask me for any refinements!"
            )
            prompts = [
                "Suggest a reasonable budget estimate",
                "Add live band entertainment",
                "Reduce total budget by 15%",
                "Review vendor checklist",
            ]

            agent_msg = ConversationMessage(
                session_id=session_obj.id,
                sender="assistant",
                content=reply_text,
                reply_type="plan_generated",
                structured_plan_payload=generated_plan.model_dump_json(),
                suggested_prompts=prompts,
            )
            db.add(agent_msg)
            db.commit()

            return AssistantChatResponse(
                session_id=str(session_obj.id),
                message=reply_text,
                reply_type="plan_generated",
                current_question=None,
                structured_plan=generated_plan,
                memory=self._build_memory_schema(memory),
                suggested_prompts=prompts,
            )

        # ---------------------------------------------------------------------
        # Case D: Multi-Turn Conversational Discovery (Ask ONE question)
        # ---------------------------------------------------------------------
        next_question, suggested_prompts = self.select_next_question(memory)
        memory.last_question_asked = next_question

        # Craft empathetic consultant response acknowledging newly received facts
        ack_parts = []
        if memory.theme and memory.event_type and ("theme" in newly_updated or "event_type" in newly_updated):
            ack_parts.append(f"That sounds like a {memory.theme.lower()} {memory.event_type.replace('-', ' ')}! Let's organize it.")
        elif memory.theme and "theme" in newly_updated:
            ack_parts.append(f"A **{memory.theme}** themed event sounds exciting! Let's plan it.")
        elif "event_type" in newly_updated and memory.event_type:
            ack_parts.append(f"A **{memory.event_type.replace('-', ' ')}** sounds wonderful! Let's plan it.")
        if "occasion" in newly_updated and memory.occasion and not memory.theme:
            ack_parts.append(f"Gathering **{memory.occasion}** will make for a great time.")
        if "expected_guest_count" in newly_updated and memory.expected_guest_count:
            noun = "participants" if memory.event_type in ("hackathon", "robotics-competition", "tech-fest", "workshop", "competition") else "attendees"
            ack_parts.append(f"Got it — around **{memory.expected_guest_count} {noun}**.")
        if "location" in newly_updated and memory.location:
            ack_parts.append(f"**{memory.location}** is a fantastic destination.")
        if "target_budget" in newly_updated and memory.target_budget:
            ack_parts.append(f"Target budget set to **INR {memory.target_budget:,.2f}**.")
        if "event_date" in newly_updated and memory.event_date:
            ack_parts.append(f"Marked for **{memory.event_date}**.")

        ack_prefix = " ".join(ack_parts)
        if ack_prefix:
            if ack_prefix.endswith("Let's organize it."):
                reply_text = f"{ack_prefix} {next_question}"
            else:
                reply_text = f"{ack_prefix}\n\n{next_question}"
        else:
            reply_text = f"Sure! Let's get that planned.\n\n{next_question}"

        agent_msg = ConversationMessage(
            session_id=session_obj.id,
            sender="assistant",
            content=reply_text,
            reply_type="discovery_question",
            current_question=next_question,
            suggested_prompts=suggested_prompts,
        )
        db.add(agent_msg)
        db.commit()

        return AssistantChatResponse(
            session_id=str(session_obj.id),
            message=reply_text,
            reply_type="discovery_question",
            current_question=next_question,
            structured_plan=None,
            memory=self._build_memory_schema(memory),
            suggested_prompts=suggested_prompts,
        )

    # =========================================================================
    # Context Retrieval & Session Management
    # =========================================================================

    def get_session_history(
        self,
        db: Session,
        session_id: str,
    ) -> ConversationSessionResponse:
        """Retrieves full conversation history and structured memory for restoring context across page reloads."""
        try:
            parsed_id = uuid.UUID(session_id)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid session UUID: {session_id}")

        session_obj = (
            db.query(ConversationSession)
            .filter(ConversationSession.id == parsed_id)
            .first()
        )
        if not session_obj:
            raise KeyError(f"Session '{session_id}' not found.")

        memory = (
            db.query(ConversationMemory)
            .filter(ConversationMemory.session_id == session_obj.id)
            .first()
        )
        if not memory:
            memory = ConversationMemory(session_id=session_obj.id)
            db.add(memory)
            db.commit()
            db.refresh(memory)

        serialized_messages: List[ChatMessageSchema] = []
        for msg in session_obj.messages:
            parsed_plan = None
            if msg.structured_plan_payload:
                try:
                    parsed_plan = GeneratedEventPlan(**json.loads(msg.structured_plan_payload))
                except Exception:
                    pass

            serialized_messages.append(
                ChatMessageSchema(
                    id=str(msg.id),
                    sender=msg.sender,
                    content=msg.content,
                    reply_type=msg.reply_type,
                    current_question=msg.current_question,
                    structured_plan=parsed_plan,
                    suggested_prompts=msg.suggested_prompts or [],
                    created_at=msg.created_at,
                )
            )

        return ConversationSessionResponse(
            session_id=str(session_obj.id),
            title=session_obj.title,
            event_id=str(session_obj.event_id) if session_obj.event_id else None,
            messages=serialized_messages,
            memory=self._build_memory_schema(memory),
            created_at=session_obj.created_at,
            updated_at=session_obj.updated_at,
        )

    def update_memory_directly(
        self,
        db: Session,
        session_id: str,
        update_req: ConversationMemoryUpdateRequest,
    ) -> ConversationMemorySchema:
        """Applies explicit user updates to structured memory."""
        try:
            parsed_id = uuid.UUID(session_id)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid session UUID: {session_id}")

        memory = (
            db.query(ConversationMemory)
            .filter(ConversationMemory.session_id == parsed_id)
            .first()
        )
        if not memory:
            raise KeyError(f"Memory for session '{session_id}' not found.")

        for field, val in update_req.model_dump(exclude_unset=True).items():
            if hasattr(memory, field) and val is not None:
                setattr(memory, field, val)

        # Refresh confirmed / missing
        confirmed = []
        if memory.event_type: confirmed.append("event_type")
        if memory.occasion: confirmed.append("occasion")
        if memory.expected_guest_count: confirmed.append("expected_guest_count")
        if memory.location: confirmed.append("location")
        if memory.event_date: confirmed.append("event_date")
        if memory.target_budget and memory.budget_provenance == "user_provided": confirmed.append("target_budget")
        if memory.venue_preferences: confirmed.append("venue_preferences")
        if memory.food_preferences: confirmed.append("food_preferences")
        if memory.entertainment_preferences: confirmed.append("entertainment_preferences")

        all_needed = ["event_type", "occasion", "expected_guest_count", "location", "event_date", "target_budget"]
        missing = [f for f in all_needed if f not in confirmed]

        memory.confirmed_fields = confirmed
        memory.missing_fields = missing
        db.commit()
        db.refresh(memory)

        return self._build_memory_schema(memory)

    # =========================================================================
    # Helpers
    # =========================================================================

    def _build_memory_schema(self, memory: ConversationMemory) -> ConversationMemorySchema:
        """Constructs Pydantic schema from database memory model."""
        ready = (
            memory.event_type is not None
            and memory.expected_guest_count is not None
            and memory.location is not None
        )
        return ConversationMemorySchema(
            event_type=memory.event_type,
            event_name=memory.event_name,
            occasion=memory.occasion,
            theme=memory.theme,
            scale=memory.scale,
            duration=memory.duration,
            format_type=memory.format_type,
            location=memory.location,
            expected_guest_count=memory.expected_guest_count,
            event_date=memory.event_date,
            event_time=memory.event_time,
            target_budget=memory.target_budget,
            budget_provenance=memory.budget_provenance,
            currency=memory.currency or "INR",
            venue_preferences=memory.venue_preferences,
            food_preferences=memory.food_preferences,
            dietary_requirements=memory.dietary_requirements,
            entertainment_preferences=memory.entertainment_preferences,
            decoration_preferences=memory.decoration_preferences,
            other_instructions=memory.other_instructions,
            confirmed_fields=memory.confirmed_fields or [],
            missing_fields=memory.missing_fields or [],
            last_question_asked=memory.last_question_asked,
            plan_generated=memory.plan_generated,
            ready_for_plan=ready,
        )

    def _build_synthesis_prompt(self, memory: ConversationMemory, latest_msg: str) -> str:
        """Combines accumulated memory facts into a clean synthesis prompt."""
        parts = []
        if memory.event_type:
            parts.append(f"Event: {memory.event_type.title()}")
        if memory.occasion:
            parts.append(f"Occasion/Audience: {memory.occasion}")
        if memory.expected_guest_count:
            parts.append(f"Guest Count: {memory.expected_guest_count} guests")
        if memory.location:
            parts.append(f"Location: {memory.location}")
        if memory.event_date:
            parts.append(f"Date: {memory.event_date}")
        if memory.target_budget and memory.budget_provenance == "user_provided":
            parts.append(f"Budget Ceiling: INR {memory.target_budget:,.2f}")
        elif memory.budget_provenance == "benchmark_estimate":
            parts.append("Budget: Please suggest a market benchmark estimate")
        if memory.venue_preferences:
            parts.append(f"Venue Style: {memory.venue_preferences}")
        if memory.food_preferences:
            parts.append(f"Food Preferences: {memory.food_preferences}")
        if memory.entertainment_preferences:
            parts.append(f"Entertainment: {memory.entertainment_preferences}")

        return " | ".join(parts) if parts else latest_msg
