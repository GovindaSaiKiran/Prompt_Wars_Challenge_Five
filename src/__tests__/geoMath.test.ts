import { describe, it, expect } from 'vitest';
import { haversineMeters, formatDistance } from '../utils/geoMath';

describe('geoMath — Geodesic Spatial Coordinates & Distance', () => {
  it('accurately calculates distance between coordinates in Hyderabad', () => {
    // Hitec City (17.4474, 78.3762) to Shilparamam (17.4526, 78.3798)
    const distance = haversineMeters(17.4474, 78.3762, 17.4526, 78.3798);
    // Real distance is ~693 meters
    expect(distance).toBeGreaterThan(650);
    expect(distance).toBeLessThan(750);
  });

  it('returns 0 for identical coordinates', () => {
    expect(haversineMeters(17.4474, 78.3762, 17.4474, 78.3762)).toBe(0);
  });

  it('formats distances cleanly for user display', () => {
    expect(formatDistance(450)).toBe('450 m away');
    expect(formatDistance(1250)).toBe('1.25 km away');
    expect(formatDistance(5000)).toBe('5.00 km away');
    expect(formatDistance(undefined)).toBe('--');
  });
});
