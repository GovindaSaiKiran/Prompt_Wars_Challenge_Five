import React from 'react';
import { AvailabilityStatus } from '../types/vendor';

interface AvailabilityPillProps {
  status: AvailabilityStatus;
  checkedAt?: string | null;
  className?: string;
}

export const AvailabilityPill: React.FC<AvailabilityPillProps> = ({
  status,
  checkedAt,
  className = '',
}) => {
  const formattedDate = checkedAt
    ? `Checked: ${new Date(checkedAt).toLocaleDateString()}`
    : 'Not verified recently';

  switch (status) {
    case 'available':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#86EFAC] text-black border border-black shadow-[1px_1px_0px_0px_#000] ${className}`}
          title={`Vendor is available for bookings. ${formattedDate}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-700 animate-pulse" />
          <span>Available</span>
        </span>
      );

    case 'limited':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#FEF08A] text-black border border-black shadow-[1px_1px_0px_0px_#000] ${className}`}
          title={`Limited availability / slots filling fast. ${formattedDate}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
          <span>Limited Slots</span>
        </span>
      );

    case 'unavailable':
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-[#FDA4AF] text-black border border-black shadow-[1px_1px_0px_0px_#000] ${className}`}
          title={`Vendor is fully booked or unavailable. ${formattedDate}`}
        >
          <span className="w-1.5 h-1.5 rounded-full bg-rose-700" />
          <span>Unavailable</span>
        </span>
      );

    default:
      return (
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-wider bg-slate-100 text-slate-700 border border-black ${className}`}
          title="Availability has not been confirmed with vendor"
        >
          <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
          <span>Avail. Unknown</span>
        </span>
      );
  }
};

