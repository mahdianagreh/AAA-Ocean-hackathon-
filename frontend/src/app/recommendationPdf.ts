/** Client-side themed PDF export for a "Recommended Response" swarm run
 *  (the full-page view at /dashboard/recommendations/:id).
 *
 *  Same mechanism as `reportPdf.ts` and for the same reason: no PDF library is
 *  bundled, so this assembles a self-contained themed HTML document, opens it
 *  in a new window and hands it to the browser's own "Save as PDF". Zero
 *  runtime fetches, offline-safe.
 *
 *  The caller (RecommendationPage) resolves every label and role/verdict
 *  string through i18n *before* calling this — this module only lays out
 *  already-resolved text, exactly like `ReportOut`'s claims arrive pre-resolved
 *  from the backend. `evidence_cited` is rendered as the plain strings the
 *  backend returns; it is not a `Citation` object with an excerpt or score, and
 *  this must not imply otherwise. */

export interface RecommendationPdfTurn {
  roleLabel: string;
  content: string;
  evidence: string[];
}

export interface RecommendationPdfRound {
  round: number;
  turns: RecommendationPdfTurn[];
}

export interface RecommendationPdfVerdict {
  verdictLabel: string;
  reasoning: string;
  evidence: string[];
}

export interface RecommendationPdfGap {
  severityLabel: string | null;
  description: string;
}

export interface RecommendationPdfData {
  eventId: string | null;
  runId: string;
  statusLabel: string;
  model: string;
  triggeredByText: string;
  createdAt: string;
  completedAt: string | null;
  briefEntries: { key: string; value: string }[];
  rounds: RecommendationPdfRound[];
  verdicts: RecommendationPdfVerdict[];
  finalBody: string | null;
  contestedNote: string | null;
  failedMessage: string | null;
  convergedText: string;
  gaps: RecommendationPdfGap[];
  evidenceAll: string[];
}

export interface RecommendationPdfLabels {
  brand: string;
  docTitle: string;
  metaEvent: string;
  metaRun: string;
  metaStatus: string;
  metaModel: string;
  metaTriggeredBy: string;
  metaCreated: string;
  metaCompleted: string;
  notCompleted: string;
  briefSection: string;
  briefEmpty: string;
  transcriptSection: string;
  transcriptEmpty: string;
  transcriptRound: string;
  evidenceLabel: string;
  evidenceNone: string;
  verdictsSection: string;
  verdictsEmpty: string;
  resultSection: string;
  resultNone: string;
  limitationsSection: string;
  limitationsEmpty: string;
  evidenceSection: string;
  evidenceEmpty: string;
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
export function downloadRecommendationPdf(
  data: RecommendationPdfData,
  opts: { lang: 'en' | 'ar'; labels: RecommendationPdfLabels },
): boolean {
  const { lang, labels } = opts;
  const dir = lang === 'ar' ? 'rtl' : 'ltr';
  const navy = tokenValue('--brand-navy', 'rgb(10 31 77)');
  const aqua = tokenValue('--brand-aqua', 'rgb(0 183 195)');

  const evidenceHtml = (evidence: string[]) =>
    evidence.length
      ? `<ul class="evidence">${evidence.map((e) => `<li>${esc(e)}</li>`).join('')}</ul>`
      : `<p class="evidence-none">${esc(labels.evidenceNone)}</p>`;

  const briefHtml = data.briefEntries.length
    ? `<dl class="brief">${data.briefEntries
        .map((e) => `<div><dt>${esc(e.key)}</dt><dd>${esc(e.value)}</dd></div>`)
        .join('')}</dl>`
    : `<p class="empty">${esc(labels.briefEmpty)}</p>`;

  const transcriptHtml = data.rounds.length
    ? data.rounds
        .map(
          (r) => `
      <div class="round">
        <h3>${esc(labels.transcriptRound)} ${r.round}</h3>
        <ul class="turns">
          ${r.turns
            .map(
              (t) => `
          <li class="turn">
            <p class="turn-role">${esc(t.roleLabel)}</p>
            <p class="turn-content">${esc(t.content)}</p>
            <p class="turn-evidence-label">${esc(labels.evidenceLabel)}</p>
            ${evidenceHtml(t.evidence)}
          </li>`,
            )
            .join('')}
        </ul>
      </div>`,
        )
        .join('')
    : `<p class="empty">${esc(labels.transcriptEmpty)}</p>`;

  const verdictsHtml = data.verdicts.length
    ? `<ul class="verdicts">${data.verdicts
        .map(
          (v) => `
      <li class="verdict">
        <p class="verdict-line"><strong>${esc(v.verdictLabel)}</strong> — ${esc(v.reasoning)}</p>
        ${evidenceHtml(v.evidence)}
      </li>`,
        )
        .join('')}</ul>`
    : `<p class="empty">${esc(labels.verdictsEmpty)}</p>`;

  const resultHtml = data.failedMessage
    ? `<p class="failed">${esc(data.failedMessage)}</p>`
    : data.finalBody
      ? `
      <p class="final-body">${esc(data.finalBody)}</p>
      ${data.contestedNote ? `<p class="contested">${esc(data.contestedNote)}</p>` : ''}
      <p class="converged">${esc(data.convergedText)}</p>`
      : `<p class="empty">${esc(labels.resultNone)}</p>`;

  const gapsHtml = data.gaps.length
    ? `<ul class="gaps">${data.gaps
        .map(
          (g) => `
      <li class="gap">
        ${g.severityLabel ? `<span class="gap-severity">${esc(g.severityLabel)}</span>` : ''}
        <span>${esc(g.description)}</span>
      </li>`,
        )
        .join('')}</ul>`
    : `<p class="empty">${esc(labels.limitationsEmpty)}</p>`;

  const html = `<!doctype html>
<html lang="${lang}" dir="${dir}">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${esc(labels.brand)} — ${esc(data.runId)}</title>
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
  .meta { margin: 20px 0 0; padding: 12px 0; border-top: 1px solid rgb(220 229 236); border-bottom: 1px solid rgb(220 229 236); font-size: 12px; color: rgb(70 82 108); }
  .meta div { margin: 2px 0; }
  .mono { font-family: ui-monospace, 'SF Mono', Menlo, monospace; unicode-bidi: isolate; }
  section { margin-top: 26px; page-break-inside: avoid; }
  section h2 { font-size: 16px; font-weight: 700; color: ${navy}; margin: 0 0 8px; padding-bottom: 6px; border-bottom: 2px solid ${aqua}; }
  section h3 { font-size: 13px; font-weight: 700; color: rgb(70 82 108); margin: 16px 0 6px; }
  .empty, .evidence-none { margin: 0; font-size: 12px; color: rgb(110 120 140); font-style: italic; }
  .brief { margin: 0; display: grid; grid-template-columns: 1fr; gap: 4px; }
  .brief div { display: flex; gap: 6px; font-size: 12px; }
  .brief dt { margin: 0; font-weight: 700; color: rgb(70 82 108); }
  .brief dd { margin: 0; }
  .turns { list-style: none; margin: 0; padding: 0; }
  .turn { margin: 0 0 12px; padding-inline-start: 12px; border-inline-start: 3px solid ${aqua}; }
  .turn-role { margin: 0; font-size: 12px; font-weight: 700; }
  .turn-content { margin: 4px 0; font-size: 13px; white-space: pre-line; }
  .turn-evidence-label { margin: 6px 0 2px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: rgb(110 120 140); }
  .evidence { margin: 0; padding-inline-start: 18px; font-size: 11px; color: rgb(70 82 108); }
  .verdicts { list-style: none; margin: 0; padding: 0; }
  .verdict { margin: 0 0 12px; padding-inline-start: 12px; border-inline-start: 3px solid rgb(220 229 236); }
  .verdict-line { margin: 0 0 4px; font-size: 13px; }
  .final-body { margin: 0; font-size: 14px; white-space: pre-line; }
  .contested { margin: 10px 0 0; padding: 10px; border-inline-start: 4px solid rgb(200 140 20); background: rgb(250 246 235); font-size: 12px; }
  .converged { margin: 10px 0 0; font-size: 12px; color: rgb(70 82 108); }
  .failed { margin: 0; font-size: 13px; color: rgb(185 60 39); font-weight: 700; }
  .gaps { list-style: none; margin: 0; padding: 0; }
  .gap { margin: 0 0 8px; display: flex; gap: 8px; align-items: baseline; font-size: 12px; }
  .gap-severity { flex-shrink: 0; padding: 2px 6px; border: 1px solid rgb(220 229 236); border-radius: 999px; font-size: 10px; font-weight: 700; text-transform: uppercase; }
  .footer { margin-top: 36px; padding-top: 12px; border-top: 1px solid rgb(220 229 236); font-size: 11px; color: rgb(110 120 140); }
  @media print { .band { -webkit-print-color-adjust: exact; print-color-adjust: exact; } }
</style>
</head>
<body>
  <div class="band">
    <div class="brand">${esc(labels.brand)}</div>
    <h1>${esc(labels.docTitle)}</h1>
  </div>
  <div class="wrap">
    <div class="meta">
      <div>${esc(labels.metaEvent)}: <span class="mono">${esc(data.eventId ?? '—')}</span></div>
      <div>${esc(labels.metaRun)}: <span class="mono">${esc(data.runId)}</span></div>
      <div>${esc(labels.metaStatus)}: ${esc(data.statusLabel)}</div>
      <div>${esc(labels.metaModel)}: <span class="mono">${esc(data.model)}</span></div>
      <div>${esc(labels.metaTriggeredBy)}: ${esc(data.triggeredByText)}</div>
      <div>${esc(labels.metaCreated)}: <span class="mono">${esc(data.createdAt)}</span></div>
      <div>${esc(labels.metaCompleted)}: <span class="mono">${esc(data.completedAt ?? labels.notCompleted)}</span></div>
    </div>

    <section>
      <h2>${esc(labels.briefSection)}</h2>
      ${briefHtml}
    </section>

    <section>
      <h2>${esc(labels.transcriptSection)}</h2>
      ${transcriptHtml}
    </section>

    <section>
      <h2>${esc(labels.verdictsSection)}</h2>
      ${verdictsHtml}
    </section>

    <section>
      <h2>${esc(labels.resultSection)}</h2>
      ${resultHtml}
    </section>

    <section>
      <h2>${esc(labels.limitationsSection)}</h2>
      ${gapsHtml}
    </section>

    <section>
      <h2>${esc(labels.evidenceSection)}</h2>
      ${data.evidenceAll.length ? evidenceHtml(data.evidenceAll) : `<p class="empty">${esc(labels.evidenceEmpty)}</p>`}
    </section>

    <div class="footer">
      ${esc(labels.footer)} · <span class="mono">${esc(data.runId)}</span>
    </div>
  </div>
  <script>window.addEventListener('load', function () { window.focus(); window.print(); });</script>
</body>
</html>`;

  const win = window.open('', '_blank');
  if (!win) return false;
  win.document.open();
  win.document.write(html);
  win.document.close();
  return true;
}
