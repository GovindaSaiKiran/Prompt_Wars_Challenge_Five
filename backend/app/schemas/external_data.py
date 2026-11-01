"""Pydantic schemas for External Data Integrations.

Covers:
- OpenWeather response normalization and deterministic weather risk assessment.
- OpenStreetMap and Overpass place discovery.
- Nominatim forward and reverse geocoding.
- Provider operational health status.
"""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WeatherClassification(str, Enum):
    """Classification of weather data."""
    CURRENT_OBSERVATION = "current_observation"
    FORECAST = "forecast"
    HISTORICAL = "historical"
    UNAVAILABLE = "unavailable"


class WeatherRiskLevel(str, Enum):
    """Categorical risk severity."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


class WeatherRiskFactor(BaseModel):
    """Individual meteorological risk factor for an event."""
    name: str = Field(..., description="Risk metric name, e.g. rainfall, high_temperature, wind, humidity")
    level: WeatherRiskLevel = Field(..., description="Assessed risk level")
    value_observed: Optional[str] = Field(None, description="Observed or forecast measurement string")
    threshold_applied: Optional[str] = Field(None, description="Configured heuristic threshold applied")
    message: str = Field(..., description="Descriptive explanation of the weather condition")
    recommendation: str = Field(..., description="Actionable event planning mitigation recommendation")


class WeatherRiskAssessment(BaseModel):
    """Deterministic weather risk evaluation computed outside the LLM."""
    overall_risk: WeatherRiskLevel = Field(..., description="Highest severity risk level across all factors")
    is_outdoor_suitable: bool = Field(..., description="Whether weather conditions are conducive for outdoor events")
    risk_score: int = Field(..., ge=0, le=100, description="Deterministic risk index from 0 (ideal) to 100 (extreme)")
    factors: List[WeatherRiskFactor] = Field(default_factory=list, description="Detailed factor-by-factor breakdown")
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations for the event host")
    disclaimer: str = Field(
        default=(
            "Heuristic weather risk assessment based on meteorological measurements. "
            "Not an official governmental meteorological alert. Weather is subject to atmospheric variation."
        ),
        description="Legal and meteorological disclaimer",
    )


class NormalizedWeatherMeasurements(BaseModel):
    """Standardized metric meteorological measurements."""
    temperature_c: Optional[float] = Field(None, description="Current or forecast temperature in Celsius")
    feels_like_c: Optional[float] = Field(None, description="Apparent temperature in Celsius")
    temp_min_c: Optional[float] = Field(None, description="Minimum temperature in Celsius")
    temp_max_c: Optional[float] = Field(None, description="Maximum temperature in Celsius")
    humidity_pct: Optional[int] = Field(None, ge=0, le=100, description="Relative humidity percentage")
    pressure_hpa: Optional[int] = Field(None, description="Atmospheric pressure at sea level in hPa")
    wind_speed_mps: Optional[float] = Field(None, description="Wind speed in meters per second")
    wind_direction_deg: Optional[int] = Field(None, ge=0, le=360, description="Wind direction in meteorological degrees")
    cloud_cover_pct: Optional[int] = Field(None, ge=0, le=100, description="Cloudiness percentage")
    rainfall_mm: Optional[float] = Field(None, description="Precipitation volume in millimeters for the preceding/forecast period")
    weather_condition: Optional[str] = Field(None, description="Primary weather condition (e.g. Rain, Clear, Clouds)")
    weather_description: Optional[str] = Field(None, description="Detailed weather description (e.g. light intensity shower rain)")
    weather_icon: Optional[str] = Field(None, description="OpenWeather icon code")
    sunrise: Optional[datetime] = Field(None, description="Sunrise UTC timestamp")
    sunset: Optional[datetime] = Field(None, description="Sunset UTC timestamp")


class WeatherResponse(BaseModel):
    """Standardized response from weather intelligence."""
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    location_name: Optional[str] = Field(None, description="Resolved city or locality name")
    requested_date: Optional[date] = Field(None, description="Target event date if provided")
    classification: WeatherClassification = Field(..., description="Data provenance classification")
    measurements: Optional[NormalizedWeatherMeasurements] = Field(None, description="Normalized metric weather data")
    risk_assessment: Optional[WeatherRiskAssessment] = Field(None, description="Deterministic risk analysis")
    provider: str = Field(default="OpenWeather")
    provider_endpoint: str = Field(...)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timezone_offset_seconds: int = Field(default=0)
    is_cached: bool = Field(default=False)
    coverage_limitations: List[str] = Field(default_factory=list, description="Clear statement of API and horizon limits")
    disclaimer: str = Field(
        default="Data provided by OpenWeather. Forecasts are estimates subject to atmospheric uncertainty."
    )


# ============================================================================
# Geocoding Schemas (Nominatim)
# ============================================================================


class GeocodingCandidate(BaseModel):
    """Geographic search result candidate."""
    place_id: Optional[str] = None
    display_name: str
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    locality: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    osm_type: Optional[str] = None
    osm_id: Optional[int] = None
    category: Optional[str] = None
    type: Optional[str] = None


class ForwardGeocodeResponse(BaseModel):
    """Forward geocoding search results."""
    query: str
    total_candidates: int
    candidates: List[GeocodingCandidate] = Field(default_factory=list)
    provider: str = Field(default="OpenStreetMap / Nominatim")
    attribution: str = Field(
        default="Data © OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright"
    )
    is_cached: bool = False
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReverseGeocodeResponse(BaseModel):
    """Reverse geocoding address result."""
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    display_name: str
    address_components: Dict[str, Any] = Field(default_factory=dict)
    provider: str = Field(default="OpenStreetMap / Nominatim")
    attribution: str = Field(
        default="Data © OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright"
    )
    is_cached: bool = False
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# Nearby Places Schemas (Overpass / OSM)
# ============================================================================


class NormalizedPlace(BaseModel):
    """A real mapped facility discovered from OpenStreetMap."""
    osm_id: str
    osm_type: str
    name: str
    category: str = Field(..., description="e.g. banquet_hall, event_venue, hotel, restaurant, park, community_centre")
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    distance_meters: Optional[float] = Field(None, ge=0, description="Exact geodesic distance calculated via Haversine")
    address: Optional[str] = None
    locality: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict, description="Original OpenStreetMap key-value tags")
    provider: str = Field(default="OpenStreetMap / Overpass API")
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PlacesResponse(BaseModel):
    """Nearby mapped event facilities."""
    center_latitude: float = Field(..., ge=-90.0, le=90.0)
    center_longitude: float = Field(..., ge=-180.0, le=180.0)
    radius_meters: int = Field(..., ge=100, le=25000)
    category: Optional[str] = None
    total_found: int
    places: List[NormalizedPlace] = Field(default_factory=list)
    attribution: str = Field(
        default="Data © OpenStreetMap contributors, ODbL 1.0. https://osm.org/copyright"
    )
    is_cached: bool = False
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    disclaimer: str = Field(
        default=(
            "Mapped places are sourced directly from OpenStreetMap. "
            "OSM listings are geographic landmarks and are not automatically verified event vendors."
        )
    )


# ============================================================================
# Provider Operational Status
# ============================================================================


class ProviderHealth(BaseModel):
    """Operational status of an individual external provider."""
    provider: str
    configured: bool
    enabled: bool
    operational_status: str  # 'ready', 'unconfigured', 'degraded', 'disabled'
    last_checked_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    message: str


class ExternalStatusResponse(BaseModel):
    """Overall status of external data integrations."""
    providers: Dict[str, ProviderHealth]
    cached_entries_count: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

