import type { ApiClient } from './client';
import type { Catchment, Health, Outlet, ReefZone } from './types';

/** Fixtures built from real repo artefacts, never invented — 07 §5.
 *
 *  Geometry and attributes come from the committed basemap GeoJSON, which
 *  scripts/frontend_basemap.py derived from data/processed/vectors/*.gpkg. So
 *  the fixture client reads the same numbers the API will eventually serve, and
 *  the swap is a change of transport rather than a change of content.
 *
 *  This is also the deterministic demo path: 10-performance-and-offline.md
 *  requires demo mode to work without network *and without the API*.
 */

const url = (n: string) => `${import.meta.env.BASE_URL}basemap/${n}.geojson`;

async function props<T>(name: string): Promise<T[]> {
  const r = await fetch(url(name));
  if (!r.ok) throw new Error(`fixture ${name}.geojson: HTTP ${r.status}`);
  const fc = (await r.json()) as { features: Array<{ properties: T }> };
  return fc.features.map((f) => f.properties);
}

export function fixtureClient(): ApiClient {
  return {
    kind: 'fixtures',

    async health() {
      // Shaped like the real /health so the panel does not branch on client kind.
      // model_available is true because a registered artefact genuinely exists now
      // — runoff_weighted_gbm_2194b48_20260803T214757Z, whose output is committed to
      // fixtures/predictions.json. It read false while data/models/ was empty, and
      // a fixture that lies in either direction hides the state we want shown.
      return {
        status: 'ok',
        version: '0.1.0',
        commit: 'fixtures',
        time_utc: new Date().toISOString(),
        model_available: true,
        data_volume_mounted: true,
      } satisfies Health;
    },

    async catchments() {
      const rows = await props<{
        catchment_id: string;
        outlet_id: string;
        area_km2: number;
        provisional: number | boolean;
      }>('catchments');
      const outlets = await props<{ outlet_id: string; lon: number; lat: number;
        position_confidence: Catchment['position_confidence']; caveat: string }>('outlets');
      const byId = new Map(outlets.map((o) => [o.outlet_id, o]));

      return rows.map((r): Catchment => {
        // Join on outlet_id, never by deriving it from the catchment number.
        // tasks/00-contracts.md:114 is explicit: "it happens to equal the
        // catchment number today; hard-coding that assumption is how the previous
        // two versions of this section broke."
        const o = byId.get(r.outlet_id);
        return {
          catchment_id: r.catchment_id,
          // Only AQ-C01 is named, and the name lives in the contract rather than
          // in catchments.gpkg, which has no name column.
          name: r.catchment_id === 'AQ-C01' ? 'Wadi Yutum' : null,
          area_km2: r.area_km2,
          outlet_id: r.outlet_id,
          lon: o?.lon ?? 0,
          lat: o?.lat ?? 0,
          position_confidence: o?.position_confidence ?? 'low',
          caveat: o?.caveat ?? '',
        };
      });
    },

    async outlets() {
      return props<Outlet>('outlets');
    },

    async reefZones() {
      const rows = await props<Omit<ReefZone, 'provisional'> & { provisional: number | boolean }>(
        'reef_zones',
      );
      return rows.map((r): ReefZone => ({ ...r, provisional: Boolean(r.provisional) }));
    },
  };
}
