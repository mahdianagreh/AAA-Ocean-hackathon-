import type { Provenance, Value } from './types';

/** The demo event's series, derived by scripts/14_frontend_event_series.py.
 *
 *  The shapes carry their own gaps deliberately. There is no sub-daily rainfall
 *  series in the repo and no 5-minute mooring record, so `subdaily.available` and
 *  `mooring.series_available` are both false and the UI has to say so rather than
 *  draw a smooth line through nothing.
 */

export interface RainPoint {
  t: string;
  /** null is a gap, not a dry day. 09 rule 4. */
  mm: number | null;
  coverage: number | null;
}

export interface EventSeries {
  event_id: string;
  window_utc: { start: string; end: string };
  rainfall_daily: {
    unit: string;
    provenance: Provenance;
    source: string;
    note: string;
    by_catchment: Record<string, RainPoint[]>;
  };
  subdaily: {
    available: false;
    reason_key: string;
    granules: number | null;
    grid_shape_time_lat_lon: number[] | null;
    /** These are maxima over the AOI grid, not a series. Plotting them on the
     *  same axis as the catchment means would compare a cell peak with a spatial
     *  average — which is why the peak 3h (11.7 mm) exceeds the peak daily mean
     *  (10.2 mm) without either being wrong. */
    extrema_not_a_series: true;
    wettest_windows: Record<string, number | null>;
    wettest_3h_window_utc: {
      start: string;
      end: string;
      max_rain_3h_mm: number | null;
      derivation: string;
    };
  };
  mooring: {
    source_citation: string;
    source_doi: string;
    position: {
      lon: number;
      lat: number;
      depth_m: number;
      uncertainty_radius_m: number;
      provenance: Provenance;
      note: string;
    };
    markers: Array<{ key: string; t: string; provenance: Provenance }>;
    elevated_duration_hours: Value;
    peak_suspended_sediment: Value;
    salinity_minimum: Value;
    salinity_anomaly: Value & { uncertainty?: { sigma: number } };
    sediment_mass_total: Value;
    series_available: false;
    source_file: string;
  };
}

export interface EventRow {
  event_id: string;
  date: string;
  rank: number;
  max_daily_mm: number;
  wettest_catchment: string;
  storm_days: number | null;
  selection_reason: string | null;
}

const url = (n: string) => `${import.meta.env.BASE_URL}fixtures/${n}.json`;

export async function loadEventSeries(): Promise<EventSeries> {
  const r = await fetch(url('event'));
  if (!r.ok) throw new Error(`event.json: HTTP ${r.status}`);
  return (await r.json()) as EventSeries;
}

export async function loadEventCatalogue(): Promise<EventRow[]> {
  const r = await fetch(url('events'));
  if (!r.ok) throw new Error(`events.json: HTTP ${r.status}`);
  return (await r.json()) as EventRow[];
}

/** The timesteps the cursor indexes. Derived from the rainfall series so the
 *  slider, the hyetograph and the map can never disagree about what step 3 is. */
export function timestepsFor(series: EventSeries): string[] {
  const first = Object.values(series.rainfall_daily.by_catchment)[0] ?? [];
  return first.map((p) => p.t);
}
