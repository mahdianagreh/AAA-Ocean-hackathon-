"""The label rule, at the point where it is actually enforced.

`build_feature_matrix.py` raises if a runoff column reaches the feature set. The
rule is only as good as the list of spellings it checks, and the spelling that
occurs in practice is the prefixed one — `label_surface_runoff_mm`, which does NOT
start with `surface_runoff`. The guard listed only the raw names, so it had a hole
exactly where the real labels arrive.

These tests pin the hole shut and pin down the target-definition trap that sits
behind it: the label is nonzero almost everywhere, so a `> 0` classification target
scores ~98 % while learning nothing.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
ANTECEDENTS = PROJECT_ROOT / "data" / "processed" / "features" / "event_antecedents.parquet"
MATRIX = PROJECT_ROOT / "data" / "processed" / "features" / "event_catchment_features.parquet"


def _load(name: str):
    """Load a script by path without leaving scripts/ on sys.path.

    `scripts/config.py` is a module and `backend/src/config/` is a package, both
    importable as `config`; leaving scripts/ on the path breaks five other test
    files at collection time.
    """
    saved_path, saved_config = list(sys.path), sys.modules.get("config")
    sys.path.insert(0, str(SCRIPTS))
    try:
        sys.modules.pop("config", None)
        spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = saved_path
        if saved_config is not None:
            sys.modules["config"] = saved_config
        else:
            sys.modules.pop("config", None)


builder = _load("build_feature_matrix")


def _is_blocked(column: str) -> bool:
    return any(column.lower().startswith(p) for p in builder.LABEL_ONLY_PREFIXES)


def test_the_prefixed_label_names_are_blocked():
    """The spelling that actually occurs. This is the regression."""
    assert _is_blocked("label_surface_runoff_mm")
    assert _is_blocked("label_subsurface_runoff_mm")


def test_the_raw_label_names_are_still_blocked():
    for column in ("sro", "ssro", "surface_runoff_mm", "subsurface_runoff_hourly_mm"):
        assert _is_blocked(column), column


def test_ordinary_features_are_not_blocked():
    """A guard that rejects real features would be quietly discarding predictors."""
    for column in ("soil_moisture_t_minus_24h", "precipitation_prior_7d_mm",
                   "precipitation_depth_mm", "wind_speed_event_time",
                   "slope_mean_deg", "urban_fraction"):
        assert not _is_blocked(column), column


def test_antecedents_are_registered_as_an_event_level_source():
    """Joined on (event_id, catchment_id), never on catchment_id alone.

    Antecedent values vary by event — that is the entire point of an antecedent
    feature. Joining them on catchment_id would fan the row count out by the number
    of events and the matrix would silently stop being one row per event-catchment.
    """
    assert "antecedent" in builder.EVENT_SOURCES
    assert "antecedent" not in builder.OPTIONAL_SOURCES


@pytest.mark.skipif(not ANTECEDENTS.exists(), reason="antecedents not extracted yet")
def test_a_zero_threshold_target_would_be_useless():
    """The trap behind the label rule: an honest-looking score that means nothing.

    Candidates are already the top ~1 % of days by rainfall, so nearly every one
    produces some ERA5 runoff. `> 0` is therefore ~98 % positive, and the
    majority-class model beats most real models on accuracy while learning nothing.
    """
    frame = pd.read_parquet(ANTECEDENTS)
    y = frame["label_surface_runoff_mm"].dropna()

    assert (y > 0).mean() > 0.9, (
        "if this drops, the >0 target may have become usable and the guidance in "
        "event_antecedents.summary.json should be revisited"
    )
    # And the magnitude does discriminate, which is why regression or a percentile
    # split is the recommended formulation rather than abandoning the label.
    assert y.max() / y.median() > 10


@pytest.mark.skipif(not MATRIX.exists(), reason="matrix not built yet")
def test_no_label_reaches_the_built_matrix():
    """The end-to-end statement, against the real artefact Mahdi trains on."""
    columns = pd.read_parquet(MATRIX).columns
    leaked = [c for c in columns if _is_blocked(c)]
    assert not leaked, f"labels reached the feature matrix: {leaked}"


@pytest.mark.skipif(not MATRIX.exists(), reason="matrix not built yet")
def test_the_matrix_carries_the_antecedent_features():
    """Withholding the labels must not withhold the features that came with them.

    The antecedent source was named in the module docstring but never registered, so
    the matrix shipped without soil moisture or prior rainfall — the event-varying
    predictors — while looking complete at 128 columns.
    """
    columns = set(pd.read_parquet(MATRIX).columns)
    for column in ("soil_moisture_t_minus_24h", "soil_moisture_t_minus_72h",
                   "precipitation_prior_24h_mm", "precipitation_prior_72h_mm",
                   "precipitation_prior_7d_mm"):
        assert column in columns, f"{column} missing from the feature matrix"


@pytest.mark.skipif(not MATRIX.exists(), reason="matrix not built yet")
def test_joining_antecedents_did_not_change_the_row_count():
    """One row per (event, catchment). A left join must not fan out or drop."""
    frame = pd.read_parquet(MATRIX)
    assert len(frame) == frame["event_id"].nunique() * frame["catchment_id"].nunique()
    assert not frame.duplicated(["event_id", "catchment_id"]).any()
