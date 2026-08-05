"""One vocabulary for `sediment_class`, across three modules that owned three.

This is an ID-contract problem wearing different clothes. `sediment_class` is produced
by Mahdi's sediment proxy, validated by Pulga's API schema and consumed by Abd's
particle engine, and on 4 Aug 2026 the three disagreed:

    sediment_proxy.CLASSES                    ("Low", "Medium", "High", "Extreme")
    particle_engine.SEDIMENT_CLASS_...        keys on "medium"
    api.schemas.RunoffPrediction              Literal[... "moderate" ...]

So the only spelling the schema permitted raised ValueError in the particle engine, and
the spelling the proxy actually emits failed validation at the API. Four API contract
tests were red on main. `medium`, lowercase, is the value that survives the whole chain.

The rule these tests encode: a value that crosses a module boundary is a contract, and
it needs the same discipline as `AQ-C01` or `R-03`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

#: The canonical vocabulary. Lowercase, and `medium` — not `moderate`.
CANONICAL = ("low", "medium", "high", "extreme")


def test_particle_engine_keys_on_the_canonical_vocabulary():
    from models.particle_engine import SEDIMENT_CLASS_PARTICLE_SCALE

    assert set(SEDIMENT_CLASS_PARTICLE_SCALE) == set(CANONICAL)


def test_the_sediment_proxy_classes_lowercase_to_the_canonical_vocabulary():
    """The proxy may present them capitalised, but they must map cleanly."""
    from models.sediment_proxy import CLASSES

    assert tuple(c.lower() for c in CLASSES) == CANONICAL, (
        f"sediment_proxy.CLASSES={CLASSES} does not lowercase to {CANONICAL}; a new "
        "class name here silently breaks the API schema and the particle engine"
    )


def test_the_api_schema_accepts_exactly_the_canonical_vocabulary():
    """The schema previously mandated `moderate`, which no producer emits and which the
    particle engine rejects — a value that could not legally cross the whole chain."""
    from api.schemas import RunoffPrediction

    field = RunoffPrediction.model_fields["sediment_class"]
    allowed = set()
    for arg in getattr(field.annotation, "__args__", ()):
        allowed.update(getattr(arg, "__args__", ()) or ())

    assert set(CANONICAL) <= allowed, f"schema allows {allowed}, missing from {CANONICAL}"
    assert "moderate" not in allowed, (
        "`moderate` is back in the schema. Nothing produces it and "
        "particle_count_for_sediment_class raises on it."
    )


def test_the_api_schema_permits_a_missing_sediment_class():
    """`None` means the proxy has not run, and it must survive rather than be defaulted.

    runoff_model.predict returns `sediment_class=None` in that case and puts the reason
    in `sediment_basis`. Substituting a class would invent a severity nobody computed;
    the project rule is that a gap is reported, never filled in. This is also the exact
    failure that turned main red: the key is PRESENT and holds None, so
    `.get("sediment_class", "moderate")` returns None and validation rejects it.
    """
    from api.schemas import RunoffPrediction

    ok = RunoffPrediction(
        catchment_id="AQ-C01", predicted_runoff_m3=1.0,
        relative_sediment_intensity=0.5, sediment_class=None,
        model_version="test", is_stub=False,
    )
    assert ok.sediment_class is None


def test_every_canonical_value_survives_the_full_chain():
    """Schema validation and particle scaling, for each value and for None.

    Either half passing alone is what let the mismatch live: the schema was internally
    consistent and so was the particle engine.
    """
    from api.schemas import RunoffPrediction
    from models.particle_engine import particle_count_for_sediment_class

    for value in (*CANONICAL, None):
        RunoffPrediction(
            catchment_id="AQ-C01", predicted_runoff_m3=1.0,
            relative_sediment_intensity=0.5, sediment_class=value,
            model_version="test", is_stub=False,
        )
        assert particle_count_for_sediment_class(2000, value) > 0


def test_the_stub_predictor_emits_a_legal_value():
    """The stub is what the UI is built against, so its output must validate too."""
    import pandas as pd

    from api.schemas import RunoffPrediction
    from models.runoff_model import _stub_response

    rows = _stub_response(pd.DataFrame([{"catchment_id": "AQ-C01", "rain_3h_mm": 12.0}]))
    for row in rows:
        assert row["sediment_class"] in CANONICAL, row["sediment_class"]
        RunoffPrediction(
            catchment_id="AQ-C01", predicted_runoff_m3=1.0,
            relative_sediment_intensity=0.5,
            sediment_class=row["sediment_class"],
            model_version="stub", is_stub=True,
        )


def test_driver_attributions_are_absent_not_zero_when_shap_is_unavailable():
    """A missing explainer must produce no drivers, never drivers of zero.

    This zero-filled on any exception, and the result was not a missing chart but a
    WRONG one: argsort over an all-zero row returns the first TOP_DRIVERS features in
    column order at `shap: 0.0`, so the UI drew a flat bar chart reading "the model says
    none of these matter". Measured on 4 Aug, the same request returned
    precipitation_mm_day / slope_mean_deg / area_km2 / season_cos at 0.0 without shap,
    and temp_c / wind_direction_deg / rain_self_percentile / rain_over_p90 at
    -1.81 / -1.10 / +0.78 / +0.76 with it. `shap` is imported lazily, so this fired
    whenever the library was absent — which it was in the local venv while present in the
    api image, meaning local and container disagreed with nothing to say so.
    """
    import builtins

    from models.runoff_model import predict_one

    real_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name == "shap":
            raise ImportError("simulated: shap absent")
        return real_import(name, *args, **kwargs)

    builtins.__import__ = blocked
    try:
        out = predict_one({"catchment_id": "AQ-C01", "rain_3h_mm": 12.0})
    finally:
        builtins.__import__ = real_import

    assert out["feature_attributions"] == [], (
        "drivers must be empty when TreeSHAP cannot run — a list of zeros is a claim "
        "about the features, and it is a false one"
    )
    status = out["feature_attributions_status"]
    assert status and "unavailable" in status.lower()
    assert "gap" in status.lower(), "the status must say this is a gap, not zero influence"


def test_the_proxy_is_anchored_and_returns_a_class():
    """Unanchored, `classify()` is skipped and the exposure product collapses to zero.

    This is the wiring that unblocked the product. The magnitude input was already
    right — `predict` feeds `baseline.runoff_depth(X)`, the IMERG-driven curve-number
    depth that scripts/26 ranked 12th of 2,362 days against 176th and 193rd for the two
    ERA5-derived alternatives. Only the SCALE was missing, so every response carried
    `sediment_class: null` and every reef zone read `minimal`.
    """
    import pandas as pd

    from models.runoff_model import _bundle, predict_one

    bundle = _bundle()
    if not (PROJECT_ROOT / "data/models/sediment_anchor.json").exists():
        pytest.skip("anchor not written — run scripts/27_anchor_sediment_proxy.py")

    assert bundle["sediment"].is_anchored, bundle.get("sediment_anchor_status")
    assert bundle.get("sediment_anchor_index", 0) > 0

    frame = pd.read_parquet(PROJECT_ROOT / "data/processed/features/training_set_full.parquet")
    day = pd.to_datetime("2016-10-28").date()
    row = frame[(pd.to_datetime(frame["date"]).dt.date == day)
                & (frame["catchment_id"] == "AQ-C01")]
    if row.empty:
        pytest.skip("anchor row absent")

    out = predict_one(row.iloc[0].to_dict())
    assert out["sediment_class"] in CANONICAL or out["sediment_class"] in (
        "Low", "Medium", "High", "Extreme"), out["sediment_class"]
    assert out["sediment_index"] > 0
    assert out["anchor_index_for_normalisation"] > 0
    assert "banded against" in str(out["sediment_basis"])


def test_a_drifted_anchor_refuses_rather_than_reporting_wrong_tonnes():
    """`k = mass / index_at_anchor`, so it is valid only for the formula that made it.

    Change a term in `SedimentProxy.index()` and a stored `k` becomes a wrong
    tonnes-per-index scale that still multiplies cleanly — confident wrong masses, no
    error, nothing to notice. So the index is re-verified at load and a mismatch leaves
    the proxy UNANCHORED with the reason attached, degrading to relative classes.
    """
    import importlib
    import json

    anchor_path = PROJECT_ROOT / "data/models/sediment_anchor.json"
    if not anchor_path.exists():
        pytest.skip("anchor not written")

    original = anchor_path.read_text()
    try:
        drifted = json.loads(original)
        drifted["index_at_anchor"] = float(drifted["index_at_anchor"]) * 1.5
        anchor_path.write_text(json.dumps(drifted))

        import models.runoff_model as rm
        importlib.reload(rm)
        bundle = rm._bundle()

        assert not bundle["sediment"].is_anchored, (
            "a drifted anchor was applied anyway — k is now a wrong tonnes-per-index "
            "scale and every mass it produces is confidently wrong"
        )
        status = bundle.get("sediment_anchor_status", "")
        assert "NOT APPLIED" in status and "drift" in status.lower()
    finally:
        anchor_path.write_text(original)
        import models.runoff_model as rm
        importlib.reload(rm)
