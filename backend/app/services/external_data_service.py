"""External Data Service Coordinator.

Provides a unified facade for external data capabilities:
- Weather intelligence and deterministic risk evaluation.
- Forward and reverse geocoding via Nominatim.
- Physical place and venue discovery via Overpass.
- System operational health monitoring across all providers.
"""

from datetime import date, datetime, timezone
import logging
from typing import Dict, Optional

from app.integrations.geocoding.nominatim import NominatimClient
from app.integrations.places.overpass import OverpassClient
from app.integrations.weather.openweather import OpenWeatherAdapter
from app.schemas.external_data import (
    ExternalStatusResponse,
    ForwardGeocodeResponse,
    PlacesResponse,
    ProviderHealth,
    ReverseGeocodeResponse,
    WeatherResponse,
)
from app.services.location_intelligence import LocationIntelligenceService
from app.services.weather_intelligence import evaluate_weather_risks

logger = logging.getLogger("eventprice.services.external_data")


class ExternalDataService:
    """Master service coordinating external meteorological and geographic providers."""

    def __init__(
        self,
        weather_adapter: Optional[OpenWeatherAdapter] = None,
        location_service: Optional[LocationIntelligenceService] = None,
    ):
        self.weather = weather_adapter or OpenWeatherAdapter()
        self.location = location_service or LocationIntelligenceService()

    def get_weather(
        self,
        latitude: float,
        longitude: float,
        event_date: Optional[date] = None,
        location_name: Optional[str] = None,
    ) -> WeatherResponse:
        """Retrieves weather observations/forecasts and attaches deterministic risk assessment."""
        weather_res = self.weather.get_weather(
            latitude=latitude,
            longitude=longitude,
            event_date=event_date,
            location_name=location_name,
        )

        # Apply deterministic risk engine if measurements exist
        if weather_res.measurements is not None:
            risk_assessment = evaluate_weather_risks(weather_res.measurements)
            weather_res.risk_assessment = risk_assessment
        else:
            # If unavailable or historical, evaluate with None to get standard guidance
            risk_assessment = evaluate_weather_risks(None)
            weather_res.risk_assessment = risk_assessment

        return weather_res

    def search_locations(
        self,
        query: str,
        limit: int = 5,
        country_code: Optional[str] = "in",
    ) -> ForwardGeocodeResponse:
        """Forward geocode a location string into candidate coordinates."""
        return self.location.search_locations(
            query=query,
            limit=limit,
            country_code=country_code,
        )

    def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
    ) -> ReverseGeocodeResponse:
        """Reverse geocode coordinates into a human-readable address."""
        return self.location.reverse_geocode(
            latitude=latitude,
            longitude=longitude,
        )

    def find_nearby_places(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 3000,
        category: Optional[str] = None,
        max_results: int = 30,
    ) -> PlacesResponse:
        """Finds physical mapped event venues and facilities around coordinates."""
        return self.location.find_nearby_venues(
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            category=category,
            max_results=max_results,
        )

    def get_status(self) -> ExternalStatusResponse:
        """Aggregates health and cache telemetry across all external integrations."""
        ow_health = self.weather.get_health()
        nom_health = self.location.nominatim.get_health()
        op_health = self.location.overpass.get_health()

        total_cached = (
            self.weather.cache.size()
            + self.location.nominatim.cache.size()
            + self.location.overpass.cache.size()
        )

        providers: Dict[str, ProviderHealth] = {
            "openweather": ow_health,
            "nominatim": nom_health,
            "overpass": op_health,
        }

        return ExternalStatusResponse(
            providers=providers,
            cached_entries_count=total_cached,
            timestamp=datetime.now(timezone.utc),
        )


_external_data_service_instance: Optional[ExternalDataService] = None


def get_external_data_service() -> ExternalDataService:
    """Singleton provider for external data service."""
    global _external_data_service_instance
    if _external_data_service_instance is None:
        _external_data_service_instance = ExternalDataService()
    return _external_data_service_instance

