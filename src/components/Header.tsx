import React, { useState, useEffect } from 'react';
import {
  Plus,
  RotateCcw,
  Sparkles,
  Search,
  Users,
  Edit3,
  Bot,
  Layers,
  Printer,
  Columns,
  Wand2,
  Building2,
  Compass,
} from 'lucide-react';
import { EventBrief } from '../types/intelligence';
import {
  BackendHealthInfo,
  checkBackendHealth,
} from '../services/assistantApi';

interface HeaderProps {
  brief: EventBrief | null;
  activeViewMode: 'split' | 'chat' | 'wizard' | 'plan' | 'vendors' | 'external';
  onChangeViewMode: (mode: 'split' | 'chat' | 'wizard' | 'plan' | 'vendors' | 'external') => void;
  onOpenInjector: () => void;
  onOpenBriefConfig: () => void;
  onExport: () => void;
  onReset: () => void;
  onOpenCommandPalette: () => void;
  onLoadSampleBatch: () => void;
  totalRecordsCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  brief,
  activeViewMode,
  onChangeViewMode,
  onOpenInjector,
  onOpenBriefConfig,
  onExport,
  onReset,
  onOpenCommandPalette,
  onLoadSampleBatch,
  totalRecordsCount,
}) => {
  const [healthInfo, setHealthInfo] = useState<BackendHealthInfo>({ state: 'connecting' });

  useEffect(() => {
    let isMounted = true;

    const probeBackend = async () => {
      const info = await checkBackendHealth();
      if (isMounted) {
        setHealthInfo(info);
      }
    };

    probeBackend();
    // Poll every 15s to keep status accurate
    const intervalId = setInterval(probeBackend, 15000);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, []);

  return (
    <header className="sticky top-0 z-40 bg-[#FFFDF9] border-b-2 border-black px-4 lg:px-8 py-2.5 shadow-[0px_3px_0px_0px_#000000]">
      <div className="flex items-center justify-between gap-3 max-w-7xl mx-auto w-full">
        {/* Brand & Active Event Meta */}
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="w-9 h-9 rounded-xl bg-[#FFE600] border-2 border-black shadow-[2px_2px_0px_0px_#000] flex items-center justify-center font-black text-black text-lg select-none">
              🎟️
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-black text-base tracking-tight text-black font-heading uppercase leading-none">
                  EventBudget
                </span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#FF6B8B] text-black font-black uppercase tracking-wider border border-black shadow-[1px_1px_0px_0px_#000]">
                  INTELLIGENCE
                </span>
              </div>
            </div>
          </div>

          {/* Active Event Badge */}
          {brief && (
            <button
              onClick={onOpenBriefConfig}
              className="hidden lg:flex items-center gap-1.5 bg-[#F8F5EE] hover:bg-[#FFE600]/40 border-2 border-black px-2.5 py-1 rounded-xl text-xs font-bold transition-all shadow-[1.5px_1.5px_0px_0px_#000] truncate max-w-[220px]"
              title="Click to edit event details & budget limit"
            >
              <span className="text-xs">🎪</span>
              <span className="font-black text-black truncate">{brief.eventName}</span>
              <span className="text-black/40 font-bold">•</span>
              <span className="text-black/70 flex items-center gap-1 font-extrabold shrink-0">
                <Users className="w-3 h-3 stroke-[2.5]" />
                {brief.guestCount}
              </span>
              <Edit3 className="w-2.5 h-2.5 text-black/60 shrink-0" />
            </button>
          )}

          {/* Real Backend Connection & AI Status Indicator */}
          {/* Real Backend Connection Indicator */}
          {healthInfo.state === 'connected' ? (
            <div
              className={`hidden xl:flex items-center gap-1.5 ${
                healthInfo.serviceStatus === 'ready_live'
                  ? 'bg-[#DCFCE7] text-[#166534]'
                  : 'bg-[#FEF08A] text-[#854D0E]'
              } border-2 border-black px-2.5 py-1 rounded-xl text-[11px] font-black shadow-[1.5px_1.5px_0px_0px_#000] whitespace-nowrap shrink-0`}
              title={
                healthInfo.serviceStatus === 'ready_live'
                  ? `FastAPI Backend Connected • Live Gemini (${healthInfo.configuredModel})`
                  : 'FastAPI Backend Connected • Deterministic Engine Active'
              }
            >
              <span
                className={`w-2 h-2 rounded-full border border-black ${
                  healthInfo.serviceStatus === 'ready_live'
                    ? 'bg-[#16a34a] animate-pulse'
                    : 'bg-[#EAB308]'
                } shrink-0`}
              />
              <span>Connected</span>
            </div>
          ) : healthInfo.state === 'connecting' ? (
            <div
              className="hidden xl:flex items-center gap-1.5 bg-[#FEF08A] text-slate-800 border-2 border-black px-2.5 py-1 rounded-xl text-[11px] font-black shadow-[1.5px_1.5px_0px_0px_#000] whitespace-nowrap shrink-0"
              title="Testing connection to FastAPI backend..."
            >
              <span className="w-2 h-2 rounded-full bg-[#EAB308] border border-black animate-pulse shrink-0" />
              <span>Connecting...</span>
            </div>
          ) : (
            <div
              className="hidden xl:flex items-center gap-1.5 bg-[#FEE2E2] text-[#991B1B] border-2 border-black px-2.5 py-1 rounded-xl text-[11px] font-black shadow-[1.5px_1.5px_0px_0px_#000] whitespace-nowrap shrink-0"
              title="Backend Server Unavailable. Ensure FastAPI is running on http://127.0.0.1:8000."
            >
              <span className="w-2 h-2 rounded-full bg-[#DC2626] border border-black shrink-0" />
              <span>Backend Unavailable</span>
            </div>
          )}
        </div>

        {/* Center: System Segmented View Mode Switcher (Split, Chat, Wizard, Plan) */}
        <div className="flex items-center bg-[#F8F5EE] border-2 border-black p-1 rounded-xl shadow-[2px_2px_0px_0px_#000] text-xs">
          <button
            onClick={() => onChangeViewMode('split')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg font-black transition-all ${
              activeViewMode === 'split'
                ? 'bg-[#FFE600] text-black border-2 border-black shadow-[1.5px_1.5px_0px_0px_#000]'
                : 'text-black/70 hover:text-black border-2 border-transparent'
            }`}
            title="Split View: AI Chat + Live Plan"
          >
            <Columns className="w-3.5 h-3.5 stroke-[2.5]" />
            <span className="hidden sm:inline">Split</span>
          </button>

          <button
            onClick={() => onChangeViewMode('chat')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg font-black transition-all ${
              activeViewMode === 'chat'
                ? 'bg-[#FFE600] text-black border-2 border-black shadow-[1.5px_1.5px_0px_0px_#000]'
                : 'text-black/70 hover:text-black border-2 border-transparent'
            }`}
            title="AI Chat Concierge"
          >
            <Bot className="w-3.5 h-3.5 stroke-[2.5]" />
            <span className="hidden sm:inline">AI Chat</span>
          </button>

          <button
            onClick={() => onChangeViewMode('wizard')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg font-black transition-all ${
              activeViewMode === 'wizard'
                ? 'bg-[#FFE600] text-black border-2 border-black shadow-[1.5px_1.5px_0px_0px_#000]'
                : 'text-black/70 hover:text-black border-2 border-transparent'
            }`}
            title="Guided Step-by-Step Wizard"
          >
            <Wand2 className="w-3.5 h-3.5 stroke-[2.5]" />
            <span className="hidden sm:inline">Guided Wizard</span>
          </button>

          <button
            onClick={() => onChangeViewMode('plan')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg font-black transition-all ${
              activeViewMode === 'plan'
                ? 'bg-[#FFE600] text-black border-2 border-black shadow-[1.5px_1.5px_0px_0px_#000]'
                : 'text-black/70 hover:text-black border-2 border-transparent'
            }`}
            title="Structured Plan & Directory"
          >
            <Layers className="w-3.5 h-3.5 stroke-[2.5]" />
            <span className="hidden sm:inline">Plan Preview</span>
            {totalRecordsCount > 0 && (
              <span className="text-[10px] px-1 rounded bg-black text-white font-black">
                {totalRecordsCount}
              </span>
            )}
          </button>

          <button
            onClick={() => onChangeViewMode('vendors')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg font-black transition-all ${
              activeViewMode === 'vendors'
                ? 'bg-[#FFE600] text-black border-2 border-black shadow-[1.5px_1.5px_0px_0px_#000]'
                : 'text-black/70 hover:text-black border-2 border-transparent'
            }`}
            title="Vendor Price Intelligence & Multi-Vendor Comparison"
          >
            <Building2 className="w-3.5 h-3.5 stroke-[2.5]" />
            <span className="hidden sm:inline">Vendors</span>
          </button>

          <button
            onClick={() => onChangeViewMode('external')}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg font-black transition-all ${
              activeViewMode === 'external'
                ? 'bg-[#FFE600] text-black border-2 border-black shadow-[1.5px_1.5px_0px_0px_#000]'
                : 'text-black/70 hover:text-black border-2 border-transparent'
            }`}
            title="OpenStreetMap Venues & Discovery"
          >
            <Compass className="w-3.5 h-3.5 stroke-[2.5]" />
            <span className="hidden sm:inline">Venue Discovery</span>
          </button>
        </div>

        {/* Right Action Cluster */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Quick Demo Button (only if empty) */}
          {totalRecordsCount === 0 && (
            <button
              onClick={onLoadSampleBatch}
              className="hidden sm:flex items-center gap-1.5 bg-white hover:bg-slate-100 text-black border-2 border-black px-2.5 py-1.5 rounded-xl text-xs font-black shadow-[2px_2px_0px_0px_#000] transition-all"
              title="Load sample verified vendors"
            >
              <Sparkles className="w-3.5 h-3.5 text-black stroke-[2.5]" />
              <span>Sample Plan</span>
            </button>
          )}

          {/* New Quote Injector Button */}
          <button
            onClick={onOpenInjector}
            className="flex items-center gap-1.5 bg-[#4ADE80] hover:bg-[#22C55E] text-black border-2 border-black px-3 py-1.5 rounded-xl text-xs font-black shadow-[2px_2px_0px_0px_#000] hover:translate-x-[0.5px] hover:translate-y-[0.5px] transition-all"
            title="Inject real quote verbatim into ledger"
          >
            <Plus className="w-3.5 h-3.5 stroke-[3]" />
            <span className="hidden md:inline">Add Quote</span>
          </button>

          {/* Quick PDF Print Button */}
          {brief && (
            <button
              onClick={onExport}
              className="hidden md:flex p-1.5 text-black bg-white hover:bg-slate-100 border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] transition-all"
              title="Export Ledger PDF"
            >
              <Printer className="w-4 h-4 stroke-[2.5]" />
            </button>
          )}

          {/* Reset Workspace */}
          <button
            onClick={onReset}
            className="p-1.5 text-black bg-white hover:bg-red-50 border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] transition-all"
            title="Clear workspace"
          >
            <RotateCcw className="w-4 h-4 stroke-[2.5]" />
          </button>
        </div>
      </div>
    </header>
  );
};
