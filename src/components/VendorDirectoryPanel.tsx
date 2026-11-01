import React, { useState, useEffect, useMemo } from 'react';
import {
  AvailabilityStatus,
  MultiVendorComparisonItem,
  MultiVendorComparisonResponse,
  Vendor,
  VendorPriceRecord,
  VendorService,
} from '../types/vendor';
import {
  addLineItemFromPriceRecord,
  compareVendorsApi,
  fetchPriceRecords,
  fetchVendor,
  fetchVendorPriceHistory,
  fetchVendors,
  updateVendor,
} from '../services/vendorApi';
import { ProvenancePill } from './ProvenancePill';
import { AvailabilityPill } from './AvailabilityPill';
import { AddVendorModal } from './AddVendorModal';
import { AddPriceRecordModal } from './AddPriceRecordModal';
import { formatInr } from '../utils/ledgerMath';
import {
  Search,
  Plus,
  Filter,
  CheckCircle2,
  Building2,
  Phone,
  Mail,
  MapPin,
  ExternalLink,
  Tag,
  Scale,
  Sparkles,
  AlertCircle,
  HelpCircle,
  ChevronRight,
  ShieldCheck,
  Check,
  Calendar,
  X,
  FileText,
  BadgeAlert,
} from 'lucide-react';

interface VendorDirectoryPanelProps {
  currentEventId?: string | null;
  currentBudgetId?: string | null;
  onLineItemAddedToBudget?: (item: any) => void;
  onShowToast: (message: string) => void;
}

const CATEGORIES = [
  'all',
  'catering',
  'venue',
  'decoration',
  'photography',
  'equipment',
  'entertainment',
  'transport',
  'other',
];

export const VendorDirectoryPanel: React.FC<VendorDirectoryPanelProps> = ({
  currentEventId,
  currentBudgetId,
  onLineItemAddedToBudget,
  onShowToast,
}) => {
  // Navigation sub-tab: 'directory' | 'comparison'
  const [activeTab, setActiveTab] = useState<'directory' | 'comparison'>('directory');

  // Directory State
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCity, setSelectedCity] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedVerification, setSelectedVerification] = useState<string>('all');
  const [activeOnly, setActiveOnly] = useState<boolean>(true);

  // Modals & Drawers
  const [isAddVendorOpen, setIsAddVendorOpen] = useState(false);
  const [isAddPriceOpen, setIsAddPriceOpen] = useState(false);
  const [editingVendor, setEditingVendor] = useState<Vendor | null>(null);
  const [selectedVendorForPrice, setSelectedVendorForPrice] = useState<Vendor | null>(null);

  // Vendor Detail View
  const [detailVendor, setDetailVendor] = useState<Vendor | null>(null);
  const [detailHistory, setDetailHistory] = useState<VendorPriceRecord[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Comparison Tool State
  const [compCategory, setCompCategory] = useState<string>('catering');
  const [compQuantity, setCompQuantity] = useState<string>('150');
  const [compUnit, setCompUnit] = useState<string>('person');
  const [compCity, setCompCity] = useState<string>('Mumbai');
  const [isComparing, setIsComparing] = useState<boolean>(false);
  const [comparisonResult, setComparisonResult] = useState<MultiVendorComparisonResponse | null>(null);
  const [compError, setCompError] = useState<string | null>(null);

  // Adding to budget tracking
  const [addingRecordId, setAddingRecordId] = useState<string | null>(null);

  // Load vendors from real backend
  const loadVendors = async () => {
    try {
      setIsLoading(true);
      const params: any = {
        limit: 100,
        is_active: activeOnly ? true : undefined,
      };
      if (searchQuery.trim()) params.search = searchQuery.trim();
      if (selectedCity.trim()) params.city = selectedCity.trim();
      if (selectedCategory !== 'all') params.category = selectedCategory;
      if (selectedVerification !== 'all') params.verification_status = selectedVerification;

      const res = await fetchVendors(params);
      setVendors(res.items);
    } catch (err: any) {
      console.error('Failed to load vendors:', err);
      onShowToast(`Failed to load vendors: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadVendors();
  }, [searchQuery, selectedCity, selectedCategory, selectedVerification, activeOnly]);

  // Open detail drawer and load price history
  const handleOpenVendorDetail = async (vendor: Vendor) => {
    try {
      setIsLoadingHistory(true);
      setDetailVendor(vendor);
      // Fetch full vendor details with services
      const fullVendor = await fetchVendor(vendor.id);
      setDetailVendor(fullVendor);
      // Fetch history
      const history = await fetchVendorPriceHistory(vendor.id);
      setDetailHistory(history);
    } catch (err: any) {
      console.error('Failed to load vendor history:', err);
      onShowToast('Could not load complete vendor history');
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // Toggle active status
  const handleToggleActive = async (vendor: Vendor) => {
    try {
      const updated = await updateVendor(vendor.id, { is_active: !vendor.is_active });
      setVendors((prev) => prev.map((v) => (v.id === updated.id ? updated : v)));
      if (detailVendor && detailVendor.id === updated.id) {
        setDetailVendor(updated);
      }
      onShowToast(`Vendor ${updated.business_name} is now ${updated.is_active ? 'active' : 'inactive'}.`);
    } catch (err: any) {
      onShowToast(`Failed to update vendor: ${err.message}`);
    }
  };

  // Run Multi-Vendor Comparison
  const handleRunComparison = async () => {
    setCompError(null);
    try {
      setIsComparing(true);
      const qtyNum = parseFloat(compQuantity);
      if (isNaN(qtyNum) || qtyNum <= 0) {
        setCompError('Please enter a valid requested quantity greater than 0.');
        setIsComparing(false);
        return;
      }

      const res = await compareVendorsApi({
        category: compCategory !== 'all' ? compCategory : undefined,
        quantity: qtyNum,
        unit: compUnit.trim() || undefined,
        target_city: compCity.trim() || undefined,
        currency: 'INR',
      });
      setComparisonResult(res);
    } catch (err: any) {
      setCompError(err.message || 'Comparison failed');
    } finally {
      setIsComparing(false);
    }
  };

  // Run initial comparison on tab switch if empty
  useEffect(() => {
    if (activeTab === 'comparison' && !comparisonResult && !isComparing) {
      handleRunComparison();
    }
  }, [activeTab]);

  // Add Price Record directly to Event Budget as Line Item
  const handleAddToBudget = async (item: MultiVendorComparisonItem | VendorPriceRecord, vendorName?: string) => {
    if (!currentEventId || !currentBudgetId) {
      onShowToast('Please create or select an event and budget first before adding line items.');
      return;
    }

    const priceRecordId = 'price_record_id' in item ? item.price_record_id : item.id;
    const category = 'category' in item ? item.category : 'other';
    const description = `${vendorName || ('vendor_name' in item ? item.vendor_name : 'Vendor')} - ${'service_name' in item ? item.service_name : 'Service Offering'}`;
    const quantity = compQuantity ? parseFloat(compQuantity) : 1;

    try {
      setAddingRecordId(priceRecordId);
      const res = await addLineItemFromPriceRecord(currentEventId, currentBudgetId, {
        category,
        description,
        quantity,
        vendor_price_record_id: priceRecordId,
        notes: `Selected via Vendor Intelligence [Record: ${priceRecordId.substring(0, 8)}]`,
      });
      onShowToast(`Added "${description}" to budget! Snapshotted rate preserved.`);
      if (onLineItemAddedToBudget) {
        onLineItemAddedToBudget(res);
      }
    } catch (err: any) {
      onShowToast(`Failed to add line item: ${err.message}`);
    } finally {
      setAddingRecordId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-[#FFFDF9] border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl">🏪</span>
            <h2 className="text-lg font-black text-black uppercase tracking-tight font-heading">
              Vendor Price Intelligence
            </h2>
            <span className="text-[10px] px-2 py-0.5 rounded bg-[#FFE600] font-black text-black border border-black shadow-[1px_1px_0px_0px_#000]">
              VERIFIED LEDGER
            </span>
          </div>
          <p className="text-xs text-black/70 font-bold mt-1">
            Browse verified vendors, audit price observations with provenance, compare normalized rates, and add directly to event budgets.
          </p>
        </div>

        {/* Top Controls */}
        <div className="flex items-center gap-2 self-stretch md:self-auto shrink-0">
          <button
            onClick={() => {
              setEditingVendor(null);
              setIsAddVendorOpen(true);
            }}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-black text-black bg-[#FFE600] hover:bg-[#FFE600]/80 border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] transition-all"
          >
            <Building2 className="w-4 h-4 stroke-[2.5]" />
            <span>Register Vendor</span>
          </button>

          <button
            onClick={() => {
              setSelectedVendorForPrice(null);
              setIsAddPriceOpen(true);
            }}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-black text-black bg-[#4ADE80] hover:bg-[#22C55E] border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] transition-all"
          >
            <Plus className="w-4 h-4 stroke-[3]" />
            <span>Add Price Record</span>
          </button>
        </div>
      </div>

      {/* Main Tabs: Directory vs Comparison */}
      <div className="flex items-center gap-2 border-b-2 border-black pb-2">
        <button
          onClick={() => setActiveTab('directory')}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-black rounded-xl transition-all ${
            activeTab === 'directory'
              ? 'bg-black text-white shadow-[2px_2px_0px_0px_#FFE600]'
              : 'bg-white text-black border-2 border-black hover:bg-slate-50'
          }`}
        >
          <Building2 className="w-4 h-4" />
          <span>Vendor Catalog ({vendors.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('comparison')}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-black rounded-xl transition-all ${
            activeTab === 'comparison'
              ? 'bg-[#FFE600] text-black border-2 border-black shadow-[2px_2px_0px_0px_#000]'
              : 'bg-white text-black border-2 border-black hover:bg-slate-50'
          }`}
        >
          <Scale className="w-4 h-4 stroke-[2.5]" />
          <span>Multi-Vendor Comparison Engine</span>
        </button>
      </div>

      {/* TAB 1: VENDOR DIRECTORY */}
      {activeTab === 'directory' && (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="bg-[#FFFDF9] border-2 border-black rounded-xl p-4 shadow-[2px_2px_0px_0px_#000] space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              {/* Search */}
              <div className="relative md:col-span-2">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-black/50" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search vendors by name, trade or services..."
                  className="w-full pl-9 pr-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[1.5px_1.5px_0px_0px_#000] focus:outline-none"
                />
              </div>

              {/* City Filter */}
              <div>
                <input
                  type="text"
                  value={selectedCity}
                  onChange={(e) => setSelectedCity(e.target.value)}
                  placeholder="Filter by City (e.g. Mumbai, Pune)..."
                  className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[1.5px_1.5px_0px_0px_#000] focus:outline-none"
                />
              </div>

              {/* Verification Status */}
              <div>
                <select
                  value={selectedVerification}
                  onChange={(e) => setSelectedVerification(e.target.value)}
                  className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[1.5px_1.5px_0px_0px_#000] focus:outline-none"
                >
                  <option value="all">All Verification Statuses</option>
                  <option value="verified">Verified Only</option>
                  <option value="pending">Pending</option>
                  <option value="unverified">Unverified</option>
                </select>
              </div>
            </div>

            {/* Category Pills & Active Toggle */}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-black/10">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[10px] font-black uppercase text-black/60 mr-1">Category:</span>
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    className={`px-2.5 py-1 text-[11px] font-black rounded-lg border border-black uppercase tracking-wider transition-all ${
                      selectedCategory === cat
                        ? 'bg-black text-white shadow-[1px_1px_0px_0px_#000]'
                        : 'bg-white text-black hover:bg-slate-100'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="activeToggle"
                  checked={activeOnly}
                  onChange={(e) => setActiveOnly(e.target.checked)}
                  className="w-4 h-4 rounded border-2 border-black accent-black cursor-pointer"
                />
                <label htmlFor="activeToggle" className="text-xs font-black text-black cursor-pointer select-none">
                  Active Listings Only
                </label>
              </div>
            </div>
          </div>

          {/* Vendors Grid */}
          {isLoading ? (
            <div className="p-12 text-center bg-white border-2 border-black rounded-2xl shadow-[4px_4px_0px_0px_#000]">
              <div className="inline-block animate-spin text-2xl mb-2">⚙️</div>
              <div className="text-xs font-black text-black uppercase">Loading verified directory...</div>
            </div>
          ) : vendors.length === 0 ? (
            <div className="p-12 text-center bg-white border-2 border-black rounded-2xl shadow-[4px_4px_0px_0px_#000] space-y-3">
              <div className="text-3xl">🔍</div>
              <h3 className="text-sm font-black text-black uppercase">No vendors match your filters</h3>
              <p className="text-xs text-black/60 max-w-sm mx-auto font-medium">
                Try broadening your search, clearing the city filter, or register a new verified vendor profile.
              </p>
              <button
                onClick={() => {
                  setSearchQuery('');
                  setSelectedCity('');
                  setSelectedCategory('all');
                  setSelectedVerification('all');
                }}
                className="px-3 py-1.5 text-xs font-black bg-[#FFE600] border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
              >
                Clear Filters
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {vendors.map((vendor) => (
                <div
                  key={vendor.id}
                  className={`bg-white border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] flex flex-col justify-between transition-all hover:translate-x-[-1px] hover:translate-y-[-1px] ${
                    !vendor.is_active ? 'opacity-70 bg-slate-50' : ''
                  }`}
                >
                  <div className="space-y-3">
                    {/* Top Row */}
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="text-[10px] font-black uppercase tracking-wider text-black/60 block">
                          {vendor.vendor_type}
                        </span>
                        <h4 className="text-sm font-black text-black font-heading leading-snug">
                          {vendor.business_name}
                        </h4>
                      </div>

                      {/* Verification Status Badge */}
                      <span
                        className={`text-[9px] px-2 py-0.5 rounded font-black uppercase tracking-wider border border-black shadow-[1px_1px_0px_0px_#000] shrink-0 ${
                          vendor.verification_status === 'verified'
                            ? 'bg-[#86EFAC] text-black'
                            : vendor.verification_status === 'pending'
                            ? 'bg-[#FEF08A] text-black'
                            : 'bg-slate-200 text-black'
                        }`}
                      >
                        {vendor.verification_status}
                      </span>
                    </div>

                    {vendor.description && (
                      <p className="text-xs text-black/70 font-medium line-clamp-2">
                        {vendor.description}
                      </p>
                    )}

                    {/* Metadata Badges */}
                    <div className="flex flex-wrap items-center gap-2 pt-2 text-[11px] font-bold text-black/80">
                      {vendor.city && (
                        <span className="flex items-center gap-1 bg-slate-100 px-2 py-0.5 rounded border border-black/20">
                          <MapPin className="w-3 h-3" />
                          {vendor.city}
                        </span>
                      )}
                      {vendor.phone && (
                        <span className="flex items-center gap-1 bg-slate-100 px-2 py-0.5 rounded border border-black/20">
                          <Phone className="w-3 h-3" />
                          {vendor.phone}
                        </span>
                      )}
                    </div>

                    {/* Services Count */}
                    <div className="text-[11px] font-black text-black pt-1">
                      Offerings: {vendor.services ? vendor.services.length : 0} catalog services
                    </div>
                  </div>

                  {/* Actions Bar */}
                  <div className="flex items-center justify-between gap-2 pt-4 border-t-2 border-black/10 mt-4">
                    <button
                      onClick={() => handleOpenVendorDetail(vendor)}
                      className="flex items-center gap-1 text-xs font-black text-black hover:underline"
                    >
                      <span>View Services & Rates</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => {
                          setSelectedVendorForPrice(vendor);
                          setIsAddPriceOpen(true);
                        }}
                        title="Record a new price observation for this vendor"
                        className="p-1.5 bg-[#4ADE80] hover:bg-[#22C55E] text-black border border-black rounded-lg shadow-[1px_1px_0px_0px_#000]"
                      >
                        <Tag className="w-3.5 h-3.5 stroke-[2.5]" />
                      </button>

                      <button
                        onClick={() => {
                          setEditingVendor(vendor);
                          setIsAddVendorOpen(true);
                        }}
                        title="Edit vendor profile"
                        className="px-2 py-1 text-[11px] font-black bg-white hover:bg-slate-100 text-black border border-black rounded-lg shadow-[1px_1px_0px_0px_#000]"
                      >
                        Edit
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: MULTI-VENDOR COMPARISON ENGINE */}
      {activeTab === 'comparison' && (
        <div className="space-y-6">
          {/* Comparison Query Controls Card */}
          <div className="bg-[#FFFDF9] border-2 border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-4">
            <div className="flex items-center justify-between border-b-2 border-black pb-3">
              <div className="flex items-center gap-2">
                <Scale className="w-5 h-5 text-black stroke-[2.5]" />
                <h3 className="text-sm font-black text-black uppercase tracking-tight font-heading">
                  Multi-Vendor Price Comparison Parameters
                </h3>
              </div>
              <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-[#FFE600] border border-black">
                DETERMINISTIC COST NORMALIZATION
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-black uppercase text-black">Category *</label>
                <select
                  value={compCategory}
                  onChange={(e) => setCompCategory(e.target.value)}
                  className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
                >
                  <option value="catering">Catering / Food & Beverage</option>
                  <option value="venue">Venue / Banquet Hall</option>
                  <option value="decoration">Decoration / Floral</option>
                  <option value="photography">Photography / Media</option>
                  <option value="equipment">Equipment / Audio-Visual</option>
                  <option value="entertainment">Entertainment / DJ / Artists</option>
                  <option value="transport">Transportation / Logistics</option>
                  <option value="other">All Categories</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-black uppercase text-black">Required Quantity *</label>
                <input
                  type="number"
                  step="1"
                  min="1"
                  value={compQuantity}
                  onChange={(e) => setCompQuantity(e.target.value)}
                  placeholder="e.g. 150"
                  className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-black uppercase text-black">Target Unit</label>
                <input
                  type="text"
                  value={compUnit}
                  onChange={(e) => setCompUnit(e.target.value)}
                  placeholder="e.g. person, plate, event, hour"
                  className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-black uppercase text-black">Event City (Proximity)</label>
                <input
                  type="text"
                  value={compCity}
                  onChange={(e) => setCompCity(e.target.value)}
                  placeholder="e.g. Mumbai, Pune"
                  className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
                />
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <span className="text-[11px] text-black/60 font-bold">
                Units in the same family (e.g. 'per person' and 'per plate') are automatically normalized. Incompatible units are explicitly flagged.
              </span>

              <button
                onClick={handleRunComparison}
                disabled={isComparing}
                className="flex items-center gap-2 px-5 py-2 text-xs font-black text-black bg-[#FFE600] hover:bg-[#FFE600]/80 border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] disabled:opacity-50 transition-all"
              >
                <Scale className="w-4 h-4 stroke-[2.5]" />
                <span>{isComparing ? 'Comparing...' : 'Run Comparison'}</span>
              </button>
            </div>
          </div>

          {compError && (
            <div className="p-3 bg-rose-50 border-2 border-rose-600 rounded-xl text-rose-900 text-xs font-bold flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{compError}</span>
            </div>
          )}

          {/* Comparison Output Results */}
          {comparisonResult && (
            <div className="space-y-4">
              {/* Summary Notes */}
              <div className="bg-white border-2 border-black rounded-xl p-4 shadow-[2px_2px_0px_0px_#000] space-y-1.5">
                <div className="text-xs font-black text-black uppercase flex items-center gap-1.5">
                  <Sparkles className="w-4 h-4 text-black" />
                  <span>Comparison Intelligence Summary</span>
                </div>
                {comparisonResult.comparison_notes.map((note, idx) => (
                  <p key={idx} className="text-xs text-black/80 font-medium">
                    • {note}
                  </p>
                ))}
              </div>

              {/* Comparison Table */}
              <div className="bg-white border-2 border-black rounded-2xl shadow-[4px_4px_0px_0px_#000] overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="bg-[#F8F5EE] border-b-2 border-black text-[11px] font-black uppercase tracking-wider text-black">
                        <th className="py-3 px-4">Vendor & Service</th>
                        <th className="py-3 px-4">Base Rate</th>
                        <th className="py-3 px-4">Tax / GST</th>
                        <th className="py-3 px-4">Total Calculated Cost</th>
                        <th className="py-3 px-4">Evidence Grade</th>
                        <th className="py-3 px-4">Availability</th>
                        <th className="py-3 px-4">Scope / Inclusions</th>
                        <th className="py-3 px-4 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y-2 divide-black/10 text-xs font-bold">
                      {comparisonResult.items.map((item) => {
                        const isBestValue = item.price_record_id === comparisonResult.best_value_price_record_id;

                        return (
                          <tr
                            key={item.price_record_id}
                            className={`hover:bg-slate-50 transition-colors ${
                              isBestValue ? 'bg-[#FFE600]/15' : ''
                            } ${!item.is_compatible ? 'bg-slate-100/60 opacity-80' : ''}`}
                          >
                            {/* Vendor & Service */}
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2">
                                <div>
                                  <div className="flex items-center gap-1.5">
                                    <span className="font-black text-black">{item.vendor_name}</span>
                                    {isBestValue && (
                                      <span className="text-[9px] px-1.5 py-0.2 rounded bg-[#FFE600] text-black font-black uppercase border border-black shadow-[1px_1px_0px_0px_#000]">
                                        ⭐ Best Value
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-[11px] text-black/60 font-semibold">
                                    {item.service_name} • <span className="capitalize">{item.category}</span>
                                  </div>
                                  {item.location_notes && (
                                    <div className="text-[10px] text-black/50 font-medium">
                                      📍 {item.location_notes}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </td>

                            {/* Base Rate */}
                            <td className="py-3 px-4">
                              <div className="font-black text-black">
                                {formatInr(Number(item.base_amount))}
                              </div>
                              <div className="text-[10px] text-black/60 font-bold">
                                /{item.unit} ({item.price_type})
                              </div>
                            </td>

                            {/* Tax Info */}
                            <td className="py-3 px-4 text-[11px]">
                              {item.tax_status === 'unknown' ? (
                                <div className="space-y-0.5">
                                  <span className="inline-block text-amber-800 font-black bg-amber-50 px-1.5 py-0.5 rounded border border-amber-300 text-[10px]">
                                    Tax Unspecified ⚠️
                                  </span>
                                  <div className="text-[9px] text-black/50">Additional taxes may apply</div>
                                </div>
                              ) : item.tax_included ? (
                                <span className="text-emerald-700 font-bold">
                                  Tax Included ({item.tax_rate !== null && item.tax_rate !== undefined ? `${item.tax_rate}%` : 'Rate unspec.'})
                                </span>
                              ) : (
                                <span className="text-black/70 font-bold">
                                  +{item.tax_rate || 0}% statutory tax
                                </span>
                              )}
                            </td>

                            {/* Total Cost / Compatibility */}
                            <td className="py-3 px-4">
                              {item.is_compatible && item.total_cost !== null ? (
                                <div>
                                  <div className="font-black text-black text-sm">
                                    {formatInr(Number(item.total_cost))}
                                  </div>
                                  <div className="text-[10px] text-black/50">
                                    Base: {formatInr(Number(item.subtotal || 0))}
                                    {item.tax_amount !== null && item.tax_amount !== undefined
                                      ? ` • Tax: ${formatInr(Number(item.tax_amount))}`
                                      : ' • Tax: Unspecified'}
                                  </div>
                                </div>
                              ) : (
                                <div className="p-1.5 rounded bg-amber-50 border border-amber-300 text-[10px] text-amber-900 font-medium max-w-[200px]">
                                  ⚠️ {item.compatibility_reason || 'Incompatible units'}
                                </div>
                              )}
                            </td>

                            {/* Evidence Quality Grade */}
                            <td className="py-3 px-4">
                              <div className="space-y-1">
                                <ProvenancePill status={item.evidence_type} />
                                <div className="text-[10px] font-extrabold text-black/70">
                                  {item.evidence_grade}
                                </div>
                                {item.source_name && (
                                  <div className="text-[9px] text-black/50 truncate max-w-[150px]">
                                    Source: {item.source_name}
                                  </div>
                                )}
                              </div>
                            </td>

                            {/* Availability */}
                            <td className="py-3 px-4">
                              <AvailabilityPill
                                status={item.availability_status}
                                checkedAt={item.availability_checked_at}
                              />
                              {item.availability_status === 'unknown' && (
                                <div className="text-[9px] text-black/60 font-semibold mt-0.5">
                                  Direct inquiry needed
                                </div>
                              )}
                            </td>

                            {/* Scope / Inclusions */}
                            <td className="py-3 px-4 max-w-[200px]">
                              {item.inclusions ? (
                                <div className="text-[11px] text-black/80 font-medium line-clamp-2">
                                  <span className="font-bold">Inc:</span> {item.inclusions}
                                </div>
                              ) : (
                                <span className="text-[10px] text-black/40">Not specified</span>
                              )}
                              {item.exclusions && (
                                <div className="text-[10px] text-rose-700 font-medium line-clamp-1 mt-0.5">
                                  <span className="font-bold">Exc:</span> {item.exclusions}
                                </div>
                              )}
                            </td>

                            {/* Action: Add to Budget */}
                            <td className="py-3 px-4 text-right">
                              <button
                                onClick={() => handleAddToBudget(item, item.vendor_name)}
                                disabled={addingRecordId === item.price_record_id || !item.is_compatible}
                                className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-black text-black bg-[#4ADE80] hover:bg-[#22C55E] border-2 border-black rounded-xl shadow-[1.5px_1.5px_0px_0px_#000] disabled:opacity-40 transition-all shrink-0"
                                title="Add to active event budget with locked snapshot"
                              >
                                <Plus className="w-3.5 h-3.5 stroke-[3]" />
                                <span>{addingRecordId === item.price_record_id ? 'Adding...' : 'Add to Budget'}</span>
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* VENDOR DETAIL DRAWER / MODAL */}
      {detailVendor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="relative w-full max-w-3xl bg-[#FFFDF9] border-2 border-black rounded-2xl shadow-[6px_6px_0px_0px_#000] overflow-hidden max-h-[90vh] flex flex-col">
            {/* Drawer Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b-2 border-black bg-[#FFE600]">
              <div className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-black stroke-[2.5]" />
                <div>
                  <h3 className="text-base font-black text-black uppercase tracking-tight font-heading">
                    {detailVendor.business_name}
                  </h3>
                  <span className="text-[11px] font-bold text-black/70">
                    {detailVendor.vendor_type} • {detailVendor.city || 'India'}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setDetailVendor(null)}
                className="p-1 rounded-lg border-2 border-black bg-white hover:bg-slate-100 transition-all text-black shadow-[1.5px_1.5px_0px_0px_#000]"
              >
                <X className="w-4 h-4 stroke-[3]" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Profile Card */}
              <div className="p-4 bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-black uppercase text-black">Contact & Profile Credentials</span>
                  <button
                    onClick={() => handleToggleActive(detailVendor)}
                    className={`text-[10px] px-2.5 py-0.5 rounded font-black uppercase border border-black ${
                      detailVendor.is_active ? 'bg-[#86EFAC] text-black' : 'bg-[#FDA4AF] text-black'
                    }`}
                  >
                    Listing: {detailVendor.is_active ? 'Active' : 'Inactive (Hidden)'}
                  </button>
                </div>
                {detailVendor.description && (
                  <p className="text-xs text-black/80 font-medium">{detailVendor.description}</p>
                )}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs font-bold pt-2 border-t border-black/10">
                  {detailVendor.contact_person && (
                    <div>👤 Rep: {detailVendor.contact_person}</div>
                  )}
                  {detailVendor.email && (
                    <div>✉️ {detailVendor.email}</div>
                  )}
                  {detailVendor.phone && (
                    <div>📞 {detailVendor.phone}</div>
                  )}
                  {detailVendor.website_url && (
                    <div className="col-span-3">
                      🌐 <a href={detailVendor.website_url} target="_blank" rel="noreferrer" className="text-blue-700 underline">
                        {detailVendor.website_url}
                      </a>
                    </div>
                  )}
                </div>
              </div>

              {/* Catalog Services Offered */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-black uppercase tracking-wider text-black flex items-center gap-1.5">
                    <span>📦 Catalog Service Offerings ({detailVendor.services?.length || 0})</span>
                  </h4>
                  <button
                    onClick={() => {
                      setSelectedVendorForPrice(detailVendor);
                      setIsAddPriceOpen(true);
                    }}
                    className="flex items-center gap-1 text-[11px] font-black text-black bg-[#4ADE80] px-2.5 py-1 rounded-lg border border-black shadow-[1px_1px_0px_0px_#000]"
                  >
                    <Plus className="w-3 h-3" />
                    <span>Record Rate for Service</span>
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {detailVendor.services && detailVendor.services.length > 0 ? (
                    detailVendor.services.map((svc) => (
                      <div
                        key={svc.id}
                        className="p-3 bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-black text-xs text-black">{svc.service_name}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 border border-black/30 font-bold uppercase">
                            {svc.category}
                          </span>
                        </div>
                        {svc.description && (
                          <p className="text-[11px] text-black/70 font-medium">{svc.description}</p>
                        )}
                        <div className="text-[10px] text-black/60 font-semibold pt-1">
                          Unit: {svc.unit || 'per item'} • Capacity: {svc.maximum_capacity || 'N/A'}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="col-span-2 text-center p-4 bg-slate-50 border border-black/20 rounded-xl text-xs text-black/60 font-bold">
                      No services currently defined for this vendor.
                    </div>
                  )}
                </div>
              </div>

              {/* Historical Price Observations & Attached Evidence */}
              <div className="space-y-3">
                <h4 className="text-xs font-black uppercase tracking-wider text-black flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-black" />
                  <span>Verified Price Observations & Evidence Trail ({detailHistory.length})</span>
                </h4>

                {isLoadingHistory ? (
                  <div className="p-6 text-center text-xs font-bold text-black/70">
                    Loading historical rate observations...
                  </div>
                ) : detailHistory.length === 0 ? (
                  <div className="p-6 text-center bg-white border-2 border-black rounded-xl text-xs text-black/60 font-bold">
                    No historical price observations recorded yet for this vendor.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {detailHistory.map((rec) => {
                      const latestEv = rec.evidence_records?.[0];
                      const effectiveStatus = latestEv?.evidence_type || 'unknown';

                      return (
                        <div
                          key={rec.id}
                          className="p-4 bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] space-y-2.5"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-black text-sm text-black">
                                  {formatInr(Number(rec.amount))} / {rec.unit}
                                </span>
                                <ProvenancePill status={effectiveStatus as any} />
                                <AvailabilityPill
                                  status={rec.availability_status}
                                  checkedAt={rec.availability_checked_at}
                                />
                              </div>
                              <div className="text-[10px] text-black/60 font-bold mt-0.5">
                                Pricing: {rec.price_type} •{' '}
                                {rec.tax_included ? `Tax Included (${rec.tax_rate || 0}%)` : `+${rec.tax_rate || 0}% Tax`} •{' '}
                                Recorded on {new Date(rec.created_at).toLocaleDateString()}
                              </div>
                            </div>

                            <button
                              onClick={() => handleAddToBudget(rec, detailVendor.business_name)}
                              disabled={addingRecordId === rec.id}
                              className="px-3 py-1.5 text-xs font-black text-black bg-[#4ADE80] hover:bg-[#22C55E] border-2 border-black rounded-xl shadow-[1.5px_1.5px_0px_0px_#000] transition-all disabled:opacity-50"
                            >
                              Add to Budget
                            </button>
                          </div>

                          {/* Evidence Scope & Provenance */}
                          {latestEv && (
                            <div className="p-3 bg-[#F8F5EE] border border-black/30 rounded-lg text-xs space-y-1">
                              <div className="font-black text-black text-[11px] flex items-center justify-between">
                                <span>📄 Evidence Source: {latestEv.source_name || 'Direct Quotation'}</span>
                                {latestEv.quoted_by && (
                                  <span className="text-black/60 font-semibold">Rep: {latestEv.quoted_by}</span>
                                )}
                              </div>
                              {latestEv.source_url && (
                                <div className="text-[10px]">
                                  <a
                                    href={latestEv.source_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-blue-700 underline font-semibold flex items-center gap-1"
                                  >
                                    <span>{latestEv.source_url}</span>
                                    <ExternalLink className="w-2.5 h-2.5" />
                                  </a>
                                </div>
                              )}
                              {latestEv.inclusions && (
                                <div className="text-[11px] text-black/80 font-medium pt-1">
                                  <span className="font-black">Inclusions:</span> {latestEv.inclusions}
                                </div>
                              )}
                              {latestEv.exclusions && (
                                <div className="text-[11px] text-rose-800 font-medium">
                                  <span className="font-black">Exclusions:</span> {latestEv.exclusions}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Drawer Footer */}
            <div className="px-6 py-3 border-t-2 border-black bg-slate-50 flex justify-end">
              <button
                onClick={() => setDetailVendor(null)}
                className="px-4 py-2 text-xs font-black bg-white hover:bg-slate-100 border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
              >
                Close Profile
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add / Edit Vendor Modal */}
      <AddVendorModal
        isOpen={isAddVendorOpen}
        onClose={() => {
          setIsAddVendorOpen(false);
          setEditingVendor(null);
        }}
        onVendorSaved={(saved) => {
          loadVendors();
          onShowToast(`Vendor "${saved.business_name}" saved successfully!`);
        }}
        initialVendor={editingVendor}
      />

      {/* Add Price Record Modal */}
      <AddPriceRecordModal
        isOpen={isAddPriceOpen}
        onClose={() => {
          setIsAddPriceOpen(false);
          setSelectedVendorForPrice(null);
        }}
        onPriceRecorded={(record) => {
          loadVendors();
          onShowToast(`Price observation of ${formatInr(Number(record.amount))} recorded with evidence!`);
          if (detailVendor && detailVendor.id === record.vendor_id) {
            handleOpenVendorDetail(detailVendor);
          }
        }}
        preselectedVendor={selectedVendorForPrice}
      />
    </div>
  );
};

