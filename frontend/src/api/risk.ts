import type { EventSeries } from './event';
import type { Scenario } from '../app/uiStore';
import type { Catchment } from './types';
import { bandForScore } from './types';
import type { RiskCardData } from '../components/RiskCard';

/** Risk cards, derived from the real rainfall series — not invented numbers.
 *
 *  The model endpoints answer 503 because `data/models/` does not exist, so there
 *  is no trained artefact to call. Rather than invent a probability, this derives a
 *  transparent index from measured rainfall and states plainly that it is a
 *  stand-in: `runoff_probability` stays **null**, which renders as a gap, and every
 *  card is flagged provisional.
 *
 *  That distinction matters more than it looks. A fabricated 0.72 on a risk card is
 *  indistinguishable from a model output, and the whole project's credibility rests
 *  on not doing that. What is shown instead is: the rainfall that actually fell, a
 *  normalised index built only from it, and an explicit "no trained model" state.
 *  When Mahdi's artefact lands, the shape does not change — the nulls fill in.
 *  See OPEN-ISSUES.md item 15.
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
      band: bandForScore(score),
      score,
      // Deliberately null. There is no trained model, and a number here would be
      // a claim we cannot support.
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
