import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fetchDiveSites, type DiveSite } from '../api/live';
import { CaveatList } from './CaveatList';
import { Empty, ErrorState, Loading } from './States';
import { ValueWithUnit } from './ValueWithUnit';
import { IdText } from '../routes/AlertsPage';

/** Dive sites joined to a reef zone, on /reef-zones/:id — feature p4-B.
 *
 *  The endpoint returns the geometric nearest-zone join only, never a risk score,
 *  so this lists the POIs whose nearest zone IS this one and shows how far each
 *  sits from it. Two honesty points, both load-bearing:
 *
 *   - The join key is `osm_id` (115/115 unique), never the name. Names repeat and
 *     drift; the id does not.
 *   - Only the ~10 sites within ~2 km are a trustworthy safety association. The
 *     rest are Wadi Rum desert attractions the OSM `kind: dive` category also
 *     carries, tens of km inland, and the backend attaches a caveat to each. That
 *     caveat is rendered here, prominently — an inland POI shown with a
 *     dive-safety status, caveat swallowed, is exactly the misleading output this
 *     project exists to avoid.
 */
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

  return (
    <div className="flex flex-col gap-3" data-dive-sites="true">
      <p className="m-0 max-w-prose text-2xs text-ink-2">{t('reefZone.diveSites.note')}</p>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {near.map((s) => {
          const name = (lang === 'ar' ? s.name_ar : s.name_en) ?? s.name_en ?? s.name_ar;
          const flagged = s.caveats.length > 0;
          return (
            <li
              key={s.osm_id}
              className="flex flex-col gap-1 border border-hairline bg-surface p-3"
              style={{ borderRadius: 'var(--radius-md)' }}
              data-dive-site={s.osm_id}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-xs font-semibold text-ink">
                  {name ?? <IdText>{s.osm_id}</IdText>}
                </span>
                <span className="flex items-baseline gap-1 text-2xs text-ink-2">
                  {t('reefZone.diveSites.distance')}
                  <ValueWithUnit value={s.distance_m} digits={0} unit={t('units.m')} provenance="measured" />
                </span>
              </div>
              {/* The join key, shown — this is what the association is really on. */}
              <span className="text-2xs text-ink-3">
                {t('reefZone.diveSites.osmId')} <IdText>{s.osm_id}</IdText>
              </span>
              {flagged ? <CaveatList items={s.caveats} /> : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
