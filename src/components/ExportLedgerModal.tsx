import React, { useState } from 'react';
import {
  VendorPriceRecord,
  EventBrief,
  LedgerFinancialSummary,
  TimelineTask,
} from '../types/intelligence';
import { calculateVendorCost, formatInr } from '../utils/ledgerMath';
import { printEventPlanAsPdf } from '../utils/printPdfPlan';
import {
  X,
  Download,
  Copy,
  Check,
  FileJson,
  FileSpreadsheet,
  Printer,
  FileText,
} from 'lucide-react';

interface ExportLedgerModalProps {
  isOpen: boolean;
  onClose: () => void;
  vendors: VendorPriceRecord[];
  brief: EventBrief | null;
  summary: LedgerFinancialSummary;
  tasks?: TimelineTask[];
}

export const ExportLedgerModal: React.FC<ExportLedgerModalProps> = ({
  isOpen,
  onClose,
  vendors,
  brief,
  summary,
  tasks = [],
}) => {
  const [copied, setCopied] = useState(false);
  const [exportFormat, setExportFormat] = useState<'pdf' | 'csv' | 'json'>('pdf');

  if (!isOpen) return null;

  const handlePrintPdf = () => {
    printEventPlanAsPdf(brief, vendors, summary, tasks);
    onClose();
  };

  const generateJsonData = () => {
    return {
      exportedAt: new Date().toISOString(),
      appName: 'EventBudget',
      event: brief,
      summary: summary,
      vendors: vendors.map((v) => {
        const cost = brief ? calculateVendorCost(v, brief) : null;
        return {
          ...v,
          calculatedCost: cost,
        };
      }),
      tasks: tasks,
    };
  };

  const generateCsvData = () => {
    const headers = [
      'Vendor Name',
      'Category',
      'Phone Number',
      'Address',
      'Google Maps Link',
      'Contact Person',
      'Base Price (INR)',
      'Pricing Unit',
      'GST %',
      'Additional Charges (INR)',
      'Subtotal (INR)',
      'GST Amount (INR)',
      'Gross Total (INR)',
      'Included In Budget',
      'Quote Status',
    ];

    const rows = vendors.map((v) => {
      const cost = brief ? calculateVendorCost(v, brief) : null;
      return [
        `"${v.vendorName.replace(/"/g, '""')}"`,
        v.category,
        `"${v.phone || ''}"`,
        `"${(v.address || '').replace(/"/g, '""')}"`,
        `"${(v.mapUrl || '').replace(/"/g, '""')}"`,
        `"${(v.contactPerson || '').replace(/"/g, '""')}"`,
        v.basePrice,
        v.unit,
        v.gstPct,
        v.additionalCharges,
        cost ? cost.taxableAmount : 0,
        cost ? cost.gstAmount : 0,
        cost ? cost.grossTotal : 0,
        v.isSelectedForBudget ? 'Yes' : 'No',
        v.status,
      ];
    });

    return [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
  };

  const jsonString = JSON.stringify(generateJsonData(), null, 2);
  const csvString = generateCsvData();

  const handleCopy = () => {
    const textToCopy = exportFormat === 'json' ? jsonString : csvString;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadFile = () => {
    const content = exportFormat === 'json' ? jsonString : csvString;
    const filename = `event-budget-${
      brief?.eventName.toLowerCase().replace(/[^a-z0-9]/g, '-') || 'export'
    }.${exportFormat}`;
    const blob = new Blob([content], {
      type: exportFormat === 'json' ? 'application/json' : 'text/csv;charset=utf-8;',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div
        className="w-full max-w-xl bg-white border-2 border-black rounded-2xl overflow-hidden shadow-[8px_8px_0px_0px_#000]"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b-2 border-black bg-[#FFE600]">
          <div>
            <h3 className="text-base font-black text-black font-heading uppercase flex items-center gap-2">
              <span>📄</span>
              <span>Export Event Plan & Directory</span>
            </h3>
            <p className="text-xs font-bold text-slate-800 mt-0.5">
              Export full plan as PDF with phone numbers, Google Maps navigation, and shopping guide.
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-black bg-white hover:bg-slate-100 border-2 border-black p-1.5 rounded-lg shadow-[2px_2px_0px_0px_#000] transition-transform hover:scale-105"
          >
            <X className="w-5 h-5 stroke-[2.5]" />
          </button>
        </div>

        {/* Format Selector */}
        <div className="flex items-center justify-between px-5 py-3 bg-[#F8F5EE] border-b-2 border-black">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setExportFormat('pdf')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-black transition-all ${
                exportFormat === 'pdf'
                  ? 'bg-[#4ADE80] text-black border-2 border-black shadow-[2px_2px_0px_0px_#000]'
                  : 'bg-white hover:bg-slate-100 text-black border-2 border-black'
              }`}
            >
              <Printer className="w-3.5 h-3.5 stroke-[2.5]" />
              <span>Full Plan (PDF)</span>
            </button>

            <button
              onClick={() => setExportFormat('csv')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-black transition-all ${
                exportFormat === 'csv'
                  ? 'bg-[#FFE600] text-black border-2 border-black shadow-[2px_2px_0px_0px_#000]'
                  : 'bg-white hover:bg-slate-100 text-black border-2 border-black'
              }`}
            >
              <FileSpreadsheet className="w-3.5 h-3.5 stroke-[2.5]" />
              <span>Spreadsheet (CSV)</span>
            </button>

            <button
              onClick={() => setExportFormat('json')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-black transition-all ${
                exportFormat === 'json'
                  ? 'bg-[#BAE6FD] text-black border-2 border-black shadow-[2px_2px_0px_0px_#000]'
                  : 'bg-white hover:bg-slate-100 text-black border-2 border-black'
              }`}
            >
              <FileJson className="w-3.5 h-3.5 stroke-[2.5]" />
              <span>Data (JSON)</span>
            </button>
          </div>

          {exportFormat !== 'pdf' && (
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 text-xs text-black font-black bg-white hover:bg-[#FFE600] border-2 border-black px-3 py-1.5 rounded-lg shadow-[1.5px_1.5px_0px_0px_#000] transition-all"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 stroke-[3]" />
                  <span>Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 stroke-[2.5]" />
                  <span>Copy</span>
                </>
              )}
            </button>
          )}
        </div>

        {/* Content Area */}
        <div className="p-5">
          {exportFormat === 'pdf' ? (
            <div className="bg-[#FFFDF9] border-2 border-black rounded-xl p-5 space-y-4 shadow-[3px_3px_0px_0px_#000]">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#4ADE80] border-2 border-black text-black flex items-center justify-center shrink-0 shadow-[2px_2px_0px_0px_#000]">
                  <FileText className="w-5 h-5 stroke-[2.5]" />
                </div>
                <div>
                  <h4 className="text-sm font-black text-black font-heading uppercase">
                    Print-Ready Event PDF Document
                  </h4>
                  <p className="text-xs font-bold text-slate-700 mt-1 leading-relaxed">
                    Includes Executive Budget Summary, Itemized Vendor Directory with <strong>Phone Numbers</strong>, <strong>Physical Addresses</strong>, <strong>Google Maps Navigation links</strong> to halls & studios, and the <strong>Nearby Shopping & Materials Guide</strong>.
                  </p>
                </div>
              </div>

              {/* PDF Preview Snapshot */}
              <div className="bg-[#FEF08A] border-2 border-black rounded-xl p-3 text-xs space-y-2 text-black font-bold shadow-[2px_2px_0px_0px_#000]">
                <div className="flex justify-between">
                  <span>Event:</span>
                  <strong className="font-black">{brief?.eventName || 'Event Plan'}</strong>
                </div>
                <div className="flex justify-between">
                  <span>Target Budget:</span>
                  <strong className="font-black">{brief ? formatInr(brief.targetBudgetInr) : '—'}</strong>
                </div>
                <div className="flex justify-between">
                  <span>Vendors Included:</span>
                  <span>{summary.selectedVendorCount} suppliers</span>
                </div>
                <div className="flex justify-between">
                  <span>Vendor Contacts & Maps:</span>
                  <span className="neo-stamp bg-[#86EFAC] text-black">
                    ✓ PHONE + MAPS READY
                  </span>
                </div>
              </div>

              <button
                onClick={handlePrintPdf}
                className="w-full bg-[#4ADE80] hover:bg-[#22C55E] text-black font-black py-3 px-4 rounded-xl text-xs border-2 border-black shadow-[3px_3px_0px_0px_#000] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[2px_2px_0px_0px_#000] active:translate-x-[3px] active:shadow-none transition-all flex items-center justify-center gap-2 cursor-pointer"
              >
                <Printer className="w-4 h-4 stroke-[2.5]" />
                <span>Export & Print / Save PDF Now</span>
              </button>
            </div>
          ) : (
            <div className="bg-[#F8F5EE] border-2 border-black rounded-xl p-3 max-h-56 overflow-auto font-mono text-[11px] text-black leading-relaxed shadow-inner">
              <pre className="whitespace-pre-wrap font-bold">
                {exportFormat === 'json' ? jsonString : csvString}
              </pre>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t-2 border-black flex items-center justify-between bg-[#F8F5EE]">
          <span className="text-xs font-bold text-slate-700">
            {vendors.length} vendor record{vendors.length === 1 ? '' : 's'} ready
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="px-3.5 py-1.5 text-xs text-black font-black bg-white hover:bg-slate-100 border-2 border-black rounded-xl shadow-[2px_2px_0px_0px_#000] transition-all"
            >
              Close
            </button>
            {exportFormat !== 'pdf' && (
              <button
                onClick={handleDownloadFile}
                className="flex items-center gap-1.5 bg-[#FFE600] hover:bg-[#FACC15] text-black font-black px-4 py-1.5 rounded-xl text-xs border-2 border-black shadow-[2px_2px_0px_0px_#000] transition-all"
              >
                <Download className="w-3.5 h-3.5 stroke-[2.5]" />
                <span>Download {exportFormat.toUpperCase()}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
