/**
 * TypeScript type definitions for Structured GenAI Event Planning Engine.
 * Conforms 1:1 with backend FastAPI Pydantic schemas in `backend/app/schemas/planning.py`.
 */

export type PlanningEventType =
  | 'wedding'
  | 'birthday'
  | 'community'
  | 'corporate'
  | 'conference'
  | 'anniversary'
  | 'other';

export interface PlanEventBrief {
  event_type: string;
  event_name: string;
  occasion?: string | null;
  theme?: string | null;
  scale?: string | null;
  duration?: string | null;
  format_type?: string | null;
  location?: string | null;
  expected_guest_count?: number | null;
  event_date?: string | null;
  event_time?: string | null;
  target_budget?: number | null;
  budget_provenance?: 'user_provided' | 'user_approved' | 'ai_suggested' | 'benchmark_estimate' | 'unknown' | string;
  currency: string;
  description?: string | null;
  confirmed_information: string[];
  missing_information: string[];
  explicit_assumptions: string[];
}

export interface PlanPersonalizedIdeas {
  theme_and_concept: string[];
  decoration_ideas: string[];
  catering_ideas: string[];
  entertainment_ideas: string[];
  guest_experience_suggestions: string[];
  practical_recommendations: string[];
}

export interface BudgetCategoryAllocation {
  category: string;
  suggested_amount: number;
  currency: string;
  rationale: string;
  source_type: string;
  tax_rate?: number | null;
  tax_included?: boolean | null;
}

export interface PlanBudgetProposal {
  allocations: BudgetCategoryAllocation[];
  total_allocated: number;
  target_budget?: number | null;
  budget_provenance?: 'user_provided' | 'user_approved' | 'ai_suggested' | 'benchmark_estimate' | 'unknown' | string;
  currency: string;
  remaining_budget?: number | null;
  variance_amount?: number | null;
  contingency_amount: number;
  contingency_percentage?: number | null;
  contingency_calculation_basis?: string | null;
  tax_calculation_policy?: 'standard' | 'inclusive' | 'exclusive';
  is_within_budget?: boolean | null;
  financial_alerts: string[];
  budget_assumptions?: string[];
  estimate_provenance_notice: string;
}

export interface VendorChecklistItem {
  category: string;
  requirement_title: string;
  description: string;
  suggested_quantity_or_capacity?: string | null;
  important_questions_to_ask: string[];
  priority: string;
  selection_considerations: string[];
}

export interface TaskDependencySpec {
  predecessor_title: string;
  dependency_type?: 'finish_to_start' | 'start_to_start' | 'finish_to_finish' | 'start_to_finish';
}

export interface PlanTimelineTask {
  task_title: string;
  description: string;
  category: string;
  priority: string;
  stage: string;
  suggested_due_date?: string | null;
  relative_timing: string;
  dependencies: (string | TaskDependencySpec)[];
  why_it_matters: string;
}

export interface GeneratedEventPlan {
  id: string;
  brief: PlanEventBrief;
  personalized_ideas: PlanPersonalizedIdeas;
  budget_proposal: PlanBudgetProposal;
  vendor_checklist: VendorChecklistItem[];
  timeline: PlanTimelineTask[];
  provider: 'gemini' | 'deterministic_fallback';
  model?: string | null;
  is_live_ai: boolean;
  status: string;
  disclaimer: string;
  created_at: string;
}

export interface AssistantStatusResponse {
  ai_enabled: boolean;
  ai_provider: string;
  configured_model: string;
  is_live_key_configured: boolean;
  service_status: 'ready_live' | 'ready_fallback' | 'disabled';
  supported_event_types: string[];
  disclaimer: string;
}

export interface PlanGenerationRequest {
  user_prompt: string;
  event_type?: string;
  event_name?: string;
  location?: string;
  guest_count?: number;
  target_budget?: number;
  budget_provenance?: string;
  currency?: string;
  event_date?: string;
}

export interface PlanRefinementRequest {
  existing_plan: GeneratedEventPlan;
  refinement_instructions: string;
}

export interface PlanApprovalFinancialSummary {
  total_allocated: number;
  contingency_amount: number;
  contingency_percentage?: number;
  tax_calculation_policy?: string;
  total_tax?: number;
  grand_total?: number | null;
  target_budget?: number | null;
  budget_provenance?: string;
  remaining_budget?: number | null;
  is_within_budget?: boolean | null;
  currency: string;
}

export interface PlanApprovalRequest {
  plan: GeneratedEventPlan;
  idempotency_key: string;
  confirm_approval: boolean;
  initial_event_status?: string;
  tax_calculation_policy?: string;
  contingency_percentage?: number;
}

export interface PlanApprovalResponse {
  success: boolean;
  event_id: string;
  event_name: string;
  event_type: string;
  status: string;
  location?: string | null;
  expected_attendees?: number | null;
  event_date?: string | null;
  created_requirements_count: number;
  budget_id: string;
  created_line_items_count: number;
  created_tasks_count: number;
  created_dependencies_count: number;
  financial_summary: PlanApprovalFinancialSummary;
  message: string;
  idempotency_key: string;
  committed_at: string;
}

export interface ConversationMemory {
  event_type?: string | null;
  event_name?: string | null;
  occasion?: string | null;
  theme?: string | null;
  scale?: string | null;
  duration?: string | null;
  format_type?: string | null;
  location?: string | null;
  expected_guest_count?: number | null;
  event_date?: string | null;
  event_time?: string | null;
  target_budget?: number | null;
  budget_provenance: string;
  currency: string;
  venue_preferences?: string | null;
  food_preferences?: string | null;
  dietary_requirements?: string | null;
  entertainment_preferences?: string | null;
  decoration_preferences?: string | null;
  other_instructions?: string | null;
  confirmed_fields: string[];
  missing_fields: string[];
  last_question_asked?: string | null;
  plan_generated: boolean;
  ready_for_plan: boolean;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  content: string;
  reply_type: 'greeting' | 'discovery_question' | 'plan_generated' | 'plan_refined' | 'general' | 'user_turn';
  current_question?: string | null;
  structured_plan?: GeneratedEventPlan | null;
  suggested_prompts: string[];
  created_at: string;
}

export interface AssistantChatRequest {
  message: string;
  session_id?: string | null;
  event_id?: string | null;
  request_plan_generation?: boolean;
}

export interface AssistantChatResponse {
  session_id: string;
  message: string;
  reply_type: 'greeting' | 'discovery_question' | 'plan_generated' | 'plan_refined' | 'general';
  current_question?: string | null;
  structured_plan?: GeneratedEventPlan | null;
  memory: ConversationMemory;
  suggested_prompts: string[];
}

export interface ConversationSessionResponse {
  session_id: string;
  title: string;
  event_id?: string | null;
  messages: ChatMessage[];
  memory: ConversationMemory;
  created_at: string;
  updated_at: string;
}

export interface ConversationMemoryUpdateRequest {
  event_type?: string | null;
  event_name?: string | null;
  occasion?: string | null;
  theme?: string | null;
  scale?: string | null;
  duration?: string | null;
  format_type?: string | null;
  location?: string | null;
  expected_guest_count?: number | null;
  event_date?: string | null;
  event_time?: string | null;
  target_budget?: number | null;
  budget_provenance?: string;
  venue_preferences?: string | null;
  food_preferences?: string | null;
  dietary_requirements?: string | null;
  entertainment_preferences?: string | null;
  decoration_preferences?: string | null;
  other_instructions?: string | null;
}


