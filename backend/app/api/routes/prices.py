"""FastAPI endpoints for Vendor Price Records, Price Evidence, and Historical Price Comparisons."""

import logging
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.database import get_db
from app.models.event import Event
from app.models.price import PriceEvidence, VendorPriceRecord
from app.models.vendor import Vendor, VendorService
from app.schemas.price import (
    AvailabilityStatus,
    EvidenceType,
    MultiVendorComparisonItem,
    MultiVendorComparisonResponse,
    PriceComparisonItem,
    PriceEvidenceCreate,
    PriceEvidenceResponse,
    PriceRecordListResponse,
    PriceType,
    ServicePriceComparisonResponse,
    VendorComparisonRequest,
    VendorPriceRecordCreate,
    VendorPriceRecordDetailResponse,
    VendorPriceRecordResponse,
    VendorPriceRecordUpdate,
)
from app.services.vendor_comparison import compare_vendors

logger = logging.getLogger("eventprice.prices")
router = APIRouter(prefix="/prices", tags=["Prices & Evidence"])


# ============================================================================
# Price Record Endpoints
# ============================================================================


@router.post(
    "/",
    response_model=VendorPriceRecordDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a new price observation",
    description=(
        "Records a new price observation for a vendor's service. Validates vendor and service "
        "co-ownership, and optionally attaches initial verification evidence."
    ),
)
def create_price_record(
    payload: VendorPriceRecordCreate,
    db: Session = Depends(get_db),
) -> VendorPriceRecord:
    """Create a new price record, validating vendor-service ownership."""
    # 1. Verify vendor exists
    vendor = db.get(Vendor, payload.vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor with id '{payload.vendor_id}' not found",
        )

    # 2. Verify vendor service exists and belongs to the vendor
    service = db.get(VendorService, payload.vendor_service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"VendorService with id '{payload.vendor_service_id}' not found",
        )

    if service.vendor_id != payload.vendor_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"VendorService '{payload.vendor_service_id}' belongs to vendor '{service.vendor_id}', "
                f"not the specified vendor '{payload.vendor_id}'"
            ),
        )

    # 3. If event_id provided, verify event exists
    if payload.event_id is not None:
        event = db.get(Event, payload.event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with id '{payload.event_id}' not found",
            )

    # 4. Create price record
    record_data = payload.model_dump(exclude={"initial_evidence"})
    if isinstance(record_data.get("price_type"), PriceType):
        record_data["price_type"] = record_data["price_type"].value
    if isinstance(record_data.get("availability_status"), AvailabilityStatus):
        record_data["availability_status"] = record_data["availability_status"].value

    new_record = VendorPriceRecord(**record_data)
    db.add(new_record)
    db.flush()  # assign new_record.id

    # 5. Attach initial evidence if provided
    if payload.initial_evidence is not None:
        evidence_data = payload.initial_evidence.model_dump()
        if isinstance(evidence_data.get("evidence_type"), EvidenceType):
            evidence_data["evidence_type"] = evidence_data["evidence_type"].value

        initial_evidence = PriceEvidence(
            price_record_id=new_record.id,
            **evidence_data,
        )
        db.add(initial_evidence)

    db.commit()

    # Re-query with eager loading to return detail response
    stmt = (
        select(VendorPriceRecord)
        .where(VendorPriceRecord.id == new_record.id)
        .options(selectinload(VendorPriceRecord.evidence_records))
    )
    loaded_record = db.execute(stmt).scalars().first()
    logger.info(
        "Recorded price observation id=%s amount=%s %s for service id=%s",
        loaded_record.id,
        loaded_record.amount,
        loaded_record.currency,
        loaded_record.vendor_service_id,
    )
    return loaded_record


@router.get(
    "/",
    response_model=PriceRecordListResponse,
    status_code=status.HTTP_200_OK,
    summary="List price observations with pagination and filters",
    description="Returns a paginated list of price observations filtered by vendor, service, event, currency, price type, or availability.",
)
def list_price_records(
    skip: int = Query(0, ge=0, description="Records to skip for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return (max 100)"),
    vendor_id: Optional[uuid.UUID] = Query(None, description="Filter by vendor UUID"),
    vendor_service_id: Optional[uuid.UUID] = Query(None, description="Filter by service UUID"),
    event_id: Optional[uuid.UUID] = Query(None, description="Filter by event UUID"),
    currency: Optional[str] = Query(None, description="Filter by 3-letter currency code (e.g. INR)"),
    price_type: Optional[PriceType] = Query(None, description="Filter by pricing model"),
    availability_status: Optional[AvailabilityStatus] = Query(None, description="Filter by availability status"),
    db: Session = Depends(get_db),
) -> PriceRecordListResponse:
    """List price records matching query criteria."""
    query = select(VendorPriceRecord)
    count_query = select(func.count(VendorPriceRecord.id))

    if vendor_id is not None:
        query = query.where(VendorPriceRecord.vendor_id == vendor_id)
        count_query = count_query.where(VendorPriceRecord.vendor_id == vendor_id)

    if vendor_service_id is not None:
        query = query.where(VendorPriceRecord.vendor_service_id == vendor_service_id)
        count_query = count_query.where(VendorPriceRecord.vendor_service_id == vendor_service_id)

    if event_id is not None:
        query = query.where(VendorPriceRecord.event_id == event_id)
        count_query = count_query.where(VendorPriceRecord.event_id == event_id)

    if currency:
        query = query.where(VendorPriceRecord.currency == currency.upper())
        count_query = count_query.where(VendorPriceRecord.currency == currency.upper())

    if price_type is not None:
        query = query.where(VendorPriceRecord.price_type == price_type.value)
        count_query = count_query.where(VendorPriceRecord.price_type == price_type.value)

    if availability_status is not None:
        query = query.where(VendorPriceRecord.availability_status == availability_status.value)
        count_query = count_query.where(VendorPriceRecord.availability_status == availability_status.value)

    total = db.execute(count_query).scalar_one()

    stmt = (
        query.order_by(VendorPriceRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = db.execute(stmt).scalars().all()

    return PriceRecordListResponse(
        items=list(items),
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{price_id}",
    response_model=VendorPriceRecordDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve price observation with evidence",
    description="Retrieves a specific price record along with all attached evidence sources via eager loading.",
)
def get_price_record(
    price_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> VendorPriceRecord:
    """Retrieve single price record with evidence records."""
    stmt = (
        select(VendorPriceRecord)
        .where(VendorPriceRecord.id == price_id)
        .options(
            selectinload(VendorPriceRecord.evidence_records),
            joinedload(VendorPriceRecord.vendor),
            joinedload(VendorPriceRecord.vendor_service),
        )
    )
    record = db.execute(stmt).scalars().first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price record with id '{price_id}' not found",
        )

    return record


@router.patch(
    "/{price_id}",
    response_model=VendorPriceRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Update descriptive fields of a price record",
    description=(
        "Updates permitted descriptive and availability fields only (tax, valid_until, availability). "
        "Historical amounts, currencies, and units are strictly immutable to prevent silent overwrites; "
        "new price changes must be submitted as new observations via POST."
    ),
)
def update_price_record(
    price_id: uuid.UUID,
    payload: VendorPriceRecordUpdate,
    db: Session = Depends(get_db),
) -> VendorPriceRecord:
    """Partially update non-financial status fields of a price observation."""
    record = db.get(VendorPriceRecord, price_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price record with id '{price_id}' not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if "availability_status" in update_data and isinstance(update_data["availability_status"], AvailabilityStatus):
        update_data["availability_status"] = update_data["availability_status"].value

    for field, value in update_data.items():
        setattr(record, field, value)

    db.commit()
    db.refresh(record)
    logger.info("Updated price record id=%s descriptive fields=%s", price_id, list(update_data.keys()))
    return record


# ============================================================================
# Price Evidence Endpoints
# ============================================================================


@router.post(
    "/{price_id}/evidence",
    response_model=PriceEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Attach evidence to a price record",
    description="Attaches a verifiable source, quotation document, or estimation record to an existing price record.",
)
def attach_price_evidence(
    price_id: uuid.UUID,
    payload: PriceEvidenceCreate,
    db: Session = Depends(get_db),
) -> PriceEvidence:
    """Attach evidence to price record."""
    record = db.get(VendorPriceRecord, price_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price record with id '{price_id}' not found",
        )

    evidence_data = payload.model_dump()
    if isinstance(evidence_data.get("evidence_type"), EvidenceType):
        evidence_data["evidence_type"] = evidence_data["evidence_type"].value

    new_evidence = PriceEvidence(
        price_record_id=price_id,
        **evidence_data,
    )
    db.add(new_evidence)
    db.commit()
    db.refresh(new_evidence)
    logger.info(
        "Attached evidence id=%s (type='%s') to price record id=%s",
        new_evidence.id,
        new_evidence.evidence_type,
        price_id,
    )
    return new_evidence


@router.get(
    "/{price_id}/evidence",
    response_model=List[PriceEvidenceResponse],
    status_code=status.HTTP_200_OK,
    summary="List evidence attached to a price record",
    description="Lists all historical and current evidence records attached to this price observation, ordered by capture date.",
)
def list_price_evidence(
    price_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[PriceEvidence]:
    """List all evidence attached to a price record."""
    record = db.get(VendorPriceRecord, price_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Price record with id '{price_id}' not found",
        )

    stmt = (
        select(PriceEvidence)
        .where(PriceEvidence.price_record_id == price_id)
        .order_by(PriceEvidence.captured_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


# ============================================================================
# Price History & Comparison Endpoints
# ============================================================================


@router.get(
    "/vendors/{vendor_id}/history",
    response_model=List[VendorPriceRecordDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Retrieve vendor price history",
    description="Returns a vendor's complete price observation history with evidence, preserving historical rates over time.",
)
def get_vendor_price_history(
    vendor_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[VendorPriceRecord]:
    """Retrieve all historical price records for a vendor."""
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor with id '{vendor_id}' not found",
        )

    stmt = (
        select(VendorPriceRecord)
        .where(VendorPriceRecord.vendor_id == vendor_id)
        .options(selectinload(VendorPriceRecord.evidence_records))
        .order_by(VendorPriceRecord.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


@router.get(
    "/services/{service_id}/comparison",
    response_model=ServicePriceComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare price observations for a service",
    description=(
        "Retrieves and classifies all available price observations for a service offering. "
        "Categorizes observations into published prices, quotations, confirmed rates, estimates, "
        "expired evidence, and unknown. Confirmed rates are strictly supported by vendor_confirmed evidence."
    ),
)
def get_service_price_comparison(
    service_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ServicePriceComparisonResponse:
    """Compare and classify price observations for a service."""
    service = db.get(VendorService, service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"VendorService with id '{service_id}' not found",
        )

    # Load all price observations for this service with evidence and vendor info
    stmt = (
        select(VendorPriceRecord)
        .where(VendorPriceRecord.vendor_service_id == service_id)
        .options(
            selectinload(VendorPriceRecord.evidence_records),
            selectinload(VendorPriceRecord.vendor),
        )
        .order_by(VendorPriceRecord.created_at.desc())
    )
    records = db.execute(stmt).scalars().all()

    now_utc = datetime.now(timezone.utc)
    today = date.today()

    published_prices: List[PriceComparisonItem] = []
    vendor_quotations: List[PriceComparisonItem] = []
    vendor_confirmed: List[PriceComparisonItem] = []
    estimates: List[PriceComparisonItem] = []
    expired: List[PriceComparisonItem] = []
    unknown: List[PriceComparisonItem] = []

    for record in records:
        latest_evidence: Optional[PriceEvidence] = (
            record.evidence_records[0] if record.evidence_records else None
        )

        # Check if record or evidence is expired
        is_evidence_expired = False
        if latest_evidence and latest_evidence.valid_until is not None:
            # normalize comparison with timezone
            evidence_valid = latest_evidence.valid_until
            if evidence_valid.tzinfo is None:
                evidence_valid = evidence_valid.replace(tzinfo=timezone.utc)
            if evidence_valid < now_utc:
                is_evidence_expired = True

        if record.valid_until is not None and record.valid_until < today:
            is_evidence_expired = True

        raw_evidence_type = (
            latest_evidence.evidence_type if latest_evidence else EvidenceType.UNKNOWN.value
        )
        if is_evidence_expired or raw_evidence_type == EvidenceType.EXPIRED.value:
            effective_evidence_type = EvidenceType.EXPIRED
        else:
            try:
                effective_evidence_type = EvidenceType(raw_evidence_type)
            except ValueError:
                effective_evidence_type = EvidenceType.UNKNOWN

        # A price is confirmed ONLY if supported by vendor_confirmed evidence AND not expired
        is_confirmed = (
            effective_evidence_type == EvidenceType.VENDOR_CONFIRMED
            and not is_evidence_expired
        )

        item = PriceComparisonItem(
            price_record_id=record.id,
            vendor_id=record.vendor_id,
            vendor_name=record.vendor.business_name if record.vendor else "Unknown Vendor",
            service_id=service.id,
            service_name=service.service_name,
            amount=record.amount,
            currency=record.currency,
            unit=record.unit,
            price_type=PriceType(record.price_type),
            evidence_type=effective_evidence_type,
            is_confirmed=is_confirmed,
            is_expired=is_evidence_expired or effective_evidence_type == EvidenceType.EXPIRED,
            captured_at=latest_evidence.captured_at if latest_evidence else record.created_at,
            source_name=latest_evidence.source_name if latest_evidence else None,
            source_url=latest_evidence.source_url if latest_evidence else None,
        )

        # Classify into specific response bucket
        if is_evidence_expired or effective_evidence_type == EvidenceType.EXPIRED:
            expired.append(item)
        elif effective_evidence_type == EvidenceType.VENDOR_CONFIRMED:
            vendor_confirmed.append(item)
        elif effective_evidence_type == EvidenceType.VENDOR_QUOTED:
            vendor_quotations.append(item)
        elif effective_evidence_type == EvidenceType.PUBLISHED:
            published_prices.append(item)
        elif effective_evidence_type == EvidenceType.ESTIMATED:
            estimates.append(item)
        else:
            unknown.append(item)

    return ServicePriceComparisonResponse(
        service_id=service.id,
        service_name=service.service_name,
        category=service.category,
        total_observations=len(records),
        published_prices=published_prices,
        vendor_quotations=vendor_quotations,
        vendor_confirmed=vendor_confirmed,
        estimates=estimates,
        expired=expired,
        unknown=unknown,
    )


@router.post(
    "/compare",
    response_model=MultiVendorComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare multiple vendors and price observations",
    description=(
        "Performs multi-vendor comparison for a requested service category, quantity, and unit. "
        "Calculates deterministic total estimated cost, normalizes compatible units, detects unit "
        "and currency incompatibilities with explanations, grades evidence quality, checks validity, "
        "and evaluates availability."
    ),
)
def compare_vendor_prices(
    payload: VendorComparisonRequest,
    db: Session = Depends(get_db),
) -> MultiVendorComparisonResponse:
    """Compare multiple vendor price records across a category or specific offerings."""
    return compare_vendors(db=db, request=payload)


