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
}

export interface PlumeFrame {
  t_hours: number;
  url: string;
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

/** The real exposure run for the demo event, from the outlet that carries 96% of
 *  the discharge. Every term in the formula comes back, including the sediment
 *  intensity — this is where the anchored proxy becomes visible on screen rather
 *  than staying a number in a terminal. */
export function fetchExposure(eventId: string, outletId = DEMO_OUTLET) {
  return tryJson<ExposureRun>(`${API_BASE}/api/v1/exposure/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ event_id: eventId, outlet_id: outletId, horizon_hours: 24 }),
  });
}

/** The timesteps a plume simulation actually produced, and a URL per frame. Never
 *  guessed — asking avoids requesting a `upto_hours` the simulation never made. */
export function fetchPlumeFrames(eventId: string, outletId = DEMO_OUTLET) {
  const q = new URLSearchParams({ event_id: eventId, outlet_id: outletId });
  return tryJson<PlumeFrames>(`${API_BASE}/api/v1/plume/map/frames?${q}`);
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
