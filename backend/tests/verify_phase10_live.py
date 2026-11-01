"""Phase 10.1 Live Integration Verification Script.

Executes real live checks against OpenWeather, Nominatim, and Overpass,
as well as the mounted FastAPI endpoints.
Ensures zero secret leakage.
"""

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys

# Ensure backend path is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from app.core.config import get_settings
from app.integrations.geocoding.nominatim import NominatimClient
from app.integrations.places.overpass import OverpassClient
from app.integrations.weather.openweather import OpenWeatherAdapter
from app.main import app
from app.schemas.external_data import WeatherClassification


def main():
    settings = get_settings()
    results = {}

    print("=================================================================")
    print("PHASE 10.1: CONTROLLED LIVE INTEGRATION VERIFICATION")
    print("=================================================================")

    # 1. OpenWeather Settings & Live Request
    print("\n--- 1. OpenWeather Live Check ---")
    ow_enabled = settings.OPENWEATHER_ENABLED
    ow_key_configured = bool(settings.OPENWEATHER_API_KEY and settings.OPENWEATHER_API_KEY.strip())
    print(f"OPENWEATHER_ENABLED: {ow_enabled}")
    print(f"OPENWEATHER_API_KEY configured: {ow_key_configured} (length: {len(settings.OPENWEATHER_API_KEY) if settings.OPENWEATHER_API_KEY else 0})")

    ow_adapter = OpenWeatherAdapter(settings=settings)
    
    # Banjara Hills coordinates
    lat, lon = 17.4156, 78.4350

    # 1a. Real current weather
    print("Executing real HTTP request for current weather at Banjara Hills (17.4156, 78.4350)...")
    curr_weather = ow_adapter.get_weather(lat, lon, event_date=date.today(), location_name="Banjara Hills, Hyderabad")
    print(f"  Classification: {curr_weather.classification.value}")
    print(f"  Provider Endpoint: {curr_weather.provider_endpoint}")
    if curr_weather.measurements:
        print(f"  Live Temperature: {curr_weather.measurements.temperature_c} C")
        print(f"  Feels Like: {curr_weather.measurements.feels_like_c} C")
        print(f"  Humidity: {curr_weather.measurements.humidity_pct}%")
        print(f"  Wind Speed: {curr_weather.measurements.wind_speed_mps} m/s")
        print(f"  Condition: {curr_weather.measurements.weather_condition} ({curr_weather.measurements.weather_description})")
        print(f"  Timestamp retrieved: {curr_weather.retrieved_at.isoformat()}")
    else:
        print(f"  Measurements: None")
        print(f"  Coverage limitations / error message: {curr_weather.coverage_limitations}")

    # 1b. Real forecast (within 5-day horizon, e.g. tomorrow)
    tomorrow = date.today() + timedelta(days=1)
    print(f"\nExecuting real HTTP forecast request for tomorrow ({tomorrow.isoformat()})...")
    forecast_weather = ow_adapter.get_weather(lat, lon, event_date=tomorrow, location_name="Banjara Hills, Hyderabad")
    print(f"  Classification: {forecast_weather.classification.value}")
    print(f"  Provider Endpoint: {forecast_weather.provider_endpoint}")
    if forecast_weather.measurements:
        print(f"  Forecast Temp: {forecast_weather.measurements.temperature_c} C")
        print(f"  Condition: {forecast_weather.measurements.weather_condition}")
    else:
        print(f"  Measurements: None")
        print(f"  Limitations: {forecast_weather.coverage_limitations}")

    # 1c. Date outside horizon (> 5 days)
    far_future = date.today() + timedelta(days=20)
    print(f"\nExecuting request for date beyond 5-day horizon ({far_future.isoformat()})...")
    far_weather = ow_adapter.get_weather(lat, lon, event_date=far_future, location_name="Banjara Hills, Hyderabad")
    print(f"  Classification: {far_weather.classification.value}")
    assert far_weather.classification == WeatherClassification.UNAVAILABLE
    assert far_weather.measurements is None
    print(f"  Correctly marked UNAVAILABLE: {far_weather.coverage_limitations}")

    # 1d. Invalid key test
    print("\nExecuting invalid API key test...")
    from app.core.config import Settings
    bad_settings = Settings(OPENWEATHER_ENABLED=True, OPENWEATHER_API_KEY="definitely_invalid_key_xyz")
    bad_adapter = OpenWeatherAdapter(settings=bad_settings)
    bad_res = bad_adapter.get_weather(lat, lon, event_date=date.today())
    print(f"  Invalid key classification: {bad_res.classification.value}")
    print(f"  Error message handled gracefully: {bad_res.coverage_limitations}")

    # 2. Nominatim Live Check
    print("\n--- 2. Nominatim Live Check ---")
    nom_client = NominatimClient(enabled=True)
    print("Executing real HTTP forward geocode request for 'Banjara Hills, Hyderabad'...")
    nom_res = nom_client.forward_geocode("Banjara Hills, Hyderabad", limit=3)
    print(f"  Total Candidates: {nom_res.total_candidates}")
    print(f"  Provider: {nom_res.provider}")
    print(f"  Attribution: {nom_res.attribution}")
    for i, c in enumerate(nom_res.candidates):
        print(f"    Candidate {i+1}: {c.display_name}")
        print(f"      Coordinates: ({c.latitude}, {c.longitude})")
        print(f"      Locality: {c.locality}, City: {c.city}, State: {c.state}, OSM ID: {c.osm_id}")

    # 2b. Reverse geocode
    print("\nExecuting real HTTP reverse geocode for (17.4156, 78.4350)...")
    rev_res = nom_client.reverse_geocode(lat, lon)
    print(f"  Display Name: {rev_res.display_name}")
    print(f"  Locality components: {list(rev_res.address_components.keys())}")

    # 3. Overpass Live Check
    print("\n--- 3. Overpass Live Check ---")
    op_client = OverpassClient(enabled=True)
    print("Executing real HTTP Overpass QL query around Banjara Hills (r=2000m)...")
    op_res = op_client.find_nearby_places(lat, lon, radius_meters=2000, category="all", max_results=10)
    print(f"  Total Found: {op_res.total_found}")
    print(f"  Attribution: {op_res.attribution}")
    print(f"  Disclaimer: {op_res.disclaimer}")
    for i, p in enumerate(op_res.places[:10]):
        print(f"    Place {i+1}: [{p.category}] {p.name} ({p.distance_meters:.0f}m away, OSM: {p.osm_type}/{p.osm_id})")
        if p.address:
            print(f"      Address: {p.address}")

    # 4. FastAPI Endpoint Live Verification
    print("\n--- 4. FastAPI Endpoints Live Verification ---")
    client = TestClient(app)

    endpoints = [
        ("/api/v1/external/status", "GET"),
        (f"/api/v1/external/weather?lat={lat}&lon={lon}&date={date.today().isoformat()}", "GET"),
        ("/api/v1/external/geocode?q=Banjara+Hills,+Hyderabad&limit=2", "GET"),
        (f"/api/v1/external/reverse-geocode?lat={lat}&lon={lon}", "GET"),
        (f"/api/v1/external/places?lat={lat}&lon={lon}&radius_meters=2000", "GET"),
    ]

    for path, method in endpoints:
        print(f"Calling {method} {path}...")
        resp = client.get(path)
        print(f"  Status Code: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        keys_summary = list(data.keys())
        print(f"  Response Keys: {keys_summary}")
        # Security: verify no API key leaked in JSON response
        data_str = json.dumps(data)
        if settings.OPENWEATHER_API_KEY and settings.OPENWEATHER_API_KEY in data_str:
            raise AssertionError("SECURITY CRITICAL: OpenWeather API key found in response body!")
        print("  Security Check: No credentials leaked in response body.")

    print("\n=================================================================")
    print("ALL LIVE VERIFICATION CHECKS COMPLETED SUCCESSFULLY")
    print("=================================================================")


if __name__ == "__main__":
    main()

