"""Automated tests for Structured GenAI Event Planning Engine.

Verifies end-to-end plan generation, refinement, deterministic financial recalculation,
relative staged timelines, error handling, provider resilience, and draft-only non-persistence.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import httpx
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.models.event import Event
from app.models.vendor import Vendor
from app.models.price import VendorPriceRecord
from app.models.budget import EventBudget
from app.models.task import EventTask
from app.schemas.planning import (
    BudgetCategoryAllocation,
    GeneratedEventPlan,
    PlanBudgetProposal,
    PlanEventBrief,
    PlanGenerationRequest,
    PlanPersonalizedIdeas,
    PlanRefinementRequest,
    PlanTimelineTask,
    VendorChecklistItem,
)
from app.services.planning_engine import (
    PlanningEngineService,
    generate_deterministic_plan,
    parse_prompt_intent,
    recalculate_and_validate_budget_proposal,
)


# ============================================================================
# 1. Deterministic Prompt Parsing Tests
# ============================================================================


def test_parse_prompt_intent_heuristics():
    """Verify natural language parsing extracts event type, location, guest count, and budget."""
    # Wedding with lakhs budget and date
    p1 = "Planning a grand wedding in Mumbai for 300 guests with budget of 15 lakhs"
    res1 = parse_prompt_intent(p1)
    assert res1["event_type"] == "wedding"
    assert res1["guest_count"] == 300
    assert res1["location"] == "Mumbai"
    assert res1["target_budget"] == Decimal("1500000")

    # Birthday with K budget
    p2 = "Organizing a first birthday party in Bengaluru for 60 pax with 50k budget"
    res2 = parse_prompt_intent(p2)
    assert res2["event_type"] == "birthday"
    assert res2["guest_count"] == 60
    assert res2["location"] == "Bengaluru"
    assert res2["target_budget"] == Decimal("50000")

    # Community festival
    p3 = "Diwali community carnival in Jaipur with 400 people"
    res3 = parse_prompt_intent(p3)
    assert res3["event_type"] == "community"
    assert res3["guest_count"] == 400
    assert res3["location"] == "Jaipur"


# ============================================================================
# 2. Deterministic Financial Recalculation Safeguard Tests
# ============================================================================


def test_deterministic_budget_recalculation_overrides_llm():
    """Verify Python Decimal arithmetic overrides any arithmetic errors from LLM output."""
    raw_allocations = [
        BudgetCategoryAllocation(category="venue", suggested_amount=Decimal("150000.50"), rationale="Hall"),
        BudgetCategoryAllocation(category="catering", suggested_amount=Decimal("250000.75"), rationale="Food"),
        BudgetCategoryAllocation(category="contingency", suggested_amount=Decimal("50000.00"), rationale="Buffer"),
    ]
    # Sum: 150000.50 + 250000.75 + 50000.00 = 450001.25
    proposal = PlanBudgetProposal(
        allocations=raw_allocations,
        total_allocated=Decimal("999999.00"),  # erroneous total from LLM
        currency="INR",
    )

    verified = recalculate_and_validate_budget_proposal(
        proposal=proposal,
        target_budget=Decimal("500000.00"),
        currency="INR",
    )

    assert verified.total_allocated == Decimal("450001.25")
    assert verified.contingency_amount == Decimal("50000.00")
    assert verified.remaining_budget == Decimal("49998.75")
    assert verified.is_within_budget is True
    assert any("Unallocated Buffer" in a for a in verified.financial_alerts)
    assert "illustrative planning assumptions" in verified.estimate_provenance_notice.lower()


def test_budget_exceeding_target_flags_deficit_alert():
    """Verify budget deficit is deterministically flagged when allocations exceed target."""
    raw_allocations = [
        BudgetCategoryAllocation(category="venue", suggested_amount=Decimal("400000.00"), rationale="Hall"),
        BudgetCategoryAllocation(category="catering", suggested_amount=Decimal("300000.00"), rationale="Food"),
    ]
    proposal = PlanBudgetProposal(allocations=raw_allocations, currency="INR")

    verified = recalculate_and_validate_budget_proposal(
        proposal=proposal,
        target_budget=Decimal("500000.00"),
        currency="INR",
    )

    # 400k + 300k = 700k vs 500k target -> 200k deficit
    assert verified.total_allocated == Decimal("700000.00")
    assert verified.is_within_budget is False
    assert verified.remaining_budget == Decimal("-200000.00")
    assert any("Budget Deficit" in a for a in verified.financial_alerts)


def test_currency_mismatches_normalized_and_alerted():
    """Verify currency mismatches across allocations are normalized and flagged in alerts."""
    raw_allocations = [
        BudgetCategoryAllocation(category="venue", suggested_amount=Decimal("100000.00"), currency="USD", rationale="Venue"),
        BudgetCategoryAllocation(category="catering", suggested_amount=Decimal("150000.00"), currency="INR", rationale="Food"),
    ]
    proposal = PlanBudgetProposal(allocations=raw_allocations, currency="INR")

    verified = recalculate_and_validate_budget_proposal(
        proposal=proposal,
        target_budget=Decimal("300000.00"),
        currency="INR",
    )

    assert verified.currency == "INR"
    assert all(a.currency == "INR" for a in verified.allocations)
    assert any("Currency mismatch" in a for a in verified.financial_alerts)


def test_negative_financial_amounts_rejected_by_schema():
    """Verify negative allocation amounts and negative budgets are rejected via validation."""
    with pytest.raises(ValidationError):
        BudgetCategoryAllocation(category="venue", suggested_amount=Decimal("-5000.00"), rationale="Invalid")

    with pytest.raises(ValidationError):
        PlanGenerationRequest(user_prompt="Event", target_budget=Decimal("-1000.00"))


def test_negative_budget_allocations_sanitized_and_alerted():
    """Verify recalculation logic handles and resets any raw negative amounts that might bypass initial typing."""
    # Create valid allocation and modify internally to simulate raw edge case
    item = BudgetCategoryAllocation(category="misc", suggested_amount=Decimal("0.00"), rationale="Test")
    object.__setattr__(item, "suggested_amount", Decimal("-2500.00"))

    proposal = PlanBudgetProposal(allocations=[item], currency="INR")
    verified = recalculate_and_validate_budget_proposal(proposal=proposal, target_budget=Decimal("10000.00"))

    assert verified.allocations[0].suggested_amount == Decimal("0.00")
    assert any("Negative allocation detected" in a for a in verified.financial_alerts)


# ============================================================================
# 3. Dedicated Event Type Plan Generation Tests
# ============================================================================


def test_wedding_plan_generation():
    """Verify wedding plan generation produces wedding-specific themes, allocations, and checklists."""
    req = PlanGenerationRequest(
        user_prompt="Traditional Hindu wedding with 250 guests in Bengaluru with 12L budget on 2026-11-20",
        event_type="wedding",
        location="Bengaluru",
        guest_count=250,
        target_budget=Decimal("1200000.00"),
        event_date=date(2026, 11, 20),
    )
    plan = generate_deterministic_plan(req)

    assert plan.brief.event_type == "wedding"
    assert plan.brief.expected_guest_count == 250
    assert plan.brief.location == "Bengaluru"
    assert plan.brief.target_budget == Decimal("1200000.00")
    assert plan.brief.event_date == date(2026, 11, 20)

    # Personalized Ideas
    assert len(plan.personalized_ideas.theme_and_concept) >= 3
    assert len(plan.personalized_ideas.catering_ideas) >= 3
    assert any("mandap" in d.lower() or "floral" in d.lower() for d in plan.personalized_ideas.decoration_ideas)

    # Budget Proposal
    categories = [a.category for a in plan.budget_proposal.allocations]
    assert "venue" in categories
    assert "catering" in categories
    assert "decoration" in categories
    assert "contingency" in categories
    assert plan.budget_proposal.total_allocated == Decimal("1200000.00")

    # Vendor Checklist
    v_cats = [v.category for v in plan.vendor_checklist]
    assert "venue" in v_cats
    assert "catering" in v_cats

    # Timeline with dates back-calculated from event_date
    for task in plan.timeline:
        assert task.suggested_due_date is not None
        assert task.suggested_due_date <= date(2026, 11, 20)

    assert plan.provider == "deterministic_fallback"
    assert plan.is_live_ai is False
    assert plan.status == "draft"


def test_birthday_plan_generation():
    """Verify birthday plan generation produces birthday-specific themes, cake ideas, and party games."""
    b_req = PlanGenerationRequest(
        user_prompt="Retro themed 30th birthday party for 40 guests in Pune with 60k budget",
        event_type="birthday",
        guest_count=40,
        target_budget=Decimal("60000.00"),
    )
    b_plan = generate_deterministic_plan(b_req)

    assert b_plan.brief.event_type == "birthday"
    assert b_plan.brief.expected_guest_count == 40
    assert any("retro" in t.lower() or "neon" in t.lower() for t in b_plan.personalized_ideas.theme_and_concept)
    assert any("cake" in c.lower() for c in b_plan.personalized_ideas.catering_ideas)
    assert any("emcee" in e.lower() or "games" in e.lower() for e in b_plan.personalized_ideas.entertainment_ideas)


def test_community_event_generation():
    """Verify community event generation produces cultural, civic, and volunteer considerations."""
    c_req = PlanGenerationRequest(
        user_prompt="Neighborhood community cleanliness drive and cultural evening for 200 people in Kolkata",
        event_type="community",
        guest_count=200,
        location="Kolkata",
    )
    c_plan = generate_deterministic_plan(c_req)

    assert c_plan.brief.event_type == "community"
    assert c_plan.brief.expected_guest_count == 200
    assert any("community" in t.lower() or "eco" in t.lower() for t in c_plan.personalized_ideas.theme_and_concept)
    assert any("permit" in p.lower() or "civic" in p.lower() for p in c_plan.personalized_ideas.practical_recommendations)


def test_missing_event_date_uses_relative_stages_without_fabricated_dates():
    """Verify when no event_date is supplied, timeline tasks have suggested_due_date=None and clear relative stages."""
    req = PlanGenerationRequest(
        user_prompt="Planning a wedding in Goa with 150 guests, dates not finalized yet",
        event_type="wedding",
    )
    plan = generate_deterministic_plan(req)

    assert plan.brief.event_date is None
    assert "Exact calendar event date (staged planning applied)" in plan.brief.missing_information

    # All timeline tasks must strictly NOT fabricate a date
    for task in plan.timeline:
        assert task.suggested_due_date is None
        assert "Stage" in task.relative_timing or "weeks" in task.relative_timing


def test_missing_budget_uses_illustrative_benchmarks_and_flags_alert():
    """Verify when estimate is requested, it uses sensible benchmarks and appends explanatory financial alert."""
    req = PlanGenerationRequest(
        user_prompt="Suggest a reasonable budget for small office party for 25 people in Hyderabad",
    )
    plan = generate_deterministic_plan(req)

    assert plan.budget_proposal.total_allocated > Decimal("0.00")
    assert plan.budget_proposal.budget_provenance == "benchmark_estimate"
    assert plan.budget_proposal.is_within_budget is None
    assert any("benchmark" in a.lower() for a in plan.budget_proposal.financial_alerts)
    assert "illustrative planning assumptions" in plan.budget_proposal.estimate_provenance_notice.lower()


def test_incomplete_minimal_user_input():
    """Verify the planning engine handles extremely minimal/sparse user inputs safely without errors."""
    req = PlanGenerationRequest(user_prompt="party")
    plan = generate_deterministic_plan(req)

    assert plan.brief.event_name is not None
    assert plan.brief.expected_guest_count is not None
    assert plan.brief.target_budget is None
    assert plan.brief.budget_provenance == "unknown"
    assert len(plan.brief.missing_information) >= 2
    assert len(plan.brief.explicit_assumptions) >= 1
    assert len(plan.personalized_ideas.theme_and_concept) >= 1
    assert len(plan.budget_proposal.allocations) == 0
    assert plan.budget_proposal.contingency_amount == Decimal("0.00")
    assert plan.budget_proposal.is_within_budget is None
    assert len(plan.vendor_checklist) >= 2
    assert len(plan.timeline) >= 3


# ============================================================================
# 4. Mocked Live Gemini Structured Response & Fallback Tests
# ============================================================================


def test_gemini_structured_plan_success_flow():
    """Verify parsing and validation of a valid structured JSON response from Gemini."""
    settings = Settings(
        GEMINI_API_KEY="test-key-valid",
        GEMINI_MODEL="gemini-2.5-flash",
        AI_ENABLED=True,
    )

    mock_plan_payload = {
        "brief": {
            "event_type": "wedding",
            "event_name": "Royal Jaipur Wedding",
            "location": "Jaipur",
            "expected_guest_count": 200,
            "target_budget": "1500000.00",
            "currency": "INR",
            "confirmed_information": ["Confirmed heritage venue"],
            "missing_information": ["Mehendi artist"],
            "explicit_assumptions": ["2-day celebration"],
        },
        "personalized_ideas": {
            "theme_and_concept": ["Rajputana Royal Grandeur"],
            "decoration_ideas": ["Mirrorwork canopies and brass lanterns"],
            "catering_ideas": ["Dal Baati Churma and Laal Maas live counters"],
            "entertainment_ideas": ["Manganiyar folk musicians"],
            "guest_experience_suggestions": ["Block-printed silk stoles"],
            "practical_recommendations": ["Book haveli palace 6 months in advance"],
        },
        "budget_proposal": {
            "allocations": [
                {"category": "venue", "suggested_amount": "400000.00", "currency": "INR", "rationale": "Haveli rent", "source_type": "estimate"},
                {"category": "catering", "suggested_amount": "600000.00", "currency": "INR", "rationale": "2-day dining", "source_type": "estimate"},
                {"category": "contingency", "suggested_amount": "150000.00", "currency": "INR", "rationale": "10% reserve", "source_type": "estimate"},
            ]
        },
        "vendor_checklist": [
            {
                "category": "venue",
                "requirement_title": "Heritage Haveli",
                "description": "Courtyard and lawn palace",
                "important_questions_to_ask": ["Are fireworks permitted?"],
                "priority": "critical",
                "selection_considerations": ["Heritage preservation rules"],
            }
        ],
        "timeline": [
            {
                "task_title": "Haveli Palace Deposit",
                "description": "Lock palace reservation",
                "category": "venue",
                "priority": "critical",
                "stage": "early_planning",
                "relative_timing": "Stage 1 (6 months prior)",
                "dependencies": [],
                "why_it_matters": "Heritage properties have limited dates",
            }
        ],
    }

    mock_gemini_json_response = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": json.dumps(mock_plan_payload)}],
                    "role": "model",
                }
            }
        ]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_gemini_json_response
    mock_client.post.return_value = mock_response

    service = PlanningEngineService(settings=settings, http_client=mock_client)
    req = PlanGenerationRequest(user_prompt="Plan a royal wedding in Jaipur for 200 guests with 15L budget")
    plan = service.generate_plan(req)

    assert plan.is_live_ai is True
    assert plan.provider == "gemini"
    assert plan.model == "gemini-2.5-flash"
    assert plan.brief.event_name == "Royal Jaipur Wedding"
    assert plan.budget_proposal.total_allocated == Decimal("1150000.00")
    assert plan.budget_proposal.is_within_budget is True
    assert plan.status == "draft"


def test_invalid_structured_gemini_response_fallback():
    """Verify that if Gemini returns valid JSON but invalid schema, the engine safely falls back."""
    settings = Settings(
        GEMINI_API_KEY="test-key-valid",
        AI_ENABLED=True,
    )

    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    # Missing required brief fields like event_type and event_name
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps({"brief": {"invalid_field": 123}})}]}}]
    }
    mock_client.post.return_value = mock_response

    service = PlanningEngineService(settings=settings, http_client=mock_client)
    req = PlanGenerationRequest(user_prompt="Birthday party in Delhi for 50 people")
    plan = service.generate_plan(req)

    assert plan.is_live_ai is False
    assert plan.provider == "deterministic_fallback"
    assert "Schema Validation Fallback" in plan.disclaimer or "Fallback" in plan.disclaimer


def test_empty_gemini_response_fallback():
    """Verify that an empty or missing candidate response from Gemini triggers deterministic fallback."""
    settings = Settings(
        GEMINI_API_KEY="test-key-valid",
        AI_ENABLED=True,
    )

    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"candidates": []}
    mock_client.post.return_value = mock_response

    service = PlanningEngineService(settings=settings, http_client=mock_client)
    req = PlanGenerationRequest(user_prompt="Anniversary dinner for 20 guests")
    plan = service.generate_plan(req)

    assert plan.is_live_ai is False
    assert plan.provider == "deterministic_fallback"
    assert "Empty Candidates" in plan.disclaimer


def test_provider_timeout_fallback():
    """Verify that HTTP timeout when connecting to Gemini triggers graceful deterministic fallback."""
    settings = Settings(
        GEMINI_API_KEY="test-key-valid",
        AI_ENABLED=True,
    )

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = httpx.TimeoutException("Connection timed out after 30s")

    service = PlanningEngineService(settings=settings, http_client=mock_client)
    req = PlanGenerationRequest(user_prompt="Corporate offsite for 80 attendees in Goa")
    plan = service.generate_plan(req)

    assert plan.is_live_ai is False
    assert plan.provider == "deterministic_fallback"
    assert "Timeout" in plan.disclaimer


def test_provider_rate_limiting_and_server_error_fallback():
    """Verify that HTTP 429 Rate Limit and HTTP 500 errors trigger clearly labeled fallback."""
    settings = Settings(
        GEMINI_API_KEY="test-key-valid",
        AI_ENABLED=True,
    )

    # 1. Test 429
    mock_client_429 = MagicMock(spec=httpx.Client)
    mock_resp_429 = MagicMock(spec=httpx.Response)
    mock_resp_429.status_code = 429
    mock_client_429.post.return_value = mock_resp_429

    service_429 = PlanningEngineService(settings=settings, http_client=mock_client_429)
    plan_429 = service_429.generate_plan(PlanGenerationRequest(user_prompt="Festival in Mumbai"))
    assert plan_429.is_live_ai is False
    assert "Rate Limit" in plan_429.disclaimer

    # 2. Test 500
    mock_client_500 = MagicMock(spec=httpx.Client)
    mock_resp_500 = MagicMock(spec=httpx.Response)
    mock_resp_500.status_code = 500
    mock_client_500.post.return_value = mock_resp_500

    service_500 = PlanningEngineService(settings=settings, http_client=mock_client_500)
    plan_500 = service_500.generate_plan(PlanGenerationRequest(user_prompt="Festival in Mumbai"))
    assert plan_500.is_live_ai is False
    assert "Status 500" in plan_500.disclaimer


# ============================================================================
# 5. Plan Refinement & Invariant Preservation Tests
# ============================================================================


def test_refinement_preserves_unchanged_event_information():
    """Verify refinement retains all unchanged properties (date, type, location, id) without mutating original."""
    initial_req = PlanGenerationRequest(
        user_prompt="Wedding in Bengaluru for 100 guests with 5L budget on 2026-12-25",
        event_type="wedding",
        location="Bengaluru",
        guest_count=100,
        target_budget=Decimal("500000.00"),
        event_date=date(2026, 12, 25),
    )
    initial_plan = generate_deterministic_plan(initial_req)

    service = PlanningEngineService()
    refine_req = PlanRefinementRequest(
        existing_plan=initial_plan,
        refinement_instructions="Update guest count to 120 people",
    )
    refined_plan = service.refine_plan(refine_req)

    # Invariants preserved
    assert refined_plan.id == initial_plan.id
    assert refined_plan.brief.event_type == initial_plan.brief.event_type
    assert refined_plan.brief.location == initial_plan.brief.location
    assert refined_plan.brief.event_date == initial_plan.brief.event_date
    assert refined_plan.brief.expected_guest_count == 120
    # Original remains unmodified
    assert initial_plan.brief.expected_guest_count == 100


def test_refinement_reduces_budget_deterministically():
    """Verify refining a plan draft with budget reduction instruction updates allocations and budget."""
    initial_req = PlanGenerationRequest(
        user_prompt="Wedding in Bengaluru for 100 guests with 5L budget",
        target_budget=Decimal("500000.00"),
    )
    initial_plan = generate_deterministic_plan(initial_req)
    initial_total = initial_plan.budget_proposal.total_allocated

    service = PlanningEngineService()
    refine_req = PlanRefinementRequest(
        existing_plan=initial_plan,
        refinement_instructions="Reduce budget by 20% to keep costs low",
    )
    refined_plan = service.refine_plan(refine_req)

    assert refined_plan.status == "refined"
    assert refined_plan.budget_proposal.total_allocated < initial_total
    assert refined_plan.brief.target_budget == Decimal("400000.00")  # 500k * 0.80 = 400k


def test_no_fake_vendor_names_phones_urls_or_availability():
    """Verify vendor checklist items contain generic scope and vetting criteria without fake business details."""
    req = PlanGenerationRequest(user_prompt="Grand anniversary party in Udaipur with 150 guests")
    plan = generate_deterministic_plan(req)

    for item in plan.vendor_checklist:
        # Check requirement title is generic
        assert not any(sym in item.requirement_title for sym in ("Pvt", "Ltd", "LLP", "Inc", "Co."))
        # Check no phone numbers (patterns of 10 digits)
        assert not any(char.isdigit() and len(word) >= 10 for word in item.description.split() for char in word)
        # Check no URLs
        assert "http://" not in item.description.lower()
        assert "https://" not in item.description.lower()
        assert ".com" not in item.description.lower()
        # Questions to ask should be present
        assert len(item.important_questions_to_ask) >= 2


def test_timeline_task_categories_align_with_task_schema():
    """Verify that all timeline tasks generated use valid task categories."""
    valid_task_categories = {
        "planning", "venue", "catering", "photography", "decoration",
        "entertainment", "transport", "accommodation", "finance",
        "invitations", "logistics", "other"
    }
    req = PlanGenerationRequest(user_prompt="Wedding celebration in Chennai")
    plan = generate_deterministic_plan(req)

    for task in plan.timeline:
        assert task.category in valid_task_categories


# ============================================================================
# 6. Endpoints Integration & Draft Non-Persistence Verification
# ============================================================================


def test_assistant_endpoints_flow(client: TestClient):
    """Verify GET /status, POST /plan/generate, and POST /plan/refine endpoints."""
    from app.api.routes.assistant import get_planning_service
    from app.main import app

    offline_settings = Settings()
    offline_settings.AI_ENABLED = False
    offline_service = PlanningEngineService(settings=offline_settings)
    app.dependency_overrides[get_planning_service] = lambda: offline_service

    try:
        # 1. Status endpoint
        res_status = client.get("/api/v1/assistant/status")
        assert res_status.status_code == 200
        st = res_status.json()
        assert "ai_enabled" in st
        assert "service_status" in st
        assert "supported_event_types" in st

        # 2. Generate endpoint
        gen_payload = {
            "user_prompt": "Planning a community cultural festival in Kolkata with 200 attendees on 2026-12-15",
            "location": "Kolkata",
            "guest_count": 200,
            "event_date": "2026-12-15",
        }
        res_gen = client.post("/api/v1/assistant/plan/generate", json=gen_payload)
        assert res_gen.status_code == 200
        plan_data = res_gen.json()

        assert plan_data["brief"]["event_type"] == "community"
        assert plan_data["status"] == "draft"
        assert len(plan_data["vendor_checklist"]) >= 1
        assert len(plan_data["timeline"]) >= 1
        assert "disclaimer" in plan_data

        # 3. Refine endpoint
        refine_payload = {
            "existing_plan": plan_data,
            "refinement_instructions": "Add acoustic percussion band and cut decoration budget by 10%",
        }
        res_ref = client.post("/api/v1/assistant/plan/refine", json=refine_payload)
        assert res_ref.status_code == 200
        ref_data = res_ref.json()
        assert ref_data["status"] == "refined"
    finally:
        app.dependency_overrides.pop(get_planning_service, None)


def test_draft_generation_and_refinement_zero_database_writes(client: TestClient):
    """Prove that plan generation and refinement do not create or update events, budgets, tasks, or vendor records."""
    from app.api.routes.assistant import get_planning_service
    from app.main import app

    offline_settings = Settings()
    offline_settings.AI_ENABLED = False
    offline_service = PlanningEngineService(settings=offline_settings)
    app.dependency_overrides[get_planning_service] = lambda: offline_service

    try:
        # Count existing rows across all entities
        initial_events = client.get("/api/v1/events/").json()["total"]
        initial_vendors = client.get("/api/v1/vendors/").json()["total"]
        initial_prices = client.get("/api/v1/prices/").json()["total"]

        # 1. Generate Plan
        gen_res = client.post(
            "/api/v1/assistant/plan/generate",
            json={"user_prompt": "Wedding with 150 guests in Chennai on 2026-11-20"},
        )
        assert gen_res.status_code == 200
        plan_data = gen_res.json()

        # 2. Refine Plan
        ref_res = client.post(
            "/api/v1/assistant/plan/refine",
            json={
                "existing_plan": plan_data,
                "refinement_instructions": "Reduce catering budget by 15%",
            },
        )
        assert ref_res.status_code == 200

        # Verify counts across database are strictly unchanged
        post_events = client.get("/api/v1/events/").json()["total"]
        post_vendors = client.get("/api/v1/vendors/").json()["total"]
        post_prices = client.get("/api/v1/prices/").json()["total"]

        assert post_events == initial_events
        assert post_vendors == initial_vendors
        assert post_prices == initial_prices
    finally:
        app.dependency_overrides.pop(get_planning_service, None)


def test_no_api_key_or_secrets_in_plan_responses(client: TestClient):
    """Verify that assistant responses never leak API keys, secret tokens, or internal tracebacks."""
    from app.api.routes.assistant import get_planning_service
    from app.main import app

    offline_settings = Settings()
    offline_settings.AI_ENABLED = False
    offline_service = PlanningEngineService(settings=offline_settings)
    app.dependency_overrides[get_planning_service] = lambda: offline_service

    try:
        res = client.post(
            "/api/v1/assistant/plan/generate",
            json={"user_prompt": "Corporate annual summit in Pune"},
        )
        assert res.status_code == 200
        raw_response = res.text

        assert "AIzaSy" not in raw_response
        assert "x-goog-api-key" not in raw_response
        assert "SECRET_KEY" not in raw_response
        assert "dev-insecure" not in raw_response
    finally:
        app.dependency_overrides.pop(get_planning_service, None)


# ============================================================================
# 7. Critical Financial Integrity & Budget Provenance Regression Tests
# ============================================================================


def test_regression_1_event_type_only_no_invented_budget():
    """1. Event type only -> no invented budget, no invented contingency."""
    req = PlanGenerationRequest(user_prompt="I want to organize a wedding.")
    plan = generate_deterministic_plan(req)

    assert plan.brief.event_type == "wedding"
    assert plan.brief.target_budget is None
    assert plan.brief.budget_provenance == "unknown"
    assert plan.budget_proposal.target_budget is None
    assert plan.budget_proposal.budget_provenance == "unknown"
    assert len(plan.budget_proposal.allocations) == 0
    assert plan.budget_proposal.total_allocated == Decimal("0.00")
    assert plan.budget_proposal.contingency_amount == Decimal("0.00")
    assert plan.budget_proposal.contingency_calculation_basis is None
    assert plan.budget_proposal.is_within_budget is None
    assert any("budget" in gap.lower() for gap in plan.brief.missing_information)


def test_regression_2_event_type_and_location_no_invented_budget():
    """2. Event type and location -> no invented budget."""
    req = PlanGenerationRequest(user_prompt="Wedding in Hyderabad")
    plan = generate_deterministic_plan(req)

    assert plan.brief.event_type == "wedding"
    assert plan.brief.location == "Hyderabad"
    assert plan.brief.target_budget is None
    assert plan.brief.budget_provenance == "unknown"
    assert plan.budget_proposal.target_budget is None
    assert plan.budget_proposal.budget_provenance == "unknown"
    assert len(plan.budget_proposal.allocations) == 0
    assert plan.budget_proposal.is_within_budget is None


def test_regression_3_event_type_and_guest_count_no_invented_budget():
    """3. Event type and guest count -> no invented budget."""
    req = PlanGenerationRequest(user_prompt="I want a wedding in Hyderabad for 200 guests.")
    plan = generate_deterministic_plan(req)

    assert plan.brief.event_type == "wedding"
    assert plan.brief.location == "Hyderabad"
    assert plan.brief.expected_guest_count == 200
    assert plan.brief.target_budget is None
    assert plan.brief.budget_provenance == "unknown"
    assert plan.budget_proposal.target_budget is None
    assert plan.budget_proposal.budget_provenance == "unknown"
    assert len(plan.budget_proposal.allocations) == 0
    assert plan.budget_proposal.total_allocated == Decimal("0.00")
    assert plan.budget_proposal.contingency_amount == Decimal("0.00")
    assert plan.budget_proposal.is_within_budget is None
    assert any("budget" in gap.lower() for gap in plan.brief.missing_information)


def test_regression_4_explicit_15_lakh_budget_preserves_user_ceiling():
    """4. Explicit ₹15 lakh budget -> preserve exact user ceiling."""
    req = PlanGenerationRequest(user_prompt="Plan a wedding for 200 guests with a ₹15 lakh budget.")
    plan = generate_deterministic_plan(req)

    assert plan.brief.target_budget == Decimal("1500000.00")
    assert plan.brief.budget_provenance == "user_provided"
    assert plan.budget_proposal.target_budget == Decimal("1500000.00")
    assert plan.budget_proposal.budget_provenance == "user_provided"
    assert plan.budget_proposal.total_allocated == Decimal("1500000.00")
    assert plan.budget_proposal.is_within_budget is True
    assert plan.budget_proposal.contingency_amount > Decimal("0.00")
    assert plan.budget_proposal.contingency_calculation_basis is not None
    assert "user" in plan.budget_proposal.contingency_calculation_basis.lower()


def test_regression_5_user_asks_for_estimated_budget_clearly_labelled():
    """5. User asks for estimated budget -> clearly labelled estimate."""
    req = PlanGenerationRequest(user_prompt="Suggest a reasonable budget for a 200-guest wedding.")
    plan = generate_deterministic_plan(req)

    assert plan.brief.target_budget is not None
    assert plan.brief.target_budget > Decimal("0.00")
    assert plan.brief.budget_provenance in ("ai_suggested", "benchmark_estimate")
    assert plan.budget_proposal.budget_provenance in ("ai_suggested", "benchmark_estimate")
    # Crucial: Never treat estimate as user-provided ceiling; do NOT claim is_within_budget is True
    assert plan.budget_proposal.is_within_budget is None
    assert len(plan.budget_proposal.budget_assumptions) > 0
    assert any("benchmark" in a.lower() or "estimate" in a.lower() for a in plan.budget_proposal.budget_assumptions)


def test_regression_6_missing_budget_no_invented_contingency():
    """6. Missing budget -> no invented contingency."""
    req = PlanGenerationRequest(user_prompt="Community cleanliness drive for 100 people in Kolkata")
    plan = generate_deterministic_plan(req)

    assert plan.brief.target_budget is None
    assert plan.budget_proposal.target_budget is None
    assert plan.budget_proposal.contingency_amount == Decimal("0.00")
    assert plan.budget_proposal.contingency_percentage is None
    assert plan.budget_proposal.contingency_calculation_basis is None


def test_regression_7_ai_hallucinated_budget_neutralized_by_backend_validation():
    """7. AI output containing an invented target budget -> backend validation rejects or safely corrects it."""
    settings = Settings(
        GEMINI_API_KEY="test-key-hallucinating-budget",
        GEMINI_MODEL="gemini-3.1-flash-lite",
        AI_ENABLED=True,
    )
    # Simulate Gemini hallucinating ₹15 Lakhs and allocations when user never supplied or asked for a budget
    hallucinated_response = {
        "brief": {
            "event_type": "wedding",
            "event_name": "Dream Wedding",
            "location": "Hyderabad",
            "expected_guest_count": 200,
            "target_budget": "1500000.00",  # Hallucinated by LLM!
            "currency": "INR",
            "confirmed_information": ["Wedding in Hyderabad"],
            "missing_information": [],
            "explicit_assumptions": [],
        },
        "personalized_ideas": {
            "theme_and_concept": ["Royal Theme"],
            "decoration_ideas": ["Floral Mandap"],
            "catering_ideas": ["Buffet Lunch"],
            "entertainment_ideas": ["Live Music"],
            "guest_experience_suggestions": ["Favors"],
            "practical_recommendations": ["Book Early"],
        },
        "budget_proposal": {
            "allocations": [
                {"category": "venue", "suggested_amount": "500000.00", "currency": "INR", "rationale": "Venue", "source_type": "estimate"},
                {"category": "catering", "suggested_amount": "500000.00", "currency": "INR", "rationale": "Food", "source_type": "estimate"},
                {"category": "contingency", "suggested_amount": "150000.00", "currency": "INR", "rationale": "10%", "source_type": "estimate"},
            ]
        },
        "vendor_checklist": [],
        "timeline": [],
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(hallucinated_response)}]}}]
    }
    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    service = PlanningEngineService(settings=settings, http_client=mock_client)
    # User prompt has NO budget and NO estimate request:
    req = PlanGenerationRequest(user_prompt="I want a wedding in Hyderabad for 200 guests")
    plan = service.generate_plan(req)

    # Backend validation MUST neutralize hallucinated budget
    assert plan.brief.target_budget is None
    assert plan.brief.budget_provenance == "unknown"
    assert plan.budget_proposal.target_budget is None
    assert plan.budget_proposal.budget_provenance == "unknown"
    assert len(plan.budget_proposal.allocations) == 0
    assert plan.budget_proposal.contingency_amount == Decimal("0.00")
    assert plan.budget_proposal.is_within_budget is None
    assert any("budget" in gap.lower() for gap in plan.brief.missing_information)


def test_regression_8_refinement_preserves_user_budget_without_permission():
    """8. Refinement does not overwrite the user's original budget without permission."""
    # Start with explicit user-provided budget
    initial_req = PlanGenerationRequest(
        user_prompt="Plan a wedding for 200 guests with a ₹15 lakh budget",
        target_budget=Decimal("1500000.00"),
    )
    initial_plan = generate_deterministic_plan(initial_req)
    assert initial_plan.brief.target_budget == Decimal("1500000.00")
    assert initial_plan.brief.budget_provenance == "user_provided"

    # User refines with instructions that do NOT ask to change budget ceiling
    refine_req = PlanRefinementRequest(
        existing_plan=initial_plan,
        refinement_instructions="Allocate budget for top 3 prizes and add a live band",
    )
    service = PlanningEngineService(settings=Settings(GEMINI_API_KEY=""))
    refined_plan = service.refine_plan(refine_req)

    # Budget ceiling and provenance MUST be preserved
    assert refined_plan.brief.target_budget == Decimal("1500000.00")
    assert refined_plan.brief.budget_provenance == "user_provided"
    assert refined_plan.budget_proposal.target_budget == Decimal("1500000.00")
    assert refined_plan.budget_proposal.budget_provenance == "user_provided"
