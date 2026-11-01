import React, { useState, useEffect, useRef } from 'react';
import { VendorPriceRecord } from '../types/intelligence';
import { CATEGORY_LABELS, formatInr } from '../utils/ledgerMath';
import { Search, Plus, Sliders, Download, Sparkles, X, ArrowRight } from 'lucide-react';

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  vendors: VendorPriceRecord[];
  onOpenInjector: () => void;
  onOpenBriefConfig: () => void;
  onExport: () => void;
  onLoadSampleBatch: () => void;
  onSelectVendor: (vendor: VendorPriceRecord) => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  vendors,
  onOpenInjector,
  onOpenBriefConfig,
  onExport,
  onLoadSampleBatch,
  onSelectVendor,
}) => {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      setQuery('');
      setSelectedIndex(0);
    }
  }, [isOpen]);

  // Built-in Actions
  const actions = [
    {
      id: 'action-add',
      title: 'Add Vendor Quote',
      description: 'Log a new direct quotation or supplier rate card',
      icon: Plus,
      emoji: '➕',
      bgColor: 'bg-[#86EFAC]',
      run: () => {
        onClose();
        onOpenInjector();
      },
    },
    {
      id: 'action-brief',
      title: 'Edit Event Details',
      description: 'Update budget cap, guest count, location, or date',
      icon: Sliders,
      emoji: '🎪',
      bgColor: 'bg-[#FED7AA]',
      run: () => {
        onClose();
        onOpenBriefConfig();
      },
    },
    {
      id: 'action-sample',
      title: 'Load Demo Event Plan',
      description: 'Populate 6 verified vendors with complete math',
      icon: Sparkles,
      emoji: '✨',
      bgColor: 'bg-[#D8B4FE]',
      run: () => {
        onClose();
        onLoadSampleBatch();
      },
    },
    {
      id: 'action-export',
      title: 'Export Full Plan & PDF',
      description: 'Download print-ready PDF with phones, maps & ledger',
      icon: Download,
      emoji: '📄',
      bgColor: 'bg-[#38BDF8]',
      run: () => {
        onClose();
        onExport();
      },
    },
  ];

  // Filtered actions & vendors
  const filteredActions = actions.filter((a) =>
    a.title.toLowerCase().includes(query.toLowerCase()) ||
    a.description.toLowerCase().includes(query.toLowerCase())
  );

  const filteredVendors = vendors.filter((v) =>
    v.vendorName.toLowerCase().includes(query.toLowerCase()) ||
    v.category.toLowerCase().includes(query.toLowerCase()) ||
    v.verbatimSnippet.toLowerCase().includes(query.toLowerCase())
  );

  const totalItems = filteredActions.length + filteredVendors.length;

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return;
      if (e.key === 'Escape') {
        onClose();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % Math.max(1, totalItems));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + totalItems) % Math.max(1, totalItems));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedIndex < filteredActions.length) {
          filteredActions[selectedIndex]?.run();
        } else {
          const vIndex = selectedIndex - filteredActions.length;
          const targetVendor = filteredVendors[vIndex];
          if (targetVendor) {
            onClose();
            onSelectVendor(targetVendor);
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, totalItems, selectedIndex, filteredActions, filteredVendors, onClose, onSelectVendor]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-24 p-4 bg-black/60 backdrop-blur-xs">
      <div
        className="w-full max-w-xl bg-white border-3 border-black rounded-2xl overflow-hidden shadow-[8px_8px_0px_0px_#000] animate-in fade-in-0 zoom-in-95 duration-100 flex flex-col"
        role="dialog"
        aria-modal="true"
      >
        {/* Neo-Brutalist Search Bar Header */}
        <div className="bg-[#FFE600] border-b-3 border-black p-3.5 sm:p-4 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-white border-2 border-black flex items-center justify-center shrink-0 shadow-[1.5px_1.5px_0px_0px_#000] text-sm font-black">
            🔍
          </div>

          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
              }}
              placeholder="Search actions, vendors, halls, catering..."
              className="w-full bg-white border-2 border-black rounded-xl px-3.5 py-2 text-xs sm:text-sm font-bold text-black placeholder:text-black/50 shadow-[2px_2px_0px_0px_#000] focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <kbd className="hidden sm:inline-flex items-center bg-[#F8F5EE] border-2 border-black text-[10px] font-black text-black px-2 py-1 rounded-lg shadow-[1px_1px_0px_0px_#000]">
              ESC
            </kbd>

            {/* Prominent Close Button */}
            <button
              onClick={onClose}
              className="p-2 rounded-xl bg-white hover:bg-black hover:text-white text-black border-2 border-black shadow-[2px_2px_0px_0px_#000] transition-transform active:translate-x-0.5 active:translate-y-0.5 cursor-pointer"
              title="Close search palette"
              aria-label="Close"
            >
              <X className="w-4 h-4 stroke-[2.5]" />
            </button>
          </div>
        </div>

        {/* List of Actions & Results */}
        <div className="max-h-[380px] overflow-y-auto p-3 sm:p-4 space-y-4 bg-[#FFFDF9]">
          {/* Actions Section */}
          {filteredActions.length > 0 && (
            <div className="space-y-2">
              <div className="text-[10px] font-black text-black uppercase tracking-wider px-1 flex items-center gap-1.5">
                <span>⚡ EVENT ACTIONS & SHORTCUTS</span>
              </div>
              <div className="space-y-2">
                {filteredActions.map((action, idx) => {
                  const isSelected = idx === selectedIndex;
                  return (
                    <button
                      key={action.id}
                      onClick={() => action.run()}
                      className={`w-full flex items-center justify-between gap-3 p-3 rounded-xl text-left border-2 border-black transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-[#FFE600] shadow-[3px_3px_0px_0px_#000] translate-x-0.5 translate-y-0.5'
                          : 'bg-[#F8F5EE] hover:bg-[#FFE600]/60 shadow-[2px_2px_0px_0px_#000]'
                      }`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={`w-8 h-8 rounded-lg ${action.bgColor} border-2 border-black flex items-center justify-center shrink-0 shadow-[1px_1px_0px_0px_#000] text-sm font-black`}
                        >
                          {action.emoji}
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs font-black text-black truncate">
                            {action.title}
                          </div>
                          <div className="text-[11px] font-bold text-black/70 truncate">
                            {action.description}
                          </div>
                        </div>
                      </div>

                      <div className="shrink-0 flex items-center gap-1 text-[11px] font-black text-black">
                        <span className="hidden sm:inline">Select</span>
                        <ArrowRight className="w-3.5 h-3.5 stroke-[2.5]" />
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Vendors Section */}
          {filteredVendors.length > 0 && (
            <div className="space-y-2 pt-2 border-t-2 border-black/10">
              <div className="text-[10px] font-black text-black uppercase tracking-wider px-1 flex items-center gap-1.5">
                <span>🎪 MATCHING VENDORS ({filteredVendors.length})</span>
              </div>
              <div className="space-y-2">
                {filteredVendors.map((vendor, idx) => {
                  const actualIdx = filteredActions.length + idx;
                  const isSelected = actualIdx === selectedIndex;
                  return (
                    <button
                      key={vendor.id}
                      onClick={() => {
                        onClose();
                        onSelectVendor(vendor);
                      }}
                      className={`w-full flex items-center justify-between gap-3 p-3 rounded-xl text-left border-2 border-black transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-[#FFE600] shadow-[3px_3px_0px_0px_#000] translate-x-0.5 translate-y-0.5'
                          : 'bg-white hover:bg-[#FFE600]/40 shadow-[2px_2px_0px_0px_#000]'
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="text-xs font-black text-black truncate">
                          {vendor.vendorName}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="bg-[#BAE6FD] text-black text-[10px] font-black px-1.5 py-0.2 rounded border border-black">
                            {CATEGORY_LABELS[vendor.category]}
                          </span>
                          <span className="text-[11px] font-bold text-black/60 truncate">
                            {vendor.phone || 'Location mapped'}
                          </span>
                        </div>
                      </div>

                      <div className="text-right shrink-0">
                        <span className="bg-[#86EFAC] text-black text-xs font-black px-2 py-0.5 rounded-md border border-black block shadow-[1px_1px_0px_0px_#000]">
                          {formatInr(vendor.basePrice)}
                        </span>
                        <span className="text-[10px] font-bold text-black/60 block mt-0.5">
                          per {vendor.unit.replace('per_', '').replace('_', ' ')}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Empty Search State */}
          {filteredActions.length === 0 && filteredVendors.length === 0 && (
            <div className="py-10 text-center space-y-2">
              <div className="w-12 h-12 rounded-xl bg-[#FFE600] border-2 border-black flex items-center justify-center mx-auto text-xl shadow-[2px_2px_0px_0px_#000]">
                🎪
              </div>
              <p className="text-xs font-black text-black">
                No matching actions or vendors found for "{query}".
              </p>
              <p className="text-[11px] font-bold text-black/60">
                Try searching for "catering", "venue", "photo", or "export".
              </p>
            </div>
          )}
        </div>

        {/* Footer Shortcut Helper */}
        <div className="px-4 py-2.5 bg-[#F8F5EE] border-t-2 border-black flex items-center justify-between text-[11px] font-black text-black">
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="bg-white border border-black px-1.5 py-0.2 rounded shadow-[1px_1px_0px_0px_#000]">↑</kbd>
              <kbd className="bg-white border border-black px-1.5 py-0.2 rounded shadow-[1px_1px_0px_0px_#000]">↓</kbd>
              <span className="text-black/70 ml-1">Navigate</span>
            </span>
            <span className="flex items-center gap-1">
              <kbd className="bg-white border border-black px-1.5 py-0.2 rounded shadow-[1px_1px_0px_0px_#000]">↵</kbd>
              <span className="text-black/70 ml-1">Select</span>
            </span>
          </div>

          <button
            onClick={onClose}
            className="text-black hover:underline cursor-pointer flex items-center gap-1"
          >
            <span>Close (ESC)</span>
          </button>
        </div>
      </div>
    </div>
  );
};
