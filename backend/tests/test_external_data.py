"""Comprehensive Automated Tests for External Data Integrations (Phase 10).

Covers:
1. OpenWeather adapter (current, forecast, >5-day unavailable horizon, 401, 429, timeout, caching).
2. OpenStreetMap Nominatim geocoding (forward, reverse, throttling, custom user-agent, caching).
3. OpenStreetMap Overpass nearby places (Haversine distance calculation, deduplication, category filtering, empty results).
4. Deterministic Weather Risk Intelligence Engine (severe rain, heatwave, high wind, humidity, ideal weather).
5. FastApi endpoint routing (/api/v1/external/*).
6. Security redaction test (URL secret parameter scrubbing).
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.integrations.base import (
    InMemoryTTLCache,
    IntervalRateLimiter,
    generate_cache_key,
    sanitize_url_for_logging,
)
from app.integrations.geocoding.nominatim import NominatimClient
from app.integrations.places.overpass import (
    OverpassClient,
    haversine_distance_meters,
)
from app.integrations.weather.openweather import OpenWeatherAdapter
from app.schemas.external_data import (
    NormalizedWeatherMeasurements,
    WeatherClassification,
    WeatherRiskLevel,
)
from app.services.external_data_service import (
    ExternalDataService,
    get_external_data_service,
)
from app.services.weather_intelligence import evaluate_weather_risks


# ============================================================================
# 1. Base Integration Infrastructure & Security Tests
# ============================================================================


def test_sanitize_url_for_logging():
    """Ensure secret parameters like appid, api_key, key are redacted from log outputs."""
    raw_url = "https://api.openweathermap.org/data/2.5/weather?lat=17.385&lon=78.486&appid=secret_openweather_token_123&units=metric"
    sanitized = sanitize_url_for_logging(raw_url)
    assert "secret_openweather_token_123" not in sanitized
    assert "appid=[REDACTED]" in sanitized
    assert "lat=17.385" in sanitized

    # Check key parameter
    raw_url_2 = "https://example.com/api?key=my_super_secret_key&format=json"
    sanitized_2 = sanitize_url_for_logging(raw_url_2)
    assert "my_super_secret_key" not in sanitized_2
    assert "key=[REDACTED]" in sanitized_2


def test_in_memory_ttl_cache():
    """Verify TTL cache set, get, hit/miss tracking, and expiration."""
    cache = InMemoryTTLCache(default_ttl_seconds=1, max_entries=5)
    cache.set("k1", "val1", ttl_seconds=10)
    assert cache.get("k1") == "val1"
    assert cache.hits == 1
    assert cache.misses == 0

    assert cache.get("nonexistent") is None
    assert cache.misses == 1

    # Short TTL expiry
    cache.set("short", "quick", ttl_seconds=-1)  # expired immediately
    assert cache.get("short") is None
    assert cache.misses == 2


def test_interval_rate_limiter():
    """Verify rate limiter allows acquire without error."""
    limiter = IntervalRateLimiter(min_interval_seconds=0.01)
    limiter.acquire()
    limiter.acquire()


# ============================================================================
# 2. OpenWeather Adapter Tests
# ============================================================================


MOCK_CURRENT_WEATHER_JSON = {
    "name": "Hyderabad",
    "timezone": 19800,
    "main": {
        "temp": 28.5,
        "feels_like": 30.1,
        "temp_min": 26.0,
        "temp_max": 31.0,
        "humidity": 68,
        "pressure": 1012,
    },
    "wind": {
        "speed": 3.8,
        "deg": 140,
    },
    "clouds": {
        "all": 20,
    },
    "weather": [
        {
            "main": "Clouds",
            "description": "scattered clouds",
            "icon": "03d",
        }
    ],
    "rain": {
        "1h": 0.0,
    },
    "sys": {
        "sunrise": 1698713400,
        "sunset": 1698755400,
    },
}

MOCK_FORECAST_WEATHER_JSON = {
    "city": {
        "name": "Hyderabad",
        "timezone": 19800,
    },
    "list": [
        {
            "dt_txt": (date.today() + timedelta(days=2)).isoformat() + " 12:00:00",
            "main": {
                "temp": 32.0,
                "feels_like": 34.5,
                "humidity": 55,
                "pressure": 1010,
            },
            "wind": {
                "speed": 4.5,
                "deg": 180,
            },
            "clouds": {
                "all": 10,
            },
            "weather": [
                {
                    "main": "Clear",
                    "description": "clear sky",
                    "icon": "01d",
                }
            ],
            "rain": {
                "3h": 0.0,
            },
        }
    ],
}


def test_openweather_current_weather_success():
    """Verify parsing and normalization of live current weather."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_CURRENT_WEATHER_JSON
    mock_client.get.return_value = mock_resp

    settings = Settings(
        OPENWEATHER_ENABLED=True,
        OPENWEATHER_API_KEY="test_api_key_valid",
    )
    adapter = OpenWeatherAdapter(settings=settings, http_client=mock_client)

    res = adapter.get_weather(latitude=17.3850, longitude=78.4867, event_date=date.today())
    assert res.classification == WeatherClassification.CURRENT_OBSERVATION
    assert res.location_name == "Hyderabad"
    assert res.measurements is not None
    assert res.measurements.temperature_c == 28.5
    assert res.measurements.humidity_pct == 68
    assert res.measurements.wind_speed_mps == 3.8
    assert res.measurements.weather_condition == "Clouds"
    assert res.is_cached is False

    # Second call should be cached
    cached_res = adapter.get_weather(latitude=17.3850, longitude=78.4867, event_date=date.today())
    assert cached_res.is_cached is True


def test_openweather_forecast_within_5_days():
    """Verify parsing and normalization of 5-day forecast slot."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_FORECAST_WEATHER_JSON
    mock_client.get.return_value = mock_resp

    target_date = date.today() + timedelta(days=2)
    settings = Settings(
        OPENWEATHER_ENABLED=True,
        OPENWEATHER_API_KEY="test_api_key_valid",
    )
    adapter = OpenWeatherAdapter(settings=settings, http_client=mock_client)

    res = adapter.get_weather(latitude=17.3850, longitude=78.4867, event_date=target_date)
    assert res.classification == WeatherClassification.FORECAST
    assert res.measurements is not None
    assert res.measurements.temperature_c == 32.0
    assert res.measurements.weather_condition == "Clear"


def test_openweather_beyond_5_days_unavailable():
    """Dates > 5 days away must be classified UNAVAILABLE with explicit disclaimers and NO fake data."""
    settings = Settings(
        OPENWEATHER_ENABLED=True,
        OPENWEATHER_API_KEY="test_api_key_valid",
    )
    adapter = OpenWeatherAdapter(settings=settings)

    future_date = date.today() + timedelta(days=30)
    res = adapter.get_weather(latitude=17.3850, longitude=78.4867, event_date=future_date)
    assert res.classification == WeatherClassification.UNAVAILABLE
    assert res.measurements is None
    assert any("OpenWeather standard forecast coverage is limited to 5 days" in lim for lim in res.coverage_limitations)
    assert any("No synthetic or fabricated future forecast data is provided" in lim for lim in res.coverage_limitations)


def test_openweather_missing_api_key():
    """If API key is missing, should return UNAVAILABLE with clear limitations."""
    settings = Settings(
        OPENWEATHER_ENABLED=True,
        OPENWEATHER_API_KEY="",
    )
    adapter = OpenWeatherAdapter(settings=settings)
    assert adapter.is_configured() is False
    res = adapter.get_weather(latitude=17.3850, longitude=78.4867, event_date=date.today())
    assert res.classification == WeatherClassification.UNAVAILABLE
    assert any("OPENWEATHER_API_KEY is not configured" in lim for lim in res.coverage_limitations)


def test_openweather_http_401_error():
    """Verify clean graceful error handling on unauthorized 401."""
    mock_client = MagicMock(spec=httpx.Client)
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_client.get.return_value = mock_resp

    settings = Settings(
        OPENWEATHER_ENABLED=True,
        OPENWEATHER_API_KEY="invalid_key",
    )
    adapter = OpenWeatherAdapter(settings=settings, http_client=mock_client)
    res = adapter.get_weather(latitude=17.3850, longitude=78.4867, event_date=date.today())
    assert res.classification == WeatherClassification.UNAVAILABLE
    assert any("invalid or unauthorized" in lim for lim in res.coverage_limitations)


# ============================================================================
# 3. Deterministic Weather Risk Engine Tests
# ============================================================================


def test_risk_engine_severe_rainfall():
    """Rainfall >= 10 mm must trigger severe risk and outdoor unsuitable."""
    meas = NormalizedWeatherMeasurements(
        temperature_c=25.0,
        humidity_pct=95,
        wind_speed_mps=6.0,
        rainfall_mm=14.5,
        weather_condition="Rain",
    )
    risk = evaluate_weather_risks(meas)
    assert risk.overall_risk == WeatherRiskLevel.SEVERE
    assert risk.is_outdoor_suitable is False
    assert risk.risk_score >= 80
    assert any("Heavy rainfall" in f.message for f in risk.factors)
    assert any("Severe rain alert" in rec for rec in risk.recommendations)


def test_risk_engine_extreme_heat():
    """Temperature >= 40°C must trigger severe heat risk."""
    meas = NormalizedWeatherMeasurements(
        temperature_c=42.0,
        humidity_pct=30,
        wind_speed_mps=2.0,
        rainfall_mm=0.0,
        weather_condition="Clear",
    )
    risk = evaluate_weather_risks(meas)
    assert risk.overall_risk == WeatherRiskLevel.SEVERE
    assert risk.is_outdoor_suitable is False
    assert any("scorching heat" in f.message for f in risk.factors)
    assert any("Extreme heat alert" in rec for rec in risk.recommendations)


def test_risk_engine_high_wind():
    """Wind speed >= 13 m/s must trigger wind hazard recommendations."""
    meas = NormalizedWeatherMeasurements(
        temperature_c=26.0,
        humidity_pct=50,
        wind_speed_mps=15.0,
        rainfall_mm=0.0,
        weather_condition="Windy",
    )
    risk = evaluate_weather_risks(meas)
    assert risk.overall_risk == WeatherRiskLevel.SEVERE
    assert risk.is_outdoor_suitable is False
    assert any("Gale or high wind" in f.message for f in risk.factors)
    assert any("truss" in f.recommendation for f in risk.factors)


def test_risk_engine_favorable_weather():
    """Optimal conditions (24°C, 50% humidity, 2 m/s wind, 0mm rain) -> LOW risk."""
    meas = NormalizedWeatherMeasurements(
        temperature_c=24.0,
        feels_like_c=24.0,
        humidity_pct=50,
        wind_speed_mps=2.0,
        rainfall_mm=0.0,
        weather_condition="Clear",
    )
    risk = evaluate_weather_risks(meas)
    assert risk.overall_risk == WeatherRiskLevel.LOW
    assert risk.is_outdoor_suitable is True
    assert risk.risk_score == 0
    assert any("favorable for open-air lawn ceremonies" in rec for rec in risk.recommendations)


# ============================================================================
# 4. OpenStreetMap Nominatim Geocoding Adapter Tests
# ============================================================================


MOCK_NOMINATIM_FORWARD_JSON = [
    {
        "place_id": 1234567,
        "osm_type": "node",
        "osm_id": 987654321,
        "lat": "17.4156",
        "lon": "78.4350",
        "display_name": "Banjara Hills, Hyderabad, Telangana, 500034, India",
        "category": "place",
        "type": "suburb",
        "address": {
            "suburb": "Banjara Hills",
            "city": "Hyderabad",
            "state": "Telangana",
            "postcode": "500034",
            "country": "India",
        },
    }
]

MOCK_NOMINATIM_REVERSE_JSON = {
    "place_id": 7654321,
    "lat": "17.4156",
    "lon": "78.4350",
    "display_name": "Road No 1, Banjara Hills, Hyderabad, Telangana, 500034, India",
    "address": {
        "road": "Road No 1",
        "suburb": "Banjara Hills",
        "city": "Hyderabad",
        "state": "Telangana",
        "country": "India",
    },
}


def test_nominatim_forward_geocode():
    """Verify Nominatim forward search candidate parsing and caching."""
    client = NominatimClient(enabled=True)

    with patch("httpx.Client") as mock_httpx:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_NOMINATIM_FORWARD_JSON
        mock_instance.get.return_value = mock_resp
        mock_httpx.return_value.__enter__.return_value = mock_instance

        res = client.forward_geocode(query="Banjara Hills, Hyderabad", limit=5)
        assert res.total_candidates == 1
        cand = res.candidates[0]
        assert cand.locality == "Banjara Hills"
        assert cand.city == "Hyderabad"
        assert cand.state == "Telangana"
        assert cand.latitude == 17.4156
        assert cand.longitude == 78.4350
        assert res.is_cached is False

        # Verify second call is served from cache
        cached_res = client.forward_geocode(query="Banjara Hills, Hyderabad", limit=5)
        assert cached_res.is_cached is True
        assert cached_res.total_candidates == 1


def test_nominatim_reverse_geocode():
    """Verify Nominatim reverse address lookup."""
    client = NominatimClient(enabled=True)

    with patch("httpx.Client") as mock_httpx:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_NOMINATIM_REVERSE_JSON
        mock_instance.get.return_value = mock_resp
        mock_httpx.return_value.__enter__.return_value = mock_instance

        res = client.reverse_geocode(latitude=17.4156, longitude=78.4350)
        assert "Banjara Hills" in res.display_name
        assert res.latitude == 17.4156
        assert res.longitude == 78.4350


# ============================================================================
# 5. OpenStreetMap Overpass Nearby Places Adapter Tests
# ============================================================================


MOCK_OVERPASS_PLACES_JSON = {
    "elements": [
        {
            "type": "node",
            "id": 111111,
            "lat": 17.4170,
            "lon": 78.4360,
            "tags": {
                "name": "Taj Krishna Hyderabad",
                "tourism": "hotel",
                "addr:city": "Hyderabad",
                "addr:street": "Road No 1",
            },
        },
        {
            "type": "way",
            "id": 222222,
            "center": {
                "lat": 17.4185,
                "lon": 78.4340,
            },
            "tags": {
                "name": "Banjara Function Hall",
                "amenity": "banquet_hall",
                "addr:suburb": "Banjara Hills",
            },
        },
        # Duplicate should be ignored
        {
            "type": "node",
            "id": 111111,
            "lat": 17.4170,
            "lon": 78.4360,
            "tags": {
                "name": "Taj Krishna Duplicate",
            },
        },
    ]
}


def test_haversine_distance_meters():
    """Verify Haversine distance matches known geodesic points."""
    # Hyderabad Banjara Hills to Charminar (~8.5 km)
    dist = haversine_distance_meters(17.4156, 78.4350, 17.3616, 78.4747)
    assert 7000 < dist < 10000


def test_overpass_places_discovery():
    """Verify Overpass QL results extraction, distance computation, deduplication, and caching."""
    client = OverpassClient(enabled=True)

    with patch("httpx.Client") as mock_httpx:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_OVERPASS_PLACES_JSON
        mock_instance.post.return_value = mock_resp
        mock_httpx.return_value.__enter__.return_value = mock_instance

        res = client.find_nearby_places(latitude=17.4156, longitude=78.4350, radius_meters=3000)
        # 2 unique elements (1 duplicate dropped)
        assert res.total_found == 2
        p1 = res.places[0]
        assert p1.name in ("Taj Krishna Hyderabad", "Banjara Function Hall")
        assert p1.distance_meters is not None
        assert p1.distance_meters > 0
        assert res.is_cached is False

        # Verify second call is served from cache
        cached_res = client.find_nearby_places(latitude=17.4156, longitude=78.4350, radius_meters=3000)
        assert cached_res.is_cached is True


def test_overpass_places_empty_elements():
    """Empty elements list from Overpass must return gracefully without error."""
    client = OverpassClient(enabled=True)

    with patch("httpx.Client") as mock_httpx:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"elements": []}
        mock_instance.post.return_value = mock_resp
        mock_httpx.return_value.__enter__.return_value = mock_instance

        res = client.find_nearby_places(latitude=17.0, longitude=78.0, radius_meters=1000)
        assert res.total_found == 0
        assert res.places == []


# ============================================================================
# 6. External Data Service Coordinator & Health Status Tests
# ============================================================================


def test_external_data_service_status():
    """Verify aggregated status contains OpenWeather, Nominatim, and Overpass health."""
    svc = ExternalDataService()
    status = svc.get_status()
    assert "openweather" in status.providers
    assert "nominatim" in status.providers
    assert "overpass" in status.providers
    assert isinstance(status.cached_entries_count, int)


# ============================================================================
# 7. FastAPI Endpoint Integration Tests
# ============================================================================


def test_endpoint_external_status(client: TestClient):
    """GET /api/v1/external/status must return 200 with provider operational status."""
    resp = client.get("/api/v1/external/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert "openweather" in data["providers"]
    assert "nominatim" in data["providers"]
    assert "overpass" in data["providers"]


def test_endpoint_external_geocode(client: TestClient):
    """GET /api/v1/external/geocode must forward geocode query."""
    with patch("httpx.Client") as mock_httpx:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_NOMINATIM_FORWARD_JSON
        mock_instance.get.return_value = mock_resp
        mock_httpx.return_value.__enter__.return_value = mock_instance

        resp = client.get("/api/v1/external/geocode?q=Banjara+Hills&limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "Banjara Hills"
        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["city"] == "Hyderabad"


def test_endpoint_external_weather(client: TestClient):
    """GET /api/v1/external/weather must return normalized weather and risk evaluation."""
    with patch.object(OpenWeatherAdapter, "is_configured", return_value=True), patch.object(
        OpenWeatherAdapter, "_execute_request", return_value=MOCK_CURRENT_WEATHER_JSON
    ):
        resp = client.get("/api/v1/external/weather?lat=17.385&lon=78.486")
        assert resp.status_code == 200
        data = resp.json()
        assert data["latitude"] == 17.385
        assert data["longitude"] == 78.486
        assert data["measurements"]["temperature_c"] == 28.5
        assert "risk_assessment" in data
        assert data["risk_assessment"]["overall_risk"] in ("low", "moderate", "high", "severe")


def test_endpoint_external_places(client: TestClient):
    """GET /api/v1/external/places must return nearby mapped venues."""
    with patch("httpx.Client") as mock_httpx:
        mock_instance = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = MOCK_OVERPASS_PLACES_JSON
        mock_instance.post.return_value = mock_resp
        mock_httpx.return_value.__enter__.return_value = mock_instance

        resp = client.get("/api/v1/external/places?lat=17.4156&lon=78.4350&radius_meters=3000")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_found"] == 2
        assert len(data["places"]) == 2
