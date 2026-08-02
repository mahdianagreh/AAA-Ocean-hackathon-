"""One-granule smoke test for the IMERG ingestion reader.

Runs entirely against the Harmony subset file already on disk. Nothing is
downloaded during pytest, and no existing data file is modified.
Skips cleanly when the smoke-test data is absent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

import xarray as xr  # noqa: E402

from config.spatial import TERRAIN_AOI  # noqa: E402
from ingestion.imerg import (  # noqa: E402
    PRECIPITATION_UNITS,
    ROLLING_WINDOWS,
    SOURCE_PRODUCT,
    add_rolling_accumulations,
    calculate_rainfall_accumulation,
    combine_imerg_subsets,
    find_wettest_window,
    precipitation_rate_to_depth,
    read_imerg_subset,
)

SUBSET_DIR = PROJECT_ROOT / "data" / "raw" / "imerg" / "harmony_smoke_test"
EVENT_DIR = PROJECT_ROOT / "data" / "raw" / "imerg" / "event_smoke_3h"

EVENT_FILE_COUNT = 6
EVENT_COMBINED_SHAPE = (6, 5, 4)
EVENT_GRID_SHAPE = (5, 4)
EVENT_INTERVAL_HOURS = 0.5
EVENT_ACCUMULATION_HOURS = 3.0
EVENT_INTERVAL_MINUTES = 30

# Aqaba padded box on the 0.1-degree IMERG grid: 5 lat x 4 lon cells.
EXPECTED_SHAPE = (1, 5, 4)
EXPECTED_DIMS = ("time", "lat", "lon")

# Coordinates and bounds are expected; anything else is an unrelated science
# variable that the variable-subset request should have excluded.
ALLOWED_NAMES = {
    "precipitation", "precipitation_depth_mm",
    "lat", "lon", "time", "lat_bnds", "lon_bnds", "time_bnds",
    "latv", "lonv", "nv", "crs", "spatial_ref",
}


def _find_subset_file() -> Path | None:
    if not SUBSET_DIR.is_dir():
        return None
    candidates = sorted(SUBSET_DIR.glob("*.nc*"))
    return candidates[0] if candidates else None


@pytest.fixture(scope="module")
def subset_path() -> Path:
    path = _find_subset_file()
    if path is None:
        pytest.skip(
            f"No Harmony smoke-test file in {SUBSET_DIR}. "
            "Run scripts/download_imerg_harmony_subset.py first."
        )
    return path


@pytest.fixture(scope="module")
def dataset(subset_path: Path):
    ds = read_imerg_subset(subset_path)
    yield ds
    ds.close()


def test_precipitation_exists(dataset) -> None:
    assert "precipitation" in dataset.variables


def test_dimensions_are_normalized(dataset) -> None:
    assert tuple(dataset["precipitation"].dims) == EXPECTED_DIMS


def test_shape_matches_aqaba_box(dataset) -> None:
    assert dataset["precipitation"].shape == EXPECTED_SHAPE


def test_units_are_rate_not_depth(dataset) -> None:
    assert dataset["precipitation"].attrs["units"] == PRECIPITATION_UNITS


def test_source_product_attribute(dataset) -> None:
    assert dataset.attrs["source_product"] == SOURCE_PRODUCT


def test_time_coordinate_preserved(dataset) -> None:
    assert "time" in dataset.coords
    assert dataset["time"].size == 1


def test_depth_is_derived_correctly(dataset) -> None:
    interval = 0.5
    result = precipitation_rate_to_depth(dataset, interval_hours=interval)

    assert "precipitation_depth_mm" in result.variables
    assert result["precipitation_depth_mm"].attrs["units"] == "mm"
    assert result["precipitation_depth_mm"].shape == EXPECTED_SHAPE

    # The rate must survive untouched alongside the derived depth.
    assert "precipitation" in result.variables
    assert result["precipitation"].attrs["units"] == PRECIPITATION_UNITS

    rate = result["precipitation"].values
    depth = result["precipitation_depth_mm"].values
    np.testing.assert_allclose(depth, rate * interval, rtol=1e-6, atol=1e-9,
                               equal_nan=True)


def test_no_unrelated_science_variables(dataset) -> None:
    names = set(map(str, dataset.variables)) | set(map(str, dataset.coords))
    unexpected = names - ALLOWED_NAMES
    assert not unexpected, f"unrelated variables present: {sorted(unexpected)}"


def test_values_are_finite_or_nan(dataset) -> None:
    values = dataset["precipitation"].values
    assert np.all(np.isfinite(values) | np.isnan(values))
    # A fill sentinel surviving into the data would break downstream maths.
    assert not np.any(np.isclose(values[~np.isnan(values)], -9999.9, atol=0.5))


def test_invalid_interval_is_rejected(dataset) -> None:
    with pytest.raises(ValueError):
        precipitation_rate_to_depth(dataset, interval_hours=0)


# ---------------------------------------------------------------------------
# 3-hour event window: combine + accumulate
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def event_paths() -> list[Path]:
    if not EVENT_DIR.is_dir():
        pytest.skip(f"No event smoke-test directory at {EVENT_DIR}.")
    paths = sorted(p for p in EVENT_DIR.glob("*.nc*") if p.is_file())
    if len(paths) != EVENT_FILE_COUNT:
        pytest.skip(
            f"Expected {EVENT_FILE_COUNT} granules in {EVENT_DIR}, "
            f"found {len(paths)}. Run "
            "scripts/download_imerg_event_smoke.py first."
        )
    return paths


@pytest.fixture(scope="module")
def combined(event_paths: list[Path]):
    ds = combine_imerg_subsets(
        event_paths, expected_interval_minutes=EVENT_INTERVAL_MINUTES
    )
    yield ds
    ds.close()


@pytest.fixture(scope="module")
def accumulated(combined):
    ds = calculate_rainfall_accumulation(
        combined,
        interval_hours=EVENT_INTERVAL_HOURS,
        output_variable="rain_3h_mm",
    )
    yield ds
    ds.close()


def test_six_files_combine_to_expected_shape(combined) -> None:
    assert combined["precipitation"].shape == EVENT_COMBINED_SHAPE
    assert tuple(combined["precipitation"].dims) == ("time", "lat", "lon")


def test_combined_timestamps_unique_and_ascending(combined) -> None:
    times = list(np.atleast_1d(combined["time"].values))
    assert len(times) == EVENT_FILE_COUNT
    labels = [t.strftime("%Y-%m-%dT%H:%M:%S") for t in times]
    assert len(set(labels)) == EVENT_FILE_COUNT, "timestamps are not unique"
    assert labels == sorted(labels), "timestamps are not ascending"


def test_combined_spacing_is_thirty_minutes(combined) -> None:
    times = list(np.atleast_1d(combined["time"].values))
    gaps = {(b - a).total_seconds() / 60 for a, b in zip(times, times[1:])}
    assert gaps == {float(EVENT_INTERVAL_MINUTES)}


def test_accumulation_has_grid_dimensions(accumulated) -> None:
    rain = accumulated["rain_3h_mm"]
    assert tuple(rain.dims) == ("lat", "lon")
    assert rain.shape == EVENT_GRID_SHAPE


def test_accumulation_equals_explicit_half_hour_sum(accumulated) -> None:
    rates = np.asarray(accumulated["precipitation"].values, dtype="float64")
    manual = np.zeros(EVENT_GRID_SHAPE, dtype="float64")
    for step in range(rates.shape[0]):
        manual += rates[step] * EVENT_INTERVAL_HOURS

    produced = np.asarray(accumulated["rain_3h_mm"].values, dtype="float64")
    np.testing.assert_allclose(produced, manual, rtol=1e-6, atol=1e-9,
                               equal_nan=True)


def test_accumulation_units_are_mm(accumulated) -> None:
    assert accumulated["rain_3h_mm"].attrs["units"] == "mm"


def test_accumulation_hours_is_three(accumulated) -> None:
    # Derived as interval_hours * n_steps, not hard-coded in the function.
    assert accumulated["rain_3h_mm"].attrs["accumulation_hours"] == pytest.approx(
        EVENT_ACCUMULATION_HOURS
    )
    assert accumulated["rain_3h_mm"].attrs["interval_count"] == EVENT_FILE_COUNT


def test_accumulation_window_bounds(accumulated) -> None:
    attrs = accumulated["rain_3h_mm"].attrs
    assert attrs["window_start_utc"] == "2016-10-27T03:00:00Z"
    assert attrs["window_end_utc"] == "2016-10-27T06:00:00Z"


def test_at_least_one_cell_has_rainfall(accumulated) -> None:
    values = np.asarray(accumulated["rain_3h_mm"].values, dtype="float64")
    valid = values[~np.isnan(values)]
    assert valid.size, "no valid accumulation cells"
    assert (valid > 0).any(), "expected non-zero rainfall in the window"


def test_rate_preserved_alongside_accumulation(accumulated) -> None:
    assert accumulated["precipitation"].attrs["units"] == PRECIPITATION_UNITS
    assert accumulated["precipitation"].shape == EVENT_COMBINED_SHAPE
    assert accumulated.attrs["source_product"] == SOURCE_PRODUCT


def test_duplicate_timestamps_raise_clear_error(event_paths) -> None:
    duplicated = [event_paths[0], event_paths[0]]
    with pytest.raises(ValueError, match="Duplicate timestamps"):
        combine_imerg_subsets(
            duplicated, expected_interval_minutes=EVENT_INTERVAL_MINUTES
        )


def test_missing_interval_raises_clear_error(event_paths) -> None:
    # Skip the third granule so the 03:30 -> 04:30 gap becomes 60 minutes.
    with_gap = [event_paths[0], event_paths[1], event_paths[3]]
    with pytest.raises(ValueError, match="Irregular or missing"):
        combine_imerg_subsets(
            with_gap, expected_interval_minutes=EVENT_INTERVAL_MINUTES
        )


def test_no_network_access_during_pipeline(event_paths, monkeypatch) -> None:
    """The combine + accumulate path must be fully offline."""
    import socket

    def deny(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("network access attempted during pytest")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny, raising=False)

    dataset = combine_imerg_subsets(
        event_paths, expected_interval_minutes=EVENT_INTERVAL_MINUTES
    )
    try:
        result = calculate_rainfall_accumulation(
            dataset, interval_hours=EVENT_INTERVAL_HOURS
        )
        assert result["rain_3h_mm"].shape == EVENT_GRID_SHAPE
        result.close()
    finally:
        dataset.close()


def test_negative_precipitation_is_rejected(combined) -> None:
    corrupted = combined.copy(deep=True)
    corrupted["precipitation"][0, 0, 0] = -1.0
    with pytest.raises(ValueError, match="Negative precipitation"):
        calculate_rainfall_accumulation(corrupted)
    corrupted.close()


# ---------------------------------------------------------------------------
# Rolling accumulations — synthetic data only, no downloaded files needed
# ---------------------------------------------------------------------------

SYNTHETIC_STEPS = 60
SYNTHETIC_INTERVAL_HOURS = 0.5


def make_synthetic(
    n_time: int = SYNTHETIC_STEPS,
    n_lat: int = 2,
    n_lon: int = 3,
    rate_value: float = 2.0,
    nan_at: tuple[int, int, int] | None = None,
) -> xr.Dataset:
    """Build an IMERG-shaped dataset with a known constant rate.

    A constant 2.0 mm/hr makes every expected rolling total exact:
    2.0 mm/hr * 0.5 h = 1.0 mm per interval, so an N-interval window is
    N millimetres.
    """
    times = np.array(
        [np.datetime64("2016-10-25T00:00:00") + np.timedelta64(30 * i, "m")
         for i in range(n_time)]
    )
    rate = np.full((n_time, n_lat, n_lon), rate_value, dtype="float32")
    if nan_at is not None:
        rate[nan_at] = np.nan

    dataset = xr.Dataset(
        {"precipitation": (("time", "lat", "lon"), rate)},
        coords={
            "time": times,
            "lat": np.linspace(29.25, 29.65, n_lat).astype("float32"),
            "lon": np.linspace(34.85, 35.15, n_lon).astype("float32"),
        },
    )
    dataset["precipitation"].attrs["units"] = PRECIPITATION_UNITS
    return precipitation_rate_to_depth(
        dataset, interval_hours=SYNTHETIC_INTERVAL_HOURS
    )


@pytest.fixture
def synthetic():
    ds = make_synthetic()
    yield ds
    ds.close()


@pytest.fixture
def rolled(synthetic):
    ds = add_rolling_accumulations(
        synthetic, windows=ROLLING_WINDOWS,
        interval_hours=SYNTHETIC_INTERVAL_HOURS,
    )
    yield ds
    ds.close()


def test_rolling_interval_counts_are_2_6_12_48() -> None:
    assert ROLLING_WINDOWS == {
        "rain_1h_mm": 2,
        "rain_3h_mm": 6,
        "rain_6h_mm": 12,
        "rain_24h_mm": 48,
    }


@pytest.mark.parametrize(
    ("name", "count", "hours"),
    [("rain_1h_mm", 2, 1.0), ("rain_3h_mm", 6, 3.0),
     ("rain_6h_mm", 12, 6.0), ("rain_24h_mm", 48, 24.0)],
)
def test_rolling_attributes_and_dims(rolled, name, count, hours) -> None:
    array = rolled[name]
    assert tuple(array.dims) == ("time", "lat", "lon")
    assert array.attrs["units"] == "mm"
    assert array.attrs["interval_count"] == count
    assert array.attrs["window_hours"] == pytest.approx(hours)
    assert array.attrs["interval_hours"] == pytest.approx(0.5)
    assert array.attrs["rolling_alignment"] == "trailing"
    assert array.attrs["missing_data_policy"] == "propagate_nan"


@pytest.mark.parametrize(
    ("name", "count"),
    [("rain_1h_mm", 2), ("rain_3h_mm", 6),
     ("rain_6h_mm", 12), ("rain_24h_mm", 48)],
)
def test_first_valid_timestamp_per_duration(rolled, name, count) -> None:
    """min_periods == interval_count: the first count-1 steps must be NaN."""
    values = np.asarray(rolled[name].values, dtype="float64")
    assert np.all(np.isnan(values[: count - 1])), (
        f"{name}: expected NaN before a full window"
    )
    assert np.all(np.isfinite(values[count - 1:])), (
        f"{name}: expected all-finite once a full window exists"
    )


@pytest.mark.parametrize(
    ("name", "count"),
    [("rain_1h_mm", 2), ("rain_3h_mm", 6),
     ("rain_6h_mm", 12), ("rain_24h_mm", 48)],
)
def test_trailing_window_values_are_exact(rolled, name, count) -> None:
    """Constant 2 mm/hr -> 1 mm per interval -> N mm over N intervals."""
    values = np.asarray(rolled[name].values, dtype="float64")
    np.testing.assert_allclose(values[count - 1:], float(count),
                               rtol=1e-6, atol=1e-6)


def test_trailing_not_centered() -> None:
    """A single wet interval must appear at and after its own index only."""
    ds = make_synthetic(n_time=10, n_lat=1, n_lon=1, rate_value=0.0)
    ds["precipitation"][4, 0, 0] = 2.0
    ds = precipitation_rate_to_depth(ds, interval_hours=0.5)
    out = add_rolling_accumulations(
        ds, windows={"rain_1h_mm": 2}, interval_hours=0.5
    )
    series = np.asarray(out["rain_1h_mm"].values, dtype="float64").ravel()

    assert np.isnan(series[0])
    assert series[3] == pytest.approx(0.0)   # window covers steps 2-3: dry
    assert series[4] == pytest.approx(1.0)   # covers 3-4: includes the wet one
    assert series[5] == pytest.approx(1.0)   # covers 4-5: still includes it
    assert series[6] == pytest.approx(0.0)   # trailing window has moved past
    out.close()
    ds.close()


def test_skipna_false_propagates_nan() -> None:
    """One NaN interval must poison every window that contains it."""
    gap = 8
    ds = make_synthetic(n_time=20, n_lat=1, n_lon=1, nan_at=(gap, 0, 0))
    out = add_rolling_accumulations(
        ds, windows={"rain_3h_mm": 6}, interval_hours=0.5
    )
    series = np.asarray(out["rain_3h_mm"].values, dtype="float64").ravel()

    # Indices 0-4 are NaN from min_periods, not from the gap.
    assert np.all(np.isnan(series[:5]))
    # Window ending at 7 covers 2..7 — complete and gap-free.
    assert series[7] == pytest.approx(6.0)
    # Windows ending at 8..13 all include the gap at index 8 -> NaN.
    assert np.all(np.isnan(series[gap:gap + 6]))
    # Window ending at 14 covers 9..14 — first one fully past the gap.
    assert series[14] == pytest.approx(6.0)
    out.close()
    ds.close()


def test_missing_value_is_not_treated_as_zero() -> None:
    ds = make_synthetic(n_time=6, n_lat=1, n_lon=1, nan_at=(2, 0, 0))
    out = add_rolling_accumulations(
        ds, windows={"rain_3h_mm": 6}, interval_hours=0.5
    )
    value = float(np.asarray(out["rain_3h_mm"].values).ravel()[-1])
    assert np.isnan(value), "a gap must not be summed as zero (would give 5.0)"
    out.close()
    ds.close()


def test_wettest_window_extraction() -> None:
    """The maximum must be found at the injected spike, not elsewhere."""
    ds = make_synthetic(n_time=20, n_lat=2, n_lon=3, rate_value=1.0)
    ds["precipitation"][10, 1, 2] = 50.0
    ds = precipitation_rate_to_depth(ds, interval_hours=0.5)
    out = add_rolling_accumulations(
        ds, windows={"rain_3h_mm": 6}, interval_hours=0.5
    )

    info = find_wettest_window(out, "rain_3h_mm", interval_hours=0.5)
    # 5 dry-ish intervals at 0.5 mm each + the 25 mm spike = 27.5 mm
    assert info["max_mm"] == pytest.approx(27.5)
    assert info["lat"] == pytest.approx(float(out["lat"].values[1]))
    assert info["lon"] == pytest.approx(float(out["lon"].values[2]))
    assert info["interval_count"] == 6
    assert info["window_hours"] == pytest.approx(3.0)
    out.close()
    ds.close()


def test_wettest_window_start_end_calculation() -> None:
    """Window spans [label - (n-1)*interval, label + interval)."""
    ds = make_synthetic(n_time=20, n_lat=1, n_lon=1, rate_value=0.0)
    ds["precipitation"][10, 0, 0] = 10.0
    ds = precipitation_rate_to_depth(ds, interval_hours=0.5)
    out = add_rolling_accumulations(
        ds, windows={"rain_3h_mm": 6}, interval_hours=0.5
    )

    info = find_wettest_window(out, "rain_3h_mm", interval_hours=0.5)
    # First window containing index 10 is the one labelled index 10:
    # covers indices 5..10 -> starts 02:30, ends 05:30 + 30 min = 05:30Z..
    assert info["label_timestamp_utc"] == "2016-10-25T05:00:00Z"
    assert info["window_start_utc"] == "2016-10-25T02:30:00Z"
    assert info["window_end_utc"] == "2016-10-25T05:30:00Z"

    start = np.datetime64(info["window_start_utc"].rstrip("Z"))
    end = np.datetime64(info["window_end_utc"].rstrip("Z"))
    hours = (end - start) / np.timedelta64(1, "h")
    assert hours == pytest.approx(3.0), "window span must equal window_hours"
    out.close()
    ds.close()


def test_all_nan_window_reports_no_maximum() -> None:
    ds = make_synthetic(n_time=4, n_lat=1, n_lon=1)
    ds["precipitation"][:] = np.nan
    ds = precipitation_rate_to_depth(ds, interval_hours=0.5)
    out = add_rolling_accumulations(
        ds, windows={"rain_1h_mm": 2}, interval_hours=0.5
    )
    info = find_wettest_window(out, "rain_1h_mm", interval_hours=0.5)
    assert info["max_mm"] is None
    out.close()
    ds.close()


def test_rolling_rejects_window_longer_than_series() -> None:
    ds = make_synthetic(n_time=4, n_lat=1, n_lon=1)
    with pytest.raises(ValueError, match="only 4"):
        add_rolling_accumulations(ds, windows={"rain_24h_mm": 48})
    ds.close()


def test_rolling_requires_depth_variable() -> None:
    ds = make_synthetic(n_time=4, n_lat=1, n_lon=1)
    stripped = ds.drop_vars("precipitation_depth_mm")
    with pytest.raises(KeyError, match="precipitation_depth_mm"):
        add_rolling_accumulations(stripped)
    stripped.close()
    ds.close()


def test_no_network_during_rolling_processing(monkeypatch) -> None:
    """Rolling + wettest extraction must be entirely offline."""
    import socket

    def deny(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("network access attempted during pytest")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny, raising=False)

    ds = make_synthetic(n_time=50, n_lat=2, n_lon=2)
    out = add_rolling_accumulations(ds, interval_hours=0.5)
    info = find_wettest_window(out, "rain_24h_mm", interval_hours=0.5)
    assert info["max_mm"] == pytest.approx(48.0)
    out.close()
    ds.close()


# ---------------------------------------------------------------------------
# Phase 4 — generic, product-aware IMERG pipeline
# ---------------------------------------------------------------------------

from datetime import datetime, timezone  # noqa: E402

from ingestion.imerg import (  # noqa: E402
    DEFAULT_MAX_GRANULES,
    IMERG_PRODUCTS,
    IMERGProductError,
    expected_granule_count,
    expected_granule_timestamps,
    existing_granules,
    get_imerg_product,
    granule_timestamp_from_name,
    missing_granule_timestamps,
    process_imerg_window,
    wettest_windows,
)

GRANULE_NAME = (
    "270558580_GPM_3IMERGHH.07_3B-HHR.MS.MRG.3IMERG."
    "20161027-S030000-E032959.0180.V07B_Grid_precipitation_subsetted.nc4"
)


def test_final_product_registry() -> None:
    final = get_imerg_product("final")
    assert final["short_name"] == "GPM_3IMERGHH"
    assert final["collection_id"] == "C2723754847-GES_DISC"
    assert final["run_type"] == "final"
    assert final["preliminary"] is False
    assert final["suitable_for_training"] is True
    assert final["capabilities_verified"] is True


def test_early_product_registry_after_metadata_resolution() -> None:
    early = get_imerg_product("early")
    assert early["short_name"] == "GPM_3IMERGHHE"
    assert early["collection_id"] == "C2723758340-GES_DISC"
    assert early["run_type"] == "early"
    assert early["preliminary"] is True
    assert early["calibrated_final_product"] is False
    assert early["suitable_for_training"] is False
    assert early["capabilities_verified"] is True


def test_products_are_separate() -> None:
    final, early = get_imerg_product("final"), get_imerg_product("early")
    assert final["collection_id"] != early["collection_id"]
    assert final["short_name"] != early["short_name"]
    assert final["run_type"] != early["run_type"]


def test_unknown_run_type_rejected() -> None:
    with pytest.raises(IMERGProductError, match="Unknown IMERG run_type"):
        get_imerg_product("late")


@pytest.mark.parametrize(
    ("start", "end", "count"),
    [
        ("2016-10-27T03:00:00Z", "2016-10-27T05:59:59Z", 6),
        ("2016-10-27T00:00:00Z", "2016-10-27T00:00:00Z", 1),
        ("2016-10-25T00:00:00Z", "2016-10-28T05:59:59Z", 156),
        ("2020-01-01T00:00:00Z", "2020-01-01T23:59:59Z", 48),
    ],
)
def test_expected_granule_count_arbitrary_windows(start, end, count) -> None:
    assert expected_granule_count(start, end) == count


def test_reversed_window_rejected() -> None:
    with pytest.raises(ValueError, match="precedes start_time"):
        expected_granule_count("2016-10-27T05:00:00Z", "2016-10-27T03:00:00Z")


def test_granule_timestamps_are_half_hourly() -> None:
    stamps = expected_granule_timestamps(
        "2016-10-27T03:00:00Z", "2016-10-27T05:59:59Z"
    )
    assert len(stamps) == 6
    assert stamps[0] == datetime(2016, 10, 27, 3, 0, tzinfo=timezone.utc)
    assert stamps[-1] == datetime(2016, 10, 27, 5, 30, tzinfo=timezone.utc)
    gaps = {(b - a).total_seconds() / 60 for a, b in zip(stamps, stamps[1:])}
    assert gaps == {30.0}


def test_granule_timestamp_parsed_from_filename() -> None:
    stamp = granule_timestamp_from_name(GRANULE_NAME)
    assert stamp == datetime(2016, 10, 27, 3, 0, tzinfo=timezone.utc)
    assert granule_timestamp_from_name("not-a-granule.nc") is None


def test_missing_timestamps_detected() -> None:
    paths = [Path(GRANULE_NAME)]
    missing = missing_granule_timestamps(
        paths, "2016-10-27T03:00:00Z", "2016-10-27T04:29:59Z"
    )
    assert missing == [
        "2016-10-27T03:30:00Z", "2016-10-27T04:00:00Z",
    ]


def test_existing_granules_scan(tmp_path) -> None:
    (tmp_path / GRANULE_NAME).write_bytes(b"x")
    (tmp_path / "unrelated.nc").write_bytes(b"x")
    found = existing_granules(tmp_path)
    assert list(found) == [datetime(2016, 10, 27, 3, 0, tzinfo=timezone.utc)]


def test_safety_limit_blocks_oversized_window() -> None:
    from ingestion.imerg import fetch_imerg_window

    with pytest.raises(ValueError, match="above max_granules"):
        fetch_imerg_window(
            "2016-01-01T00:00:00Z", "2016-12-31T23:59:59Z",
            bbox=TERRAIN_AOI.wsen,
            output_dir=Path("/tmp/never-used"),
            max_granules=10,
        )


def test_default_max_granules_is_sane() -> None:
    assert DEFAULT_MAX_GRANULES == 500
    assert set(IMERG_PRODUCTS) == {"final", "early"}


@pytest.fixture(scope="module")
def event_window_paths() -> list[Path]:
    directory = PROJECT_ROOT / "data" / "raw" / "imerg" / "event_smoke_3h"
    if not directory.is_dir():
        pytest.skip("event smoke granules absent")
    paths = sorted(directory.glob("*.nc*"))
    if len(paths) != 6:
        pytest.skip(f"expected 6 granules, found {len(paths)}")
    return paths


def test_process_window_rolling_and_run_type(event_window_paths) -> None:
    result = process_imerg_window(
        event_window_paths, rolling_windows_hours=(1, 3),
        run_type="final", bbox=TERRAIN_AOI.wsen,
    )
    try:
        assert result.attrs["imerg_run_type"] == "final"
        assert result.attrs["suitable_for_training"] == "true"
        assert result.attrs["preliminary"] == "false"
        assert "rain_1h_mm" in result.data_vars
        assert "rain_3h_mm" in result.data_vars
        assert "precipitation_depth_mm" in result.data_vars
        assert result["precipitation"].shape == (6, 5, 4)
        assert result.attrs["data_completeness_percent"] == pytest.approx(100.0)
        assert result.attrs["granule_count"] == 6
    finally:
        result.close()


def test_process_window_marks_early_separately(event_window_paths) -> None:
    """Same files, Early label -> unmistakably different metadata."""
    result = process_imerg_window(
        event_window_paths, rolling_windows_hours=(1,), run_type="early"
    )
    try:
        assert result.attrs["imerg_run_type"] == "early"
        assert result.attrs["preliminary"] == "true"
        assert result.attrs["suitable_for_training"] == "false"
        assert result.attrs["imerg_short_name"] == "GPM_3IMERGHHE"
        assert "Early" in result.attrs["source_product"]
    finally:
        result.close()


def test_wettest_windows_generic(event_window_paths) -> None:
    result = process_imerg_window(
        event_window_paths, rolling_windows_hours=(1, 3)
    )
    try:
        peaks = wettest_windows(result, rolling_windows_hours=(1, 3))
        assert set(peaks) == {"rain_1h_mm", "rain_3h_mm"}
        for info in peaks.values():
            assert info["max_mm"] is not None
            assert info["window_start_utc"].endswith("Z")
            assert info["window_end_utc"].endswith("Z")
    finally:
        result.close()


def test_process_window_rejects_sub_interval_window(event_window_paths) -> None:
    with pytest.raises(ValueError, match="shorter than 30 min"):
        process_imerg_window(event_window_paths, rolling_windows_hours=(0.1,))


def test_no_network_during_window_processing(event_window_paths, monkeypatch) -> None:
    import socket

    def deny(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("network access attempted during pytest")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)

    result = process_imerg_window(event_window_paths, rolling_windows_hours=(1,))
    try:
        assert result.attrs["imerg_run_type"] == "final"
    finally:
        result.close()
