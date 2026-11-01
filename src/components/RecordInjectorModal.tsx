import React, { useState, useEffect } from 'react';
import {
  VendorPriceRecord,
  ServiceCategory,
  PricingUnit,
  EvidenceStatus,
  EventBrief,
} from '../types/intelligence';
import { SAMPLE_VENDOR_BATCH } from '../utils/samplePayloads';
import { calculateVendorCost, formatInr, CATEGORY_LABELS } from '../utils/ledgerMath';
import { X, Sparkles, PlusCircle } from 'lucide-react';

interface RecordInjectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onInjectRecord: (records: VendorPriceRecord[]) => void;
  brief: EventBrief | null;
}

export const RecordInjectorModal: React.FC<RecordInjectorModalProps> = ({
  isOpen,
  onClose,
  onInjectRecord,
  brief,
}) => {
  const [activeTab, setActiveTab] = useState<'form' | 'json'>('form');

  // Simple, clean form state
  const [formData, setFormData] = useState<Partial<VendorPriceRecord>>({
    vendorName: '',
    category: 'catering',
    basePrice: 1500,
    unit: 'per_person',
    minUnits: 1,
    gstPct: 5,
    additionalCharges: 0,
    status: 'vendor_quoted',
    sourceUrl: '',
    verbatimSnippet: '',
    inclusions: [],
    exclusions: [],
    isSelectedForBudget: true,
  });

  const [inclusionsText, setInclusionsText] = useState('3-Course Buffet, Service Staff, Welcome Drinks');
  const [notesText, setNotesText] = useState('');
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});

  // JSON Tab State
  const [jsonText, setJsonText] = useState<string>('');
  const [jsonError, setJsonError] = useState<string | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Real-time calculation preview
  const previewCost = brief && formData.basePrice
    ? calculateVendorCost(
        {
          ...(formData as VendorPriceRecord),
          id: 'temp-preview',
          unit: formData.unit || 'per_person',
          basePrice: Number(formData.basePrice) || 0,
          gstPct: Number(formData.gstPct) || 0,
          additionalCharges: Number(formData.additionalCharges) || 0,
          inclusions: inclusionsText.split(',').map((s) => s.trim()).filter(Boolean),
          exclusions: [],
        },
        brief
      )
    : null;

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const errs: Record<string, string> = {};
    if (!formData.vendorName?.trim()) errs.vendorName = 'Please enter a vendor name';
    if (!formData.basePrice || Number(formData.basePrice) <= 0)
      errs.basePrice = 'Price must be greater than 0';

    if (Object.keys(errs).length > 0) {
      setFormErrors(errs);
      return;
    }

    const newRecord: VendorPriceRecord = {
      id: `ven-${Date.now()}`,
      vendorName: formData.vendorName!.trim(),
      category: formData.category || 'catering',
      basePrice: Number(formData.basePrice),
      unit: formData.unit || 'per_person',
      minUnits: Number(formData.minUnits) || 1,
      gstPct: Number(formData.gstPct) || 0,
      additionalCharges: Number(formData.additionalCharges) || 0,
      status: formData.status || 'vendor_quoted',
      sourceUrl: formData.sourceUrl || '',
      verbatimSnippet: notesText.trim() || 'Custom vendor quote added manually by user.',
      inclusions: inclusionsText
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      exclusions: [],
      isSelectedForBudget: true,
      confidenceScore: 0.95,
      timestamp: new Date().toISOString(),
    };

    onInjectRecord([newRecord]);
    onClose();

    // Reset form
    setFormData({
      vendorName: '',
      category: 'catering',
      basePrice: 1500,
      unit: 'per_person',
      minUnits: 1,
      gstPct: 5,
      additionalCharges: 0,
      status: 'vendor_quoted',
      sourceUrl: '',
      verbatimSnippet: '',
      inclusions: [],
      exclusions: [],
      isSelectedForBudget: true,
    });
    setInclusionsText('');
    setNotesText('');
    setFormErrors({});
  };

  const handleJsonSubmit = () => {
    setJsonError(null);
    try {
      const parsed = JSON.parse(jsonText);
      const items = Array.isArray(parsed) ? parsed : [parsed];
      if (items.length === 0) {
        setJsonError('No records found in JSON.');
        return;
      }
      onInjectRecord(items);
      onClose();
    } catch (err: any) {
      setJsonError(`Invalid JSON: ${err.message}`);
    }
  };

  const handleLoadSampleJson = () => {
    setJsonText(JSON.stringify(SAMPLE_VENDOR_BATCH, null, 2));
    setJsonError(null);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="w-full max-w-xl bg-white border-3 border-black rounded-2xl shadow-[8px_8px_0px_0px_#000] overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="p-4 sm:p-5 bg-[#FFE600] border-b-3 border-black flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-white border-2 border-black shadow-[2px_2px_0px_0px_#000] flex items-center justify-center text-lg">
              🎪
            </div>
            <div>
              <h2 className="text-base font-black text-black tracking-tight">
                Add Vendor Quote
              </h2>
              <p className="text-xs font-semibold text-black/80">
                Log direct vendor pricing into your event budget ledger
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="text-black bg-white hover:bg-black hover:text-white p-1.5 rounded-lg border-2 border-black shadow-[2px_2px_0px_0px_#000] transition-transform active:translate-x-0.5 active:translate-y-0.5"
            title="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Switcher */}
        <div className="px-5 pt-3 pb-3 bg-[#F8F5EE] border-b-2 border-black flex items-center gap-3">
          <button
            onClick={() => setActiveTab('form')}
            className={`px-3.5 py-1.5 text-xs font-black rounded-lg border-2 border-black transition-all ${
              activeTab === 'form'
                ? 'bg-[#FF6B8B] text-black shadow-[2px_2px_0px_0px_#000]'
                : 'bg-white text-black/70 hover:text-black hover:bg-white shadow-[1px_1px_0px_0px_#000]'
            }`}
          >
            📝 Simple Form
          </button>

          <button
            onClick={() => setActiveTab('json')}
            className={`px-3.5 py-1.5 text-xs font-black rounded-lg border-2 border-black transition-all ${
              activeTab === 'json'
                ? 'bg-[#38BDF8] text-black shadow-[2px_2px_0px_0px_#000]'
                : 'bg-white text-black/70 hover:text-black hover:bg-white shadow-[1px_1px_0px_0px_#000]'
            }`}
          >
            💻 Import JSON
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-5 bg-[#FFFDF9]">
          {activeTab === 'form' ? (
            <form onSubmit={handleFormSubmit} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Vendor Name */}
                <div className="sm:col-span-2">
                  <label htmlFor="modal-vendor-name" className="block text-xs font-black text-black uppercase tracking-wider mb-1">
                    Vendor / Company Name
                  </label>
                  <input
                    id="modal-vendor-name"
                    type="text"
                    value={formData.vendorName}
                    onChange={(e) =>
                      setFormData({ ...formData, vendorName: e.target.value })
                    }
                    placeholder="e.g. Royal Orchid Grand Palace"
                    className={`w-full bg-[#F8F5EE] border-2 border-black rounded-lg px-3 py-2 text-xs font-bold text-black placeholder-black/40 focus:outline-none focus:bg-white shadow-[2px_2px_0px_0px_#000] transition-colors ${
                      formErrors.vendorName ? 'border-red-600 bg-red-50' : 'border-black'
                    }`}
                  />
                  {formErrors.vendorName && (
                    <p className="text-[11px] font-black text-red-600 mt-1">
                      ⚠️ {formErrors.vendorName}
                    </p>
                  )}
                </div>

                {/* Service Category */}
                <div>
                  <label htmlFor="modal-service-category" className="block text-xs font-black text-black uppercase tracking-wider mb-1">
                    Service Category
                  </label>
                  <select
                    id="modal-service-category"
                    value={formData.category}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        category: e.target.value as ServiceCategory,
                      })
                    }
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-lg px-3 py-2 text-xs font-bold text-black focus:outline-none focus:bg-white shadow-[2px_2px_0px_0px_#000]"
                  >
                    {(Object.keys(CATEGORY_LABELS) as ServiceCategory[]).map(
                      (cat) => (
                        <option key={cat} value={cat}>
                          {CATEGORY_LABELS[cat]}
                        </option>
                      )
                    )}
                  </select>
                </div>

                {/* Pricing Type */}
                <div>
                  <label htmlFor="modal-pricing-unit" className="block text-xs font-black text-black uppercase tracking-wider mb-1">
                    Billing Structure
                  </label>
                  <select
                    id="modal-pricing-unit"
                    value={formData.unit}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        unit: e.target.value as PricingUnit,
                      })
                    }
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-lg px-3 py-2 text-xs font-bold text-black focus:outline-none focus:bg-white shadow-[2px_2px_0px_0px_#000]"
                  >
                    <option value="per_person">Per Guest / Plate</option>
                    <option value="per_day">Per Day (Venue / Stage)</option>
                    <option value="per_hour">Per Hour (DJ / Artists)</option>
                    <option value="fixed">Fixed Lump Sum Contract</option>
                  </select>
                </div>

                {/* Rate / Price */}
                <div>
                  <label htmlFor="modal-base-price" className="block text-xs font-black text-black uppercase tracking-wider mb-1">
                    Rate / Base Price (₹)
                  </label>
                  <input
                    id="modal-base-price"
                    type="number"
                    min="0"
                    value={formData.basePrice || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        basePrice: parseFloat(e.target.value) || 0,
                      })
                    }
                    placeholder="e.g. 1500"
                    className={`w-full bg-[#F8F5EE] border-2 border-black rounded-lg px-3 py-2 text-xs font-bold text-black placeholder-black/40 focus:outline-none focus:bg-white shadow-[2px_2px_0px_0px_#000] transition-colors ${
                      formErrors.basePrice ? 'border-red-600 bg-red-50' : 'border-black'
                    }`}
                  />
                  {formErrors.basePrice && (
                    <p className="text-[11px] font-black text-red-600 mt-1">
                      ⚠️ {formErrors.basePrice}
                    </p>
                  )}
                </div>

                {/* GST Rate */}
                <div>
                  <label htmlFor="modal-gst-pct" className="block text-xs font-black text-black uppercase tracking-wider mb-1">
                    GST Tax Slab
                  </label>
                  <select
                    id="modal-gst-pct"
                    value={formData.gstPct}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        gstPct: parseInt(e.target.value, 10) || 0,
                      })
                    }
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-lg px-3 py-2 text-xs font-bold text-black focus:outline-none focus:bg-white shadow-[2px_2px_0px_0px_#000]"
                  >
                    <option value={5}>5% (Food, Catering, Buffet)</option>
                    <option value={18}>18% (Venue, Event Mgmt, AV)</option>
                    <option value={12}>12% (Logistics & Transport)</option>
                    <option value={0}>0% (Tax Exempt / Unregistered)</option>
                  </select>
                </div>

                {/* Additional Charges */}
                <div>
                  <label htmlFor="modal-additional-charges" className="block text-xs font-black text-black uppercase tracking-wider mb-1">
                    Extra Setup / Security (₹)
                  </label>
                  <input
                    id="modal-additional-charges"
                    type="number"
                    min="0"
                    value={formData.additionalCharges || ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        additionalCharges: parseFloat(e.target.value) || 0,
                      })
                    }
                    placeholder="e.g. 15000 (optional)"
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-lg px-3 py-2 text-xs font-bold text-black placeholder-black/40 focus:outline-none focus:bg-white shadow-[2px_2px_0px_0px_#000]"
                  />
                </div>

                {/* Quote Status */}
                <div>
                  <label htmlFor="modal-status" className="block text-xs font-black text-black uppercase tracking-wider mb-1">
                    Verification Status
                  </label>
                  <select
                    id="modal-status"
                    value={formData.status}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        status: e.target.value as EvidenceStatus,
                      })
                    }
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-lg px-3 py-2 text-xs font-bold text-black focus:outline-none focus:bg-white shadow-[2px_2px_0px_0px_#000]"
                  >
                    <option value="vendor_confirmed">Confirmed (Contract Signed)</option>
                    <option value="vendor_quoted">Direct Quote (Official Rate Card)</option>
                    <option value="published">Published Online Rate</option>
                    <option value="estimated">Rough Estimate / Benchmark</option>
                  </select>
                </div>

                {/* Inclusions */}
                <div className="sm:col-span-2">
                  <label htmlFor="modal-inclusions" className="block text-xs font-black text-black uppercase tracking-wider mb-1">
                    Inclusions (Comma Separated)
                  </label>
                  <input
                    id="modal-inclusions"
                    type="text"
                    value={inclusionsText}
                    onChange={(e) => setInclusionsText(e.target.value)}
                    placeholder="e.g. Buffet, 4 Staff, Welcome Drink, Cleanup"
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-lg px-3 py-2 text-xs font-bold text-black placeholder-black/40 focus:outline-none focus:bg-white shadow-[2px_2px_0px_0px_#000]"
                  />
                </div>

                {/* Notes or link */}
                <div className="sm:col-span-2">
                  <label htmlFor="modal-notes" className="block text-xs font-black text-black uppercase tracking-wider mb-1">
                    Notes or Contact Details (Optional)
                  </label>
                  <input
                    id="modal-notes"
                    type="text"
                    value={notesText}
                    onChange={(e) => setNotesText(e.target.value)}
                    placeholder="e.g. Quoted by Manager Rajesh on WhatsApp +91 98450 12345"
                    className="w-full bg-[#F8F5EE] border-2 border-black rounded-lg px-3 py-2 text-xs font-bold text-black placeholder-black/40 focus:outline-none focus:bg-white shadow-[2px_2px_0px_0px_#000]"
                  />
                </div>
              </div>

              {/* Real-time Calculated Cost Preview */}
              {previewCost && brief && (
                <div className="mt-4 p-3.5 rounded-xl bg-[#86EFAC] border-2 border-black shadow-[3px_3px_0px_0px_#000] flex items-center justify-between text-xs">
                  <div>
                    <div className="font-black text-black flex items-center gap-1.5">
                      <span>⚡ Cost Calculation ({previewCost.unitQuantity} units):</span>
                    </div>
                    <div className="text-black/80 font-bold text-[11px] mt-0.5">
                      Base: {formatInr(previewCost.baseCost)} + Tax: {formatInr(previewCost.gstAmount)}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] uppercase font-black tracking-wider text-black/70 block">Total Cost</span>
                    <span className="text-base font-black text-black">
                      {formatInr(previewCost.grossTotal)}
                    </span>
                  </div>
                </div>
              )}

              {/* Modal Footer */}
              <div className="pt-3 border-t-2 border-black flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-black text-black bg-[#F8F5EE] border-2 border-black rounded-lg hover:bg-white shadow-[2px_2px_0px_0px_#000] transition-transform active:translate-x-0.5 active:translate-y-0.5"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="bg-[#4ADE80] hover:bg-[#22c55e] text-black font-black px-5 py-2 text-xs rounded-lg border-2 border-black shadow-[3px_3px_0px_0px_#000] transition-transform active:translate-x-0.5 active:translate-y-0.5 flex items-center gap-1.5"
                >
                  <PlusCircle className="w-4 h-4" />
                  <span>Add Vendor to Budget</span>
                </button>
              </div>
            </form>
          ) : (
            /* JSON Import Tab */
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <label className="text-xs font-black text-black uppercase tracking-wider">
                  Paste JSON Array or Object
                </label>
                <button
                  type="button"
                  onClick={handleLoadSampleJson}
                  className="text-xs font-black text-black bg-[#FFE600] px-2.5 py-1 rounded-md border-2 border-black shadow-[2px_2px_0px_0px_#000] hover:bg-yellow-300 flex items-center gap-1"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Load Sample Batch</span>
                </button>
              </div>

              <textarea
                value={jsonText}
                onChange={(e) => setJsonText(e.target.value)}
                placeholder='[ { "vendorName": "...", "basePrice": 1500, "category": "catering" } ]'
                rows={10}
                className="w-full font-mono text-xs bg-[#F8F5EE] border-2 border-black rounded-lg p-3 text-black font-medium focus:outline-none focus:bg-white shadow-[2px_2px_0px_0px_#000]"
              />

              {jsonError && (
                <p className="text-xs font-black text-red-600 bg-red-100 p-2 rounded-lg border-2 border-red-600">
                  ⚠️ {jsonError}
                </p>
              )}

              <div className="pt-2 border-t-2 border-black flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 text-xs font-black text-black bg-[#F8F5EE] border-2 border-black rounded-lg hover:bg-white shadow-[2px_2px_0px_0px_#000]"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleJsonSubmit}
                  className="bg-[#38BDF8] hover:bg-sky-400 text-black font-black px-5 py-2 text-xs rounded-lg border-2 border-black shadow-[3px_3px_0px_0px_#000]"
                >
                  Import Records
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
