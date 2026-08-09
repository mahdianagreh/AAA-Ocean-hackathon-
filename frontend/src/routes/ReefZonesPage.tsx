import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fetchAlerts, fetchReefZonesLive, type AlertRow, type ReefZoneRow } from '../api/live';
import { Link } from '../components/Link';
import { ErrorState, Loading } from '../components/States';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { PageShell, Section } from '../shell/PageShell';
import { BandChip, Caveats, IdText } from './AlertsPage';

/** The eight named Jordanian reef zones, at /reef-zones.
 *
 *  Two calls, joined here rather than on the server: `GET /api/v1/reef-zones`
 *  gives the geometry-derived attributes (Allen Coral Atlas v2.0 habitat, area,
 *  median depth, marine-park overlap), and `GET /api/v1/alerts` gives whatever
 *  the last stored exposure run said about each of them. There is no endpoint
 *  that returns both, and inventing one on the client is a join, not a claim.
 *
 *  The join is a LEFT join and stays one. A zone with no stored alert is shown
 *  as *no run*, never as `minimal` — "the model has not been run for this zone"
 *  and "the model ran and found almost nothing" are different statements, and
 *  the second is the one that would be wrong today. Since the plume's largest
 *  modelled extent (418 m) falls well short of the nearest zone (1923 m), the
 *  honest answer for every zone is currently the first one.
 *
 *  `sensitivity_weight_status === 'PLACEHOLDER_PENDING_MARINE_SCIENTIST'` is
 *  carried on the row itself rather than in a footnote. All eight zones hold an
 *  unreviewed 1.0, so exposure varies only through the hazard term — a ranked
 *  list that did not say so would read as "these reefs are ranked by how fragile
 *  they are", which no one has assessed.
 */

type SortKey = 'score' | 'area' | 'name';
type SortDir = 'asc' | 'desc';

interface Joined {
  zone: ReefZoneRow;
  alert: AlertRow | null;
}

export function ReefZonesPage() {
  const { t } = useTranslation('pages');

  const [zones, setZones] = useState<ReefZoneRow[] | null>(null);
  const [alerts, setAlerts] = useState<AlertRow[]>([]);
  const [failed, setFailed] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  useEffect(() => {
    let live = true;
    // Both are best-effort by construction, so Promise.all cannot reject here —
    // a missing alert feed must still leave the zone attributes on screen.
    void Promise.all([fetchReefZonesLive(), fetchAlerts()]).then(([z, a]) => {
      if (!live) return;
      if (z === null) setFailed(true);
      else setZones(z);
      setAlerts(a);
    });
    return () => {
      live = false;
    };
  }, []);

  const joined = useMemo<Joined[]>(() => {
    if (!zones) return [];
    // Highest score wins when a zone appears in more than one stored run: the
    // feed is chronological, not deduplicated, and quietly taking the first
    // would make the list depend on insertion order.
    const best = new Map<string, AlertRow>();
    for (const a of alerts) {
      const prev = best.get(a.reef_zone_id);
      if (!prev || a.risk_score > prev.risk_score) best.set(a.reef_zone_id, a);
    }
    const rows = zones.map((zone) => ({ zone, alert: best.get(zone.reef_zone_id) ?? null }));

    const dir = sortDir === 'asc' ? 1 : -1;
    return rows.sort((x, y) => {
      if (sortKey === 'name') {
        return dir * (x.zone.zone_name ?? x.zone.reef_zone_id).localeCompare(
          y.zone.zone_name ?? y.zone.reef_zone_id,
        );
      }
      if (sortKey === 'area') return dir * (x.zone.area_km2 - y.zone.area_km2);
      // Zones with no stored run sort last in both directions rather than
      // sorting as zero, which would read as "assessed, and lowest".
      const xs = x.alert?.risk_score ?? null;
      const ys = y.alert?.risk_score ?? null;
      if (xs === null && ys === null) return 0;
      if (xs === null) return 1;
      if (ys === null) return -1;
      return dir * (xs - ys);
    });
  }, [zones, alerts, sortKey, sortDir]);

  const caveats = useMemo(() => {
    const seen = new Set<string>();
    const out: unknown[] = [];
    for (const { zone } of joined) {
      for (const c of zone.caveats ?? []) {
        const key = JSON.stringify(c);
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(c);
      }
    }
    return out;
  }, [joined]);

  const toggle = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(key);
      setSortDir(key === 'name' ? 'asc' : 'desc');
    }
  };

  const ariaSort = (key: SortKey): 'ascending' | 'descending' | 'none' =>
    sortKey !== key ? 'none' : sortDir === 'asc' ? 'ascending' : 'descending';

  const placeholderCount = joined.filter(
    (j) => j.zone.sensitivity_weight_status === 'PLACEHOLDER_PENDING_MARINE_SCIENTIST',
  ).length;

  return (
    <PageShell title={t('reefZones.title')} lede={t('reefZones.lede')}>
      <Section label={t('reefZones.rankLabel')}>
        {failed ? (
          <ErrorState what={t('reefZones.errorTitle')} message={t('reefZones.errorBody')} />
        ) : zones === null ? (
          <Loading what={t('reefZones.loading')} />
        ) : (
          <>
            <p className="m-0 text-xs font-medium text-ink-2">
              {t('reefZones.count', { n: joined.length })}
            </p>
            {placeholderCount > 0 ? (
              <p className="m-0 max-w-prose glass-panel p-4 mt-2 text-sm text-ink-2 border-accent shadow-[0_0_15px_color-mix(in_srgb,var(--accent)_30%,transparent)] font-medium leading-relaxed">
                {t('reefZones.placeholderSummary', { n: placeholderCount })}
              </p>
            ) : null}
            <div className="overflow-x-auto glass-panel p-5 mt-4">
              <table className="w-full border-collapse text-sm">
                <caption className="sr-only">{t('reefZones.tableCaption')}</caption>
                <thead>
                  <tr className="border-b border-hairline-2 text-xs text-ink-2 font-bold premium-gradient-text">
                    <th
                      scope="col"
                      aria-sort={ariaSort('name')}
                      className="p-3 text-start"
                    >
                      <button
                        type="button"
                        onClick={() => toggle('name')}
                        className="text-xs font-bold text-ink hover:text-accent transition-all hover:scale-105 cursor-pointer underline decoration-hairline-2 underline-offset-4"
                      >
                        {t('reefZones.col.zone')}
                      </button>
                    </th>
                    <th
                      scope="col"
                      aria-sort={ariaSort('score')}
                      className="p-3 text-start"
                    >
                      <button
                        type="button"
                        onClick={() => toggle('score')}
                        className="text-xs font-bold text-ink hover:text-accent transition-all hover:scale-105 cursor-pointer underline decoration-hairline-2 underline-offset-4"
                      >
                        {t('reefZones.col.exposure')}
                      </button>
                    </th>
                    <th
                      scope="col"
                      aria-sort={ariaSort('area')}
                      className="p-3 text-start"
                    >
                      <button
                        type="button"
                        onClick={() => toggle('area')}
                        className="text-xs font-bold text-ink hover:text-accent transition-all hover:scale-105 cursor-pointer underline decoration-hairline-2 underline-offset-4"
                      >
                        {t('reefZones.col.area')}
                      </button>
                    </th>
                    <th scope="col" className="p-3 text-start">
                      {t('reefZones.col.habitat')}
                    </th>
                    <th scope="col" className="p-3 text-start">
                      {t('reefZones.col.depth')}
                    </th>
                    <th scope="col" className="p-3 text-start">
                      {t('reefZones.col.park')}
                    </th>
                    <th scope="col" className="p-3 text-start">
                      {t('reefZones.col.sensitivity')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {joined.map(({ zone, alert }) => {
                    const placeholder =
                      zone.sensitivity_weight_status === 'PLACEHOLDER_PENDING_MARINE_SCIENTIST';
                    return (
                      <tr key={zone.reef_zone_id} className="border-b border-hairline align-top transition-colors hover:bg-surface/50 group/row">
                        <th scope="row" className="p-3 text-start font-medium group-hover/row:text-accent transition-colors">
                          <Link
                            to={`/reef-zones/${encodeURIComponent(zone.reef_zone_id)}`}
                            className="hover:underline"
                          >
                            {zone.zone_name ?? zone.reef_zone_id}
                          </Link>
                          <span className="block text-xs text-ink-3 mt-1 font-mono">
                            <IdText>{zone.reef_zone_id}</IdText>
                          </span>
                        </th>
                        <td className="p-3">
                          {alert ? (
                            <span className="flex flex-col items-start gap-1">
                              <BandChip band={alert.risk_level} />
                              <ValueWithUnit
                                value={alert.risk_score}
                                digits={1}
                                provenance="modelled"
                              />
                            </span>
                          ) : (
                            <span className="text-ink-3" title={t('reefZones.noRunHint')}>
                              {t('reefZones.noRun')}
                            </span>
                          )}
                        </td>
                        <td className="p-3">
                          <ValueWithUnit
                            value={zone.area_km2}
                            digits={3}
                            unit={t('units.km2')}
                            provenance="measured"
                          />
                        </td>
                        <td className="p-3">
                          {zone.habitat_class ?? <ValueWithUnit value={null} />}
                          {zone.geomorphic_class ? (
                            <span className="block text-xs text-ink-3 mt-1">
                              {zone.geomorphic_class}
                            </span>
                          ) : null}
                        </td>
                        <td className="p-3">
                          <ValueWithUnit
                            value={zone.depth_median_m}
                            digits={1}
                            unit={t('units.m')}
                            provenance="measured"
                          />
                        </td>
                        <td className="p-3">
                          <ValueWithUnit
                            value={zone.marine_park_overlap_pct}
                            digits={1}
                            unit={t('units.pct')}
                            provenance="measured"
                          />
                        </td>
                        <td className="max-w-prose p-3">
                          <ValueWithUnit
                            value={zone.sensitivity_weight}
                            digits={2}
                            provenance="modelled"
                          />
                          {placeholder ? (
                            <span className="mt-2 block text-xs text-ink-2">
                              {t('reefZones.placeholderWeight')}
                            </span>
                          ) : (
                            <span className="mt-2 block text-xs text-ink-3">
                              {t('reefZones.reviewedWeight')}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="m-0 max-w-prose text-xs text-ink-3 mt-4">{t('reefZones.depthNote')}</p>
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
