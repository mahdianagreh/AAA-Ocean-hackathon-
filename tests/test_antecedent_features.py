"""Synthetic tests for event-agnostic antecedent feature extraction.

No project data file is required and no network access occurs.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from processing.antecedent_features import (  # noqa: E402
    WIND_DIRECTION_CONVENTION,
    AntecedentFeatureError,
    antecedent_features_to_dataframe,
    extract_antecedent_features,
)

START = "2016-10-20T00:00:00"
EVENT = datetime(2016, 10, 28, 0, 0, tzinfo=timezone.utc)
N_LAT, N_LON = 2, 2


def make_dataset(
    n_hours: int = 200,
    rain_mm_per_hour: float = 1.0,
    soil_base: float = 0.10,
    u: float = 3.0,
    v: float = 4.0,
    temperature: float = 295.0,
    sea_cells: tuple[tuple[int, int], ...] = ((0, 0),),
    nan_hours: tuple[int, ...] = (),
) -> xr.Dataset:
    """Hourly ERA5-Land-shaped dataset with known constant values."""
    times = np.array(
        [np.datetime64(START) + np.timedelta64(i, "h") for i in range(n_hours)]
    )
    shape = (n_hours, N_LAT, N_LON)

    def field(value: float) -> np.ndarray:
        array = np.full(shape, value, dtype="float64")
        for row, col in sea_cells:
            array[:, row, col] = np.nan
        return array

    rain = field(rain_mm_per_hour)
    for hour in nan_hours:
        rain[hour, :, :] = np.nan

    # Soil moisture rises 0.001 per hour so each lag has a distinct value.
    soil = field(soil_base)
    ramp = np.arange(n_hours, dtype="float64") * 0.001
    soil = soil + ramp[:, None, None]
    for row, col in sea_cells:
        soil[:, row, col] = np.nan

    dataset = xr.Dataset(
        {
            "total_precipitation_hourly_mm": (("time", "lat", "lon"), rain),
            "surface_runoff_hourly_mm": (("time", "lat", "lon"), field(0.5)),
            "subsurface_runoff_hourly_mm": (("time", "lat", "lon"), field(0.25)),
            "swvl1": (("time", "lat", "lon"), soil),
            "u10": (("time", "lat", "lon"), field(u)),
            "v10": (("time", "lat", "lon"), field(v)),
            "t2m": (("time", "lat", "lon"), field(temperature)),
        },
        coords={
            "time": times,
            "lat": np.array([29.3, 29.4]),
            "lon": np.array([34.8, 34.9]),
        },
    )
    dataset["total_precipitation_hourly_mm"].attrs["units"] = "mm"
    dataset["swvl1"].attrs["units"] = "m**3 m**-3"
    dataset["u10"].attrs["units"] = "m s**-1"
    dataset["v10"].attrs["units"] = "m s**-1"
    dataset["t2m"].attrs["units"] = "K"
    dataset.attrs["temporal_semantics_mode"] = "cumulative"
    dataset.attrs["source_product"] = "ERA5-Land Hourly"
    return dataset


def land(values: xr.DataArray) -> float:
    return float(np.asarray(values.values, dtype="float64")[-1, -1])


@pytest.fixture
def features():
    return extract_antecedent_features(make_dataset(), EVENT)


# --- window sums -----------------------------------------------------------


def test_precipitation_windows_are_exact(features) -> None:
    assert land(features["precipitation_prior_24h_mm"]) == pytest.approx(24.0)
    assert land(features["precipitation_prior_72h_mm"]) == pytest.approx(72.0)
    assert land(features["precipitation_prior_7d_mm"]) == pytest.approx(168.0)


def test_runoff_windows_are_exact(features) -> None:
    assert land(features["surface_runoff_prior_24h_mm"]) == pytest.approx(12.0)
    assert land(features["surface_runoff_prior_7d_mm"]) == pytest.approx(84.0)
    assert land(features["subsurface_runoff_prior_24h_mm"]) == pytest.approx(6.0)
    assert land(features["subsurface_runoff_prior_72h_mm"]) == pytest.approx(18.0)


def test_window_is_exclusive_of_start_inclusive_of_event() -> None:
    """(event - 24h, event] is 24 hourly stamps, not 25."""
    ds = make_dataset()
    out = extract_antecedent_features(ds, EVENT)
    assert land(out["precipitation_prior_24h_mm"]) == pytest.approx(24.0)


# --- exact lag selection ---------------------------------------------------


def test_soil_moisture_lags_select_exact_timestamps() -> None:
    ds = make_dataset()
    out = extract_antecedent_features(ds, EVENT)
    times = pd.DatetimeIndex(ds["time"].values)
    event = pd.Timestamp("2016-10-28T00:00:00")

    for offset in (24, 72):
        expected_index = int(np.where(times == event - pd.Timedelta(hours=offset))[0][0])
        expected = float(ds["swvl1"].values[expected_index, -1, -1])
        assert land(out[f"soil_moisture_t_minus_{offset}h"]) == pytest.approx(expected)

    # The two lags must differ, proving real selection rather than reuse.
    assert land(out["soil_moisture_t_minus_24h"]) != pytest.approx(
        land(out["soil_moisture_t_minus_72h"])
    )


# --- wind ------------------------------------------------------------------


def test_wind_speed_is_pythagorean(features) -> None:
    assert land(features["wind_speed_event_time"]) == pytest.approx(5.0)


@pytest.mark.parametrize(
    ("u", "v", "expected"),
    [
        (0.0, -1.0, 0.0),     # blowing toward the south -> FROM the north
        (-1.0, 0.0, 90.0),    # toward the west -> FROM the east
        (0.0, 1.0, 180.0),    # toward the north -> FROM the south
        (1.0, 0.0, 270.0),    # toward the east -> FROM the west
    ],
)
def test_wind_direction_meteorological_convention(u, v, expected) -> None:
    out = extract_antecedent_features(make_dataset(u=u, v=v), EVENT)
    assert land(out["wind_direction_event_time"]) == pytest.approx(expected)
    assert "blows FROM" in WIND_DIRECTION_CONVENTION


def test_state_window_means(features) -> None:
    assert land(features["mean_wind_speed_prior_state_window"]) == pytest.approx(5.0)
    assert land(features["mean_temperature_prior_state_window"]) == pytest.approx(295.0)
    assert land(features["temperature_2m_event_time"]) == pytest.approx(295.0)


# --- missing data ----------------------------------------------------------


def test_missing_hours_are_not_zero() -> None:
    """Six NaN hours in the last day reduce the total, not to zero-filled."""
    ds = make_dataset(nan_hours=tuple(range(186, 192)))
    out = extract_antecedent_features(ds, EVENT, minimum_valid_fraction=0.5)

    total = land(out["precipitation_prior_24h_mm"])
    assert total == pytest.approx(18.0), "only the 18 valid hours should count"
    assert total != pytest.approx(24.0)
    fraction = land(out["precipitation_prior_24h_mm_valid_fraction"])
    assert fraction == pytest.approx(18 / 24)


def test_partial_window_is_flagged() -> None:
    ds = make_dataset(nan_hours=tuple(range(186, 192)))
    out = extract_antecedent_features(ds, EVENT, minimum_valid_fraction=1.0)
    flags = np.asarray(out["quality_flag"].values)
    assert flags[-1, -1] in ("PARTIAL_WINDOW", "MISSING_DATA")


def test_sea_mask_propagates_to_features(features) -> None:
    for name in ("precipitation_prior_24h_mm", "soil_moisture_t_minus_24h",
                 "wind_speed_event_time"):
        values = np.asarray(features[name].values, dtype="float64")
        assert np.isnan(values[0, 0]), f"{name} filled a sea cell"


def test_sea_cells_flagged_no_data(features) -> None:
    flags = np.asarray(features["quality_flag"].values)
    assert flags[0, 0] == "NO_DATA"
    assert flags[-1, -1] == "GOOD"


# --- validation ------------------------------------------------------------


def test_incomplete_history_raises() -> None:
    ds = make_dataset(n_hours=48)          # not enough for a 168 h window
    with pytest.raises(AntecedentFeatureError, match="longest requested window"):
        extract_antecedent_features(
            ds, datetime(2016, 10, 21, 0, tzinfo=timezone.utc)
        )


def test_incomplete_history_allowed_when_opted_in() -> None:
    ds = make_dataset(n_hours=48)
    out = extract_antecedent_features(
        ds, datetime(2016, 10, 21, 0, tzinfo=timezone.utc),
        require_full_windows=False, minimum_valid_fraction=0.1,
    )
    assert "precipitation_prior_7d_mm" in out.data_vars
    # 24 hours of history exist, so the 7-day window is only partly covered.
    assert land(out["precipitation_prior_7d_mm_valid_fraction"]) < 1.0


def test_event_outside_range_raises() -> None:
    ds = make_dataset()
    with pytest.raises(AntecedentFeatureError, match="outside the dataset"):
        extract_antecedent_features(
            ds, datetime(2020, 1, 1, 0, tzinfo=timezone.utc)
        )


def test_non_utc_event_rejected() -> None:
    ds = make_dataset()
    local = datetime(2016, 10, 28, 3, tzinfo=timezone(timedelta(hours=3)))
    with pytest.raises(AntecedentFeatureError, match="must be UTC"):
        extract_antecedent_features(ds, local)


def test_non_hour_aligned_event_rejected() -> None:
    ds = make_dataset()
    with pytest.raises(AntecedentFeatureError, match="hour-aligned"):
        extract_antecedent_features(
            ds, datetime(2016, 10, 28, 0, 30, tzinfo=timezone.utc)
        )


def test_naive_event_time_treated_as_utc() -> None:
    ds = make_dataset()
    out = extract_antecedent_features(ds, datetime(2016, 10, 28, 0, 0))
    assert out.attrs["event_time_utc"] == "2016-10-28T00:00:00Z"


def test_event_agnostic_different_timestamp() -> None:
    """The same code must work for a completely different event time."""
    ds = make_dataset()
    other = datetime(2016, 10, 27, 12, 0, tzinfo=timezone.utc)
    out = extract_antecedent_features(ds, other)
    assert out.attrs["event_time_utc"] == "2016-10-27T12:00:00Z"
    assert land(out["precipitation_prior_24h_mm"]) == pytest.approx(24.0)


def test_custom_windows_are_honoured() -> None:
    ds = make_dataset()
    out = extract_antecedent_features(
        ds, EVENT,
        soil_moisture_offsets_hours=(12,),
        precipitation_windows_hours=(6, 48),
        runoff_windows_hours=(6,),
        state_window_hours=3,
    )
    assert "soil_moisture_t_minus_12h" in out.data_vars
    assert land(out["precipitation_prior_6h_mm"]) == pytest.approx(6.0)
    assert land(out["precipitation_prior_48h_mm"]) == pytest.approx(48.0)
    assert "precipitation_prior_24h_mm" not in out.data_vars


def test_dataset_attributes(features) -> None:
    assert features.attrs["event_time_utc"] == "2016-10-28T00:00:00Z"
    assert features.attrs["canonical_timezone"] == "UTC"
    assert features.attrs["interpolation_performed"] == "no"
    assert "preserve_nan" in features.attrs["missing_data_policy"]
    assert features.attrs["temporal_semantics_mode"] == "cumulative"
    assert "precipitation" in features.attrs["feature_window"]


# --- exporter --------------------------------------------------------------


def test_dataframe_exporter(features) -> None:
    frame = antecedent_features_to_dataframe(features, "AQ-TEST-01")

    assert len(frame) == N_LAT * N_LON
    for column in ("event_id", "event_time_utc", "lat", "lon",
                   "precipitation_prior_24h_mm", "wind_speed_event_time",
                   "valid_data_fraction", "quality_flag"):
        assert column in frame.columns
    assert (frame["event_id"] == "AQ-TEST-01").all()
    assert frame.columns[-1] == "quality_flag"

    row = frame[(frame.lat == 29.4) & (frame.lon == 34.9)].iloc[0]
    assert row["precipitation_prior_24h_mm"] == pytest.approx(24.0)
    assert row["quality_flag"] == "GOOD"


def test_no_network_during_extraction(monkeypatch) -> None:
    import socket

    def deny(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("network access attempted during pytest")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)

    out = extract_antecedent_features(make_dataset(), EVENT)
    frame = antecedent_features_to_dataframe(out, "AQ-TEST-02")
    assert len(frame) == N_LAT * N_LON
