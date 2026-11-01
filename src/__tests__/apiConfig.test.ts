import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getApiBaseUrl, CLOUD_BACKEND_URL } from '../config/api';

describe('apiConfig — Centralized Base URL Resolution', () => {
  const originalWindow = global.window;

  afterEach(() => {
    global.window = originalWindow;
  });

  it('exposes the production cloud backend URL constant', () => {
    expect(CLOUD_BACKEND_URL).toBe('https://prompt-wars-c5-api.onrender.com');
  });

  it('routes to cloud backend in production when running on a hosted domain', () => {
    // Simulate running in browser on a Vercel domain
    global.window = {
      location: {
        hostname: 'prompt-wars-challenge-five.vercel.app',
      },
    } as any;

    const url = getApiBaseUrl();
    expect(url).toBe(CLOUD_BACKEND_URL);
  });
});
