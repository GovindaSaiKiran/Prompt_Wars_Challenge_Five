import React, { useState } from 'react';
import { ApprovalAction } from '../types/intelligence';
import { Check, X, Mail, Plus, Send } from 'lucide-react';

interface ApprovalQueuePanelProps {
  approvals: ApprovalAction[];
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onCreateAction: (action: Omit<ApprovalAction, 'id' | 'createdAt' | 'status'>) => void;
}

export const ApprovalQueuePanel: React.FC<ApprovalQueuePanelProps> = ({
  approvals,
  onApprove,
  onReject,
  onCreateAction,
}) => {
  const [isCreating, setIsCreating] = useState(false);
  const [actionType, setActionType] = useState<'send_inquiry' | 'calendar_invite' | 'lock_quote'>('send_inquiry');
  const [vendorName, setVendorName] = useState('');
  const [recipientContact, setRecipientContact] = useState('');
  const [draftContent, setDraftContent] = useState('');

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!vendorName.trim() || !draftContent.trim()) return;

    onCreateAction({
      actionType,
      vendorName: vendorName.trim(),
      recipientContact: recipientContact.trim() || 'vendor@example.com',
      draftContent: draftContent.trim(),
    });

    setVendorName('');
    setRecipientContact('');
    setDraftContent('');
    setIsCreating(false);
  };

  const pendingCount = approvals.filter((a) => a.status === 'pending').length;

  return (
    <div className="bg-white border-2 border-black rounded-2xl overflow-hidden shadow-[4px_4px_0px_0px_#000]">
      {/* Header */}
      <div className="p-4 sm:p-5 bg-[#38BDF8] border-b-2 border-black flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-white border-2 border-black flex items-center justify-center text-sm shadow-[1px_1px_0px_0px_#000]">
              ✉️
            </div>
            <h3 className="text-base font-black text-black tracking-tight">
              Vendor Inquiries & Negotiation
            </h3>
            {pendingCount > 0 && (
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-[#FFE600] text-black border-2 border-black font-black shadow-[1px_1px_0px_0px_#000]">
                {pendingCount} Pending
              </span>
            )}
          </div>
          <p className="text-xs font-semibold text-black/80 mt-1">
            Dispatch official booking requests, WhatsApp inquiries, or contract signatures
          </p>
        </div>

        <button
          onClick={() => setIsCreating(!isCreating)}
          className="flex items-center gap-1.5 text-xs font-black text-black bg-[#FFE600] hover:bg-yellow-300 px-3.5 py-1.5 rounded-lg border-2 border-black shadow-[2px_2px_0px_0px_#000] transition-transform active:translate-x-0.5 active:translate-y-0.5"
        >
          <Plus className="w-3.5 h-3.5 stroke-[3]" />
          <span>New Inquiry</span>
        </button>
      </div>

      {/* Inline Create Form */}
      {isCreating && (
        <form
          onSubmit={handleCreateSubmit}
          className="p-4 border-b-2 border-black bg-[#F8F5EE] space-y-3 animate-in fade-in duration-150"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-black uppercase text-black mb-1">
                Vendor Name
              </label>
              <input
                type="text"
                value={vendorName}
                onChange={(e) => setVendorName(e.target.value)}
                placeholder="e.g. AcousticVision Pro Sound"
                className="w-full bg-white border-2 border-black rounded-lg px-3 py-2 text-xs font-bold text-black placeholder-black/40 focus:outline-none shadow-[2px_2px_0px_0px_#000]"
                autoFocus
              />
            </div>

            <div>
              <label className="block text-xs font-black uppercase text-black mb-1">
                Vendor Email / Phone
              </label>
              <input
                type="text"
                value={recipientContact}
                onChange={(e) => setRecipientContact(e.target.value)}
                placeholder="e.g. contact@acousticvision.com or +91 98450 12345"
                className="w-full bg-white border-2 border-black rounded-lg px-3 py-2 text-xs font-bold text-black placeholder-black/40 focus:outline-none shadow-[2px_2px_0px_0px_#000]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-black uppercase text-black mb-1">
              Message / Inclusions Request
            </label>
            <textarea
              value={draftContent}
              onChange={(e) => setDraftContent(e.target.value)}
              placeholder="Hi Rajesh, we would like to confirm our booking for the event..."
              rows={3}
              className="w-full bg-white border-2 border-black rounded-lg p-3 text-xs font-bold text-black placeholder-black/40 focus:outline-none shadow-[2px_2px_0px_0px_#000]"
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => setIsCreating(false)}
              className="px-3 py-1.5 rounded-lg text-xs font-black text-black bg-white border-2 border-black shadow-[1px_1px_0px_0px_#000]"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="bg-[#4ADE80] text-black font-black px-4 py-1.5 rounded-lg text-xs border-2 border-black shadow-[2px_2px_0px_0px_#000] hover:bg-[#22c55e]"
            >
              Save Inquiry
            </button>
          </div>
        </form>
      )}

      {/* Messages List */}
      {approvals.length === 0 ? (
        <div className="p-8 text-center text-black/60 font-bold text-xs bg-[#FFFDF9]">
          No vendor inquiries yet. Click "Details &gt; Contact" on any vendor or "New Inquiry" above.
        </div>
      ) : (
        <div className="divide-y-2 divide-black bg-[#FFFDF9]">
          {approvals.map((item) => {
            const isApproved = item.status === 'approved';
            const isRejected = item.status === 'rejected';

            return (
              <div
                key={item.id}
                className="p-4 sm:px-5 space-y-2 hover:bg-[#F8F5EE] transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-black text-black text-xs">
                      {item.vendorName}
                    </span>
                    <span className="text-[11px] font-bold text-black/60">
                      ({item.recipientContact})
                    </span>
                  </div>

                  {/* Status */}
                  <div>
                    {isApproved ? (
                      <span className="text-[11px] px-2.5 py-0.5 rounded-md bg-[#86EFAC] text-black border-2 border-black font-black shadow-[1px_1px_0px_0px_#000]">
                        ✓ Sent / Approved
                      </span>
                    ) : isRejected ? (
                      <span className="text-[11px] px-2.5 py-0.5 rounded-md bg-[#FDA4AF] text-black border-2 border-black font-black shadow-[1px_1px_0px_0px_#000]">
                        Dismissed
                      </span>
                    ) : (
                      <span className="text-[11px] px-2.5 py-0.5 rounded-md bg-[#FFE600] text-black border-2 border-black font-black shadow-[1px_1px_0px_0px_#000]">
                        Ready to Send
                      </span>
                    )}
                  </div>
                </div>

                <p className="text-xs font-medium text-black leading-relaxed bg-[#F8F5EE] p-3 rounded-lg border-2 border-black shadow-[2px_2px_0px_0px_#000]">
                  {item.draftContent}
                </p>

                {item.status === 'pending' && (
                  <div className="flex items-center justify-end gap-2 pt-1">
                    <button
                      onClick={() => onReject(item.id)}
                      className="px-2.5 py-1 text-xs font-black text-black bg-white border border-black rounded-md hover:bg-red-50"
                    >
                      Dismiss
                    </button>
                    <button
                      onClick={() => onApprove(item.id)}
                      className="flex items-center gap-1.5 bg-[#4ADE80] text-black border-2 border-black px-3 py-1 rounded-md text-xs font-black shadow-[2px_2px_0px_0px_#000] hover:bg-[#22c55e]"
                    >
                      <Check className="w-3.5 h-3.5 stroke-[3]" />
                      <span>Mark as Sent</span>
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
