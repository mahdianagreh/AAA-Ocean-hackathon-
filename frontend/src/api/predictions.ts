import type { HazardBand } from './types';

/** Real model output, derived offline by scripts/frontend_predictions.py.
 *
 *  This replaces the transparent stand-in index the risk cards used while
 *  `data/models/` was empty. A registered artefact with its own SHAP attributions
 *  beats a hand-rolled proxy, however carefully the proxy was labelled — and the
 *  proxy's whole justification was that no model existed.
 *
 *  Derived rather than fetched for two reasons: the API that serves
 *  /api/v1/runoff/predict does not currently start (OPEN-ISSUES #21), and DoD item 9
 *  requires the demo to run with no network and no API regardless. Same pattern as
 *  the basemap.
 */

export interface PredictionDriver {
  key: string;
  contribution: number;
  /** Frequently null in the model's own output. Rendered as a gap, never
   *  substituted with the input value — a SHAP attribution without its feature
   *  value is exactly the "missing is not zero" case. */
  value: number | null;
}

export interface Prediction {
  t: string;
  /** Travels through so a stub can never be mistaken for a trained prediction. */
  is_stub: boolean;
  runoff_probability: number;
  /** Always null: `predict_one()` never returns this key. The registered model is
   *  a runoff CLASSIFIER, not a volume regressor — there is no m3 figure to give,
   *  and rendering one would be a fabrication (task file: "render the gap; do not
   *  compute a substitute"). Carried as an explicit field rather than left absent
   *  so the card states the gap instead of silently never mentioning volume. */
  predicted_runoff_m3: number | null;
  /** The model's own vocabulary: none | low | medium | high | extreme. */
  severity: string;
  confidence: number;
  confidence_terms?: Record<string, unknown>;
  /** null unless the sediment proxy is anchored. The model returns null rather
   *  than a class it cannot support, and that reaches the screen as a gap. */
  sediment_class: string | null;
  sediment_index: number | null;
  sediment_basis?: string;
  transmission_loss: number | null;
  drivers: PredictionDriver[];
}

export interface Predictions {
  event_id: string;
  model: {
    version_id: string;
    algorithm: string;
    is_synthetic: boolean;
    cv_scheme?: string;
    mean_AP?: number;
    baseline_mean_AP?: number;
    trained_at?: string;
    n_training_events?: number;
    features: string[];
  };
  feature_source: string;
  derivation: string;
  by_catchment: Record<string, Prediction[]>;
}

/** The model's severity bands are not the interface's hazard bands.
 *
 *  runoff_model.py thresholds at 0.05 / 0.25 / 0.50 / 0.75 and names the results
 *  none | low | medium | high | extreme. Concept §14.5 names the five interface
 *  bands minimal | low | moderate | high | critical. They are the same five steps
 *  with two different vocabularies, so this is a rename rather than a re-banding —
 *  and doing it in one place means the score and the colour cannot disagree.
 */
const SEVERITY_TO_BAND: Record<string, HazardBand> = {
  none: 'minimal',
  low: 'low',
  medium: 'moderate',
  high: 'high',
  extreme: 'critical',
};

export function bandForSeverity(severity: string): HazardBand {
  return SEVERITY_TO_BAND[severity] ?? 'minimal';
}

export async function loadPredictions(): Promise<Predictions | null> {
  const r = await fetch(`${import.meta.env.BASE_URL}fixtures/predictions.json`);
  // A missing file is not an error: before a model was registered there was
  // nothing to derive, and the stand-in index is the correct fallback. The UI says
  // which one it is showing either way.
  if (!r.ok) return null;
  return (await r.json()) as Predictions;
}
