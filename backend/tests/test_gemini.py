"""Automated tests for Backend Gemini AI Integration Service and Endpoints."""

from decimal import Decimal
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.models.budget import BudgetLineItem, EventBudget
from app.models.event import Event
from app.schemas.ai import AIEventAdviceRequest
from app.services.gemini_service import GeminiService


# ============================================================================
# Helpers
# ============================================================================


def create_test_event(client: TestClient, name: str = "Bengaluru AI Gala") -> dict:
    """Helper to create an event in the test database."""
    res = client.post(
        "/api/v1/events/",
        json={"name": name, "event_type": "gala", "city": "Bengaluru", "expected_attendees": 250},
    )
    assert res.status_code == 201
    return res.json()


# ============================================================================
# 1. Configuration & Missing Key / Disabled State Tests
# ============================================================================


def test_gemini_missing_api_key_returns_fallback():
    """Verify that if GEMINI_API_KEY is unset or empty, the service returns deterministic fallback without error."""
    settings = Settings(
        GEMINI_API_KEY=None,
        AI_ENABLED=True,
    )
    service = GeminiService(settings=settings)
    result = service.generate_event_advice(
        user_query="How can I optimize catering?",
        event_name="Product Launch",
        location="Mumbai",
        guest_count=150,
        target_budget=Decimal("500000.00"),
    )

    assert result.success is False
    assert result.provider == "deterministic_fallback"
    assert result.status == "fallback_missing_key"
    assert "API Key Not Configured" in result.advice
    assert result.model is None


def test_gemini_disabled_configuration_returns_fallback():
    """Verify that if AI_ENABLED is False, the service returns disabled fallback immediately."""
    settings = Settings(
        GEMINI_API_KEY="dummy-key-for-test",
        AI_ENABLED=False,
    )
    service = GeminiService(settings=settings)
    result = service.generate_event_advice(
        user_query="Give me theme ideas",
        event_name="Anniversary",
    )

    assert result.success is False
    assert result.provider == "deterministic_fallback"
    assert result.status == "fallback_disabled"
    assert "AI Disabled in Settings" in result.advice


# ============================================================================
# 2. Mocked Provider Success & Response Structure Tests
# ============================================================================


def test_gemini_successful_provider_response():
    """Verify successful synthesis from mocked Gemini REST API response."""
    settings = Settings(
        GEMINI_API_KEY="test-valid-key",
        GEMINI_MODEL="gemini-2.5-flash",
        AI_ENABLED=True,
    )

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": "Congratulations on planning the Bengaluru AI Gala! Here are 3 tips:\n- Tip 1\n- Tip 2\n- Tip 3"
                        }
                    ],
                    "role": "model",
                },
                "finishReason": "STOP",
            }
        ]
    }

    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = mock_gemini_response
    mock_client.post.return_value = mock_response

    service = GeminiService(settings=settings, http_client=mock_client)
    result = service.generate_event_advice(
        user_query="Make it elegant and cost effective",
        event_name="Bengaluru AI Gala",
        location="Bengaluru",
        guest_count=200,
        target_budget=Decimal("1000000.00"),
    )

    assert result.success is True
    assert result.provider == "gemini"
    assert result.model == "gemini-2.5-flash"
    assert result.status == "success"
    assert "Bengaluru AI Gala" in result.advice
    assert "Tip 1" in result.advice

    # Verify key was transmitted in header, not in URL
    call_args = mock_client.post.call_args
    assert call_args is not None
    called_url, called_kwargs = call_args[0][0], call_args[1]
    assert "key=" not in called_url
    assert called_kwargs["headers"]["x-goog-api-key"] == "test-valid-key"


# ============================================================================
# 3. Provider Error Handling & Rate Limiting Tests
# ============================================================================


def test_gemini_rate_limit_429_returns_graceful_fallback():
    """Verify that HTTP 429 returns fallback_rate_limited without throwing an unhandled exception."""
    settings = Settings(
        GEMINI_API_KEY="test-valid-key",
        GEMINI_MODEL="gemini-2.5-flash",
        AI_ENABLED=True,
    )

    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 429
    mock_response.text = "RESOURCE_EXHAUSTED: Rate limit exceeded"
    mock_client.post.return_value = mock_response

    service = GeminiService(settings=settings, http_client=mock_client)
    result = service.generate_event_advice(
        user_query="Plan music",
        event_name="Concert",
    )

    assert result.success is False
    assert result.provider == "deterministic_fallback"
    assert result.status == "fallback_rate_limited"
    assert "Rate Limit Exceeded" in result.advice


def test_gemini_provider_error_500_sanitizes_output():
    """Verify provider 500 error does not leak credentials or raw stack traces."""
    settings = Settings(
        GEMINI_API_KEY="test-valid-key",
        GEMINI_MODEL="gemini-2.5-flash",
        AI_ENABLED=True,
    )

    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error with sensitive stack trace"
    mock_client.post.return_value = mock_response

    service = GeminiService(settings=settings, http_client=mock_client)
    result = service.generate_event_advice(
        user_query="Plan lighting",
        event_name="Concert",
    )

    assert result.success is False
    assert result.provider == "deterministic_fallback"
    assert result.status == "fallback_error"
    assert "Provider Error (HTTP 500)" in result.advice
    assert "test-valid-key" not in result.advice


def test_gemini_timeout_handling():
    """Verify that network timeout returns fallback_timeout cleanly."""
    settings = Settings(
        GEMINI_API_KEY="test-valid-key",
        AI_ENABLED=True,
        GEMINI_TIMEOUT_SECONDS=2.0,
    )

    mock_client = MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = httpx.TimeoutException("Connection timed out after 2.0s")

    service = GeminiService(settings=settings, http_client=mock_client)
    result = service.generate_event_advice(
        user_query="Plan security",
        event_name="Summit",
    )

    assert result.success is False
    assert result.provider == "deterministic_fallback"
    assert result.status == "fallback_timeout"
    assert "Request Timeout" in result.advice


def test_gemini_empty_or_malformed_response():
    """Verify that blank or malformed candidate parts return fallback_empty_response."""
    settings = Settings(
        GEMINI_API_KEY="test-valid-key",
        AI_ENABLED=True,
    )

    mock_client = MagicMock(spec=httpx.Client)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "   "}]}}]}
    mock_client.post.return_value = mock_response

    service = GeminiService(settings=settings, http_client=mock_client)
    result = service.generate_event_advice(
        user_query="Check flowers",
        event_name="Wedding",
    )

    assert result.success is False
    assert result.provider == "deterministic_fallback"
    assert result.status == "fallback_empty_response"


# ============================================================================
# 4. Backend Endpoints Integration Tests
# ============================================================================


def test_adhoc_ai_advice_endpoint(client: TestClient):
    """Verify POST /api/v1/ai/event-advice executes and returns structured JSON response."""
    payload = {
        "user_query": "How to budget for 150 guests?",
        "event_name": "Tech Expo",
        "location": "Hyderabad",
        "guest_count": 150,
        "target_budget": 350000.0,
    }

    res = client.post("/api/v1/ai/event-advice", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert "success" in data
    assert "advice" in data
    assert "provider" in data
    assert "status" in data
    assert "disclaimer" in data
    # In test environment without GEMINI_API_KEY, fallback is cleanly returned
    assert data["provider"] in ("gemini", "deterministic_fallback")


def test_event_grounded_ai_advice_endpoint(client: TestClient):
    """Verify POST /api/v1/events/{event_id}/ai-advice reuses authoritative backend event details."""
    event = create_test_event(client, "Heritage Music Fest")
    event_id = event["id"]

    res = client.post(
        f"/api/v1/events/{event_id}/ai-advice",
        json={"user_query": "What are optimal stage configurations?"},
    )
    assert res.status_code == 200
    data = res.json()

    assert "advice" in data
    assert "Heritage Music Fest" in data["advice"]
    assert data["provider"] in ("gemini", "deterministic_fallback")


def test_event_ai_advice_404_for_nonexistent_event(client: TestClient):
    """Verify 404 for invalid event_id."""
    random_id = uuid.uuid4()
    res = client.post(
        f"/api/v1/events/{random_id}/ai-advice",
        json={"user_query": "Hello"},
    )
    assert res.status_code == 404


# ============================================================================
# 5. Frontend Cleanliness & Security Verification Tests
# ============================================================================


def test_frontend_has_no_raw_gemini_key_or_direct_google_calls():
    """Verify frontend code contains no VITE_GEMINI_API_KEY, localStorage key access, or direct Google calls."""
    root_dir = Path(__file__).resolve().parent.parent.parent

    # 1. Check geminiService.ts
    gemini_service_path = root_dir / "src" / "utils" / "geminiService.ts"
    assert gemini_service_path.exists(), "src/utils/geminiService.ts must exist"
    content = gemini_service_path.read_text(encoding="utf-8")

    assert "VITE_GEMINI_API_KEY" not in content, "Frontend must not reference VITE_GEMINI_API_KEY"
    assert "localStorage.getItem('gemini_api_key')" not in content, "Frontend must not access localStorage for API keys"
    assert "generativelanguage.googleapis.com" not in content, "Frontend must not call Google Generative Language directly"
    assert "/api/v1/ai/event-advice" in content, "Frontend must proxy to backend endpoint"

    # 2. Check root .env
    root_env_path = root_dir / ".env"
    if root_env_path.exists():
        env_content = root_env_path.read_text(encoding="utf-8")
        assert "VITE_GEMINI_API_KEY" not in env_content, "Root .env must not contain VITE_GEMINI_API_KEY"

    # 3. Check root .env.example
    root_example_path = root_dir / ".env.example"
    if root_example_path.exists():
        example_content = root_example_path.read_text(encoding="utf-8")
        assert "VITE_GEMINI_API_KEY=" not in example_content, "Root .env.example must not expose VITE_GEMINI_API_KEY placeholder"

