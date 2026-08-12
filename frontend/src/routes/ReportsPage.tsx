import { useEffect, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, PageShell, Section } from '../shell/PageShell';
import { CaveatCard } from '../components/CaveatCard';
import {
  fetchEvents,
  fetchReport,
  generateReport,
  reviewReport,
  type EventRow,
  type ReportOut,
} from '../api/live';
import { loadEventSeries } from '../api/event';
import { useAuth } from '../app/AuthContext';
import { downloadReportPdf } from '../app/reportPdf';

/** Forensic event reports, at /reports.
 *
 *  THERE IS NO LIST ENDPOINT. GET /api/v1/reports does not exist — the API
 *  offers generate, read-one-by-id, and mark-reviewed, and nothing that
 *  enumerates. So this page keeps the reports generated during the session in
 *  component state and says, on screen and permanently, that a persistent list
 *  is not available for that reason. The alternative — inventing a list, or
 *  quietly showing an empty one — teaches a reader that no reports exist, which
 *  is a different and false claim. A report id can still be pasted in and
 *  fetched, which is the honest substitute for browsing.
 *
 *  THE STATUS BADGE IS NEVER DEFAULTED AWAY. `ai_drafted` and `human_reviewed`
 *  are visually and textually distinct on every report, in the header and beside
 *  the id, because a drafted report shown without it is indistinguishable from a
 *  reviewed one — and that is the exact failure this page is guarding against.
 *  It is text plus border, never colour alone.
 */

type Notice =
  | { kind: 'none' }
  | { kind: 'generating' }
  | { kind: 'failed'; what: 'generate' | 'fetch' | 'review' };

export function ReportsPage() {
  const { t } = useTranslation('tools');
  // The identity the backend will record — `current_user.email or .sub`, mirrored
  // here so the screen names the same person the audit trail will.
  const { session } = useAuth();
  const signedInAs = session?.user?.email ?? session?.user?.id ?? null;
  const eventSelectId = useId();
  const lookupId = useId();

  const [eventId, setEventId] = useState<string | null>(null);
  const [events, setEvents] = useState<EventRow[] | null>(null);

  /** Session-only. See the file docstring: there is nothing to load this from. */
  const [reports, setReports] = useState<ReportOut[]>([]);
  const [lookup, setLookup] = useState('');
  const [notice, setNotice] = useState<Notice>({ kind: 'none' });
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void loadEventSeries()
      .then((s) => live && setEventId(s.event_id))
      .catch(() => {
        /* the selector falls back to the events list */
      });
    void fetchEvents().then((rows) => {
      if (!live) return;
      setEvents(rows);
      setEventId((current) => current ?? rows?.[0]?.event_id ?? null);
    });
    return () => {
      live = false;
    };
  }, []);

  const options = events?.length ? events.map((e) => e.event_id) : eventId ? [eventId] : [];

  /** Newest first, and a regenerated/reviewed report replaces its own row rather
   *  than appearing twice under the same id. */
  function upsert(report: ReportOut) {
    setReports((rows) => [report, ...rows.filter((r) => r.report_id !== report.report_id)]);
  }

  async function onGenerate() {
    if (!eventId) return;
    setNotice({ kind: 'generating' });
    const report = await generateReport(eventId);
    if (!report) {
      setNotice({ kind: 'failed', what: 'generate' });
      return;
    }
    setNotice({ kind: 'none' });
    upsert(report);
  }

  async function onLookup() {
    const id = lookup.trim();
    if (!id) return;
    const report = await fetchReport(id);
    if (!report) {
      setNotice({ kind: 'failed', what: 'fetch' });
      return;
    }
    setNotice({ kind: 'none' });
    upsert(report);
  }

  async function onReview(id: string) {
    if (!signedInAs) return;
    setBusyId(id);
    const report = await reviewReport(id);
    setBusyId(null);
    if (!report) {
      setNotice({ kind: 'failed', what: 'review' });
      return;
    }
    setNotice({ kind: 'none' });
    upsert(report);
  }

  return (
    <PageShell title={t('reports.title')} lede={t('reports.lede')}>
      <Section label={t('reports.generateSection')}>
        <Card>
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor={eventSelectId} className="text-xs font-semibold">
                {t('reports.eventLabel')}
              </label>
              <select
                id={eventSelectId}
                className="h-10 rounded-md border border-hairline bg-surface/50 px-3 text-sm text-ink hover:border-accent focus:border-accent outline-none transition-colors"
                value={eventId ?? ''}
                onChange={(e) => setEventId(e.target.value)}
                disabled={!options.length}
              >
                {options.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              onClick={() => void onGenerate()}
              disabled={!eventId || notice.kind === 'generating'}
              className="h-10 rounded-full px-5 text-sm font-bold premium-button hover:premium-button-hover disabled:opacity-50"
            >
              {notice.kind === 'generating' ? t('reports.generating') : t('reports.generate')}
            </button>
          </div>

          <div className="flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor={lookupId} className="text-xs font-semibold">
                {t('reports.lookupLabel')}
              </label>
              <input
                id={lookupId}
                type="text"
                dir="ltr"
                value={lookup}
                onChange={(e) => setLookup(e.target.value)}
                placeholder="report_…"
                className="h-10 w-64 rounded-md border border-hairline bg-surface/50 px-3 font-mono num text-sm text-ink placeholder:text-ink-3 hover:border-accent focus:border-accent outline-none transition-colors"
              />
            </div>
            <button
              type="button"
              onClick={() => void onLookup()}
              disabled={!lookup.trim()}
              className="h-10 rounded-full border-2 border-accent px-5 text-sm font-bold text-accent hover:bg-accent/10 transition-colors disabled:opacity-50 cursor-pointer"
            >
              {t('reports.lookup')}
            </button>
          </div>

          {notice.kind === 'failed' ? (
            <p role="alert" className="m-0 text-xs font-semibold text-ink">
              {t(`reports.failed.${notice.what}`)}
            </p>
          ) : null}

          {/* Permanent, not a toast. The absence of a list is a property of the
              API, not a transient condition. */}
          <div className="flex flex-col gap-1 rounded-md border border-hairline-2 bg-surface-2 p-4">
            <h3 className="m-0 text-xs font-bold">{t('reports.noListTitle')}</h3>
            <p className="m-0 max-w-prose text-xs text-ink-2">{t('reports.noListBody')}</p>
            <p className="m-0 text-2xs text-ink-3">
              <code dir="ltr" className="font-mono num">
                GET /api/v1/reports
              </code>{' '}
              {t('reports.noListEndpoint')}
            </p>
          </div>
        </Card>
      </Section>

      <Section label={t('reports.sessionSection')}>
        {!reports.length ? (
          <Card>
            <h3 className="m-0 text-sm font-semibold">{t('reports.emptyTitle')}</h3>
            <p className="m-0 max-w-prose text-xs text-ink-2">{t('reports.emptyBody')}</p>
          </Card>
        ) : (
          <>
            {/* Phase 8, Track B: this used to be a free-text "reviewer" box, and
                the backend stopped trusting it — `review_report` records
                `current_user.email or .sub` from the verified session and ignores
                the body. A field whose value is silently discarded is worse than
                no field: someone types a colleague's name, the audit trail records
                a different one, and nothing on screen says so. The signed-in
                identity is shown instead, because that IS what gets recorded. */}
            <Card>
              <div className="flex flex-wrap items-center gap-4">
                {signedInAs ? (
                  <>
                    <span className="text-xs font-semibold">{t('reports.reviewerLabel')}</span>
                    <span dir="auto" className="text-sm text-ink">{signedInAs}</span>
                  </>
                ) : (
                  <p className="m-0 max-w-prose text-xs text-ink-2">{t('reports.reviewSignInRequired')}</p>
                )}
                <p className="m-0 max-w-prose text-2xs text-ink-2">{t('reports.reviewerHint')}</p>
              </div>
            </Card>

            {reports.map((r) => (
              <ReportCard
                key={r.report_id}
                report={r}
                canReview={Boolean(signedInAs)}
                busy={busyId === r.report_id}
                onReview={() => void onReview(r.report_id)}
              />
            ))}
          </>
        )}
      </Section>
    </PageShell>
  );
}


/** Is this the "Caveats carried with this run" section? Backend titles are
 *  English, but we also match Arabic in case they ever localise. */
function isCaveatsSection(title: string): boolean {
  return /caveat/i.test(title) || title.includes('تحفظ') || title.includes('تحفّظ');
}

/** A claim citation, collapsed by default with a Show-full-citation toggle. */
function Citation({ source }: { source: string | null }) {
  const { t } = useTranslation('tools');
  const [open, setOpen] = useState(false);
  if (!source) {
    return (
      <span className="text-2xs text-ink-3">
        {t('reports.claimSource')}: {t('reports.claimSourceMissing')}
      </span>
    );
  }
  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="inline-flex w-fit cursor-pointer items-center gap-1 text-2xs font-semibold text-accent hover:underline"
      >
        {open ? t('reports.hideCitation') : t('reports.showCitation')}
      </button>
      {open ? (
        <span dir="auto" className="text-2xs text-ink-2">
          {t('reports.claimSource')}:{' '}
          <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="num font-mono">
            {source}
          </span>
        </span>
      ) : null}
    </div>
  );
}

function ReportCard({
  report,
  canReview,
  busy,
  onReview,
}: {
  report: ReportOut;
  canReview: boolean;
  busy: boolean;
  onReview: () => void;
}) {
  const { t, i18n } = useTranslation('tools');
  const lang = i18n.language.startsWith('ar') ? 'ar' : 'en';
  const drafted = report.status === 'ai_drafted';
  const [pdfBlocked, setPdfBlocked] = useState(false);

  function onDownload() {
    const ok = downloadReportPdf(report, {
      lang,
      labels: {
        brand: 'AQABA AQUA AI',
        docTitle: t('reports.pdfTitle'),
        statusDrafted: t('reports.statusDrafted'),
        statusReviewed: t('reports.statusReviewed'),
        draftedMeaning: t('reports.draftedMeaning'),
        reviewedMeaning: t('reports.reviewedMeaning'),
        eventLabel: t('reports.eventLabel'),
        generatedAt: t('reports.generatedAt'),
        reviewedAt: t('reports.reviewedAt'),
        reviewedBy: t('reports.reviewedBy'),
        notReviewed: t('reports.notReviewed'),
        source: t('reports.claimSource'),
        sourceMissing: t('reports.claimSourceMissing'),
        footer: t('reports.pdfFooter'),
      },
    });
    setPdfBlocked(!ok);
  }

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1.5">
          {/* Event id in H2, per the header redesign. */}
          <h2 dir="ltr" className="m-0 font-mono num text-lg font-bold text-ink">
            {report.event_id}
          </h2>
          <code dir="ltr" className="font-mono num text-2xs text-ink-3">
            {report.report_id}
          </code>
        </div>
        <div className="flex flex-col items-end gap-2">
          {/* Prominent, solid status badge — never the thin outline it was. Both
              variants use an AA-safe solid pairing so it cannot be missed. */}
          {drafted ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-risk-high px-3 py-1 text-2xs font-bold uppercase tracking-wide text-risk-high-on" data-status-badge="ai_drafted">
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M8 2 15 14H1z" />
                <path d="M8 6.5v3.5" />
                <circle cx="8" cy="11.8" r="0.5" fill="currentColor" />
              </svg>
              {t('reports.statusDrafted')}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3 py-1 text-2xs font-bold uppercase tracking-wide text-ink-inverse" data-status-badge="human_reviewed">
              <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M3 8.5 6.5 12 13 4.5" />
              </svg>
              {t('reports.statusReviewed')}
            </span>
          )}
          <button
            type="button"
            onClick={onDownload}
            className="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-full border-2 border-accent px-4 text-xs font-bold text-accent transition-colors hover:bg-accent/10"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M8 2v8M4.5 6.5 8 10l3.5-3.5M3 13h10" />
            </svg>
            {t('reports.download')}
          </button>
          {pdfBlocked ? (
            <span role="alert" className="max-w-[12rem] text-end text-2xs text-risk-critical">
              {t('reports.pdfBlocked')}
            </span>
          ) : null}
        </div>
      </div>

      <p className="m-0 max-w-prose text-xs text-ink-2">
        {drafted ? t('reports.draftedMeaning') : t('reports.reviewedMeaning')}
      </p>

      <dl className="m-0 flex flex-wrap gap-x-6 gap-y-1 text-2xs text-ink-3">
        <div>
          <dt className="inline">{t('reports.generatedAt')} </dt>
          <dd className="m-0 inline font-mono num" dir="ltr">
            {report.generated_at}
          </dd>
        </div>
        <div>
          <dt className="inline">{t('reports.reviewedAt')} </dt>
          <dd className="m-0 inline font-mono num" dir="ltr">
            {report.reviewed_at ?? t('reports.notReviewed')}
          </dd>
        </div>
      </dl>

      {/* The review action, and its confirmed post-click state. */}
      {drafted ? (
        <button
          type="button"
          onClick={onReview}
          disabled={!canReview || busy}
          className="inline-flex h-10 w-fit cursor-pointer items-center justify-center rounded-md bg-ink px-5 text-sm font-bold text-ink-inverse transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? t('reports.reviewing') : t('reports.markReviewed')}
        </button>
      ) : (
        <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-surface-2 px-3 py-1.5 text-2xs font-semibold text-ink-2">
          <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="text-accent">
            <path d="M3 8.5 6.5 12 13 4.5" />
          </svg>
          {t('reports.reviewedBy')} <span dir="auto" className="text-ink">{report.reviewed_by}</span>
          {report.reviewed_at ? (
            <>
              {' · '}
              <span dir="ltr" className="num font-mono">{report.reviewed_at}</span>
            </>
          ) : null}
        </span>
      )}

      {report.sections.map((s) => (
        <section key={s.title} className="flex flex-col gap-3">
          <h3 dir="auto" className="m-0 text-sm font-bold text-ink">
            {s.title}
          </h3>
          {!s.claims.length ? (
            <p className="m-0 text-2xs text-ink-3">{t('reports.noClaims')}</p>
          ) : isCaveatsSection(s.title) ? (
            // The caveats section gets the shared CaveatCard treatment (Page 3).
            <div className="flex flex-col gap-3">
              {s.claims.map((c, i) => (
                <CaveatCard key={`${s.title}-${i}`} severity="note" message={c.text} source={c.source} />
              ))}
            </div>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {s.claims.map((c, i) => (
                <li
                  key={`${s.title}-${i}`}
                  className="flex flex-col gap-1.5 border-s-2 border-hairline-2 ps-3"
                >
                  {/* Verbatim. A forensic report that paraphrases its own claims
                      is no longer forensic. */}
                  <p dir="auto" className="m-0 max-w-prose whitespace-pre-line text-xs text-ink-2">
                    {c.text}
                  </p>
                  <Citation source={c.source} />
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </Card>
  );
}
