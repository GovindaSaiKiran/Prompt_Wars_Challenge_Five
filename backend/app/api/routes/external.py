"""External Data API Endpoints.

Mounts routes for:
- Weather observations, forecasts, and deterministic risk assessments.
- Forward and reverse geocoding via Nominatim.
- Nearby physical place discovery via Overpass.
- Integration provider health status.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.schemas.external_data import (
    ExternalStatusResponse,
    ForwardGeocodeResponse,
    PlacesResponse,
    ReverseGeocodeResponse,
    WeatherResponse,
)
from app.services.external_data_service import (
    ExternalDataService,
    get_external_data_service,
)

router = APIRouter(prefix="/external", tags=["External Data"])


@router.get("/weather", response_model=WeatherResponse, summary="Get weather data and risk evaluation")
def get_weather(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees"),
    event_date: Optional[date] = Query(None, alias="date", description="Target event date (YYYY-MM-DD)"),
    location_name: Optional[str] = Query(None, description="Optional city or locality name"),
    service: ExternalDataService = Depends(get_external_data_service),
) -> WeatherResponse:
    """Retrieves current or forecast weather observations and computes a deterministic risk evaluation."""
    return service.get_weather(
        latitude=lat,
        longitude=lon,
        event_date=event_date,
        location_name=location_name,
    )


@router.get("/geocode", response_model=ForwardGeocodeResponse, summary="Forward geocode location query")
def forward_geocode(
    q: str = Query(..., min_length=1, description="Location search query (e.g. Banjara Hills, Hyderabad)"),
    limit: int = Query(5, ge=1, le=20, description="Maximum number of candidates"),
    country_code: Optional[str] = Query("in", description="Country code bias (ISO 3166-1 alpha-2, e.g. 'in')"),
    service: ExternalDataService = Depends(get_external_data_service),
) -> ForwardGeocodeResponse:
    """Forward geocode a text query to geographic coordinates via Nominatim."""
    return service.search_locations(
        query=q,
        limit=limit,
        country_code=country_code,
    )


@router.get("/reverse-geocode", response_model=ReverseGeocodeResponse, summary="Reverse geocode coordinates")
def reverse_geocode(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees"),
    service: ExternalDataService = Depends(get_external_data_service),
) -> ReverseGeocodeResponse:
    """Reverse geocode coordinates into a structured human-readable address."""
    return service.reverse_geocode(
        latitude=lat,
        longitude=lon,
    )


@router.get("/places", response_model=PlacesResponse, summary="Discover nearby physical venues and amenities")
def get_nearby_places(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Center latitude in decimal degrees"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Center longitude in decimal degrees"),
    radius_meters: int = Query(3000, ge=100, le=25000, description="Search radius in meters"),
    category: Optional[str] = Query(
        None,
        description="Filter category: banquet_hall, event_venue, hotel, restaurant, park, community_centre",
    ),
    max_results: int = Query(30, ge=1, le=100, description="Max results to return"),
    service: ExternalDataService = Depends(get_external_data_service),
) -> PlacesResponse:
    """Discovers real physical mapped event venues and facilities around coordinates using Overpass / OpenStreetMap."""
    return service.find_nearby_places(
        latitude=lat,
        longitude=lon,
        radius_meters=radius_meters,
        category=category,
        max_results=max_results,
    )


@router.get("/status", response_model=ExternalStatusResponse, summary="Get external data provider health status")
def get_external_status(
    service: ExternalDataService = Depends(get_external_data_service),
) -> ExternalStatusResponse:
    """Returns the operational status, configuration check, and cache metrics for all external data providers."""
    return service.get_status()

