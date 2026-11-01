import React, { useState } from 'react';
import {
  Calendar,
  MapPin,
  Users,
  DollarSign,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  RotateCcw,
  Layers,
  Heart,
  Cake,
  Building2,
  PartyPopper,
  Music,
  Utensils,
  Lightbulb,
  ShieldCheck,
  Check,
} from 'lucide-react';
import { GeneratedEventPlan, PlanGenerationRequest } from '../types/planning';
import { generateEventPlanApi } from '../services/assistantApi';
import { formatInr } from '../utils/ledgerMath';

interface GuidedPlanningWizardProps {
  onPlanGenerated: (plan: GeneratedEventPlan) => void;
  onCancel?: () => void;
}

const EVENT_TYPES = [
  { id: 'wedding', label: 'Wedding', icon: '💍', desc: 'Sangeet, Reception, Mehendi, Beach or Royal Wedding' },
  { id: 'birthday', label: 'Birthday', icon: '🎂', desc: 'Kids, Milestone 30th/50th, Theme parties' },
  { id: 'community', label: 'Community', icon: '🎪', desc: 'Festival, Cleanliness drive, Carnival, Fundraiser' },
  { id: 'corporate', label: 'Corporate', icon: '🏢', desc: 'Offsite, Team dinner, Awards banquet, Annual party' },
  { id: 'conference', label: 'Conference', icon: '🎤', desc: 'Summit, Tech expo, Hackathon, Symposium' },
  { id: 'anniversary', label: 'Anniversary', icon: '🥂', desc: 'Silver/Golden jubilee, Family celebration' },
  { id: 'other', label: 'Other Celebration', icon: '🎉', desc: 'Housewarming, Baby shower, Get-together' },
];

const BUDGET_PRESETS = [
  { label: '₹75,000', value: 75000, desc: 'Intimate / Home' },
  { label: '₹1.5 Lakhs', value: 150000, desc: 'Party Hall' },
  { label: '₹5 Lakhs', value: 500000, desc: 'Medium Scale' },
  { label: '₹12 Lakhs', value: 1200000, desc: 'Large Event' },
  { label: '₹25 Lakhs', value: 2500000, desc: 'Grand Celebration' },
  { label: '₹50 Lakhs+', value: 5000000, desc: 'Luxury / Multi-day' },
];

export const GuidedPlanningWizard: React.FC<GuidedPlanningWizardProps> = ({
  onPlanGenerated,
  onCancel,
}) => {
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3 | 4>(1);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Form State
  // Step 1: Basics
  const [eventType, setEventType] = useState('wedding');
  const [eventName, setEventName] = useState('');
  const [location, setLocation] = useState('Bengaluru');
  const [guestCount, setGuestCount] = useState<number>(150);
  const [eventDate, setEventDate] = useState('');

  // Step 2: Budget
  const [targetBudget, setTargetBudget] = useState<number>(1000000);
  const [currency, setCurrency] = useState('INR');
  const [budgetFlexibility, setBudgetFlexibility] = useState<'strict' | 'moderate' | 'estimate'>('moderate');

  // Step 3: Preferences
  const [themePreference, setThemePreference] = useState('');
  const [cateringPreference, setCateringPreference] = useState('Regional buffet with live counters');
  const [entertainmentPreference, setEntertainmentPreference] = useState('Live DJ and acoustic band');
  const [specialRequirements, setSpecialRequirements] = useState('');

  // Step Validation
  const validateStep1 = () => {
    if (!eventName.trim()) {
      setEventName(`${location} ${eventType.charAt(0).toUpperCase() + eventType.slice(1)}`);
    }
    return true;
  };

  const handleNext = () => {
    setErrorMessage(null);
    if (currentStep === 1) {
      validateStep1();
      setCurrentStep(2);
    } else if (currentStep === 2) {
      setCurrentStep(3);
    } else if (currentStep === 3) {
      setCurrentStep(4);
    }
  };

  const handleBack = () => {
    setErrorMessage(null);
    if (currentStep > 1) {
      setCurrentStep((prev) => (prev - 1) as any);
    }
  };

  // Compile prompt for the backend planning engine
  const constructPrompt = (): string => {
    const parts = [
      `Plan a ${eventType} named "${eventName || `${location} ${eventType}`}" in ${location} for ${guestCount} attendees.`,
    ];

    if (targetBudget && budgetFlexibility !== 'estimate') {
      parts.push(`Budget ceiling is ₹${targetBudget.toLocaleString('en-IN')}${budgetFlexibility === 'strict' ? ' (strict limit)' : ' (moderate flexibility)'}.`);
    } else {
      parts.push('Target budget is flexible; please provide market estimate allocations based on headcount.');
    }

    if (eventDate) {
      parts.push(`Scheduled calendar date is ${eventDate}.`);
    } else {
      parts.push('Dates are not finalized yet; use staged planning timelines.');
    }

    if (themePreference.trim()) {
      parts.push(`Theme preference: ${themePreference.trim()}.`);
    }

    if (cateringPreference.trim()) {
      parts.push(`Catering style: ${cateringPreference.trim()}.`);
    }

    if (entertainmentPreference.trim()) {
      parts.push(`Entertainment preference: ${entertainmentPreference.trim()}.`);
    }

    if (specialRequirements.trim()) {
      parts.push(`Special requirements & notes: ${specialRequirements.trim()}.`);
    }

    return parts.join(' ');
  };

  const handleGeneratePlan = async () => {
    setIsLoading(true);
    setErrorMessage(null);

    const compiledPrompt = constructPrompt();

    const requestPayload: PlanGenerationRequest = {
      user_prompt: compiledPrompt,
      event_type: eventType,
      event_name: eventName || `${location} ${eventType.charAt(0).toUpperCase() + eventType.slice(1)}`,
      location: location || 'Bengaluru',
      guest_count: guestCount > 0 ? guestCount : 100,
      target_budget: budgetFlexibility !== 'estimate' && targetBudget > 0 ? targetBudget : undefined,
      currency: currency || 'INR',
      event_date: eventDate || undefined,
    };

    try {
      const generated = await generateEventPlanApi(requestPayload);
      onPlanGenerated(generated);
    } catch (err: any) {
      console.error('Wizard generation error:', err);
      setErrorMessage(
        err.userMessage ||
          err.message ||
          'Failed to generate plan. Please verify backend service connectivity and retry.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-white border-2 border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] max-w-4xl mx-auto space-y-6">
      {/* Wizard Header & Progress Bar */}
      <div className="space-y-4 border-b-2 border-black pb-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-8 h-8 rounded-xl bg-[#FFE600] border-2 border-black flex items-center justify-center font-black text-black text-sm shadow-[1.5px_1.5px_0px_0px_#000]">
                🧙‍♂️
              </span>
              <h2 className="text-xl sm:text-2xl font-black text-black font-heading uppercase tracking-tight">
                Guided Event Planning Wizard
              </h2>
            </div>
            <p className="text-xs text-slate-600 font-bold mt-1">
              Follow 4 structured steps to calibrate your event parameters before generating an AI plan.
            </p>
          </div>

          {onCancel && (
            <button
              onClick={onCancel}
              className="self-start sm:self-auto text-xs font-black text-slate-600 hover:text-black border-2 border-black px-3 py-1.5 rounded-xl hover:bg-slate-100 transition-colors"
            >
              Exit Wizard
            </button>
          )}
        </div>

        {/* 4 Steps Indicator Bar */}
        <div className="grid grid-cols-4 gap-2 pt-2">
          {[
            { step: 1, label: '1. Basics', color: 'bg-[#FFE600]' },
            { step: 2, label: '2. Budget', color: 'bg-[#BAE6FD]' },
            { step: 3, label: '3. Preferences', color: 'bg-[#D8B4FE]' },
            { step: 4, label: '4. Generate', color: 'bg-[#DCFCE7]' },
          ].map((s) => (
            <button
              key={s.step}
              type="button"
              onClick={() => {
                if (s.step < currentStep) setCurrentStep(s.step as any);
              }}
              className={`p-2.5 rounded-xl border-2 border-black text-left transition-all ${
                currentStep === s.step
                  ? `${s.color} text-black font-black shadow-[2px_2px_0px_0px_#000]`
                  : currentStep > s.step
                  ? 'bg-white text-black font-bold shadow-[1px_1px_0px_0px_#000]'
                  : 'bg-[#F8F5EE] text-slate-400 font-bold opacity-60'
              }`}
            >
              <div className="text-[10px] font-black uppercase flex items-center justify-between">
                <span>{s.label}</span>
                {currentStep > s.step && <Check className="w-3 h-3 text-[#16a34a] stroke-[3]" />}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Error Alert if any */}
      {errorMessage && (
        <div className="bg-[#FEE2E2] border-2 border-black rounded-2xl p-4 text-xs font-black text-[#991B1B] shadow-[3px_3px_0px_0px_#000] flex items-center gap-2">
          <span>⚠️ {errorMessage}</span>
        </div>
      )}

      {/* =========================================================================
          STEP 1: EVENT BASICS
      ========================================================================= */}
      {currentStep === 1 && (
        <div className="space-y-6">
          {/* Event Type Grid */}
          <div className="space-y-2">
            <label className="block text-xs font-black text-black uppercase tracking-wider">
              Select Event Type
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {EVENT_TYPES.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setEventType(t.id)}
                  className={`p-3 rounded-2xl border-2 border-black text-left transition-all ${
                    eventType === t.id
                      ? 'bg-[#FFE600] text-black font-black shadow-[3px_3px_0px_0px_#000] translate-x-[-1px] translate-y-[-1px]'
                      : 'bg-[#F8F5EE] hover:bg-white text-slate-700 font-bold shadow-[1.5px_1.5px_0px_0px_#000]'
                  }`}
                >
                  <div className="text-2xl mb-1">{t.icon}</div>
                  <div className="text-xs font-black capitalize text-black">{t.label}</div>
                  <div className="text-[10px] text-slate-600 line-clamp-1 mt-0.5">{t.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Form Fields: Name, Location, Guests, Date */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-black text-black uppercase mb-1">
                Event Title / Working Name
              </label>
              <input
                type="text"
                value={eventName}
                onChange={(e) => setEventName(e.target.value)}
                placeholder={`e.g. Royal ${eventType} Gala`}
                className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-4 py-2.5 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
              />
            </div>

            <div>
              <label className="block text-xs font-black text-black uppercase mb-1">
                Destination / City
              </label>
              <input
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Bengaluru, Mumbai, Goa, Jaipur"
                className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-4 py-2.5 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
              />
            </div>

            <div>
              <label className="block text-xs font-black text-black uppercase mb-1">
                Expected Guest Count (Pax)
              </label>
              <input
                type="number"
                min="5"
                max="50000"
                value={guestCount}
                onChange={(e) => setGuestCount(Math.max(1, Number(e.target.value)))}
                className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-4 py-2.5 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
              />
            </div>

            <div>
              <label className="block text-xs font-black text-black uppercase mb-1">
                Event Calendar Date (Optional)
              </label>
              <input
                type="date"
                value={eventDate}
                onChange={(e) => setEventDate(e.target.value)}
                className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-4 py-2.5 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
              />
              <span className="text-[10px] text-slate-500 font-bold mt-1 block">
                Leave blank if dates are tentative — staged relative timelines will be used.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          STEP 2: BUDGET & CURRENCY
      ========================================================================= */}
      {currentStep === 2 && (
        <div className="space-y-6">
          <div>
            <label className="block text-xs font-black text-black uppercase mb-2">
              Select or Enter Target Budget
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {BUDGET_PRESETS.map((preset) => (
                <button
                  key={preset.value}
                  type="button"
                  onClick={() => setTargetBudget(preset.value)}
                  className={`p-3 rounded-2xl border-2 border-black text-left transition-all ${
                    targetBudget === preset.value
                      ? 'bg-[#BAE6FD] text-black font-black shadow-[3px_3px_0px_0px_#000]'
                      : 'bg-[#F8F5EE] hover:bg-white text-slate-700 font-bold shadow-[1.5px_1.5px_0px_0px_#000]'
                  }`}
                >
                  <div className="text-base font-black text-black">{preset.label}</div>
                  <div className="text-[10px] text-slate-600">{preset.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-black text-black uppercase mb-1">
                Custom Budget Amount (₹)
              </label>
              <input
                type="number"
                min="0"
                step="1000"
                value={targetBudget}
                onChange={(e) => setTargetBudget(Number(e.target.value))}
                className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-4 py-2.5 text-sm font-black text-black focus:outline-none focus:ring-2 focus:ring-[#BAE6FD]"
              />
              <span className="text-[11px] font-black text-[#0369a1] mt-1 block">
                Formatted: {formatInr(targetBudget)}
              </span>
            </div>

            <div>
              <label className="block text-xs font-black text-black uppercase mb-1">
                Currency
              </label>
              <select
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-4 py-2.5 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-[#BAE6FD]"
              >
                <option value="INR">INR — Indian Rupee (₹)</option>
                <option value="USD">USD — US Dollar ($)</option>
                <option value="EUR">EUR — Euro (€)</option>
                <option value="GBP">GBP — British Pound (£)</option>
              </select>
            </div>
          </div>

          {/* Budget Flexibility Option */}
          <div className="space-y-2">
            <label className="block text-xs font-black text-black uppercase">
              Budget Flexibility Policy
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[
                { id: 'strict', label: 'Strict Ceiling', desc: 'Category allocations must not exceed limit' },
                { id: 'moderate', label: 'Moderate Flexibility', desc: 'Standard 10-15% buffer allowed for quality' },
                { id: 'estimate', label: 'Explore Benchmarks', desc: 'Calculate standard market per-guest estimates' },
              ].map((policy) => (
                <button
                  key={policy.id}
                  type="button"
                  onClick={() => setBudgetFlexibility(policy.id as any)}
                  className={`p-3 rounded-2xl border-2 border-black text-left transition-all ${
                    budgetFlexibility === policy.id
                      ? 'bg-[#FFE600] text-black font-black shadow-[2px_2px_0px_0px_#000]'
                      : 'bg-[#F8F5EE] hover:bg-white text-slate-700 font-bold border-black/40'
                  }`}
                >
                  <div className="text-xs font-black text-black">{policy.label}</div>
                  <div className="text-[10px] text-slate-600 mt-0.5">{policy.desc}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          STEP 3: PREFERENCES & STYLING
      ========================================================================= */}
      {currentStep === 3 && (
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-black text-black uppercase mb-1">
              Theme, Aesthetic & Atmosphere Preferences
            </label>
            <input
              type="text"
              value={themePreference}
              onChange={(e) => setThemePreference(e.target.value)}
              placeholder="e.g. Royal Marigold & Brass, Minimalist Bohemian, Neon Retro Arcade..."
              className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-4 py-2.5 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-[#D8B4FE]"
            />
          </div>

          <div>
            <label className="block text-xs font-black text-black uppercase mb-1">
              Catering & Dining Style
            </label>
            <input
              type="text"
              value={cateringPreference}
              onChange={(e) => setCateringPreference(e.target.value)}
              placeholder="e.g. Traditional banana-leaf lunch + evening Chaat counter, multi-cuisine buffet..."
              className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-4 py-2.5 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-[#D8B4FE]"
            />
          </div>

          <div>
            <label className="block text-xs font-black text-black uppercase mb-1">
              Entertainment & Performance
            </label>
            <input
              type="text"
              value={entertainmentPreference}
              onChange={(e) => setEntertainmentPreference(e.target.value)}
              placeholder="e.g. Acoustic fusion band, Live DJ with percussion, Magic show, Standup comedy..."
              className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-4 py-2.5 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-[#D8B4FE]"
            />
          </div>

          <div>
            <label className="block text-xs font-black text-black uppercase mb-1">
              Special Requirements or Logistical Considerations
            </label>
            <textarea
              rows={3}
              value={specialRequirements}
              onChange={(e) => setSpecialRequirements(e.target.value)}
              placeholder="e.g. Require wheelchair accessible venue, sound curfew after 10 PM, ample parking for 80 cars..."
              className="w-full bg-[#F8F5EE] border-2 border-black rounded-xl px-4 py-2.5 text-xs font-bold text-black focus:outline-none focus:ring-2 focus:ring-[#D8B4FE]"
            />
          </div>
        </div>
      )}

      {/* =========================================================================
          STEP 4: REVIEW & GENERATE
      ========================================================================= */}
      {currentStep === 4 && (
        <div className="space-y-5">
          <div className="bg-[#F8F5EE] border-2 border-black rounded-2xl p-5 shadow-[3px_3px_0px_0px_#000] space-y-3">
            <div className="flex items-center justify-between border-b-2 border-black pb-2">
              <span className="text-xs font-black text-black uppercase tracking-wider">
                Compiled Plan Parameters
              </span>
              <span className="text-xs font-black px-2 py-0.5 rounded bg-[#DCFCE7] text-[#166534] border border-black">
                Ready to Synthesize
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <span className="text-slate-500 font-bold block text-[10px] uppercase">Format</span>
                <span className="font-black text-black capitalize">{eventType}</span>
              </div>
              <div>
                <span className="text-slate-500 font-bold block text-[10px] uppercase">Destination</span>
                <span className="font-black text-black">{location}</span>
              </div>
              <div>
                <span className="text-slate-500 font-bold block text-[10px] uppercase">Guest Count</span>
                <span className="font-black text-black">{guestCount} attendees</span>
              </div>
              <div>
                <span className="text-slate-500 font-bold block text-[10px] uppercase">Ceiling Budget</span>
                <span className="font-black text-black">{formatInr(targetBudget)}</span>
              </div>
            </div>

            <div className="pt-2 border-t border-black/10">
              <span className="text-slate-500 font-bold block text-[10px] uppercase">Compiled Planning Prompt:</span>
              <p className="text-xs font-bold text-slate-800 italic mt-0.5 bg-white p-3 rounded-xl border border-black/20">
                "{constructPrompt()}"
              </p>
            </div>
          </div>

          <div className="bg-[#FEF08A] border-2 border-black rounded-2xl p-4 text-xs font-bold text-black space-y-1">
            <span className="font-black uppercase tracking-wider block">⚡ Shared Planning Engine Guarantee:</span>
            <p className="leading-snug">
              This request calls the exact same FastAPI planning endpoint (`/api/v1/assistant/plan/generate`) used by the chat interface. All budget calculations and contingency buffers are calculated deterministically via Python Decimal logic.
            </p>
          </div>
        </div>
      )}

      {/* Navigation Buttons: Back / Next / Generate */}
      <div className="flex items-center justify-between pt-4 border-t-2 border-black">
        {currentStep > 1 ? (
          <button
            type="button"
            onClick={handleBack}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl border-2 border-black text-xs font-black text-black bg-[#F8F5EE] hover:bg-slate-100 shadow-[2px_2px_0px_0px_#000] disabled:opacity-50 transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back</span>
          </button>
        ) : (
          <div />
        )}

        {currentStep < 4 ? (
          <button
            type="button"
            onClick={handleNext}
            className="flex items-center gap-1.5 px-6 py-2.5 rounded-xl border-2 border-black text-xs font-black text-black bg-[#FFE600] hover:bg-[#FACC15] shadow-[2.5px_2.5px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] transition-all"
          >
            <span>Next Step</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleGeneratePlan}
            disabled={isLoading}
            className="flex items-center gap-2 px-7 py-3 rounded-2xl border-2 border-black text-xs font-black text-black bg-[#DCFCE7] hover:bg-[#BBF7D0] shadow-[3px_3px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] disabled:opacity-50 transition-all"
          >
            {isLoading ? (
              <>
                <RotateCcw className="w-4 h-4 animate-spin" />
                <span>Synthesizing Structured Plan...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-[#16a34a]" />
                <span>Generate Structured Event Plan</span>
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
};

