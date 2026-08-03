/** The type boundary the API swaps in behind.
 *
 *  07-data-contracts.md is locked before code, so these shapes are written from
 *  it rather than generated from the backend. That is deliberate: four of the
 *  five live endpoints return bare dicts with no response_model, so
 *  openapi.json describes them as unconstrained objects and codegen would yield
 *  `unknown`. Hand-maintained against the doc is the honest option.
 *
 *  Phase 0 defines only what Phase 0 renders. The rest lands with its endpoint.
 */

/** 07 §2. A reported number, a timezone-converted number and a number we
 *  computed are three different things and are never presented as one — that is
 *  carry-over rule 5. Making `provenance` non-optional means an unlabelled
 *  number fails type-check, so it cannot reach the screen. */
export type Provenance = 'measured' | 'reported' | 'converted' | 'modelled';

export interface Value {
  value: number;
  unit: string;
  provenance: Provenance;
  uncertainty?: { lower: number; upper: number } | { sigma: number };
}

/** Concept §14.5's five bands. The names are the contract — the same five
 *  strings appear in scripts/qa_frontend_palette.py, in the CSS tokens, and in
 *  the i18n keys, and qa_frontend_docs.py checks they stay identical across the
 *  documentation. */
export type HazardBand = 'minimal' | 'low' | 'moderate' | 'high' | 'critical';

export const HAZARD_BANDS: readonly HazardBand[] = [
  'minimal',
  'low',
  'moderate',
  'high',
  'critical',
] as const;

/** Score ranges, for the legend. Kept beside the band names so the two cannot
 *  drift apart. */
export const HAZARD_RANGES: Record<HazardBand, string> = {
  minimal: '0–20',
  low: '21–40',
  moderate: '41–60',
  high: '61–80',
  critical: '81–100',
};

export function bandForScore(score: number): HazardBand {
  if (score <= 20) return 'minimal';
  if (score <= 40) return 'low';
  if (score <= 60) return 'moderate';
  if (score <= 80) return 'high';
  return 'critical';
}

// ---------------------------------------------------------------------------
// Live endpoint shapes.
//
// Hand-written against backend/src/api/main.py rather than generated, because
// only /health declares a response_model — the other four return bare dicts, so
// openapi.json describes them as unconstrained objects and codegen yields
// `unknown`. These types are the contract until that changes; see
// docs/OPEN-ISSUES.md items 1 and 6.
// ---------------------------------------------------------------------------

/** The one typed response the API has. Note the path is `/health`, NOT
 *  `/api/v1/health` as the planning docs say — OPEN-ISSUES.md item 5. */
export interface Health {
  status: string;
  version: string;
  commit: string;
  time_utc: string;
  /** False today: data/models/ does not exist. */
  model_available: boolean;
  data_volume_mounted: boolean;
}

/** Two vocabularies for the same five outlets, so the union covers both.
 *  /api/v1/catchments emits plausible|low|good, /api/v1/outlets emits high|low.
 *  OPEN-ISSUES.md item 7. */
export type PositionConfidence = 'low' | 'plausible' | 'good' | 'high';

export interface Catchment {
  catchment_id: string;
  /** Only AQ-C01 has one ("Wadi Yutum"); the rest are null. */
  name: string | null;
  area_km2: number;
  outlet_id: string;
  lon: number;
  lat: number;
  position_confidence: PositionConfidence;
  caveat: string;
}

/** Four fields appear only when outlets.geojson is readable and vanish on the
 *  embedded fallback, with no flag in the payload — main.py:191 filters with
 *  `if k in r`. Hence the optionals. OPEN-ISSUES.md item 8. */
export interface Outlet {
  outlet_id: string;
  catchment_id: string;
  lon: number;
  lat: number;
  position_confidence: PositionConfidence;
  caveat: string;
  culvert_verdict?: string;
  unmodelled_coastal_culverts?: number;
  nearest_culvert_m?: number;
  upstream_km2?: number;
}

/** No endpoint serves these yet — OPEN-ISSUES.md item 1. The shape follows the
 *  committed reef_zones_PROVISIONAL.gpkg columns so the swap is a rename at most. */
export interface ReefZone {
  reef_zone_id: string;
  zone_name: string;
  area_km2: number;
  marine_park_overlap_pct: number;
  /** 1.0 on all eight zones, and flagged PLACEHOLDER_PENDING_MARINE_SCIENTIST.
   *  Exposure therefore varies only through the hazard term, and the legend must
   *  not imply the zones differ. OPEN-ISSUES.md item 17. */
  sensitivity_weight: number;
  sensitivity_weight_status: string;
  provisional: boolean;
}

/** AQ-O01 carries 96% of the discharge and is the demo path.
 *  AQ-O04 discharges into an enclosed harbour basin, so a particle simulation
 *  from that coordinate produces a confidently wrong plume — 01 §6.7 requires its
 *  caveat to travel with it wherever it is selectable. */
export const DEMO_OUTLET = 'AQ-O01';
export const HARBOUR_BASIN_OUTLETS = new Set(['AQ-O04']);
