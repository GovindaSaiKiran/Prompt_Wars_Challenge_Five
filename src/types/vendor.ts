/**
 * Vendor Price Intelligence Types.
 * Matches backend schemas for Vendors, Services, Price Observations, Evidence, and Comparison.
 */

export type VerificationStatus = 'unverified' | 'pending' | 'verified' | 'rejected';
export type PriceType = 'fixed' | 'starting_from' | 'range' | 'per_unit' | 'package';
export type AvailabilityStatus = 'available' | 'limited' | 'unavailable' | 'unknown';
export type EvidenceType =
  | 'published'
  | 'vendor_quoted'
  | 'vendor_confirmed'
  | 'estimated'
  | 'expired'
  | 'unknown';

export interface VendorService {
  id: string;
  vendor_id: string;
  service_name: string;
  category: string;
  description?: string | null;
  unit?: string | null;
  minimum_quantity?: number | null;
  maximum_capacity?: number | null;
  service_area?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface VendorServiceCreate {
  service_name: string;
  category: string;
  description?: string;
  unit?: string;
  minimum_quantity?: number;
  maximum_capacity?: number;
  service_area?: string;
  is_active?: boolean;
}

export interface Vendor {
  id: string;
  business_name: string;
  description?: string | null;
  vendor_type: string;
  contact_person?: string | null;
  email?: string | null;
  phone?: string | null;
  website_url?: string | null;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  country: string;
  postal_code?: string | null;
  verification_status: VerificationStatus;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  services?: VendorService[];
}

export interface VendorCreate {
  business_name: string;
  description?: string;
  vendor_type: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  website_url?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  verification_status?: VerificationStatus;
  is_active?: boolean;
}

export interface VendorUpdate {
  business_name?: string;
  description?: string;
  vendor_type?: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  website_url?: string;
  address?: string;
  city?: string;
  state?: string;
  country?: string;
  postal_code?: string;
  verification_status?: VerificationStatus;
  is_active?: boolean;
}

export interface VendorListResponse {
  items: Vendor[];
  total: number;
  skip: number;
  limit: number;
}

export interface PriceEvidence {
  id: string;
  price_record_id: string;
  evidence_type: EvidenceType;
  source_url?: string | null;
  source_name?: string | null;
  captured_at: string;
  quoted_by?: string | null;
  valid_until?: string | null;
  inclusions?: string | null;
  exclusions?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface PriceEvidenceCreate {
  evidence_type: EvidenceType;
  source_url?: string;
  source_name?: string;
  captured_at?: string;
  quoted_by?: string;
  valid_until?: string;
  inclusions?: string;
  exclusions?: string;
  notes?: string;
}

export interface VendorPriceRecord {
  id: string;
  vendor_id: string;
  vendor_service_id: string;
  event_id?: string | null;
  amount: number | string;
  currency: string;
  unit: string;
  minimum_quantity?: number | null;
  maximum_quantity?: number | null;
  price_type: PriceType;
  tax_included?: boolean | null;
  tax_rate?: number | string | null;
  valid_from?: string | null;
  valid_until?: string | null;
  availability_status: AvailabilityStatus;
  availability_checked_at?: string | null;
  created_at: string;
  updated_at: string;
  vendor_business_name?: string | null;
  service_name?: string | null;
  evidence_records?: PriceEvidence[];
}

export interface VendorPriceRecordCreate {
  vendor_id: string;
  vendor_service_id: string;
  amount: number | string;
  currency?: string;
  unit: string;
  minimum_quantity?: number;
  maximum_quantity?: number;
  price_type?: PriceType;
  tax_included?: boolean;
  tax_rate?: number;
  valid_from?: string;
  valid_until?: string;
  availability_status?: AvailabilityStatus;
  initial_evidence?: PriceEvidenceCreate;
}

export interface MultiVendorComparisonItem {
  price_record_id: string;
  vendor_id: string;
  vendor_name: string;
  vendor_city?: string | null;
  verification_status: string;
  service_id: string;
  service_name: string;
  category: string;
  base_amount: number | string;
  currency: string;
  unit: string;
  price_type: PriceType;
  tax_included?: boolean | null;
  tax_rate?: number | string | null;
  tax_status?: string;
  tax_notes?: string | null;
  is_compatible: boolean;
  compatibility_reason?: string | null;
  normalized_quantity?: number | null;
  subtotal?: number | string | null;
  tax_amount?: number | string | null;
  total_cost?: number | string | null;
  inclusions?: string | null;
  exclusions?: string | null;
  evidence_type: EvidenceType;
  evidence_grade: string;
  is_confirmed?: boolean;
  is_estimated?: boolean;
  source_name?: string | null;
  source_url?: string | null;
  captured_at?: string | null;
  is_expired: boolean;
  valid_until?: string | null;
  availability_status: AvailabilityStatus;
  availability_checked_at?: string | null;
  availability_notes?: string | null;
  location_match?: boolean | null;
  city_match?: boolean | null;
  location_notes?: string | null;
}

export interface MultiVendorComparisonResponse {
  requested_category?: string | null;
  requested_quantity: number | string;
  requested_unit?: string | null;
  requested_currency: string;
  total_compared: number;
  compatible_count: number;
  items: MultiVendorComparisonItem[];
  best_value_price_record_id?: string | null;
  best_value_rationale?: string | null;
  comparison_notes: string[];
}

export interface VendorComparisonRequest {
  category?: string;
  quantity: number | string;
  unit?: string;
  vendor_ids?: string[];
  vendor_service_ids?: string[];
  price_record_ids?: string[];
  target_city?: string;
  currency?: string;
}

