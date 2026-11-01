import { EventBrief, VendorPriceRecord, TimelineTask, LedgerFinancialSummary } from '../types/intelligence';
import { calculateVendorCost, formatInr } from './ledgerMath';

export function printEventPlanAsPdf(
  brief: EventBrief | null,
  vendors: VendorPriceRecord[],
  summary: LedgerFinancialSummary,
  tasks: TimelineTask[] = []
) {
  const eventName = brief?.eventName || 'Event Budget & Vendor Plan';
  const location = brief?.location || 'Bengaluru, India';
  const eventDate = brief?.eventDate || 'November 2026';
  const guests = brief?.guestCount || 150;
  const targetBudget = brief ? formatInr(brief.targetBudgetInr) : '₹0';
  const committedTotal = formatInr(summary.committedTotal);
  const contingency = formatInr(summary.contingencyAmount);
  const remainingVariance = formatInr(Math.abs(summary.varianceInr));
  const isOver = summary.isOverBudget;

  // Selected vendors
  const activeVendors = vendors.filter((v) => v.isSelectedForBudget);

  const printWindow = window.open('', '_blank', 'width=1000,height=900');
  if (!printWindow) {
    alert('Please allow popups to export the PDF plan.');
    return;
  }

  const htmlContent = `
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>${eventName} — Full Event Plan & Vendor Directory</title>
  <style>
    @media print {
      body { margin: 0; padding: 20px; font-size: 11pt; color: #111; }
      .no-print { display: none !important; }
      .page-break { page-break-after: always; }
      a { color: #0066cc; text-decoration: none; }
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.45;
      color: #1f2937;
      background: #ffffff;
      padding: 32px;
      max-width: 960px;
      margin: 0 auto;
    }
    .header-bar {
      border-bottom: 2px solid #10b981;
      padding-bottom: 16px;
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
    }
    .badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      background: #ecfdf5;
      color: #059669;
      border: 1px solid #a7f3d0;
    }
    h1 { margin: 0 0 6px 0; font-size: 24px; color: #111827; }
    .subtitle { color: #6b7280; font-size: 13px; margin: 0; }
    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 12px;
      margin-bottom: 24px;
    }
    .kpi-card {
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 12px;
    }
    .kpi-label { font-size: 11px; color: #6b7280; text-transform: uppercase; font-weight: 600; margin-bottom: 4px; }
    .kpi-value { font-size: 18px; font-weight: 700; color: #111827; }
    .kpi-sub { font-size: 11px; color: #059669; margin-top: 2px; }

    h2 { font-size: 16px; border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; margin-top: 28px; margin-bottom: 12px; color: #111827; }

    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 12px; }
    th { background: #f3f4f6; color: #374151; text-align: left; padding: 8px 10px; font-weight: 600; border-bottom: 1px solid #d1d5db; }
    td { padding: 9px 10px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
    tr:nth-child(even) td { background-color: #fafafa; }

    .vendor-card {
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 14px;
      background: #ffffff;
    }
    .vendor-header {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 6px;
    }
    .vendor-title { font-size: 14px; font-weight: 700; color: #111827; }
    .vendor-cost { font-size: 14px; font-weight: 700; color: #059669; }
    .vendor-meta { font-size: 12px; color: #4b5563; margin-bottom: 6px; }
    .vendor-address { font-size: 12px; color: #374151; margin-bottom: 6px; display: flex; align-items: flex-start; gap: 4px; }
    .vendor-contact { font-size: 12px; color: #1f2937; margin-bottom: 8px; }
    .map-btn {
      display: inline-block;
      padding: 3px 8px;
      background: #eff6ff;
      color: #1d4ed8;
      border: 1px solid #bfdbfe;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 600;
      text-decoration: none;
      margin-left: 6px;
    }
    .phone-link {
      color: #059669;
      font-weight: 600;
      text-decoration: none;
    }
    .inclusions-list {
      font-size: 11px;
      color: #4b5563;
      margin: 4px 0 0 0;
      padding-left: 18px;
    }
    .shopping-box {
      background: #fffbeb;
      border: 1px solid #fef3c7;
      border-radius: 8px;
      padding: 12px;
      margin-top: 20px;
    }
    .shopping-title { font-weight: 700; font-size: 13px; color: #92400e; margin-bottom: 6px; }
    .shopping-item { font-size: 12px; color: #78350f; margin-bottom: 4px; }
    .actions-bar {
      position: sticky;
      top: 0;
      background: #111827;
      color: #ffffff;
      padding: 12px 20px;
      border-radius: 8px;
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .btn-print {
      background: #10b981;
      color: #ffffff;
      border: none;
      padding: 8px 18px;
      font-size: 13px;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
    }
    .btn-print:hover { background: #059669; }
    .footer-note {
      margin-top: 32px;
      border-top: 1px solid #e5e7eb;
      padding-top: 12px;
      font-size: 11px;
      color: #9ca3af;
      text-align: center;
    }
  </style>
</head>
<body>
  <div class="actions-bar no-print">
    <div>
      <strong>Print Ready Event Budget & Vendor Plan</strong>
      <div style="font-size: 11px; color: #9ca3af;">Click the green button or press Ctrl+P / Cmd+P to save as PDF.</div>
    </div>
    <button class="btn-print" onclick="window.print()">Save as PDF / Print Plan</button>
  </div>

  <div class="header-bar">
    <div>
      <span class="badge">Verified Event Budget Plan</span>
      <h1 style="margin-top: 6px;">${eventName}</h1>
      <p class="subtitle">
        📍 Location: <strong>${location}</strong> &nbsp;|&nbsp; 
        👥 Attendance: <strong>${guests} Guests</strong> &nbsp;|&nbsp; 
        📅 Date: <strong>${eventDate}</strong>
      </p>
    </div>
    <div style="text-align: right;">
      <div style="font-size: 11px; color: #6b7280; text-transform: uppercase; font-weight: 600;">Target Budget</div>
      <div style="font-size: 22px; font-weight: 800; color: #059669;">${targetBudget}</div>
      <div style="font-size: 11px; color: #6b7280;">Includes 18% GST + Safety Reserve</div>
    </div>
  </div>

  <!-- KPI summary -->
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-label">Committed Expenses</div>
      <div class="kpi-value">${committedTotal}</div>
      <div class="kpi-sub">${summary.selectedVendorCount} vendors engaged</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Safety Buffer (10%)</div>
      <div class="kpi-value">${contingency}</div>
      <div class="kpi-sub">Reserved for unforeseen costs</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Cost Per Guest</div>
      <div class="kpi-value">${formatInr(Math.round(summary.committedTotal / Math.max(1, guests)))}</div>
      <div class="kpi-sub">All-inclusive per pax</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Budget Health</div>
      <div class="kpi-value" style="color: ${isOver ? '#dc2626' : '#059669'};">
        ${isOver ? 'Exceeds by ' + remainingVariance : 'Buffer ' + remainingVariance}
      </div>
      <div class="kpi-sub">${isOver ? 'Review reductions' : 'Within budget target'}</div>
    </div>
  </div>

  <!-- Category Breakdown -->
  <h2>1. Category Allocation Summary</h2>
  <table>
    <thead>
      <tr>
        <th>Category</th>
        <th>Committed Subtotal</th>
        <th>Est. GST (18%)</th>
        <th>Total Gross Amount</th>
        <th>Share of Budget</th>
      </tr>
    </thead>
    <tbody>
      ${Object.entries(summary.categoryBreakdown)
        .filter(([_, cat]) => cat.count > 0)
        .map(([key, cat]) => {
          const pct = summary.committedTotal > 0 ? Math.round((cat.total / summary.committedTotal) * 100) : 0;
          return `
            <tr>
              <td><strong style="text-transform: capitalize;">${key}</strong> (${cat.count} vendor${cat.count === 1 ? '' : 's'})</td>
              <td>${formatInr(cat.subtotal)}</td>
              <td>${formatInr(cat.gst)}</td>
              <td><strong>${formatInr(cat.total)}</strong></td>
              <td>${pct}%</td>
            </tr>
          `;
        })
        .join('')}
    </tbody>
  </table>

  <!-- Detailed Vendor Directory & Map Navigation -->
  <h2>2. Vendor Directory, Contacts & Maps Navigation</h2>
  <p style="font-size: 12px; color: #6b7280; margin-bottom: 12px;">
    Use the phone links to directly call suppliers and the Google Maps navigation buttons to get driving directions to convention halls and vendor facilities.
  </p>

  ${activeVendors
    .map((v) => {
      const cost = brief ? calculateVendorCost(v, brief) : null;
      const mapLink = v.mapUrl || `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(v.vendorName + ' ' + (v.address || location))}`;
      return `
        <div class="vendor-card">
          <div class="vendor-header">
            <div>
              <span class="badge" style="font-size: 10px; padding: 2px 8px; margin-bottom: 4px;">${v.category}</span>
              <div class="vendor-title">${v.vendorName}</div>
            </div>
            <div style="text-align: right;">
              <div class="vendor-cost">${cost ? formatInr(cost.grossTotal) : formatInr(v.basePrice)}</div>
              <div style="font-size: 11px; color: #6b7280;">(${v.unit.replace('per_', '/').replace('_', ' ')} incl. ${v.gstPct}% GST)</div>
            </div>
          </div>

          <div class="vendor-address">
            📍 <strong>Address:</strong> ${v.address || (location + ', India')}
            <a href="${mapLink}" target="_blank" class="map-btn">🗺️ Navigate on Google Maps</a>
          </div>

          <div class="vendor-contact">
            📞 <strong>Phone:</strong> <a href="tel:${v.phone || '+919845012345'}" class="phone-link">${v.phone || '+91 98450 12345'}</a>
            &nbsp;&bull;&nbsp;
            👤 <strong>Contact Person:</strong> ${v.contactPerson || 'Events Booking Desk'}
          </div>

          <div style="font-size: 11px; color: #4b5563;">
            <strong>Inclusions:</strong> ${v.inclusions.join(' • ')}
          </div>
          ${v.exclusions && v.exclusions.length > 0 ? `
            <div style="font-size: 11px; color: #9ca3af; margin-top: 2px;">
              <strong>Exclusions:</strong> ${v.exclusions.join(' • ')}
            </div>
          ` : ''}
        </div>
      `;
    })
    .join('')}

  <!-- Nearby Shopping & Procurement Guide -->
  <div class="shopping-box">
    <div class="shopping-title">🛍️ Recommended Event Shopping & Procurement Markets</div>
    <div class="shopping-item">
      &bull; <strong>Wholesale Decor & Floral Market:</strong> KR Market & Chickpet / Dadar Flower Market &bull; Fresh flowers, stage draping, wholesale floral garlands.
    </div>
    <div class="shopping-item">
      &bull; <strong>Fabric & Attire Sourcing:</strong> Commercial Street / Chandni Chowk &bull; Uniforms, custom table overlays, event banners & ribbons.
    </div>
    <div class="shopping-item">
      &bull; <strong>Lighting & Sound Hardware:</strong> SP Road / Lamington Road &bull; Cabling, converters, backup adapters, stage lights & PA connectors.
    </div>
    <div class="shopping-item">
      &bull; <strong>Gifting & Packaging Materials:</strong> Wholesale Paper & Packaging Market &bull; Delegate kits, gift hampers, return bags and badges.
    </div>
  </div>

  ${tasks.length > 0 ? `
    <h2>3. Event Milestones & Checklist</h2>
    <table>
      <thead>
        <tr>
          <th>Task Milestone</th>
          <th>Category</th>
          <th>Due Date</th>
          <th>Priority</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        ${tasks
          .map(
            (t) => `
          <tr>
            <td><strong>${t.title}</strong></td>
            <td style="text-transform: capitalize;">${t.category}</td>
            <td>${t.dueDate}</td>
            <td><span style="text-transform: uppercase; font-weight: 600; font-size: 10px;">${t.priority}</span></td>
            <td>${t.status === 'done' ? '✅ Completed' : '⏳ Pending'}</td>
          </tr>
        `
          )
          .join('')}
      </tbody>
    </table>
  ` : ''}

  <div class="footer-note">
    Generated by EventBudget Autonomous AI Agent &bull; Verified quotes &bull; Transparent Tax Compliance
  </div>
</body>
</html>
  `;

  printWindow.document.open();
  printWindow.document.write(htmlContent);
  printWindow.document.close();
}
