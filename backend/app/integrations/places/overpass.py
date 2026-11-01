"""OpenStreetMap Overpass API Integration.

Discovers real physical mapped venues, hotels, parks, and event spaces
surrounding given geographic coordinates using the Overpass QL query engine.
- Computes geodesic distance in meters via the Haversine formula.
- Deduplicates elements across nodes, ways, and relations.
- Normalizes OSM tags into standardized place models.
- Preserves truthfulness: does NOT fabricate phone numbers, ratings, or prices.
- Implements bounded timeouts, error handling, and in-memory TTL caching.
"""

from datetime import datetime, timezone
import logging
import math
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

from app.core.config import settings
from app.integrations.base import (
    InMemoryTTLCache,
    generate_cache_key,
    sanitize_url_for_logging,
)
from app.schemas.external_data import (
    NormalizedPlace,
    PlacesResponse,
    ProviderHealth,
)

logger = logging.getLogger("eventprice.integrations.overpass")

# Mapping of supported categories to OSM key=value pairs
CATEGORY_TAG_FILTERS: Dict[str, List[Tuple[str, str]]] = {
    "banquet_hall": [("amenity", "banquet_hall")],
    "event_venue": [("amenity", "events_venue"), ("amenity", "conference_centre")],
    "hotel": [("tourism", "hotel"), ("tourism", "resort")],
    "restaurant": [("amenity", "restaurant")],
    "park": [("leisure", "park"), ("leisure", "garden")],
    "community_centre": [("amenity", "community_centre"), ("amenity", "social_facility")],
}


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two points in meters."""
    R = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class OverpassClient:
    """Client for querying nearby amenities and facilities via Overpass API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        enabled: Optional[bool] = None,
        cache_ttl_seconds: int = 1800,  # 30 minutes
    ):
        self.base_url = (base_url or settings.OVERPASS_BASE_URL).rstrip("/")
        self.timeout = timeout_seconds or settings.OVERPASS_TIMEOUT_SECONDS
        self.enabled = enabled if enabled is not None else settings.OVERPASS_ENABLED
        self.cache = InMemoryTTLCache(default_ttl_seconds=cache_ttl_seconds, max_entries=1000)

        # Operational health metrics
        self.last_checked_at: Optional[datetime] = None
        self.last_success_at: Optional[datetime] = None
        self.last_error: Optional[str] = None

    def _build_overpass_ql(
        self,
        lat: float,
        lon: float,
        radius_meters: int,
        category: Optional[str] = None,
    ) -> str:
        """Constructs an optimized Overpass QL query string."""
        tag_filters: List[Tuple[str, str]] = []

        if category and category.lower() in CATEGORY_TAG_FILTERS:
            tag_filters.extend(CATEGORY_TAG_FILTERS[category.lower()])
        else:
            # Query all relevant event facility categories
            for filters in CATEGORY_TAG_FILTERS.values():
                tag_filters.extend(filters)

        statements: List[str] = []
        for key, value in tag_filters:
            statements.append(f'nwr["{key}"="{value}"](around:{radius_meters},{lat},{lon});')

        query_body = "\n  ".join(statements)
        # Bounded server timeout (25s) to keep Overpass responsive
        return f"""[out:json][timeout:25];
(
  {query_body}
);
out center tags;"""

    def _determine_category(self, tags: Dict[str, str]) -> str:
        """Determines best matching high-level category from tags."""
        amenity = tags.get("amenity", "")
        tourism = tags.get("tourism", "")
        leisure = tags.get("leisure", "")

        if amenity in ("banquet_hall", "events_venue", "conference_centre"):
            return "banquet_hall"
        if tourism in ("hotel", "resort", "motel"):
            return "hotel"
        if leisure in ("park", "garden"):
            return "park"
        if amenity in ("community_centre", "social_facility"):
            return "community_centre"
        if amenity == "restaurant":
            return "restaurant"
        return "event_venue"

    def _extract_address(self, tags: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
        """Extracts address and locality from OSM address tags."""
        housenumber = tags.get("addr:housenumber", "")
        street = tags.get("addr:street", "")
        suburb = tags.get("addr:suburb", "") or tags.get("addr:neighbourhood", "")
        city = tags.get("addr:city", "")
        postcode = tags.get("addr:postcode", "")

        addr_parts = [p for p in (housenumber, street, suburb) if p]
        address = ", ".join(addr_parts) if addr_parts else None
        locality = city or suburb or None
        return address, locality

    def find_nearby_places(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 3000,
        category: Optional[str] = None,
        max_results: int = 30,
    ) -> PlacesResponse:
        """Finds physical mapped event venues and facilities around coordinates."""
        now = datetime.now(timezone.utc)
        self.last_checked_at = now

        # Enforce bounds
        bounded_radius = min(max(100, radius_meters), 25000)

        if not self.enabled:
            return PlacesResponse(
                center_latitude=latitude,
                center_longitude=longitude,
                radius_meters=bounded_radius,
                category=category,
                total_found=0,
                places=[],
                attribution="Overpass / OSM integration is currently disabled in backend settings.",
            )

        # Coordinate rounding for caching (approx 50m precision)
        cache_key = generate_cache_key(
            "overpass:places",
            {
                "lat": round(latitude, 3),
                "lon": round(longitude, 3),
                "radius": bounded_radius,
                "cat": (category or "all").lower(),
            },
        )
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            cached_copy = cached_result.model_copy()
            cached_copy.is_cached = True
            return cached_copy

        ql_query = self._build_overpass_ql(latitude, longitude, bounded_radius, category)
        endpoints_to_try = [self.base_url]
        if "overpass-api.de" in self.base_url:
            endpoints_to_try.append("https://overpass.kumi.systems/api/interpreter")

        raw_json = None
        for endpoint in endpoints_to_try:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        endpoint,
                        data={"data": ql_query},
                        headers={
                            "User-Agent": settings.NOMINATIM_USER_AGENT,
                            "Accept": "application/json, */*",
                            "Content-Type": "application/x-www-form-urlencoded",
                        },
                    )
                    response.raise_for_status()
                    raw_json = response.json()
                    break
            except Exception as endpoint_err:
                logger.warning(f"Overpass endpoint {endpoint} failed: {endpoint_err}")
                self.last_error = str(endpoint_err)

        if raw_json is None:
            return PlacesResponse(
                center_latitude=latitude,
                center_longitude=longitude,
                radius_meters=bounded_radius,
                category=category,
                total_found=0,
                places=[],
                attribution=f"Error contacting Overpass: {self.last_error}",
            )

        try:
            elements = raw_json.get("elements", [])
            places: List[NormalizedPlace] = []
            seen_identifiers: Set[str] = set()

            for el in elements:
                osm_type = el.get("type", "node")
                osm_id = str(el.get("id", ""))
                unique_key = f"{osm_type}:{osm_id}"
                if unique_key in seen_identifiers:
                    continue
                seen_identifiers.add(unique_key)

                # Extract coordinates
                # For nodes: 'lat', 'lon' are top-level
                # For ways/relations: 'center' dict holds 'lat', 'lon' (from `out center`)
                lat = el.get("lat")
                lon = el.get("lon")
                if lat is None or lon is None:
                    center = el.get("center", {})
                    lat = center.get("lat")
                    lon = center.get("lon")

                if lat is None or lon is None:
                    continue

                try:
                    place_lat = float(lat)
                    place_lon = float(lon)
                except (ValueError, TypeError):
                    continue

                tags = el.get("tags", {})
                name = tags.get("name")
                # If unnamed place, omit or use fallback with category
                if not name:
                    # Prefer named landmarks for event venues
                    continue

                distance = haversine_distance_meters(latitude, longitude, place_lat, place_lon)
                cat = self._determine_category(tags)
                address, locality = self._extract_address(tags)

                place = NormalizedPlace(
                    osm_id=osm_id,
                    osm_type=osm_type,
                    name=name,
                    category=cat,
                    latitude=place_lat,
                    longitude=place_lon,
                    distance_meters=round(distance, 1),
                    address=address,
                    locality=locality,
                    tags={k: str(v) for k, v in tags.items()},
                    retrieved_at=now,
                )
                places.append(place)

            # Sort by distance
            places.sort(key=lambda p: p.distance_meters if p.distance_meters is not None else float("inf"))
            capped_places = places[:max_results]

            result = PlacesResponse(
                center_latitude=latitude,
                center_longitude=longitude,
                radius_meters=bounded_radius,
                category=category,
                total_found=len(capped_places),
                places=capped_places,
                is_cached=False,
                retrieved_at=now,
            )

            self.cache.set(cache_key, result)
            self.last_success_at = now
            self.last_error = None
            return result

        except httpx.HTTPStatusError as e:
            self.last_error = f"HTTP {e.response.status_code}"
            logger.error(f"Overpass API HTTP error: {self.last_error}")
            return PlacesResponse(
                center_latitude=latitude,
                center_longitude=longitude,
                radius_meters=bounded_radius,
                category=category,
                total_found=0,
                places=[],
                attribution=f"Error contacting Overpass: HTTP {e.response.status_code}",
            )
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Overpass places query failed: {e}")
            return PlacesResponse(
                center_latitude=latitude,
                center_longitude=longitude,
                radius_meters=bounded_radius,
                category=category,
                total_found=0,
                places=[],
                attribution=f"Error contacting Overpass: {type(e).__name__}",
            )

    def get_health(self) -> ProviderHealth:
        """Returns the operational status of the Overpass integration."""
        is_configured = bool(self.base_url)
        status = "ready"
        message = "Overpass places provider is operational."

        if not self.enabled:
            status = "disabled"
            message = "Overpass places integration is disabled in configuration."
        elif not is_configured:
            status = "unconfigured"
            message = "Overpass API endpoint configuration missing."
        elif self.last_error:
            status = "degraded"
            message = f"Recent error: {self.last_error}"

        return ProviderHealth(
            provider="Overpass (OpenStreetMap)",
            configured=is_configured,
            enabled=self.enabled,
            operational_status=status,
            last_checked_at=self.last_checked_at,
            last_success_at=self.last_success_at,
            message=message,
        )
