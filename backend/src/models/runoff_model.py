"""Serving: the one function the API calls.

Everything the model layer does for a request goes through `predict`. The API
never imports the trainer, never reads a parquet, never fits anything.

Only one of the returned fields comes from `model.predict_proba`. The rest is
calibration, banding, a separately-computed confidence, TreeSHAP, the rule
baseline, and the sediment formula - which is why this is its own module and
not a one-line wrapper.

    from models.runoff_model import predict
    predict({"catchment_id": "AQ-C01", "rain_3h_mm": 42.7, ...})

The response is shaped as a `runoff_predictions` row on purpose: the API can
insert what it returns without a translation layer.

Sources, chosen by REEFSHIELD_MODEL_SOURCE:

    artifact   (default) the latest registered trained model
    stub       fixed-shape placeholder, every field stamped

The stub has to be asked for by name. A serving layer that silently invents
numbers when no model is present is worse than one that fails, because the
caller cannot tell the difference.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from . import artifacts, schema

# Calibrated probability -> severity. Bands are a product decision, not a
# statistical one, so they live in one visible place and are reported with
# every response rather than being implied by a colour on a map.
SEVERITY_BANDS = ((0.05, "none"), (0.25, "low"), (0.50, "medium"), (0.75, "high"))
SEVERITY_TOP = "extreme"

STUB_VERSION_ID = "STUB-no-model-trained"

#: Named in the unanchored-sediment message so the fix is obvious from the
#: response alone. Kept as a string to avoid importing sediment_proxy here.
SEDIMENT_ANCHOR = "AQ-2016-10-28 / AQ-C01 (~24,400 t)"

#: The one number in this module NOT sourced from model_versions.jsonl.
#: `scripts/22_label_leakage_diagnostic.py`'s one-off feature ablation
#: (reports/model/label_problem.md, docs/model_card.md — Mahdi, 4 Aug), run once
#: to diagnose why the shipped model's mean_AP was high, never registered as its
#: own trained artefact because it was never shipped. Root CLAUDE.md's label rule
#: section, verbatim: "Quote 0.662, not 0.741, for 'predicts runoff from
#: independent inputs'." Exists as a module constant, not a magic number in a
#: template, for the same reason SEDIMENT_ANCHOR is: named once, quoted everywhere.
LABEL_LEAKAGE_ABLATION = {
    "claim": "predicts runoff from inputs independent of the label's own atmosphere",
    "defensible_model": "M1 -- IMERG rainfall + neutral features, no ERA5 input at all",
    "defensible_n_features": 15,
    "defensible_mean_AP": 0.6623,
    "shipped_model": "M2 -- the shipped CD- feature set (this artefact's own feature list)",
    "shipped_n_features": 20,
    "shipped_mean_AP": 0.7445,
    "why_shipped_is_not_defensible": (
        "corr(ERA5-Land sro, ERA5-Land rainfall) = +0.985 vs corr(sro, IMERG "
        "rainfall) = +0.573 -- the label is near-deterministic in ERA5's own "
        "weather, so any ERA5-sourced feature this model uses "
        "(soil_moisture_lag1d, soil_moisture_lag3d, wind_speed_ms, "
        "wind_direction_deg, temp_c) leaks the same atmosphere the label came "
        "from, not hydrology. M2-M1 = +0.082: those five columns alone "
        "contribute 15% of the model's lift over baseline."
    ),
    "source": "reports/model/label_problem.md; docs/model_card.md",
}

#: Phase 5, B2. Mirrors sediment_proxy.TRANSMISSION_LOSS_BASIS - duplicated as
#: a literal for the same reason as SEDIMENT_ANCHOR above, not because the two
#: could drift independently. Unconditional: there is no "learned" path yet.
TRANSMISSION_LOSS_BASIS = "negev_proxy"

#: How many SHAP drivers the risk card shows.
TOP_DRIVERS = 4


def severity_for(p: float) -> str:
    for edge, label in SEVERITY_BANDS:
        if p < edge:
            return label
    return SEVERITY_TOP


def _confidence(row: pd.Series, bundle: dict[str, Any]) -> tuple[float, dict]:
    """How much to trust this row's probability, and why.

    Deliberately not derived from the probability itself: 0.5 can be a
    well-supported "genuinely borderline" or an unsupported "no idea", and the
    dashboard shows both numbers, so they have to mean different things.

    Every term is returned so the figure is auditable instead of decorative -
    the same reason `reef_exposures` stores its formula terms.
    """
    feats = bundle["features"]
    terms: dict[str, float | str] = {}

    # 1. how well the model did on THIS catchment when it was held out.
    #    The honest starting point, and it is what LOCO was run for.
    scores = bundle.get("catchment_scores") or {}
    cid = row.get("catchment_id")
    base = scores.get(cid)
    if base is None:
        base = float(np.mean(list(scores.values()))) if scores else 0.5
        terms["catchment_ap"] = f"{base:.3f} (mean - {cid} not in LOCO folds)"
    else:
        terms["catchment_ap"] = round(float(base), 3)

    # 2. missing inputs. Half weight: a NaN is carried through rather than
    #    zero-filled, so the model still predicts, just with less to go on.
    present = [f for f in feats if f in row.index and pd.notna(row.get(f))]
    missing_frac = 1.0 - (len(present) / len(feats) if feats else 1.0)
    missing_term = 1.0 - 0.5 * missing_frac
    terms["missing_fraction"] = round(missing_frac, 3)

    # 3. extrapolation. Outside the training range the trees predict the edge
    #    leaf, confidently and with no basis.
    ranges = bundle.get("feature_ranges") or {}
    out = [
        f for f in present
        if f in ranges and not (ranges[f][0] <= float(row[f]) <= ranges[f][1])
    ]
    range_term = 0.8 if out else 1.0
    terms["features_out_of_range"] = out[:6]

    # 4. an uncalibrated probability is not a probability.
    calib_term = 1.0 if bundle.get("is_calibrated") else 0.7
    terms["calibrated"] = bool(bundle.get("is_calibrated"))

    conf = float(np.clip(base * missing_term * range_term * calib_term, 0.0, 1.0))
    return round(conf, 3), terms


def _frame(features: dict | pd.Series | pd.DataFrame) -> pd.DataFrame:
    if isinstance(features, pd.DataFrame):
        return features.reset_index(drop=True)
    if isinstance(features, pd.Series):
        return features.to_frame().T.reset_index(drop=True)
    return pd.DataFrame([features])


#: Written by scripts/27_anchor_sediment_proxy.py. A sidecar rather than a field in the
#: .joblib, because `k` is a calibration constant and not a learned parameter — storing
#: it in the artefact would mean rewriting a trained file to hold one float and
#: invalidating its git_commit provenance for a change unrelated to training.
SEDIMENT_ANCHOR_FILE = Path(__file__).resolve().parents[3] / "data" / "models" / "sediment_anchor.json"


def _apply_sediment_anchor(bundle: dict[str, Any]) -> dict[str, Any]:
    """Anchor the proxy from the sidecar, and REFUSE if the calibration has drifted.

    Without this the proxy has `_k = None`, `classify()` is skipped, every response
    carries `sediment_class: null` — and the exposure formula, being a product of five
    terms, collapses to 0.0 so every reef zone reads `minimal` no matter what the plume
    does. The magnitude input was already correct: `predict` feeds
    `baseline.runoff_depth(X)`, the IMERG-driven curve-number depth that scripts/26
    showed ranks the anchor event 12th of 2,362 days, against 176th and 193rd for the
    two ERA5-derived alternatives. Only the SCALE was missing.

    The drift check is the point. `k = mass / index_at_anchor`, so it is valid only for
    the formula and feature set that produced that index. Change a term in
    `SedimentProxy.index()` and the stored `k` becomes a wrong tonnes-per-index scale
    that still multiplies cleanly — confident wrong masses, no error, nothing to notice.
    So the index is recomputed here and a mismatch leaves the proxy UNANCHORED with the
    reason attached, which degrades to relative classes rather than lying about tonnes.
    """
    if not SEDIMENT_ANCHOR_FILE.exists():
        return bundle

    import json

    anchor = json.loads(SEDIMENT_ANCHOR_FILE.read_text())
    stored = float(anchor["index_at_anchor"])
    tolerance = float(anchor.get("drift_tolerance", 1e-6))

    training_set = SEDIMENT_ANCHOR_FILE.parents[1] / "processed" / "features" / "training_set_full.parquet"
    if not training_set.exists():
        # Cannot verify, so do not anchor. An unverifiable calibration is exactly the
        # kind of thing that is right until the day it is not.
        bundle["sediment_anchor_status"] = (
            f"NOT APPLIED: {training_set.name} absent, so index_at_anchor could not be "
            "re-verified. Relative classes only."
        )
        return bundle

    frame = pd.read_parquet(training_set)
    day = pd.to_datetime(anchor["anchor_event"].removeprefix("AQ-")).date()
    frame = frame[(pd.to_datetime(frame["date"]).dt.date == day)
                  & (frame["catchment_id"] == anchor["anchor_catchment"])]
    if frame.empty:
        bundle["sediment_anchor_status"] = (
            f"NOT APPLIED: anchor row {anchor['anchor_event']}/"
            f"{anchor['anchor_catchment']} absent from the training set."
        )
        return bundle

    X = frame.reindex(columns=bundle["row"]["features"])
    recomputed = float(bundle["sediment"].index(X, bundle["baseline"].runoff_depth(X))[0])
    drift = abs(recomputed - stored) / stored if stored else 1.0

    if drift > tolerance:
        bundle["sediment_anchor_status"] = (
            f"NOT APPLIED: index_at_anchor drifted {drift:.3e} (stored {stored:,.4f}, "
            f"recomputed {recomputed:,.4f}). The formula or feature set changed since "
            "the anchor was written, so `k` is no longer a valid tonnes-per-index "
            "scale. Re-run scripts/27_anchor_sediment_proxy.py. Relative classes only "
            "until then."
        )
        return bundle

    bundle["sediment"].calibrate_to_anchor(recomputed, float(anchor["mass_t"]))
    # Kept on the bundle so `predict` can expose it without importing sediment_proxy —
    # this module avoids that import on purpose, see SEDIMENT_ANCHOR above.
    bundle["sediment_anchor_index"] = recomputed
    bundle["sediment_anchor_status"] = (
        f"applied: {anchor['anchor_event']}/{anchor['anchor_catchment']} at "
        f"{anchor['mass_t']:,.0f} t, k={anchor['k_tonnes_per_index']:.6f} t/index. "
        "ONE measurement fixes the scale, never the shape — a mass for any other event "
        "is an extrapolation along an unverified curve."
    )
    return bundle


@lru_cache(maxsize=4)
def _bundle(version_id: str | None = None) -> dict[str, Any]:
    """Loaded once per process, not per request. Anchored on the way through."""
    return _apply_sediment_anchor(artifacts.load(version_id))


def _stub_response(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Correctly-shaped, obviously-not-real. Lets the API be built today.

    Values are a transparent function of 3-hour rainfall so they move sensibly
    when Pulga clicks around, and every row is stamped in three places -
    `is_stub`, the version id, and `basis`.
    """
    out = []
    for _, row in df.iterrows():
        r3 = float(pd.to_numeric(row.get("rain_3h_mm"), errors="coerce") or 0.0)
        p = float(np.clip(1.0 - np.exp(-r3 / 35.0), 0.0, 0.99))
        out.append({
            "is_stub": True,
            "model_version_id": STUB_VERSION_ID,
            "basis": "STUB - no model has been trained. Shape only; not a prediction.",
            "catchment_id": row.get("catchment_id"),
            "runoff_probability": round(p, 4),
            "severity": severity_for(p),
            "confidence": 0.0,
            "confidence_terms": {"stub": "no trained model, confidence is not defined"},
            "rule_baseline_index": round(p * 0.9, 4),
            "feature_attributions": [
                {"feature": "rain_3h_mm", "shap": round(p, 4), "value": r3},
            ],
            # Lowercase: the canonical vocabulary is low|medium|high|extreme, which is what
            # particle_engine keys on and what the API schema validates. "Medium" here was
            # rejected by both.
            "sediment_class": "medium",
            "sediment_index": None,
            "transmission_loss": None,
            "transmission_loss_basis": None,
        })
    return out


def predict(
    features: dict | pd.Series | pd.DataFrame,
    *,
    version_id: str | None = None,
    source: str | None = None,
    transmission_loss_override: float | None = None,
) -> list[dict[str, Any]]:
    """Features in, one response dict per row out.

    Keys match `runoff_predictions` so the caller can insert the result as-is.

    `transmission_loss_override` (Phase 4, the what-if slider): substitutes a
    different `SedimentParams.transmission_loss` for this call only, via
    `SedimentProxy.with_transmission_loss()` — a new instance, the anchored bundle's
    own proxy is never mutated. This does not invalidate the anchor: `k` (tonnes per
    index unit) stays the one fitted at tau=0.525, and since `index ∝ (1 − tau)`
    linearly, a different tau just rescales the index the anchor's ratio is computed
    against — physically, "what if less/more of the sediment made it to the sea,"
    which is exactly what the slider claims to answer.
    """
    source = (source or os.environ.get("REEFSHIELD_MODEL_SOURCE") or "artifact").lower()
    df = _frame(features)

    if source == "stub":
        return _stub_response(df)
    if source != "artifact":
        raise ValueError(f"unknown model source {source!r} (artifact | stub)")

    bundle = _bundle(version_id)
    feats: list[str] = bundle["features"]

    # The leakage rule applies at serving too, not only at training. A caller
    # passing an ERA5 runoff column would otherwise have it silently accepted
    # if it ever entered the trained feature list.
    schema.assert_no_label_leakage(feats)

    # Reindex, never reorder-by-luck: XGBoost is positional, and a wrong order
    # does not raise. It returns confident nonsense.
    X = df.reindex(columns=feats)
    absent = [f for f in feats if f not in df.columns]

    gbm = bundle["gbm"]
    baseline = bundle["baseline"]
    sediment = bundle["sediment"]
    if transmission_loss_override is not None:
        sediment = sediment.with_transmission_loss(transmission_loss_override)

    proba = gbm.predict_proba(X)
    base_p = baseline.predict_proba(X)
    depth = baseline.runoff_depth(X)

    # The sediment CLASS needs absolute bands. Unanchored, classify() bands
    # against within-dataset quantiles - and a request has no dataset, so
    # quantiles over one row collapse to a single edge and every response comes
    # back "Extreme". The index is absolute given the formula, so it is still
    # returned; only the class is withheld, with the reason attached.
    sed_index = sediment.index(X, depth)
    anchored = bool(getattr(sediment, "is_anchored", False))
    sed = sediment.classify(X, depth) if anchored else None
    unanchored_note = (
        "UNANCHORED - index is comparable between requests, but no absolute "
        f"class exists. Anchor the proxy at training time on {SEDIMENT_ANCHOR}."
    )

    # Attributions are either real or ABSENT. Never zero-filled.
    #
    # This used to fall back to np.zeros on any exception, and the consequence was not a
    # missing chart — it was a WRONG one. argsort over an all-zero row returns the first
    # TOP_DRIVERS features in column order, each with `shap: 0.0`, so the API served four
    # arbitrary feature names and the UI drew a flat bar chart that reads as "the model
    # says none of these matter". Measured on 4 Aug: without shap installed the drivers
    # came back as precipitation_mm_day / slope_mean_deg / area_km2 / season_cos at 0.0;
    # with it, temp_c / wind_direction_deg / rain_self_percentile / rain_over_p90 at
    # -1.81 / -1.10 / +0.78 / +0.76. A different answer, silently.
    #
    # `shap` is imported lazily inside predictors.py, so this fires whenever the library
    # is absent — which it was in the local venv while being present in the api image,
    # meaning local and container disagreed about the drivers with nothing to say so.
    shap_vals = None
    shap_unavailable = None
    try:
        shap_vals = np.asarray(gbm.shap_values(X))
    except Exception as exc:
        shap_unavailable = (
            f"{type(exc).__name__}: {exc}. TreeSHAP could not run, so driver "
            "attributions are unavailable for this prediction. This is a gap, not a "
            "statement that the features have zero influence."
        )

    results = []
    for i in range(len(X)):
        conf, terms = _confidence(df.iloc[i], bundle)
        if absent:
            terms["features_absent_from_request"] = absent

        if shap_vals is None:
            # Empty, not fabricated. The UI renders "drivers unavailable" from the
            # accompanying status rather than a chart of zeros.
            drivers = []
        else:
            order = np.argsort(-np.abs(shap_vals[i]))[:TOP_DRIVERS]
            drivers = [
                {
                    "feature": feats[j],
                    "shap": round(float(shap_vals[i][j]), 5),
                    "value": (None if pd.isna(X.iloc[i, j]) else float(X.iloc[i, j])),
                }
                for j in order
            ]

        p = float(proba[i])
        results.append({
            "is_stub": False,
            "model_version_id": bundle["version_id"],
            "basis": bundle["row"]["feature_source"],
            "catchment_id": df.iloc[i].get("catchment_id"),
            "runoff_probability": round(p, 4),
            "severity": severity_for(p),
            "confidence": conf,
            "confidence_terms": terms,
            "rule_baseline_index": round(float(base_p[i]), 4),
            "feature_attributions": drivers,
            "feature_attributions_status": shap_unavailable,
            "sediment_class": str(sed.sediment_class.iloc[i]) if sed is not None else None,
            "sediment_index": round(float(sed_index[i]), 6),
            # The index is unbounded, and the exposure formula needs 0-1. Exposing the
            # anchor's own index lets a caller normalise against a DOCUMENTED reference
            # — 1.0 meaning "as intense as October 2016, ~24,400 t" — instead of picking
            # an arbitrary ceiling. None when unanchored, so a caller cannot silently
            # divide by a number that does not exist.
            "anchor_index_for_normalisation": (
                bundle.get("sediment_anchor_index") if anchored else None),
            "sediment_basis": (str(sed.class_basis.iloc[i]) if sed is not None
                               else unanchored_note),
            "transmission_loss": float(sediment.params.transmission_loss),
            "transmission_loss_basis": TRANSMISSION_LOSS_BASIS,
        })
    return results


def predict_one(features: dict, **kw) -> dict[str, Any]:
    """Single-row convenience for the API's per-catchment endpoint."""
    return predict(features, **kw)[0]


def model_info(version_id: str | None = None) -> dict[str, Any]:
    """What is being served, for GET /api/v1/models and the About panel."""
    source = (os.environ.get("REEFSHIELD_MODEL_SOURCE") or "artifact").lower()
    if source == "stub":
        return {
            "source": "stub",
            "model_version_id": STUB_VERSION_ID,
            "trained": False,
            "note": "No model trained. Responses are shape-only placeholders.",
        }
    row = dict(_bundle(version_id)["row"])
    row["source"] = "artifact"
    row["trained"] = True
    row["n_training_events"] = len(row.get("training_event_ids") or [])
    # Not one of this artefact's own recorded metrics -- a different, never-shipped
    # model, carried here so a caller asking "does this predict from independent
    # inputs" gets routed to the number that actually answers that question rather
    # than this artefact's own (leakage-contaminated) mean_AP.
    row["label_leakage_ablation"] = LABEL_LEAKAGE_ABLATION
    return row


def available_versions() -> Iterable[dict[str, Any]]:
    return artifacts.list_versions()
