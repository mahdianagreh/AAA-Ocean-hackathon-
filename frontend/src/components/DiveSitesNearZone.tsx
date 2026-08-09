import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fetchDiveSites, type DiveSite } from '../api/live';
import { Empty, ErrorState, Loading } from './States';
import { ValueWithUnit } from './ValueWithUnit';
import { IdText } from '../routes/AlertsPage';

/** Dive sites joined to a reef zone, on /reef-zones/:id — feature p4-B.
 *
 *  The endpoint returns the geometric nearest-zone join only, joined by `osm_id`
 *  (never the name). It splits cleanly in two, and the UI splits with it:
 *
 *   - COASTAL: the ~10 sites within ~2 km — a trustworthy safety association.
 *     These are the useful rows, so they lead, as clean cards.
 *   - INLAND: Wadi Rum desert attractions the OSM `kind: dive` category also
 *     carries, tens of km away. The backend flags each with a caveat. Rather than
 *     repeat that identical paragraph 35 times — a wall of text that buries the
 *     coastal sites — the warning is stated ONCE for the whole group, and each
 *     row keeps the one thing that varies (its distance) plus its exact caveat on
 *     hover. Nothing is dropped; it is said once instead of thirty-five times.
 */
function siteName(s: DiveSite, lang: 'en' | 'ar'): string | null {
  return (lang === 'ar' ? s.name_ar : s.name_en) ?? s.name_en ?? s.name_ar;
}

function caveatText(s: DiveSite): string | undefined {
  const first = s.caveats[0] as { message?: string } | undefined;
  return first?.message;
}

export function DiveSitesNearZone({ zoneId }: { zoneId: string }) {
  const { t, i18n } = useTranslation('pages');
  const lang = i18n.language.startsWith('ar') ? 'ar' : 'en';
  const [sites, setSites] = useState<DiveSite[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    setSites(null);
    setFailed(false);
    void fetchDiveSites().then((s) => {
      if (!live) return;
      if (s === null) setFailed(true);
      else setSites(s);
    });
    return () => {
      live = false;
    };
  }, [zoneId]);

  if (failed) {
    return <ErrorState what={t('reefZone.diveSites.errorTitle')} message={t('reefZone.diveSites.errorBody')} />;
  }
  if (sites === null) {
    return <Loading what={t('reefZone.diveSites.loading')} />;
  }

  const near = sites
    .filter((s) => s.nearest_reef_zone_id === zoneId)
    .sort((a, b) => (a.distance_m ?? Infinity) - (b.distance_m ?? Infinity));

  if (near.length === 0) {
    return <Empty title={t('reefZone.diveSites.emptyTitle')} body={t('reefZone.diveSites.emptyBody')} />;
  }

  // The backend attaches a caveat exactly to the inland POIs; that flag is the
  // split, not a distance threshold re-derived here.
  const coastal = near.filter((s) => s.caveats.length === 0);
  const inland = near.filter((s) => s.caveats.length > 0);

  return (
    <div className="flex flex-col gap-4" data-dive-sites="true">
      {coastal.length > 0 ? (
        <div className="flex flex-col gap-2">
          <h4 className="m-0 flex items-baseline gap-2 text-xs font-semibold text-ink-2">
            {t('reefZone.diveSites.coastalHeading')}
            <span className="font-mono num text-2xs text-ink-3">{coastal.length}</span>
          </h4>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {coastal.map((s) => (
              <div
                key={s.osm_id}
                className="flex flex-col gap-1 border border-hairline bg-surface p-3"
                style={{ borderRadius: 'var(--radius-md)' }}
                data-dive-site={s.osm_id}
              >
                <span className="text-xs font-semibold text-ink">
                  {siteName(s, lang) ?? <IdText>{s.osm_id}</IdText>}
                </span>
                <span className="flex items-baseline gap-1 text-2xs text-ink-2">
                  {t('reefZone.diveSites.distance')}
                  <ValueWithUnit value={s.distance_m} digits={0} unit={t('units.m')} provenance="measured" />
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {inland.length > 0 ? (
        <div className="flex flex-col gap-2">
          <h4 className="m-0 flex items-baseline gap-2 text-xs font-semibold text-ink-2">
            {t('reefZone.diveSites.inlandHeading')}
            <span className="font-mono num text-2xs text-ink-3">{inland.length}</span>
          </h4>
          {/* The warning, once. */}
          <div
            className="rule bg-surface-2 p-3 text-2xs text-ink-2"
            data-caveats="true"
            role="note"
          >
            {t('reefZone.diveSites.inlandBanner')}
          </div>
          <ul className="m-0 flex list-none flex-col gap-px overflow-hidden rule p-0">
            {inland.map((s) => (
              <li
                key={s.osm_id}
                className="flex items-center justify-between gap-3 bg-surface px-3 py-2 text-xs"
                data-dive-site={s.osm_id}
                title={caveatText(s)}
              >
                <span className="min-w-0 truncate text-ink-2">
                  {siteName(s, lang) ?? <IdText>{s.osm_id}</IdText>}
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <ValueWithUnit value={s.distance_m} digits={0} unit={t('units.m')} provenance="measured" />
                  <span
                    className="border border-hairline-2 px-1.5 py-0.5 text-2xs text-ink-3"
                    style={{ borderRadius: 'var(--radius-sm)' }}
                  >
                    {t('reefZone.diveSites.inlandTag')}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
