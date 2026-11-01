export type EvidenceStatus = 'published' | 'vendor_quoted' | 'vendor_confirmed' | 'estimated' | 'expired' | 'unknown';
export type PricingUnit = 'per_person' | 'per_hour' | 'per_day' | 'per_event' | 'fixed';
export type ServiceCategory = 'venue' | 'catering' | 'photography' | 'decor' | 'entertainment' | 'logistics';

export interface EventBrief {
  eventName: string;
  location: string;
  eventDate: string;
  guestCount: number;
  durationDays: number;
  durationHours: number;
  targetBudgetInr?: number | null;
  budgetProvenance?: string;
  contingencyPct: number;
}

export interface VendorPriceRecord {
  id: string;
  vendorName: string;
  category: ServiceCategory;
  basePrice: number;
  unit: PricingUnit;
  minUnits: number;
  gstPct: number;
  additionalCharges: number;
  status: EvidenceStatus;
  sourceUrl: string;
  retrievedAt: string;
  validUntil?: string;
  verbatimSnippet: string;
  inclusions: string[];
  exclusions: string[];
  isSelectedForBudget: boolean;
  phone?: string;
  address?: string;
  mapUrl?: string;
  contactPerson?: string;
  shoppingNearby?: string[];
}

export interface TimelineTask {
  id: string;
  title: string;
  category: ServiceCategory;
  dueDate: string;
  priority: 'high' | 'medium' | 'low';
  status: 'todo' | 'in_progress' | 'blocked' | 'done';
  linkedVendorId?: string;
}

export interface ApprovalAction {
  id: string;
  actionType: 'send_inquiry' | 'calendar_invite' | 'lock_quote';
  vendorName: string;
  recipientContact: string;
  draftContent: string;
  createdAt: string;
  status: 'pending' | 'approved' | 'rejected';
}

export interface CalculatedVendorCost {
  vendorId: string;
  unitQuantity: number;
  baseCost: number;
  additionalCharges: number;
  taxableAmount: number;
  gstAmount: number;
  grossTotal: number;
}

export interface LedgerFinancialSummary {
  targetBudget: number;
  contingencyAmount: number;
  effectiveTargetWithContingency: number;
  committedSubtotal: number;
  committedGst: number;
  committedTotal: number;
  varianceInr: number;
  variancePct: number;
  isOverBudget: boolean;
  selectedVendorCount: number;
  totalVendorCount: number;
  verifiedVendorCount: number;
  categoryBreakdown: Record<ServiceCategory, {
    count: number;
    subtotal: number;
    gst: number;
    total: number;
  }>;
}
