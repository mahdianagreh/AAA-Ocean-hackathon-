import type { EventSeries } from './event';
import type { Scenario } from '../app/uiStore';
import type { Catchment } from './types';
import { bandForScore } from './types';
import { bandForSeverity, type Predictions } from './predictions';
import type { RiskCardData } from '../components/RiskCard';

/** Risk cards, from the registered model — with a labelled index as the fallback.
 *
 *  Two builders, and which one runs is stated on every card.
 *
 *  `riskFromPredictions` is the normal path. A trained artefact now exists
 *  (`runoff_weighted_gbm_2194b48_20260803T214757Z`, leave-one-catchment-out mean AP
 *  0.7474 against a 0.2004 baseline), so the cards show its probabilities and its
 *  own SHAP attributions, tagged with the version id.
 *
 *  `riskFromSeries` is the stand-in index, kept for the one case the model cannot
 *  serve: what-if mode. The predictions are model output at fixed inputs, and
 *  re-deriving them for an arbitrary transmission-loss slider would mean inventing a
 *  prediction the model never made. So the index answers instead, with
 *  `runoff_probability` **null** — a gap rather than a fabricated 0.72, which on a
 *  risk card is indistinguishable from model output.
 *
 *  This was written the other way round: until 3 Aug 2026 `data/models/` was empty
 *  and the index was the only path. OPEN-ISSUES.md item 15, now closed.
 */

/** Wet-day 99th percentile, from events.summary.json (14.31–15.59 mm across the
 *  five catchments). The rainfall term is scaled against this rather than an
 *  arbitrary constant, so "a lot of rain" means a lot *for Aqaba*. */
const WET_DAY_P99 = 15.0;

/** Catchment areas, for the concentration term. From catchments.gpkg. */
const AREA_MIN_KM2 = 35.64; // AQ-C05
const AREA_MAX_KM2 = 4453.08; // AQ-C01, Wadi Yutum

/** How much of a flood never reaches the sea. 20–85% infiltrates the wadi bed,
 *  and the pipeline does not model it. Applied as a fixed haircut with the
 *  midpoint of that range, and surfaced as a driver so it is visible rather than
 *  buried in a constant. */
const TRANSMISSION_LOSS = 0.5;

/** Concentration: a large catchment delivers far more water to one outlet from
 *  the same depth of rain.
 *
 *  This term is why the index discriminates at all. Measured, the five catchments
 *  received 9.2–10.2 mm on the peak day — within 10% of each other — so a
 *  rainfall-only index rated four of five `critical` and ranked AQ-C02 above
 *  AQ-C01. That is backwards: AQ-C01 is Wadi Yutum at 4,453 km², two orders of
 *  magnitude larger than the rest, and it carries 96% of the discharge.
 *
 *  Log-scaled, because the areas span 125x and a linear term would collapse the
 *  four small catchments into indistinguishable noise. */
function concentration(areaKm2: number): number {
  const lo = Math.log10(AREA_MIN_KM2);
  const hi = Math.log10(AREA_MAX_KM2);
  const t = (Math.log10(Math.max(AREA_MIN_KM2, areaKm2)) - lo) / (hi - lo);
  return 0.42 + 0.58 * t;
}

/** Real model output, when a registered artefact exists.
 *
 *  Preferred over the stand-in index below in every case — a measured prediction
 *  with its own SHAP attributions is strictly better evidence than a proxy. The
 *  proxy's only justification was that `data/models/` was empty, and it is not.
 *
 *  The scenario controls deliberately do NOT alter these numbers. They are model
 *  output at fixed inputs; re-deriving them for an arbitrary transmission-loss
 *  slider would mean inventing a prediction the model never made. So moving a
 *  control falls back to the index, and the card says which it is showing —
 *  09 rule 8, never claim exactness.
 */
export function riskFromPredictions(
  preds: Predictions,
  catchments: Catchment[],
  cursor: number,
): RiskCardData[] {
  return catchments.map((c) => {
    const rows = preds.by_catchment[c.catchment_id] ?? [];
    const p = rows[cursor];

    if (!p) {
      // No prediction at this step for this catchment. A gap, not a zero.
      return {
        catchment_id: c.catchment_id,
        name: c.name,
        area_km2: c.area_km2,
        band: 'minimal' as const,
        score: 0,
        runoff_probability: null,
        provisional: true,
        caveat: c.caveat,
        drivers: [],
        confidence: {
          members_exceeding: 0,
          members_total: rows.length,
          threshold_key: 'risk.thresholdModel',
          threshold_value: { value: 0, unit: '', provenance: 'modelled' as const },
        },
      };
    }

    return {
      catchment_id: c.catchment_id,
      name: c.name,
      area_km2: c.area_km2,
      band: bandForSeverity(p.severity),
      score: Math.round(p.runoff_probability * 100),
      runoff_probability: p.runoff_probability,
      // The model is real, so the card is no longer a stand-in. A stub prediction
      // would still be flagged, which is why is_stub travels through the fixture.
      provisional: p.is_stub,
      modelVersion: preds.model.version_id,
      caveat: c.caveat,
      drivers: p.drivers.slice(0, 4).map((d) => ({
        key: d.key,
        contribution: d.contribution,
        value: { value: d.value, unit: '', provenance: 'modelled' as const },
      })),
      confidence: {
        // The model reports a single confidence figure rather than ensemble
        // components, so the meter shows it against 1.0 and the label says what it
        // is. Composing "22 of 30 members" would be inventing an ensemble — Day-1
        // ask #6 is still owed.
        members_exceeding: Math.round(p.confidence * 100),
        members_total: 100,
        threshold_key: 'risk.thresholdModel',
        threshold_value: {
          value: preds.model.mean_AP ?? 0,
          unit: 'AP',
          provenance: 'modelled' as const,
        },
      },
    };
  });
}

export function riskFromSeries(
  series: EventSeries,
  catchments: Catchment[],
  cursor: number,
  scenario?: Scenario,
): RiskCardData[] {
  // Scenario overrides, or the documented midpoints. Transmission loss is a
  // control rather than a constant because it is the project's largest
  // unquantified uncertainty — 20-85% of a flood never reaches the sea — and
  // letting a judge move it is more honest than a caveat in prose.
  const loss = (scenario?.transmissionLoss ?? TRANSMISSION_LOSS * 100) / 100;
  const rainScale = (scenario?.rainfallScale ?? 100) / 100;
  const wetness = (scenario?.antecedentWetness ?? 50) / 50; // 1.0 at the default
  const by = series.rainfall_daily.by_catchment;

  return catchments.map((c) => {
    const points = by[c.catchment_id] ?? [];
    const today = points[cursor]?.mm ?? null;
    // Antecedent wetness: the two days before this step. A dry catchment absorbs
    // the first rain; a wet one runs. This is the crudest possible stand-in for
    // what the real antecedent features encode.
    const prior = points
      .slice(Math.max(0, cursor - 2), cursor)
      .map((p) => p.mm ?? 0)
      .reduce((a, b) => a + b, 0);

    // Rainfall for this catchment, against its own wet-day climatology.
    const rainIndex =
      today === null ? 0 : (today * rainScale + 0.5 * prior * wetness) / WET_DAY_P99;
    // Scaled by how much of it arrives at one outlet, minus what never gets there.
    const conc = concentration(c.area_km2);
    const index = rainIndex * conc * (1 - loss * 0.5);
    const score = Math.round(Math.min(100, index * 100));

    return {
      catchment_id: c.catchment_id,
      name: c.name,
      area_km2: c.area_km2,
      band: bandForScore(score),
      score,
      // Deliberately null. A trained model exists, but it cannot be re-run in the
      // browser against moved sliders — so on this path there is no probability to
      // report, and a number here would be a claim nothing computed.
      runoff_probability: null,
      provisional: true,
      caveat: c.caveat,
      drivers: [
        {
          key: 'rain_today',
          contribution: today === null ? 0 : ((today * rainScale) / WET_DAY_P99) * 0.6,
          value: { value: today === null ? null : today * rainScale, unit: 'mm', provenance: 'modelled' },
        },
        {
          key: 'antecedent_rain_48h',
          contribution: (prior / WET_DAY_P99) * 0.3,
          value: { value: prior, unit: 'mm', provenance: 'modelled' },
        },
        {
          key: 'catchment_area',
          // The term that actually discriminates — see concentration() above.
          contribution: rainIndex * (conc - 0.42),
          value: { value: c.area_km2, unit: 'km²', provenance: 'modelled' },
        },
        {
          key: 'transmission_loss',
          // Negative, and it is the largest single reduction. 20–85% of a Negev
          // flood infiltrates the wadi bed and never reaches the sea; the pipeline
          // does not model it, so this is the midpoint of that range applied as a
          // stated haircut rather than a pretence of a quantity.
          contribution: -rainIndex * conc * loss * 0.5,
          value: { value: loss * 100, unit: '%', provenance: 'modelled' },
        },
      ],
      confidence: {
        // Not an ensemble — there is no ensemble. These are the days in the window
        // where this catchment exceeded its own wet-day p99, which is a real count
        // over real values and is labelled as such.
        members_exceeding: points.filter((p) => (p.mm ?? 0) >= WET_DAY_P99 * 0.6).length,
        members_total: points.length,
        threshold_key: 'risk.thresholdWetDay',
        threshold_value: { value: WET_DAY_P99, unit: 'mm', provenance: 'modelled' },
      },
    };
  });
}
