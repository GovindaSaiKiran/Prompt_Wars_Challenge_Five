import React, { useState, useEffect } from 'react';
import {
  AvailabilityStatus,
  EvidenceType,
  PriceType,
  Vendor,
  VendorPriceRecord,
  VendorPriceRecordCreate,
  VendorService,
} from '../types/vendor';
import { createPriceRecord, createVendorService, fetchVendors } from '../services/vendorApi';
import { X, Tag, ShieldCheck, CheckCircle2, AlertCircle, Calendar, Plus } from 'lucide-react';

interface AddPriceRecordModalProps {
  isOpen: boolean;
  onClose: () => void;
  onPriceRecorded: (record: VendorPriceRecord) => void;
  preselectedVendor?: Vendor | null;
  preselectedService?: VendorService | null;
}

export const AddPriceRecordModal: React.FC<AddPriceRecordModalProps> = ({
  isOpen,
  onClose,
  onPriceRecorded,
  preselectedVendor,
  preselectedService,
}) => {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [selectedVendorId, setSelectedVendorId] = useState<string>(preselectedVendor?.id || '');
  const [availableServices, setAvailableServices] = useState<VendorService[]>(
    preselectedVendor?.services || []
  );
  const [selectedServiceId, setSelectedServiceId] = useState<string>(preselectedService?.id || '');

  // Quick New Service inline toggle
  const [showNewService, setShowNewService] = useState(false);
  const [newServiceName, setNewServiceName] = useState('');
  const [newServiceCategory, setNewServiceCategory] = useState('catering');
  const [newServiceUnit, setNewServiceUnit] = useState('per_plate');

  // Price record fields
  const [amount, setAmount] = useState<string>('1500');
  const [currency, setCurrency] = useState<string>('INR');
  const [unit, setUnit] = useState<string>('per_plate');
  const [priceType, setPriceType] = useState<PriceType>('fixed');
  const [taxIncluded, setTaxIncluded] = useState<boolean>(false);
  const [taxRate, setTaxRate] = useState<string>('5.00');
  const [validUntil, setValidUntil] = useState<string>('');
  const [availabilityStatus, setAvailabilityStatus] = useState<AvailabilityStatus>('available');

  // Evidence fields
  const [evidenceType, setEvidenceType] = useState<EvidenceType>('vendor_quoted');
  const [sourceName, setSourceName] = useState<string>('Direct Vendor Quotation');
  const [sourceUrl, setSourceUrl] = useState<string>('');
  const [quotedBy, setQuotedBy] = useState<string>('');
  const [inclusions, setInclusions] = useState<string>('');
  const [exclusions, setExclusions] = useState<string>('');
  const [evidenceNotes, setEvidenceNotes] = useState<string>('');

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load vendors if not provided
  useEffect(() => {
    if (isOpen) {
      if (preselectedVendor) {
        setSelectedVendorId(preselectedVendor.id);
        setAvailableServices(preselectedVendor.services || []);
        if (preselectedService) {
          setSelectedServiceId(preselectedService.id);
          if (preselectedService.unit) setUnit(preselectedService.unit);
        }
      } else {
        fetchVendors({ limit: 50, is_active: true })
          .then((res) => {
            setVendors(res.items);
            if (res.items.length > 0 && !selectedVendorId) {
              setSelectedVendorId(res.items[0].id);
              setAvailableServices(res.items[0].services || []);
              if (res.items[0].services && res.items[0].services.length > 0) {
                setSelectedServiceId(res.items[0].services[0].id);
                if (res.items[0].services[0].unit) setUnit(res.items[0].services[0].unit);
              }
            }
          })
          .catch((err) => console.error('Failed to load vendors for modal:', err));
      }
    }
  }, [isOpen, preselectedVendor, preselectedService]);

  const handleVendorChange = (vid: string) => {
    setSelectedVendorId(vid);
    const v = vendors.find((vend) => vend.id === vid) || (preselectedVendor?.id === vid ? preselectedVendor : null);
    const svcs = v?.services || [];
    setAvailableServices(svcs);
    if (svcs.length > 0) {
      setSelectedServiceId(svcs[0].id);
      if (svcs[0].unit) setUnit(svcs[0].unit);
    } else {
      setSelectedServiceId('');
      setShowNewService(true);
    }
  };

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    let activeServiceId = selectedServiceId;

    if (!selectedVendorId) {
      setError('Please select a vendor.');
      return;
    }

    try {
      setIsSubmitting(true);

      // If user is creating a new service inline
      if (showNewService || !activeServiceId) {
        if (!newServiceName.trim()) {
          setError('Please provide a service name.');
          setIsSubmitting(false);
          return;
        }
        const createdSvc = await createVendorService(selectedVendorId, {
          service_name: newServiceName.trim(),
          category: newServiceCategory,
          unit: newServiceUnit,
          is_active: true,
        });
        activeServiceId = createdSvc.id;
      }

      const parsedAmount = parseFloat(amount);
      if (isNaN(parsedAmount) || parsedAmount <= 0) {
        setError('Price amount must be a positive number.');
        setIsSubmitting(false);
        return;
      }

      const parsedTaxRate = taxRate ? parseFloat(taxRate) : 0;

      const payload: VendorPriceRecordCreate = {
        vendor_id: selectedVendorId,
        vendor_service_id: activeServiceId,
        amount: parsedAmount,
        currency: currency.trim().toUpperCase() || 'INR',
        unit: unit.trim() || 'item',
        price_type: priceType,
        tax_included: taxIncluded,
        tax_rate: parsedTaxRate,
        valid_until: validUntil ? validUntil : undefined,
        availability_status: availabilityStatus,
        initial_evidence: {
          evidence_type: evidenceType,
          source_name: sourceName.trim() || undefined,
          source_url: sourceUrl.trim() || undefined,
          quoted_by: quotedBy.trim() || undefined,
          inclusions: inclusions.trim() || undefined,
          exclusions: exclusions.trim() || undefined,
          notes: evidenceNotes.trim() || undefined,
        },
      };

      const result = await createPriceRecord(payload);
      onPriceRecorded(result);
      onClose();
    } catch (err: any) {
      setError(err?.message || 'Failed to record price observation.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="relative w-full max-w-2xl bg-[#FFFDF9] border-2 border-black rounded-2xl shadow-[6px_6px_0px_0px_#000] overflow-hidden max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b-2 border-black bg-[#4ADE80]">
          <div className="flex items-center gap-2">
            <Tag className="w-5 h-5 text-black stroke-[2.5]" />
            <h3 className="text-base font-black text-black uppercase tracking-tight font-heading">
              Record Price Observation & Evidence
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg border-2 border-black bg-white hover:bg-slate-100 transition-all text-black shadow-[1.5px_1.5px_0px_0px_#000]"
          >
            <X className="w-4 h-4 stroke-[3]" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-4">
          {error && (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-rose-50 border-2 border-rose-600 text-rose-900 text-xs font-bold">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-600" />
              <span>{error}</span>
            </div>
          )}

          {/* Vendor and Service Selection */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-black uppercase tracking-wider text-black">
                Vendor *
              </label>
              {preselectedVendor ? (
                <div className="px-3 py-2 text-xs font-black bg-slate-100 border-2 border-black rounded-xl text-black">
                  {preselectedVendor.business_name} ({preselectedVendor.city || 'India'})
                </div>
              ) : (
                <select
                  value={selectedVendorId}
                  onChange={(e) => handleVendorChange(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
                >
                  <option value="">-- Choose Vendor --</option>
                  {vendors.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.business_name} ({v.vendor_type} - {v.city || 'India'})
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="text-xs font-black uppercase tracking-wider text-black">
                  Service Offering *
                </label>
                <button
                  type="button"
                  onClick={() => setShowNewService(!showNewService)}
                  className="text-[10px] font-black underline text-black/70 hover:text-black flex items-center gap-0.5"
                >
                  <Plus className="w-2.5 h-2.5" />
                  {showNewService ? 'Pick existing' : 'Add new service'}
                </button>
              </div>

              {!showNewService && availableServices.length > 0 ? (
                <select
                  value={selectedServiceId}
                  onChange={(e) => {
                    setSelectedServiceId(e.target.value);
                    const s = availableServices.find((svc) => svc.id === e.target.value);
                    if (s?.unit) setUnit(s.unit);
                  }}
                  required
                  className="w-full px-3 py-2 text-xs font-bold bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000]"
                >
                  {availableServices.map((svc) => (
                    <option key={svc.id} value={svc.id}>
                      {svc.service_name} ({svc.category} • {svc.unit || 'custom'})
                    </option>
                  ))}
                </select>
              ) : (
                <div className="p-3 bg-amber-50 border-2 border-black rounded-xl space-y-2">
                  <div className="text-[11px] font-black text-black">Define Service Offering:</div>
                  <input
                    type="text"
                    value={newServiceName}
                    onChange={(e) => setNewServiceName(e.target.value)}
                    placeholder="e.g. Deluxe Dinner Buffet"
                    className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border border-black rounded-lg"
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <select
                      value={newServiceCategory}
                      onChange={(e) => setNewServiceCategory(e.target.value)}
                      className="px-2 py-1 text-xs font-bold bg-white border border-black rounded-lg"
                    >
                      <option value="catering">Catering</option>
                      <option value="venue">Venue</option>
                      <option value="decoration">Decoration</option>
                      <option value="photography">Photography</option>
                      <option value="entertainment">Entertainment</option>
                      <option value="equipment">Equipment / AV</option>
                      <option value="transport">Transport</option>
                      <option value="other">Other</option>
                    </select>
                    <select
                      value={newServiceUnit}
                      onChange={(e) => {
                        setNewServiceUnit(e.target.value);
                        setUnit(e.target.value);
                      }}
                      className="px-2 py-1 text-xs font-bold bg-white border border-black rounded-lg"
                    >
                      <option value="per_plate">per_plate</option>
                      <option value="per_person">per_person</option>
                      <option value="per_event">per_event</option>
                      <option value="per_hour">per_hour</option>
                      <option value="per_day">per_day</option>
                      <option value="item">item</option>
                    </select>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Pricing Details */}
          <div className="p-4 bg-white border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] space-y-3">
            <div className="text-xs font-black uppercase tracking-wider text-black flex items-center gap-1.5 border-b pb-2">
              <span>💰 Pricing Structure</span>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-black uppercase text-black">Amount *</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  required
                  className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-black uppercase text-black">Currency</label>
                <select
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
                >
                  <option value="INR">INR (₹)</option>
                  <option value="USD">USD ($)</option>
                  <option value="EUR">EUR (€)</option>
                  <option value="GBP">GBP (£)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-black uppercase text-black">Billing Unit *</label>
                <input
                  type="text"
                  value={unit}
                  onChange={(e) => setUnit(e.target.value)}
                  placeholder="e.g. per_plate, per_day"
                  required
                  className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-black uppercase text-black">Pricing Model</label>
                <select
                  value={priceType}
                  onChange={(e) => setPriceType(e.target.value as PriceType)}
                  className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
                >
                  <option value="fixed">Fixed Rate</option>
                  <option value="package">Package Deal</option>
                  <option value="per_unit">Per Unit</option>
                  <option value="starting_from">Starting From</option>
                  <option value="range">Range Benchmark</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
              <div className="flex items-center gap-2 pt-2">
                <input
                  type="checkbox"
                  id="taxIncCheckbox"
                  checked={taxIncluded}
                  onChange={(e) => setTaxIncluded(e.target.checked)}
                  className="w-4 h-4 rounded border-2 border-black accent-[#FFE600]"
                />
                <label htmlFor="taxIncCheckbox" className="text-xs font-black text-black cursor-pointer">
                  Statutory Tax Included
                </label>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-black uppercase text-black">Tax Rate (%)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={taxRate}
                  onChange={(e) => setTaxRate(e.target.value)}
                  placeholder="e.g. 5.00 or 18.00"
                  className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-black uppercase text-black">Validity Date</label>
                <input
                  type="date"
                  value={validUntil}
                  onChange={(e) => setValidUntil(e.target.value)}
                  className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
                />
              </div>
            </div>

            <div className="space-y-1 pt-2">
              <label className="text-[11px] font-black uppercase text-black">
                Availability Status (Independent from Price Evidence)
              </label>
              <select
                value={availabilityStatus}
                onChange={(e) => setAvailabilityStatus(e.target.value as AvailabilityStatus)}
                className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
              >
                <option value="available">🟢 Available for Bookings</option>
                <option value="limited">🟡 Limited Availability</option>
                <option value="unavailable">🔴 Fully Booked / Unavailable</option>
                <option value="unknown">⚪ Unknown / Unchecked</option>
              </select>
            </div>
          </div>

          {/* Verification Evidence */}
          <div className="p-4 bg-[#F8F5EE] border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] space-y-3">
            <div className="text-xs font-black uppercase tracking-wider text-black flex items-center gap-1.5 border-b border-black/20 pb-2">
              <ShieldCheck className="w-4 h-4 text-black" />
              <span>Verification Provenance & Evidence</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-black uppercase text-black">
                  Evidence Classification *
                </label>
                <select
                  value={evidenceType}
                  onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}
                  className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
                >
                  <option value="vendor_confirmed">Vendor Confirmed (Signed Contract / Verified Quote)</option>
                  <option value="vendor_quoted">Vendor Quoted (Direct Quote from Vendor Representative)</option>
                  <option value="published">Published (Public Website / Rate Card)</option>
                  <option value="estimated">Estimated (Market Benchmark / Auditor Estimate)</option>
                  <option value="expired">Expired (Historical Past Rate)</option>
                  <option value="unknown">Unknown (Unverified Crowdsourced Rate)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-black uppercase text-black">
                  Source / Document Name *
                </label>
                <input
                  type="text"
                  value={sourceName}
                  onChange={(e) => setSourceName(e.target.value)}
                  placeholder="e.g. Email Quote Ref #2026-B, Rate Card"
                  className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-black uppercase text-black">Source URL (if public)</label>
                <input
                  type="url"
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  placeholder="https://vendor.example.com/packages"
                  className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-black uppercase text-black">Quoted By (Contact Person)</label>
                <input
                  type="text"
                  value={quotedBy}
                  onChange={(e) => setQuotedBy(e.target.value)}
                  placeholder="e.g. Suresh Patel, Head of Events"
                  className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[11px] font-black uppercase text-black">Inclusions</label>
                <textarea
                  rows={2}
                  value={inclusions}
                  onChange={(e) => setInclusions(e.target.value)}
                  placeholder="Covered services, staff, equipment"
                  className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-black uppercase text-black">Exclusions / Caveats</label>
                <textarea
                  rows={2}
                  value={exclusions}
                  onChange={(e) => setExclusions(e.target.value)}
                  placeholder="Extra charges, transport, power backup"
                  className="w-full px-2.5 py-1.5 text-xs font-bold bg-white border-2 border-black rounded-lg"
                />
              </div>
            </div>
          </div>

          {/* Footer Buttons */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t-2 border-black">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-black text-black bg-white hover:bg-slate-100 border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center gap-1.5 px-5 py-2 text-xs font-black text-black bg-[#4ADE80] hover:bg-[#22C55E] border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] transition-all disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4 stroke-[2.5]" />
              <span>{isSubmitting ? 'Recording...' : 'Save Price Observation'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

