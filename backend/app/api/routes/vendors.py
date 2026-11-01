"""FastAPI endpoints for Vendor and VendorService management."""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.vendor import Vendor, VendorService
from app.schemas.vendor import (
    VendorCreate,
    VendorDetailResponse,
    VendorListResponse,
    VendorResponse,
    VendorServiceCreate,
    VendorServiceResponse,
    VendorServiceUpdate,
    VendorUpdate,
    VerificationStatus,
)

logger = logging.getLogger("eventprice.vendors")
router = APIRouter(prefix="/vendors", tags=["Vendors"])


# ============================================================================
# Vendor Endpoints
# ============================================================================


@router.post(
    "/",
    response_model=VendorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new vendor",
    description="Registers a new vendor in the vendor catalog.",
)
def create_vendor(
    payload: VendorCreate,
    db: Session = Depends(get_db),
) -> Vendor:
    """Create and persist a new vendor profile."""
    vendor_data = payload.model_dump()
    if isinstance(vendor_data.get("verification_status"), VerificationStatus):
        vendor_data["verification_status"] = vendor_data["verification_status"].value

    new_vendor = Vendor(**vendor_data)
    db.add(new_vendor)
    db.commit()
    db.refresh(new_vendor)
    logger.info("Created vendor id=%s business_name='%s'", new_vendor.id, new_vendor.business_name)
    return new_vendor


@router.get(
    "/",
    response_model=VendorListResponse,
    status_code=status.HTTP_200_OK,
    summary="List vendors with pagination and filters",
    description="Returns a paginated list of vendors filtered by name/description search, city, vendor type, verification status, active flag, service category, or service name.",
)
def list_vendors(
    skip: int = Query(0, ge=0, description="Records to skip for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records to return (max 100)"),
    search: Optional[str] = Query(None, description="Search query matching vendor name or description"),
    city: Optional[str] = Query(None, description="Filter by city name (case-insensitive substring)"),
    vendor_type: Optional[str] = Query(None, description="Filter by vendor type (case-insensitive substring)"),
    verification_status: Optional[VerificationStatus] = Query(None, description="Filter by verification status"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    category: Optional[str] = Query(None, description="Filter vendors offering services under this category"),
    service_name: Optional[str] = Query(None, description="Filter vendors offering a service with this name"),
    db: Session = Depends(get_db),
) -> VendorListResponse:
    """List vendors matching query criteria."""
    query = select(Vendor)
    count_query = select(func.count(Vendor.id))

    if search:
        search_filter = or_(
            Vendor.business_name.ilike(f"%{search.strip()}%"),
            Vendor.description.ilike(f"%{search.strip()}%"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if city:
        query = query.where(Vendor.city.ilike(f"%{city.strip()}%"))
        count_query = count_query.where(Vendor.city.ilike(f"%{city.strip()}%"))

    if vendor_type:
        query = query.where(Vendor.vendor_type.ilike(f"%{vendor_type.strip()}%"))
        count_query = count_query.where(Vendor.vendor_type.ilike(f"%{vendor_type.strip()}%"))

    if verification_status is not None:
        query = query.where(Vendor.verification_status == verification_status.value)
        count_query = count_query.where(Vendor.verification_status == verification_status.value)

    if is_active is not None:
        query = query.where(Vendor.is_active == is_active)
        count_query = count_query.where(Vendor.is_active == is_active)

    if category:
        category_subquery = (
            select(VendorService.vendor_id)
            .where(VendorService.category.ilike(f"%{category.strip()}%"))
            .scalar_subquery()
        )
        query = query.where(Vendor.id.in_(category_subquery))
        count_query = count_query.where(Vendor.id.in_(category_subquery))

    if service_name:
        service_subquery = (
            select(VendorService.vendor_id)
            .where(VendorService.service_name.ilike(f"%{service_name.strip()}%"))
            .scalar_subquery()
        )
        query = query.where(Vendor.id.in_(service_subquery))
        count_query = count_query.where(Vendor.id.in_(service_subquery))

    total = db.execute(count_query).scalar_one()

    vendors_stmt = (
        query.order_by(Vendor.business_name.asc(), Vendor.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = db.execute(vendors_stmt).scalars().all()

    return VendorListResponse(
        items=list(items),
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{vendor_id}",
    response_model=VendorDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve vendor profile with services",
    description="Retrieves single vendor details along with all associated services using eager loading.",
)
def get_vendor(
    vendor_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Vendor:
    """Retrieve single vendor with services via selectinload."""
    stmt = (
        select(Vendor)
        .where(Vendor.id == vendor_id)
        .options(selectinload(Vendor.services))
    )
    vendor = db.execute(stmt).scalars().first()

    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor with id '{vendor_id}' not found",
        )

    return vendor


@router.patch(
    "/{vendor_id}",
    response_model=VendorResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a vendor profile",
    description="Partially updates an existing vendor's attributes.",
)
def update_vendor(
    vendor_id: uuid.UUID,
    payload: VendorUpdate,
    db: Session = Depends(get_db),
) -> Vendor:
    """Partially update vendor fields."""
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor with id '{vendor_id}' not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    if "verification_status" in update_data and isinstance(update_data["verification_status"], VerificationStatus):
        update_data["verification_status"] = update_data["verification_status"].value

    for field, value in update_data.items():
        setattr(vendor, field, value)

    db.commit()
    db.refresh(vendor)
    logger.info("Updated vendor id=%s fields=%s", vendor_id, list(update_data.keys()))
    return vendor


@router.delete(
    "/{vendor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a vendor",
    description="Deletes a vendor profile and cascades deletion to all service offerings.",
)
def delete_vendor(
    vendor_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Delete vendor and cascade delete services."""
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor with id '{vendor_id}' not found",
        )

    db.delete(vendor)
    db.commit()
    logger.info("Deleted vendor id=%s and cascaded services", vendor_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================================
# Vendor Service Endpoints
# ============================================================================


@router.post(
    "/{vendor_id}/services",
    response_model=VendorServiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add service offering to a vendor",
    description="Adds a new service offering to an existing vendor's catalog.",
)
def create_vendor_service(
    vendor_id: uuid.UUID,
    payload: VendorServiceCreate,
    db: Session = Depends(get_db),
) -> VendorService:
    """Create a new service offering associated with the given vendor."""
    vendor = db.get(Vendor, vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vendor with id '{vendor_id}' not found",
        )

    service_data = payload.model_dump()
    new_service = VendorService(vendor_id=vendor_id, **service_data)
    db.add(new_service)
    db.commit()
    db.refresh(new_service)
    logger.info(
        "Created service id=%s for vendor id=%s (category='%s', name='%s')",
        new_service.id,
        vendor_id,
        new_service.category,
        new_service.service_name,
    )
    return new_service


@router.patch(
    "/{vendor_id}/services/{service_id}",
    response_model=VendorServiceResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a vendor service offering",
    description="Partially updates an existing service offering. Enforces that the service belongs to the specified vendor.",
)
def update_vendor_service(
    vendor_id: uuid.UUID,
    service_id: uuid.UUID,
    payload: VendorServiceUpdate,
    db: Session = Depends(get_db),
) -> VendorService:
    """Update service ensuring strict vendor ownership."""
    stmt = select(VendorService).where(
        VendorService.id == service_id,
        VendorService.vendor_id == vendor_id,
    )
    service = db.execute(stmt).scalars().first()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with id '{service_id}' not found under vendor '{vendor_id}'",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(service, field, value)

    db.commit()
    db.refresh(service)
    logger.info("Updated service id=%s for vendor id=%s", service_id, vendor_id)
    return service


@router.delete(
    "/{vendor_id}/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a vendor service offering",
    description="Deletes a service offering. Enforces that the service belongs to the specified vendor.",
)
def delete_vendor_service(
    vendor_id: uuid.UUID,
    service_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Delete service ensuring strict vendor ownership."""
    stmt = select(VendorService).where(
        VendorService.id == service_id,
        VendorService.vendor_id == vendor_id,
    )
    service = db.execute(stmt).scalars().first()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service with id '{service_id}' not found under vendor '{vendor_id}'",
        )

    db.delete(service)
    db.commit()
    logger.info("Deleted service id=%s from vendor id=%s", service_id, vendor_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

