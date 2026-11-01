import React from 'react';
import { LedgerFinancialSummary } from '../types/intelligence';
import { formatInr, formatCompactInr } from '../utils/ledgerMath';

interface GlobalMetricsBarProps {
  summary: LedgerFinancialSummary;
}

export const GlobalMetricsBar: React.FC<GlobalMetricsBarProps> = ({ summary }) => {
  const percentUsed =
    summary.targetBudget > 0
      ? Math.min(Math.round((summary.committedTotal / summary.targetBudget) * 100), 100)
      : 0;

  const actualPercent =
    summary.targetBudget > 0
      ? Math.round((summary.committedTotal / summary.targetBudget) * 100)
      : 0;

  return (
    <div className="bg-[#FFFDF9] border-b-2 border-black px-4 lg:px-8 py-3">
      <div className="max-w-7xl mx-auto w-full">
        <div className="bg-white border-2 border-black rounded-2xl p-3.5 sm:p-4 shadow-[3px_3px_0px_0px_#000] space-y-3">
          {/* 4 Clean Metric Columns */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 divide-y md:divide-y-0 md:divide-x-2 divide-black/10">
            {/* Metric 1: Target Budget */}
            <div className="pt-2 md:pt-0 md:px-3 first:pl-0">
              <div className="flex items-center justify-between text-[11px] font-black uppercase tracking-wider text-black/70 mb-1">
                <span className="flex items-center gap-1.5">
                  <span>🎟️</span>
                  <span>Target Budget</span>
                </span>
                <span className="text-[10px] bg-[#FFE600] text-black px-1.5 py-0.2 rounded border border-black font-black">
                  CAP
                </span>
              </div>
              <div className="text-xl sm:text-2xl font-black text-black font-heading tracking-tight">
                {formatInr(summary.targetBudget)}
              </div>
              <div className="text-[11px] font-bold text-black/60 mt-0.5">
                Calibrated spending limit
              </div>
            </div>

            {/* Metric 2: Committed Costs */}
            <div className="pt-2 md:pt-0 md:px-3">
              <div className="flex items-center justify-between text-[11px] font-black uppercase tracking-wider text-black/70 mb-1">
                <span className="flex items-center gap-1.5">
                  <span>🎪</span>
                  <span>Committed Costs</span>
                </span>
                <span className="text-[10px] bg-[#D8B4FE] text-black px-1.5 py-0.2 rounded border border-black font-black">
                  {summary.selectedVendorCount} LOCKED
                </span>
              </div>
              <div className="text-xl sm:text-2xl font-black text-black font-heading tracking-tight">
                {formatInr(summary.committedTotal)}
              </div>
              <div className="text-[11px] font-bold text-black/70 mt-0.5 flex items-center justify-between">
                <span>Base: {formatCompactInr(summary.committedSubtotal)}</span>
                <span className="text-black/50">•</span>
                <span>GST: {formatCompactInr(summary.committedGst)}</span>
              </div>
            </div>

            {/* Metric 3: Safe Celebration Buffer */}
            <div className="pt-2 md:pt-0 md:px-3">
              <div className="flex items-center justify-between text-[11px] font-black uppercase tracking-wider text-black/70 mb-1">
                <span className="flex items-center gap-1.5">
                  <span>{summary.isOverBudget ? '⚠️' : '🥂'}</span>
                  <span>{summary.isOverBudget ? 'Budget Overrun' : 'Safe Buffer'}</span>
                </span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded border border-black font-black ${
                    summary.isOverBudget ? 'bg-[#FDA4AF] text-black' : 'bg-[#86EFAC] text-black'
                  }`}
                >
                  {summary.isOverBudget ? 'DEFICIT' : 'BUFFER'}
                </span>
              </div>
              <div
                className={`text-xl sm:text-2xl font-black font-heading tracking-tight ${
                  summary.isOverBudget ? 'text-red-600' : 'text-emerald-700'
                }`}
              >
                {summary.varianceInr >= 0 ? '+' : ''}
                {formatInr(summary.varianceInr)}
              </div>
              <div className="text-[11px] font-bold text-black/60 mt-0.5">
                {summary.isOverBudget
                  ? 'Exceeds budget cap • Trim quotes'
                  : 'Safe surplus remaining'}
              </div>
            </div>

            {/* Metric 4: Safety Cushion */}
            <div className="pt-2 md:pt-0 md:px-3 last:pr-0">
              <div className="flex items-center justify-between text-[11px] font-black uppercase tracking-wider text-black/70 mb-1">
                <span className="flex items-center gap-1.5">
                  <span>🛡️</span>
                  <span>Contingency</span>
                </span>
                <span className="text-[10px] bg-[#FED7AA] text-black px-1.5 py-0.2 rounded border border-black font-black">
                  10% CUSHION
                </span>
              </div>
              <div className="text-xl sm:text-2xl font-black text-black font-heading tracking-tight">
                {formatInr(summary.contingencyAmount)}
              </div>
              <div className="text-[11px] font-bold text-black/60 mt-0.5">
                Reserved for last-minute needs
              </div>
            </div>
          </div>

          {/* Integrated Slim Progress Bar */}
          <div className="pt-2 border-t-2 border-black/10 flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-[11px] font-black text-black">
              <div className="flex items-center gap-2">
                <span>Budget Allocation:</span>
                <span className="font-extrabold text-black/70">
                  {actualPercent}% utilized of {formatCompactInr(summary.targetBudget)} cap
                </span>
              </div>

              <span
                className={`text-[10px] px-2 py-0.2 rounded font-black border border-black ${
                  summary.isOverBudget
                    ? 'bg-red-200 text-red-900'
                    : 'bg-[#86EFAC] text-black'
                }`}
              >
                {summary.isOverBudget ? '⚠️ TRIM REQUIRED' : '✓ IN BUDGET'}
              </span>
            </div>

            <div className="w-full h-2.5 bg-[#F8F5EE] border-2 border-black rounded-full overflow-hidden p-[1px]">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  summary.isOverBudget
                    ? 'bg-red-500'
                    : 'bg-[#4ADE80]'
                }`}
                style={{ width: `${percentUsed}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
