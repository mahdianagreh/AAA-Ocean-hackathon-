import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { Card, PageShell, Section } from '../shell/PageShell';
import { DataTable, type Column } from '../components/DataTable';
import { CaveatList } from '../components/CaveatList';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { Loading } from '../components/States';
import { IdText } from './AlertsPage';
import {
  fetchDataSources,
  fetchDiveSites,
  fetchEvents,
  fetchReefZonesLive,
  type DataSourceRow,
  type DiveSite,
  type EventRow,
  type ReefZoneRow,
} from '../api/live';

/** Data explorer, at /data-explorer.
 *
 *  A browse-what-the-API-serves surface: pick a dataset and read it, as it is
 *  served, in the shared DataTable (so it matches every other table and reflows
 *  to a card stack on a phone). Everything here is a real live endpoint; each
 *  dataset degrades to an honest "unavailable" or "empty" state rather than a
 *  blank, and every number goes through ValueWithUnit. */

type Cat = 'reefZones' | 'events' | 'diveSites' | 'dataSources';
const CATS: Cat[] = ['reefZones', 'events', 'diveSites', 'dataSources'];

const FETCHERS: Record<Cat, () => Promise<unknown[] | null>> = {
  reefZones: () => fetchReefZonesLive(),
  events: () => fetchEvents(),
  diveSites: () => fetchDiveSites(),
  dataSources: () => fetchDataSources(),
};

export function DataExplorerPage() {
  const { t } = useTranslation('tools');
  const [cat, setCat] = useState<Cat>('reefZones');
  const [rows, setRows] = useState<unknown[] | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let live = true;
    setLoaded(false);
    setRows(null);
    void FETCHERS[cat]().then((r) => {
      if (!live) return;
      setRows(r);
      setLoaded(true);
    });
    return () => {
      live = false;
    };
  }, [cat]);

  return (
    <PageShell title={t('dataExplorer.title')} lede={t('dataExplorer.lede')}>
      <Section label={t('dataExplorer.categorySection')}>
        <div role="group" aria-label={t('dataExplorer.categorySection')} className="flex flex-wrap gap-2">
          {CATS.map((c) => (
            <button
              key={c}
              type="button"
              aria-pressed={cat === c}
              onClick={() => setCat(c)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors cursor-pointer ${
                cat === c ? 'bg-ink text-ink-inverse' : 'glass-panel text-ink-2 hover:border-accent'
              }`}
            >
              {t(`dataExplorer.cat.${c}`)}
            </button>
          ))}
        </div>
      </Section>

      <Section label={t(`dataExplorer.cat.${cat}`)}>
        {!loaded ? (
          <Loading what={t('dataExplorer.loading')} />
        ) : !rows ? (
          <Card>
            <p className="m-0 max-w-prose text-xs text-ink-2">{t('dataExplorer.unavailable')}</p>
          </Card>
        ) : rows.length === 0 ? (
          <Card>
            <p className="m-0 text-xs text-ink-2">{t('dataExplorer.empty')}</p>
          </Card>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="m-0 text-2xs text-ink-2">{t('dataExplorer.count', { n: rows.length })}</p>
            {renderTable(cat, rows, t)}
          </div>
        )}
      </Section>
    </PageShell>
  );
}

function renderTable(cat: Cat, rows: unknown[], t: TFunction) {
  switch (cat) {
    case 'reefZones': {
      const data = rows as ReefZoneRow[];
      const cols: Column<ReefZoneRow>[] = [
        { key: 'id', header: t('dataExplorer.col.id'), cell: (r) => <IdText>{r.reef_zone_id}</IdText> },
        { key: 'name', header: t('dataExplorer.col.name'), cell: (r) => r.zone_name ?? <ValueWithUnit value={null} /> },
        { key: 'area', align: 'end', header: t('dataExplorer.col.area'), cell: (r) => <ValueWithUnit value={r.area_km2} digits={3} unit="km²" provenance="measured" /> },
        { key: 'depth', align: 'end', header: t('dataExplorer.col.depth'), cell: (r) => <ValueWithUnit value={r.depth_median_m} digits={1} unit="m" provenance="measured" /> },
        { key: 'habitat', header: t('dataExplorer.col.habitat'), cell: (r) => r.habitat_class ?? <ValueWithUnit value={null} /> },
      ];
      return <DataTable columns={cols} rows={data} getRowKey={(r) => r.reef_zone_id} ariaLabel={t('dataExplorer.cat.reefZones')} />;
    }
    case 'events': {
      const data = rows as EventRow[];
      const cols: Column<EventRow>[] = [
        { key: 'id', header: t('dataExplorer.col.id'), cell: (r) => <IdText>{r.event_id}</IdText> },
        { key: 'label', header: t('dataExplorer.col.label'), cell: (r) => (r.label ? <span dir="auto">{r.label}</span> : <ValueWithUnit value={null} />) },
        { key: 'start', header: t('dataExplorer.col.start'), cell: (r) => (r.start ? <IdText>{r.start}</IdText> : <ValueWithUnit value={null} />) },
        { key: 'rank', align: 'end', header: t('dataExplorer.col.rank'), cell: (r) => <ValueWithUnit value={r.rank} digits={0} provenance="measured" /> },
        { key: 'maxDaily', align: 'end', header: t('dataExplorer.col.maxDaily'), cell: (r) => <ValueWithUnit value={r.max_daily_mm} digits={1} unit="mm" provenance="measured" /> },
      ];
      return <DataTable columns={cols} rows={data} getRowKey={(r) => r.event_id} ariaLabel={t('dataExplorer.cat.events')} />;
    }
    case 'diveSites': {
      const data = rows as DiveSite[];
      const cols: Column<DiveSite>[] = [
        { key: 'name', header: t('dataExplorer.col.name'), cell: (r) => (r.name_en ?? r.name_ar) ? <span dir="auto">{r.name_en ?? r.name_ar}</span> : <IdText>{r.osm_id}</IdText> },
        { key: 'nearestZone', header: t('dataExplorer.col.nearestZone'), cell: (r) => (r.nearest_reef_zone_id ? <IdText>{r.nearest_reef_zone_id}</IdText> : <ValueWithUnit value={null} />) },
        { key: 'distance', align: 'end', header: t('dataExplorer.col.distance'), cell: (r) => <ValueWithUnit value={r.distance_m} digits={0} unit="m" provenance="measured" /> },
      ];
      // The dive-site caveat MUST render: a large distance_m is an inland OSM
      // POI (e.g. a Wadi Rum desert attraction), and showing it beside a coastal
      // dive table without the backend's caveat is actively misleading. Deduped
      // across rows so one message is not repeated per inland POI.
      const seen = new Set<string>();
      const caveats: unknown[] = [];
      for (const r of data) {
        for (const c of r.caveats ?? []) {
          const key = JSON.stringify(c);
          if (seen.has(key)) continue;
          seen.add(key);
          caveats.push(c);
        }
      }
      return (
        <div className="flex flex-col gap-4">
          <DataTable columns={cols} rows={data} getRowKey={(r) => r.osm_id} ariaLabel={t('dataExplorer.cat.diveSites')} />
          {caveats.length ? <CaveatList items={caveats} /> : null}
        </div>
      );
    }
    case 'dataSources': {
      const data = rows as DataSourceRow[];
      const cols: Column<DataSourceRow>[] = [
        { key: 'name', header: t('dataExplorer.col.name'), cell: (r) => <span dir="auto">{r.name}</span> },
        { key: 'version', header: t('dataExplorer.col.version'), cell: (r) => <span dir="auto">{r.product_version}</span> },
        { key: 'accessed', header: t('dataExplorer.col.accessed'), cell: (r) => <IdText>{r.access_date}</IdText> },
        { key: 'licence', header: t('dataExplorer.col.licence'), cell: (r) => <span dir="auto">{r.licence}</span> },
      ];
      return <DataTable columns={cols} rows={data} getRowKey={(r) => r.name} ariaLabel={t('dataExplorer.cat.dataSources')} />;
    }
    default:
      return null;
  }
}
