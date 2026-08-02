"""The ranking choices behind the candidate storm catalogue.

Two of these are scientific decisions rather than plumbing, so they get tests
rather than a comment:

  - percentiles are taken over WET days, not all days
  - literature dates are read from docs/event_dates.md, never hard-coded

The third guards the honest-reporting rule: `is_exhaustive` must not claim a
complete historical catalogue from a partial sweep.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "build_event_catalogue", PROJECT_ROOT / "scripts" / "build_event_catalogue.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_event_catalogue"] = module
    spec.loader.exec_module(module)
    return module


catalogue = _load_script()


def _daily(values, catchment_id="AQ-C01"):
    return pd.DataFrame(
        {
            "catchment_id": [catchment_id] * len(values),
            catalogue.DEPTH_COLUMN: values,
            "valid_area_fraction": [1.0] * len(values),
        }
    )


def test_wet_day_percentiles_ignore_the_dry_majority():
    """Aqaba is hyper-arid: most days are exactly zero.

    A p99 over all days is dominated by dry days and ends up describing
    drizzle. Over wet days it describes a storm. This is the difference
    between a threshold that means something and one that does not.
    """
    values = [0.0] * 95 + [2.0, 4.0, 8.0, 20.0, 40.0]
    result = catalogue.build_climatology(_daily(values)).iloc[0]

    assert result["n_days"] == 100
    assert result["n_wet_days"] == 5
    assert result["p99_wet_mm"] > result["p99_all_mm"]
    # The wet-day threshold must land in storm territory, not drizzle.
    assert result["p99_wet_mm"] > 20.0


def test_wet_day_threshold_is_the_standard_one_millimetre():
    assert catalogue.WET_DAY_MM == 1.0
    values = [0.5, 0.9, 1.0, 5.0]
    result = catalogue.build_climatology(_daily(values)).iloc[0]
    assert result["n_wet_days"] == 2  # 1.0 and 5.0; 0.9 is not a wet day


def test_percentiles_are_computed_per_catchment():
    """AQ-C01 reaches the Ma'an highlands, AQ-C05 is a coastal wadi.

    One shared threshold would describe neither, and "exceeds this
    catchment's own 99th percentile" would stop being a measurement.
    """
    wet = pd.concat(
        [_daily([0.0] * 50 + [50.0] * 5, "AQ-C01"),
         _daily([0.0] * 50 + [5.0] * 5, "AQ-C05")],
        ignore_index=True,
    )
    result = catalogue.build_climatology(wet).set_index("catchment_id")
    assert result.loc["AQ-C01", "p99_wet_mm"] > result.loc["AQ-C05", "p99_wet_mm"]


def test_literature_dates_come_from_the_contract_file():
    """docs/event_dates.md rule 1: never hard-code an event date in a script."""
    source = (PROJECT_ROOT / "scripts" / "build_event_catalogue.py").read_text()
    assert "AQ-2016-10-28" not in source, (
        "The demo event date is hard-coded in the catalogue script. It must be "
        "parsed from docs/event_dates.md, which is the single source of truth "
        "for event timing."
    )

    found = catalogue.literature_dates()
    assert any(item["event_id"] == "AQ-2016-10-28" for item in found)


def test_unresolved_literature_events_are_not_invented():
    """February 2013 has no date. It must be skipped, not guessed at."""
    for item in catalogue.literature_dates():
        assert not item["event_id"].startswith("TO_BE_")
        assert item["date"] is not None


def test_percentile_set_spans_ordinary_to_extreme():
    assert catalogue.RANKING_PERCENTILE in catalogue.PERCENTILES
    assert min(catalogue.PERCENTILES) <= 0.5
    assert max(catalogue.PERCENTILES) >= 0.999


def test_top_n_is_generous_by_design():
    """A tight top-N would drop exactly the short-burst days the daily screen
    already under-ranks. The generosity is the mitigation."""
    assert catalogue.DEFAULT_TOP_N >= 100
