import { useTranslation } from 'react-i18next';
import { API_BASE } from '../api/client';
import type { AlertRow } from '../api/live';
import { BAND_CLASS } from '../api/types';
import { Link } from './Link';
import { ValueWithUnit } from './ValueWithUnit';

/** One alert, as a card. Phase 8 asks for a reusable alert row/card built even
 *  though the feed is empty today (the exposure engine reaches no named zone), so
 *  it is reviewable on the specimen route with sample data and ready the day a run
 *  reaches a zone.
 *
 *  Every field comes from AlertRow: severity badge (risk_level through BAND_CLASS,
 *  never colour alone — the band name is printed) + risk_score, the reef zone name
 *  (resolved from reef_zone_id when the caller supplies a map, id otherwise), the
 *  issued timestamp, the locale headline, the arrival window (null is a gap, never
 *  0–0), and a link into the stored run behind it. */

function formatInstant(iso: string, lang: 'en' | 'ar'): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  // Western digits in both languages and UTC, so an alert time can be compared
  // with the run it came from rather than the viewer's local zone.
  return new Intl.DateTimeFormat(lang === 'ar' ? 'ar-JO-u-nu-latn' : 'en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(d);
}

export function AlertCard({ alert, zoneName }: { alert: AlertRow; zoneName?: string | null }) {
  const { t, i18n } = useTranslation('pages');
  const lang = i18n.language.startsWith('ar') ? 'ar' : 'en';
  const issued = formatInstant(alert.issued_at, lang);
  const win = alert.arrival_window_hours;
  const headline = lang === 'ar' ? alert.headline_ar : alert.headline_en;

  return (
    <article data-alert-card="true" className="flex flex-col gap-3 glass-panel p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`inline-block border px-1.5 py-0.5 text-2xs ${BAND_CLASS[alert.risk_level]}`}>
              {t(`common:hazard.${alert.risk_level}`)}
            </span>
            <ValueWithUnit value={alert.risk_score} digits={1} provenance="modelled" />
          </div>
          <Link
            to={`/reef-zones/${encodeURIComponent(alert.reef_zone_id)}`}
            className="text-sm font-semibold hover:underline"
          >
            {zoneName ?? alert.reef_zone_id}
          </Link>
          <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="num font-mono text-2xs text-ink-2">
            {alert.reef_zone_id}
          </span>
        </div>
        {issued ? (
          <time dateTime={alert.issued_at} className="text-2xs text-ink-2">
            {t('time.utc', { when: issued })}
          </time>
        ) : null}
      </div>

      {/* Headline is API text — rendered verbatim, not translated in the UI. */}
      <p className="m-0 max-w-prose text-xs text-ink-2">{headline}</p>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-2xs text-ink-2">
        <span className="inline-flex items-center gap-1.5">
          <span className="font-semibold uppercase tracking-wide">{t('alerts.col.window')}</span>
          {win ? (
            <span className="inline-flex items-baseline gap-1">
              <ValueWithUnit value={win[0]} digits={0} provenance="modelled" />
              <span aria-hidden="true">–</span>
              <ValueWithUnit value={win[1]} digits={0} unit={t('units.hours')} provenance="modelled" />
            </span>
          ) : (
            <ValueWithUnit value={null} />
          )}
        </span>
        {/* Leaves the app for the stored run on the API — the only place the run
            behind an alert can actually be inspected. */}
        <a
          href={`${API_BASE}/api/v1/exposure/runs/${encodeURIComponent(alert.source_run_id)}`}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 underline"
          title={t('alerts.runLinkHint')}
        >
          <span className="font-semibold uppercase tracking-wide">{t('alerts.col.run')}</span>
          <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="num font-mono">
            {alert.source_run_id}
          </span>
        </a>
      </div>
    </article>
  );
}
