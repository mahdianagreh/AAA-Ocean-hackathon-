import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { API_BASE } from '../api/client';
import { fetchAlerts, type AlertRow } from '../api/live';
import { BAND_CLASS, type HazardBand } from '../api/types';
import { Link } from '../components/Link';
import { Empty, Loading } from '../components/States';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { PageShell, Section } from '../shell/PageShell';

/** The stored alert feed, at /alerts.
 *
 *  Everything here is `GET /api/v1/alerts`. There is no fixture behind it and no
 *  fallback: an alert is a claim that a named reef zone was reached, and a claim
 *  we invented offline is worse than no claim at all.
 *
 *  `[]` is the expected answer today, not a failure. The exposure engine reports
 *  "no reef zone is reached from AQ-O01 within 24 h — the nearest is R-01 at
 *  1923 m and the plume's largest modelled extent is 418 m", which is a *stated
 *  absence*, so the feed correctly has nothing to list. That is rendered as an
 *  empty state that says why, never as an error and never as a silent blank —
 *  "not reached" and "the feed broke" must not look the same on stage.
 */

/** Every live endpoint attaches `caveats`, and dropping them is how a hedged
 *  number becomes an unhedged one. Rendered here rather than in five copies:
 *  the file budget for this change is five route files, so the two pieces every
 *  page needs live in the page that uses both most heavily and are imported.
 *  Both are components, so `react/only-export-components` is satisfied. */
interface Caveat {
  field: string | null;
  message: string;
  severity: string | null;
  source: string | null;
}

/** The API types `caveats` as `unknown[]` — four of the five endpoints return
 *  bare dicts — so it is narrowed at the boundary rather than asserted. An entry
 *  that is not shaped like a caveat is dropped, never rendered as `[object
 *  Object]`. */
function asCaveat(x: unknown): Caveat | null {
  if (!x || typeof x !== 'object') return null;
  const o = x as Record<string, unknown>;
  if (typeof o.message !== 'string') return null;
  return {
    field: typeof o.field === 'string' ? o.field : null,
    message: o.message,
    severity: typeof o.severity === 'string' ? o.severity : null,
    source: typeof o.source === 'string' ? o.source : null,
  };
}

export function Caveats({ items, title }: { items: unknown[]; title?: string }) {
  const { t } = useTranslation('pages');
  const rows = items.map(asCaveat).filter((c): c is Caveat => c !== null);
  if (rows.length === 0) return null;

  return (
    <section className="flex flex-col gap-2 rule bg-surface-2 p-3" data-caveats="true">
      <h3 className="m-0 text-2xs font-semibold text-ink-2">{title ?? t('caveats.title')}</h3>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {rows.map((c, i) => (
          <li key={`${c.field ?? 'caveat'}-${i}`} className="flex flex-col gap-0.5">
            <span className="text-2xs font-semibold text-ink-2">
              {t(`caveats.severity.${c.severity ?? 'info'}`, {
                defaultValue: c.severity ?? '',
              })}
              {c.field ? ` · ${c.field}` : ''}
            </span>
            {/* The message is API text, not UI copy — it is not translated here,
                because a caveat paraphrased by the frontend is no longer the
                caveat the backend stands behind. */}
            <p className="m-0 max-w-prose text-2xs text-ink-2">{c.message}</p>
            {c.source ? (
              <p className="m-0 text-2xs text-ink-3">{t('caveats.source', { source: c.source })}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** An identifier — `AQ-C01`, `R-08`, `sim_01KZ…`. Isolated the same way
 *  ValueWithUnit isolates a measurement: without it, RTL reorders the segments
 *  and `R-08` can render with its digits leading. */
export function IdText({ children, className }: { children: string; className?: string }) {
  return (
    <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className={`font-mono num ${className ?? ''}`}>
      {children}
    </span>
  );
}

/** The five bands, as a chip. Never colour alone — the band name is always
 *  printed next to the fill (09 rule: no colour-only meaning). */
export function BandChip({ band }: { band: HazardBand }) {
  const { t } = useTranslation('pages');
  return (
    <span className={`inline-block border px-1.5 py-0.5 text-2xs ${BAND_CLASS[band]}`}>
      {t(`common:hazard.${band}`)}
    </span>
  );
}

/** Alerts carry a `caveats` array the shared type does not model yet, and
 *  live.ts is owned elsewhere in this change — so it is widened locally rather
 *  than dropped. */
type AlertRowFull = AlertRow & { caveats?: unknown[] };

function formatInstant(iso: string, lang: 'en' | 'ar'): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  // Western digits in both languages (06 §5), and UTC rather than a local zone:
  // an alert timestamp rendered in whichever zone the browser happens to sit in
  // cannot be compared with the run it came from.
  return new Intl.DateTimeFormat(lang === 'ar' ? 'ar-JO-u-nu-latn' : 'en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(d);
}

export function AlertsPage() {
  const { t, i18n } = useTranslation('pages');
  const lang = i18n.language.startsWith('ar') ? 'ar' : 'en';

  // `null` is "still asking", `[]` is "asked, got nothing" — the whole point of
  // this page is that those two render differently.
  const [rows, setRows] = useState<AlertRowFull[] | null>(null);

  useEffect(() => {
    let live = true;
    void fetchAlerts().then((a) => {
      if (live) setRows(a as AlertRowFull[]);
    });
    return () => {
      live = false;
    };
  }, []);

  const sorted = rows
    ? [...rows].sort((a, b) => Date.parse(b.issued_at) - Date.parse(a.issued_at))
    : [];

  // Deduped: every alert from one run repeats the same run-level caveats, and
  // eight copies of the same sentence reads as noise rather than as a warning.
  const seen = new Set<string>();
  const caveats: unknown[] = [];
  for (const r of sorted) {
    for (const c of r.caveats ?? []) {
      const parsed = asCaveat(c);
      if (!parsed || seen.has(parsed.message)) continue;
      seen.add(parsed.message);
      caveats.push(c);
    }
  }

  return (
    <PageShell title={t('alerts.title')} lede={t('alerts.lede')}>
      <Section label={t('alerts.feedLabel')}>
        {rows === null ? (
          <Loading what={t('alerts.loading')} />
        ) : sorted.length === 0 ? (
          <Empty title={t('alerts.emptyTitle')} body={t('alerts.emptyBody')} />
        ) : (
          <>
            <p className="m-0 text-2xs text-ink-2">
              {/* `n`, never i18next's `count`: `count` switches on plural rules,
                  and Arabic has six forms to English's two — the two locale
                  files would then be required to hold different key sets, which
                  the parity check forbids. */}
              {t('alerts.count', { n: sorted.length })}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-xs">
                <caption className="sr-only">{t('alerts.tableCaption')}</caption>
                <thead>
                  <tr className="border-b border-hairline text-start text-2xs text-ink-2">
                    <th scope="col" className="p-2 text-start font-semibold">
                      {t('alerts.col.zone')}
                    </th>
                    <th scope="col" className="p-2 text-start font-semibold">
                      {t('alerts.col.band')}
                    </th>
                    <th scope="col" className="p-2 text-start font-semibold">
                      {t('alerts.col.score')}
                    </th>
                    <th scope="col" className="p-2 text-start font-semibold">
                      {t('alerts.col.window')}
                    </th>
                    <th scope="col" className="p-2 text-start font-semibold">
                      {t('alerts.col.issued')}
                    </th>
                    <th scope="col" className="p-2 text-start font-semibold">
                      {t('alerts.col.headline')}
                    </th>
                    <th scope="col" className="p-2 text-start font-semibold">
                      {t('alerts.col.run')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((a) => {
                    const issued = formatInstant(a.issued_at, lang);
                    const win = a.arrival_window_hours;
                    return (
                      <tr key={a.alert_id} className="border-b border-hairline align-top">
                        <th scope="row" className="p-2 text-start font-normal">
                          <Link to={`/reef-zones/${a.reef_zone_id}`} className="underline">
                            <IdText>{a.reef_zone_id}</IdText>
                          </Link>
                        </th>
                        <td className="p-2">
                          <BandChip band={a.risk_level} />
                        </td>
                        <td className="p-2">
                          <ValueWithUnit value={a.risk_score} digits={1} provenance="modelled" />
                        </td>
                        <td className="p-2">
                          {win ? (
                            <span className="inline-flex items-baseline gap-1">
                              <ValueWithUnit value={win[0]} digits={0} provenance="modelled" />
                              <span aria-hidden="true">–</span>
                              <ValueWithUnit
                                value={win[1]}
                                digits={0}
                                unit={t('units.hours')}
                                provenance="modelled"
                              />
                            </span>
                          ) : (
                            <ValueWithUnit value={null} />
                          )}
                        </td>
                        <td className="p-2">
                          {issued ? (
                            <time dateTime={a.issued_at} className="text-ink-2">
                              {t('time.utc', { when: issued })}
                            </time>
                          ) : (
                            <ValueWithUnit value={null} />
                          )}
                        </td>
                        <td className="max-w-prose p-2">
                          {lang === 'ar' ? a.headline_ar : a.headline_en}
                        </td>
                        <td className="p-2">
                          {/* Not a <Link>: this leaves the app for the stored run
                              on the API itself, which is the only place the run
                              behind an alert can actually be inspected. */}
                          <a
                            href={`${API_BASE}/api/v1/exposure/runs/${encodeURIComponent(a.source_run_id)}`}
                            target="_blank"
                            rel="noreferrer"
                            className="underline"
                            title={t('alerts.runLinkHint')}
                          >
                            <IdText>{a.source_run_id}</IdText>
                          </a>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Section>

      {caveats.length > 0 ? (
        <Section label={t('caveats.sectionLabel')}>
          <Caveats items={caveats} />
        </Section>
      ) : null}
    </PageShell>
  );
}
