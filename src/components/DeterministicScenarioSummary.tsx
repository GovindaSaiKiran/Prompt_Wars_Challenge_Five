import React from 'react';
import { LedgerFinancialSummary, EventBrief, ServiceCategory } from '../types/intelligence';
import { formatInr, CATEGORY_LABELS } from '../utils/ledgerMath';
import { Users, TrendingUp, Receipt, Sparkles } from 'lucide-react';

interface DeterministicScenarioSummaryProps {
  summary: LedgerFinancialSummary;
  brief: EventBrief | null;
}

const CATEGORY_THEMES: Record<
  ServiceCategory,
  {
    bg: string;
    barColor: string;
    icon: string;
    accent: string;
  }
> = {
  venue: {
    bg: 'bg-[#F3E8FF]',
    barColor: 'bg-[#C084FC]',
    icon: '🏰',
    accent: 'text-purple-950',
  },
  catering: {
    bg: 'bg-[#FEF9C3]',
    barColor: 'bg-[#FACC15]',
    icon: '🍽️',
    accent: 'text-amber-950',
  },
  decor: {
    bg: 'bg-[#FCE7F3]',
    barColor: 'bg-[#F472B6]',
    icon: '🌸',
    accent: 'text-pink-950',
  },
  entertainment: {
    bg: 'bg-[#E0F2FE]',
    barColor: 'bg-[#38BDF8]',
    icon: '🔊',
    accent: 'text-sky-950',
  },
  photography: {
    bg: 'bg-[#FEF3C7]',
    barColor: 'bg-[#FB923C]',
    icon: '📸',
    accent: 'text-orange-950',
  },
  logistics: {
    bg: 'bg-[#DCFCE7]',
    barColor: 'bg-[#4ADE80]',
    icon: '🚐',
    accent: 'text-emerald-950',
  },
};

export const DeterministicScenarioSummary: React.FC<DeterministicScenarioSummaryProps> = ({
  summary,
  brief,
}) => {
  const categories = Object.keys(summary.categoryBreakdown) as ServiceCategory[];

  const costPerGuest =
    brief && brief.guestCount > 0
      ? Math.round(summary.committedTotal / brief.guestCount)
      : 0;

  // Find highest category
  let topCategory: { name: string; amount: number; pct: number } | null = null;
  categories.forEach((cat) => {
    const data = summary.categoryBreakdown[cat];
    if (!topCategory || data.total > topCategory.amount) {
      topCategory = {
        name: CATEGORY_LABELS[cat],
        amount: data.total,
        pct: summary.committedTotal > 0 ? Math.round((data.total / summary.committedTotal) * 100) : 0,
      };
    }
  });

  return (
    <div className="space-y-4">
      {/* Quick Event Unit Metrics in Neo-Brutalist Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {/* Card 1: Cost Per Guest (Sky Blue) */}
        <div className="bg-[#BAE6FD] text-black border-2 border-black p-4 rounded-xl shadow-[3px_3px_0px_0px_#000] hover:translate-x-[0.5px] hover:translate-y-[0.5px] transition-all">
          <div className="text-black text-xs font-black uppercase tracking-wider flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <span>👥</span>
              <span>Cost Per Guest</span>
            </span>
            <Users className="w-4 h-4 stroke-[2.5]" />
          </div>
          <div className="text-2xl font-black text-black font-heading mt-2">
            {formatInr(costPerGuest)}
          </div>
          <p className="text-[11px] font-bold text-slate-800 mt-0.5">
            Based on {brief?.guestCount || 0} attending guests
          </p>
        </div>

        {/* Card 2: Largest Area (Lilac Purple) */}
        <div className="bg-[#E9D5FF] text-black border-2 border-black p-4 rounded-xl shadow-[3px_3px_0px_0px_#000] hover:translate-x-[0.5px] hover:translate-y-[0.5px] transition-all">
          <div className="text-black text-xs font-black uppercase tracking-wider flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <span>👑</span>
              <span>Top Allocation</span>
            </span>
            <TrendingUp className="w-4 h-4 stroke-[2.5]" />
          </div>
          <div className="text-2xl font-black text-black font-heading mt-2 truncate">
            {topCategory && topCategory.amount > 0 ? topCategory.name : 'None yet'}
          </div>
          <p className="text-[11px] font-bold text-slate-800 mt-0.5 truncate">
            {topCategory && topCategory.amount > 0
              ? `${formatInr(topCategory.amount)} (${topCategory.pct}% of total)`
              : 'Add vendors to see distribution'}
          </p>
        </div>

        {/* Card 3: Estimated Taxes (Sunny Yellow) */}
        <div className="bg-[#FEF08A] text-black border-2 border-black p-4 rounded-xl shadow-[3px_3px_0px_0px_#000] hover:translate-x-[0.5px] hover:translate-y-[0.5px] transition-all">
          <div className="text-black text-xs font-black uppercase tracking-wider flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <span>📋</span>
              <span>Estimated GST (18%)</span>
            </span>
            <Receipt className="w-4 h-4 stroke-[2.5]" />
          </div>
          <div className="text-2xl font-black text-black font-heading mt-2">
            {formatInr(summary.committedGst)}
          </div>
          <p className="text-[11px] font-bold text-slate-800 mt-0.5">
            Transparently computed across quotes
          </p>
        </div>
      </div>

      {/* Category Breakdown Card with Distinctive Neo-Brutalism Styling */}
      <div className="bg-white border-2 border-black rounded-2xl p-5 space-y-4 shadow-[4px_4px_0px_0px_#000]">
        <div className="flex items-center justify-between border-b-2 border-black pb-3">
          <div>
            <h3 className="text-base font-black text-black tracking-tight font-heading flex items-center gap-2 uppercase">
              <span>🎪</span>
              <span>Event Spending by Category</span>
            </h3>
            <p className="text-xs font-bold text-slate-600 mt-0.5">
              Visual allocation across all vendor service categories.
            </p>
          </div>
          <span className="neo-stamp bg-[#FFE600] text-black hidden sm:inline-block">
            100% TRANSPARENT
          </span>
        </div>

        <div className="space-y-3 pt-1">
          {categories.map((cat) => {
            const data = summary.categoryBreakdown[cat];
            const theme = CATEGORY_THEMES[cat];
            const pctOfCommitted =
              summary.committedTotal > 0
                ? Math.round((data.total / summary.committedTotal) * 100)
                : 0;

            return (
              <div
                key={cat}
                className={`p-3.5 rounded-xl border-2 border-black ${theme.bg} shadow-[2.5px_2.5px_0px_0px_#000] hover:translate-x-[0.5px] hover:translate-y-[0.5px] transition-all`}
              >
                <div className="flex items-center justify-between text-xs mb-2 font-bold text-black">
                  <div className="flex items-center gap-2">
                    <span className="text-base">{theme.icon}</span>
                    <span className="font-black text-sm uppercase tracking-tight">
                      {CATEGORY_LABELS[cat]}
                    </span>
                    <span className="text-[11px] bg-white/80 px-2 py-0.5 rounded border border-black font-bold">
                      {data.count} vendor{data.count === 1 ? '' : 's'}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="font-black text-black text-sm font-heading">
                      {formatInr(data.total)}
                    </span>
                    <span className="px-2 py-0.5 rounded-md font-black text-xs bg-black text-white border border-black shadow-[1px_1px_0px_0px_#000]">
                      {pctOfCommitted}%
                    </span>
                  </div>
                </div>

                {/* Striped Neo-Brutalist Progress Bar */}
                <div className="w-full bg-white h-3 rounded-full overflow-hidden p-0.5 border-2 border-black">
                  <div
                    className={`h-full ${theme.barColor} border-r border-black rounded-full transition-all duration-500`}
                    style={{ width: `${pctOfCommitted}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
