/**
 * Utility to map a GeneratedEventPlan from the planning engine
 * into the legacy ledger format (EventBrief, VendorPriceRecord[], TimelineTask[]).
 * This ensures full backward compatibility with the existing ledger table and scenario summary.
 */

import { GeneratedEventPlan } from '../types/planning';
import {
  EventBrief,
  VendorPriceRecord,
  TimelineTask,
  ApprovalAction,
  ServiceCategory,
  PricingUnit,
} from '../types/intelligence';

export function mapPlanToLedger(plan: GeneratedEventPlan): {
  brief: EventBrief;
  vendors: VendorPriceRecord[];
  tasks: TimelineTask[];
  approvals: ApprovalAction[];
} {
  const brief: EventBrief = {
    eventName: plan.brief.event_name,
    location: plan.brief.location || 'India',
    eventDate: plan.brief.event_date || '2026-11-20',
    guestCount: plan.brief.expected_guest_count || 100,
    durationDays: 1,
    durationHours: 8,
    targetBudgetInr: plan.brief.target_budget ?? (plan.budget_proposal.target_budget ?? 0),
    budgetProvenance: plan.brief.budget_provenance || plan.budget_proposal.budget_provenance || 'unknown',
    contingencyPct: 10,
  };

  const categoryMap: Record<string, ServiceCategory> = {
    venue: 'venue',
    catering: 'catering',
    decoration: 'decor',
    decor: 'decor',
    photography: 'photography',
    entertainment: 'entertainment',
    logistics: 'logistics',
    transport: 'logistics',
    accommodation: 'venue',
    finance: 'logistics',
    invitations: 'logistics',
  };

  const vendors: VendorPriceRecord[] = plan.budget_proposal.allocations
    .filter((alloc) => !alloc.category.toLowerCase().includes('contingency'))
    .map((alloc, idx) => {
      const catKey = alloc.category.toLowerCase();
      const mappedCategory = categoryMap[catKey] || 'logistics';

      return {
        id: `gen-vendor-${idx + 1}-${Date.now()}`,
        vendorName: `${alloc.category.charAt(0).toUpperCase() + alloc.category.slice(1)} Partner (${plan.brief.location || 'Local'})`,
        category: mappedCategory,
        basePrice: alloc.suggested_amount,
        unit: 'fixed' as PricingUnit,
        minUnits: 1,
        gstPct: 18,
        additionalCharges: 0,
        status: 'estimated',
        sourceUrl: 'https://eventprice.intelligence/benchmarks',
        retrievedAt: new Date().toISOString(),
        verbatimSnippet: alloc.rationale,
        inclusions: [alloc.rationale],
        exclusions: ['Late payment penalties', 'Damage deposits'],
        isSelectedForBudget: true,
        address: `${plan.brief.location || 'Local Market'} Hub`,
        phone: '+91 98XXX XXXXX (Vetting Phase)',
      };
    });

  const tasks: TimelineTask[] = plan.timeline.map((t, idx) => ({
    id: `gen-task-${idx + 1}-${Date.now()}`,
    title: t.task_title,
    category: (categoryMap[t.category.toLowerCase()] || 'logistics'),
    dueDate: t.suggested_due_date || '2026-11-01',
    priority: (t.priority === 'critical' || t.priority === 'high' ? 'high' : t.priority === 'low' ? 'low' : 'medium'),
    status: 'todo',
  }));

  const approvals: ApprovalAction[] = plan.vendor_checklist.slice(0, 3).map((item, idx) => ({
    id: `gen-act-${idx + 1}-${Date.now()}`,
    actionType: 'send_inquiry',
    vendorName: item.requirement_title,
    recipientContact: 'procurement@eventprice.intelligence',
    draftContent: `Requesting preliminary quotes for ${item.requirement_title}. Questions: ${item.important_questions_to_ask.slice(0, 2).join('; ')}`,
    createdAt: new Date().toISOString(),
    status: 'pending',
  }));

  return { brief, vendors, tasks, approvals };
}

