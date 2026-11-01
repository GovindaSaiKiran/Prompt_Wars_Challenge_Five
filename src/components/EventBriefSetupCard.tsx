import React, { useState, useEffect } from 'react';
import { EventBrief } from '../types/intelligence';
import { SAMPLE_BRIEFS } from '../utils/samplePayloads';
import { formatInr } from '../utils/ledgerMath';
import { Calendar, MapPin, Users, DollarSign, X, Sparkles, Check } from 'lucide-react';

interface EventBriefSetupCardProps {
  initialBrief: EventBrief | null;
  onSaveBrief: (brief: EventBrief) => void;
  onClose?: () => void;
  isModal?: boolean;
}

export const EventBriefSetupCard: React.FC<EventBriefSetupCardProps> = ({
  initialBrief,
  onSaveBrief,
  onClose,
  isModal = false,
}) => {
  const [formData, setFormData] = useState<EventBrief>({
    eventName: initialBrief?.eventName || '',
    location: initialBrief?.location || '',
    eventDate: initialBrief?.eventDate || '2026-11-15',
    guestCount: initialBrief?.guestCount || 400,
    durationDays: initialBrief?.durationDays || 2,
    durationHours: initialBrief?.durationHours || 16,
    targetBudgetInr: initialBrief?.targetBudgetInr || 3500000,
    contingencyPct: initialBrief?.contingencyPct || 10,
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (initialBrief) {
      setFormData(initialBrief);
    }
  }, [initialBrief]);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!formData.eventName.trim()) errs.eventName = 'Please enter an event name';
    if (!formData.location.trim()) errs.location = 'Please enter a location';
    if (!formData.eventDate) errs.eventDate = 'Please select a date';
    if (!formData.guestCount || formData.guestCount <= 0)
      errs.guestCount = 'Guest count must be at least 1';
    if (!formData.targetBudgetInr || formData.targetBudgetInr <= 0)
      errs.targetBudgetInr = 'Target budget must be greater than 0';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    onSaveBrief(formData);
    if (onClose) onClose();
  };

  const handleApplyPreset = (preset: EventBrief) => {
    setFormData(preset);
    setErrors({});
  };

  const perGuestTarget =
    formData.guestCount > 0
      ? Math.round(formData.targetBudgetInr / formData.guestCount)
      : 0;

  const contingencyAmount = Math.round(
    formData.targetBudgetInr * (formData.contingencyPct / 100)
  );

  return (
    <div
      className={`bg-[#141517] border border-white/[0.08] rounded-2xl overflow-hidden shadow-2xl ${
        isModal ? 'max-w-xl w-full p-6' : 'p-6 max-w-2xl mx-auto my-6'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/[0.08]">
        <div>
          <h2 className="text-base font-semibold text-white tracking-tight">
            {initialBrief ? 'Edit Event Details' : 'Set Up Your Event'}
          </h2>
          <p className="text-xs text-zinc-400 mt-1">
            Enter your event basics so vendor quotes are calculated accurately.
          </p>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="text-zinc-500 hover:text-white p-1 rounded-lg transition-colors"
            title="Close"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Quick Templates */}
      <div className="mt-4">
        <label className="text-xs font-medium text-zinc-400 mb-2 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
          <span>Or pick a ready-made template:</span>
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {SAMPLE_BRIEFS.map((s, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleApplyPreset(s.brief)}
              className="bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 hover:border-zinc-700 text-left p-2.5 rounded-xl text-xs transition-colors group"
            >
              <div className="font-medium text-zinc-200 group-hover:text-white truncate">
                {s.brief.eventName}
              </div>
              <div className="text-[11px] text-zinc-500 mt-0.5">
                {s.brief.guestCount} Guests • {formatInr(s.brief.targetBudgetInr)}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="mt-5 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Event Name */}
          <div className="sm:col-span-2">
            <label className="block text-xs font-medium text-zinc-300 mb-1">
              Event Name
            </label>
            <input
              type="text"
              value={formData.eventName}
              onChange={(e) =>
                setFormData({ ...formData, eventName: e.target.value })
              }
              placeholder="e.g. Annual Tech Conference 2026"
              className={`w-full bg-zinc-900 border rounded-lg px-3 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-colors ${
                errors.eventName ? 'border-rose-500' : 'border-zinc-800'
              }`}
            />
            {errors.eventName && (
              <p className="text-[11px] text-rose-400 mt-1">{errors.eventName}</p>
            )}
          </div>

          {/* Location */}
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1">
              City / Venue Location
            </label>
            <input
              type="text"
              value={formData.location}
              onChange={(e) =>
                setFormData({ ...formData, location: e.target.value })
              }
              placeholder="e.g. Bengaluru, Karnataka"
              className={`w-full bg-zinc-900 border rounded-lg px-3 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-colors ${
                errors.location ? 'border-rose-500' : 'border-zinc-800'
              }`}
            />
            {errors.location && (
              <p className="text-[11px] text-rose-400 mt-1">{errors.location}</p>
            )}
          </div>

          {/* Date */}
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1">
              Event Date
            </label>
            <input
              type="date"
              value={formData.eventDate}
              onChange={(e) =>
                setFormData({ ...formData, eventDate: e.target.value })
              }
              className={`w-full bg-zinc-900 border rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500 transition-colors ${
                errors.eventDate ? 'border-rose-500' : 'border-zinc-800'
              }`}
            />
            {errors.eventDate && (
              <p className="text-[11px] text-rose-400 mt-1">{errors.eventDate}</p>
            )}
          </div>

          {/* Guest Count */}
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1">
              Expected Guests (Pax)
            </label>
            <input
              type="number"
              min="1"
              value={formData.guestCount || ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  guestCount: parseInt(e.target.value, 10) || 0,
                })
              }
              placeholder="e.g. 400"
              className={`w-full bg-zinc-900 border rounded-lg px-3 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-colors ${
                errors.guestCount ? 'border-rose-500' : 'border-zinc-800'
              }`}
            />
            {errors.guestCount && (
              <p className="text-[11px] text-rose-400 mt-1">{errors.guestCount}</p>
            )}
          </div>

          {/* Total Budget */}
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1">
              Total Budget (₹ INR)
            </label>
            <input
              type="number"
              min="1000"
              step="10000"
              value={formData.targetBudgetInr || ''}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  targetBudgetInr: parseInt(e.target.value, 10) || 0,
                })
              }
              placeholder="e.g. 3500000"
              className={`w-full bg-zinc-900 border rounded-lg px-3 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-emerald-500 transition-colors ${
                errors.targetBudgetInr ? 'border-rose-500' : 'border-zinc-800'
              }`}
            />
            {errors.targetBudgetInr && (
              <p className="text-[11px] text-rose-400 mt-1">
                {errors.targetBudgetInr}
              </p>
            )}
          </div>

          {/* Duration Days */}
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1">
              Duration (Days)
            </label>
            <input
              type="number"
              min="1"
              max="30"
              value={formData.durationDays}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  durationDays: parseInt(e.target.value, 10) || 1,
                })
              }
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500"
            />
          </div>

          {/* Contingency Buffer % */}
          <div>
            <label className="block text-xs font-medium text-zinc-300 mb-1">
              Emergency Reserve Buffer (%)
            </label>
            <input
              type="number"
              min="0"
              max="40"
              value={formData.contingencyPct}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  contingencyPct: parseInt(e.target.value, 10) || 0,
                })
              }
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>

        {/* Live Calculation Summary */}
        <div className="bg-zinc-900/60 border border-zinc-800/80 p-3 rounded-xl flex items-center justify-between text-xs text-zinc-400">
          <div>
            <span className="text-zinc-500">Per Guest Target: </span>
            <span className="font-semibold text-zinc-200">
              {formatInr(perGuestTarget)}
            </span>
          </div>
          <div>
            <span className="text-zinc-500">Safety Reserve: </span>
            <span className="font-semibold text-zinc-200">
              {formatInr(contingencyAmount)} ({formData.contingencyPct}%)
            </span>
          </div>
        </div>

        {/* Buttons */}
        <div className="pt-2 flex items-center justify-end gap-2">
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-xs font-medium text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors"
            >
              Cancel
            </button>
          )}

          <button
            type="submit"
            className="bg-white hover:bg-zinc-100 text-zinc-950 font-semibold px-5 py-2 rounded-lg text-xs transition-colors shadow-sm"
          >
            Save Event Details
          </button>
        </div>
      </form>
    </div>
  );
};
