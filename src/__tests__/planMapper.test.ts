import { describe, it, expect } from 'vitest';
import { mapPlanToLedger } from '../utils/planMapper';
import { GeneratedEventPlan } from '../types/planning';

describe('planMapper — Structured Plan to Client Ledger Translation', () => {
  const samplePlan: GeneratedEventPlan = {
    plan_id: 'plan-test-123',
    status: 'draft',
    brief: {
      event_type: 'wedding',
      event_name: 'Ananya & Kabir Wedding',
      location: 'Bengaluru',
      event_date: '2026-12-15',
      expected_guest_count: 250,
      target_budget: 1800000,
      currency: 'INR',
      confirmed_information: ['250 guests', 'December wedding'],
      missing_information: [],
      explicit_assumptions: [],
    },
    personalized_ideas: {
      theme_and_concept: ['Royal Heritage Garden Theme'],
      decoration_ideas: ['Marigold and Jasmine Floral Arches'],
      catering_ideas: ['South Indian Traditional Feast & Live Chaat'],
      entertainment_ideas: ['Live Carnatic Fusion Band'],
      guest_experience_suggestions: ['Customized Welcome Hampers'],
      practical_recommendations: ['Book outdoor lawn 6 months in advance'],
    },
    budget_proposal: {
      allocations: [
        {
          category: 'venue',
          suggested_amount: 500000,
          currency: 'INR',
          rationale: 'Heritage Palace Lawn booking for 1 full day',
          source_type: 'estimate',
        },
        {
          category: 'catering',
          suggested_amount: 600000,
          currency: 'INR',
          rationale: '250 guests at ₹2,400 per person dinner buffet',
          source_type: 'estimate',
        },
      ],
      total_allocated: 1100000,
      contingency_percentage: 10,
      contingency_amount: 110000,
      contingency_calculation_basis: '10% buffer',
      target_budget: 1800000,
      remaining_budget: 590000,
      is_within_budget: true,
      currency: 'INR',
      budget_assumptions: [],
      financial_alerts: [],
      estimate_provenance_notice: 'Illustrative estimates',
    },
    vendor_checklist: [
      {
        requirement_title: 'Heritage Banquet Lawn',
        category: 'venue',
        description: 'Outdoor lawn with capacity for 250+ guests',
        is_essential: true,
        estimated_budget: 500000,
        currency: 'INR',
        important_questions_to_ask: ['Power backup included?', 'Music cutoff time?'],
      },
    ],
    timeline: [
      {
        task_title: 'Finalize and book wedding lawn',
        category: 'venue',
        relative_stage: 'd-minus-60',
        due_date: '2026-10-15',
        description: 'Sign contract and pay 20% advance',
        prerequisites: [],
      },
    ],
  };

  it('correctly maps GeneratedEventPlan into EventBrief', () => {
    const { brief } = mapPlanToLedger(samplePlan);
    expect(brief.eventName).toBe('Ananya & Kabir Wedding');
    expect(brief.location).toBe('Bengaluru');
    expect(brief.guestCount).toBe(250);
    expect(brief.targetBudgetInr).toBe(1800000);
    expect(brief.contingencyPct).toBe(10);
  });

  it('maps budget allocations into selected vendor price records', () => {
    const { vendors } = mapPlanToLedger(samplePlan);
    expect(vendors.length).toBe(2);

    const venue = vendors.find((v) => v.category === 'venue');
    expect(venue).toBeDefined();
    expect(venue?.basePrice).toBe(500000);
    expect(venue?.isSelectedForBudget).toBe(true);

    const catering = vendors.find((v) => v.category === 'catering');
    expect(catering).toBeDefined();
    expect(catering?.basePrice).toBe(600000);
  });

  it('maps timeline tasks into client TimelineTask models', () => {
    const { tasks } = mapPlanToLedger(samplePlan);
    expect(tasks.length).toBe(1);
    expect(tasks[0].title).toBe('Finalize and book wedding lawn');
    expect(tasks[0].category).toBe('venue');
    expect(tasks[0].status).toBe('todo');
  });
});
