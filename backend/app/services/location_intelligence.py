"""Location Intelligence Service.

Coordinates geocoding and nearby physical venue / place discovery.
Interfaces with Nominatim and Overpass adapters while providing clean abstractions.
"""

import logging
from typing import Optional

from app.integrations.geocoding.nominatim import NominatimClient
from app.integrations.places.overpass import OverpassClient
from app.schemas.external_data import (
    ForwardGeocodeResponse,
    PlacesResponse,
    ReverseGeocodeResponse,
)

logger = logging.getLogger("eventprice.services.location_intelligence")


class LocationIntelligenceService:
    """Service providing geocoding and geographic venue intelligence."""

    def __init__(
        self,
        nominatim_client: Optional[NominatimClient] = None,
        overpass_client: Optional[OverpassClient] = None,
    ):
        self.nominatim = nominatim_client or NominatimClient()
        self.overpass = overpass_client or OverpassClient()

    def search_locations(
        self,
        query: str,
        limit: int = 5,
        country_code: Optional[str] = "in",
    ) -> ForwardGeocodeResponse:
        """Forward geocode a location string into candidate coordinates."""
        return self.nominatim.forward_geocode(query=query, limit=limit, country_code=country_code)

    def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
    ) -> ReverseGeocodeResponse:
        """Reverse geocode coordinates into a human-readable address."""
        return self.nominatim.reverse_geocode(latitude=latitude, longitude=longitude)

    def find_nearby_venues(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 3000,
        category: Optional[str] = None,
        max_results: int = 30,
    ) -> PlacesResponse:
        """Finds physical mapped event venues and facilities around coordinates."""
        return self.overpass.find_nearby_places(
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            category=category,
            max_results=max_results,
        )


_location_service_instance: Optional[LocationIntelligenceService] = None


def get_location_intelligence_service() -> LocationIntelligenceService:
    """Singleton provider for location intelligence service."""
    global _location_service_instance
    if _location_service_instance is None:
        _location_service_instance = LocationIntelligenceService()
    return _location_service_instance

