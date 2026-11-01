/**
 * Centralized API Client for External Data Integrations.
 *
 * Communicates with FastAPI backend (/api/v1/external/*).
 * Covers OpenWeather, OpenStreetMap Nominatim geocoding, and Overpass nearby venue discovery.
 */

import {
  ExternalStatusResponse,
  ForwardGeocodeResponse,
  PlacesResponse,
  ReverseGeocodeResponse,
  WeatherResponse,
} from '../types/external';

const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string') {
    return envUrl.replace(/\/+$/, '');
  }
  return '';
};

export class ExternalApiError extends Error {
  statusCode?: number;
  details?: any;

  constructor(message: string, statusCode?: number, details?: any) {
    super(message);
    this.name = 'ExternalApiError';
    this.statusCode = statusCode;
    this.details = details;
  }
}

/**
 * Fetch external data provider health and cache statistics.
 */
export async function fetchExternalStatus(signal?: AbortSignal): Promise<ExternalStatusResponse> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}/api/v1/external/status`;

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    });
    if (!res.ok) {
      throw new ExternalApiError(`Failed to fetch status: ${res.statusText}`, res.status);
    }
    return (await res.json()) as ExternalStatusResponse;
  } catch (err: any) {
    if (err.name === 'AbortError') throw err;
    throw new ExternalApiError(err.message || 'Network error fetching external provider status');
  }
}

/**
 * Forward geocode a location search string into coordinate candidates via Nominatim.
 */
export async function forwardGeocode(
  query: string,
  limit: number = 5,
  countryCode: string = 'in',
  signal?: AbortSignal
): Promise<ForwardGeocodeResponse> {
  const baseUrl = getApiBaseUrl();
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
  });
  if (countryCode) {
    params.set('country_code', countryCode);
  }
  const url = `${baseUrl}/api/v1/external/geocode?${params.toString()}`;

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    });
    if (!res.ok) {
      throw new ExternalApiError(`Geocoding error: ${res.statusText}`, res.status);
    }
    return (await res.json()) as ForwardGeocodeResponse;
  } catch (err: any) {
    if (err.name === 'AbortError') throw err;
    throw new ExternalApiError(err.message || 'Network error performing geocoding lookup');
  }
}

/**
 * Reverse geocode coordinates to an address via Nominatim.
 */
export async function reverseGeocode(
  lat: number,
  lon: number,
  signal?: AbortSignal
): Promise<ReverseGeocodeResponse> {
  const baseUrl = getApiBaseUrl();
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
  });
  const url = `${baseUrl}/api/v1/external/reverse-geocode?${params.toString()}`;

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    });
    if (!res.ok) {
      throw new ExternalApiError(`Reverse geocode error: ${res.statusText}`, res.status);
    }
    return (await res.json()) as ReverseGeocodeResponse;
  } catch (err: any) {
    if (err.name === 'AbortError') throw err;
    throw new ExternalApiError(err.message || 'Network error performing reverse geocoding');
  }
}

/**
 * Retrieve weather observations/forecasts and deterministic risk evaluation.
 */
export async function fetchWeather(
  lat: number,
  lon: number,
  date?: string,
  locationName?: string,
  signal?: AbortSignal
): Promise<WeatherResponse> {
  const baseUrl = getApiBaseUrl();
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
  });
  if (date) params.set('date', date);
  if (locationName) params.set('location_name', locationName);

  const url = `${baseUrl}/api/v1/external/weather?${params.toString()}`;

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    });
    if (!res.ok) {
      throw new ExternalApiError(`Weather error: ${res.statusText}`, res.status);
    }
    return (await res.json()) as WeatherResponse;
  } catch (err: any) {
    if (err.name === 'AbortError') throw err;
    throw new ExternalApiError(err.message || 'Network error fetching weather intelligence');
  }
}

/**
 * Discover nearby real mapped event facilities via Overpass API.
 */
export async function fetchNearbyPlaces(
  lat: number,
  lon: number,
  radiusMeters: number = 3000,
  category?: string,
  maxResults: number = 30,
  signal?: AbortSignal
): Promise<PlacesResponse> {
  const baseUrl = getApiBaseUrl();
  const params = new URLSearchParams({
    lat: String(lat),
    lon: String(lon),
    radius_meters: String(radiusMeters),
    max_results: String(maxResults),
  });
  if (category && category !== 'all') {
    params.set('category', category);
  }

  const url = `${baseUrl}/api/v1/external/places?${params.toString()}`;

  try {
    const res = await fetch(url, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      signal,
    });
    if (!res.ok) {
      throw new ExternalApiError(`Nearby places error: ${res.statusText}`, res.status);
    }
    return (await res.json()) as PlacesResponse;
  } catch (err: any) {
    if (err.name === 'AbortError') throw err;
    throw new ExternalApiError(err.message || 'Network error fetching nearby places');
  }
}

