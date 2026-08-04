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
