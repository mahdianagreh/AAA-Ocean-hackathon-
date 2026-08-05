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


@lru_cache(maxsize=4)
def _bundle(version_id: str | None = None) -> dict[str, Any]:
    """Loaded once per process, not per request."""
    return artifacts.load(version_id)


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
        })
    return out


def predict(
    features: dict | pd.Series | pd.DataFrame,
    *,
    version_id: str | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """Features in, one response dict per row out.

    Keys match `runoff_predictions` so the caller can insert the result as-is.
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
            "sediment_basis": (str(sed.class_basis.iloc[i]) if sed is not None
                               else unanchored_note),
            "transmission_loss": float(sediment.params.transmission_loss),
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
    return row


def available_versions() -> Iterable[dict[str, Any]]:
    return artifacts.list_versions()
