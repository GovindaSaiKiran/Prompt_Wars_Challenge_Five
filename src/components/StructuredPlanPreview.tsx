import React, { useState } from 'react';
import {
  Calendar,
  MapPin,
  Users,
  DollarSign,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Sparkles,
  Edit2,
  Save,
  X,
  Plus,
  Trash2,
  Clock,
  Briefcase,
  ShieldAlert,
  Send,
  RotateCcw,
  Info,
  Check,
  ChevronRight,
  TrendingDown,
  Layers,
  ListTodo,
  FileText,
  Lightbulb,
  Copy,
  Database,
  ShieldCheck,
} from 'lucide-react';
import {
  GeneratedEventPlan,
  BudgetCategoryAllocation,
  VendorChecklistItem,
  PlanTimelineTask,
  PlanApprovalResponse,
} from '../types/planning';
import { formatInr } from '../utils/ledgerMath';
import { approveEventPlanApi } from '../services/assistantApi';

interface StructuredPlanPreviewProps {
  plan: GeneratedEventPlan;
  onUpdatePlan: (updatedPlan: GeneratedEventPlan) => void;
  onRefinePlan: (instructions: string) => Promise<void>;
  isRefining?: boolean;
  onLoadIntoLedger?: () => void;
  onPlanApproved?: (response: PlanApprovalResponse) => void;
}

export const StructuredPlanPreview: React.FC<StructuredPlanPreviewProps> = ({
  plan,
  onUpdatePlan,
  onRefinePlan,
  isRefining = false,
  onLoadIntoLedger,
  onPlanApproved,
}) => {
  const [activeTab, setActiveTab] = useState<'brief' | 'ideas' | 'budget' | 'checklist' | 'timeline'>('brief');
  const [isEditingBrief, setIsEditingBrief] = useState(false);
  const [isUserEdited, setIsUserEdited] = useState(false);
  const [refinementText, setRefinementText] = useState('');
  const [refinementSuccessMsg, setRefinementSuccessMsg] = useState<string | null>(null);

  // Approval & Database Commitment State
  const [isApprovalModalOpen, setIsApprovalModalOpen] = useState(false);
  const [isApproving, setIsApproving] = useState(false);
  const [approvalConfirmed, setApprovalConfirmed] = useState(false);
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [approvalSuccess, setApprovalSuccess] = useState<PlanApprovalResponse | null>(null);
  const [copiedEventId, setCopiedEventId] = useState(false);

  // Editable Brief Local State
  const [briefForm, setBriefForm] = useState({
    eventName: plan.brief.event_name,
    eventType: plan.brief.event_type,
    location: plan.brief.location || '',
    guestCount: plan.brief.expected_guest_count || 100,
    targetBudget: plan.brief.target_budget != null ? plan.brief.target_budget : '',
    eventDate: plan.brief.event_date || '',
  });

  const handleSaveBrief = () => {
    const parsedBudget = briefForm.targetBudget !== '' && !isNaN(Number(briefForm.targetBudget)) && Number(briefForm.targetBudget) > 0
      ? Number(briefForm.targetBudget)
      : null;
    const newProv = parsedBudget != null ? 'user_provided' : (plan.brief.budget_provenance || 'unknown');

    const updated: GeneratedEventPlan = {
      ...plan,
      brief: {
        ...plan.brief,
        event_name: briefForm.eventName,
        event_type: briefForm.eventType,
        location: briefForm.location || null,
        expected_guest_count: Number(briefForm.guestCount) || null,
        target_budget: parsedBudget,
        budget_provenance: newProv,
        event_date: briefForm.eventDate || null,
      },
      budget_proposal: {
        ...plan.budget_proposal,
        target_budget: parsedBudget,
        budget_provenance: newProv,
        remaining_budget: parsedBudget != null ? parsedBudget - plan.budget_proposal.total_allocated : null,
        is_within_budget: parsedBudget != null ? plan.budget_proposal.total_allocated <= parsedBudget : null,
      },
    };
    onUpdatePlan(updated);
    setIsEditingBrief(false);
    setIsUserEdited(true);
  };

  const handleAllocationAmountChange = (index: number, newAmount: number) => {
    const updatedAllocations = [...plan.budget_proposal.allocations];
    const item = updatedAllocations[index];
    if (!item) return;

    updatedAllocations[index] = {
      ...item,
      suggested_amount: Math.max(0, newAmount),
      source_type: 'user_edited',
    };

    // Calculate new total allocated for local preview
    const newTotal = updatedAllocations.reduce((sum, a) => sum + (Number(a.suggested_amount) || 0), 0);
    const target = plan.budget_proposal.target_budget;
    const remaining = target != null ? target - newTotal : null;

    const updated: GeneratedEventPlan = {
      ...plan,
      budget_proposal: {
        ...plan.budget_proposal,
        allocations: updatedAllocations,
        total_allocated: newTotal,
        remaining_budget: remaining,
        is_within_budget: target != null ? newTotal <= target : null,
      },
    };

    onUpdatePlan(updated);
    setIsUserEdited(true);
  };

  const handleUpdateChecklistItem = (index: number, updatedItem: Partial<VendorChecklistItem>) => {
    const list = [...plan.vendor_checklist];
    list[index] = { ...list[index], ...updatedItem };
    onUpdatePlan({ ...plan, vendor_checklist: list });
    setIsUserEdited(true);
  };

  const handleUpdateTimelineTask = (index: number, updatedTask: Partial<PlanTimelineTask>) => {
    const list = [...plan.timeline];
    list[index] = { ...list[index], ...updatedTask };
    onUpdatePlan({ ...plan, timeline: list });
    setIsUserEdited(true);
  };

  const handleQuickRefinement = async (instruction: string) => {
    setRefinementText(instruction);
    try {
      await onRefinePlan(instruction);
      setRefinementSuccessMsg(`Refinement applied: "${instruction}"`);
      setTimeout(() => setRefinementSuccessMsg(null), 4000);
      setRefinementText('');
    } catch {
      // handled by parent
    }
  };

  const handleSubmitRefinement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!refinementText.trim() || isRefining) return;
    try {
      await onRefinePlan(refinementText.trim());
      setRefinementSuccessMsg(`Refinement applied: "${refinementText.trim()}"`);
      setTimeout(() => setRefinementSuccessMsg(null), 4000);
      setRefinementText('');
    } catch {
      // parent catches
    }
  };

  const handleCommitApproval = async () => {
    if (!approvalConfirmed || isApproving) return;
    setIsApproving(true);
    setApprovalError(null);

    try {
      const idempotencyKey =
        typeof crypto !== 'undefined' && crypto.randomUUID
          ? crypto.randomUUID()
          : `plan-approve-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;

      const res = await approveEventPlanApi({
        plan,
        idempotency_key: idempotencyKey,
        confirm_approval: true,
        initial_event_status: 'planning',
      });

      setApprovalSuccess(res);
      setIsApprovalModalOpen(false);
      if (onPlanApproved) {
        onPlanApproved(res);
      }
    } catch (err: any) {
      setApprovalError(err.message || 'Failed to commit plan to database.');
    } finally {
      setIsApproving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Persistent Plan Approval Success Banner */}
      {approvalSuccess && (
        <div className="bg-[#DCFCE7] border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[#16A34A] text-white flex items-center justify-center font-black border-2 border-black shadow-[2px_2px_0px_0px_#000] shrink-0">
                <Check className="w-6 h-6 stroke-[3]" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2 py-0.5 rounded-md bg-[#166534] text-white font-black uppercase tracking-wider">
                    Committed to Database
                  </span>
                  <span className="text-xs font-bold text-slate-600">
                    {new Date(approvalSuccess.committed_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
                <h3 className="text-lg font-black text-black">
                  Plan Approved & Committed: {approvalSuccess.event_name}
                </h3>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(approvalSuccess.event_id);
                  setCopiedEventId(true);
                  setTimeout(() => setCopiedEventId(false), 2000);
                }}
                className="flex items-center gap-1.5 bg-white hover:bg-slate-50 text-black font-black px-3 py-1.5 rounded-xl text-xs border border-black shadow-[1.5px_1.5px_0px_0px_#000] transition-all"
              >
                {copiedEventId ? <Check className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedEventId ? 'Copied ID' : 'Copy Event ID'}</span>
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-black/15 text-xs">
            <div className="bg-white/80 p-2.5 rounded-xl border border-black/20">
              <span className="text-slate-500 font-bold block text-[10px] uppercase">Event ID</span>
              <span className="font-mono font-bold text-slate-800 truncate block" title={approvalSuccess.event_id}>
                {approvalSuccess.event_id.substring(0, 13)}...
              </span>
            </div>
            <div className="bg-white/80 p-2.5 rounded-xl border border-black/20">
              <span className="text-slate-500 font-bold block text-[10px] uppercase">Requirements</span>
              <span className="font-black text-slate-800">{approvalSuccess.created_requirements_count} Items</span>
            </div>
            <div className="bg-white/80 p-2.5 rounded-xl border border-black/20">
              <span className="text-slate-500 font-bold block text-[10px] uppercase">Budget Line Items</span>
              <span className="font-black text-slate-800">{approvalSuccess.created_line_items_count} Items ({formatInr(approvalSuccess.financial_summary.total_allocated)})</span>
            </div>
            <div className="bg-white/80 p-2.5 rounded-xl border border-black/20">
              <span className="text-slate-500 font-bold block text-[10px] uppercase">Tasks & Deps</span>
              <span className="font-black text-slate-800">{approvalSuccess.created_tasks_count} Tasks ({approvalSuccess.created_dependencies_count} Deps)</span>
            </div>
          </div>
        </div>
      )}

      {/* Header Banner & Metadata Badges */}
      <div className="bg-white border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] relative overflow-hidden">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs px-2.5 py-1 rounded-lg bg-[#FFE600] text-black font-black uppercase tracking-wider border border-black shadow-[1px_1px_0px_0px_#000]">
                {plan.brief.event_type}
              </span>

              {/* Live Gemini vs Fallback Badge */}
              {plan.is_live_ai ? (
                <span className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg bg-[#DCFCE7] text-[#166534] font-black border border-black shadow-[1px_1px_0px_0px_#000]">
                  <Sparkles className="w-3.5 h-3.5 text-[#16a34a]" />
                  <span>Synthesized with Gemini ({plan.model || 'gemini-2.5-flash'})</span>
                </span>
              ) : (
                <span className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg bg-[#FEF08A] text-[#854D0E] font-black border border-black shadow-[1px_1px_0px_0px_#000]">
                  <span className="w-2 h-2 rounded-full bg-[#EAB308] border border-black" />
                  <span>Deterministic Fallback Engine</span>
                </span>
              )}

              {/* User Edited Badge */}
              {isUserEdited && (
                <span className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-[#BAE6FD] text-[#075985] font-black border border-black shadow-[1px_1px_0px_0px_#000]">
                  <Edit2 className="w-3 h-3" />
                  <span>User-Edited Draft</span>
                </span>
              )}

              <span className="text-xs px-2.5 py-1 rounded-lg bg-[#F8F5EE] text-slate-700 font-bold border border-black/40">
                Draft Preview (Non-Persistent)
              </span>
            </div>

            <h2 className="text-2xl sm:text-3xl font-black text-black font-heading tracking-tight pt-1">
              {plan.brief.event_name}
            </h2>

            <div className="flex flex-wrap items-center gap-4 text-xs font-bold text-slate-700 pt-1">
              <span className="flex items-center gap-1">
                <MapPin className="w-3.5 h-3.5 text-black" />
                {plan.brief.location || 'Location Not Specified'}
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Users className="w-3.5 h-3.5 text-black" />
                {plan.brief.expected_guest_count ? `${plan.brief.expected_guest_count} Attendees` : 'Headcount TBD'}
              </span>
              <span>•</span>
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-black" />
                {plan.brief.event_date ? new Date(plan.brief.event_date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Date Unscheduled (Staged Milestones)'}
              </span>
              <span>•</span>
              <span className="flex items-center gap-1 font-black text-black">
                <DollarSign className="w-3.5 h-3.5 text-black" />
                {plan.brief.budget_provenance === 'unknown' || (!plan.brief.target_budget && plan.budget_proposal.total_allocated === 0)
                  ? 'Budget: Not provided'
                  : plan.brief.budget_provenance === 'ai_suggested' || plan.brief.budget_provenance === 'benchmark_estimate'
                  ? `Estimate: ~${formatInr(plan.brief.target_budget || plan.budget_proposal.total_allocated)} (AI-Suggested)`
                  : `Ceiling: ${formatInr(plan.brief.target_budget)}`}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            {/* Human Approval Commit Button */}
            {!approvalSuccess ? (
              <button
                onClick={() => {
                  setApprovalConfirmed(false);
                  setApprovalError(null);
                  setIsApprovalModalOpen(true);
                }}
                className="flex items-center gap-2 bg-[#22C55E] hover:bg-[#16A34A] text-white font-black px-4 py-2.5 rounded-xl text-xs border-2 border-black shadow-[2.5px_2.5px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] transition-all"
              >
                <ShieldCheck className="w-4 h-4 stroke-[2.5]" />
                <span>Approve & Commit Plan</span>
              </button>
            ) : (
              <span className="flex items-center gap-1.5 bg-[#DCFCE7] text-[#166534] font-black px-3.5 py-2 rounded-xl text-xs border-2 border-black shadow-[2px_2px_0px_0px_#000]">
                <Check className="w-4 h-4 stroke-[3]" />
                <span>Committed to DB</span>
              </span>
            )}

            {onLoadIntoLedger && (
              <button
                onClick={onLoadIntoLedger}
                className="flex items-center gap-2 bg-[#FFE600] hover:bg-[#FACC15] text-black font-black px-4 py-2.5 rounded-xl text-xs border-2 border-black shadow-[2.5px_2.5px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] transition-all"
              >
                <Layers className="w-4 h-4" />
                <span>Load into Ledger</span>
              </button>
            )}
          </div>
        </div>

        {/* Disclaimer Strip */}
        <div className="mt-4 pt-3 border-t border-black/10 flex items-start gap-2 text-[11px] text-slate-600 font-medium">
          <Info className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
          <p className="leading-snug">{plan.disclaimer}</p>
        </div>
      </div>

      {/* Interactive Tab Navigation */}
      <div className="flex flex-wrap items-center gap-2 bg-white p-1.5 rounded-2xl border-2 border-black shadow-[3px_3px_0px_0px_#000]">
        <button
          onClick={() => setActiveTab('brief')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-black transition-all ${
            activeTab === 'brief'
              ? 'bg-[#FFE600] text-black border-2 border-black shadow-[2px_2px_0px_0px_#000]'
              : 'text-slate-700 hover:text-black border-2 border-transparent'
          }`}
        >
          <FileText className="w-4 h-4 stroke-[2.5]" />
          <span>A. Event Brief</span>
        </button>

        <button
          onClick={() => setActiveTab('ideas')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-black transition-all ${
            activeTab === 'ideas'
              ? 'bg-[#FEF08A] text-black border-2 border-black shadow-[2px_2px_0px_0px_#000]'
              : 'text-slate-700 hover:text-black border-2 border-transparent'
          }`}
        >
          <Lightbulb className="w-4 h-4 stroke-[2.5]" />
          <span>B. Personalized Ideas</span>
        </button>

        <button
          onClick={() => setActiveTab('budget')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-black transition-all ${
            activeTab === 'budget'
              ? 'bg-[#BAE6FD] text-black border-2 border-black shadow-[2px_2px_0px_0px_#000]'
              : 'text-slate-700 hover:text-black border-2 border-transparent'
          }`}
        >
          <DollarSign className="w-4 h-4 stroke-[2.5]" />
          <span>
            {plan.budget_proposal.budget_provenance === 'unknown' || (!plan.budget_proposal.target_budget && plan.budget_proposal.total_allocated === 0)
              ? 'C. Budget Proposal (Not provided)'
              : plan.budget_proposal.budget_provenance === 'ai_suggested' || plan.budget_proposal.budget_provenance === 'benchmark_estimate'
              ? `C. Budget Proposal (~${formatInr(plan.budget_proposal.total_allocated || plan.budget_proposal.target_budget || 0)} Estimate)`
              : `C. Budget Proposal (${formatInr(plan.budget_proposal.total_allocated)})`}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('checklist')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-black transition-all ${
            activeTab === 'checklist'
              ? 'bg-[#D8B4FE] text-black border-2 border-black shadow-[2px_2px_0px_0px_#000]'
              : 'text-slate-700 hover:text-black border-2 border-transparent'
          }`}
        >
          <ListTodo className="w-4 h-4 stroke-[2.5]" />
          <span>D. Vendor Checklist ({plan.vendor_checklist.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('timeline')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-black transition-all ${
            activeTab === 'timeline'
              ? 'bg-[#FFB5C5] text-black border-2 border-black shadow-[2px_2px_0px_0px_#000]'
              : 'text-slate-700 hover:text-black border-2 border-transparent'
          }`}
        >
          <Clock className="w-4 h-4 stroke-[2.5]" />
          <span>E. Staged Timeline ({plan.timeline.length})</span>
        </button>
      </div>

      {/* =========================================================================
          TAB A: EVENT BRIEF (SPECS, MISSING INFO, ASSUMPTIONS)
      ========================================================================= */}
      {activeTab === 'brief' && (
        <div className="space-y-6">
          <div className="bg-white border-2 border-black rounded-2xl p-6 shadow-[4px_4px_0px_0px_#000] space-y-6">
            <div className="flex items-center justify-between border-b-2 border-black pb-3">
              <div>
                <h3 className="text-lg font-black text-black font-heading uppercase tracking-tight">
                  Event Brief & Boundary Conditions
                </h3>
                <p className="text-xs text-slate-600 font-bold">
                  Core parameters, confirmed facts, and missing data points detected by the engine.
                </p>
              </div>

              {!isEditingBrief ? (
                <button
                  onClick={() => setIsEditingBrief(true)}
                  className="flex items-center gap-1.5 bg-[#F8F5EE] hover:bg-[#FFE600] px-3 py-1.5 rounded-xl border-2 border-black text-xs font-black shadow-[2px_2px_0px_0px_#000] transition-all"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                  <span>Edit Specifications</span>
                </button>
              ) : (
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSaveBrief}
                    className="flex items-center gap-1 bg-[#DCFCE7] hover:bg-[#BBF7D0] px-3 py-1.5 rounded-xl border-2 border-black text-xs font-black shadow-[2px_2px_0px_0px_#000] transition-all"
                  >
                    <Save className="w-3.5 h-3.5" />
                    <span>Save Edits</span>
                  </button>
                  <button
                    onClick={() => setIsEditingBrief(false)}
                    className="px-2.5 py-1.5 rounded-xl border-2 border-black text-xs font-bold hover:bg-slate-100"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
            </div>

            {/* Editable or Display Brief Grid */}
            {isEditingBrief ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-black text-black uppercase mb-1">Event Name</label>
                  <input
                    type="text"
                    value={briefForm.eventName}
                    onChange={(e) => setBriefForm({ ...briefForm, eventName: e.target.value })}
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-3 py-2 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-black text-black uppercase mb-1">Event Type</label>
                  <input
                    type="text"
                    value={briefForm.eventType}
                    onChange={(e) => setBriefForm({ ...briefForm, eventType: e.target.value })}
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-3 py-2 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-black text-black uppercase mb-1">Destination / City</label>
                  <input
                    type="text"
                    value={briefForm.location}
                    onChange={(e) => setBriefForm({ ...briefForm, location: e.target.value })}
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-3 py-2 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-black text-black uppercase mb-1">Guest Count</label>
                  <input
                    type="number"
                    value={briefForm.guestCount}
                    onChange={(e) => setBriefForm({ ...briefForm, guestCount: Number(e.target.value) })}
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-3 py-2 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-black text-black uppercase mb-1">Target Budget (₹)</label>
                  <input
                    type="number"
                    value={briefForm.targetBudget}
                    onChange={(e) => setBriefForm({ ...briefForm, targetBudget: Number(e.target.value) })}
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-3 py-2 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-black text-black uppercase mb-1">Event Date (Optional)</label>
                  <input
                    type="date"
                    value={briefForm.eventDate}
                    onChange={(e) => setBriefForm({ ...briefForm, eventDate: e.target.value })}
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-3 py-2 text-xs font-bold focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
                  />
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                <div className="bg-[#F8F5EE] border-2 border-black rounded-xl p-3 shadow-[2px_2px_0px_0px_#000]">
                  <div className="text-[10px] font-black text-slate-500 uppercase">Format</div>
                  <div className="text-sm font-black text-black capitalize truncate">{plan.brief.event_type}</div>
                </div>

                <div className="bg-[#F8F5EE] border-2 border-black rounded-xl p-3 shadow-[2px_2px_0px_0px_#000]">
                  <div className="text-[10px] font-black text-slate-500 uppercase">Location</div>
                  <div className="text-sm font-black text-black truncate">{plan.brief.location || 'Flexible'}</div>
                </div>

                <div className="bg-[#F8F5EE] border-2 border-black rounded-xl p-3 shadow-[2px_2px_0px_0px_#000]">
                  <div className="text-[10px] font-black text-slate-500 uppercase">Attendees</div>
                  <div className="text-sm font-black text-black">{plan.brief.expected_guest_count || 'TBD'} pax</div>
                </div>

                <div className="bg-[#F8F5EE] border-2 border-black rounded-xl p-3 shadow-[2px_2px_0px_0px_#000]">
                  <div className="text-[10px] font-black text-slate-500 uppercase">Target Budget</div>
                  <div className="text-sm font-black text-black">
                    {plan.brief.budget_provenance === 'unknown' || (!plan.brief.target_budget && plan.budget_proposal.total_allocated === 0)
                      ? 'Not provided'
                      : plan.brief.budget_provenance === 'ai_suggested' || plan.brief.budget_provenance === 'benchmark_estimate'
                      ? `~${formatInr(plan.brief.target_budget || plan.budget_proposal.total_allocated)} (Estimate)`
                      : formatInr(plan.brief.target_budget)}
                  </div>
                </div>

                <div className="bg-[#F8F5EE] border-2 border-black rounded-xl p-3 shadow-[2px_2px_0px_0px_#000]">
                  <div className="text-[10px] font-black text-slate-500 uppercase">Event Date</div>
                  <div className="text-sm font-black text-black truncate">{plan.brief.event_date || 'Relative Stages'}</div>
                </div>

                <div className="bg-[#F8F5EE] border-2 border-black rounded-xl p-3 shadow-[2px_2px_0px_0px_#000]">
                  <div className="text-[10px] font-black text-slate-500 uppercase">Currency</div>
                  <div className="text-sm font-black text-black">{plan.brief.currency}</div>
                </div>
              </div>
            )}

            {/* Confirmed, Missing, Assumptions 3-Column Section */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-2">
              {/* Confirmed Facts */}
              <div className="bg-[#F0FDF4] border-2 border-black rounded-2xl p-4 shadow-[3px_3px_0px_0px_#000] space-y-2.5">
                <div className="flex items-center gap-2 text-xs font-black text-[#166534] uppercase tracking-wider">
                  <CheckCircle2 className="w-4 h-4 text-[#16a34a]" />
                  <span>Confirmed Facts ({plan.brief.confirmed_information.length})</span>
                </div>
                <ul className="space-y-1.5 text-xs text-slate-700 font-bold">
                  {plan.brief.confirmed_information.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-1.5">
                      <span className="text-[#16a34a] font-black">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Missing Information Gaps */}
              <div className="bg-[#FFFBEB] border-2 border-black rounded-2xl p-4 shadow-[3px_3px_0px_0px_#000] space-y-2.5">
                <div className="flex items-center gap-2 text-xs font-black text-[#92400E] uppercase tracking-wider">
                  <HelpCircle className="w-4 h-4 text-[#d97706]" />
                  <span>Critical Information Gaps ({plan.brief.missing_information.length})</span>
                </div>
                {plan.brief.missing_information.length === 0 ? (
                  <p className="text-xs text-slate-500 italic">No missing information flags.</p>
                ) : (
                  <ul className="space-y-1.5 text-xs text-slate-700 font-bold">
                    {plan.brief.missing_information.map((item, idx) => (
                      <li key={idx} className="flex items-start gap-1.5">
                        <span className="text-[#d97706] font-black">?</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Planning Assumptions */}
              <div className="bg-[#EFF6FF] border-2 border-black rounded-2xl p-4 shadow-[3px_3px_0px_0px_#000] space-y-2.5">
                <div className="flex items-center gap-2 text-xs font-black text-[#1E40AF] uppercase tracking-wider">
                  <Info className="w-4 h-4 text-[#2563eb]" />
                  <span>Engine Assumptions ({plan.brief.explicit_assumptions.length})</span>
                </div>
                <ul className="space-y-1.5 text-xs text-slate-700 font-bold">
                  {plan.brief.explicit_assumptions.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-1.5">
                      <span className="text-[#2563eb] font-black">→</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB B: PERSONALIZED IDEAS
      ========================================================================= */}
      {activeTab === 'ideas' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {/* Themes */}
          <div className="bg-white border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-3">
            <div className="flex items-center gap-2 border-b-2 border-black pb-2 text-sm font-black text-black uppercase">
              <span className="text-lg">🎨</span>
              <span>Theme & Atmosphere</span>
            </div>
            <ul className="space-y-2 text-xs font-bold text-slate-800">
              {plan.personalized_ideas.theme_and_concept.map((item, i) => (
                <li key={i} className="p-2.5 rounded-xl bg-[#F8F5EE] border border-black/20 flex items-start gap-2">
                  <span className="text-black font-black">#{i + 1}</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Decor Concepts */}
          <div className="bg-white border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-3">
            <div className="flex items-center gap-2 border-b-2 border-black pb-2 text-sm font-black text-black uppercase">
              <span className="text-lg">✨</span>
              <span>Decor & Lighting Concepts</span>
            </div>
            <ul className="space-y-2 text-xs font-bold text-slate-800">
              {plan.personalized_ideas.decoration_ideas.map((item, i) => (
                <li key={i} className="p-2.5 rounded-xl bg-[#F8F5EE] border border-black/20 flex items-start gap-2">
                  <span className="text-black font-black">#{i + 1}</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Catering */}
          <div className="bg-white border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-3">
            <div className="flex items-center gap-2 border-b-2 border-black pb-2 text-sm font-black text-black uppercase">
              <span className="text-lg">🍽️</span>
              <span>Catering & Menu Highlights</span>
            </div>
            <ul className="space-y-2 text-xs font-bold text-slate-800">
              {plan.personalized_ideas.catering_ideas.map((item, i) => (
                <li key={i} className="p-2.5 rounded-xl bg-[#F8F5EE] border border-black/20 flex items-start gap-2">
                  <span className="text-black font-black">#{i + 1}</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Entertainment */}
          <div className="bg-white border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-3">
            <div className="flex items-center gap-2 border-b-2 border-black pb-2 text-sm font-black text-black uppercase">
              <span className="text-lg">🎵</span>
              <span>Entertainment & Activities</span>
            </div>
            <ul className="space-y-2 text-xs font-bold text-slate-800">
              {plan.personalized_ideas.entertainment_ideas.map((item, i) => (
                <li key={i} className="p-2.5 rounded-xl bg-[#F8F5EE] border border-black/20 flex items-start gap-2">
                  <span className="text-black font-black">#{i + 1}</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Guest Experience */}
          <div className="bg-white border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-3">
            <div className="flex items-center gap-2 border-b-2 border-black pb-2 text-sm font-black text-black uppercase">
              <span className="text-lg">🎁</span>
              <span>Guest Experience Enhancements</span>
            </div>
            <ul className="space-y-2 text-xs font-bold text-slate-800">
              {plan.personalized_ideas.guest_experience_suggestions.map((item, i) => (
                <li key={i} className="p-2.5 rounded-xl bg-[#F8F5EE] border border-black/20 flex items-start gap-2">
                  <span className="text-black font-black">#{i + 1}</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Practical Tips */}
          <div className="bg-white border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-3">
            <div className="flex items-center gap-2 border-b-2 border-black pb-2 text-sm font-black text-black uppercase">
              <span className="text-lg">🛡️</span>
              <span>Practical Tips & Local Logistics</span>
            </div>
            <ul className="space-y-2 text-xs font-bold text-slate-800">
              {plan.personalized_ideas.practical_recommendations.map((item, i) => (
                <li key={i} className="p-2.5 rounded-xl bg-[#F8F5EE] border border-black/20 flex items-start gap-2">
                  <span className="text-black font-black">#{i + 1}</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB C: DETERMINISTIC BUDGET PROPOSAL
      ========================================================================= */}
      {activeTab === 'budget' && (
        <div className="space-y-5">
          {/* Missing Budget or AI-Suggested Banner */}
          {(() => {
            const prov = plan.budget_proposal.budget_provenance || plan.brief.budget_provenance || 'unknown';
            const isMissing = prov === 'unknown' || (!plan.budget_proposal.target_budget && plan.budget_proposal.total_allocated === 0);
            const isEstimate = prov === 'ai_suggested' || prov === 'benchmark_estimate';

            if (isMissing) {
              return (
                <div className="bg-[#FEF3C7] border-2 border-black rounded-2xl p-4 shadow-[3px_3px_0px_0px_#000] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <div className="text-xs font-black text-black uppercase flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 text-amber-700" />
                      <span>Target Budget Not Provided</span>
                    </div>
                    <p className="text-xs font-bold text-slate-800 mt-1">
                      EventPrice Intelligence never invents financial figures. No target budget ceiling was assumed. You can provide an explicit budget ceiling or ask for a market benchmark estimate.
                    </p>
                  </div>
                  <button
                    onClick={() => setIsEditingBrief(true)}
                    className="px-3.5 py-2 rounded-xl bg-white border-2 border-black font-black text-xs shadow-[2px_2px_0px_0px_#000] hover:bg-slate-50 transition-all shrink-0"
                  >
                    Enter Target Budget
                  </button>
                </div>
              );
            }

            if (isEstimate) {
              return (
                <div className="bg-[#E0F2FE] border-2 border-black rounded-2xl p-4 shadow-[3px_3px_0px_0px_#000] space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-black text-[#0369A1] uppercase flex items-center gap-1.5">
                      <Sparkles className="w-4 h-4 text-[#0284C7]" />
                      <span>AI-Suggested Estimate (Unapproved)</span>
                    </div>
                    <span className="text-[10px] font-black uppercase px-2 py-0.5 bg-white border border-black rounded-md">
                      Planning Benchmark
                    </span>
                  </div>
                  <p className="text-xs font-bold text-slate-800">
                    This budget is an AI-suggested starting estimate based on market assumptions. It is NOT your confirmed budget ceiling until you review and approve it.
                  </p>
                  {plan.budget_proposal.budget_assumptions && plan.budget_proposal.budget_assumptions.length > 0 && (
                    <div className="pt-2 border-t border-black/10">
                      <span className="text-[10px] font-black uppercase text-slate-600 block mb-1">Modeling Assumptions:</span>
                      <ul className="text-xs font-bold text-slate-700 space-y-1 list-disc pl-5">
                        {plan.budget_proposal.budget_assumptions.map((assump, idx) => (
                          <li key={idx}>{assump}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              );
            }

            return null;
          })()}

          {/* Financial Summary Cards */}
          {(() => {
            const prov = plan.budget_proposal.budget_provenance || plan.brief.budget_provenance || 'unknown';
            const isMissing = prov === 'unknown' || (!plan.budget_proposal.target_budget && plan.budget_proposal.total_allocated === 0);
            const isEstimate = prov === 'ai_suggested' || prov === 'benchmark_estimate';

            return (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-white border-2 border-black rounded-2xl p-4 shadow-[3px_3px_0px_0px_#000]">
                  <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">
                    {isMissing ? 'Proposed Allocation' : isEstimate ? 'Estimated Total' : 'Total Proposed'}
                  </div>
                  <div className="text-2xl font-black text-black mt-1 font-heading">
                    {isMissing ? 'Not provided' : formatInr(plan.budget_proposal.total_allocated)}
                  </div>
                  <div className="text-[10px] font-bold text-slate-500 mt-1">
                    {isMissing ? 'No budget invented' : 'Authoritative Python Total'}
                  </div>
                </div>

                <div className="bg-white border-2 border-black rounded-2xl p-4 shadow-[3px_3px_0px_0px_#000]">
                  <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Emergency Contingency</div>
                  <div className="text-2xl font-black text-[#854D0E] mt-1 font-heading">
                    {isMissing ? '—' : formatInr(plan.budget_proposal.contingency_amount)}
                  </div>
                  <div className="text-[10px] font-bold text-slate-500 mt-1">
                    {isMissing
                      ? 'Requires target budget'
                      : plan.budget_proposal.contingency_calculation_basis || 'Protected Buffer (10-15%)'}
                  </div>
                </div>

                <div className="bg-white border-2 border-black rounded-2xl p-4 shadow-[3px_3px_0px_0px_#000]">
                  <div className="text-[10px] font-black text-slate-500 uppercase tracking-wider">Target Ceiling</div>
                  <div className="text-2xl font-black text-black mt-1 font-heading">
                    {isMissing
                      ? 'Not provided'
                      : isEstimate
                      ? `~${formatInr(plan.budget_proposal.target_budget || plan.budget_proposal.total_allocated)}`
                      : plan.budget_proposal.target_budget
                      ? formatInr(plan.budget_proposal.target_budget)
                      : 'Not provided'}
                  </div>
                  <div className="text-[10px] font-bold text-slate-500 mt-1">
                    {isMissing
                      ? 'User budget unassigned'
                      : isEstimate
                      ? 'AI-suggested estimate (Unapproved)'
                      : 'User Budget Boundary'}
                  </div>
                </div>

                <div className={`border-2 border-black rounded-2xl p-4 shadow-[3px_3px_0px_0px_#000] ${
                  isMissing || isEstimate || plan.budget_proposal.is_within_budget == null
                    ? 'bg-[#F8F5EE]'
                    : plan.budget_proposal.is_within_budget
                    ? 'bg-[#DCFCE7]'
                    : 'bg-[#FEE2E2]'
                }`}>
                  <div className="text-[10px] font-black text-slate-700 uppercase tracking-wider">Budget Variance</div>
                  <div className={`text-2xl font-black mt-1 font-heading ${
                    isMissing || isEstimate || plan.budget_proposal.is_within_budget == null
                      ? 'text-slate-600'
                      : plan.budget_proposal.is_within_budget
                      ? 'text-[#166534]'
                      : 'text-[#991B1B]'
                  }`}>
                    {isMissing || isEstimate || plan.budget_proposal.remaining_budget == null
                      ? 'N/A'
                      : `${plan.budget_proposal.remaining_budget >= 0 ? '+' : ''}${formatInr(plan.budget_proposal.remaining_budget)}`}
                  </div>
                  <div className="text-[10px] font-bold text-slate-700 mt-1">
                    {isMissing
                      ? 'Ceiling required'
                      : isEstimate
                      ? 'Pending user approval'
                      : plan.budget_proposal.is_within_budget == null
                      ? 'N/A'
                      : plan.budget_proposal.is_within_budget
                      ? 'Within Target Ceiling'
                      : 'Budget Deficit Alert'}
                  </div>
                </div>
              </div>
            );
          })()}

          {/* Financial Alerts Banner */}
          {plan.budget_proposal.financial_alerts.length > 0 && (
            <div className="bg-[#FEF08A] border-2 border-black rounded-2xl p-4 shadow-[3px_3px_0px_0px_#000] space-y-1">
              <div className="flex items-center gap-2 text-xs font-black text-black uppercase">
                <AlertTriangle className="w-4 h-4 text-black" />
                <span>Deterministic Financial Notices</span>
              </div>
              <ul className="text-xs font-bold text-slate-800 space-y-1 pl-6 list-disc">
                {plan.budget_proposal.financial_alerts.map((alert, i) => (
                  <li key={i}>{alert}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Allocation Items Table */}
          <div className="bg-white border-2 border-black rounded-2xl shadow-[4px_4px_0px_0px_#000] overflow-hidden">
            <div className="px-5 py-4 border-b-2 border-black flex items-center justify-between">
              <div>
                <h4 className="font-black text-black text-base uppercase font-heading">Category Allocation Proposals</h4>
                <p className="text-xs text-slate-600 font-bold">
                  Editable estimates calibrated via headcount benchmarks and structured AI synthesis.
                </p>
              </div>
              <div className="text-[11px] font-black px-2.5 py-1 rounded-lg bg-[#F8F5EE] border border-black">
                {plan.budget_proposal.allocations.length} Categories
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-bold">
                <thead className="bg-[#F8F5EE] border-b-2 border-black text-black uppercase text-[11px]">
                  <tr>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-4">Suggested Amount (₹)</th>
                    <th className="py-3 px-4">Share (%)</th>
                    <th className="py-3 px-4">Allocation Rationale</th>
                    <th className="py-3 px-4">Provenance</th>
                  </tr>
                </thead>
                <tbody className="divide-y-2 divide-black/10">
                  {plan.budget_proposal.allocations.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-slate-500 font-bold">
                        No budget allocations have been generated. Enter a target budget or request an AI-suggested estimate to build category line items.
                      </td>
                    </tr>
                  ) : (
                    plan.budget_proposal.allocations.map((alloc, idx) => {
                    const sharePct = plan.budget_proposal.total_allocated > 0
                      ? ((alloc.suggested_amount / plan.budget_proposal.total_allocated) * 100).toFixed(1)
                      : '0';

                    return (
                      <tr key={idx} className="hover:bg-[#FFFDF0] transition-colors">
                        <td className="py-3 px-4 font-black text-black capitalize">
                          {alloc.category}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-1.5">
                            <span className="text-slate-500 font-black">₹</span>
                            <input
                              type="number"
                              min="0"
                              value={alloc.suggested_amount}
                              onChange={(e) => handleAllocationAmountChange(idx, Number(e.target.value))}
                              className="w-28 bg-[#F8F5EE] border border-black rounded-lg px-2 py-1 text-xs font-black text-black focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
                            />
                          </div>
                        </td>
                        <td className="py-3 px-4 font-black text-slate-700">
                          {sharePct}%
                        </td>
                        <td className="py-3 px-4 text-slate-700 max-w-xs">
                          {alloc.rationale}
                        </td>
                        <td className="py-3 px-4">
                          <span className={`text-[10px] font-black px-2 py-0.5 rounded border border-black/40 ${
                            alloc.source_type === 'user_edited'
                              ? 'bg-[#BAE6FD] text-black'
                              : 'bg-[#F8F5EE] text-slate-600'
                          }`}>
                            {alloc.source_type === 'user_edited' ? 'User Edited' : 'Illustrative Estimate'}
                          </span>
                        </td>
                      </tr>
                    );
                  }))}
                </tbody>
              </table>
            </div>

            {/* Estimate Provenance Notice Footer */}
            <div className="p-4 bg-[#F8F5EE] border-t-2 border-black text-[11px] text-slate-600 font-bold flex items-start gap-2">
              <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <span className="text-black font-black uppercase tracking-wider block">Provenance Notice:</span>
                <p className="mt-0.5">{plan.budget_proposal.estimate_provenance_notice}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB D: VENDOR PROCUREMENT CHECKLIST
      ========================================================================= */}
      {activeTab === 'checklist' && (
        <div className="space-y-4">
          <div className="bg-white border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] flex items-center justify-between">
            <div>
              <h3 className="text-lg font-black text-black font-heading uppercase tracking-tight">
                Vendor Procurement & Vetting Checklist
              </h3>
              <p className="text-xs text-slate-600 font-bold">
                Actionable deliverables and critical questions to ask before signing contracts. (No fake vendor names or numbers).
              </p>
            </div>
            <span className="text-xs font-black px-3 py-1 bg-[#D8B4FE] text-black border-2 border-black rounded-xl shadow-[1.5px_1.5px_0px_0px_#000]">
              {plan.vendor_checklist.length} Categories
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {plan.vendor_checklist.map((item, idx) => (
              <div
                key={idx}
                className="bg-white border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-3 flex flex-col justify-between"
              >
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between gap-2 border-b-2 border-black pb-2">
                    <span className="text-xs font-black uppercase px-2 py-0.5 rounded bg-[#FFE600] text-black border border-black">
                      {item.category}
                    </span>
                    <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded border border-black ${
                      item.priority === 'critical'
                        ? 'bg-[#FEE2E2] text-[#991B1B]'
                        : item.priority === 'high'
                        ? 'bg-[#FEF3C7] text-[#92400E]'
                        : 'bg-[#F8F5EE] text-slate-700'
                    }`}>
                      {item.priority} Priority
                    </span>
                  </div>

                  <h4 className="text-base font-black text-black font-heading">
                    {item.requirement_title}
                  </h4>

                  <p className="text-xs text-slate-700 font-bold leading-relaxed">
                    {item.description}
                  </p>

                  {item.suggested_quantity_or_capacity && (
                    <div className="text-xs font-bold text-slate-800 bg-[#F8F5EE] p-2 rounded-xl border border-black/20">
                      <span className="text-black font-black">Sizing Guide: </span>
                      {item.suggested_quantity_or_capacity}
                    </div>
                  )}

                  {item.important_questions_to_ask.length > 0 && (
                    <div className="space-y-1.5 pt-1">
                      <div className="text-xs font-black text-black uppercase tracking-wider">
                        Vetting Questions to Ask:
                      </div>
                      <ul className="space-y-1 text-xs text-slate-700 font-bold">
                        {item.important_questions_to_ask.map((q, qIdx) => (
                          <li key={qIdx} className="flex items-start gap-1.5">
                            <span className="text-amber-600 font-black">?</span>
                            <span>{q}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {item.selection_considerations.length > 0 && (
                  <div className="pt-2 border-t border-black/10 flex flex-wrap gap-1.5">
                    {item.selection_considerations.map((c, cIdx) => (
                      <span key={cIdx} className="text-[10px] font-bold px-2 py-0.5 bg-slate-100 rounded-lg text-slate-700 border border-slate-300">
                        ✓ {c}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB E: STAGED TIMELINE TASKS
      ========================================================================= */}
      {activeTab === 'timeline' && (
        <div className="space-y-4">
          <div className="bg-white border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] flex items-center justify-between">
            <div>
              <h3 className="text-lg font-black text-black font-heading uppercase tracking-tight">
                Staged Timeline & Execution Milestones
              </h3>
              <p className="text-xs text-slate-600 font-bold">
                Sequential roadmap with relative stages and predecessor dependencies.
              </p>
            </div>
            <span className="text-xs font-black px-3 py-1 bg-[#FFB5C5] text-black border-2 border-black rounded-xl shadow-[1.5px_1.5px_0px_0px_#000]">
              {plan.timeline.length} Milestones
            </span>
          </div>

          <div className="space-y-3">
            {plan.timeline.map((task, idx) => (
              <div
                key={idx}
                className="bg-white border-2 border-black rounded-2xl p-4 shadow-[3px_3px_0px_0px_#000] hover:translate-x-[2px] transition-transform space-y-2"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-black/10 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="w-6 h-6 rounded-lg bg-[#FFE600] border border-black font-black text-black flex items-center justify-center text-xs">
                      {idx + 1}
                    </span>
                    <h4 className="text-sm font-black text-black font-heading">
                      {task.task_title}
                    </h4>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2 py-0.5 bg-[#BAE6FD] text-black font-black rounded-lg border border-black">
                      {task.relative_timing}
                    </span>
                    {task.suggested_due_date ? (
                      <span className="text-xs px-2 py-0.5 bg-[#DCFCE7] text-[#166534] font-black rounded-lg border border-black">
                        Due: {new Date(task.suggested_due_date).toLocaleDateString()}
                      </span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 bg-[#F8F5EE] text-slate-600 font-bold rounded-lg border border-black/30">
                        Date TBD (Staged)
                      </span>
                    )}
                    <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded border border-black ${
                      task.priority === 'critical' ? 'bg-[#FEE2E2] text-[#991B1B]' : 'bg-[#F8F5EE] text-slate-700'
                    }`}>
                      {task.priority}
                    </span>
                  </div>
                </div>

                <p className="text-xs text-slate-700 font-bold">
                  {task.description}
                </p>

                <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px] font-bold text-slate-600">
                  <div>
                    <span className="font-black text-black">Why It Matters: </span>
                    {task.why_it_matters}
                  </div>

                  {task.dependencies.length > 0 && (
                    <div className="flex items-center gap-1 text-[10px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-300">
                      <span>
                        Depends on:{' '}
                        {task.dependencies
                          .map((d) => (typeof d === 'string' ? d : `${d.predecessor_title} (${d.dependency_type || 'finish_to_start'})`))
                          .join(', ')}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* =========================================================================
          CONVERSATIONAL DRAFT REFINEMENT BAR
      ========================================================================= */}
      <div className="bg-white border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-black" />
            <h4 className="text-sm font-black text-black font-heading uppercase">
              Refine This Draft with AI
            </h4>
          </div>
          <span className="text-[11px] font-bold text-slate-500">
            Uses Backend Planning Engine (/api/v1/assistant/plan/refine)
          </span>
        </div>

        {/* Quick Refinement Chips */}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={isRefining}
            onClick={() => handleQuickRefinement('Reduce total budget by 15%')}
            className="text-xs font-black px-3 py-1.5 bg-[#F8F5EE] hover:bg-[#FFE600] text-black border border-black rounded-xl transition-all shadow-[1px_1px_0px_0px_#000] disabled:opacity-50"
          >
            📉 Cut Budget by 15%
          </button>
          <button
            type="button"
            disabled={isRefining}
            onClick={() => handleQuickRefinement('Add acoustic live music band and DJ')}
            className="text-xs font-black px-3 py-1.5 bg-[#F8F5EE] hover:bg-[#FFE600] text-black border border-black rounded-xl transition-all shadow-[1px_1px_0px_0px_#000] disabled:opacity-50"
          >
            🎸 Add Live Acoustic Band
          </button>
          <button
            type="button"
            disabled={isRefining}
            onClick={() => handleQuickRefinement('Focus on sustainable eco-friendly decor')}
            className="text-xs font-black px-3 py-1.5 bg-[#F8F5EE] hover:bg-[#FFE600] text-black border border-black rounded-xl transition-all shadow-[1px_1px_0px_0px_#000] disabled:opacity-50"
          >
            🌱 Eco-Friendly Decor
          </button>
          <button
            type="button"
            disabled={isRefining}
            onClick={() => handleQuickRefinement('Switch to authentic South Indian regional buffet')}
            className="text-xs font-black px-3 py-1.5 bg-[#F8F5EE] hover:bg-[#FFE600] text-black border border-black rounded-xl transition-all shadow-[1px_1px_0px_0px_#000] disabled:opacity-50"
          >
            🍲 Regional South Indian Menu
          </button>
        </div>

        {/* Custom Refinement Input Form */}
        <form onSubmit={handleSubmitRefinement} className="flex gap-2">
          <input
            type="text"
            value={refinementText}
            onChange={(e) => setRefinementText(e.target.value)}
            disabled={isRefining}
            placeholder="Type your adjustment (e.g. 'Tighten decor budget', 'Make it formal royal theme', 'Change to 80 guests')..."
            className="flex-1 bg-[#F8F5EE] border-2 border-black rounded-xl px-4 py-2.5 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-[#FFE600] disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isRefining || !refinementText.trim()}
            className="flex items-center gap-2 bg-[#FFE600] hover:bg-[#FACC15] disabled:bg-slate-200 text-black font-black px-5 py-2.5 rounded-xl text-xs border-2 border-black shadow-[2px_2px_0px_0px_#000] transition-all disabled:opacity-50 shrink-0"
          >
            {isRefining ? (
              <>
                <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                <span>Refining...</span>
              </>
            ) : (
              <>
                <Send className="w-3.5 h-3.5" />
                <span>Refine Plan</span>
              </>
            )}
          </button>
        </form>

        {refinementSuccessMsg && (
          <div className="text-xs font-black text-[#166534] bg-[#DCFCE7] p-2.5 rounded-xl border border-black flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-[#16a34a]" />
            <span>{refinementSuccessMsg}</span>
          </div>
        )}
      </div>

      {/* =========================================================================
          HUMAN APPROVAL COMMITMENT MODAL
      ========================================================================= */}
      {isApprovalModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white border-2 border-black rounded-3xl p-6 sm:p-7 max-w-xl w-full shadow-[8px_8px_0px_0px_#000] space-y-5 animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex items-start justify-between gap-4 border-b-2 border-black pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-2xl bg-[#FFE600] text-black border-2 border-black shadow-[2px_2px_0px_0px_#000] flex items-center justify-center shrink-0">
                  <Database className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-xl font-black text-black font-heading tracking-tight">
                    Commit Plan to Database
                  </h3>
                  <p className="text-xs font-bold text-slate-600">
                    Step 8D: Human Approval & Transactional Database Persistence
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => !isApproving && setIsApprovalModalOpen(false)}
                disabled={isApproving}
                className="p-1.5 rounded-xl border border-black hover:bg-slate-100 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Persistence Scope Summary */}
            <div className="space-y-3">
              <div className="text-xs font-bold text-slate-700">
                You are giving human approval to convert this draft event plan into real database entities. The following records will be created atomically:
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="bg-[#F8F5EE] border border-black rounded-xl p-3">
                  <span className="font-black text-black block mb-0.5">1. Event Record</span>
                  <span className="text-slate-700 block truncate font-medium">"{plan.brief.event_name}" ({plan.brief.event_type})</span>
                  <span className="text-slate-500 text-[11px] block">{plan.brief.expected_guest_count ? `${plan.brief.expected_guest_count} guests` : 'Headcount TBD'} • {plan.brief.location || 'Location TBD'}</span>
                </div>

                <div className="bg-[#F8F5EE] border border-black rounded-xl p-3">
                  <span className="font-black text-black block mb-0.5">2. Event Requirements</span>
                  <span className="text-slate-700 font-medium">{plan.vendor_checklist.length} Procurement Items</span>
                  <span className="text-slate-500 text-[11px] block">No fake quotes or fake businesses</span>
                </div>

                <div className="bg-[#F8F5EE] border border-black rounded-xl p-3">
                  <span className="font-black text-black block mb-0.5">3. Baseline Budget</span>
                  <span className="text-slate-700 font-medium">{plan.budget_proposal.allocations.length} Line Items</span>
                  <span className="text-slate-500 text-[11px] block">
                    {plan.budget_proposal.budget_provenance === 'unknown' || (!plan.budget_proposal.target_budget && plan.budget_proposal.total_allocated === 0)
                      ? 'No budget ceiling (Unconstrained baseline)'
                      : plan.budget_proposal.budget_provenance === 'ai_suggested' || plan.budget_proposal.budget_provenance === 'benchmark_estimate'
                      ? `Estimate: ~${formatInr(plan.budget_proposal.total_allocated)} (Approved by confirmation)`
                      : `Total: ${formatInr(plan.budget_proposal.total_allocated)} (${plan.brief.currency || 'INR'})`}
                  </span>
                </div>

                <div className="bg-[#F8F5EE] border border-black rounded-xl p-3">
                  <span className="font-black text-black block mb-0.5">4. Tasks & Audit Log</span>
                  <span className="text-slate-700 font-medium">{plan.timeline.length} Milestones</span>
                  <span className="text-slate-500 text-[11px] block">Predecessor dependencies linked</span>
                </div>
              </div>
            </div>

            {/* Error Message if any */}
            {approvalError && (
              <div className="bg-[#FEE2E2] border-2 border-black text-[#991B1B] p-3.5 rounded-2xl text-xs font-bold flex items-start gap-2 shadow-[2px_2px_0px_0px_#000]">
                <AlertTriangle className="w-4 h-4 text-[#DC2626] shrink-0 mt-0.5" />
                <div className="space-y-0.5">
                  <span className="font-black block">Approval Commitment Failed</span>
                  <p>{approvalError}</p>
                </div>
              </div>
            )}

            {/* Explicit Human Approval Checkbox */}
            <div className="bg-[#FEF08A]/60 border-2 border-black rounded-2xl p-4 shadow-[2px_2px_0px_0px_#000]">
              <label className="flex items-start gap-3 cursor-pointer select-none">
                <input
                  type="checkbox"
                  id="approval-confirmation-toggle"
                  checked={approvalConfirmed}
                  onChange={(e) => setApprovalConfirmed(e.target.checked)}
                  disabled={isApproving}
                  className="mt-1 w-4 h-4 accent-black rounded cursor-pointer shrink-0"
                />
                <div className="space-y-1">
                  <span className="text-xs font-black text-black block">
                    Explicit Human Approval Confirmation
                  </span>
                  <span className="text-[11px] font-bold text-slate-700 leading-snug block">
                    I confirm that I have reviewed the event brief, budget allocations, vendor checklist items, and timeline milestones. I authorize EventPrice Intelligence to commit these records to the database.
                  </span>
                </div>
              </label>
            </div>

            {/* Modal Actions */}
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setIsApprovalModalOpen(false)}
                disabled={isApproving}
                className="px-4 py-2.5 rounded-xl border-2 border-black text-xs font-black text-slate-700 hover:bg-slate-100 transition-colors"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleCommitApproval}
                disabled={!approvalConfirmed || isApproving}
                className="flex items-center gap-2 bg-[#22C55E] hover:bg-[#16A34A] disabled:bg-slate-300 text-white font-black px-5 py-2.5 rounded-xl text-xs border-2 border-black shadow-[3px_3px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isApproving ? (
                  <>
                    <RotateCcw className="w-4 h-4 animate-spin" />
                    <span>Committing Transaction...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Confirm & Commit to Database</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

