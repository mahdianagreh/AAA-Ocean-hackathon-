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
