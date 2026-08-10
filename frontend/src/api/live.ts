import { API_BASE } from './client';
import { DEMO_OUTLET } from './types';

/** The genuinely-live surface: exposure, the plume-prediction image, and alerts.
 *
 *  These three have no fixture equivalent and no offline fallback, unlike
 *  `catchments`/`outlets`/`reefZones` — there is no committed geometry to fall
 *  back to for "what did the model actually compute", because the whole point is
 *  that it is computed, not derived once and frozen. So every function here is
 *  best-effort: a failure (API down, CORS, network) resolves to `null`/`[]`
 *  rather than throwing, and the caller renders the same "not available" state
 *  it would show for a cold start. A demo that depends on this succeeding is a
 *  demo that can fail on stage; a demo that degrades gracefully when it fails
 *  is the one Phase 3's plan asks for.
 *
 *  `event_id` is passed in rather than assumed, per the project rule that no
 *  script (or component) hard-codes an event date — `useEventData` already reads
 *  it from the committed event fixture, so it is threaded through instead of
 *  duplicated here.
 */

export interface ExposureFormulaTerms {
  plume_probability?: number;
  relative_sediment_intensity?: number;
  relative_sediment_intensity_source?: string;
  exposure_duration_weight?: number;
  habitat_sensitivity_weight?: number;
  habitat_sensitivity_weight_status?: string;
  confidence_adjustment?: number;
  sediment_basis?: string;
  plume_source?: string;
  [key: string]: unknown;
}

export interface ExposureResult {
  reef_zone_id: string;
  risk_score: number;
  risk_level: 'minimal' | 'low' | 'moderate' | 'high' | 'critical';
  arrival_window_hours: [number, number] | null;
  max_exposure_probability: number;
  zone_fraction_affected: number;
  confidence: 'low' | 'moderate' | 'high';
  formula_terms: ExposureFormulaTerms;
}

export interface ExposureRun {
  run_id: string;
  event_id: string;
  outlet_id: string;
  created_at: string;
  results: ExposureResult[];
  model_versions: Record<string, string>;
  /** `unknown[]`, narrowed at the render boundary — same convention as every
   *  other live endpoint's caveats (see AlertsPage.tsx). Declared here rather
   *  than cast at each call site: `run.caveats` is a real response field
   *  (backend/src/api/main.py's exposure_calculate), not an extension. */
  caveats: unknown[];
}

export interface PlumeFrame {
  t_hours: number;
  url: string;
}

/** Source vs derived, made explicit — backend `schemas.Provenance`. Currents
 *  read "HYCOM GLBu0.08/expt_91.2 historical archive, cached …" where the
 *  archive exists for this event, or begin `PLACEHOLDER:` otherwise — rendered
 *  verbatim rather than paraphrased, because whichever it is on a given
 *  checkout is itself the fact the panel exists to show. */
export interface PlumeProvenanceEntry {
  kind: 'source' | 'derived' | 'assumed' | 'stub';
  detail: string;
}

export interface PlumeFrames {
  event_id: string;
  outlet_id: string;
  frame_count: number;
  frames: PlumeFrame[];
  basemap_present: boolean;
  /** Flips from 'stub' to 'particle-engine' the day Abd's real engine lands, with
   *  no change needed here — the point of asking the API rather than hard-coding
   *  it. A stub labelled as a stub is honest; shown as a forecast, it is not. */
  plume_source: 'stub' | 'particle-engine';
  /** The run's own provenance/caveats, carrying the currents source and the
   *  permanent wind-is-zero statement. `caveats` is `unknown[]`, narrowed at the
   *  render boundary by `Caveats`/`CaveatList` — same convention as every other
   *  live endpoint's caveats, per AlertsPage.tsx's own note on why. */
  provenance: PlumeProvenanceEntry[];
  caveats: unknown[];
  /** From `data/models/plume_calibration.json`, only when it was fit against
   *  THIS event — null (not 0), never invented, when no calibration ran here.
   *  `windage_is_tiebreak` is true exactly when a fit exists: the wind field is
   *  identically zero in every trial, so any windage_fraction that "wins" a
   *  72-trial grid search is a tie-break artefact, not a calibrated value. */
  windage_fraction: number | null;
  windage_is_tiebreak: boolean;
  windage_caveat: string | null;
}

export interface AlertRow {
  alert_id: string;
  source_run_id: string;
  reef_zone_id: string;
  risk_level: 'minimal' | 'low' | 'moderate' | 'high' | 'critical';
  risk_score: number;
  issued_at: string;
  arrival_window_hours: [number, number] | null;
  headline_en: string;
  headline_ar: string;
}

export interface ForecastCatchmentRainfall {
  catchment_id: string;
  lead_hours: number;
  rain_mm: number | null;
  wind_speed_ms: number | null;
  wind_direction_deg: number | null;
}

export interface ForecastExceedance {
  catchment_id: string;
  window_hours: number;
  threshold_mm: number;
  threshold_source: string;
  members_total: number;
  members_exceeding: number;
  exceedance_prob: number | null;
}

/** Percentile-relative, not a z-score -- `catchment_rainfall_climatology` only
 *  has percentiles, not a mean/std. See backend/src/processing/anomaly_detection.py. */
export interface ForecastAnomaly {
  catchment_id: string;
  window_hours: number;
  rain_mm: number;
  climatology_p50: number;
  climatology_p99: number;
  climatology_p99_9: number;
  percentile_band: string;
  anomaly_score: number;
  is_anomalous: boolean;
}

export interface ForecastRunMeta {
  id: string;
  model: string;
  reference_time: string;
  n_members: number;
  max_lead_hours: number;
}

export interface ForecastLatest {
  /** One reference_time per model (gfs/gefs), not a single timestamp. */
  issued_at: Record<string, string>;
  models: Record<string, ForecastRunMeta>;
  catchment_rainfall: ForecastCatchmentRainfall[];
  exceedance: ForecastExceedance[];
  anomalies: ForecastAnomaly[];
  anomaly_caveat: string;
}

export interface CurrentsAgreementCaveat {
  field: string;
  message: string;
  severity: string;
  source: string;
}

export interface CurrentsAgreement {
  lon: number;
  lat: number;
  time: string;
  hycom_direction_from_deg: number | null;
  copernicus_marine_direction_from_deg: number | null;
  direction_diff_deg: number | null;
  /** Continuous, 1.0 at 0deg disagreement, 0.0 at 180deg -- never a hardcoded cutoff. */
  agreement: number | null;
  window: string;
  sources: { hycom: string; copernicus_marine: string };
  caveats: CurrentsAgreementCaveat[];
}

async function tryJson<T>(url: string, init?: RequestInit): Promise<T | null> {
  try {
    const r = await fetch(url, init);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    // Network error, CORS, API not running — all the same "not available" state
    // from the caller's point of view.
    return null;
  }
}

/** Parameters for the exposure calculation, including optional scenario knobs. */
export interface ExposureParams {
  outletId?: string;
  horizonHours?: number;
  /** 0.5 – 2.0. Omit to use the default (1.0). */
  rainfallMultiplier?: number;
  /** 0.20 – 0.85. Omit entirely when unset — do NOT send null or the default,
   *  because the echo in formula_terms.transmission_loss is how you prove the
   *  override took effect, and sending 0.525 explicitly makes "unchanged" and
   *  "overridden to the default" indistinguishable. */
  transmissionLossOverride?: number;
}

/** The real exposure run for the demo event, from the outlet that carries 96% of
 *  the discharge. Every term in the formula comes back, including the sediment
 *  intensity — this is where the anchored proxy becomes visible on screen rather
 *  than staying a number in a terminal. */
export function fetchExposure(eventId: string, params: ExposureParams = {}) {
  const { outletId = DEMO_OUTLET, horizonHours = 24, rainfallMultiplier, transmissionLossOverride } = params;
  const body: Record<string, unknown> = {
    event_id: eventId,
    outlet_id: outletId,
    horizon_hours: horizonHours,
  };
  if (rainfallMultiplier !== undefined) {
    body.rainfall_multiplier = Math.max(0.5, Math.min(2.0, rainfallMultiplier));
  }
  if (transmissionLossOverride !== undefined) {
    body.transmission_loss_override = Math.max(0.20, Math.min(0.85, transmissionLossOverride));
  }
  return tryJson<ExposureRun>(`${API_BASE}/api/v1/exposure/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}


/** The timesteps a plume simulation actually produced, and a URL per frame. Never
 *  guessed — asking avoids requesting a `upto_hours` the simulation never made. */
export function fetchPlumeFrames(eventId: string, outletId = DEMO_OUTLET) {
  const q = new URLSearchParams({ event_id: eventId, outlet_id: outletId });
  return tryJson<PlumeFrames>(`${API_BASE}/api/v1/plume/map/frames?${q}`);
}

export interface RunoffDriver {
  key: string;
  contribution: number;
  value: number | null;
}

/** Component A (runoff occurrence) and Component B (the sediment proxy), one
 *  call — the backend scores both from the same real feature row. Unlike the
 *  plume/mooring, this has no `flood_arrival_utc` dependency: it resolves for
 *  ANY event with a real row in `training_set_full.parquet`, not the anchor
 *  event alone. `rainfall_mm_3h` is required by the schema but is ignored
 *  whenever a real historical row exists for `(event_id, catchment_id)` — it
 *  only matters for a what-if scenario with no matching row, which Replay does
 *  not use. */
export interface RunoffPrediction {
  catchment_id: string;
  predicted_runoff_m3: number | null;
  relative_sediment_intensity: number;
  runoff_probability: number | null;
  severity: string | null;
  confidence: number | null;
  sediment_class: 'low' | 'medium' | 'high' | 'extreme' | null;
  model_version: string;
  is_stub: boolean;
  drivers: RunoffDriver[];
  transmission_loss: number | null;
  transmission_loss_basis?: string | null;
  provenance: PlumeProvenanceEntry[];
  caveats: unknown[];
}

export function fetchRunoffPredict(eventId: string, catchmentId: string) {
  return tryJson<RunoffPrediction>(`${API_BASE}/api/v1/runoff/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // rainfall_mm_3h is a required field the endpoint does not use for a real
    // historical (event_id, catchment_id) row (see the interface docstring) —
    // 0 rather than a fabricated depth, since it is discarded either way.
    body: JSON.stringify({ catchment_id: catchmentId, rainfall_mm_3h: 0, event_id: eventId }),
  });
}

/** Real stored alerts. `[]` is a legitimate answer — `min_level` defaults to
 *  something above `minimal` on the API, so while the plume is still a stub
 *  (capping every score inside the minimal band) this comes back empty. That is
 *  not a broken feed; it is the same root cause as every zone reading minimal,
 *  so the caller renders one honest empty state rather than two different ones. */
export async function fetchAlerts(): Promise<AlertRow[]> {
  // `tryJson` returns a Promise, so `?? []` on the function call (not the
  // awaited value) would be dead code — a Promise object is always truthy.
  return (await tryJson<AlertRow[]>(`${API_BASE}/api/v1/alerts?min_level=minimal`)) ?? [];
}

/* ---------------------------------------------------------------------------
 * The rest of the real API surface.
 *
 * Before the rebrand exactly three endpoints in this file were ever called
 * live; every other panel read a committed fixture. That was defensible while
 * the pages were storyboards, but it meant the UI could not have shown a wrong
 * number even if the backend produced one — there was nothing to disagree with.
 * Everything below is the live route, verified against backend/src/api/main.py.
 *
 * Two path corrections worth recording, because both are easy to get wrong from
 * the planning docs:
 *   - mooring is GET /api/v1/events/{id}/mooring, NOT /api/v1/mooring/{id}
 *   - there is no GET /api/v1/reef-zones/{id}; zone detail is assembled from the
 *     list plus the /photos sub-resource
 * ------------------------------------------------------------------------- */

export interface EventRow {
  event_id: string;
  start: string | null;
  end: string | null;
  label: string | null;
  source: string | null;
  rank: number | null;
  max_daily_mm: number | null;
  mean_daily_mm: number | null;
  max_anomaly_ratio: number | null;
  catchments_exceeding_p99: number | null;
  wettest_catchment: string | null;
  storm_days: number | null;
  is_exhaustive: boolean | null;
  /** Empirical "top N%": this event's max_daily_mm sits in the top N% of all days
   *  in wettest_catchment's ~28-year record. A real percentile of the record, NOT
   *  max_anomaly_ratio (stale, never shown). null when the daily record or the
   *  wettest catchment is absent — render a gap, never a fabricated rank. */
  /** Optional, not just nullable: GET /api/v1/events omits this key entirely
   *  today. Typing it `number | null` is what made a strict `!== null` guard
   *  look safe in IntensityRanking and let `undefined` reach
   *  `.toLocaleString()`, blanking the view. */
  intensity_top_percent?: number | null;
  caveats: unknown[];
}

export interface ReefZoneRow {
  reef_zone_id: string;
  zone_name: string | null;
  habitat_class: string | null;
  area_km2: number;
  sensitivity_weight: number;
  sensitivity_weight_status: 'PLACEHOLDER_PENDING_MARINE_SCIENTIST' | 'SCIENTIST_ASSIGNED';
  marine_park_overlap_pct: number | null;
  depth_median_m: number | null;
  geomorphic_class: string | null;
  caveats: unknown[];
}

export interface DataSourceRow {
  name: string;
  product_version: string;
  access_date: string;
  access_method: string;
  spatial_resolution: string | null;
  licence: string;
  limitations: string[];
  qa_figures: string[];
  substituted: boolean;
  substitution_note: string | null;
}

export interface Citation {
  source_file: string;
  section: string;
  excerpt: string;
  score: number | null;
}

export interface AskResponse {
  answer: string;
  citations: Citation[];
  language: 'en' | 'ar';
  corpus_files_searched: number;
}

export interface ReportClaim {
  text: string;
  source: string | null;
}
export interface ReportSection {
  title: string;
  claims: ReportClaim[];
}
export interface ReportOut {
  report_id: string;
  event_id: string;
  /** Never defaulted away in the UI. A drafted report shown without this badge
   *  is indistinguishable from a reviewed one, which is the whole risk. */
  status: 'ai_drafted' | 'human_reviewed';
  generated_at: string;
  reviewed_at: string | null;
  reviewed_by: string | null;
  sections: ReportSection[];
}

export interface CriterionScore {
  criterion: 'C1' | 'C2' | 'C3' | 'C4' | 'C5' | 'C6';
  score: number | null;
  status: 'scored' | 'insufficient_data';
  evidence: Citation[];
}
export interface SiteScoreResponse {
  site_id: string;
  site_name: string | null;
  bbox: [number, number, number, number];
  criteria: CriterionScore[];
  narrative: string;
  caveats: unknown[];
}

export interface ReefZonePhoto {
  photo_id: string;
  reef_zone_id: string;
  uploaded_at: string;
  predicted_class: 'healthy' | 'stressed' | 'bleached';
  confidence: number;
  /** 'heuristic_rule_v1' means no trained classifier exists on disk and the
   *  result came from colour/texture rules with confidence capped at 0.55. */
  model_basis: 'heuristic_rule_v1' | 'trained_classifier';
  model_version: string | null;
}

export interface ProposedSensitivityWeight {
  reef_zone_id: string;
  proposed_value: number | null;
  status: 'INSUFFICIENT_PHOTOS' | 'PROPOSED_PENDING_REVIEW';
  n_photos: number;
  live_sensitivity_weight: number;
  live_sensitivity_weight_status: string;
}

export const fetchEvents = () => tryJson<EventRow[]>(`${API_BASE}/api/v1/events`);
export const fetchEvent = (id: string) =>
  tryJson<EventRow>(`${API_BASE}/api/v1/events/${encodeURIComponent(id)}`);

/** One calendar month of the seasonal rainfall-intensity calendar. Buckets are
 *  RAINFALL INTENSITY, not exposure — the consuming component must say so. */
export interface SeasonalMonth {
  month: number;
  month_name: string;
  event_count: number;
  max_daily_mm: number | null;
  mean_daily_mm: number | null;
  worst_event_id: string | null;
}

/** The twelve-month calendar plus where it came from. `provenance: 'snapshot'`
 *  means the live endpoint was unreachable and the committed fixture answered —
 *  a real, dated export of the same parquet, not invented data. The caller states
 *  which on screen so a snapshot is never mistaken for a live read. */
export interface SeasonalCalendar {
  months: SeasonalMonth[];
  provenance: 'live' | 'snapshot';
}

/** p4-K ships both an endpoint and a committed fixture. Try live first; fall back
 *  to the shipped snapshot so the calendar survives the wifi-off demo path.
 *
 *  The live call is time-boxed: a backend that is *hung* (accepting the socket but
 *  never answering) is not the same as one that is down, and without a deadline
 *  the fetch would wait indefinitely and the fixture fallback would never run —
 *  the page would sit in "Loading" forever. A short deadline turns a hung backend
 *  into the same graceful snapshot the wifi-off path already relies on. */
export async function fetchSeasonalCalendar(): Promise<SeasonalCalendar | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 4000);
  const live = await tryJson<SeasonalMonth[]>(`${API_BASE}/api/v1/seasonal-risk-calendar`, {
    signal: ctrl.signal,
  });
  clearTimeout(timer);
  if (live && live.length) return { months: live, provenance: 'live' };
  const snapshot = await tryJson<SeasonalMonth[]>('/fixtures/seasonal.json');
  if (snapshot && snapshot.length) return { months: snapshot, provenance: 'snapshot' };
  return null;
}

/** Real Kalman et al. (2025) mooring record. Only AQ-2016-10-28 has one; every
 *  other event 404s by design, which `tryJson` surfaces as null. */
export const fetchMooring = (eventId: string) =>
  tryJson<Record<string, unknown>>(
    `${API_BASE}/api/v1/events/${encodeURIComponent(eventId)}/mooring`,
  );

export const fetchReefZonesLive = (includeGeometry = false) =>
  tryJson<ReefZoneRow[]>(`${API_BASE}/api/v1/reef-zones?include_geometry=${includeGeometry}`);

export const fetchDataSources = () => tryJson<DataSourceRow[]>(`${API_BASE}/api/v1/data-sources`);
export const fetchForecastLatest = () =>
  tryJson<ForecastLatest>(`${API_BASE}/api/v1/forecast/latest`);

/** Real HYCOM-vs-Copernicus-Marine disagreement for the demo event by default
 *  (mooring peak-response time) -- never a live fetch, reads whichever cached
 *  `.nc` pair is already on disk. `null` fields mean the cache aged out or a
 *  point falls outside a resolved cell -- render "not available", never 0. */
export const fetchCurrentsAgreement = () =>
  tryJson<CurrentsAgreement>(`${API_BASE}/api/v1/currents/agreement`);

/** `TTLCache.stats()` (backend/src/api/data_access.py) -- exactly these three
 *  fields, nothing else. `size` is an ENTRY COUNT, not bytes -- label it
 *  "Entries" on screen, not "Size", or it reads as memory on a page titled
 *  "Memory & Cache Stats". No `last_updated`/`hit_rate` is stored server-side;
 *  a hit rate is `hits / (hits + misses)`, computed here and labelled derived,
 *  never shown as `0%` when `hits + misses === 0` (that's "no traffic yet", a
 *  gap, not a measured zero). Both caches share a 30-minute TTL
 *  (`ttl_seconds=1800`) -- show it next to the count so an entry count doesn't
 *  read as a permanent total. */
export interface CacheStats {
  hits: number;
  misses: number;
  size: number;
}

export interface CacheStatsResponse {
  plume: CacheStats;
  exposure: CacheStats;
}

export const fetchCacheStats = () =>
  tryJson<CacheStatsResponse>(`${API_BASE}/api/v1/cache-stats`);
/** A dive-site POI joined to its nearest reef zone. `osm_id` is the stable join
 *  key (115/115 unique) — never join on name. `distance_m` is a real EPSG:32636
 *  measurement; a large one means an inland OSM `kind: dive` POI (Wadi Rum desert
 *  attraction) that is not a coastal dive site, and the backend attaches a caveat
 *  saying so. That caveat MUST render — an inland POI shown with a dive-safety
 *  status is actively misleading. */
export interface DiveSite {
  osm_id: string;
  name_en: string | null;
  name_ar: string | null;
  lon: number;
  lat: number;
  nearest_reef_zone_id: string | null;
  distance_m: number | null;
  caveats: unknown[];
}

export const fetchDiveSites = () => tryJson<DiveSite[]>(`${API_BASE}/api/v1/dive-sites`);
export const fetchCatchments = () => tryJson<any[]>(`${API_BASE}/api/v1/catchments`);
export const fetchOutlets = () => tryJson<any[]>(`${API_BASE}/api/v1/outlets`);

/** Retrieval over the project's own docs. No LLM is involved anywhere in this
 *  path — the backend composes an extractive answer from cited excerpts, and an
 *  uncited answer is not returned at all. */
export const ask = (question: string, language: 'en' | 'ar' = 'en', k = 5) =>
  tryJson<AskResponse>(`${API_BASE}/api/v1/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, language, k }),
  });

export const generateReport = (eventId: string) =>
  tryJson<ReportOut>(`${API_BASE}/api/v1/reports/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event_id: eventId }),
  });

export const fetchReport = (id: string) =>
  tryJson<ReportOut>(`${API_BASE}/api/v1/reports/${encodeURIComponent(id)}`);

export const reviewReport = (id: string, reviewedBy: string) =>
  tryJson<ReportOut>(`${API_BASE}/api/v1/reports/${encodeURIComponent(id)}/review`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewed_by: reviewedBy }),
  });

export const scoreSite = (bbox: [number, number, number, number], siteName?: string) =>
  tryJson<SiteScoreResponse>(`${API_BASE}/api/v1/sites/score`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bbox, site_name: siteName ?? null }),
  });

export const fetchReefZonePhotos = (zoneId: string) =>
  tryJson<{ photos: ReefZonePhoto[]; proposed_sensitivity_weight: ProposedSensitivityWeight }>(
    `${API_BASE}/api/v1/reef-zones/${encodeURIComponent(zoneId)}/photos`,
  );

export async function uploadReefZonePhoto(zoneId: string, file: File) {
  const body = new FormData();
  body.append('file', file);
  // No Content-Type header: the browser must set the multipart boundary itself,
  // and setting it by hand produces a request the server cannot parse.
  return tryJson<ReefZonePhoto>(
    `${API_BASE}/api/v1/reef-zones/${encodeURIComponent(zoneId)}/photos`,
    { method: 'POST', body },
  );
}

// ------------------------------------------------------------------- System Health

export interface HealthOut {
  status: 'ok' | 'degraded';
  version: string;
  artifacts_present: Record<string, boolean>;
  degraded_reason: string[];
}

export const fetchSystemHealth = () => tryJson<HealthOut>(`${API_BASE}/api/v1/health`);
// fetchCacheStats lives above, typed as CacheStatsResponse. The untyped
// Record<string, unknown> version that used to sit here is what let String(value)
// render "[object Object]" for the nested plume/exposure objects.

// ------------------------------------------------------------------- Backtesting

export interface BacktestRequest {
  event_id: string;
  outlet_id?: string;
  baseline?: 'circular_buffer' | 'none';
}

export interface BacktestCaveat {
  kind: 'gap' | 'proxy' | 'heuristic' | 'limit';
  severity: 'info' | 'warning' | 'critical';
  detail: string;
}

export interface BacktestResult {
  run_id: string;
  event_id: string;
  status: 'queued' | 'running' | 'complete' | 'failed' | 'not_possible';
  metrics?: Record<string, number>;
  baseline_metrics?: Record<string, number>;
  note?: string;
  caveats: BacktestCaveat[];
}

export const runBacktest = (req: BacktestRequest) =>
  tryJson<BacktestResult>(`${API_BASE}/api/v1/backtests/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });

export const fetchBacktest = (runId: string) =>
  tryJson<BacktestResult>(`${API_BASE}/api/v1/backtests/${encodeURIComponent(runId)}`);
