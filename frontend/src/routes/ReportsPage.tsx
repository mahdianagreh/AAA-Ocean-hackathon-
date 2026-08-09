import { useEffect, useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, PageShell, Section } from '../shell/PageShell';
import { StatusBadge } from '../components/StatusBadge';
import {
  fetchEvents,
  fetchReport,
  generateReport,
  reviewReport,
  type EventRow,
  type ReportOut,
} from '../api/live';
import { loadEventSeries } from '../api/event';

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
  const eventSelectId = useId();
  const lookupId = useId();
  const reviewerId = useId();

  const [eventId, setEventId] = useState<string | null>(null);
  const [events, setEvents] = useState<EventRow[] | null>(null);

  /** Session-only. See the file docstring: there is nothing to load this from. */
  const [reports, setReports] = useState<ReportOut[]>([]);
  const [lookup, setLookup] = useState('');
  const [reviewer, setReviewer] = useState('');
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
    const by = reviewer.trim();
    if (!by) return;
    setBusyId(id);
    const report = await reviewReport(id, by);
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
            <Card>
              <div className="flex flex-wrap items-end gap-4">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor={reviewerId} className="text-xs font-semibold">
                    {t('reports.reviewerLabel')}
                  </label>
                  <input
                    id={reviewerId}
                    type="text"
                    dir="auto"
                    value={reviewer}
                    onChange={(e) => setReviewer(e.target.value)}
                    className="h-10 w-64 rounded-md border border-hairline bg-surface/50 px-3 text-sm text-ink hover:border-accent focus:border-accent outline-none transition-colors"
                  />
                </div>
                <p className="m-0 max-w-prose text-2xs text-ink-2">{t('reports.reviewerHint')}</p>
              </div>
            </Card>

            {reports.map((r) => (
              <ReportCard
                key={r.report_id}
                report={r}
                canReview={Boolean(reviewer.trim())}
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
  const { t } = useTranslation('tools');
  const drafted = report.status === 'ai_drafted';

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h3 className="m-0 flex flex-wrap items-center gap-2 text-sm font-semibold">
            <span dir="ltr" className="font-mono num">
              {report.event_id}
            </span>
            <StatusBadge variant={report.status} />
          </h3>
          <code dir="ltr" className="font-mono num text-2xs text-ink-3">
            {report.report_id}
          </code>
        </div>
        {drafted ? (
          <button
            type="button"
            onClick={onReview}
            disabled={!canReview || busy}
            className="h-9 rounded-full border-2 border-accent px-4 text-xs font-bold text-accent hover:bg-accent/10 transition-colors disabled:opacity-50 cursor-pointer"
          >
            {busy ? t('reports.reviewing') : t('reports.markReviewed')}
          </button>
        ) : null}
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
        <div>
          <dt className="inline">{t('reports.reviewedBy')} </dt>
          <dd className="m-0 inline" dir="auto">
            {report.reviewed_by ?? t('reports.notReviewed')}
          </dd>
        </div>
      </dl>

      {report.sections.map((s) => (
        <section key={s.title} className="flex flex-col gap-2">
          <h4 dir="auto" className="m-0 text-xs font-bold">
            {s.title}
          </h4>
          {!s.claims.length ? (
            <p className="m-0 text-2xs text-ink-3">{t('reports.noClaims')}</p>
          ) : (
            <ul className="m-0 flex list-none flex-col gap-3 p-0">
              {s.claims.map((c, i) => (
                <li
                  key={`${s.title}-${i}`}
                  className="flex flex-col gap-1 border-s-2 border-hairline-2 ps-3"
                >
                  {/* Verbatim. A forensic report that paraphrases its own claims
                      is no longer forensic. */}
                  <p dir="auto" className="m-0 max-w-prose whitespace-pre-line text-xs text-ink-2">
                    {c.text}
                  </p>
                  <span className="text-2xs text-ink-3">
                    {t('reports.claimSource')}{' '}
                    {c.source ? (
                      <span dir="auto" className="text-ink-2">
                        {c.source}
                      </span>
                    ) : (
                      <span className="text-ink-3">{t('reports.claimSourceMissing')}</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </Card>
  );
}
