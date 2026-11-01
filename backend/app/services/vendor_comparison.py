"""Vendor Comparison Service.

Provides deterministic multi-vendor price comparison, unit normalization,
tax handling, evidence quality evaluation, availability reporting, and
location matching without fabrication.
"""

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional, Set

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.price import PriceEvidence, VendorPriceRecord
from app.models.vendor import Vendor, VendorService
from app.schemas.price import (
    AvailabilityStatus,
    EvidenceType,
    MultiVendorComparisonItem,
    MultiVendorComparisonResponse,
    PriceType,
    VendorComparisonRequest,
)
from app.services.budget_engine import calculate_line_item, quantize_money

logger = logging.getLogger("eventprice.vendor_comparison")

# Unit Families for Normalization
GUEST_UNITS: Set[str] = {
    "person",
    "per_person",
    "per person",
    "plate",
    "per_plate",
    "per plate",
    "guest",
    "per_guest",
    "per guest",
    "pax",
    "per_pax",
    "per pax",
    "head",
    "per_head",
    "per head",
}

HOUR_UNITS: Set[str] = {
    "hour",
    "per_hour",
    "per hour",
    "hr",
    "per_hr",
    "per hr",
    "hours",
    "hrs",
}

DAY_UNITS: Set[str] = {
    "day",
    "per_day",
    "per day",
    "days",
}

EVENT_UNITS: Set[str] = {
    "event",
    "per_event",
    "per event",
    "package",
    "per_package",
    "per package",
    "flat",
    "fixed",
    "total",
    "lump sum",
    "lot",
}

ITEM_UNITS: Set[str] = {
    "item",
    "per_item",
    "per item",
    "unit",
    "per_unit",
    "per unit",
    "piece",
    "pc",
    "pieces",
}


def _clean_unit(u: Optional[str]) -> str:
    if not u:
        return ""
    return u.strip().lower().replace("-", " ")


def _find_unit_family(unit_str: str) -> Optional[str]:
    clean = _clean_unit(unit_str)
    if clean in GUEST_UNITS:
        return "guest"
    if clean in HOUR_UNITS:
        return "hour"
    if clean in DAY_UNITS:
        return "day"
    if clean in EVENT_UNITS:
        return "event"
    if clean in ITEM_UNITS:
        return "item"
    return None


def _check_unit_compatibility(
    req_unit: Optional[str],
    rec_unit: str,
    quantity: Decimal,
) -> tuple[bool, Optional[Decimal], Optional[str]]:
    """Determine whether requested quantity & unit can be normalized to vendor record unit.

    Returns: (is_compatible, normalized_quantity, compatibility_reason)
    """
    rec_clean = _clean_unit(rec_unit)
    rec_family = _find_unit_family(rec_clean)

    if req_unit:
        req_clean = _clean_unit(req_unit)
        req_family = _find_unit_family(req_clean)

        # Same unit family (e.g., 'per plate' vs 'per person')
        if req_family and rec_family and req_family == rec_family:
            return True, quantity, None

        # Exact string match
        if req_clean == rec_clean:
            return True, quantity, None

        # Vendor charges flat event/package rate
        if rec_family == "event" or rec_clean in EVENT_UNITS:
            return (
                True,
                Decimal("1.00"),
                f"Flat rate pricing: vendor charges per event/package; requested {quantity} {req_unit} covered under 1 package.",
            )

        # Incompatible units
        return (
            False,
            None,
            f"Incompatible unit: requested '{req_unit}' cannot be normalized against vendor unit '{rec_unit}' without duration or conversion metrics.",
        )

    # No specific unit requested (raw count)
    if rec_family in {"guest", "item"}:
        return True, quantity, None

    if rec_family == "event":
        return (
            True,
            Decimal("1.00"),
            "Flat rate pricing: vendor charges per event/package.",
        )

    return (
        False,
        None,
        f"Ambiguous unit: vendor charges '{rec_unit}', but requested quantity {quantity} has no duration or unit specified.",
    )


def compare_vendors(
    db: Session,
    request: VendorComparisonRequest,
) -> MultiVendorComparisonResponse:
    """Compare multiple vendor price records against the specified requirement."""
    # Build query for active vendors and active services
    stmt = (
        select(VendorPriceRecord)
        .join(VendorService, VendorPriceRecord.vendor_service_id == VendorService.id)
        .join(Vendor, VendorPriceRecord.vendor_id == Vendor.id)
        .where(
            Vendor.is_active == True,  # noqa: E712
            VendorService.is_active == True,  # noqa: E712
        )
        .options(
            selectinload(VendorPriceRecord.evidence_records),
            selectinload(VendorPriceRecord.vendor),
            selectinload(VendorPriceRecord.vendor_service),
        )
    )

    if request.category:
        clean_cat = request.category.strip()
        stmt = stmt.where(VendorService.category.ilike(f"%{clean_cat}%"))

    if request.vendor_ids:
        stmt = stmt.where(VendorPriceRecord.vendor_id.in_(request.vendor_ids))

    if request.vendor_service_ids:
        stmt = stmt.where(VendorPriceRecord.vendor_service_id.in_(request.vendor_service_ids))

    if request.price_record_ids:
        stmt = stmt.where(VendorPriceRecord.id.in_(request.price_record_ids))

    records = db.execute(stmt.order_by(VendorPriceRecord.amount.asc())).scalars().all()

    now_utc = datetime.now(timezone.utc)
    today = date.today()
    target_currency = request.currency.strip().upper()

    comparison_items: List[MultiVendorComparisonItem] = []
    comparison_notes: List[str] = []

    compatible_count = 0
    best_value_record_id: Optional[uuid.UUID] = None
    best_value_rationale: Optional[str] = None
    lowest_compatible_total: Optional[Decimal] = None
    best_value_vendor_name: Optional[str] = None

    has_unknown_tax = False
    has_unknown_availability = False

    for record in records:
        vendor: Vendor = record.vendor
        service: VendorService = record.vendor_service

        latest_evidence: Optional[PriceEvidence] = (
            record.evidence_records[0] if record.evidence_records else None
        )

        # 1. Expiration check
        is_record_expired = False
        if record.valid_until is not None and record.valid_until < today:
            is_record_expired = True

        is_evidence_expired = False
        if latest_evidence and latest_evidence.valid_until is not None:
            ev_valid = latest_evidence.valid_until
            if ev_valid.tzinfo is None:
                ev_valid = ev_valid.replace(tzinfo=timezone.utc)
            if ev_valid < now_utc:
                is_evidence_expired = True

        effective_expired = is_record_expired or is_evidence_expired

        # 2. Evidence classification & grade
        raw_evidence = (
            latest_evidence.evidence_type
            if latest_evidence
            else EvidenceType.UNKNOWN.value
        )

        if effective_expired or raw_evidence == EvidenceType.EXPIRED.value:
            effective_evidence_type = EvidenceType.EXPIRED
            evidence_grade = "Grade F (Expired / Historical Rate)"
        elif raw_evidence == EvidenceType.VENDOR_CONFIRMED.value:
            effective_evidence_type = EvidenceType.VENDOR_CONFIRMED
            evidence_grade = "Grade A (Direct Vendor Confirmation)"
        elif raw_evidence == EvidenceType.VENDOR_QUOTED.value:
            effective_evidence_type = EvidenceType.VENDOR_QUOTED
            evidence_grade = "Grade B (Official Vendor Quotation)"
        elif raw_evidence == EvidenceType.PUBLISHED.value:
            effective_evidence_type = EvidenceType.PUBLISHED
            evidence_grade = "Grade B (Publicly Published Rate)"
        elif raw_evidence == EvidenceType.ESTIMATED.value:
            effective_evidence_type = EvidenceType.ESTIMATED
            evidence_grade = "Grade C (Market Benchmark Estimate)"
        else:
            effective_evidence_type = EvidenceType.UNKNOWN
            evidence_grade = "Grade D (Unverified / Unknown Provenance)"

        is_confirmed = (
            effective_evidence_type == EvidenceType.VENDOR_CONFIRMED
            and not effective_expired
        )
        is_estimated = (effective_evidence_type == EvidenceType.ESTIMATED)

        # 3. Currency Check
        rec_curr = record.currency.strip().upper()
        if rec_curr != target_currency:
            is_compatible = False
            norm_qty = None
            reason = (
                f"Currency mismatch: vendor rate is in '{rec_curr}', while comparison requested '{target_currency}'. "
                "Cross-currency conversions are not estimated without verified exchange rates."
            )
            subtotal = None
            tax_amount = None
            total_cost = None
            tax_status = "unknown"
            tax_notes = "Currency mismatch; tax calculation skipped."
        else:
            # 4. Unit Compatibility Check
            is_compatible, norm_qty, reason = _check_unit_compatibility(
                req_unit=request.unit,
                rec_unit=record.unit,
                quantity=request.quantity,
            )

            # 5. Financial Calculation (deterministic math consistent with budget engine)
            if is_compatible and norm_qty is not None:
                # Rule: Tax is calculated ONLY from explicitly supplied tax information.
                # No tax rate is ever inferred from vendor category or service type.
                if record.tax_rate is not None:
                    calc_line = calculate_line_item(
                        quantity=norm_qty,
                        unit_price=record.amount,
                        tax_included=bool(record.tax_included),
                        tax_rate=record.tax_rate,
                        category=service.category,
                        description=service.service_name,
                    )
                    subtotal = (
                        calc_line.taxable_amount
                        if record.tax_included
                        else calc_line.raw_subtotal
                    )
                    tax_amount = calc_line.tax_amount
                    total_cost = calc_line.line_total
                    tax_status = "inclusive" if record.tax_included else "exclusive"
                    tax_notes = (
                        f"Calculated deterministically at {record.tax_rate}% "
                        f"({'tax inclusive' if record.tax_included else 'tax exclusive'})."
                    )
                else:
                    # Unknown tax rate: NEVER treat as confirmed 0.00
                    has_unknown_tax = True
                    if record.tax_included is True:
                        subtotal = quantize_money(record.amount * norm_qty)
                        tax_amount = None  # Tax rate is unknown, cannot confirm 0 tax
                        total_cost = subtotal  # Rate is marked tax-inclusive
                        tax_status = "inclusive"
                        tax_notes = "Rate is all-inclusive, but statutory tax rate breakdown is unspecified."
                    else:
                        subtotal = quantize_money(record.amount * norm_qty)
                        tax_amount = None  # Unknown tax, NOT confirmed zero
                        total_cost = subtotal  # Represents base net amount
                        tax_status = "unknown"
                        tax_notes = (
                            "Statutory tax rate is unspecified and not included. "
                            "Additional GST/statutory taxes may apply upon booking."
                        )
            else:
                subtotal = None
                tax_amount = None
                total_cost = None
                tax_status = "unknown"
                tax_notes = None

        # 6. Availability Status & Explanation
        avail = AvailabilityStatus(record.availability_status)
        checked_str = (
            record.availability_checked_at.strftime("%Y-%m-%d")
            if record.availability_checked_at
            else None
        )

        if avail == AvailabilityStatus.AVAILABLE:
            availability_notes = (
                f"Vendor is marked available for bookings"
                f"{f' (verified {checked_str})' if checked_str else ''}."
            )
        elif avail == AvailabilityStatus.LIMITED:
            availability_notes = "Limited booking slots remaining; early reservation recommended."
        elif avail == AvailabilityStatus.UNAVAILABLE:
            availability_notes = "Vendor is fully booked or unavailable for this period."
        else:
            has_unknown_availability = True
            availability_notes = (
                "Availability has not been verified with the vendor. "
                "Direct inquiry required to confirm booking dates."
            )

        # 7. Best-Value Recommendation Evaluation
        # Strict Integrity Rules:
        # - Expired prices cannot win
        # - Unavailable vendors cannot win
        # - Unknown availability cannot win (not treated as available)
        # - Incompatible units cannot win
        # - Currency mismatches cannot win
        # - Unverified market benchmarks/estimates cannot win (must have vendor quote/published rate)
        if is_compatible:
            compatible_count += 1
            can_qualify_for_best_value = (
                not effective_expired
                and avail == AvailabilityStatus.AVAILABLE
                and effective_evidence_type in {
                    EvidenceType.VENDOR_CONFIRMED,
                    EvidenceType.VENDOR_QUOTED,
                    EvidenceType.PUBLISHED,
                }
                and total_cost is not None
            )

            if can_qualify_for_best_value:
                if lowest_compatible_total is None or total_cost < lowest_compatible_total:
                    lowest_compatible_total = total_cost
                    best_value_record_id = record.id
                    best_value_vendor_name = vendor.business_name

        # 8. Location & Proximity Integrity
        # Administrative city-name matching is NOT presented as actual geographic distance.
        city_match: Optional[bool] = None
        location_notes: Optional[str] = None

        if request.target_city and vendor.city:
            if request.target_city.strip().lower() == vendor.city.strip().lower():
                city_match = True
                location_notes = (
                    f"Administrative city match: {vendor.city}. "
                    "Note: Precise geographic distance, transit duration, and travel times "
                    "are not calculated without coordinate mapping and routing services."
                )
            else:
                city_match = False
                location_notes = (
                    f"Operating in {vendor.city} (Target: {request.target_city}); "
                    "outstation travel fees may apply. Precise distance requires routing integration."
                )
        elif vendor.city:
            location_notes = f"Operating in {vendor.city}."
        else:
            location_notes = "Operating location unspecified."

        location_match = city_match

        # 9. Inclusions and Exclusions from latest evidence
        inclusions = latest_evidence.inclusions if latest_evidence else None
        exclusions = latest_evidence.exclusions if latest_evidence else None

        item = MultiVendorComparisonItem(
            price_record_id=record.id,
            vendor_id=vendor.id,
            vendor_name=vendor.business_name,
            vendor_city=vendor.city,
            verification_status=vendor.verification_status,
            service_id=service.id,
            service_name=service.service_name,
            category=service.category,
            base_amount=record.amount,
            currency=record.currency,
            unit=record.unit,
            price_type=PriceType(record.price_type),
            tax_included=record.tax_included,
            tax_rate=record.tax_rate,
            tax_status=tax_status,
            tax_notes=tax_notes,
            is_compatible=is_compatible,
            compatibility_reason=reason,
            normalized_quantity=norm_qty,
            subtotal=subtotal,
            tax_amount=tax_amount,
            total_cost=total_cost,
            inclusions=inclusions,
            exclusions=exclusions,
            evidence_type=effective_evidence_type,
            evidence_grade=evidence_grade,
            is_confirmed=is_confirmed,
            is_estimated=is_estimated,
            source_name=latest_evidence.source_name if latest_evidence else None,
            source_url=latest_evidence.source_url if latest_evidence else None,
            captured_at=latest_evidence.captured_at if latest_evidence else record.created_at,
            is_expired=effective_expired,
            valid_until=record.valid_until,
            availability_status=avail,
            availability_checked_at=record.availability_checked_at,
            availability_notes=availability_notes,
            location_match=location_match,
            city_match=city_match,
            location_notes=location_notes,
        )
        comparison_items.append(item)

    # 10. Formulate Comprehensive Comparison Notes
    total_found = len(records)
    if total_found == 0:
        comparison_notes.append("No active vendor price observations found matching the requested criteria.")
    else:
        comparison_notes.append(
            f"Evaluated {total_found} vendor price observations: {compatible_count} compatible for requested quantity {request.quantity}."
        )
        incompatible_count = total_found - compatible_count
        if incompatible_count > 0:
            comparison_notes.append(
                f"{incompatible_count} observation(s) marked incompatible due to unit divergence or currency mismatches."
            )

        if has_unknown_tax:
            comparison_notes.append(
                "One or more price records have unspecified tax rates. Totals represent net base amounts; additional taxes may apply."
            )

        if has_unknown_availability:
            comparison_notes.append(
                "One or more vendors have unverified availability and are not treated as confirmed available."
            )

        if best_value_record_id:
            best_value_rationale = (
                f"Lowest verified price option among available vendors with confirmed/published rates: "
                f"{lowest_compatible_total} {target_currency} ({best_value_vendor_name})."
            )
            comparison_notes.append(
                f"Lowest verified price option identified at {lowest_compatible_total} {target_currency} ({best_value_vendor_name}). "
                "Note: Lowest price is not automatically the superior overall choice; inspect inclusions, exclusions, and deliverables."
            )
        else:
            best_value_rationale = None
            comparison_notes.append(
                "No vendor qualifies for a verified best-value recommendation. "
                "Criteria require confirmed availability, valid (non-expired) rates, and direct vendor provenance (not estimates)."
            )

    return MultiVendorComparisonResponse(
        requested_category=request.category,
        requested_quantity=request.quantity,
        requested_unit=request.unit,
        requested_currency=target_currency,
        total_compared=total_found,
        compatible_count=compatible_count,
        items=comparison_items,
        best_value_price_record_id=best_value_record_id,
        best_value_rationale=best_value_rationale,
        comparison_notes=comparison_notes,
    )
