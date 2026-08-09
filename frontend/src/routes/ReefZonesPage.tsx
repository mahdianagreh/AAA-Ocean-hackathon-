import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { fetchAlerts, fetchReefZonesLive, type AlertRow, type ReefZoneRow } from '../api/live';
import { CaveatCard } from '../components/CaveatCard';
import { DataTable, type Column } from '../components/DataTable';
import { Link } from '../components/Link';
import { ErrorState, Loading } from '../components/States';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { PageShell, Section } from '../shell/PageShell';
import { BandChip, Caveats, IdText } from './AlertsPage';

/** A sortable column header — a button whose th carries aria-sort. */
function SortButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="cursor-pointer text-2xs font-bold uppercase tracking-wide text-ink-2 underline decoration-hairline-2 underline-offset-4 transition-colors hover:text-accent"
    >
      {label}
    </button>
  );
}

/** Marine-park overlap as a small horizontal bar + the value. A null overlap is
 *  a gap (rendered by ValueWithUnit), never a 0% bar — "not measured" and
 *  "measured at zero" are different statements. */
function ParkOverlap({ pct, unit }: { pct: number | null | undefined; unit: string }) {
  if (pct === null || pct === undefined || Number.isNaN(pct)) {
    return <ValueWithUnit value={null} />;
  }
  const clamped = Math.max(0, Math.min(100, pct));
  return (
    <div className="flex items-center gap-2">
      <span className="relative block h-1.5 w-16 overflow-hidden rounded-full bg-surface-2" aria-hidden="true">
        <span
          className="absolute inset-y-0 start-0 rounded-full"
          style={{ width: `${clamped}%`, background: 'var(--accent)' }}
        />
      </span>
      <ValueWithUnit value={pct} digits={1} unit={unit} provenance="measured" />
    </div>
  );
}

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

  // Depth caveats repeat near-identically across R-02/R-06/R-07/R-08, so they are
  // grouped into ONE card with a per-zone line rather than four separate cards.
  // The zone id comes from the join (not parsed from text) and each message is
  // rendered verbatim — including R-02's different "no water cell" branch, which
  // is simply another line — so no fact is dropped or reworded, and no percentage
  // is invented (Phase 8 discrepancy (b)).
  const { depthCaveats, restCaveats } = useMemo(() => {
    const seen = new Set<string>();
    const rest: unknown[] = [];
    const depth: { zoneId: string; message: string; source: string | null; severity: string | null }[] = [];
    for (const { zone } of joined) {
      for (const c of zone.caveats ?? []) {
        const o = c && typeof c === 'object' ? (c as Record<string, unknown>) : null;
        const field = o && typeof o.field === 'string' ? o.field : null;
        const message = o && typeof o.message === 'string' ? o.message : null;
        if (field && field.includes('depth') && message) {
          // Every depth caveat becomes its own line (keyed by zone) — none is
          // dropped, even if a zone ever carried more than one.
          depth.push({
            zoneId: zone.reef_zone_id,
            message,
            source: o && typeof o.source === 'string' ? o.source : null,
            severity: o && typeof o.severity === 'string' ? o.severity : null,
          });
          continue;
        }
        const key = JSON.stringify(c);
        if (seen.has(key)) continue;
        seen.add(key);
        rest.push(c);
      }
    }
    return { depthCaveats: depth, restCaveats: rest };
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

  const columns: Column<Joined>[] = [
    {
      key: 'zone',
      ariaSort: ariaSort('name'),
      cardLabel: t('reefZones.col.zone'),
      header: <SortButton onClick={() => toggle('name')} label={t('reefZones.col.zone')} />,
      cell: ({ zone }) => (
        <div className="flex flex-col gap-0.5">
          <Link
            to={`/reef-zones/${encodeURIComponent(zone.reef_zone_id)}`}
            className="font-medium hover:underline"
          >
            {zone.zone_name ?? zone.reef_zone_id}
          </Link>
          <IdText className="text-2xs text-ink-2">{zone.reef_zone_id}</IdText>
        </div>
      ),
    },
    {
      key: 'exposure',
      ariaSort: ariaSort('score'),
      cardLabel: t('reefZones.col.exposure'),
      header: <SortButton onClick={() => toggle('score')} label={t('reefZones.col.exposure')} />,
      cell: ({ alert }) =>
        alert ? (
          <span className="flex flex-col items-start gap-1">
            <BandChip band={alert.risk_level} />
            <ValueWithUnit value={alert.risk_score} digits={1} provenance="modelled" />
          </span>
        ) : (
          // Neutral badge, not a hazard colour: "no run" is an absence of data,
          // not a low risk. The hint explains the distinction.
          <span
            title={t('reefZones.noRunHint')}
            className="inline-flex items-center rounded-full border border-hairline bg-surface-2 px-2 py-0.5 text-2xs text-ink-2"
          >
            {t('reefZones.noRun')}
          </span>
        ),
    },
    {
      key: 'area',
      align: 'end',
      ariaSort: ariaSort('area'),
      cardLabel: t('reefZones.col.area'),
      header: <SortButton onClick={() => toggle('area')} label={t('reefZones.col.area')} />,
      cell: ({ zone }) => (
        <ValueWithUnit value={zone.area_km2} digits={3} unit={t('units.km2')} provenance="measured" />
      ),
    },
    {
      key: 'habitat',
      header: t('reefZones.col.habitat'),
      cell: ({ zone }) => (
        <div className="flex flex-col gap-0.5">
          {zone.habitat_class ?? <ValueWithUnit value={null} />}
          {zone.geomorphic_class ? (
            <span className="text-2xs text-ink-2">{zone.geomorphic_class}</span>
          ) : null}
        </div>
      ),
    },
    {
      key: 'depth',
      align: 'end',
      header: t('reefZones.col.depth'),
      cell: ({ zone }) => (
        <ValueWithUnit value={zone.depth_median_m} digits={1} unit={t('units.m')} provenance="measured" />
      ),
    },
    {
      key: 'park',
      header: t('reefZones.col.park'),
      cell: ({ zone }) => <ParkOverlap pct={zone.marine_park_overlap_pct} unit={t('units.pct')} />,
    },
    {
      key: 'sensitivity',
      header: t('reefZones.col.sensitivity'),
      cell: ({ zone }) => {
        const placeholder =
          zone.sensitivity_weight_status === 'PLACEHOLDER_PENDING_MARINE_SCIENTIST';
        return (
          <div className="flex flex-col items-start gap-1.5">
            <ValueWithUnit value={zone.sensitivity_weight} digits={2} provenance="modelled" />
            {placeholder ? (
              // Amber pill from the hazard ramp's own AA-safe pairing; the full
              // explanation lives in the tooltip, not inline gray text.
              <span
                title={t('reefZones.placeholderWeight')}
                className="inline-flex items-center gap-1.5 rounded-full border border-hairline bg-surface px-2 py-0.5 text-2xs font-bold text-ink-2"
              >
                {/* An amber dot rather than a filled amber chip, so a status pill
                    is not misread as a "Low" hazard band. */}
                <span aria-hidden="true" className="inline-block h-2 w-2 rounded-full" style={{ background: 'var(--risk-moderate)' }} />
                {t('reefZones.placeholderPill')}
              </span>
            ) : (
              <span className="text-2xs text-ink-2">{t('reefZones.reviewedWeight')}</span>
            )}
          </div>
        );
      },
    },
  ];

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
            <div className="mt-4">
              <DataTable
                columns={columns}
                rows={joined}
                getRowKey={({ zone }) => zone.reef_zone_id}
                ariaLabel={t('reefZones.tableCaption')}
              />
            </div>
            <p className="m-0 max-w-prose text-xs text-ink-3 mt-4">{t('reefZones.depthNote')}</p>
          </>
        )}
      </Section>

      {restCaveats.length > 0 || depthCaveats.length > 0 ? (
        <Section label={t('caveats.sectionLabel')}>
          <div className="flex flex-col gap-3">
            {depthCaveats.length > 0 ? (
              <CaveatCard
                severity={depthCaveats[0].severity ?? 'warning'}
                headline={t('reefZones.depthGroupHeadline')}
                source={depthCaveats[0].source}
              >
                <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
                  {depthCaveats.map((d) => (
                    <li key={d.zoneId} className="flex flex-col gap-0.5">
                      <IdText className="text-2xs font-bold text-ink-2">{d.zoneId}</IdText>
                      <span className="max-w-prose text-xs text-ink-2">{d.message}</span>
                    </li>
                  ))}
                </ul>
              </CaveatCard>
            ) : null}
            {restCaveats.length > 0 ? <Caveats items={restCaveats} /> : null}
          </div>
        </Section>
      ) : null}
    </PageShell>
  );
}
