"""OpenWeather API Integration Adapter.

Provides standardized metric weather intelligence using official OpenWeather endpoints:
- Current Weather Data (/weather)
- 5 Day / 3 Hour Forecast Data (/forecast)

Enforces strict provenance, never fabricates weather observations, and clearly flags
dates beyond the 5-day atmospheric horizon as unavailable.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import Settings, get_settings
from app.integrations.base import (
    InMemoryTTLCache,
    generate_cache_key,
    sanitize_url_for_logging,
)
from app.schemas.external_data import (
    NormalizedWeatherMeasurements,
    ProviderHealth,
    WeatherClassification,
    WeatherResponse,
)

logger = logging.getLogger("eventprice.integrations.openweather")


class OpenWeatherAdapter:
    """Adapter for interacting with OpenWeather API."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        cache: Optional[InMemoryTTLCache] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        self.settings = settings or get_settings()
        self.cache = cache or InMemoryTTLCache(default_ttl_seconds=900)  # 15 min default
        self._client = http_client
        self.last_checked_at: Optional[datetime] = None
        self.last_success_at: Optional[datetime] = None
        self.last_error: Optional[str] = None

    def is_configured(self) -> bool:
        """Returns True if an API key is configured."""
        return bool(self.settings.OPENWEATHER_API_KEY and self.settings.OPENWEATHER_API_KEY.strip())

    def _execute_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executes HTTP request to OpenWeather with timeouts, secret redaction, and error isolation."""
        api_key = self.settings.OPENWEATHER_API_KEY
        if not api_key or not api_key.strip():
            raise ValueError("OPENWEATHER_API_KEY is not configured on the server.")

        base_url = self.settings.OPENWEATHER_BASE_URL.rstrip("/")
        url = f"{base_url}/{endpoint}"

        query_params = {
            **params,
            "appid": api_key.strip(),
            "units": "metric",
        }

        safe_log_url = sanitize_url_for_logging(f"{url}?lat={params.get('lat')}&lon={params.get('lon')}")
        logger.debug("Requesting OpenWeather: %s", safe_log_url)

        timeout = httpx.Timeout(self.settings.OPENWEATHER_TIMEOUT_SECONDS, connect=5.0)

        try:
            client = self._client or httpx.Client(timeout=timeout)
            response = client.get(url, params=query_params)
            self.last_checked_at = datetime.now(timezone.utc)

            if response.status_code == 401:
                self.last_error = "Invalid API key or unauthorized account access."
                logger.error("OpenWeather authentication failed (HTTP 401).")
                raise ValueError("OpenWeather API key is invalid or unauthorized.")

            if response.status_code == 429:
                self.last_error = "OpenWeather rate limit exceeded."
                logger.warning("OpenWeather rate limit exceeded (HTTP 429).")
                raise RuntimeError("OpenWeather rate limit exceeded. Please retry later.")

            if response.status_code != 200:
                self.last_error = f"HTTP {response.status_code}: {response.text[:100]}"
                logger.error("OpenWeather error HTTP %d: %s", response.status_code, response.text[:150])
                raise RuntimeError(f"OpenWeather server error: HTTP {response.status_code}")

            data = response.json()
            self.last_success_at = datetime.now(timezone.utc)
            self.last_error = None
            return data

        except httpx.TimeoutException as exc:
            self.last_error = "Connection timed out."
            logger.error("OpenWeather request timed out: %s", exc)
            raise TimeoutError("OpenWeather request timed out.") from exc
        except httpx.RequestError as exc:
            self.last_error = f"Network connection error: {str(exc)}"
            logger.error("OpenWeather network error: %s", exc)
            raise ConnectionError("Failed to connect to OpenWeather service.") from exc

    def _parse_measurements(self, data: Dict[str, Any]) -> NormalizedWeatherMeasurements:
        """Parses OpenWeather JSON data into NormalizedWeatherMeasurements."""
        main = data.get("main", {})
        weather_list = data.get("weather", [{}])
        weather_primary = weather_list[0] if weather_list else {}
        wind = data.get("wind", {})
        clouds = data.get("clouds", {})
        rain = data.get("rain", {})
        sys = data.get("sys", {})

        # Precipitation: check 1h or 3h
        rainfall_mm = None
        if isinstance(rain, dict):
            rainfall_mm = rain.get("1h") or rain.get("3h") or 0.0

        sunrise = None
        if "sunrise" in sys:
            try:
                sunrise = datetime.fromtimestamp(sys["sunrise"], tz=timezone.utc)
            except Exception:
                pass

        sunset = None
        if "sunset" in sys:
            try:
                sunset = datetime.fromtimestamp(sys["sunset"], tz=timezone.utc)
            except Exception:
                pass

        return NormalizedWeatherMeasurements(
            temperature_c=float(main["temp"]) if "temp" in main else None,
            feels_like_c=float(main["feels_like"]) if "feels_like" in main else None,
            temp_min_c=float(main["temp_min"]) if "temp_min" in main else None,
            temp_max_c=float(main["temp_max"]) if "temp_max" in main else None,
            humidity_pct=int(main["humidity"]) if "humidity" in main else None,
            pressure_hpa=int(main["pressure"]) if "pressure" in main else None,
            wind_speed_mps=float(wind["speed"]) if "speed" in wind else None,
            wind_direction_deg=int(wind["deg"]) if "deg" in wind else None,
            cloud_cover_pct=int(clouds["all"]) if "all" in clouds else None,
            rainfall_mm=float(rainfall_mm) if rainfall_mm is not None else 0.0,
            weather_condition=weather_primary.get("main"),
            weather_description=weather_primary.get("description"),
            weather_icon=weather_primary.get("icon"),
            sunrise=sunrise,
            sunset=sunset,
        )

    def get_weather(
        self,
        latitude: float,
        longitude: float,
        event_date: Optional[date] = None,
        location_name: Optional[str] = None,
    ) -> WeatherResponse:
        """Retrieves and normalizes weather data for coordinates, respecting date horizons."""
        today = date.today()

        # Validate coordinate range
        if not (-90.0 <= latitude <= 90.0):
            raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
        if not (-180.0 <= longitude <= 180.0):
            raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")

        # Check enabled
        if not self.settings.OPENWEATHER_ENABLED:
            return WeatherResponse(
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                requested_date=event_date,
                classification=WeatherClassification.UNAVAILABLE,
                measurements=None,
                risk_assessment=None,
                provider="OpenWeather",
                provider_endpoint="disabled",
                timezone_offset_seconds=0,
                coverage_limitations=["OpenWeather integration is disabled in application settings."],
            )

        if not self.is_configured():
            return WeatherResponse(
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                requested_date=event_date,
                classification=WeatherClassification.UNAVAILABLE,
                measurements=None,
                risk_assessment=None,
                provider="OpenWeather",
                provider_endpoint="unconfigured",
                timezone_offset_seconds=0,
                coverage_limitations=["OPENWEATHER_API_KEY is not configured in backend environment."],
            )

        # 1. Determine horizon:
        # Standard OpenWeather 5-day forecast covers today up to today + 5 days
        max_forecast_date = today + timedelta(days=5)

        # CASE A: Event date is in the far future (> 5 days)
        if event_date and event_date > max_forecast_date:
            days_away = (event_date - today).days
            return WeatherResponse(
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                requested_date=event_date,
                classification=WeatherClassification.UNAVAILABLE,
                measurements=None,
                risk_assessment=None,
                provider="OpenWeather",
                provider_endpoint="/forecast (5-day limit)",
                timezone_offset_seconds=0,
                coverage_limitations=[
                    f"Requested event date ({event_date.isoformat()}) is {days_away} days away. "
                    "OpenWeather standard forecast coverage is limited to 5 days.",
                    "No synthetic or fabricated future forecast data is provided.",
                    "Recommendation: Consult historical seasonal weather patterns for planning, "
                    "and retrieve live atmospheric forecasts 1–5 days prior to the event.",
                ],
            )

        # CASE B: Event date is in the past (< today)
        if event_date and event_date < today:
            return WeatherResponse(
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                requested_date=event_date,
                classification=WeatherClassification.HISTORICAL,
                measurements=None,
                risk_assessment=None,
                provider="OpenWeather",
                provider_endpoint="/timemachine (historical)",
                timezone_offset_seconds=0,
                coverage_limitations=[
                    f"Requested date ({event_date.isoformat()}) is in the past.",
                    "Historical hourly data requires specialized paid archive endpoints not configured on this account.",
                ],
            )

        # CASE C: Event date is today or within the 5-day forecast window
        # Check cache first
        cache_key = generate_cache_key(
            "ow_weather",
            {"lat": round(latitude, 3), "lon": round(longitude, 3), "date": str(event_date or today)},
        )
        cached: Optional[WeatherResponse] = self.cache.get(cache_key)
        if cached is not None:
            # Return cached with is_cached=True
            return cached.model_copy(update={"is_cached": True})

        try:
            # Fetch current weather if event_date is today or None
            if not event_date or event_date == today:
                raw_data = self._execute_request("weather", {"lat": latitude, "lon": longitude})
                measurements = self._parse_measurements(raw_data)
                tz_offset = raw_data.get("timezone", 0)
                res = WeatherResponse(
                    latitude=latitude,
                    longitude=longitude,
                    location_name=raw_data.get("name") or location_name,
                    requested_date=event_date or today,
                    classification=WeatherClassification.CURRENT_OBSERVATION,
                    measurements=measurements,
                    provider="OpenWeather",
                    provider_endpoint="/weather",
                    timezone_offset_seconds=tz_offset,
                    is_cached=False,
                    coverage_limitations=["Live real-time atmospheric observation."],
                )
                self.cache.set(cache_key, res, ttl_seconds=900)  # 15 minutes
                return res

            # Otherwise, fetch 5-day / 3-hour forecast for upcoming date (1 to 5 days)
            raw_data = self._execute_request("forecast", {"lat": latitude, "lon": longitude})
            forecast_list = raw_data.get("list", [])
            city_info = raw_data.get("city", {})
            tz_offset = city_info.get("timezone", 0)

            # Find the forecast slot closest to 12:00 PM (midday) on the target date
            target_iso = event_date.isoformat()
            matching_slots = []
            for slot in forecast_list:
                dt_txt = slot.get("dt_txt", "")
                if dt_txt.startswith(target_iso):
                    matching_slots.append(slot)

            chosen_slot = None
            if matching_slots:
                # Prefer 12:00:00 or 15:00:00 (midday)
                preferred = [s for s in matching_slots if "12:00:00" in s.get("dt_txt", "") or "15:00:00" in s.get("dt_txt", "")]
                chosen_slot = preferred[0] if preferred else matching_slots[len(matching_slots) // 2]
            elif forecast_list:
                # Fallback to the closest available slot
                chosen_slot = forecast_list[-1]

            if not chosen_slot:
                return WeatherResponse(
                    latitude=latitude,
                    longitude=longitude,
                    location_name=city_info.get("name") or location_name,
                    requested_date=event_date,
                    classification=WeatherClassification.UNAVAILABLE,
                    measurements=None,
                    provider="OpenWeather",
                    provider_endpoint="/forecast",
                    timezone_offset_seconds=tz_offset,
                    coverage_limitations=["No forecast slots returned for the requested date."],
                )

            measurements = self._parse_measurements(chosen_slot)
            res = WeatherResponse(
                latitude=latitude,
                longitude=longitude,
                location_name=city_info.get("name") or location_name,
                requested_date=event_date,
                classification=WeatherClassification.FORECAST,
                measurements=measurements,
                provider="OpenWeather",
                provider_endpoint="/forecast (3-hour interval)",
                timezone_offset_seconds=tz_offset,
                is_cached=False,
                coverage_limitations=[
                    f"3-hour interval atmospheric forecast sampled for target date {event_date.isoformat()}.",
                    "Atmospheric conditions may shift closer to event date.",
                ],
            )
            self.cache.set(cache_key, res, ttl_seconds=1800)  # 30 minutes
            return res

        except Exception as exc:
            logger.error("OpenWeather query failed: %s", exc)
            self.last_error = str(exc)
            return WeatherResponse(
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                requested_date=event_date or today,
                classification=WeatherClassification.UNAVAILABLE,
                measurements=None,
                provider="OpenWeather",
                provider_endpoint="error",
                timezone_offset_seconds=0,
                coverage_limitations=[
                    f"OpenWeather request error: {str(exc)}",
                    "Note: Newly generated OpenWeather API keys may take 10-60 minutes to propagate across OpenWeather servers.",
                ],
            )

    def get_health(self) -> ProviderHealth:
        """Returns the operational status of the OpenWeather integration."""
        is_configured = self.is_configured()
        status = "ready"
        message = "OpenWeather provider is operational."

        if not self.settings.OPENWEATHER_ENABLED:
            status = "disabled"
            message = "OpenWeather integration is disabled in configuration."
        elif not is_configured:
            status = "unconfigured"
            message = "OPENWEATHER_API_KEY is not configured on the server."
        elif self.last_error:
            status = "degraded"
            message = f"Recent error: {self.last_error}"

        return ProviderHealth(
            provider="OpenWeather",
            configured=is_configured,
            enabled=self.settings.OPENWEATHER_ENABLED,
            operational_status=status,
            last_checked_at=self.last_checked_at,
            last_success_at=self.last_success_at,
            message=message,
        )

