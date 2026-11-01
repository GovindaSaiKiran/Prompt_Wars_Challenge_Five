"""Safe Live Smoke Test for External Data Integrations (Hyderabad, India).

Queries live Nominatim and Overpass endpoints for Hyderabad.
Never reveals or leaks API credentials.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.integrations.geocoding.nominatim import NominatimClient
from app.integrations.places.overpass import OverpassClient
from app.services.external_data_service import ExternalDataService


def main():
    print("=== External Data Integration Smoke Test ===")
    svc = ExternalDataService()
    
    # 1. Provider Status
    status = svc.get_status()
    print(f"\n1. Provider Status:")
    for name, p in status.providers.items():
        print(f"  - {name}: configured={p.configured}, enabled={p.enabled}, status={p.operational_status}")

    # 2. Forward Geocode Hyderabad
    print(f"\n2. Nominatim Forward Geocoding ('Banjara Hills, Hyderabad'):")
    geo_res = svc.search_locations("Banjara Hills, Hyderabad", limit=2)
    print(f"  - Found {geo_res.total_candidates} candidates (cached={geo_res.is_cached})")
    for cand in geo_res.candidates:
        print(f"    * {cand.display_name[:70]}... ({cand.latitude:.4f}, {cand.longitude:.4f})")

    # 3. Overpass Nearby Places around Banjara Hills (17.4156, 78.4350)
    print(f"\n3. Overpass Nearby Venues around Hyderabad (17.4156, 78.4350, r=2000m):")
    places_res = svc.find_nearby_places(17.4156, 78.4350, radius_meters=2000, max_results=5)
    print(f"  - Found {places_res.total_found} mapped landmarks (cached={places_res.is_cached})")
    for place in places_res.places[:5]:
        print(f"    * [{place.category}] {place.name} (~{place.distance_meters:.0f}m away)")

    # 4. Weather status check
    print(f"\n4. Weather Service Check:")
    weather_res = svc.get_weather(17.4156, 78.4350)
    print(f"  - Classification: {weather_res.classification.value}")
    if weather_res.measurements:
        print(f"  - Temperature: {weather_res.measurements.temperature_c}°C, Condition: {weather_res.measurements.weather_condition}")
    else:
        print(f"  - Note: {weather_res.coverage_limitations[0] if weather_res.coverage_limitations else 'No measurements'}")
    if weather_res.risk_assessment:
        print(f"  - Assessed Risk: {weather_res.risk_assessment.overall_risk.value.upper()} (Outdoor suitable: {weather_res.risk_assessment.is_outdoor_suitable})")

    print("\n=== Smoke Test Complete ===")


if __name__ == "__main__":
    main()
