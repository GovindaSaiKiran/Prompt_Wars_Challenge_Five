import {
  EventBrief,
  VendorPriceRecord,
  CalculatedVendorCost,
  LedgerFinancialSummary,
  ServiceCategory,
  EvidenceStatus,
} from '../types/intelligence';

/**
 * Deterministically computes the cost breakdown for a single vendor record
 * against the current active event brief specifications.
 */
export function calculateVendorCost(
  record: VendorPriceRecord,
  brief: EventBrief
): CalculatedVendorCost {
  let unitQuantity = 1;

  switch (record.unit) {
    case 'per_person':
      unitQuantity = Math.max(brief.guestCount || 0, record.minUnits || 0);
      break;
    case 'per_hour':
      unitQuantity = Math.max(brief.durationHours || 0, record.minUnits || 0);
      break;
    case 'per_day':
      unitQuantity = Math.max(brief.durationDays || 0, record.minUnits || 0);
      break;
    case 'per_event':
    case 'fixed':
    default:
      unitQuantity = 1;
      break;
  }

  const baseCost = Math.round(record.basePrice * unitQuantity);
  const additionalCharges = Math.round(record.additionalCharges || 0);
  const taxableAmount = baseCost + additionalCharges;
  const gstPct = record.gstPct || 0;
  const gstAmount = Math.round(taxableAmount * (gstPct / 100));
  const grossTotal = taxableAmount + gstAmount;

  return {
    vendorId: record.id,
    unitQuantity,
    baseCost,
    additionalCharges,
    taxableAmount,
    gstAmount,
    grossTotal,
  };
}

/**
 * Computes deterministic aggregated ledger summary across all active records.
 */
export function calculateLedgerSummary(
  vendors: VendorPriceRecord[],
  brief: EventBrief
): LedgerFinancialSummary {
  const initialCategoryBreakdown: Record<
    ServiceCategory,
    { count: number; subtotal: number; gst: number; total: number }
  > = {
    venue: { count: 0, subtotal: 0, gst: 0, total: 0 },
    catering: { count: 0, subtotal: 0, gst: 0, total: 0 },
    photography: { count: 0, subtotal: 0, gst: 0, total: 0 },
    decor: { count: 0, subtotal: 0, gst: 0, total: 0 },
    entertainment: { count: 0, subtotal: 0, gst: 0, total: 0 },
    logistics: { count: 0, subtotal: 0, gst: 0, total: 0 },
  };

  let committedSubtotal = 0;
  let committedGst = 0;
  let committedTotal = 0;
  let selectedVendorCount = 0;
  let verifiedVendorCount = 0;

  for (const vendor of vendors) {
    if (vendor.status === 'published' || vendor.status === 'vendor_confirmed') {
      verifiedVendorCount++;
    }

    if (vendor.isSelectedForBudget) {
      selectedVendorCount++;
      const cost = calculateVendorCost(vendor, brief);
      committedSubtotal += cost.taxableAmount;
      committedGst += cost.gstAmount;
      committedTotal += cost.grossTotal;

      if (initialCategoryBreakdown[vendor.category]) {
        initialCategoryBreakdown[vendor.category].count++;
        initialCategoryBreakdown[vendor.category].subtotal += cost.taxableAmount;
        initialCategoryBreakdown[vendor.category].gst += cost.gstAmount;
        initialCategoryBreakdown[vendor.category].total += cost.grossTotal;
      }
    }
  }

  const targetBudget = brief.targetBudgetInr || 0;
  const contingencyPct = brief.contingencyPct || 0;
  const contingencyAmount = Math.round(targetBudget * (contingencyPct / 100));
  const effectiveTargetWithContingency = targetBudget - contingencyAmount;
  
  // Variance = Target Budget - (Total Committed + Contingency)
  const totalProjectedCommitment = committedTotal + contingencyAmount;
  const varianceInr = targetBudget - totalProjectedCommitment;
  const variancePct = targetBudget > 0 ? (varianceInr / targetBudget) * 100 : 0;
  const isOverBudget = varianceInr < 0;

  return {
    targetBudget,
    contingencyAmount,
    effectiveTargetWithContingency,
    committedSubtotal,
    committedGst,
    committedTotal,
    varianceInr,
    variancePct,
    isOverBudget,
    selectedVendorCount,
    totalVendorCount: vendors.length,
    verifiedVendorCount,
    categoryBreakdown: initialCategoryBreakdown,
  };
}

/**
 * Format Indian Rupee currency with standard Indian grouping: 1,00,000
 */
export function formatInr(amount: number): string {
  if (isNaN(amount) || amount === null || amount === undefined) return '₹0';
  const isNegative = amount < 0;
  const abs = Math.abs(amount);
  const formatted = abs.toLocaleString('en-IN');
  return `${isNegative ? '-' : ''}₹${formatted}`;
}

/**
 * Format compact INR (e.g. ₹45.5L, ₹1.2Cr, ₹85K)
 */
export function formatCompactInr(amount: number): string {
  if (isNaN(amount) || amount === null || amount === undefined) return '₹0';
  const isNegative = amount < 0;
  const abs = Math.abs(amount);

  let formatted = '';
  if (abs >= 10000000) {
    formatted = `${(abs / 10000000).toFixed(2)}Cr`;
  } else if (abs >= 100000) {
    formatted = `${(abs / 100000).toFixed(2)}L`;
  } else if (abs >= 1000) {
    formatted = `${(abs / 1000).toFixed(1)}k`;
  } else {
    formatted = `${abs}`;
  }

  return `${isNegative ? '-' : ''}₹${formatted}`;
}

export const CATEGORY_LABELS: Record<ServiceCategory, string> = {
  venue: 'Venue & Spaces',
  catering: 'Catering & F&B',
  photography: 'Photo & Video',
  decor: 'Production & Decor',
  entertainment: 'Artists & Stage',
  logistics: 'Logistics & Transit',
};

export const EVIDENCE_STATUS_METADATA: Record<
  EvidenceStatus,
  { label: string; dotColor: string; description: string }
> = {
  published: {
    label: 'Published',
    dotColor: '#10B981', // Emerald
    description: 'Verifiable public rate card or live published index',
  },
  vendor_quoted: {
    label: 'Vendor Quoted',
    dotColor: '#3B82F6', // Blue
    description: 'Direct written quotation from registered vendor representative',
  },
  vendor_confirmed: {
    label: 'Confirmed',
    dotColor: '#14B8A6', // Teal
    description: 'Executed statement of work / locked price confirmation',
  },
  estimated: {
    label: 'Estimated',
    dotColor: '#F59E0B', // Amber
    description: 'Heuristic or historical benchmark estimation',
  },
  expired: {
    label: 'Expired',
    dotColor: '#EF4444', // Red
    description: 'Quote validity window has elapsed',
  },
  unknown: {
    label: 'Unverified',
    dotColor: '#EF4444', // Red
    description: 'Unverified source without provenance timestamp',
  },
};
