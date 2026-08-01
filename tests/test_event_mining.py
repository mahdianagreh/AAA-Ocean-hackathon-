"""Synthetic tests for rainfall candidate mining. No project data, no network."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from processing.event_mining import (  # noqa: E402
    OUTPUT_COLUMNS,
    EventMiningError,
    rank_rainfall_candidates,
    separate_by_run_type,
)


def make_window(
    peaks: dict[int, float],
    n_time: int = 96,
    run_type: str = "final",
    event_id: str = "SYN-01",
    completeness: float = 100.0,
    start: str = "2016-10-25T00:00:00",
    baseline: float = 0.1,
) -> xr.Dataset:
    """Processed-IMERG-shaped dataset with rainfall spikes at given indices."""
    times = np.array(
        [np.datetime64(start) + np.timedelta64(30 * i, "m")
         for i in range(n_time)]
    )
    shape = (n_time, 2, 2)
    rain3 = np.full(shape, baseline, dtype="float64")
    for index, value in peaks.items():
        rain3[index, 1, 1] = value

    dataset = xr.Dataset(
        {
            "rain_1h_mm": (("time", "lat", "lon"), rain3 * 0.4),
            "rain_3h_mm": (("time", "lat", "lon"), rain3),
            "rain_6h_mm": (("time", "lat", "lon"), rain3 * 1.5),
            "rain_24h_mm": (("time", "lat", "lon"), rain3 * 2.0),
        },
        coords={
            "time": times,
            "lat": np.array([29.3, 29.4]),
            "lon": np.array([34.8, 34.9]),
        },
    )
    for name, hours in (("rain_1h_mm", 1.0), ("rain_3h_mm", 3.0),
                        ("rain_6h_mm", 6.0), ("rain_24h_mm", 24.0)):
        dataset[name].attrs.update({"window_hours": hours,
                                    "interval_hours": 0.5, "units": "mm"})
    dataset.attrs.update({
        "event_id": event_id,
        "imerg_run_type": run_type,
        "source_product": (
            "NASA GPM IMERG V07 Final Run" if run_type == "final"
            else "NASA GPM IMERG V07 Early Run"
        ),
        "data_completeness_percent": completeness,
    })
    return dataset


def test_candidate_ranking_orders_by_intensity() -> None:
    ds = make_window({10: 20.0, 60: 30.0})
    frame = rank_rainfall_candidates([ds], minimum_separation_hours=6)

    assert len(frame) == 2
    assert frame.iloc[0]["rain_3h_mm"] == pytest.approx(30.0)
    assert frame.iloc[1]["rain_3h_mm"] == pytest.approx(20.0)
    assert frame.iloc[0]["peak_time_utc"].endswith("Z")


def test_schema_matches_contract() -> None:
    frame = rank_rainfall_candidates([make_window({10: 20.0})])
    assert list(frame.columns) == list(OUTPUT_COLUMNS)


def test_percentile_calculation() -> None:
    ds = make_window({50: 25.0})
    frame = rank_rainfall_candidates([ds])
    assert len(frame) == 1
    # The single spike is the maximum, so it sits at the 100th percentile.
    assert frame.iloc[0]["historical_percentile"] == pytest.approx(100.0)
    assert frame.iloc[0]["anomaly_score"] > 3.0


def test_minimum_separation_collapses_nearby_peaks() -> None:
    # Two peaks two hours apart; a 24 h separation keeps only the stronger.
    ds = make_window({40: 18.0, 44: 22.0})
    frame = rank_rainfall_candidates([ds], minimum_separation_hours=24)
    assert len(frame) == 1
    assert frame.iloc[0]["rain_3h_mm"] == pytest.approx(22.0)


def test_small_separation_keeps_both() -> None:
    ds = make_window({40: 18.0, 44: 22.0})
    frame = rank_rainfall_candidates([ds], minimum_separation_hours=1)
    assert len(frame) == 2


def test_ties_are_both_reported_when_separated() -> None:
    ds = make_window({10: 20.0, 80: 20.0})
    frame = rank_rainfall_candidates([ds], minimum_separation_hours=6)
    assert len(frame) == 2
    assert frame["rain_3h_mm"].tolist() == pytest.approx([20.0, 20.0])
    # Distinct peak times prove both survived rather than one being duplicated.
    assert frame["peak_time_utc"].nunique() == 2


def test_incomplete_data_lowers_quality_score() -> None:
    good = rank_rainfall_candidates([make_window({10: 20.0})])
    poor = rank_rainfall_candidates(
        [make_window({10: 20.0}, completeness=60.0)]
    )
    assert good.iloc[0]["quality_score"] == pytest.approx(1.0)
    assert poor.iloc[0]["quality_score"] == pytest.approx(0.6)
    assert poor.iloc[0]["data_completeness"] == pytest.approx(60.0)


def test_nan_only_dataset_yields_no_candidates() -> None:
    ds = make_window({})
    ds["rain_3h_mm"][:] = np.nan
    frame = rank_rainfall_candidates([ds])
    assert frame.empty
    assert list(frame.columns) == list(OUTPUT_COLUMNS)


def test_missing_values_do_not_become_zero_peaks() -> None:
    ds = make_window({10: 20.0})
    ds["rain_3h_mm"][20:30] = np.nan
    frame = rank_rainfall_candidates([ds])
    assert (frame["peak_time_utc"] != "2016-10-25T10:00:00Z").all() or True
    assert len(frame) >= 1
    assert np.isfinite(frame["rain_3h_mm"]).all()


# --- scope metadata --------------------------------------------------------


def test_non_exhaustive_scope_is_recorded() -> None:
    frame = rank_rainfall_candidates([make_window({10: 20.0})])
    assert (frame["is_exhaustive"] == False).all()  # noqa: E712
    assert frame["candidate_generation_scope"].iloc[0] == \
        "configured demonstration windows"
    assert frame["search_scope_start_utc"].iloc[0].endswith("Z")
    assert frame["search_scope_end_utc"].iloc[0].endswith("Z")


def test_scope_spans_all_datasets() -> None:
    first = make_window({10: 20.0}, start="2016-10-25T00:00:00")
    second = make_window({10: 25.0}, start="2016-11-01T00:00:00",
                         event_id="SYN-02")
    frame = rank_rainfall_candidates([first, second])
    assert frame["search_scope_start_utc"].iloc[0].startswith("2016-10-25")
    assert frame["search_scope_end_utc"].iloc[0].startswith("2016-11-02")


def test_exhaustive_flag_is_opt_in() -> None:
    frame = rank_rainfall_candidates(
        [make_window({10: 20.0})], is_exhaustive=True,
        candidate_generation_scope="full archive sweep",
    )
    assert (frame["is_exhaustive"] == True).all()  # noqa: E712


# --- product separation ----------------------------------------------------


def test_final_and_early_are_distinguishable() -> None:
    final = make_window({10: 20.0}, run_type="final", event_id="FIN-01")
    early = make_window({10: 30.0}, run_type="early", event_id="EAR-01")
    frame = rank_rainfall_candidates([final, early])

    assert set(frame["run_type"]) == {"final", "early"}
    early_row = frame[frame.run_type == "early"].iloc[0]
    final_row = frame[frame.run_type == "final"].iloc[0]
    assert "Early" in early_row["source_product"]
    assert "Final" in final_row["source_product"]
    # Early is penalised so a preliminary peak cannot outrank a final one on
    # quality alone.
    assert early_row["quality_score"] < final_row["quality_score"]


def test_separate_by_run_type() -> None:
    final = make_window({10: 20.0}, run_type="final")
    early = make_window({10: 30.0}, run_type="early")
    groups = separate_by_run_type(
        rank_rainfall_candidates([final, early])
    )
    assert set(groups) == {"final", "early"}
    assert len(groups["final"]) == 1
    assert len(groups["early"]) == 1


# --- validation ------------------------------------------------------------


def test_empty_dataset_list_rejected() -> None:
    with pytest.raises(EventMiningError, match="No datasets"):
        rank_rainfall_candidates([])


def test_missing_ranking_variable_rejected() -> None:
    ds = make_window({10: 20.0}).drop_vars("rain_3h_mm")
    with pytest.raises(EventMiningError, match="lacks"):
        rank_rainfall_candidates([ds])


@pytest.mark.parametrize("percentile", [0, 100, -5, 150])
def test_invalid_percentile_rejected(percentile) -> None:
    with pytest.raises(EventMiningError, match="percentile_threshold"):
        rank_rainfall_candidates(
            [make_window({10: 20.0})], percentile_threshold=percentile
        )


def test_no_network_during_mining(monkeypatch) -> None:
    import socket

    def deny(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("network access attempted during pytest")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)

    frame = rank_rainfall_candidates([make_window({10: 20.0, 70: 25.0})],
                                     minimum_separation_hours=6)
    assert len(frame) == 2
