/**
 * Centralized API Client for Vendor Price Intelligence.
 * Connects directly to backend endpoints (/api/v1/vendors, /api/v1/prices, /api/v1/events).
 */

import {
  MultiVendorComparisonResponse,
  PriceEvidence,
  PriceEvidenceCreate,
  Vendor,
  VendorComparisonRequest,
  VendorCreate,
  VendorListResponse,
  VendorPriceRecord,
  VendorPriceRecordCreate,
  VendorPriceRecordUpdate,
  VendorService,
  VendorServiceCreate,
  VendorServiceUpdate,
  VendorUpdate,
} from '../types/vendor';

const getApiBaseUrl = (): string => {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && typeof envUrl === 'string') {
    return envUrl.replace(/\/+$/, '');
  }
  return '';
};

export class VendorApiError extends Error {
  statusCode?: number;
  details?: any;

  constructor(message: string, statusCode?: number, details?: any) {
    super(message);
    this.name = 'VendorApiError';
    this.statusCode = statusCode;
    this.details = details;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${path}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }
  if (options.body && typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 204) {
    return {} as T;
  }

  if (!res.ok) {
    let errBody: any;
    try {
      errBody = await res.json();
    } catch {
      errBody = await res.text();
    }
    const msg =
      typeof errBody === 'object' && errBody !== null
        ? errBody.detail || errBody.message || JSON.stringify(errBody)
        : String(errBody || res.statusText);
    throw new VendorApiError(msg, res.status, errBody);
  }

  return res.json();
}

// ============================================================================
// Vendor Management APIs
// ============================================================================

export async function fetchVendors(params?: {
  skip?: number;
  limit?: number;
  search?: string;
  city?: string;
  vendor_type?: string;
  verification_status?: string;
  is_active?: boolean;
  category?: string;
  service_name?: string;
}): Promise<VendorListResponse> {
  const sp = new URLSearchParams();
  if (params?.skip !== undefined) sp.append('skip', String(params.skip));
  if (params?.limit !== undefined) sp.append('limit', String(params.limit));
  if (params?.search) sp.append('search', params.search);
  if (params?.city) sp.append('city', params.city);
  if (params?.vendor_type) sp.append('vendor_type', params.vendor_type);
  if (params?.verification_status) sp.append('verification_status', params.verification_status);
  if (params?.is_active !== undefined) sp.append('is_active', String(params.is_active));
  if (params?.category) sp.append('category', params.category);
  if (params?.service_name) sp.append('service_name', params.service_name);

  const query = sp.toString() ? `?${sp.toString()}` : '';
  return request<VendorListResponse>(`/api/v1/vendors/${query}`);
}

export async function fetchVendor(vendorId: string): Promise<Vendor> {
  return request<Vendor>(`/api/v1/vendors/${vendorId}`);
}

export async function createVendor(payload: VendorCreate): Promise<Vendor> {
  return request<Vendor>('/api/v1/vendors/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateVendor(vendorId: string, payload: VendorUpdate): Promise<Vendor> {
  return request<Vendor>(`/api/v1/vendors/${vendorId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteVendor(vendorId: string): Promise<void> {
  await request<void>(`/api/v1/vendors/${vendorId}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// Vendor Services APIs
// ============================================================================

export async function createVendorService(
  vendorId: string,
  payload: VendorServiceCreate,
): Promise<VendorService> {
  return request<VendorService>(`/api/v1/vendors/${vendorId}/services`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateVendorService(
  vendorId: string,
  serviceId: string,
  payload: VendorServiceUpdate,
): Promise<VendorService> {
  return request<VendorService>(`/api/v1/vendors/${vendorId}/services/${serviceId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function deleteVendorService(vendorId: string, serviceId: string): Promise<void> {
  await request<void>(`/api/v1/vendors/${vendorId}/services/${serviceId}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// Vendor Price Records & Evidence APIs
// ============================================================================

export async function fetchPriceRecords(params?: {
  skip?: number;
  limit?: number;
  vendor_id?: string;
  vendor_service_id?: string;
  currency?: string;
  availability_status?: string;
}): Promise<{ items: VendorPriceRecord[]; total: number }> {
  const sp = new URLSearchParams();
  if (params?.skip !== undefined) sp.append('skip', String(params.skip));
  if (params?.limit !== undefined) sp.append('limit', String(params.limit));
  if (params?.vendor_id) sp.append('vendor_id', params.vendor_id);
  if (params?.vendor_service_id) sp.append('vendor_service_id', params.vendor_service_id);
  if (params?.currency) sp.append('currency', params.currency);
  if (params?.availability_status) sp.append('availability_status', params.availability_status);

  const query = sp.toString() ? `?${sp.toString()}` : '';
  return request<{ items: VendorPriceRecord[]; total: number }>(`/api/v1/prices/${query}`);
}

export async function fetchPriceRecord(priceId: string): Promise<VendorPriceRecord> {
  return request<VendorPriceRecord>(`/api/v1/prices/${priceId}`);
}

export async function createPriceRecord(payload: VendorPriceRecordCreate): Promise<VendorPriceRecord> {
  return request<VendorPriceRecord>('/api/v1/prices/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updatePriceRecord(
  priceId: string,
  payload: VendorPriceRecordUpdate,
): Promise<VendorPriceRecord> {
  return request<VendorPriceRecord>(`/api/v1/prices/${priceId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function attachPriceEvidence(
  priceId: string,
  payload: PriceEvidenceCreate,
): Promise<PriceEvidence> {
  return request<PriceEvidence>(`/api/v1/prices/${priceId}/evidence`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchVendorPriceHistory(vendorId: string): Promise<VendorPriceRecord[]> {
  return request<VendorPriceRecord[]>(`/api/v1/prices/vendors/${vendorId}/history`);
}

// ============================================================================
// Multi-Vendor Comparison API
// ============================================================================

export async function compareVendorsApi(
  payload: VendorComparisonRequest,
): Promise<MultiVendorComparisonResponse> {
  return request<MultiVendorComparisonResponse>('/api/v1/prices/compare', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// ============================================================================
// Budget Integration: Add Line Item from Vendor Price Record
// ============================================================================

export async function addLineItemFromPriceRecord(
  eventId: string,
  budgetId: string,
  payload: {
    category: string;
    description: string;
    quantity: number | string;
    vendor_price_record_id: string;
    notes?: string;
  },
): Promise<any> {
  return request<any>(`/api/v1/events/${eventId}/budgets/${budgetId}/items`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

