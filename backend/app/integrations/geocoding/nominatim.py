"""Nominatim Geocoding Integration.

Provides forward and reverse geocoding using OpenStreetMap Nominatim.
Adheres strictly to the Nominatim Usage Policy:
- Custom, identifiable User-Agent header.
- Strict 1 request per second throttling via IntervalRateLimiter.
- In-memory TTL caching of geocode lookups to minimize remote hits.
- Standardized candidate normalization into Pydantic models.
- Graceful degradation when network or service errors occur.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.integrations.base import (
    InMemoryTTLCache,
    IntervalRateLimiter,
    generate_cache_key,
    sanitize_url_for_logging,
)
from app.schemas.external_data import (
    ForwardGeocodeResponse,
    GeocodingCandidate,
    ProviderHealth,
    ReverseGeocodeResponse,
)

logger = logging.getLogger("eventprice.integrations.nominatim")


class NominatimClient:
    """Client for OpenStreetMap Nominatim forward and reverse geocoding."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        user_agent: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        enabled: Optional[bool] = None,
        cache_ttl_seconds: int = 86400,  # 24 hours for geocoding
    ):
        self.base_url = (base_url or settings.NOMINATIM_BASE_URL).rstrip("/")
        self.user_agent = user_agent or settings.NOMINATIM_USER_AGENT
        self.timeout = timeout_seconds or settings.NOMINATIM_TIMEOUT_SECONDS
        self.enabled = enabled if enabled is not None else settings.NOMINATIM_ENABLED
        self.cache = InMemoryTTLCache(default_ttl_seconds=cache_ttl_seconds, max_entries=2000)
        self.rate_limiter = IntervalRateLimiter(min_interval_seconds=1.0)
        
        # Operational health metrics
        self.last_checked_at: Optional[datetime] = None
        self.last_success_at: Optional[datetime] = None
        self.last_error: Optional[str] = None

    def _headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

    def _extract_locality(self, address: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Extracts city, locality, state, country, postal code from address dict."""
        city = (
            address.get("city")
            or address.get("town")
            or address.get("municipality")
            or address.get("village")
        )
        locality = (
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("residential")
            or address.get("city_district")
            or address.get("county")
            or city
        )
        state = address.get("state")
        country = address.get("country")
        postal_code = address.get("postcode")
        return city, locality, state, country, postal_code

    def forward_geocode(
        self,
        query: str,
        limit: int = 5,
        country_code: Optional[str] = "in",
    ) -> ForwardGeocodeResponse:
        """Forward geocode a location query to coordinate candidates.
        
        Args:
            query: Location query string (e.g. 'Banjara Hills, Hyderabad').
            limit: Maximum number of candidates to return (default 5, max 20).
            country_code: Optional ISO country code bias (defaults to 'in' for India).
        """
        now = datetime.now(timezone.utc)
        self.last_checked_at = now

        if not self.enabled:
            return ForwardGeocodeResponse(
                query=query,
                total_candidates=0,
                candidates=[],
                provider="Nominatim (Disabled)",
                attribution="Nominatim integration is currently disabled in backend settings.",
            )

        clean_query = query.strip()
        if not clean_query:
            return ForwardGeocodeResponse(
                query=query,
                total_candidates=0,
                candidates=[],
            )

        # Check Cache
        cache_key = generate_cache_key("nominatim:forward", {"q": clean_query.lower(), "limit": limit, "cc": country_code})
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            # Return cached response marked as cached
            cached_copy = cached_result.model_copy()
            cached_copy.is_cached = True
            return cached_copy

        params: Dict[str, Any] = {
            "q": clean_query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": min(max(1, limit), 20),
        }
        if country_code:
            params["countrycodes"] = country_code.lower()

        search_url = f"{self.base_url}/search"

        try:
            # Respect 1 req/sec policy
            self.rate_limiter.acquire()

            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    search_url,
                    params=params,
                    headers=self._headers(),
                )
                response.raise_for_status()
                raw_data = response.json()

            candidates: List[GeocodingCandidate] = []
            if isinstance(raw_data, list):
                for item in raw_data:
                    try:
                        lat = float(item["lat"])
                        lon = float(item["lon"])
                        address = item.get("address", {})
                        city, locality, state, country, postal = self._extract_locality(address)

                        candidate = GeocodingCandidate(
                            place_id=str(item.get("place_id", "")),
                            display_name=item.get("display_name", ""),
                            latitude=lat,
                            longitude=lon,
                            locality=locality,
                            city=city,
                            state=state,
                            country=country,
                            postal_code=postal,
                            osm_type=item.get("osm_type"),
                            osm_id=int(item["osm_id"]) if item.get("osm_id") is not None else None,
                            category=item.get("category"),
                            type=item.get("type"),
                        )
                        candidates.append(candidate)
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Skipping malformed Nominatim candidate item: {e}")
                        continue

            result = ForwardGeocodeResponse(
                query=clean_query,
                total_candidates=len(candidates),
                candidates=candidates,
                is_cached=False,
                retrieved_at=now,
            )

            # Store in cache
            self.cache.set(cache_key, result)
            self.last_success_at = now
            self.last_error = None
            return result

        except httpx.HTTPStatusError as e:
            self.last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            logger.error(f"Nominatim forward geocode HTTP error for '{clean_query}': {self.last_error}")
            return ForwardGeocodeResponse(
                query=clean_query,
                total_candidates=0,
                candidates=[],
                attribution=f"Error contacting Nominatim: HTTP {e.response.status_code}",
            )
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Nominatim forward geocode failed for '{clean_query}': {e}")
            return ForwardGeocodeResponse(
                query=clean_query,
                total_candidates=0,
                candidates=[],
                attribution=f"Error contacting Nominatim: {type(e).__name__}",
            )

    def reverse_geocode(
        self,
        latitude: float,
        longitude: float,
    ) -> ReverseGeocodeResponse:
        """Reverse geocode latitude and longitude to an address."""
        now = datetime.now(timezone.utc)
        self.last_checked_at = now

        if not self.enabled:
            return ReverseGeocodeResponse(
                latitude=latitude,
                longitude=longitude,
                display_name="Nominatim integration disabled",
                attribution="Nominatim integration is currently disabled in backend settings.",
            )

        # Coordinate rounding for caching (approx 10-meter precision)
        rounded_lat = round(latitude, 4)
        rounded_lon = round(longitude, 4)
        cache_key = generate_cache_key("nominatim:reverse", {"lat": rounded_lat, "lon": rounded_lon})

        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            cached_copy = cached_result.model_copy()
            cached_copy.is_cached = True
            return cached_copy

        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "jsonv2",
            "addressdetails": 1,
        }
        reverse_url = f"{self.base_url}/reverse"

        try:
            self.rate_limiter.acquire()

            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    reverse_url,
                    params=params,
                    headers=self._headers(),
                )
                response.raise_for_status()
                item = response.json()

            display_name = item.get("display_name", f"Coordinates ({latitude:.4f}, {longitude:.4f})")
            address = item.get("address", {})

            result = ReverseGeocodeResponse(
                latitude=latitude,
                longitude=longitude,
                display_name=display_name,
                address_components=address,
                is_cached=False,
                retrieved_at=now,
            )

            self.cache.set(cache_key, result)
            self.last_success_at = now
            self.last_error = None
            return result

        except httpx.HTTPStatusError as e:
            self.last_error = f"HTTP {e.response.status_code}"
            logger.error(f"Nominatim reverse geocode error: {self.last_error}")
            return ReverseGeocodeResponse(
                latitude=latitude,
                longitude=longitude,
                display_name=f"Location at ({latitude:.4f}, {longitude:.4f})",
                attribution=f"Error contacting Nominatim: HTTP {e.response.status_code}",
            )
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Nominatim reverse geocode failed: {e}")
            return ReverseGeocodeResponse(
                latitude=latitude,
                longitude=longitude,
                display_name=f"Location at ({latitude:.4f}, {longitude:.4f})",
                attribution=f"Error contacting Nominatim: {type(e).__name__}",
            )

    def get_health(self) -> ProviderHealth:
        """Returns the operational status of the Nominatim integration."""
        is_configured = bool(self.base_url and self.user_agent)
        status = "ready"
        message = "Nominatim geocoding provider is operational."

        if not self.enabled:
            status = "disabled"
            message = "Nominatim geocoding is disabled in configuration."
        elif not is_configured:
            status = "unconfigured"
            message = "Nominatim configuration is incomplete."
        elif self.last_error:
            status = "degraded"
            message = f"Recent error: {self.last_error}"

        return ProviderHealth(
            provider="Nominatim (OpenStreetMap)",
            configured=is_configured,
            enabled=self.enabled,
            operational_status=status,
            last_checked_at=self.last_checked_at,
            last_success_at=self.last_success_at,
            message=message,
        )


# Type alias for helper return
Tuple_Locality = tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]

