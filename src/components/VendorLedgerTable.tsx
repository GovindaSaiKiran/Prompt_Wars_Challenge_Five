import React, { useState, useMemo } from 'react';
import {
  VendorPriceRecord,
  ServiceCategory,
  EventBrief,
} from '../types/intelligence';
import {
  formatInr,
  calculateVendorCost,
  CATEGORY_LABELS,
} from '../utils/ledgerMath';
import { ProvenancePill } from './ProvenancePill';
import {
  Search,
  Plus,
  Trash2,
  Mail,
  Check,
  Phone,
  MapPin,
  ArrowUpDown,
  Sparkles,
} from 'lucide-react';

interface VendorLedgerTableProps {
  vendors: VendorPriceRecord[];
  brief: EventBrief | null;
  onToggleSelect: (id: string) => void;
  onSelectAll: (select: boolean) => void;
  onDeleteVendor: (id: string) => void;
  onOpenAudit: (vendor: VendorPriceRecord) => void;
  onDraftAction: (vendor: VendorPriceRecord) => void;
  onOpenInjector: () => void;
  onLoadSampleBatch: () => void;
}

const CATEGORY_BADGE_STYLES: Record<ServiceCategory, { bg: string; icon: string }> = {
  venue: { bg: 'bg-[#FED7AA]', icon: '🏰' },
  catering: { bg: 'bg-[#FEF08A]', icon: '🍽️' },
  decor: { bg: 'bg-[#FDA4AF]', icon: '🌸' },
  av: { bg: 'bg-[#D8B4FE]', icon: '🔊' },
  photo: { bg: 'bg-[#FBCFE8]', icon: '📸' },
  entertainment: { bg: 'bg-[#BAE6FD]', icon: '🎸' },
  logistics: { bg: 'bg-[#A7F3D0]', icon: '🚐' },
};

export const VendorLedgerTable: React.FC<VendorLedgerTableProps> = ({
  vendors,
  brief,
  onToggleSelect,
  onSelectAll,
  onDeleteVendor,
  onOpenAudit,
  onDraftAction,
  onOpenInjector,
  onLoadSampleBatch,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<ServiceCategory | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'total' | 'name' | 'category'>('total');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Filtered vendors
  const filteredVendors = useMemo(() => {
    return vendors.filter((v) => {
      const matchesCategory =
        selectedCategory === 'all' || v.category === selectedCategory;
      const matchesSearch =
        searchQuery === '' ||
        v.vendorName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        v.verbatimSnippet.toLowerCase().includes(searchQuery.toLowerCase()) ||
        v.inclusions.some((inc) =>
          inc.toLowerCase().includes(searchQuery.toLowerCase())
        );
      return matchesCategory && matchesSearch;
    });
  }, [vendors, selectedCategory, searchQuery]);

  // Sorted vendors
  const sortedVendors = useMemo(() => {
    const list = [...filteredVendors];
    list.sort((a, b) => {
      if (sortBy === 'total') {
        const costA = brief ? calculateVendorCost(a, brief).grossTotal : a.basePrice;
        const costB = brief ? calculateVendorCost(b, brief).grossTotal : b.basePrice;
        return sortDirection === 'asc' ? costA - costB : costB - costA;
      }
      if (sortBy === 'name') {
        return sortDirection === 'asc'
          ? a.vendorName.localeCompare(b.vendorName)
          : b.vendorName.localeCompare(a.vendorName);
      }
      if (sortBy === 'category') {
        return sortDirection === 'asc'
          ? a.category.localeCompare(b.category)
          : b.category.localeCompare(a.category);
      }
      return 0;
    });
    return list;
  }, [filteredVendors, sortBy, sortDirection, brief]);

  const allFilteredSelected =
    filteredVendors.length > 0 && filteredVendors.every((v) => v.isSelectedForBudget);

  const toggleSort = (field: 'total' | 'name' | 'category') => {
    if (sortBy === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortDirection('desc');
    }
  };

  // Category Counts
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = { all: vendors.length };
    vendors.forEach((v) => {
      counts[v.category] = (counts[v.category] || 0) + 1;
    });
    return counts;
  }, [vendors]);

  return (
    <div className="bg-white border-2 border-black rounded-2xl overflow-hidden shadow-[4px_4px_0px_0px_#000]">
      {/* Table Toolbar */}
      <div className="p-3.5 sm:p-4 border-b-2 border-black bg-[#F8F5EE] space-y-3">
        {/* Category Pills Strip */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1 no-scrollbar w-full">
          <button
            onClick={() => setSelectedCategory('all')}
            className={`px-2.5 py-1 rounded-lg text-xs font-black transition-all shrink-0 ${
              selectedCategory === 'all'
                ? 'bg-[#FFE600] text-black border-2 border-black shadow-[1.5px_1.5px_0px_0px_#000]'
                : 'bg-white hover:bg-slate-100 text-black border-2 border-black/80'
            }`}
          >
            All Categories ({categoryCounts.all || 0})
          </button>
          {(Object.keys(CATEGORY_LABELS) as ServiceCategory[]).map((cat) => {
            const theme = CATEGORY_BADGE_STYLES[cat] || { bg: 'bg-white', icon: '📦' };
            return (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-2.5 py-1 rounded-lg text-xs font-black transition-all shrink-0 flex items-center gap-1.5 ${
                  selectedCategory === cat
                    ? 'bg-[#FFE600] text-black border-2 border-black shadow-[1.5px_1.5px_0px_0px_#000]'
                    : 'bg-white hover:bg-slate-100 text-black border-2 border-black/80'
                }`}
              >
                <span>{theme.icon}</span>
                <span>{CATEGORY_LABELS[cat]}</span>
                <span className="text-[10px] bg-black text-white px-1 py-0.2 rounded font-black">
                  {categoryCounts[cat] || 0}
                </span>
              </button>
            );
          })}
        </div>

        {/* Search & Actions Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 text-black absolute left-3 top-1/2 -translate-y-1/2 stroke-[2.5]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search vendor name, inclusions, or notes..."
              className="w-full bg-white border-2 border-black rounded-xl pl-8.5 pr-3 py-1.5 text-xs text-black placeholder:text-slate-500 font-bold focus:outline-none shadow-[1.5px_1.5px_0px_0px_#000] transition-all"
            />
          </div>

          {/* Quick Select All & Add Button */}
          <div className="flex items-center gap-2 shrink-0">
            {vendors.length > 0 && (
              <button
                onClick={() => onSelectAll(!allFilteredSelected)}
                className="text-xs font-black text-black bg-white hover:bg-slate-100 border-2 border-black px-2.5 py-1.5 rounded-xl shadow-[1.5px_1.5px_0px_0px_#000] transition-all"
              >
                {allFilteredSelected ? 'Deselect All' : 'Select All in Budget'}
              </button>
            )}

            <button
              onClick={onOpenInjector}
              className="flex items-center gap-1.5 bg-[#FFE600] hover:bg-[#FACC15] text-black font-black px-3 py-1.5 rounded-xl text-xs border-2 border-black shadow-[1.5px_1.5px_0px_0px_#000] transition-all"
            >
              <Plus className="w-3.5 h-3.5 stroke-[3]" />
              <span>Add Quote</span>
            </button>
          </div>
        </div>
      </div>

      {/* Empty State vs Table */}
      {vendors.length === 0 ? (
        <div className="p-10 text-center bg-white space-y-3">
          <div className="w-12 h-12 rounded-2xl bg-[#FFE600] border-2 border-black flex items-center justify-center mx-auto text-xl shadow-[2.5px_2.5px_0px_0px_#000]">
            🎪
          </div>
          <h3 className="text-base font-black text-black font-heading uppercase">
            No Event Quotes Added Yet
          </h3>
          <p className="text-xs font-bold text-slate-600 max-w-sm mx-auto">
            Tell the AI concierge about your event on the left or load sample verified vendor quotes.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-2.5 mt-3">
            <button
              onClick={onOpenInjector}
              className="bg-[#FFE600] hover:bg-[#FACC15] text-black font-black px-4 py-2 rounded-xl text-xs border-2 border-black shadow-[2px_2px_0px_0px_#000] flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5 stroke-[3]" />
              <span>Add First Vendor</span>
            </button>
            <button
              onClick={onLoadSampleBatch}
              className="bg-[#86EFAC] hover:bg-[#4ADE80] text-black font-black px-4 py-2 rounded-xl text-xs border-2 border-black shadow-[2px_2px_0px_0px_#000] flex items-center gap-1.5"
            >
              <Sparkles className="w-3.5 h-3.5 stroke-[2.5]" />
              <span>Load Sample Plan</span>
            </button>
          </div>
        </div>
      ) : sortedVendors.length === 0 ? (
        <div className="p-10 text-center text-black font-bold text-xs bg-white">
          No vendors found matching "{searchQuery}".
        </div>
      ) : (
        /* Responsive Vendor Table */
        <div className="overflow-x-auto bg-white">
          <table className="w-full text-left text-xs border-collapse min-w-[620px]">
            <thead>
              <tr className="border-b-2 border-black bg-[#F8F5EE] text-black text-[10px] font-black uppercase tracking-wider select-none">
                <th className="py-2.5 px-3 w-12 text-center">Budget</th>
                <th className="py-2.5 px-3">
                  <button
                    onClick={() => toggleSort('name')}
                    className="flex items-center gap-1 hover:text-black font-black"
                  >
                    <span>Vendor & Details</span>
                    <ArrowUpDown className="w-3 h-3 stroke-[2.5]" />
                  </button>
                </th>
                <th className="py-2.5 px-3 w-32">Rate / Unit</th>
                <th className="py-2.5 px-3 text-right w-32">
                  <button
                    onClick={() => toggleSort('total')}
                    className="flex items-center gap-1 ml-auto hover:text-black font-black"
                  >
                    <span>Total Cost</span>
                    <ArrowUpDown className="w-3 h-3 stroke-[2.5]" />
                  </button>
                </th>
                <th className="py-2.5 px-3 w-28">Status</th>
                <th className="py-2.5 px-3 text-right w-28">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y-2 divide-black/10">
              {sortedVendors.map((vendor) => {
                const cost = brief ? calculateVendorCost(vendor, brief) : null;
                const isSelected = vendor.isSelectedForBudget;
                const theme = CATEGORY_BADGE_STYLES[vendor.category] || { bg: 'bg-[#F3F4F6]', icon: '📦' };

                return (
                  <tr
                    key={vendor.id}
                    className={`transition-colors hover:bg-[#FFFDF0] ${
                      isSelected ? 'bg-white' : 'opacity-60 bg-slate-50'
                    }`}
                  >
                    {/* Include in Budget Checkbox */}
                    <td className="py-3 px-3 text-center align-middle">
                      <button
                        onClick={() => onToggleSelect(vendor.id)}
                        className={`w-5 h-5 rounded-md flex items-center justify-center transition-all mx-auto ${
                          isSelected
                            ? 'bg-[#4ADE80] text-black border-2 border-black shadow-[1px_1px_0px_0px_#000]'
                            : 'border-2 border-black bg-white hover:bg-slate-100'
                        }`}
                        title={isSelected ? 'Included in budget. Click to exclude.' : 'Excluded. Click to include.'}
                      >
                        <Check className="w-3.5 h-3.5 stroke-[3]" />
                      </button>
                    </td>

                    {/* Vendor Name, Category, Phone & Map Navigation */}
                    <td className="py-3 px-3 align-middle">
                      <div className="font-black text-black text-xs sm:text-sm">
                        {vendor.vendorName}
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 mt-1">
                        <span className={`text-[10px] font-black px-1.5 py-0.2 rounded border border-black text-black ${theme.bg}`}>
                          <span>{theme.icon}</span> {CATEGORY_LABELS[vendor.category]}
                        </span>

                        {vendor.phone && (
                          <a
                            href={`tel:${vendor.phone}`}
                            className="text-[10px] text-black bg-[#86EFAC] hover:bg-[#4ADE80] border border-black shadow-[1px_1px_0px_0px_#000] px-1.5 py-0.2 rounded flex items-center gap-1 font-black transition-colors"
                            title={`Call ${vendor.vendorName}`}
                          >
                            <Phone className="w-2.5 h-2.5 stroke-[3]" />
                            <span>{vendor.phone}</span>
                          </a>
                        )}

                        {vendor.mapUrl && (
                          <a
                            href={vendor.mapUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-[10px] text-black bg-[#7DD3FC] hover:bg-[#38BDF8] border border-black shadow-[1px_1px_0px_0px_#000] px-1.5 py-0.2 rounded flex items-center gap-1 font-black transition-colors"
                            title="Open directions in Google Maps"
                          >
                            <MapPin className="w-2.5 h-2.5 stroke-[3]" />
                            <span>Maps</span>
                          </a>
                        )}
                      </div>
                    </td>

                    {/* Base Rate */}
                    <td className="py-3 px-3 align-middle text-black">
                      <div className="font-black text-black text-xs font-heading">
                        {formatInr(vendor.basePrice)}
                      </div>
                      <div className="text-[10px] font-bold text-slate-600">
                        per {vendor.unit.replace('per_', '').replace('_', ' ')}
                        {vendor.gstPct > 0 && ` (+${vendor.gstPct}% GST)`}
                      </div>
                    </td>

                    {/* Total Estimated Cost */}
                    <td className="py-3 px-3 text-right align-middle">
                      <div className="font-black text-black text-xs sm:text-sm font-heading">
                        {cost ? formatInr(cost.grossTotal) : formatInr(vendor.basePrice)}
                      </div>
                      <div className="mt-0.5">
                        {isSelected ? (
                          <span className="text-[9px] font-black px-1.5 py-0.2 rounded bg-[#86EFAC] text-black border border-black">
                            IN BUDGET
                          </span>
                        ) : (
                          <span className="text-[9px] font-bold text-slate-500">
                            Excluded
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Status Pill */}
                    <td className="py-3 px-3 align-middle">
                      <ProvenancePill status={vendor.status} />
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-3 text-right align-middle">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => onOpenAudit(vendor)}
                          className="px-2 py-0.5 text-[11px] text-black bg-white hover:bg-[#FFE600] border border-black shadow-[1px_1px_0px_0px_#000] rounded transition-all font-black"
                          title="View quote details"
                        >
                          Details
                        </button>

                        <button
                          onClick={() => onDraftAction(vendor)}
                          className="p-1 text-black bg-white hover:bg-[#BAE6FD] border border-black shadow-[1px_1px_0px_0px_#000] rounded transition-all"
                          title="Message vendor"
                        >
                          <Mail className="w-3 h-3 stroke-[2.5]" />
                        </button>

                        <button
                          onClick={() => onDeleteVendor(vendor.id)}
                          className="p-1 text-black hover:text-red-600 bg-white hover:bg-red-50 border border-black shadow-[1px_1px_0px_0px_#000] rounded transition-all"
                          title="Delete quote"
                        >
                          <Trash2 className="w-3 h-3 stroke-[2.5]" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
