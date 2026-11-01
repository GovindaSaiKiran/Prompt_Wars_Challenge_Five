import { describe, it, expect } from 'vitest';
import {
  calculateVendorCost,
  calculateLedgerSummary,
  formatInr,
} from '../utils/ledgerMath';
import { EventBrief, VendorPriceRecord } from '../types/intelligence';

describe('ledgerMath — Deterministic Financial Calculations', () => {
  const sampleBrief: EventBrief = {
    eventName: 'Annual Tech Summit',
    location: 'Hyderabad, India',
    eventDate: '2026-11-20',
    guestCount: 200,
    durationDays: 1,
    durationHours: 8,
    targetBudgetInr: 1000000,
    contingencyPct: 10,
  };

  it('correctly calculates per_person vendor cost with 18% GST', () => {
    const cateringVendor: VendorPriceRecord = {
      id: 'v-cater-1',
      name: 'Grand Royal Caterers',
      category: 'catering',
      itemScope: 'Buffet Lunch & High Tea',
      unit: 'per_person',
      basePrice: 800,
      minUnits: 50,
      additionalCharges: 10000, // Service/setup fee
      gstPct: 18,
      status: 'published',
      isSelectedForBudget: true,
      evidenceStatus: 'confirmed_quote',
      vendorContact: { phone: '+91 98765 43210' },
    };

    const cost = calculateVendorCost(cateringVendor, sampleBrief);
    // Base cost: 800 * 200 guests = 160,000
    expect(cost.baseCost).toBe(160000);
    // Additional charges: 10,000
    expect(cost.additionalCharges).toBe(10000);
    // Taxable amount: 160,000 + 10,000 = 170,000
    expect(cost.taxableAmount).toBe(170000);
    // GST 18%: 170,000 * 0.18 = 30,600
    expect(cost.gstAmount).toBe(30600);
    // Gross Total: 170,000 + 30,600 = 200,600
    expect(cost.grossTotal).toBe(200600);
  });

  it('correctly calculates per_hour vendor cost', () => {
    const djVendor: VendorPriceRecord = {
      id: 'v-dj-1',
      name: 'Sonic Beats Sound',
      category: 'entertainment',
      itemScope: 'Live DJ & Audio Console',
      unit: 'per_hour',
      basePrice: 5000,
      minUnits: 4,
      additionalCharges: 0,
      gstPct: 18,
      status: 'published',
      isSelectedForBudget: true,
      evidenceStatus: 'confirmed_quote',
    };

    const cost = calculateVendorCost(djVendor, sampleBrief);
    // 8 hours * 5,000 = 40,000
    expect(cost.baseCost).toBe(40000);
    // Taxable = 40,000; GST 18% = 7,200; Gross = 47,200
    expect(cost.taxableAmount).toBe(40000);
    expect(cost.gstAmount).toBe(7200);
    expect(cost.grossTotal).toBe(47200);
  });

  it('computes aggregated ledger summary with contingency buffer and per-guest metrics', () => {
    const vendors: VendorPriceRecord[] = [
      {
        id: 'v-1',
        name: 'Venue Hall',
        category: 'venue',
        itemScope: 'Main Hall',
        unit: 'per_event',
        basePrice: 200000,
        additionalCharges: 0,
        gstPct: 18,
        status: 'published',
        isSelectedForBudget: true,
        evidenceStatus: 'confirmed_quote',
      },
      {
        id: 'v-2',
        name: 'Catering Team',
        category: 'catering',
        itemScope: 'Buffet',
        unit: 'per_person',
        basePrice: 1000,
        additionalCharges: 0,
        gstPct: 18,
        status: 'published',
        isSelectedForBudget: true,
        evidenceStatus: 'confirmed_quote',
      },
      {
        id: 'v-3',
        name: 'Unselected Photographer',
        category: 'photography',
        itemScope: 'Photo & Video',
        unit: 'per_event',
        basePrice: 75000,
        additionalCharges: 0,
        gstPct: 18,
        status: 'draft',
        isSelectedForBudget: false, // Should NOT be included in committed summary
        evidenceStatus: 'indicative_estimate',
      },
    ];

    const summary = calculateLedgerSummary(vendors, sampleBrief);

    // v-1: 200,000 + 36,000 = 236,000
    // v-2: (1,000 * 200) = 200,000 + 36,000 = 236,000
    // Total Committed: 400,000 subtotal + 72,000 GST = 472,000 committed
    expect(summary.committedSubtotal).toBe(400000);
    expect(summary.committedGst).toBe(72000);
    expect(summary.committedTotal).toBe(472000);

    // 10% contingency on target budget (1,000,000) = 100,000
    expect(summary.contingencyAmount).toBe(100000);

    // Variance: 1,000,000 - (472,000 committed + 100,000 contingency) = 428,000
    expect(summary.varianceInr).toBe(428000);
    expect(summary.isOverBudget).toBe(false);
    expect(summary.selectedVendorCount).toBe(2);
    expect(summary.totalVendorCount).toBe(3);
  });

  it('formats Indian currency (INR) with standard notation', () => {
    expect(formatInr(0)).toBe('₹0');
    expect(formatInr(150000)).toBe('₹1,50,000');
    expect(formatInr(1500000)).toBe('₹15,00,000');
    expect(formatInr(10000000)).toBe('₹1,00,00,000');
  });
});
