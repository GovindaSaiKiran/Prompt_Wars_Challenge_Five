import React from 'react';
import { VendorPriceRecord, EventBrief } from '../types/intelligence';
import { ProvenancePill } from './ProvenancePill';
import { formatInr, calculateVendorCost, CATEGORY_LABELS } from '../utils/ledgerMath';
import {
  X,
  ExternalLink,
  CheckCircle2,
  Mail,
  Receipt,
  Info,
  PhoneCall,
  MapPin,
  ShoppingBag,
} from 'lucide-react';

interface VerbatimAuditDrawerProps {
  record: VendorPriceRecord | null;
  brief: EventBrief | null;
  onClose: () => void;
  onDraftInquiry?: (vendor: VendorPriceRecord) => void;
}

export const VerbatimAuditDrawer: React.FC<VerbatimAuditDrawerProps> = ({
  record,
  brief,
  onClose,
  onDraftInquiry,
}) => {
  if (!record) return null;

  const cost = brief ? calculateVendorCost(record, brief) : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/60 backdrop-blur-xs">
      <div
        className="w-full max-w-lg h-full bg-[#FFFDF9] border-l-3 border-black flex flex-col shadow-[-8px_0px_0px_0px_#000] animate-in slide-in-from-right duration-200"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="p-4 sm:p-5 bg-[#FFE600] border-b-3 border-black flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-white border-2 border-black shadow-[2px_2px_0px_0px_#000] flex items-center justify-center text-lg">
              🎟️
            </div>
            <div>
              <h3 className="text-base font-black text-black tracking-tight">
                Vendor Quote Dossier
              </h3>
              <p className="text-xs font-semibold text-black/80">
                Audited verification, rates, contact & map coordinates
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

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Vendor Card */}
          <div className="bg-white border-2 border-black p-4 rounded-xl shadow-[3px_3px_0px_0px_#000]">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-black uppercase tracking-wider text-black bg-[#E2E8F0] px-2.5 py-0.5 rounded-md border-2 border-black">
                {CATEGORY_LABELS[record.category]}
              </span>
              <ProvenancePill status={record.status} />
            </div>
            <h2 className="text-lg font-black text-black mt-2">
              {record.vendorName}
            </h2>
            <div className="mt-3 pt-3 border-t-2 border-black flex items-baseline justify-between text-xs">
              <span className="font-bold text-black/70">Base Quoted Rate:</span>
              <span className="text-black font-black text-sm">
                {formatInr(record.basePrice)} per {record.unit.replace('per_', '').replace('_', ' ')}
              </span>
            </div>
          </div>

          {/* Contact, Location & Google Maps Navigation */}
          <div className="bg-[#BAE6FD] border-2 border-black p-4 rounded-xl shadow-[3px_3px_0px_0px_#000] space-y-3 text-xs">
            <div className="flex items-center justify-between gap-2 pb-2 border-b-2 border-black">
              <span className="font-black text-black flex items-center gap-1.5 uppercase tracking-wider">
                <MapPin className="w-4 h-4 text-black" />
                <span>Location & Navigation</span>
              </span>
              {record.mapUrl && (
                <a
                  href={record.mapUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-[#38BDF8] hover:bg-sky-400 text-black font-black px-2.5 py-1 rounded-lg border-2 border-black text-[11px] inline-flex items-center gap-1 shadow-[2px_2px_0px_0px_#000] transition-transform active:translate-x-0.5 active:translate-y-0.5"
                >
                  <span>Open Maps</span>
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>

            <div className="space-y-2 text-black">
              <div className="flex items-start gap-2">
                <span className="font-bold text-black/70 shrink-0">Address:</span>
                <span className="font-extrabold">
                  {record.address || 'Central City Area, Convention District'}
                </span>
              </div>

              <div className="flex items-center justify-between gap-2 pt-1">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-black/70 shrink-0">Phone:</span>
                  <a
                    href={`tel:${record.phone || '+919845012345'}`}
                    className="font-black text-black hover:underline"
                  >
                    {record.phone || '+91 98450 12345'}
                  </a>
                </div>
                <a
                  href={`tel:${record.phone || '+919845012345'}`}
                  className="bg-[#4ADE80] hover:bg-[#22c55e] text-black font-black px-2.5 py-1 rounded-lg border-2 border-black shadow-[2px_2px_0px_0px_#000] text-[11px] inline-flex items-center gap-1"
                >
                  <PhoneCall className="w-3 h-3" />
                  <span>Call Now</span>
                </a>
              </div>

              {record.contactPerson && (
                <div className="flex items-center gap-2 pt-1 border-t border-black/20">
                  <span className="font-bold text-black/70 shrink-0">POC:</span>
                  <span className="font-black text-black">{record.contactPerson}</span>
                </div>
              )}
            </div>

            {/* Nearby Shopping / Procurement */}
            {record.shoppingNearby && record.shoppingNearby.length > 0 && (
              <div className="mt-3 pt-3 border-t-2 border-black">
                <div className="text-[11px] font-black text-black mb-1.5 flex items-center gap-1 uppercase tracking-wider">
                  <ShoppingBag className="w-3.5 h-3.5" />
                  <span>Nearby Shopping & Procurement Hubs:</span>
                </div>
                <div className="space-y-1 text-xs font-bold text-black/90">
                  {record.shoppingNearby.map((shop, sIdx) => (
                    <div key={sIdx} className="flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-black"></span>
                      <span>{shop}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Cost Calculation Breakdown */}
          {cost && brief && (
            <div className="bg-[#FED7AA] border-2 border-black rounded-xl p-4 space-y-2.5 text-xs shadow-[3px_3px_0px_0px_#000]">
              <div className="flex items-center gap-1.5 pb-2 border-b-2 border-black">
                <Receipt className="w-4 h-4 text-black" />
                <span className="font-black text-black uppercase tracking-wider">
                  Deterministic Math Breakdown
                </span>
              </div>

              <div className="space-y-1.5 font-bold text-black pt-1">
                <div className="flex justify-between">
                  <span className="text-black/70">Quantity / Units:</span>
                  <span>{cost.unitQuantity} {record.unit.replace('per_', '').replace('_', ' ')}s</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-black/70">Base Subtotal:</span>
                  <span>{formatInr(cost.baseCost)}</span>
                </div>
                {cost.additionalCharges > 0 && (
                  <div className="flex justify-between">
                    <span className="text-black/70">Additional Surcharges:</span>
                    <span>+{formatInr(cost.additionalCharges)}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-black/70">GST ({record.gstPct}%):</span>
                  <span>+{formatInr(cost.gstAmount)}</span>
                </div>
                <div className="pt-2 border-t-2 border-black flex justify-between font-black text-sm text-black">
                  <span>Gross Total Commitment:</span>
                  <span className="text-emerald-800 bg-[#86EFAC] px-2 py-0.5 rounded border border-black">{formatInr(cost.grossTotal)}</span>
                </div>
              </div>
            </div>
          )}

          {/* Inclusions */}
          {record.inclusions && record.inclusions.length > 0 && (
            <div>
              <h4 className="text-xs font-black text-black uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-black" />
                <span>What's Included in Package</span>
              </h4>
              <div className="flex flex-wrap gap-2">
                {record.inclusions.map((item, idx) => (
                  <span
                    key={idx}
                    className="bg-white border-2 border-black text-black font-black px-2.5 py-1 rounded-lg text-xs shadow-[2px_2px_0px_0px_#000]"
                  >
                    ✓ {item}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Exclusions */}
          {record.exclusions && record.exclusions.length > 0 && (
            <div>
              <h4 className="text-xs font-black text-black uppercase tracking-wider mb-2">
                Not Included / Extra Charges
              </h4>
              <div className="flex flex-wrap gap-2">
                {record.exclusions.map((item, idx) => (
                  <span
                    key={idx}
                    className="bg-[#FED7AA] border-2 border-black text-black font-bold px-2.5 py-1 rounded-lg text-xs shadow-[2px_2px_0px_0px_#000]"
                  >
                    ✕ {item}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Notes or Quote Source */}
          {record.verbatimSnippet && (
            <div>
              <h4 className="text-xs font-black text-black uppercase tracking-wider mb-2 flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5 text-black" />
                <span>Notes & Rate Card Snippet</span>
              </h4>
              <div className="bg-white border-2 border-black p-3 rounded-xl text-xs font-medium text-black leading-relaxed shadow-[3px_3px_0px_0px_#000]">
                {record.verbatimSnippet}
              </div>
            </div>
          )}

          {/* Source Link */}
          {record.sourceUrl && (
            <div>
              <a
                href={record.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-xs font-black text-black bg-[#FFE600] px-3 py-1.5 rounded-lg border-2 border-black shadow-[2px_2px_0px_0px_#000] hover:bg-yellow-300"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>View Original Quoting Portal / Rate Card</span>
              </a>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="p-4 border-t-2 border-black flex items-center justify-between gap-3 bg-[#F8F5EE]">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-black text-black bg-white border-2 border-black rounded-lg shadow-[2px_2px_0px_0px_#000] hover:bg-[#F8F5EE] transition-transform active:translate-x-0.5 active:translate-y-0.5"
          >
            Close
          </button>

          {onDraftInquiry && (
            <button
              onClick={() => {
                onDraftInquiry(record);
                onClose();
              }}
              className="bg-[#FF6B8B] hover:bg-pink-400 text-black font-black px-4 py-2 text-xs rounded-lg border-2 border-black shadow-[3px_3px_0px_0px_#000] transition-transform active:translate-x-0.5 active:translate-y-0.5 flex items-center gap-1.5"
            >
              <Mail className="w-3.5 h-3.5" />
              <span>Contact / Draft WhatsApp</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
