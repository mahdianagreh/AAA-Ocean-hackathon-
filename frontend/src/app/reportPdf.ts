import type { ReportOut } from '../api/live';

/** Client-side themed PDF export for a forensic report (Phase 8, Page 5).
 *
 *  ReportOut already carries the full structured content, so no server endpoint
 *  is needed and no PDF library is bundled: we assemble a self-contained, themed
 *  HTML document, open it in a new window and hand it to the browser's own
 *  "Save as PDF". Zero runtime fetches, so it stays offline-safe.
 *
 *  The AI-DRAFTED / HUMAN-REVIEWED status is printed as a prominent banner — a
 *  drafted report exported without it is indistinguishable from a reviewed one,
 *  which is the exact failure this carries the status to prevent.
 *
 *  Colours: the brand tokens (navy/aqua) are read from the live stylesheet so no
 *  hex literal enters the source; everything else uses rgb()/named colours. The
 *  document is deliberately light regardless of the app theme — it is print. */

export interface ReportPdfLabels {
  brand: string;
  docTitle: string;
  statusDrafted: string;
  statusReviewed: string;
  draftedMeaning: string;
  reviewedMeaning: string;
  eventLabel: string;
  generatedAt: string;
  reviewedAt: string;
  reviewedBy: string;
  notReviewed: string;
  source: string;
  sourceMissing: string;
  footer: string;
}

function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function tokenValue(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

/** Returns false if the print window was blocked (so the caller can tell the
 *  user), true once the document has been handed to the browser. */
export function downloadReportPdf(
  report: ReportOut,
  opts: { lang: 'en' | 'ar'; labels: ReportPdfLabels },
): boolean {
  const { lang, labels } = opts;
  const dir = lang === 'ar' ? 'rtl' : 'ltr';
  // Fixed brand furniture — does not invert with theme; safe to read live.
  const navy = tokenValue('--brand-navy', 'rgb(10 31 77)');
  const aqua = tokenValue('--brand-aqua', 'rgb(0 183 195)');

  const drafted = report.status === 'ai_drafted';
  // Drafted = a red caution banner; reviewed = the brand navy. White text on both.
  const statusBg = drafted ? 'rgb(185 60 39)' : navy;
  const statusText = drafted ? labels.statusDrafted : labels.statusReviewed;
  const statusMeaning = drafted ? labels.draftedMeaning : labels.reviewedMeaning;

  const sectionsHtml = report.sections
    .map((s) => {
      const claims = s.claims.length
        ? s.claims
            .map(
              (c) => `
        <li class="claim">
          <p class="claim-text">${esc(c.text)}</p>
          <p class="claim-source">${esc(labels.source)}: ${
            c.source ? `<span class="mono">${esc(c.source)}</span>` : esc(labels.sourceMissing)
          }</p>
        </li>`,
            )
            .join('')
        : `<li class="claim"><p class="claim-source">—</p></li>`;
      return `
      <section class="report-section">
        <h2>${esc(s.title)}</h2>
        <ul class="claims">${claims}</ul>
      </section>`;
    })
    .join('');

  const reviewedLine = report.reviewed_by
    ? `${esc(labels.reviewedBy)}: ${esc(report.reviewed_by)} · ${esc(report.reviewed_at ?? '')}`
    : esc(labels.notReviewed);

  const html = `<!doctype html>
<html lang="${lang}" dir="${dir}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${esc(labels.brand)} — ${esc(report.event_id)}</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
    color: rgb(24 32 51);
    background: white;
    line-height: 1.55;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .wrap { max-width: 760px; margin: 0 auto; padding: 0 28px 48px; }
  .band {
    background: linear-gradient(135deg, ${navy} 0%, ${aqua} 100%);
    color: white;
    padding: 28px;
    text-align: ${dir === 'rtl' ? 'right' : 'left'};
  }
  .band .brand { font-size: 13px; font-weight: 700; letter-spacing: 0.12em; opacity: 0.9; }
  .band h1 { margin: 6px 0 0; font-size: 26px; font-weight: 700; }
  .band .eid { margin-top: 4px; font-size: 13px; opacity: 0.9; font-family: ui-monospace, 'SF Mono', Menlo, monospace; }
  .status {
    display: inline-block; margin: 20px 0 0;
    background: ${statusBg}; color: white;
    padding: 8px 16px; border-radius: 999px;
    font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase;
  }
  .status-meaning { margin: 8px 0 0; font-size: 12px; color: rgb(90 100 120); max-width: 60ch; }
  .meta { margin: 20px 0 0; padding: 12px 0; border-top: 1px solid rgb(220 229 236); border-bottom: 1px solid rgb(220 229 236); font-size: 12px; color: rgb(70 82 108); }
  .meta div { margin: 2px 0; }
  .mono { font-family: ui-monospace, 'SF Mono', Menlo, monospace; unicode-bidi: isolate; }
  .report-section { margin-top: 26px; page-break-inside: avoid; }
  .report-section h2 { font-size: 16px; font-weight: 700; color: ${navy}; margin: 0 0 8px; padding-bottom: 6px; border-bottom: 2px solid ${aqua}; }
  .claims { list-style: none; margin: 0; padding: 0; }
  .claim { margin: 0 0 12px; padding-inline-start: 12px; border-inline-start: 3px solid rgb(220 229 236); }
  .claim-text { margin: 0; font-size: 13px; white-space: pre-line; }
  .claim-source { margin: 4px 0 0; font-size: 11px; color: rgb(110 120 140); }
  .footer { margin-top: 36px; padding-top: 12px; border-top: 1px solid rgb(220 229 236); font-size: 11px; color: rgb(110 120 140); }
  @media print { .band { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
</style>
</head>
<body>
  <div class="band">
    <div class="brand">${esc(labels.brand)}</div>
    <h1>${esc(labels.docTitle)}</h1>
    <div class="eid">${esc(labels.eventLabel)}: ${esc(report.event_id)}</div>
  </div>
  <div class="wrap">
    <div class="status">${esc(statusText)}</div>
    <p class="status-meaning">${esc(statusMeaning)}</p>
    <div class="meta">
      <div>${esc(labels.generatedAt)}: <span class="mono">${esc(report.generated_at)}</span></div>
      <div>${esc(labels.reviewedAt)}: <span class="mono">${esc(report.reviewed_at ?? labels.notReviewed)}</span></div>
      <div>${reviewedLine}</div>
    </div>
    ${sectionsHtml}
    <div class="footer">
      ${esc(labels.footer)} · ${esc(labels.brand)} · <span class="mono">${esc(report.report_id)}</span>
    </div>
  </div>
  <script>window.addEventListener('load', function () { window.focus(); window.print(); });</script>
</body>
</html>`;

  const win = window.open('', '_blank');
  if (!win) return false; // popup blocked — the caller surfaces this to the user
  win.document.open();
  win.document.write(html);
  win.document.close();
  return true;
}
