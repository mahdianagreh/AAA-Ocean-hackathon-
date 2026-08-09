import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fetchAlerts, fetchReefZonesLive, type AlertRow } from '../api/live';
import { AlertCard } from '../components/AlertCard';
import { CaveatList } from '../components/CaveatList';
import { BAND_CLASS, type HazardBand } from '../api/types';
import { Empty, Loading } from '../components/States';
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

/** Delegates to the one shared caveat treatment (CaveatCard, via CaveatList), so
 *  every caveat on every page renders identically — severity icon, accent border,
 *  source pill — per Phase 8 Global Rule 2, instead of the old flat gray box that
 *  put a low-contrast source line on --surface-2 and localized severity from a
 *  second, drifted vocabulary. Kept as a thin wrapper so its three call sites
 *  (this page, ReplayPage, ReefZonesPage) need no change. */
export function Caveats({ items, title }: { items: unknown[]; title?: string }) {
  const { t } = useTranslation('pages');
  return <CaveatList items={items} title={title ?? t('caveats.title')} />;
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

export function AlertsPage() {
  const { t } = useTranslation('pages');

  // `null` is "still asking", `[]` is "asked, got nothing" — the whole point of
  // this page is that those two render differently.
  const [rows, setRows] = useState<AlertRowFull[] | null>(null);
  const [zoneNames, setZoneNames] = useState<Record<string, string>>({});

  useEffect(() => {
    let live = true;
    void fetchAlerts().then((a) => {
      if (live) setRows(a as AlertRowFull[]);
    });
    // Best-effort zone-name resolution so a card can read "Power Station Reef"
    // rather than R-03; falls back to the id when unavailable (offline/fixtures).
    void fetchReefZonesLive().then((z) => {
      if (!live || !z) return;
      const map: Record<string, string> = {};
      for (const zone of z) if (zone.zone_name) map[zone.reef_zone_id] = zone.zone_name;
      setZoneNames(map);
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
          <Empty
            icon={
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
            }
            title={t('alerts.emptyTitle')}
            body={t('alerts.emptyBody')}
          />
        ) : (
          <>
            <p className="m-0 text-2xs text-ink-2">
              {/* `n`, never i18next's `count`: `count` switches on plural rules,
                  and Arabic has six forms to English's two — the two locale
                  files would then be required to hold different key sets, which
                  the parity check forbids. */}
              {t('alerts.count', { n: sorted.length })}
            </p>
            <ul
              className="m-0 grid list-none gap-3 p-0"
              style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(20rem, 1fr))' }}
            >
              {sorted.map((a) => (
                <li key={a.alert_id}>
                  <AlertCard alert={a} zoneName={zoneNames[a.reef_zone_id]} />
                </li>
              ))}
            </ul>
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
