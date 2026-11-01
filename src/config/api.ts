/**
 * Global API Client Configuration
 *
 * Centralizes backend base URL resolution across all API services.
 * Dynamically switches between local development (localhost) and production
 * (Render cloud backend) to prevent Mixed Content security rejections.
 */

export const CLOUD_BACKEND_URL = 'https://prompt-wars-c5-api.onrender.com';

export const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string' && envUrl.trim()) {
    const trimmed = envUrl.trim().replace(/\/+$/, '');
    // In browser production (e.g. *.vercel.app or non-localhost), route to deployed backend
    if (
      typeof window !== 'undefined' &&
      window.location.hostname !== 'localhost' &&
      window.location.hostname !== '127.0.0.1'
    ) {
      if (trimmed.includes('localhost') || trimmed.includes('127.0.0.1')) {
        return CLOUD_BACKEND_URL;
      }
    }
    return trimmed;
  }
  // Production default for hosted environments
  if (
    typeof window !== 'undefined' &&
    window.location.hostname !== 'localhost' &&
    window.location.hostname !== '127.0.0.1'
  ) {
    return CLOUD_BACKEND_URL;
  }
  return '';
};

