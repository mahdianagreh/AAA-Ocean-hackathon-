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

/** Literal class names, never `bg-risk-${band}` — Tailwind scans source
 *  statically, so an interpolated class is not a string in the file and the
 *  utility is never generated. That shipped once already in the Phase 0
 *  specimen: the strokes rendered because they were inline styles, and every
 *  fill silently fell back to the canvas, reading as a washed-out ramp rather
 *  than a missing one — which is why it survived a passing test suite.
 *
 *  Lives here rather than in RiskCard.tsx, which first defined it: any
 *  component showing a hazard band (RiskCard, and the reef-zone exposure rows
 *  in SideRail) needs the SAME AA-fix, and a second component copying it would
 *  risk silently missing Correction #10 below. */
export const BAND_CLASS: Record<HazardBand, string> = {
  minimal: 'bg-risk-minimal text-risk-minimal-on border-risk-minimal-stroke',
  low: 'bg-risk-low text-risk-low-on border-risk-low-stroke',
  moderate:
    // Correction #10: no AA-compliant text colour exists for this band in dark
    // theme (4.04 measured). So dark drops the fill and keeps the hue as a stroke
    // on --surface, where --ink reaches 14.32. Light theme is unaffected.
    'bg-risk-moderate text-risk-moderate-on border-risk-moderate-stroke ' +
    'dark:bg-surface dark:text-ink dark:border-risk-moderate',
  high: 'bg-risk-high text-risk-high-on border-risk-high-stroke',
  critical: 'bg-risk-critical text-risk-critical-on border-risk-critical-stroke',
};

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
  /** True since 3 Aug 2026. Read false while data/models/ was empty, and the
   *  interface renders both states rather than assuming either. */
  model_available: boolean;
  data_volume_mounted: boolean;
}

/** OPEN-ISSUES.md item 7 — CLOSED 2026-08-05. There was never really a
 *  two-vocabulary problem on the API side: /api/v1/catchments never emitted this
 *  field at all, and /api/v1/outlets was reading a hand-typed guess
 *  ({good, plausible, low}) that had silently diverged from the geometry team's
 *  actual DEM/culvert cross-check on 3 of 5 outlets. /outlets now reads the real
 *  vocabulary straight from source: high | low | unchecked. */
export type PositionConfidence = 'high' | 'low' | 'unchecked';

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
   *  not imply the zones differ. OPEN-ISSUES.md item 17.
   *
   *  Note the split: contract swap-in #3 landed, so the GEOMETRY is now real Allen
   *  Coral Atlas habitat (source `ACA/reef_habitat/v2_0`) while the WEIGHTING is
   *  still a placeholder. Two separate claims, and the copy says so separately. */
  sensitivity_weight: number;
  sensitivity_weight_status: string;
  provisional: boolean;
  /** Only meaningful since the ACA swap — the provisional file had 'unknown' on all
   *  eight zones. e.g. "Coral/Algae" over an "Outer Reef Flat". */
  habitat_class?: string;
  geomorphic_class?: string;
  source?: string;
}

/** AQ-O01 carries 96% of the discharge and is the demo path.
 *  AQ-O04 discharges into an enclosed harbour basin, so a particle simulation
 *  from that coordinate produces a confidently wrong plume — 01 §6.7 requires its
 *  caveat to travel with it wherever it is selectable. */
export const DEMO_OUTLET = 'AQ-O01';
export const HARBOUR_BASIN_OUTLETS = new Set(['AQ-O04']);
