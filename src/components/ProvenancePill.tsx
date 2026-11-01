import React from 'react';
import { EvidenceStatus } from '../types/intelligence';

interface ProvenancePillProps {
  status: EvidenceStatus;
  className?: string;
  showTooltip?: boolean;
}

export const ProvenancePill: React.FC<ProvenancePillProps> = ({
  status,
  className = '',
  showTooltip = true,
}) => {
  switch (status) {
    case 'vendor_confirmed':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#86EFAC] text-black border border-black shadow-[1px_1px_0px_0px_#000] ${className}`}
          title={showTooltip ? 'Signed contract or confirmed booking' : undefined}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-black" />
          <span>Confirmed</span>
        </span>
      );

    case 'vendor_quoted':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#BAE6FD] text-black border border-black shadow-[1px_1px_0px_0px_#000] ${className}`}
          title={showTooltip ? 'Direct written quote from vendor' : undefined}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-black" />
          <span>Direct Quote</span>
        </span>
      );

    case 'published':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#FEF08A] text-black border border-black shadow-[1px_1px_0px_0px_#000] ${className}`}
          title={showTooltip ? 'Public rate card or catalog price' : undefined}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-black" />
          <span>Published Rate</span>
        </span>
      );

    case 'estimated':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#FED7AA] text-black border border-black shadow-[1px_1px_0px_0px_#000] ${className}`}
          title={showTooltip ? 'Rough estimate / placeholder' : undefined}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-black" />
          <span>Estimate</span>
        </span>
      );

    case 'expired':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#FDA4AF] text-black border border-black shadow-[1px_1px_0px_0px_#000] ${className}`}
          title={showTooltip ? 'Quote validity has expired' : undefined}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-black" />
          <span>Expired</span>
        </span>
      );

    default:
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-slate-200 text-black border border-black ${className}`}
          title={showTooltip ? 'Unverified quote' : undefined}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-black" />
          <span>Unverified</span>
        </span>
      );
  }
};
