"""Backend Gemini AI Integration Service for EventPrice Intelligence.

Executes server-side requests to Google's Generative Language API using bounded timeouts,
safe error handling, sanitized logging, and deterministic fallback behavior.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import Settings, get_settings
from app.schemas.ai import AIEventAdviceResponse

logger = logging.getLogger("eventprice.gemini")

GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_INSTRUCTION = (
    "You are an elite, warm, and highly resourceful Event Planning Concierge for EventPrice Intelligence. "
    "Your role is to review an event plan that has already been mathematically balanced with verified vendors, "
    "phone numbers, and location details. "
    "Provide a friendly, personalized 2-3 paragraph response acknowledging the user's special event, "
    "highlighting key cost-saving and aesthetic tips, and reassuring them that their budget is completely under control. "
    "Keep the tone natural, encouraging, and structured with clear markdown bullet points."
)


def build_deterministic_fallback(
    event_name: str,
    location: str,
    guest_count: int,
    target_budget: Decimal,
    reason: str,
) -> str:
    """Deterministic fallback guidance when Gemini is unavailable or disabled."""
    formatted_budget = f"₹{target_budget:,.2f}" if target_budget else "Not specified"
    return (
        f"**Deterministic Event Planning Baseline**\n\n"
        f"• **Event**: {event_name or 'Special Event'}\n"
        f"• **Location**: {location or 'General'}\n"
        f"• **Estimated Guests**: {guest_count or 'TBD'}\n"
        f"• **Target Budget**: {formatted_budget}\n\n"
        f"Your event budget is mathematically balanced against verified category cost baselines. "
        f"All quotes and line items are locked to prevent cost overruns. "
        f"*(Note: Live AI advice unavailable [{reason}]. Deterministic ledger remains 100% active.)*"
    )


class GeminiService:
    """Service encapsulating secure server-side interactions with the Gemini API."""

    def __init__(self, settings: Optional[Settings] = None, http_client: Optional[httpx.Client] = None):
        self.settings = settings or get_settings()
        self._client = http_client

    def generate_event_advice(
        self,
        user_query: str,
        event_name: Optional[str] = None,
        location: Optional[str] = None,
        guest_count: Optional[int] = None,
        target_budget: Optional[Decimal] = None,
        category_summary: Optional[str] = None,
    ) -> AIEventAdviceResponse:
        """Query Gemini server-side with bounded timeouts and deterministic fallback."""
        event_name_str = event_name or "Event"
        location_str = location or "India"
        guest_count_int = guest_count or 100
        budget_decimal = target_budget or Decimal("0.00")

        # 1. Check if AI is enabled in configuration
        if not self.settings.AI_ENABLED:
            logger.info("AI functionality is disabled via AI_ENABLED=False configuration.")
            return AIEventAdviceResponse(
                success=False,
                advice=build_deterministic_fallback(
                    event_name_str, location_str, guest_count_int, budget_decimal, "AI Disabled in Settings"
                ),
                provider="deterministic_fallback",
                model=None,
                status="fallback_disabled",
            )

        # 2. Check if API key is configured
        api_key = self.settings.GEMINI_API_KEY
        if not api_key or not api_key.strip():
            logger.info("GEMINI_API_KEY is not configured on the backend server. Falling back to deterministic output.")
            return AIEventAdviceResponse(
                success=False,
                advice=build_deterministic_fallback(
                    event_name_str, location_str, guest_count_int, budget_decimal, "API Key Not Configured"
                ),
                provider="deterministic_fallback",
                model=None,
                status="fallback_missing_key",
            )

        # 3. Construct user prompt payload
        user_content = (
            f"Event Details:\n"
            f"- Name: {event_name_str}\n"
            f"- Location: {location_str}\n"
            f"- Guests: {guest_count_int} pax\n"
            f"- Target Budget: ₹{budget_decimal:,.2f}\n"
            f"- Allocated Categories: {category_summary or 'General allocations'}\n\n"
            f"User Request: \"{user_query}\"\n\n"
            f"Write a warm, natural, human-like response explicitly mentioning '{event_name_str}' and explaining how this plan fulfills their vision."
        )

        model = self.settings.GEMINI_MODEL
        url = GEMINI_API_ENDPOINT.format(model=model)

        request_body: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": f"{SYSTEM_INSTRUCTION}\n\n{user_content}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 800,
            },
        }

        # Secure headers: transmit key via header, NEVER in URL query params
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key.strip(),
        }

        timeout = httpx.Timeout(self.settings.GEMINI_TIMEOUT_SECONDS, connect=5.0)

        try:
            client = self._client or httpx.Client(timeout=timeout)
            response = client.post(url, json=request_body, headers=headers)

            if response.status_code == 429:
                logger.warning("Gemini rate limit exceeded (HTTP 429).")
                return AIEventAdviceResponse(
                    success=False,
                    advice=build_deterministic_fallback(
                        event_name_str, location_str, guest_count_int, budget_decimal, "Rate Limit Exceeded"
                    ),
                    provider="deterministic_fallback",
                    model=model,
                    status="fallback_rate_limited",
                )

            if response.status_code != 200:
                logger.warning(
                    "Gemini API returned non-success HTTP status %d: %s",
                    response.status_code,
                    response.text[:200],  # sanitized log
                )
                return AIEventAdviceResponse(
                    success=False,
                    advice=build_deterministic_fallback(
                        event_name_str, location_str, guest_count_int, budget_decimal, f"Provider Error (HTTP {response.status_code})"
                    ),
                    provider="deterministic_fallback",
                    model=model,
                    status="fallback_error",
                )

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                logger.warning("Gemini returned empty candidate list.")
                return AIEventAdviceResponse(
                    success=False,
                    advice=build_deterministic_fallback(
                        event_name_str, location_str, guest_count_int, budget_decimal, "Empty Provider Output"
                    ),
                    provider="deterministic_fallback",
                    model=model,
                    status="fallback_empty_response",
                )

            parts = candidates[0].get("content", {}).get("parts", [])
            advice_text = parts[0].get("text") if parts else None

            if not advice_text or not advice_text.strip():
                logger.warning("Gemini returned blank text in response parts.")
                return AIEventAdviceResponse(
                    success=False,
                    advice=build_deterministic_fallback(
                        event_name_str, location_str, guest_count_int, budget_decimal, "Blank Provider Text"
                    ),
                    provider="deterministic_fallback",
                    model=model,
                    status="fallback_empty_response",
                )

            logger.info("Successfully synthesized Gemini advice using model '%s'.", model)
            return AIEventAdviceResponse(
                success=True,
                advice=advice_text.strip(),
                provider="gemini",
                model=model,
                status="success",
            )

        except httpx.TimeoutException:
            logger.warning("Gemini API call timed out after %s seconds.", self.settings.GEMINI_TIMEOUT_SECONDS)
            return AIEventAdviceResponse(
                success=False,
                advice=build_deterministic_fallback(
                    event_name_str, location_str, guest_count_int, budget_decimal, "Request Timeout"
                ),
                provider="deterministic_fallback",
                model=model,
                status="fallback_timeout",
            )
        except Exception as exc:
            logger.error("Unexpected error invoking Gemini: %s", str(exc))
            return AIEventAdviceResponse(
                success=False,
                advice=build_deterministic_fallback(
                    event_name_str, location_str, guest_count_int, budget_decimal, "Internal Service Error"
                ),
                provider="deterministic_fallback",
                model=model,
                status="fallback_error",
            )

