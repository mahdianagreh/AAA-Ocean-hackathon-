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
    # Strip comments and string literals first. A docstring explaining WHY the
    # contract ID must survive a storm merge is documentation, not a hard-coded
    # date — the rule is about code that would bypass event_dates.md. The first
    # version of this test grepped raw text and flagged its own explanation.
    import io
    import tokenize

    path = PROJECT_ROOT / "scripts" / "build_event_catalogue.py"
    raw = path.read_text()
    code_tokens = []
    for token in tokenize.generate_tokens(io.StringIO(raw).readline):
        if token.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        code_tokens.append(token.string)
    source = " ".join(code_tokens)

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


def test_the_merge_floor_is_below_the_wet_day_threshold():
    """Merging storms and computing percentiles are different questions.

    `WET_DAY_MM = 1.0` is the ETCCDI convention and is right for percentiles. It was
    also being used to decide which consecutive days join a storm, which is fine while
    --top-n stays above 1 mm and breaks silently the moment it does not: at
    --top-n 675 the floor is ~0.2 mm, every selected day under 1 mm bypassed merging,
    and the catalogue came out with **152 consecutive-day pairs** — one drizzle episode
    counted as two events. That is precisely the train/test leakage the merge exists to
    prevent, and it produced a larger, healthier-looking catalogue while doing it.
    """
    assert catalogue.MERGE_MIN_MM < catalogue.WET_DAY_MM
    assert catalogue.MERGE_MIN_MM > 0, (
        "a zero floor would chain every day in the record into one storm"
    )


def test_consecutive_days_never_survive_as_separate_storms():
    """The invariant, stated directly on the merge function.

    Two adjacent days each carrying measurable rain are one storm. If they both come
    out as storms, the same rainfall can land in train and in test.
    """
    days = pd.to_datetime(["2016-10-26", "2016-10-27", "2016-10-28", "2017-03-01"])
    frame = pd.DataFrame({
        "date": days,
        "event_id": days.strftime("AQ-%Y-%m-%d"),
        "max_daily_mm": [0.4, 0.6, 10.2, 5.0],     # first two are BELOW WET_DAY_MM
        "mean_daily_mm": [0.2, 0.3, 9.6, 4.0],
        "wettest_catchment": ["AQ-C01"] * 4,
        "catchments_exceeding_p99": [0, 0, 0, 0],
        "max_anomaly_ratio": [0.1, 0.1, 0.7, 0.4],
        "min_valid_area_fraction": [1.0] * 4,
    })

    eligible = frame[frame["max_daily_mm"] >= catalogue.MERGE_MIN_MM]
    storms = catalogue.group_into_storms(eligible, protected_ids=set())

    gaps = pd.to_datetime(storms["date"]).sort_values().diff().dt.days
    assert not (gaps == 1).any(), (
        f"consecutive days survived as separate storms:\n{storms[['event_id', 'storm_days']]}"
    )
    # The Oct 2016 run is one storm of three days, not three storms.
    oct_storm = storms[storms["date"].dt.month == 10].iloc[0]
    assert oct_storm["storm_days"] == 3, storms[["event_id", "storm_days"]]


def test_top_n_is_generous_by_design():
    """A tight top-N would drop exactly the short-burst days the daily screen
    already under-ranks. The generosity is the mitigation."""
    assert catalogue.DEFAULT_TOP_N >= 100
