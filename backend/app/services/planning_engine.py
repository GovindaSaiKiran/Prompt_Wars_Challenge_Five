"""Structured GenAI Event Planning Engine.

Converts natural-language event concepts into structured, editable event plans.
Reuses the secure GeminiService infrastructure for LLM synthesis while strictly
enforcing that all financial totals, contingencies, and validations are computed
deterministically via Python Decimal arithmetic.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import Settings, get_settings
from app.schemas.planning import (
    AssistantStatusResponse,
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
from app.services.budget_engine import quantize_money, TWO_PLACES

logger = logging.getLogger("eventprice.planning_engine")

PLANNING_SYSTEM_INSTRUCTION = """You are the Senior GenAI Event Planning Engine for EventPrice Intelligence.
Your task is to convert the user's natural language event request into a comprehensive, highly realistic, and actionable structured event plan JSON.

Output Requirements:
1. Return strictly pure JSON matching the specified schema. Do not output markdown, explanations, or conversational filler outside the JSON.
2. Structure the plan into:
   - brief (event_type, event_name, location, expected_guest_count, event_date, target_budget, budget_provenance, currency, description, confirmed_information, missing_information, explicit_assumptions)
   - personalized_ideas (theme_and_concept, decoration_ideas, catering_ideas, entertainment_ideas, guest_experience_suggestions, practical_recommendations)
   - budget_proposal (allocations list: each with category, suggested_amount, currency, rationale, source_type; target_budget, budget_provenance, budget_assumptions, contingency_calculation_basis)
   - vendor_checklist (list: category, requirement_title, description, suggested_quantity_or_capacity, important_questions_to_ask, priority, selection_considerations)
   - timeline (list: task_title, description, category, priority, stage, relative_timing, dependencies, why_it_matters)
3. CRITICAL FINANCIAL INTEGRITY RULES — NEVER INVENT USER BUDGETS:
   - NEVER invent or assume a target budget ceiling.
   - If the user has NOT provided an explicit budget amount:
     * Set brief.target_budget to null.
     * Set brief.budget_provenance to "unknown".
     * Set budget_proposal.target_budget to null.
     * Set budget_proposal.budget_provenance to "unknown".
     * Set budget_proposal.allocations to empty [].
     * DO NOT invent a contingency buffer (contingency must be 0 with null calculation basis).
     * In brief.missing_information, explicitly list "Target budget ceiling (please specify your budget ceiling or request an AI-suggested estimate)".
   - If the user EXPLICITLY REQUESTS a suggested budget or estimate (e.g. "Suggest a reasonable budget for a 200-guest wedding", "estimate budget"):
     * Set brief.target_budget to the proposed realistic estimate.
     * Set brief.budget_provenance to "ai_suggested".
     * Set budget_proposal.target_budget to the proposed realistic estimate.
     * Set budget_proposal.budget_provenance to "ai_suggested".
     * Disclose all cost-per-guest and market tier assumptions in budget_proposal.budget_assumptions.
     * Clearly state in missing_information and alerts that this estimate requires explicit user approval.
     * Include an explicit calculation basis for contingency (e.g., "10% contingency calculated on AI-suggested estimate").
   - If the user PROVIDES an explicit budget ceiling (e.g. "Plan a wedding for 200 guests with a ₹15 lakh budget"):
     * Set brief.target_budget to that exact user amount.
     * Set brief.budget_provenance to "user_provided".
     * Set budget_proposal.target_budget to that exact amount.
     * Set budget_proposal.budget_provenance to "user_provided".
     * Propose category allocations that strictly fit within this user ceiling.
     * Include an explicit contingency calculation basis (e.g., "10% emergency reserve of user-provided ceiling").
   - NEVER convert an unknown budget into 0.
   - NEVER claim allocations are within a user's budget when none was provided.
4. Vendor Rules:
   - DO NOT invent real vendor business names, fake phone numbers, or fake URLs.
   - Describe requirements, quantities, vetting questions, and selection criteria generically.
5. Timeline Rules:
   - If an event_date is not provided, use relative stages ("Stage 1: 8-12 weeks out", etc.) and do NOT fabricate calendar dates.
"""


# ============================================================================
# Deterministic Financial Safeguards
# ============================================================================


def recalculate_and_validate_budget_proposal(
    proposal: PlanBudgetProposal,
    target_budget: Optional[Decimal] = None,
    currency: str = "INR",
    budget_provenance: Optional[str] = None,
    budget_assumptions: Optional[List[str]] = None,
) -> PlanBudgetProposal:
    """Enforces deterministic Python Decimal calculations for budget allocations.

    The LLM is NEVER trusted with authoritative financial math. All totals,
    contingencies, variances, and alerts are computed deterministically.
    """
    clean_currency = currency.strip().upper() if currency else "INR"
    alerts: List[str] = list(proposal.financial_alerts or [])
    clean_allocations: List[BudgetCategoryAllocation] = []

    total_allocated = Decimal("0.00")
    contingency_amount = Decimal("0.00")

    for item in proposal.allocations:
        item_curr = item.currency.strip().upper() if item.currency else clean_currency
        if item_curr != clean_currency:
            alerts.append(
                f"Currency mismatch detected in '{item.category}': expected {clean_currency}, got {item_curr}. Normalized to {clean_currency}."
            )

        # Reject negative amounts
        amount = item.suggested_amount
        if amount < Decimal("0.00"):
            alerts.append(f"Negative allocation detected for '{item.category}' ({clean_currency} {amount}). Reset to {clean_currency} 0.00.")
            amount = Decimal("0.00")

        amount = quantize_money(amount)
        total_allocated += amount

        if "contingency" in item.category.lower():
            contingency_amount += amount

        clean_allocations.append(
            BudgetCategoryAllocation(
                category=item.category,
                suggested_amount=amount,
                currency=clean_currency,
                rationale=item.rationale,
                source_type=item.source_type,
                tax_rate=item.tax_rate,
                tax_included=item.tax_included,
            )
        )

    # Determine resolved provenance & target budget
    resolved_target = quantize_money(target_budget) if target_budget is not None else proposal.target_budget
    if resolved_target is not None:
        resolved_target = quantize_money(resolved_target)

    if budget_provenance:
        prov = budget_provenance
    elif proposal.budget_provenance and proposal.budget_provenance != "unknown":
        prov = proposal.budget_provenance
    elif resolved_target is not None:
        prov = "user_provided"
    else:
        prov = "unknown"

    tax_policy = getattr(proposal, "tax_calculation_policy", "standard")
    if tax_policy not in ("standard", "inclusive", "exclusive"):
        tax_policy = "standard"

    contingency_pct = getattr(proposal, "contingency_percentage", None)
    contingency_basis = getattr(proposal, "contingency_calculation_basis", None)
    assumptions = list(budget_assumptions or proposal.budget_assumptions or [])

    remaining_budget: Optional[Decimal] = None
    variance_amount: Optional[Decimal] = None
    is_within_budget: Optional[bool] = None

    if prov == "unknown" or (resolved_target is None and prov not in ("benchmark_estimate", "ai_suggested")):
        prov = "unknown"
        resolved_target = None
        remaining_budget = None
        variance_amount = None
        is_within_budget = None
        contingency_amount = Decimal("0.00")
        contingency_pct = None
        contingency_basis = None
        if clean_allocations:
            alerts.append(
                f"No target budget ceiling specified. Allocations reflect initial illustrative planning assumptions in {clean_currency}."
            )
        else:
            alerts.append(
                "Target budget ceiling not provided. Budget allocation deferred until a budget ceiling is specified or an estimate is requested."
            )
    elif prov in ("ai_suggested", "benchmark_estimate"):
        is_within_budget = None
        if resolved_target is not None:
            remaining_budget = quantize_money(resolved_target - total_allocated)
            variance_amount = quantize_money(total_allocated - resolved_target)
            if contingency_amount > Decimal("0.00"):
                if contingency_pct is None and resolved_target > Decimal("0.00"):
                    contingency_pct = quantize_money((contingency_amount / resolved_target) * Decimal("100"))
                if not contingency_basis:
                    contingency_basis = f"Contingency calculated on {prov.replace('_', ' ')} total ({clean_currency} {resolved_target:,.2f})"
        alerts.append(
            f"{prov.replace('_', ' ').title()}: {clean_currency} {resolved_target:,.2f} is an unapproved planning estimate based on market benchmarks. Not a user-provided budget ceiling."
        )
    elif prov in ("user_provided", "user_approved"):
        if resolved_target is not None and resolved_target > Decimal("0.00"):
            remaining_budget = quantize_money(resolved_target - total_allocated)
            variance_amount = quantize_money(total_allocated - resolved_target)
            is_within_budget = total_allocated <= resolved_target
            if contingency_amount > Decimal("0.00"):
                if contingency_pct is None:
                    contingency_pct = quantize_money((contingency_amount / resolved_target) * Decimal("100"))
                if not contingency_basis:
                    contingency_basis = f"Contingency buffer calculated against user ceiling ({clean_currency} {resolved_target:,.2f})"

            if not is_within_budget:
                deficit = total_allocated - resolved_target
                alerts.append(
                    f"Budget Deficit: Proposed allocations total {clean_currency} {total_allocated:,.2f}, which exceeds target budget ({clean_currency} {resolved_target:,.2f}) by {clean_currency} {deficit:,.2f}."
                )
            elif remaining_budget > Decimal("0.00"):
                alerts.append(
                    f"Unallocated Buffer: {clean_currency} {remaining_budget:,.2f} remains available under your target budget ceiling."
                )
        else:
            prov = "unknown"
            resolved_target = None
            is_within_budget = None

    return PlanBudgetProposal(
        allocations=clean_allocations,
        total_allocated=total_allocated,
        target_budget=resolved_target,
        budget_provenance=prov,
        currency=clean_currency,
        remaining_budget=remaining_budget,
        variance_amount=variance_amount,
        contingency_amount=contingency_amount,
        contingency_percentage=contingency_pct,
        contingency_calculation_basis=contingency_basis,
        tax_calculation_policy=tax_policy,
        is_within_budget=is_within_budget,
        financial_alerts=alerts,
        budget_assumptions=assumptions,
        estimate_provenance_notice=(
            "All category budget figures are illustrative planning assumptions calculated deterministically. "
            "They are neither verified local market prices nor binding vendor quotes."
        ),
    )


# ============================================================================
# Heuristic Text Parser for Incomplete Inputs
# ============================================================================


def parse_prompt_intent(prompt: str) -> Dict[str, Any]:
    """Lightweight deterministic NLP parser extracting event parameters from conversational text."""
    lower = prompt.lower()

    # Detect event type
    event_type = "other"
    if any(w in lower for w in ("robotics competition", "robotics challenge", "robotics contest", "robotics tournament")):
        event_type = "robotics-competition"
    elif any(w in lower for w in ("hackathon", "codefest", "coding marathon", "buildathon", "ideathon")):
        event_type = "hackathon"
    elif any(w in lower for w in ("tech fest", "technical fest", "college tech fest", "college technical fest")):
        event_type = "tech-fest"
    elif any(w in lower for w in ("workshop", "bootcamp", "training session", "masterclass")):
        event_type = "workshop"
    elif any(w in lower for w in ("seminar", "webinar", "colloquium")):
        event_type = "seminar"
    elif any(w in lower for w in ("meetup", "user group meet", "developers meetup", "founders meetup")):
        event_type = "meetup"
    elif any(w in lower for w in ("networking event", "networking session", "business mixer")):
        event_type = "networking"
    elif any(w in lower for w in ("exhibition", "trade show", "product showcase", "art exhibition", "science fair")):
        event_type = "exhibition"
    elif any(w in lower for w in ("product launch", "launch party", "app launch")):
        event_type = "product-launch"
    elif any(w in lower for w in ("wedding", "shaadi", "marriage", "reception", "sangeet", "mehendi", "nikah")):
        event_type = "wedding"
    elif any(w in lower for w in ("birthday", "bday", "turning", "first birthday", "kids party")):
        event_type = "birthday"
    elif any(w in lower for w in ("get-together", "get together", "get to gether", "gettogether", "reunion", "hangout", "party with friends", "alumni meet")):
        event_type = "get-together"
    elif any(w in lower for w in ("community", "fundraiser", "charity", "ngo", "marathon", "festival", "diwali", "carnival")):
        event_type = "community"
    elif any(w in lower for w in ("conference", "summit", "symposium", "expo")):
        event_type = "conference"
    elif any(w in lower for w in ("anniversary", "jubilee", "milestone")):
        event_type = "anniversary"
    elif any(w in lower for w in ("corporate", "offsite", "team lunch", "company party", "townhall", "annual meet")):
        event_type = "corporate"

    # Detect guest count
    guest_count = None
    guest_match = re.search(r"(\d+)\s*(?:guests?|people|pax|attendees?|members?|persons?)", lower)
    if guest_match:
        try:
            guest_count = int(guest_match.group(1))
        except ValueError:
            pass

    # Detect estimate requested
    estimate_phrases = (
        "suggest a budget", "suggest budget", "reasonable budget", "estimate budget",
        "recommend budget", "recommend a budget", "what budget", "how much budget",
        "suggest a reasonable budget", "budget suggestion", "estimated budget",
        "give me a budget", "propose a budget", "budget estimate", "recommend an estimate"
    )
    estimate_requested = any(phrase in lower for phrase in estimate_phrases)

    # Detect budget
    budget = None
    # Check for formats like "10 crores", "10cr", "5 lakhs", "5L", "50k", "500000", "₹5,00,000"
    crore_match = re.search(r"(?:rs\.?|inr|₹|budget\s+is\s+|budget\s+of\s+)?\s*(\d+(?:\.\d+)?)\s*(?:crores?|cr)\b", lower)
    if crore_match:
        try:
            budget = Decimal(crore_match.group(1)) * Decimal("10000000")
        except Exception:
            pass
    if budget is None:
        lakh_match = re.search(r"(?:rs\.?|inr|₹|budget\s+is\s+|budget\s+of\s+)?\s*(\d+(?:\.\d+)?)\s*(?:lakhs?|lac|l)\b", lower)
        if lakh_match:
            try:
                budget = Decimal(lakh_match.group(1)) * Decimal("100000")
            except Exception:
                pass
    if budget is None:
        k_match = re.search(r"(?:rs\.?|inr|₹|budget\s+is\s+|budget\s+of\s+)?\s*(\d+(?:\.\d+)?)\s*(?:k|thousand)\b", lower)
        if k_match:
            try:
                budget = Decimal(k_match.group(1)) * Decimal("1000")
            except Exception:
                pass
    if budget is None:
        raw_match = re.search(r"(?:rs\.?|inr|₹|budget\s+is\s+|budget\s+of\s+)\s*(\d[\d,]+)", lower)
        if raw_match:
            try:
                cleaned_val = raw_match.group(1).replace(",", "")
                budget = Decimal(cleaned_val)
            except Exception:
                pass

    # Determine budget provenance
    if budget is not None:
        budget_provenance = "user_provided"
        estimate_requested = False
    elif estimate_requested:
        budget_provenance = "benchmark_estimate"
    else:
        budget_provenance = "unknown"

    # Detect location
    location = None
    cities = [
        "bengaluru", "bangalore", "mumbai", "delhi", "goa", "hyderabad",
        "chennai", "kolkata", "pune", "jaipur", "udaipur", "ahmedabad", "kerala"
    ]
    for c in cities:
        if c in lower:
            location = c.title()
            if location == "Bangalore":
                location = "Bengaluru"
            break

    return {
        "event_type": event_type,
        "guest_count": guest_count,
        "target_budget": budget,
        "budget_provenance": budget_provenance,
        "estimate_requested": estimate_requested,
        "location": location,
    }


# ============================================================================
# Deterministic Rule-Based Fallback Planner
# ============================================================================


def generate_deterministic_plan(
    request: PlanGenerationRequest,
    reason: str = "Deterministic Rule-Based Baseline",
) -> GeneratedEventPlan:
    """Generates a complete, high-quality, structured plan draft without calling an LLM.

    Guarantees 100% reliable responses during offline mode, missing API keys, or provider outages.
    """
    inferred = parse_prompt_intent(request.user_prompt)

    event_type = request.event_type or inferred["event_type"]
    guest_count = request.guest_count or inferred["guest_count"] or (200 if event_type == "wedding" else 50 if event_type == "birthday" else 150)
    location = request.location or inferred["location"] or "Bengaluru"
    currency = request.currency or "INR"

    # Target budget resolution
    explicit_budget = request.target_budget or inferred["target_budget"]
    estimate_requested = inferred.get("estimate_requested", False)

    budget_assumptions: List[str] = []
    contingency_basis: Optional[str] = None
    contingency_percentage: Optional[Decimal] = None

    if explicit_budget is not None:
        target_budget = Decimal(str(explicit_budget))
        budget_provenance = "user_provided"
        contingency_percentage = Decimal("10.00")
        contingency_basis = f"10% emergency buffer based on user-provided budget ceiling ({currency} {target_budget:,.2f})"
    elif estimate_requested:
        # Benchmark defaults per guest ONLY when user explicitly asked for estimate
        per_guest = 4000 if event_type == "wedding" else 1200 if event_type == "birthday" else 500
        target_budget = Decimal(str(guest_count * per_guest))
        budget_provenance = "benchmark_estimate"
        contingency_percentage = Decimal("10.00")
        contingency_basis = f"10% emergency buffer based on {event_type} benchmark estimate ({currency} {target_budget:,.2f})"
        budget_assumptions = [
            f"Illustrative market benchmark of {currency} {per_guest:,.2f} per guest for {event_type} events",
            f"Estimated benchmark total for {guest_count} guests: {currency} {target_budget:,.2f}",
            "10% emergency contingency allocation included in estimate",
            "This estimate is unapproved and requires explicit client confirmation",
        ]
    else:
        target_budget = None
        budget_provenance = "unknown"
        contingency_percentage = None
        contingency_basis = None

    event_name = request.event_name or f"{location} {event_type.title()} Celebration"
    event_date = request.event_date

    # 1. Brief
    confirmed = [f"Event format: {event_type.title()}"]
    if request.location or inferred["location"]:
        confirmed.append(f"Destination: {location}")
    if request.guest_count or inferred["guest_count"]:
        confirmed.append(f"Guest count: {guest_count} attendees")
    if budget_provenance == "user_provided" and target_budget is not None:
        confirmed.append(f"User budget ceiling: {currency} {target_budget:,.2f}")
    elif budget_provenance == "benchmark_estimate" and target_budget is not None:
        confirmed.append(f"AI-suggested benchmark estimate: {currency} {target_budget:,.2f} (unapproved)")
    if event_date:
        confirmed.append(f"Event date: {event_date.isoformat()}")

    if request.external_weather and request.external_weather.risk_assessment:
        w_risk = request.external_weather.risk_assessment
        confirmed.append(f"Weather Risk: {w_risk.overall_risk.value.upper()} (Outdoor suitable: {w_risk.is_outdoor_suitable})")

    if request.nearby_places:
        top_places = [p.name for p in request.nearby_places[:3]]
        confirmed.append(f"Nearby Landmarks: {', '.join(top_places)}")

    missing = []
    if not event_date:
        missing.append("Exact calendar event date (staged planning applied)")
    if not request.location and not inferred["location"]:
        missing.append("Confirmed venue address or preferred locality")
    if budget_provenance == "unknown":
        missing.append("Target budget ceiling (specify your budget ceiling or request an AI-suggested estimate)")

    assumptions = [
        f"Assumed guest count of {guest_count} attendees for capacity and catering sizing",
        "Assumed standard 18% GST applicable on commercial catering, decor, and AV equipment",
    ]
    if contingency_basis:
        assumptions.append(contingency_basis)

    brief = PlanEventBrief(
        event_type=event_type,
        event_name=event_name,
        location=location,
        expected_guest_count=guest_count,
        event_date=event_date,
        target_budget=target_budget,
        budget_provenance=budget_provenance,
        currency=currency,
        description=request.user_prompt,
        confirmed_information=confirmed,
        missing_information=missing,
        explicit_assumptions=assumptions,
    )

    # 2. Personalized Ideas based on Event Type
    if event_type == "wedding":
        ideas = PlanPersonalizedIdeas(
            theme_and_concept=[
                "Royal Heritage with Contemporary Botanical Elements",
                "Warm Sunset Brass & Marigold Palette",
                "Sustainable Zero-Waste Wedding Concept",
            ],
            decoration_ideas=[
                "Mogra & Marigold floral canopies with fairy light mesh ceiling",
                "Minimalist wooden mandap with fresh foliage and brass bell accents",
                "Custom photo booth inspired by traditional jharokhas",
            ],
            catering_ideas=[
                "Regional fusion live food stations (Chaat counter, artisanal Dosa bar, Live Woodfired Pizza)",
                "Traditional banana-leaf seated lunch paired with evening modern fusion buffet",
                "Signature welcome drinks (Tender Coconut with mint, Mango Panna spritzers)",
            ],
            entertainment_ideas=[
                "Acoustic instrumental fusion band for welcome reception",
                "Live DJ with percussionist for evening Sangeet / party",
                "Folk dance troupe for cultural entryway welcome",
            ],
            guest_experience_suggestions=[
                "Custom welcome bags with regional sweets and herbal hydration kits",
                "Live Polaroid guestbook station for instant keepsake messages",
                "Dedicated comfort lounge with footwear station (juttis/slippers for dancing)",
            ],
            practical_recommendations=[
                f"Book venue in {location} at least 4-6 months early to secure peak wedding dates",
                "Verify indoor air-conditioned backup hall in case of sudden weather shifts",
                "Conduct mandatory food and sound tastings before signing vendor contracts",
            ],
        )
    elif event_type == "birthday":
        ideas = PlanPersonalizedIdeas(
            theme_and_concept=[
                "Retro Arcade & Neon Glow Extravaganza",
                "Enchanted Pastel Garden Picnic",
                "Classic Vintage Hollywood Red Carpet",
            ],
            decoration_ideas=[
                "Custom organic balloon garland arch with customized neon signage",
                "Themed dessert table backdrop with dynamic LED uplighting",
                "Color-coordinated table runners and interactive photo wall",
            ],
            catering_ideas=[
                "Interactive live sliders and gourmet mini-burgers counter",
                "Custom multi-tiered fondant birthday cake with matching cupcakes",
                "Mocktail bar featuring smoking dry-ice drinks and boba tea",
            ],
            entertainment_ideas=[
                "Professional emcee host conducting interactive team games and quizzes",
                "Live close-up illusionist / mentalist performance",
                "Curated party playlist with sound and laser light package",
            ],
            guest_experience_suggestions=[
                "Customized takeaway gift boxes with personalized artisanal treats",
                "Digital caricature artist providing instant phone-compatible portraits",
                "360-degree video booth with instant social sharing",
            ],
            practical_recommendations=[
                "Schedule main cake-cutting 90 minutes after arrival to keep energy high",
                "Confirm sound decibel limits with the venue if booking an outdoor lawn",
                "Prepare a locked storage room for guest gifts and personal belongings",
            ],
        )
    else:  # Community / Conference / Generic
        ideas = PlanPersonalizedIdeas(
            theme_and_concept=[
                "Community Connect: Celebrating Shared Heritage & Unity",
                "Eco-Conscious Green Gathering with Zero Plastic Footprint",
                "Vibrant Cultural Carnival & Artisan Marketplace",
            ],
            decoration_ideas=[
                "Upcycled fabric drapes and eco-friendly terracotta signage",
                "Bunting flags and warm festoon lighting across open lawns",
                "Modular branded stage backdrop with dual LED visual screens",
            ],
            catering_ideas=[
                "Wholesome multi-regional buffet with vegetarian and vegan highlights",
                "All-day tea, South Indian filter coffee, and local snack stations",
                "Refillable glass water dispenser stations throughout the venue",
            ],
            entertainment_ideas=[
                "Community open-mic and youth acoustic musical showcase",
                "Interactive cultural percussion drum-circle workshop",
                "Closing awards and volunteer appreciation ceremony",
            ],
            guest_experience_suggestions=[
                "Seed paper badges and welcome plantable sapling giveaways",
                "Interactive community art canvas where every attendee contributes",
                "Accessible priority seating zone and volunteer helpdesk",
            ],
            practical_recommendations=[
                f"Ensure municipal permissions, sound permits, and fire NOC are secured in {location}",
                "Provide dedicated parking management with volunteer traffic marshals",
                "Set up an on-site first-aid tent with an emergency medical kit",
            ],
        )

    # Append weather recommendations if available
    if request.external_weather and request.external_weather.risk_assessment:
        for rec in request.external_weather.risk_assessment.recommendations:
            ideas.practical_recommendations.append(f"Meteorological Advisory: {rec}")

    # 3. Budget Proposal (Category Benchmarks)
    raw_allocations = []
    if target_budget is not None:
        if event_type == "wedding":
            alloc_specs = [
                ("venue", Decimal("0.25"), "Banquet hall / lawn rental and basic venue infrastructure"),
                ("catering", Decimal("0.35"), f"Buffet catering and welcome drinks for {guest_count} guests"),
                ("decoration", Decimal("0.15"), "Mandap, floral styling, entryway, and ambient lighting"),
                ("photography", Decimal("0.10"), "Candid photo, cinematic videography, and drone footage"),
                ("entertainment", Decimal("0.05"), "DJ setup, sound system, and live acoustic performance"),
                ("contingency", Decimal("0.10"), "10% emergency buffer for last-minute headcount adjustments"),
            ]
        elif event_type == "birthday":
            alloc_specs = [
                ("venue", Decimal("0.20"), "Party hall or private dining venue rental"),
                ("catering", Decimal("0.40"), f"Party snacks, buffet, and custom cake for {guest_count} guests"),
                ("decoration", Decimal("0.15"), "Theme styling, balloon installations, and photo backdrop"),
                ("entertainment", Decimal("0.10"), "Emcee, party games, music system, and magician"),
                ("photography", Decimal("0.05"), "Event photographer coverage for 3-4 hours"),
                ("contingency", Decimal("0.10"), "10% reserve for extra plates and overtime"),
            ]
        else:
            alloc_specs = [
                ("venue", Decimal("0.20"), "Community ground / hall rental and civic permits"),
                ("catering", Decimal("0.30"), f"Refreshments and boxed meals for {guest_count} attendees"),
                ("logistics", Decimal("0.20"), "Stage, PA sound system, chairs, and generator backup"),
                ("decoration", Decimal("0.10"), "Banners, wayfinding signage, and eco-friendly drapes"),
                ("contingency", Decimal("0.20"), "Emergency buffer and municipal compliance reserve"),
            ]

        for cat, pct, rat in alloc_specs:
            alloc_amt = quantize_money(target_budget * pct)
            raw_allocations.append(
                BudgetCategoryAllocation(
                    category=cat,
                    suggested_amount=alloc_amt,
                    currency=currency,
                    rationale=rat,
                    source_type="user_provided" if budget_provenance == "user_provided" else "benchmark_estimate",
                )
            )

    budget_prop = recalculate_and_validate_budget_proposal(
        PlanBudgetProposal(
            allocations=raw_allocations,
            currency=currency,
            contingency_percentage=contingency_percentage,
            contingency_calculation_basis=contingency_basis,
            budget_assumptions=budget_assumptions,
        ),
        target_budget=target_budget,
        currency=currency,
        budget_provenance=budget_provenance,
        budget_assumptions=budget_assumptions,
    )

    # 4. Vendor Checklist
    checklist = [
        VendorChecklistItem(
            category="venue",
            requirement_title=f"{event_type.title()} Venue Booking",
            description=f"Securing suitable space in {location} accommodating at least {guest_count} guests.",
            suggested_quantity_or_capacity=f"Capacity: {guest_count} - {int(guest_count * 1.25)} pax",
            important_questions_to_ask=[
                "What is the exact rental duration and policy on vendor setup hours?",
                "Are in-house catering and decor mandatory or are outside vendors permitted?",
                "Is diesel generator (DG) power backup included in the hall rental?",
            ],
            priority="critical",
            selection_considerations=["Parking capacity", "Restroom hygiene", "Noise curfew rules"],
        ),
        VendorChecklistItem(
            category="catering",
            requirement_title=f"Food & Beverage Service ({guest_count} pax)",
            description=f"Appetizers, main course, desserts, and beverage service for {guest_count} attendees.",
            suggested_quantity_or_capacity=f"{guest_count} plates + 10% buffer",
            important_questions_to_ask=[
                "Can you conduct an in-person tasting session for 2-3 key menu dishes?",
                "What is your ratio of service staff to guest count?",
                "Are water bottles, cutlery, chaffing dishes, and dustbins included in the plate price?",
            ],
            priority="critical",
            selection_considerations=["FSSAI food hygiene certification", "Taste consistency", "Warm food replenishment"],
        ),
        VendorChecklistItem(
            category="decoration",
            requirement_title="Theme Floral & Ambient Lighting Setup",
            description="Stage backdrop, entryway arch, table centerpieces, and warm wash lighting.",
            suggested_quantity_or_capacity="Full hall / venue coverage",
            important_questions_to_ask=[
                "Do you provide a 3D visual render or moodboard prior to production?",
                "What type of flowers are used (fresh seasonal vs. artificial blends)?",
                "How many hours do you require for setup and teardown?",
            ],
            priority="high",
            selection_considerations=["Portfolio of past similar events", "Structural safety of trusses", "Punctuality"],
        ),
        VendorChecklistItem(
            category="photography",
            requirement_title="Photo & Video Coverage",
            description="Capturing key milestones, guest portraits, and cinematic highlight reel.",
            suggested_quantity_or_capacity="2 photographers + 1 videographer",
            important_questions_to_ask=[
                "What is your delivery timeline for edited photos and final video teaser?",
                "Are candid photography and drone permissions included?",
                "Do you provide raw untouched footage backups?",
            ],
            priority="medium",
            selection_considerations=["Editing color grading style", "Experience with event lighting", "Backup camera gear"],
        ),
    ]

    # 5. Timeline with Staged Tasks
    timeline_stages = [
        ("Finalize Venue Contract & Date", "Lock down venue booking with advance deposit and confirm timings.", "venue", "critical", "early_planning", -60, "Stage 1 (8-10 weeks prior)", []),
        ("Book Core Catering & Menu Tasting", "Review sample tasting, finalize menu items, and agree on plate count.", "catering", "high", "early_planning", -45, "Stage 2 (6-8 weeks prior)", ["Finalize Venue Contract & Date"]),
        ("Confirm Theme Styling & Decor Package", "Approve moodboard, lighting plan, and floral installations.", "decoration", "high", "vendor_booking", -30, "Stage 3 (4-5 weeks prior)", ["Finalize Venue Contract & Date"]),
        ("Send Invitations & Track RSVPs", "Distribute digital and printed invitations with Google Maps venue location.", "invitations", "medium", "final_prep", -21, "Stage 4 (3 weeks prior)", ["Finalize Venue Contract & Date"]),
        ("Final Headcount & Vendor Briefing", "Reconfirm final plate count with caterer and setup sequence with sound vendor.", "logistics", "critical", "event_week", -3, "Stage 5 (3 days prior)", ["Book Core Catering & Menu Tasting"]),
        ("On-Site Event Execution & Wrap-Up", "Oversee vendor arrival, manage timeline schedule, and settle vendor balances.", "logistics", "critical", "day_of_event", 0, "Stage 6 (Day of Event)", ["Final Headcount & Vendor Briefing"]),
    ]

    timeline_items = []
    for title, desc, cat, prio, stage, day_offset, rel_str, deps in timeline_stages:
        due_d = None
        if event_date is not None:
            due_d = event_date + timedelta(days=day_offset)

        timeline_items.append(
            PlanTimelineTask(
                task_title=title,
                description=desc,
                category=cat,
                priority=prio,
                stage=stage,
                suggested_due_date=due_d,
                relative_timing=rel_str,
                dependencies=deps,
                why_it_matters=f"Ensures {cat} deliverables remain on schedule and avoids last-minute rush.",
            )
        )

    return GeneratedEventPlan(
        brief=brief,
        personalized_ideas=ideas,
        budget_proposal=budget_prop,
        vendor_checklist=checklist,
        timeline=timeline_items,
        provider="deterministic_fallback",
        model=None,
        is_live_ai=False,
        status="draft",
        disclaimer=(
            f"Note: Generated using EventPrice Deterministic Planning Engine ({reason}). "
            "All category allocations and checklists are unapproved drafts. "
            "No database records or financial commitments have been made."
        ),
    )


# ============================================================================
# Gemini Service Integration (Structured JSON Mode)
# ============================================================================


class PlanningEngineService:
    """Orchestrates structured plan generation and refinement using Gemini with deterministic safety."""

    def __init__(self, settings: Optional[Settings] = None, http_client: Optional[httpx.Client] = None):
        self.settings = settings or get_settings()
        self._client = http_client

    def get_status(self) -> AssistantStatusResponse:
        """Returns assistant operational status."""
        has_key = bool(self.settings.GEMINI_API_KEY and self.settings.GEMINI_API_KEY.strip())
        is_ready_live = self.settings.AI_ENABLED and has_key

        return AssistantStatusResponse(
            ai_enabled=self.settings.AI_ENABLED,
            ai_provider=self.settings.AI_PROVIDER,
            configured_model=self.settings.GEMINI_MODEL,
            is_live_key_configured=has_key,
            service_status="ready_live" if is_ready_live else "ready_fallback" if self.settings.AI_ENABLED else "disabled",
            supported_event_types=["wedding", "birthday", "community", "corporate", "conference", "anniversary", "other"],
            disclaimer="Assistant generates draft plans. Financial arithmetic is verified deterministically by the backend.",
        )

    def generate_plan(self, request: PlanGenerationRequest) -> GeneratedEventPlan:
        """Generates a structured plan from user prompt, falling back deterministically if needed."""
        # Check if AI is enabled and key is present
        if not self.settings.AI_ENABLED:
            logger.info("AI disabled in configuration; using deterministic planning engine.")
            return generate_deterministic_plan(request, reason="AI Disabled in Settings")

        api_key = self.settings.GEMINI_API_KEY
        if not api_key or not api_key.strip():
            logger.info("GEMINI_API_KEY not set; using deterministic planning engine.")
            return generate_deterministic_plan(request, reason="Live Key Unset — Deterministic Baseline")

        # Build prompt for Gemini structured JSON output
        external_context_lines = []
        if request.external_weather:
            w = request.external_weather
            meas_str = "None"
            if w.measurements:
                meas_str = f"Temp: {w.measurements.temperature_c}°C, Humidity: {w.measurements.humidity_pct}%, Wind: {w.measurements.wind_speed_mps} m/s, Rain: {w.measurements.rainfall_mm}mm, Condition: {w.measurements.weather_condition}"
            risk_str = "None"
            if w.risk_assessment:
                risk_str = f"Risk Level: {w.risk_assessment.overall_risk.value.upper()}, Outdoor Suitable: {w.risk_assessment.is_outdoor_suitable}, Recommendations: {'; '.join(w.risk_assessment.recommendations)}"
            external_context_lines.append(
                f"- Verified Real Weather ({w.provider}): Classification={w.classification.value}, Measurements=[{meas_str}], Risk Evaluation=[{risk_str}]"
            )
        if request.nearby_places:
            places_summary = [f"{p.name} ({p.category}, ~{p.distance_meters:.0f}m away)" for p in request.nearby_places[:5]]
            external_context_lines.append(
                f"- Real OpenStreetMap Venues Nearby: {'; '.join(places_summary)}"
            )

        external_section = ""
        if external_context_lines:
            external_section = (
                "\nVerified External Geographic & Meteorological Intelligence:\n"
                + "\n".join(external_context_lines)
                + "\nImportant: Ground your practical recommendations and contingency allocations in these real weather risks and nearby facilities. Do NOT invent fake commercial pricing or fake vendor URLs.\n"
            )

        user_spec = (
            f"Event Request:\n\"{request.user_prompt}\"\n\n"
            f"Optional Structured Brief Overrides:\n"
            f"- Event Type: {request.event_type or 'Infer from prompt'}\n"
            f"- Event Name: {request.event_name or 'Infer from prompt'}\n"
            f"- Location: {request.location or 'Infer from prompt'}\n"
            f"- Guest Count: {request.guest_count or 'Infer from prompt'}\n"
            f"- Target Budget: {f'₹{request.target_budget:,.2f}' if request.target_budget else 'Infer from prompt'}\n"
            f"- Event Date: {request.event_date.isoformat() if request.event_date else 'None provided (use relative stages)'}\n"
            f"{external_section}\n"
            f"Generate a comprehensive, structured plan JSON adhering strictly to the required schema."
        )

        model = self.settings.GEMINI_MODEL
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        request_body = {
            "contents": [
                {
                    "parts": [{"text": f"{PLANNING_SYSTEM_INSTRUCTION}\n\n{user_spec}"}],
                }
            ],
            "generationConfig": {
                "temperature": 0.3,  # lower temperature for reliable structural compliance
                "responseMimeType": "application/json",
                "maxOutputTokens": 4096,
            },
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key.strip(),
        }

        timeout = httpx.Timeout(self.settings.GEMINI_TIMEOUT_SECONDS, connect=5.0)

        try:
            client = self._client or httpx.Client(timeout=timeout)
            response = client.post(url, json=request_body, headers=headers)

            if response.status_code == 429:
                logger.warning("Gemini API rate limited (HTTP 429). Falling back to deterministic plan.")
                return generate_deterministic_plan(
                    request, reason="Gemini Rate Limit (HTTP 429)"
                )

            if response.status_code != 200:
                logger.warning(
                    "Gemini API returned status %d. Falling back to deterministic plan.",
                    response.status_code,
                )
                return generate_deterministic_plan(
                    request, reason=f"Gemini Provider Status {response.status_code}"
                )

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return generate_deterministic_plan(request, reason="Gemini Empty Candidates")

            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not raw_text or not raw_text.strip():
                return generate_deterministic_plan(request, reason="Gemini Blank Output")

            # Clean potential markdown wrapping (e.g. ```json ... ```)
            cleaned_json = raw_text.strip()
            if cleaned_json.startswith("```"):
                cleaned_json = re.sub(r"^```(?:json)?\s*", "", cleaned_json)
                cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

            plan_dict = json.loads(cleaned_json)
            if isinstance(plan_dict, list) and plan_dict:
                plan_dict = plan_dict[0]
            if not isinstance(plan_dict, dict):
                plan_dict = {}

            # Build Pydantic models from parsed dictionary with validation
            brief = PlanEventBrief(**plan_dict.get("brief", {}))
            ideas = PlanPersonalizedIdeas(**plan_dict.get("personalized_ideas", {}))

            inferred = parse_prompt_intent(request.user_prompt)
            has_user_budget = (request.target_budget is not None) or (inferred["target_budget"] is not None)
            estimate_requested = inferred.get("estimate_requested", False)

            budget_raw = plan_dict.get("budget_proposal", {})
            if isinstance(budget_raw, list):
                raw_alloc_items = budget_raw
            elif isinstance(budget_raw, dict):
                raw_alloc_items = budget_raw.get("allocations", [])
            else:
                raw_alloc_items = []

            raw_allocations = [
                BudgetCategoryAllocation(**a) for a in raw_alloc_items if isinstance(a, dict)
            ]

            # CRITICAL BACKEND FINANCIAL INTEGRITY VALIDATION LAYER:
            contingency_basis = None
            contingency_percentage = None
            budget_assumptions: List[str] = []

            if has_user_budget:
                user_ceiling = request.target_budget or inferred["target_budget"]
                brief.target_budget = quantize_money(Decimal(str(user_ceiling)))
                brief.budget_provenance = "user_provided"
                contingency_percentage = Decimal("10.00")
                contingency_basis = f"10% emergency buffer based on user-provided budget ceiling ({brief.currency} {brief.target_budget:,.2f})"
            elif estimate_requested:
                brief.budget_provenance = "ai_suggested"
                if brief.target_budget is None:
                    gc = brief.expected_guest_count or 100
                    per_guest = 4000 if brief.event_type == "wedding" else 1200 if brief.event_type == "birthday" else 500
                    brief.target_budget = quantize_money(Decimal(str(gc * per_guest)))
                contingency_percentage = Decimal("10.00")
                contingency_basis = f"10% emergency buffer based on AI-suggested estimate ({brief.currency} {brief.target_budget:,.2f})"
                budget_assumptions = [
                    f"AI-suggested estimate calculated for {brief.expected_guest_count or 100} guests",
                    "Requires explicit user approval before saving as approved project budget",
                ]
            else:
                # User did NOT provide a budget and did NOT request an estimate
                # Reject/neutralize ANY hallucinated budget from Gemini to preserve financial integrity
                brief.target_budget = None
                brief.budget_provenance = "unknown"
                raw_allocations = []
                contingency_percentage = None
                contingency_basis = None
                budget_gap = "Target budget ceiling (specify your budget ceiling or request an AI-suggested estimate)"
                if budget_gap not in brief.missing_information:
                    brief.missing_information.append(budget_gap)

            raw_proposal = PlanBudgetProposal(
                allocations=raw_allocations,
                currency=request.currency or brief.currency or "INR",
                contingency_percentage=contingency_percentage,
                contingency_calculation_basis=contingency_basis,
                budget_assumptions=budget_assumptions,
            )

            # Enforce deterministic financial recalculation
            verified_proposal = recalculate_and_validate_budget_proposal(
                proposal=raw_proposal,
                target_budget=brief.target_budget,
                currency=brief.currency,
                budget_provenance=brief.budget_provenance,
                budget_assumptions=budget_assumptions,
            )

            checklist_raw = plan_dict.get("vendor_checklist", [])
            if isinstance(checklist_raw, dict):
                checklist_raw = checklist_raw.get("items", checklist_raw.get("checklist", []))
            checklist = [
                VendorChecklistItem(**item) for item in checklist_raw if isinstance(item, dict)
            ]

            timeline_raw = plan_dict.get("timeline", [])
            if isinstance(timeline_raw, dict):
                timeline_raw = timeline_raw.get("tasks", timeline_raw.get("milestones", []))
            timeline = [
                PlanTimelineTask(**task) for task in timeline_raw if isinstance(task, dict)
            ]

            # Invariant check: if request had no date, ensure timeline tasks don't have fabricated dates
            if request.event_date is None:
                brief.event_date = None
                for t in timeline:
                    t.suggested_due_date = None

            return GeneratedEventPlan(
                brief=brief,
                personalized_ideas=ideas,
                budget_proposal=verified_proposal,
                vendor_checklist=checklist,
                timeline=timeline,
                provider="gemini",
                model=model,
                is_live_ai=True,
                status="draft",
                disclaimer=(
                    "Plan synthesized via live Gemini AI. Budget figures are illustrative estimates and not verified vendor quotes. "
                    "All financial totals are calculated deterministically by EventPrice Intelligence."
                ),
            )

        except httpx.TimeoutException as timeout_err:
            logger.warning("Gemini timeout (%s). Falling back to deterministic plan.", str(timeout_err))
            return generate_deterministic_plan(request, reason="Gemini Provider Timeout")
        except httpx.RequestError as net_err:
            logger.warning("Gemini network error (%s). Falling back to deterministic plan.", str(net_err))
            return generate_deterministic_plan(request, reason=f"Network Error: {type(net_err).__name__}")
        except json.JSONDecodeError as json_err:
            logger.warning("Failed to parse Gemini JSON output: %s. Falling back to deterministic plan.", str(json_err))
            return generate_deterministic_plan(request, reason="Malformed AI Output")
        except Exception as exc:
            logger.error("Schema validation or unexpected error in Gemini plan generation: %s", str(exc))
            return generate_deterministic_plan(request, reason=f"Schema Validation Fallback: {type(exc).__name__}")

    def refine_plan(self, request: PlanRefinementRequest) -> GeneratedEventPlan:
        """Refines an existing plan draft according to user instructions."""
        existing = request.existing_plan
        instructions = request.refinement_instructions

        # If live AI is available, ask Gemini to adjust the plan JSON
        has_key = bool(self.settings.GEMINI_API_KEY and self.settings.GEMINI_API_KEY.strip())
        if self.settings.AI_ENABLED and has_key:
            refine_spec = (
                f"You are refining an EXISTING Event Plan. Do NOT create an unrelated new event.\n"
                f"Preserve the core event identity: '{existing.brief.event_name}' ({existing.brief.event_type}) in {existing.brief.location or 'specified location'}.\n\n"
                f"Existing Event Plan JSON:\n{existing.model_dump_json()}\n\n"
                f"User Refinement Instruction:\n\"{instructions}\"\n\n"
                f"Refinement Rules:\n"
                f"1. Keep the existing event format, event name, location, and guest count unless specifically requested to change.\n"
                f"2. Seamlessly incorporate the user's modifications (e.g. allocating prizes, updating categories, adjusting budget, adding vendor requirements, adding timeline steps).\n"
                f"3. If the user asks for prizes, awards, or gifts, add or adjust allocations under 'prizes', 'awards', or 'entertainment' within the current event's budget proposal.\n"
                f"4. Propose non-negative realistic amounts. Output strictly pure JSON conforming to the schema.\n"
            )

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.settings.GEMINI_MODEL}:generateContent"
            request_body = {
                "contents": [{"parts": [{"text": f"{PLANNING_SYSTEM_INSTRUCTION}\n\n{refine_spec}"}]}],
                "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json", "maxOutputTokens": 4096},
            }
            headers = {"Content-Type": "application/json", "x-goog-api-key": self.settings.GEMINI_API_KEY.strip()}
            timeout = httpx.Timeout(self.settings.GEMINI_TIMEOUT_SECONDS, connect=5.0)

            try:
                client = self._client or httpx.Client(timeout=timeout)
                resp = client.post(url, json=request_body, headers=headers)
                if resp.status_code == 200:
                    raw_text = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    cleaned = raw_text.strip()
                    if cleaned.startswith("```"):
                        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
                        cleaned = re.sub(r"\s*```$", "", cleaned)
                    plan_dict = json.loads(cleaned)
                    if isinstance(plan_dict, list) and plan_dict:
                        plan_dict = plan_dict[0]
                    if not isinstance(plan_dict, dict):
                        plan_dict = {}

                    brief = PlanEventBrief(**plan_dict.get("brief", existing.brief.model_dump()))
                    inst_lower = instructions.lower()

                    # RULE 8: Refinement does not overwrite user's original budget ceiling without permission
                    budget_change_requested = any(w in inst_lower for w in ("cut budget", "reduce budget", "increase budget", "raise budget", "change budget", "set budget", "budget to", "budget of", "% budget", "budget by"))
                    if existing.brief.budget_provenance in ("user_provided", "user_approved") and not budget_change_requested:
                        brief.target_budget = existing.brief.target_budget
                        brief.budget_provenance = existing.brief.budget_provenance
                    elif existing.brief.budget_provenance == "unknown" and not budget_change_requested:
                        new_intent = parse_prompt_intent(instructions)
                        if new_intent["target_budget"] is not None:
                            brief.target_budget = new_intent["target_budget"]
                            brief.budget_provenance = "user_provided"
                        elif new_intent.get("estimate_requested", False):
                            brief.budget_provenance = "ai_suggested"
                        else:
                            brief.target_budget = None
                            brief.budget_provenance = "unknown"

                    # Preserve core event identity on refinement unless user explicitly asked to change it
                    if "rename" not in inst_lower and "change name" not in inst_lower and existing.brief.event_name:
                        brief.event_name = existing.brief.event_name
                    if existing.brief.event_type and existing.brief.event_type != "other":
                        brief.event_type = existing.brief.event_type
                    if "change location" not in inst_lower and "move to" not in inst_lower and existing.brief.location:
                        brief.location = existing.brief.location
                    ideas = PlanPersonalizedIdeas(**plan_dict.get("personalized_ideas", existing.personalized_ideas.model_dump()))

                    budget_raw = plan_dict.get("budget_proposal", {})
                    if isinstance(budget_raw, list):
                        raw_alloc_items = budget_raw
                    elif isinstance(budget_raw, dict):
                        raw_alloc_items = budget_raw.get("allocations", [])
                    else:
                        raw_alloc_items = []

                    raw_allocations = [
                        BudgetCategoryAllocation(**a) for a in raw_alloc_items if isinstance(a, dict)
                    ]
                    raw_proposal = PlanBudgetProposal(
                        allocations=raw_allocations or existing.budget_proposal.allocations,
                        currency=brief.currency,
                        contingency_percentage=existing.budget_proposal.contingency_percentage,
                        contingency_calculation_basis=existing.budget_proposal.contingency_calculation_basis,
                        budget_assumptions=existing.budget_proposal.budget_assumptions,
                    )
                    verified_proposal = recalculate_and_validate_budget_proposal(
                        proposal=raw_proposal,
                        target_budget=brief.target_budget,
                        currency=brief.currency,
                        budget_provenance=brief.budget_provenance,
                        budget_assumptions=existing.budget_proposal.budget_assumptions,
                    )

                    checklist_raw = plan_dict.get("vendor_checklist", [])
                    if isinstance(checklist_raw, dict):
                        checklist_raw = checklist_raw.get("items", checklist_raw.get("checklist", []))
                    checklist = [
                        VendorChecklistItem(**item) for item in checklist_raw if isinstance(item, dict)
                    ]

                    timeline_raw = plan_dict.get("timeline", [])
                    if isinstance(timeline_raw, dict):
                        timeline_raw = timeline_raw.get("tasks", timeline_raw.get("milestones", []))
                    timeline = [
                        PlanTimelineTask(**task) for task in timeline_raw if isinstance(task, dict)
                    ]

                    # Enforce date invariant on refinement
                    if existing.brief.event_date is None and "date" not in instructions.lower():
                        brief.event_date = None
                        for t in timeline:
                            t.suggested_due_date = None

                    return GeneratedEventPlan(
                        id=existing.id,
                        brief=brief,
                        personalized_ideas=ideas,
                        budget_proposal=verified_proposal,
                        vendor_checklist=checklist or existing.vendor_checklist,
                        timeline=timeline or existing.timeline,
                        provider="gemini",
                        model=self.settings.GEMINI_MODEL,
                        is_live_ai=True,
                        status="refined",
                        disclaimer=existing.disclaimer,
                    )
            except Exception as e:
                logger.warning("Live refinement failed (%s); applying deterministic adjustments.", str(e))

        # Deterministic refinement fallback
        updated_brief = existing.brief.model_copy(deep=True)
        updated_allocations = [a.model_copy(deep=True) for a in existing.budget_proposal.allocations]
        lower_inst = instructions.lower()

        budget_change_requested = any(w in lower_inst for w in ("cut budget", "reduce budget", "increase budget", "raise budget", "change budget", "set budget", "budget to", "budget of", "% budget", "budget by"))

        # Check for budget percentage adjustment (e.g. "cut by 20%", "reduce budget by 10%")
        pct_match = re.search(r"(\d+)\s*%", instructions)
        pct_val = Decimal(pct_match.group(1)) / Decimal("100") if pct_match else Decimal("0.15")

        if any(w in lower_inst for w in ("reduce", "cut", "tighten", "lower", "trim")):
            factor = Decimal("1.00") - pct_val
            for alloc in updated_allocations:
                if "contingency" not in alloc.category.lower():
                    alloc.suggested_amount = quantize_money(alloc.suggested_amount * factor)
                    alloc.rationale += f" [Reduced by {int(pct_val * 100)}% per user instruction]"
            if updated_brief.target_budget and budget_change_requested:
                updated_brief.target_budget = quantize_money(updated_brief.target_budget * factor)
        elif any(w in lower_inst for w in ("increase", "raise", "expand", "boost")):
            factor = Decimal("1.00") + pct_val
            for alloc in updated_allocations:
                if "contingency" not in alloc.category.lower():
                    alloc.suggested_amount = quantize_money(alloc.suggested_amount * factor)
                    alloc.rationale += f" [Increased by {int(pct_val * 100)}% per user instruction]"
            if updated_brief.target_budget and budget_change_requested:
                updated_brief.target_budget = quantize_money(updated_brief.target_budget * factor)

        # Check for guest count adjustment in instruction
        guest_match = re.search(r"(\d+)\s*(?:guests?|people|pax|attendees?)", lower_inst)
        if guest_match and any(w in lower_inst for w in ("guest", "people", "pax", "attendee")):
            new_count = int(guest_match.group(1))
            updated_brief.expected_guest_count = new_count
            updated_brief.confirmed_information.append(f"Updated guest count to {new_count}")

        # Check for prizes/awards addition
        if any(w in lower_inst for w in ("prize", "prizes", "award", "awards", "trophy", "trophies")):
            has_prizes = any("prize" in a.category.lower() or "award" in a.category.lower() for a in updated_allocations)
            if not has_prizes:
                prize_amt = quantize_money(updated_brief.target_budget * Decimal("0.10")) if updated_brief.target_budget else Decimal("25000.00")
                updated_allocations.append(
                    BudgetCategoryAllocation(
                        category="prizes",
                        suggested_amount=prize_amt,
                        currency=updated_brief.currency,
                        rationale="Prizes and awards allocation for top winners / participants as requested",
                        source_type="refinement",
                    )
                )

        # Enforce budget provenance preservation
        if existing.brief.budget_provenance in ("user_provided", "user_approved") and not budget_change_requested:
            updated_brief.target_budget = existing.brief.target_budget
            updated_brief.budget_provenance = existing.brief.budget_provenance
        elif existing.brief.budget_provenance == "unknown" and not budget_change_requested:
            new_intent = parse_prompt_intent(instructions)
            if new_intent["target_budget"] is not None:
                updated_brief.target_budget = new_intent["target_budget"]
                updated_brief.budget_provenance = "user_provided"
            elif new_intent.get("estimate_requested", False):
                updated_brief.budget_provenance = "ai_suggested"
            else:
                updated_brief.target_budget = None
                updated_brief.budget_provenance = "unknown"

        updated_brief.confirmed_information.append(f"Refinement applied: '{instructions[:80]}...'")

        verified_proposal = recalculate_and_validate_budget_proposal(
            proposal=PlanBudgetProposal(
                allocations=updated_allocations,
                currency=updated_brief.currency,
                contingency_percentage=existing.budget_proposal.contingency_percentage,
                contingency_calculation_basis=existing.budget_proposal.contingency_calculation_basis,
                budget_assumptions=existing.budget_proposal.budget_assumptions,
            ),
            target_budget=updated_brief.target_budget,
            currency=updated_brief.currency,
            budget_provenance=updated_brief.budget_provenance,
            budget_assumptions=existing.budget_proposal.budget_assumptions,
        )

        return GeneratedEventPlan(
            id=existing.id,
            brief=updated_brief,
            personalized_ideas=existing.personalized_ideas,
            budget_proposal=verified_proposal,
            vendor_checklist=existing.vendor_checklist,
            timeline=existing.timeline,
            provider="deterministic_fallback",
            model=None,
            is_live_ai=False,
            status="refined",
            disclaimer=existing.disclaimer,
        )
