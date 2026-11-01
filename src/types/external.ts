/**
 * TypeScript Interfaces for External Data Integrations.
 *
 * Covers OpenWeather, OpenStreetMap Nominatim, and Overpass API data models.
 */

export type WeatherRiskLevel = 'low' | 'moderate' | 'high' | 'severe';

export type WeatherClassification =
  | 'current_observation'
  | 'forecast'
  | 'historical'
  | 'unavailable';

export interface WeatherRiskFactor {
  name: string;
  level: WeatherRiskLevel;
  value_observed?: string;
  threshold_applied?: string;
  message: string;
  recommendation: string;
}

export interface WeatherRiskAssessment {
  overall_risk: WeatherRiskLevel;
  is_outdoor_suitable: boolean;
  risk_score: number;
  factors: WeatherRiskFactor[];
  recommendations: string[];
  disclaimer: string;
}

export interface NormalizedWeatherMeasurements {
  temperature_c?: number;
  feels_like_c?: number;
  temp_min_c?: number;
  temp_max_c?: number;
  humidity_pct?: number;
  pressure_hpa?: number;
  wind_speed_mps?: number;
  wind_direction_deg?: number;
  cloud_cover_pct?: number;
  rainfall_mm?: number;
  weather_condition?: string;
  weather_description?: string;
  weather_icon?: string;
  sunrise?: string;
  sunset?: string;
}

export interface WeatherResponse {
  latitude: number;
  longitude: number;
  location_name?: string;
  requested_date?: string;
  classification: WeatherClassification;
  measurements?: NormalizedWeatherMeasurements;
  risk_assessment?: WeatherRiskAssessment;
  provider: string;
  provider_endpoint: string;
  retrieved_at: string;
  timezone_offset_seconds: number;
  is_cached: boolean;
  coverage_limitations: string[];
  disclaimer: string;
}

export interface GeocodingCandidate {
  place_id?: string;
  display_name: string;
  latitude: number;
  longitude: number;
  locality?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  osm_type?: string;
  osm_id?: number;
  category?: string;
  type?: string;
}

export interface ForwardGeocodeResponse {
  query: string;
  total_candidates: number;
  candidates: GeocodingCandidate[];
  provider: string;
  attribution: string;
  is_cached: boolean;
  retrieved_at: string;
}

export interface ReverseGeocodeResponse {
  latitude: number;
  longitude: number;
  display_name: string;
  address_components: Record<string, any>;
  provider: string;
  attribution: string;
  is_cached: boolean;
  retrieved_at: string;
}

export interface NormalizedPlace {
  osm_id: string;
  osm_type: string;
  name: string;
  category: string;
  latitude: number;
  longitude: number;
  distance_meters?: number;
  address?: string;
  locality?: string;
  tags: Record<string, string>;
  provider: string;
  retrieved_at: string;
}

export interface PlacesResponse {
  center_latitude: number;
  center_longitude: number;
  radius_meters: number;
  category?: string;
  total_found: number;
  places: NormalizedPlace[];
  attribution: string;
  is_cached: boolean;
  retrieved_at: string;
  disclaimer: string;
}

export interface ProviderHealth {
  provider: string;
  configured: boolean;
  enabled: boolean;
  operational_status: string;
  last_checked_at?: string;
  last_success_at?: string;
  message: string;
}

export interface ExternalStatusResponse {
  providers: Record<string, ProviderHealth>;
  cached_entries_count: number;
  timestamp: string;
}

