/**
 * Geodesic spatial math utilities.
 * Calculates great-circle distances using the Haversine formula.
 */

const EARTH_RADIUS_METERS = 6371000;

export function haversineMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(EARTH_RADIUS_METERS * c * 10) / 10;
}

export function formatDistance(meters?: number): string {
  if (meters === undefined || meters === null || isNaN(meters)) return '--';
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(2)} km away`;
  }
  return `${Math.round(meters)} m away`;
}
