"""Comprehensive Regression Test Suite for Stateful Conversational Discovery and Persistent Memory."""

from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.routes.assistant import get_conversation_service
from app.core.config import Settings
from app.main import app
from app.models.conversation import (
    ConversationMemory,
    ConversationMessage,
    ConversationSession,
)
from app.schemas.planning import (
    AssistantChatRequest,
    ConversationMemoryUpdateRequest,
)
from app.services.conversation_service import ConversationService
from app.services.planning_engine import PlanningEngineService


def _get_test_service() -> ConversationService:
    """Helper providing offline deterministic planning service for fast hermetic tests."""
    offline_settings = Settings()
    offline_settings.AI_ENABLED = False
    planning_svc = PlanningEngineService(settings=offline_settings)
    return ConversationService(planning_service=planning_svc)


class DirectTestClient:
    """In-process direct test client ensuring fast, hermetic, socketless test execution."""

    def __init__(self, db: Session, svc: ConversationService):
        self.db = db
        self.svc = svc

    def post(self, url: str, json: dict = None):
        class MockResponse:
            def __init__(self, status_code: int, data: dict):
                self.status_code = status_code
                self._data = data

            def json(self):
                return self._data

        if url == "/api/v1/assistant/chat":
            req = AssistantChatRequest(**(json or {}))
            res = self.svc.process_chat_message(self.db, req)
            return MockResponse(200, res.model_dump(mode="json"))
        elif "/memory/update" in url:
            parts = url.split("/")
            sid = parts[parts.index("sessions") + 1]
            req = ConversationMemoryUpdateRequest(**(json or {}))
            res = self.svc.update_memory_directly(self.db, sid, req)
            return MockResponse(200, res.model_dump(mode="json"))
        raise NotImplementedError(url)

    def get(self, url: str):
        class MockResponse:
            def __init__(self, status_code: int, data: dict):
                self.status_code = status_code
                self._data = data

            def json(self):
                return self._data

        if "/api/v1/assistant/sessions/" in url:
            sid = url.rstrip("/").split("/")[-1]
            res = self.svc.get_session_history(self.db, sid)
            return MockResponse(200, res.model_dump(mode="json"))
        raise NotImplementedError(url)


@pytest.fixture
def client(db_session: Session) -> DirectTestClient:
    """In-process direct test client ensuring fast, hermetic, socketless execution."""
    svc = _get_test_service()
    return DirectTestClient(db_session, svc)


def test_1_greeting_does_not_trigger_planning(client: TestClient):
    """Test: Vague greeting (hi/hello) responds with consultant greeting and does not generate a plan."""
    res = client.post("/api/v1/assistant/chat", json={"message": "hi"})
    assert res.status_code == 200
    data = res.json()

    assert data["session_id"] is not None
    assert data["reply_type"] == "greeting"
    assert data["structured_plan"] is None
    assert data["current_question"] is not None
    assert "What type of event" in data["current_question"]
    assert not data["memory"]["plan_generated"]
    assert data["memory"]["target_budget"] is None
    assert data["memory"]["budget_provenance"] == "unknown"


def test_2_vague_event_intent_starts_discovery(client: TestClient):
    """Test: Vague intent like 'I want to plan a get-together' starts discovery without generating a plan."""
    res = client.post("/api/v1/assistant/chat", json={"message": "I want to plan a get-together."})
    assert res.status_code == 200
    data = res.json()

    assert data["session_id"] is not None
    assert data["reply_type"] == "discovery_question"
    assert data["structured_plan"] is None
    assert not data["memory"]["plan_generated"]
    assert data["memory"]["event_type"] == "get-together"
    assert data["current_question"] is not None
    # Asks who is invited or what is the occasion
    assert "invite" in data["current_question"].lower() or "occasion" in data["current_question"].lower()


def test_3_one_question_is_asked_at_a_time(client: TestClient):
    """Test: Assistant asks exactly one targeted question per turn as information is collected."""
    # Turn 1: User says get-together
    res1 = client.post("/api/v1/assistant/chat", json={"message": "I want to plan a get-together."})
    session_id = res1.json()["session_id"]
    q1 = res1.json()["current_question"]
    assert q1 is not None
    assert res1.json()["structured_plan"] is None

    # Turn 2: User says college friends
    res2 = client.post("/api/v1/assistant/chat", json={"session_id": session_id, "message": "My college friends."})
    q2 = res2.json()["current_question"]
    assert q2 is not None
    assert "how many" in q2.lower()
    assert res2.json()["structured_plan"] is None

    # Turn 3: User says around 30
    res3 = client.post("/api/v1/assistant/chat", json={"session_id": session_id, "message": "Around 30."})
    q3 = res3.json()["current_question"]
    assert q3 is not None
    assert "where" in q3.lower() or "city" in q3.lower()
    assert res3.json()["structured_plan"] is None


def test_4_previously_supplied_details_are_remembered(client: TestClient, db_session: Session):
    """Test: Facts extracted across multiple turns are preserved in persistent memory."""
    # Turn 1
    res1 = client.post("/api/v1/assistant/chat", json={"message": "I want to plan a get-together."})
    sid = res1.json()["session_id"]

    # Turn 2
    client.post("/api/v1/assistant/chat", json={"session_id": sid, "message": "My college friends."})

    # Turn 3
    client.post("/api/v1/assistant/chat", json={"session_id": sid, "message": "Around 30 guests."})

    # Turn 4
    res4 = client.post("/api/v1/assistant/chat", json={"session_id": sid, "message": "In Hyderabad."})
    mem = res4.json()["memory"]

    assert mem["event_type"] == "get-together"
    assert "college friends" in mem["occasion"].lower()
    assert mem["expected_guest_count"] == 30
    assert mem["location"] == "Hyderabad"
    assert "event_type" in mem["confirmed_fields"]
    assert "expected_guest_count" in mem["confirmed_fields"]
    assert "location" in mem["confirmed_fields"]


def test_5_page_refresh_restores_conversation_context(client: TestClient):
    """Test: GET /sessions/{session_id} restores full chat messages and structured memory across reloads."""
    # Seed 3 turns
    res1 = client.post("/api/v1/assistant/chat", json={"message": "I want to plan a get-together."})
    sid = res1.json()["session_id"]
    client.post("/api/v1/assistant/chat", json={"session_id": sid, "message": "My college friends."})
    client.post("/api/v1/assistant/chat", json={"session_id": sid, "message": "Around 30."})

    # Simulate Page Refresh: fetch session history
    get_res = client.get(f"/api/v1/assistant/sessions/{sid}")
    assert get_res.status_code == 200
    session_data = get_res.json()

    assert session_data["session_id"] == sid
    # 3 user turns + 3 assistant responses = 6 messages
    assert len(session_data["messages"]) == 6
    assert session_data["memory"]["event_type"] == "get-together"
    assert session_data["memory"]["expected_guest_count"] == 30
    assert "college friends" in session_data["memory"]["occasion"].lower()


def test_6_corrected_facts_replace_old_facts(client: TestClient):
    """Test: User can correct previously stated facts (e.g. 50 guests instead of 30)."""
    res1 = client.post("/api/v1/assistant/chat", json={"message": "Planning a party in Bengaluru for 30 guests."})
    sid = res1.json()["session_id"]
    assert res1.json()["memory"]["expected_guest_count"] == 30

    # User corrects headcount
    res2 = client.post(
        "/api/v1/assistant/chat",
        json={"session_id": sid, "message": "Actually, make that 50 guests instead of 30."},
    )
    assert res2.json()["memory"]["expected_guest_count"] == 50
    # Location remains preserved
    assert res2.json()["memory"]["location"] == "Bengaluru"


def test_7_different_events_do_not_share_memory(client: TestClient):
    """Test: Separate sessions maintain isolated event contexts and memory."""
    # Event 1: Wedding in Goa for 150 guests
    res_a = client.post("/api/v1/assistant/chat", json={"message": "I want to plan a wedding in Goa for 150 guests."})
    sid_a = res_a.json()["session_id"]

    # Event 2: Tech conference in Delhi for 500 guests
    res_b = client.post("/api/v1/assistant/chat", json={"message": "Planning a tech conference in Delhi for 500 people."})
    sid_b = res_b.json()["session_id"]

    assert sid_a != sid_b

    # Verify session A
    get_a = client.get(f"/api/v1/assistant/sessions/{sid_a}").json()
    assert get_a["memory"]["event_type"] == "wedding"
    assert get_a["memory"]["location"] == "Goa"
    assert get_a["memory"]["expected_guest_count"] == 150

    # Verify session B
    get_b = client.get(f"/api/v1/assistant/sessions/{sid_b}").json()
    assert get_b["memory"]["event_type"] == "conference"
    assert get_b["memory"]["location"] == "Delhi"
    assert get_b["memory"]["expected_guest_count"] == 500


def test_8_missing_budget_remains_unknown(client: TestClient):
    """Test: Missing budget remains null/unknown and is not invented or defaulted."""
    res = client.post("/api/v1/assistant/chat", json={"message": "Plan a birthday party in Hyderabad for 25 people."})
    mem = res.json()["memory"]
    assert mem["target_budget"] is None
    assert mem["budget_provenance"] == "unknown"


def test_9_ai_estimates_are_not_treated_as_approved_budgets(client: TestClient):
    """Test: User asking for estimated budget labels it benchmark_estimate, not user_provided."""
    res1 = client.post("/api/v1/assistant/chat", json={"message": "Suggest a reasonable budget for a 200-guest wedding in Mumbai."})
    sid = res1.json()["session_id"]
    mem = res1.json()["memory"]
    assert mem["budget_provenance"] == "benchmark_estimate"


def test_10_explicit_plan_generation_requests_work(client: TestClient):
    """Test: When user explicitly requests a plan, the gate opens and structured plan is generated."""
    # Turn 1: discovery
    res1 = client.post("/api/v1/assistant/chat", json={"message": "I want to plan a get-together with college friends in Hyderabad for 30 people."})
    sid = res1.json()["session_id"]

    # Turn 2: User explicitly asks for plan
    res2 = client.post("/api/v1/assistant/chat", json={"session_id": sid, "message": "Please generate the plan now."})
    assert res2.status_code == 200
    data = res2.json()

    assert data["reply_type"] == "plan_generated"
    assert data["structured_plan"] is not None
    plan = data["structured_plan"]
    assert plan["brief"]["event_type"] == "get-together"
    assert plan["brief"]["expected_guest_count"] == 30
    assert plan["brief"]["location"] == "Hyderabad"
    assert len(plan["vendor_checklist"]) > 0
    assert len(plan["timeline"]) > 0
    assert data["memory"]["plan_generated"] is True


def test_11_memory_direct_update_endpoint(client: TestClient):
    """Test: Direct user corrections to memory via PATCH/POST."""
    res1 = client.post("/api/v1/assistant/chat", json={"message": "I want to plan a dinner party."})
    sid = res1.json()["session_id"]

    # Direct edit of location and guest count
    update_res = client.post(
        f"/api/v1/assistant/sessions/{sid}/memory/update",
        json={
            "location": "Jaipur",
            "expected_guest_count": 45,
            "target_budget": 50000.0,
            "budget_provenance": "user_provided",
            "venue_preferences": "Rooftop heritage haveli",
        },
    )
    assert update_res.status_code == 200
    updated_mem = update_res.json()

    assert updated_mem["location"] == "Jaipur"
    assert updated_mem["expected_guest_count"] == 45
    assert float(updated_mem["target_budget"]) == 50000.0
    assert updated_mem["budget_provenance"] == "user_provided"
    assert updated_mem["venue_preferences"] == "Rooftop heritage haveli"


def test_12_robotics_hackathon_natural_language_recognition(client: TestClient):
    """Test: 'I want to plan a small hackathon about robotics.' recognizes event_type, theme, scale, and asks for participant count."""
    res = client.post("/api/v1/assistant/chat", json={"message": "I want to plan a small hackathon about robotics."})
    assert res.status_code == 200
    data = res.json()

    # Event classification
    mem = data["memory"]
    assert mem["event_type"] == "hackathon"
    assert mem["theme"] == "Robotics"
    assert mem["scale"] == "small"

    # Unspecified fields remain null/unknown
    assert mem["expected_guest_count"] is None
    assert mem["location"] is None
    assert mem["event_date"] is None
    assert mem["target_budget"] is None
    assert mem["budget_provenance"] == "unknown"

    # Next question and prompt suggestions
    assert data["current_question"] == "How many participants are you expecting?"
    assert data["message"] == "That sounds like a robotics hackathon! Let's organize it. How many participants are you expecting?"
    assert data["suggested_prompts"] == [
        "50 participants",
        "One-day event",
        "College campus venue",
        "Team-based competition",
    ]


def test_13_custom_event_type_recognition(client: TestClient):
    """Test: Custom event classification works without schema failures."""
    res = client.post("/api/v1/assistant/chat", json={"message": "I want to organize a photography exhibition in Bengaluru."})
    assert res.status_code == 200
    data = res.json()

    mem = data["memory"]
    assert mem["event_type"] in ("photography-exhibition", "exhibition")
    assert mem["location"] == "Bengaluru"
    assert mem["expected_guest_count"] is None
    assert mem["target_budget"] is None


def test_14_get_together_with_crores_and_date(client: TestClient):
    """Test: 'i planned a get to gether in hyderabad on 3 november for 20 guests budget is 10 crores give me complete plan'
    correctly extracts event type, location, date, guest count, crore budget ceiling, and generates a plan without error.
    """
    msg = "i planned a get to gether in hyderabad on 3 november for 20 guests budget is 10 crores give me complete plan"
    res = client.post("/api/v1/assistant/chat", json={"message": msg})
    assert res.status_code == 200
    data = res.json()

    mem = data["memory"]
    assert mem["event_type"] == "get-together"
    assert mem["location"] == "Hyderabad"
    assert mem["expected_guest_count"] == 20
    assert "3 November" in mem["event_date"]
    assert mem["target_budget"] == "100000000.00"
    assert mem["budget_provenance"] == "user_provided"

    # Verifies complete plan was generated
    assert data["reply_type"] == "plan_generated"
    assert data["structured_plan"] is not None
    plan = data["structured_plan"]
    assert plan["brief"]["expected_guest_count"] == 20
    assert plan["brief"]["target_budget"] == "100000000"
    assert plan["budget_proposal"]["total_allocated"] == "100000000.00"
    assert plan["budget_proposal"]["budget_provenance"] == "user_provided"


