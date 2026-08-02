"""Tests for the ERA5-Land ingestion module.

Real-file tests use the existing one-hour smoke-test download and skip
cleanly when it is absent. Everything else is synthetic. No CDS request is
ever submitted: ``cdsapi.Client.retrieve`` is never called, and a socket guard
proves the read/build paths are offline.
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

from ingestion.era5_land import (  # noqa: E402
    AREA,
    ERA5_LAND_DATASET,
    ERA5_SHORT_NAMES,
    ERA5_VARIABLES,
    GRID_ALIGNMENT_WARNING,
    SOURCE_PRODUCT,
    ERA5LandRequestError,
    ERA5LandValidationError,
    ACCUMULATED_VARIABLES,
    HOURLY_MM_NAMES,
    METRES_TO_MM,
    RAW_ACCUMULATION_SEMANTICS,
    build_era5_land_request,
    deaccumulate_era5_land,
    download_era5_land,
    read_era5_land,
    resolve_short_names,
    strip_request_metadata,
    validate_expected_variables,
)

ALL_SHORT_NAMES = ["swvl1", "tp", "sro", "ssro", "u10", "v10", "t2m"]
MULTIVAR_VARIABLES = [
    "volumetric_soil_water_layer_1",
    "total_precipitation",
    "surface_runoff",
    "sub_surface_runoff",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_temperature",
]
UNITS_BY_SHORT_NAME = {
    "swvl1": "m**3 m**-3",
    "tp": "m",
    "sro": "m",
    "ssro": "m",
    "u10": "m s**-1",
    "v10": "m s**-1",
    "t2m": "K",
}

SMOKE_FILE = (
    PROJECT_ROOT / "data" / "raw" / "era5_land" / "smoke_test"
    / "era5_land_soil_water_l1_20161027_0000.nc"
)

EXPECTED_SHAPE = (1, 5, 4)
EXPECTED_TIMESTAMP = np.datetime64("2016-10-27T00:00:00", "ns")
EXPECTED_UNITS = "m**3 m**-3"
EXPECTED_SEA_CELLS = 3

# ERA5-Land delivers latitude descending; these are the delivered centres.
SYNTHETIC_LAT_DESC = [29.70, 29.60, 29.50, 29.40, 29.30]
SYNTHETIC_LON = [34.80, 34.90, 35.00, 35.10]


def make_synthetic(
    values: np.ndarray | None = None,
    short_name: str = "swvl1",
    units: str = EXPECTED_UNITS,
    lat: list[float] | None = None,
) -> xr.Dataset:
    """ERA5-Land-shaped dataset with descending latitude, as delivered."""
    lat = list(SYNTHETIC_LAT_DESC if lat is None else lat)
    lon = list(SYNTHETIC_LON)
    if values is None:
        # Row value encodes its latitude so reordering errors are visible.
        values = np.array(
            [[[lat_value] * len(lon) for lat_value in lat]], dtype="float32"
        )
    values = np.asarray(values, dtype="float32")

    dataset = xr.Dataset(
        {short_name: (("valid_time", "latitude", "longitude"), values)},
        coords={
            "valid_time": np.array(
                [np.datetime64("2016-10-27T00:00:00")]
                * values.shape[0]
            )[: values.shape[0]],
            "latitude": np.array(lat, dtype="float32"),
            "longitude": np.array(lon, dtype="float32"),
        },
    )
    dataset[short_name].attrs["units"] = units
    dataset[short_name].attrs["long_name"] = "synthetic test field"
    return dataset


def write_synthetic(dataset: xr.Dataset, tmp_path: Path) -> Path:
    path = tmp_path / "synthetic_era5.nc"
    dataset.to_netcdf(path)
    return path


# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------


def test_constants_match_contract() -> None:
    assert ERA5_LAND_DATASET == "reanalysis-era5-land"
    assert AREA == [29.70, 34.80, 29.25, 35.15]
    assert ERA5_VARIABLES["soil_moisture"] == "volumetric_soil_water_layer_1"
    assert ERA5_VARIABLES["subsurface_runoff"] == "sub_surface_runoff"
    assert ERA5_SHORT_NAMES["swvl1"] == "soil_moisture"
    assert ERA5_SHORT_NAMES["ssro"] == "subsurface_runoff"
    assert set(ERA5_SHORT_NAMES.values()) <= set(ERA5_VARIABLES)


# ---------------------------------------------------------------------------
# real smoke-test file
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def smoke_path() -> Path:
    if not SMOKE_FILE.exists():
        pytest.skip(
            f"ERA5-Land smoke-test file absent: {SMOKE_FILE}. "
            "Run scripts/test_era5_land_access.py first."
        )
    return SMOKE_FILE


@pytest.fixture(scope="module")
def smoke(smoke_path: Path):
    dataset = read_era5_land(smoke_path)
    yield dataset
    dataset.close()


def test_swvl1_exists(smoke) -> None:
    assert "swvl1" in smoke.data_vars


def test_dimensions_normalised(smoke) -> None:
    assert tuple(smoke["swvl1"].dims) == ("time", "lat", "lon")


def test_shape_is_one_by_five_by_four(smoke) -> None:
    assert smoke["swvl1"].shape == EXPECTED_SHAPE


def test_latitude_becomes_ascending(smoke) -> None:
    lat = np.asarray(smoke["lat"].values, dtype="float64")
    assert np.all(np.diff(lat) > 0), f"latitude not ascending: {lat}"


def test_longitude_remains_ascending(smoke) -> None:
    lon = np.asarray(smoke["lon"].values, dtype="float64")
    assert np.all(np.diff(lon) > 0), f"longitude not ascending: {lon}"


def test_time_is_datetime64_ns(smoke) -> None:
    assert smoke["time"].dtype == np.dtype("datetime64[ns]")


def test_timestamp_preserved(smoke) -> None:
    assert np.atleast_1d(smoke["time"].values)[0] == EXPECTED_TIMESTAMP


def test_units_preserved(smoke) -> None:
    assert smoke["swvl1"].attrs["units"] == EXPECTED_UNITS


def test_sea_cells_remain_nan(smoke) -> None:
    values = np.asarray(smoke["swvl1"].values, dtype="float64")
    assert int(np.isnan(values).sum()) == EXPECTED_SEA_CELLS
    assert int(np.isfinite(values).sum()) == values.size - EXPECTED_SEA_CELLS


def test_tiny_negative_noise_clamped_in_real_file(smoke) -> None:
    values = np.asarray(smoke["swvl1"].values, dtype="float64")
    finite = values[np.isfinite(values)]
    assert finite.min() >= 0.0, "negative noise survived clamping"
    assert (finite == 0.0).any(), "expected clamped zeros in this granule"


def test_no_unrelated_science_variables(smoke) -> None:
    assert sorted(map(str, smoke.data_vars)) == ["swvl1"]


def test_metadata_attributes_added(smoke) -> None:
    assert smoke.attrs["source_product"] == SOURCE_PRODUCT
    assert smoke.attrs["canonical_timezone"] == "UTC"
    assert smoke.attrs["spatial_grid"] == (
        "ERA5-Land native 0.1 degree grid"
    )
    assert smoke.attrs["grid_alignment_warning"] == GRID_ALIGNMENT_WARNING
    assert "never" in smoke.attrs["sea_mask_policy"]


# ---------------------------------------------------------------------------
# synthetic reader behaviour
# ---------------------------------------------------------------------------


def test_descending_latitude_reordered_with_its_data(tmp_path) -> None:
    """Each row's value must follow its own latitude through the sort."""
    path = write_synthetic(make_synthetic(), tmp_path)
    dataset = read_era5_land(path)
    try:
        lat = np.asarray(dataset["lat"].values, dtype="float64")
        values = np.asarray(dataset["swvl1"].values, dtype="float64")[0]
        assert np.all(np.diff(lat) > 0)
        # Row value equals its latitude, so data stayed attached after sorting.
        for index, latitude in enumerate(lat):
            assert values[index, 0] == pytest.approx(latitude, abs=1e-3)
    finally:
        dataset.close()


def test_sea_mask_nans_preserved(tmp_path) -> None:
    values = np.zeros((1, 5, 4), dtype="float32")
    values[0, 2, 2] = np.nan
    values[0, 3, 1] = np.nan
    path = write_synthetic(make_synthetic(values=values), tmp_path)

    dataset = read_era5_land(path)
    try:
        result = np.asarray(dataset["swvl1"].values, dtype="float64")
        assert int(np.isnan(result).sum()) == 2, "NaN count changed"
    finally:
        dataset.close()


def test_tiny_negative_clamped_to_zero(tmp_path) -> None:
    values = np.zeros((1, 5, 4), dtype="float32")
    values[0, 0, 0] = -1e-21
    values[0, 1, 1] = np.nan
    path = write_synthetic(make_synthetic(values=values), tmp_path)

    dataset = read_era5_land(path)
    try:
        result = np.asarray(dataset["swvl1"].values, dtype="float64")
        finite = result[np.isfinite(result)]
        assert finite.min() == 0.0
        assert int(np.isnan(result).sum()) == 1, "NaN must survive clamping"
    finally:
        dataset.close()


def test_real_negative_soil_moisture_raises(tmp_path) -> None:
    values = np.zeros((1, 5, 4), dtype="float32")
    values[0, 0, 0] = -0.25          # far below the noise tolerance
    path = write_synthetic(make_synthetic(values=values), tmp_path)

    with pytest.raises(ERA5LandValidationError, match="cannot be physically"):
        read_era5_land(path)


def test_negative_wind_is_not_clamped(tmp_path) -> None:
    """Wind components are legitimately negative and must pass through."""
    values = np.full((1, 5, 4), -3.5, dtype="float32")
    dataset = make_synthetic(
        values=values, short_name="u10", units="m s**-1"
    )
    path = write_synthetic(dataset, tmp_path)

    result = read_era5_land(path)
    try:
        assert float(result["u10"].min()) == pytest.approx(-3.5)
        assert result["u10"].attrs["units"] == "m s**-1"
    finally:
        result.close()


def test_negative_temperature_anomaly_not_clamped(tmp_path) -> None:
    values = np.full((1, 5, 4), -12.0, dtype="float32")
    path = write_synthetic(
        make_synthetic(values=values, short_name="t2m", units="K"), tmp_path
    )
    result = read_era5_land(path)
    try:
        assert float(result["t2m"].min()) == pytest.approx(-12.0)
    finally:
        result.close()


def test_missing_file_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        read_era5_land(tmp_path / "absent.nc")


# ---------------------------------------------------------------------------
# request builder
# ---------------------------------------------------------------------------


def test_request_builder_hourly_timestamps() -> None:
    start = datetime(2016, 10, 27, 0, 0, tzinfo=timezone.utc)
    end = datetime(2016, 10, 27, 5, 0, tzinfo=timezone.utc)
    request = build_era5_land_request(["soil_moisture"], start, end)

    assert request["variable"] == ["volumetric_soil_water_layer_1"]
    assert request["year"] == ["2016"]
    assert request["month"] == ["10"]
    assert request["day"] == ["27"]
    assert request["time"] == [
        "00:00", "01:00", "02:00", "03:00", "04:00", "05:00"
    ]
    assert request["_expected_timestamp_count"] == 6
    assert request["_expected_timestamps"][0] == "2016-10-27T00:00:00Z"
    assert request["_expected_timestamps"][-1] == "2016-10-27T05:00:00Z"
    assert request["data_format"] == "netcdf"
    assert request["download_format"] == "unarchived"


def test_request_preserves_cds_area_order() -> None:
    request = build_era5_land_request(
        ["soil_moisture"],
        datetime(2016, 10, 27, tzinfo=timezone.utc),
        datetime(2016, 10, 27, tzinfo=timezone.utc),
    )
    assert request["area"] == [29.70, 34.80, 29.25, 35.15]
    north, west, south, east = request["area"]
    assert north > south and east > west


def test_single_hour_range_is_one_timestamp() -> None:
    moment = datetime(2016, 10, 27, 0, 0, tzinfo=timezone.utc)
    request = build_era5_land_request(["soil_moisture"], moment, moment)
    assert request["_expected_timestamp_count"] == 1
    assert request["time"] == ["00:00"]


def test_multi_day_range_exposes_cartesian_over_request() -> None:
    """CDS expands year x month x day x time, so partial days over-request."""
    start = datetime(2016, 10, 27, 22, 0, tzinfo=timezone.utc)
    end = datetime(2016, 10, 28, 1, 0, tzinfo=timezone.utc)
    request = build_era5_land_request(["soil_moisture"], start, end)

    assert request["_expected_timestamp_count"] == 4
    assert request["day"] == ["27", "28"]
    assert request["time"] == ["00:00", "01:00", "22:00", "23:00"]
    # 2 days x 4 hours = 8 returned for 4 wanted.
    assert request["_cartesian_timestamp_count"] == 8
    assert request["_cartesian_timestamp_count"] > \
        request["_expected_timestamp_count"]


def test_full_day_range_has_no_over_request() -> None:
    start = datetime(2016, 10, 27, 0, 0, tzinfo=timezone.utc)
    end = datetime(2016, 10, 27, 23, 0, tzinfo=timezone.utc)
    request = build_era5_land_request(["soil_moisture"], start, end)
    assert request["_expected_timestamp_count"] == 24
    assert request["_cartesian_timestamp_count"] == 24


def test_variable_names_accepted_in_three_forms() -> None:
    moment = datetime(2016, 10, 27, tzinfo=timezone.utc)
    for name in ("soil_moisture", "volumetric_soil_water_layer_1", "swvl1"):
        request = build_era5_land_request([name], moment, moment)
        assert request["variable"] == ["volumetric_soil_water_layer_1"]


def test_duplicate_variables_deduplicated() -> None:
    moment = datetime(2016, 10, 27, tzinfo=timezone.utc)
    request = build_era5_land_request(
        ["soil_moisture", "swvl1", "volumetric_soil_water_layer_1"],
        moment, moment,
    )
    assert request["variable"] == ["volumetric_soil_water_layer_1"]


def test_invalid_variable_rejected() -> None:
    moment = datetime(2016, 10, 27, tzinfo=timezone.utc)
    with pytest.raises(ERA5LandRequestError, match="Unknown ERA5-Land variable"):
        build_era5_land_request(["rainfall"], moment, moment)


def test_empty_variable_list_rejected() -> None:
    moment = datetime(2016, 10, 27, tzinfo=timezone.utc)
    with pytest.raises(ERA5LandRequestError, match="At least one variable"):
        build_era5_land_request([], moment, moment)


@pytest.mark.parametrize(
    "moment",
    [
        datetime(2016, 10, 27, 0, 30, tzinfo=timezone.utc),
        datetime(2016, 10, 27, 0, 0, 30, tzinfo=timezone.utc),
        datetime(2016, 10, 27, 0, 0, 0, 500, tzinfo=timezone.utc),
    ],
)
def test_non_hour_aligned_rejected(moment) -> None:
    with pytest.raises(ERA5LandRequestError, match="hour-aligned"):
        build_era5_land_request(["soil_moisture"], moment, moment)


def test_non_utc_timezone_rejected() -> None:
    local = datetime(
        2016, 10, 27, 3, 0, tzinfo=timezone(timedelta(hours=3))
    )
    with pytest.raises(ERA5LandRequestError, match="must be UTC"):
        build_era5_land_request(["soil_moisture"], local, local)


def test_naive_datetime_treated_as_utc() -> None:
    naive = datetime(2016, 10, 27, 0, 0)
    request = build_era5_land_request(["soil_moisture"], naive, naive)
    assert request["_expected_timestamps"] == ["2016-10-27T00:00:00Z"]


def test_reversed_range_rejected() -> None:
    start = datetime(2016, 10, 27, 5, 0, tzinfo=timezone.utc)
    end = datetime(2016, 10, 27, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ERA5LandRequestError, match="precedes start_time"):
        build_era5_land_request(["soil_moisture"], start, end)


def test_malformed_area_rejected() -> None:
    moment = datetime(2016, 10, 27, tzinfo=timezone.utc)
    with pytest.raises(ERA5LandRequestError, match="North, West, South, East"):
        build_era5_land_request(["soil_moisture"], moment, moment, area=[1, 2])
    with pytest.raises(ERA5LandRequestError, match="south of South"):
        build_era5_land_request(
            ["soil_moisture"], moment, moment,
            area=[29.25, 34.80, 29.70, 35.15],   # north/south swapped
        )


def test_metadata_stripped_before_submission() -> None:
    moment = datetime(2016, 10, 27, tzinfo=timezone.utc)
    request = build_era5_land_request(["soil_moisture"], moment, moment)
    payload = strip_request_metadata(request)
    assert not any(key.startswith("_") for key in payload)
    assert set(payload) == {
        "variable", "year", "month", "day", "time", "area",
        "data_format", "download_format",
    }


# ---------------------------------------------------------------------------
# download guard rails — retrieve() is never called
# ---------------------------------------------------------------------------


def test_download_refuses_to_overwrite(tmp_path) -> None:
    existing = tmp_path / "already_here.nc"
    existing.write_bytes(b"not empty")
    moment = datetime(2016, 10, 27, tzinfo=timezone.utc)
    request = build_era5_land_request(["soil_moisture"], moment, moment)

    with pytest.raises(FileExistsError, match="overwrite=True"):
        download_era5_land(request, existing)

    assert existing.read_bytes() == b"not empty", "file must be untouched"


def test_retrieve_is_never_called_by_build_or_read(monkeypatch, tmp_path) -> None:
    """Guard: building a request and reading a file must not hit CDS."""
    import cdsapi

    def explode(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("cdsapi.Client.retrieve was called")

    monkeypatch.setattr(cdsapi.Client, "retrieve", explode, raising=False)

    moment = datetime(2016, 10, 27, tzinfo=timezone.utc)
    build_era5_land_request(["soil_moisture"], moment, moment)
    dataset = read_era5_land(write_synthetic(make_synthetic(), tmp_path))
    dataset.close()


def test_no_network_access_during_build_and_read(monkeypatch, tmp_path) -> None:
    import socket

    def deny(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("network access attempted during pytest")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny, raising=False)

    start = datetime(2016, 10, 27, 0, 0, tzinfo=timezone.utc)
    end = datetime(2016, 10, 27, 3, 0, tzinfo=timezone.utc)
    request = build_era5_land_request(
        ["soil_moisture", "total_precipitation"], start, end
    )
    assert request["_expected_timestamp_count"] == 4

    path = write_synthetic(make_synthetic(), tmp_path)
    dataset = read_era5_land(path)
    try:
        assert tuple(dataset["swvl1"].dims) == ("time", "lat", "lon")
    finally:
        dataset.close()


# ---------------------------------------------------------------------------
# multi-variable, six-hour synthetic coverage (no downloaded file required)
# ---------------------------------------------------------------------------


def make_multivariable(
    n_time: int = 6,
    sea_cells: tuple[tuple[int, int], ...] = ((2, 2), (3, 1), (4, 0)),
    soil_noise: float = -1e-21,
) -> xr.Dataset:
    """Seven ERA5-Land variables on one grid, with a shared sea mask.

    Latitude is descending, as CDS delivers it. Every land-only variable gets
    NaN at the same water cells so mask-consistency logic can be exercised.
    """
    lat = list(SYNTHETIC_LAT_DESC)
    lon = list(SYNTHETIC_LON)
    shape = (n_time, len(lat), len(lon))
    times = np.array(
        [np.datetime64("2016-10-27T00:00:00") + np.timedelta64(i, "h")
         for i in range(n_time)]
    )

    def field(fill: float) -> np.ndarray:
        return np.full(shape, fill, dtype="float32")

    soil = field(0.01)
    soil[0, 0, 0] = soil_noise            # numerical noise, must clamp to 0
    wind_u = field(-3.5)                  # negative wind is physical
    wind_v = field(2.25)
    temperature = field(295.15)           # Kelvin
    # Cumulative-looking field: mean rises with each step.
    precipitation = np.stack(
        [np.full((len(lat), len(lon)), 0.001 * (i + 1), dtype="float32")
         for i in range(n_time)]
    )
    runoff = precipitation * 0.5
    subsurface = precipitation * 0.25

    variables = {
        "swvl1": soil, "tp": precipitation, "sro": runoff, "ssro": subsurface,
        "u10": wind_u, "v10": wind_v, "t2m": temperature,
    }
    for array in variables.values():
        for row, col in sea_cells:
            array[:, row, col] = np.nan

    dataset = xr.Dataset(
        {
            name: (("valid_time", "latitude", "longitude"), values)
            for name, values in variables.items()
        },
        coords={
            "valid_time": times,
            "latitude": np.array(lat, dtype="float32"),
            "longitude": np.array(lon, dtype="float32"),
        },
    )
    for name in variables:
        dataset[name].attrs["units"] = UNITS_BY_SHORT_NAME[name]
    return dataset


@pytest.fixture
def multivariable(tmp_path):
    path = write_synthetic(make_multivariable(), tmp_path)
    dataset = read_era5_land(path)
    yield dataset
    dataset.close()


def test_multiple_variables_read_together(multivariable) -> None:
    assert sorted(map(str, multivariable.data_vars)) == sorted(ALL_SHORT_NAMES)
    for short in ALL_SHORT_NAMES:
        assert tuple(multivariable[short].dims) == ("time", "lat", "lon")
        assert multivariable[short].shape == (6, 5, 4)


def test_variable_specific_units_preserved(multivariable) -> None:
    for short, units in UNITS_BY_SHORT_NAME.items():
        assert multivariable[short].attrs["units"] == units, short


def test_negative_wind_preserved_in_multivariable(multivariable) -> None:
    u10 = np.asarray(multivariable["u10"].values, dtype="float64")
    v10 = np.asarray(multivariable["v10"].values, dtype="float64")
    assert np.nanmin(u10) == pytest.approx(-3.5)
    assert np.nanmin(v10) == pytest.approx(2.25)


def test_kelvin_temperature_preserved(multivariable) -> None:
    t2m = np.asarray(multivariable["t2m"].values, dtype="float64")
    assert multivariable["t2m"].attrs["units"] == "K"
    assert np.nanmin(t2m) == pytest.approx(295.15)
    assert np.nanmin(t2m) > 100, "looks converted to Celsius"


def test_only_soil_moisture_is_clamped(multivariable) -> None:
    soil = np.asarray(multivariable["swvl1"].values, dtype="float64")
    assert np.nanmin(soil) >= 0.0, "soil noise not clamped"
    # Wind stayed negative, proving the clamp is not applied globally.
    assert np.nanmin(
        np.asarray(multivariable["u10"].values, dtype="float64")
    ) < 0


def test_six_timestamps_unique_sorted_hourly(multivariable) -> None:
    times = np.atleast_1d(multivariable["time"].values)
    assert len(times) == 6
    assert len(set(times.tolist())) == 6
    assert all(b > a for a, b in zip(times, times[1:]))
    gaps = np.diff(times).astype("timedelta64[m]").astype(int)
    assert set(gaps.tolist()) == {60}


def test_sea_mask_shared_across_land_only_variables(multivariable) -> None:
    reference = np.isnan(
        np.asarray(multivariable["swvl1"].values, dtype="float64")
    ).any(axis=0)
    assert int(reference.sum()) == 3
    for short in ALL_SHORT_NAMES:
        mask = np.isnan(
            np.asarray(multivariable[short].values, dtype="float64")
        ).any(axis=0)
        assert np.array_equal(mask, reference), f"{short} mask differs"


def test_sea_cells_not_filled(multivariable) -> None:
    for short in ALL_SHORT_NAMES:
        values = np.asarray(multivariable[short].values, dtype="float64")
        assert int(np.isnan(values).sum()) == 3 * 6, short


def test_variable_mapping_matches_contract(multivariable) -> None:
    mapping = resolve_short_names(multivariable)
    assert mapping == {
        "swvl1": "soil_moisture",
        "tp": "total_precipitation",
        "sro": "surface_runoff",
        "ssro": "subsurface_runoff",
        "u10": "u10",
        "v10": "v10",
        "t2m": "temperature_2m",
    }


def test_missing_expected_variable_raises(tmp_path) -> None:
    dataset = make_multivariable().drop_vars("t2m")
    path = write_synthetic(dataset, tmp_path)
    loaded = read_era5_land(path)
    try:
        with pytest.raises(ERA5LandValidationError, match="missing"):
            validate_expected_variables(loaded, ALL_SHORT_NAMES)
    finally:
        loaded.close()


def test_unexpected_science_variable_reported_not_renamed(tmp_path) -> None:
    dataset = make_multivariable()
    dataset["zzz_unknown"] = dataset["t2m"].copy()
    path = write_synthetic(dataset, tmp_path)
    loaded = read_era5_land(path)
    try:
        report = validate_expected_variables(loaded, ALL_SHORT_NAMES)
        assert report["unexpected"] == ["zzz_unknown"]
        assert report["unmapped"] == ["zzz_unknown"]
        # Reported, never renamed away.
        assert "zzz_unknown" in loaded.data_vars
    finally:
        loaded.close()


def test_seven_variable_request_counts_are_six() -> None:
    """The smoke-test window must not trigger the Cartesian over-request."""
    request = build_era5_land_request(
        MULTIVAR_VARIABLES,
        datetime(2016, 10, 27, 0, 0, tzinfo=timezone.utc),
        datetime(2016, 10, 27, 5, 0, tzinfo=timezone.utc),
    )
    assert len(request["variable"]) == 7
    assert request["_expected_timestamp_count"] == 6
    assert request["_cartesian_timestamp_count"] == 6
    assert request["area"] == [29.70, 34.80, 29.25, 35.15]


def test_cross_day_window_would_fail_the_precheck() -> None:
    """A window crossing midnight over-requests, so the guard must catch it."""
    request = build_era5_land_request(
        MULTIVAR_VARIABLES,
        datetime(2016, 10, 27, 22, 0, tzinfo=timezone.utc),
        datetime(2016, 10, 28, 3, 0, tzinfo=timezone.utc),
    )
    assert request["_expected_timestamp_count"] == 6
    assert request["_cartesian_timestamp_count"] != 6
    # This inequality is exactly what the script aborts on before submitting.
    assert request["_cartesian_timestamp_count"] == 12


def test_no_network_during_multivariable_validation(monkeypatch, tmp_path) -> None:
    import socket

    def deny(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("network access attempted during pytest")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny, raising=False)

    path = write_synthetic(make_multivariable(), tmp_path)
    dataset = read_era5_land(path)
    try:
        report = validate_expected_variables(dataset, ALL_SHORT_NAMES)
        assert report["missing"] == []
        assert report["unexpected"] == []
        assert dataset["swvl1"].shape == (6, 5, 4)
    finally:
        dataset.close()


# ---------------------------------------------------------------------------
# Deaccumulation — synthetic only, no downloaded data required
# ---------------------------------------------------------------------------


def make_accumulated(
    hourly_mm_by_day: dict[str, list[float]],
    start: str = "2016-10-26T00:00:00",
    first_value_mm: float = 5.0,
    n_lat: int = 2,
    n_lon: int = 2,
    sea_cells: tuple[tuple[int, int], ...] = ((0, 0),),
    variables: tuple[str, ...] = ACCUMULATED_VARIABLES,
    include_soil: bool = True,
) -> xr.Dataset:
    """Build a raw ERA5-Land accumulated series with known hourly truth.

    `hourly_mm_by_day` maps a ``YYYY-MM-DD`` key to 24 hourly totals in mm,
    covering 01:00 that day through 00:00 the next. The series starts at
    `start` (a 00:00 stamp carrying `first_value_mm` as the previous day's
    total) and runs to the final 00:00.
    """
    days = sorted(hourly_mm_by_day)
    times = [np.datetime64(start)]
    cumulative_mm = [first_value_mm]

    for day in days:
        hours = hourly_mm_by_day[day]
        assert len(hours) == 24, f"{day} needs 24 hourly values"
        running = 0.0
        for offset, value in enumerate(hours, start=1):
            running += value
            times.append(np.datetime64(f"{day}T00:00:00") +
                         np.timedelta64(offset, "h"))
            cumulative_mm.append(running)

    stamps = np.array(times, dtype="datetime64[ns]")
    metres = np.array(cumulative_mm, dtype="float64") / METRES_TO_MM
    field = np.broadcast_to(
        metres[:, None, None], (metres.size, n_lat, n_lon)
    ).astype("float64").copy()
    for row, col in sea_cells:
        field[:, row, col] = np.nan

    data = {name: (("time", "lat", "lon"), field.copy()) for name in variables}
    if include_soil:
        soil = np.full((metres.size, n_lat, n_lon), 0.02)
        for row, col in sea_cells:
            soil[:, row, col] = np.nan
        data["swvl1"] = (("time", "lat", "lon"), soil)

    dataset = xr.Dataset(
        data,
        coords={
            "time": stamps,
            "lat": np.linspace(29.3, 29.7, n_lat),
            "lon": np.linspace(34.8, 35.1, n_lon),
        },
    )
    for name in variables:
        dataset[name].attrs["units"] = "m"
    if include_soil:
        dataset["swvl1"].attrs["units"] = "m**3 m**-3"
    return dataset


ONE_DAY = {"2016-10-26": [0.4, 0.7] + [0.0] * 21 + [1.5]}
TWO_DAYS = {
    "2016-10-26": [0.4, 0.7] + [0.0] * 21 + [1.5],
    "2016-10-27": [2.0, 0.0, 3.5] + [0.0] * 20 + [0.25],
}


def hourly_mm(dataset: xr.Dataset, short: str = "tp") -> np.ndarray:
    """Land-cell hourly series in mm (first land column)."""
    values = np.asarray(
        dataset[HOURLY_MM_NAMES[short]].values, dtype="float64"
    )
    return values[:, -1, -1]


def test_ordinary_cumulative_differencing() -> None:
    result = deaccumulate_era5_land(make_accumulated(ONE_DAY))
    series = hourly_mm(result)
    # 02:00 = 1.1 - 0.4 = 0.7 mm
    assert series[2] == pytest.approx(0.7, rel=1e-9)


def test_zero_one_hundred_reset_uses_raw_value() -> None:
    """01:00 is the daily reset: its increment IS the raw 01:00 value."""
    result = deaccumulate_era5_land(make_accumulated(ONE_DAY))
    series = hourly_mm(result)
    assert series[1] == pytest.approx(0.4, rel=1e-9)
    # The catastrophic bug would be 0.4 - 5.0 = -4.6.
    assert series[1] > 0


def test_midnight_uses_previous_day_final_hour() -> None:
    """00:00 = 24 h total minus the previous day's 23:00 cumulative."""
    result = deaccumulate_era5_land(make_accumulated(ONE_DAY))
    series = hourly_mm(result)
    assert series[24] == pytest.approx(1.5, rel=1e-9)


def test_first_midnight_without_predecessor_is_nan() -> None:
    result = deaccumulate_era5_land(make_accumulated(ONE_DAY))
    series = hourly_mm(result)
    assert np.isnan(series[0]), "unknown increment must be NaN, never zero"


def test_two_complete_utc_days() -> None:
    result = deaccumulate_era5_land(make_accumulated(TWO_DAYS))
    times = pd.DatetimeIndex(np.atleast_1d(result["time"].values))
    assert times.size == 49
    series = hourly_mm(result)
    assert np.isnan(series[0])
    assert np.all(np.isfinite(series[1:]))
    # Day two resets at 2016-10-27T01:00 (index 25).
    assert series[25] == pytest.approx(2.0, rel=1e-9)
    assert series[27] == pytest.approx(3.5, rel=1e-9)


@pytest.mark.parametrize("short", ACCUMULATED_VARIABLES)
def test_daily_sum_equals_next_midnight_total(short) -> None:
    """Sum of a day's increments must equal the next 00:00 raw total."""
    result = deaccumulate_era5_land(make_accumulated(TWO_DAYS))
    times = pd.DatetimeIndex(np.atleast_1d(result["time"].values))
    raw = np.asarray(result[short].values, dtype="float64")[:, -1, -1]
    hourly = np.asarray(
        result[f"{short}_hourly_m"].values, dtype="float64"
    )[:, -1, -1]

    for day_end in ("2016-10-27T00:00:00", "2016-10-28T00:00:00"):
        end = np.datetime64(day_end)
        start = end - np.timedelta64(23, "h")
        window = (times >= start) & (times <= end)
        assert int(window.sum()) == 24
        total = float(np.nansum(hourly[window]))
        expected = float(raw[times == end][0])
        assert total == pytest.approx(expected, abs=1e-12), short


def test_metre_to_millimetre_conversion() -> None:
    result = deaccumulate_era5_land(make_accumulated(TWO_DAYS))
    for short, mm_name in HOURLY_MM_NAMES.items():
        metres = np.asarray(result[f"{short}_hourly_m"].values, dtype="float64")
        millimetres = np.asarray(result[mm_name].values, dtype="float64")
        np.testing.assert_allclose(
            millimetres, metres * 1000.0, rtol=1e-12, equal_nan=True
        )
        assert result[mm_name].attrs["units"] == "mm"
        assert result[f"{short}_hourly_m"].attrs["units"] == "m"


def test_raw_accumulated_variables_unchanged() -> None:
    source = make_accumulated(TWO_DAYS)
    before = {
        short: np.asarray(source[short].values, dtype="float64").copy()
        for short in ACCUMULATED_VARIABLES
    }
    result = deaccumulate_era5_land(source)
    for short, original in before.items():
        np.testing.assert_array_equal(
            np.asarray(result[short].values, dtype="float64"), original
        )
        assert result[short].attrs["units"] == "m"


def test_soil_moisture_untouched() -> None:
    source = make_accumulated(TWO_DAYS)
    before = np.asarray(source["swvl1"].values, dtype="float64").copy()
    result = deaccumulate_era5_land(source)

    np.testing.assert_array_equal(
        np.asarray(result["swvl1"].values, dtype="float64"), before
    )
    assert "swvl1_hourly_m" not in result.data_vars
    assert "swvl1_hourly_mm" not in result.data_vars


def test_deaccumulating_instantaneous_variable_raises() -> None:
    source = make_accumulated(ONE_DAY)
    with pytest.raises(ERA5LandValidationError, match="instantaneous"):
        deaccumulate_era5_land(source, accumulated_variables=("swvl1",))


def test_sea_mask_nans_survive_deaccumulation() -> None:
    result = deaccumulate_era5_land(make_accumulated(TWO_DAYS))
    for short in ACCUMULATED_VARIABLES:
        hourly = np.asarray(
            result[f"{short}_hourly_m"].values, dtype="float64"
        )
        assert np.all(np.isnan(hourly[:, 0, 0])), "sea cell was filled"


def test_tiny_negative_increment_clamped() -> None:
    source = make_accumulated(ONE_DAY)
    # Nudge one cumulative value down by float noise.
    source["tp"][3, -1, -1] = float(source["tp"][3, -1, -1]) - 1e-13
    result = deaccumulate_era5_land(source)

    hourly = np.asarray(result["tp_hourly_m"].values, dtype="float64")
    finite = hourly[np.isfinite(hourly)]
    assert finite.min() >= 0.0
    assert result["tp_hourly_m"].attrs["negative_noise_clamped_count"] >= 1


def test_material_negative_increment_raises() -> None:
    source = make_accumulated(ONE_DAY)
    source["tp"][5, -1, -1] = 0.0      # a real drop mid-day
    with pytest.raises(ERA5LandValidationError, match="below the"):
        deaccumulate_era5_land(source)


def test_duplicate_timestamps_raise() -> None:
    source = make_accumulated(ONE_DAY)
    times = np.array(source["time"].values, copy=True)
    times[3] = times[2]
    source = source.assign_coords(time=times)
    with pytest.raises(ERA5LandValidationError, match="Duplicate timestamps"):
        deaccumulate_era5_land(source)


def test_missing_hourly_interval_raises() -> None:
    source = make_accumulated(ONE_DAY)
    kept = list(range(source["time"].size))
    kept.remove(4)                     # punch a hole in the hourly axis
    with pytest.raises(ERA5LandValidationError, match="Non-hourly gap"):
        deaccumulate_era5_land(source.isel(time=kept))


def test_unsorted_timestamps_raise() -> None:
    source = make_accumulated(ONE_DAY)
    order = list(range(source["time"].size))
    order[1], order[2] = order[2], order[1]
    with pytest.raises(ERA5LandValidationError, match="not ascending"):
        deaccumulate_era5_land(source.isel(time=order))


def test_deaccumulation_metadata() -> None:
    result = deaccumulate_era5_land(make_accumulated(TWO_DAYS))
    assert result.attrs["raw_accumulation_semantics"] == \
        RAW_ACCUMULATION_SEMANTICS

    for short in ACCUMULATED_VARIABLES:
        for name in (f"{short}_hourly_m", HOURLY_MM_NAMES[short]):
            attrs = result[name].attrs
            assert attrs["accumulation_processing"] == \
                "ERA5-Land forecast deaccumulation"
            assert attrs["interval_hours"] == 1
            assert attrs["interval_label"] == "interval_end"
            assert attrs["canonical_timezone"] == "UTC"
            assert attrs["missing_data_policy"] == "preserve_nan"
            assert attrs["negative_noise_tolerance_m"] == pytest.approx(1e-10)


def test_no_network_during_deaccumulation(monkeypatch) -> None:
    import socket

    def deny(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("network access attempted during pytest")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny, raising=False)

    result = deaccumulate_era5_land(make_accumulated(TWO_DAYS))
    series = hourly_mm(result)
    assert series[1] == pytest.approx(0.4, rel=1e-9)
    assert np.isnan(series[0])


# ---------------------------------------------------------------------------
# Phase 1 — metadata-driven temporal semantics
# ---------------------------------------------------------------------------

from ingestion.era5_land import (  # noqa: E402
    FLUX_HOURLY_M_NAMES,
    ERA5LandTemporalSemanticsError,
    infer_temporal_semantics,
    normalize_era5_land_fluxes,
)


def tag_step_type(dataset: xr.Dataset, step_type: str,
                  data_type: str = "fc") -> xr.Dataset:
    """Attach GRIB step metadata to the flux variables."""
    out = dataset.copy()
    for short in ACCUMULATED_VARIABLES:
        if short in out.data_vars:
            out[short].attrs["GRIB_stepType"] = step_type
            out[short].attrs["GRIB_dataType"] = data_type
    return out


def make_hourly_source(values_mm: list[float]) -> xr.Dataset:
    """A dataset whose flux values are already per-hour totals."""
    n = len(values_mm)
    times = np.array(
        [np.datetime64("2016-10-26T01:00:00") + np.timedelta64(i, "h")
         for i in range(n)]
    )
    metres = np.array(values_mm, dtype="float64") / METRES_TO_MM
    field = np.broadcast_to(metres[:, None, None], (n, 2, 2)).copy()
    field[:, 0, 0] = np.nan                    # sea cell
    data = {s: (("time", "lat", "lon"), field.copy())
            for s in ACCUMULATED_VARIABLES}
    ds = xr.Dataset(data, coords={
        "time": times,
        "lat": np.array([29.3, 29.4]),
        "lon": np.array([34.8, 34.9]),
    })
    for s in ACCUMULATED_VARIABLES:
        ds[s].attrs["units"] = "m"
    return ds


def test_infer_semantics_from_accum_step_type() -> None:
    ds = tag_step_type(make_accumulated(TWO_DAYS), "accum")
    mode, evidence = infer_temporal_semantics(ds, ACCUMULATED_VARIABLES)
    assert mode == "cumulative"
    assert "accum" in evidence


def test_infer_semantics_rejects_instant_flux() -> None:
    ds = tag_step_type(make_accumulated(ONE_DAY), "instant", data_type="an")
    with pytest.raises(ERA5LandTemporalSemanticsError, match="instantaneous"):
        infer_temporal_semantics(ds, ACCUMULATED_VARIABLES)


def test_auto_mode_raises_without_metadata() -> None:
    """No GRIB_stepType -> refuse to guess, even though values look cumulative."""
    ds = make_accumulated(TWO_DAYS)
    with pytest.raises(ERA5LandTemporalSemanticsError, match="GRIB_stepType"):
        normalize_era5_land_fluxes(ds, mode="auto")


def test_auto_mode_never_uses_value_behaviour() -> None:
    """A monotonic series without metadata must still raise."""
    ds = make_hourly_source([1.0, 2.0, 3.0, 4.0])   # rising, looks cumulative
    with pytest.raises(ERA5LandTemporalSemanticsError):
        normalize_era5_land_fluxes(ds, mode="auto")


def test_auto_mode_proven_cumulative_normalises() -> None:
    ds = tag_step_type(make_accumulated(TWO_DAYS), "accum")
    out = normalize_era5_land_fluxes(ds, mode="auto")
    assert out.attrs["temporal_semantics_mode"] == "cumulative"
    series = np.asarray(
        out["total_precipitation_hourly_mm"].values, dtype="float64"
    )[:, -1, -1]
    assert np.isnan(series[0])
    assert series[1] == pytest.approx(0.4, rel=1e-9)   # reset hour
    assert series[2] == pytest.approx(0.7, rel=1e-9)   # differenced


def test_hourly_mode_leaves_values_unchanged() -> None:
    ds = make_hourly_source([0.5, 1.5, 2.5])
    out = normalize_era5_land_fluxes(ds, mode="hourly")
    assert out.attrs["temporal_semantics_mode"] == "hourly"
    mm = np.asarray(
        out["total_precipitation_hourly_mm"].values, dtype="float64"
    )[:, -1, -1]
    np.testing.assert_allclose(mm, [0.5, 1.5, 2.5], rtol=1e-9)


def test_hourly_mode_declares_evidence() -> None:
    ds = make_hourly_source([1.0, 1.0])
    out = normalize_era5_land_fluxes(ds, mode="hourly")
    assert "caller-specified" in out.attrs["temporal_semantics_evidence"]


def test_previous_normalisation_marker_is_honoured() -> None:
    ds = make_hourly_source([1.0, 2.0])
    ds.attrs["temporal_semantics_mode"] = "hourly"
    mode, evidence = infer_temporal_semantics(ds, ACCUMULATED_VARIABLES)
    assert mode == "hourly"
    assert "previous normalisation" in evidence


def test_canonical_names_and_units() -> None:
    ds = tag_step_type(make_accumulated(TWO_DAYS), "accum")
    out = normalize_era5_land_fluxes(ds, mode="auto")
    for short, metre_name in FLUX_HOURLY_M_NAMES.items():
        assert metre_name in out.data_vars
        assert out[metre_name].attrs["units"] == "m"
        mm_name = HOURLY_MM_NAMES[short]
        assert out[mm_name].attrs["units"] == "mm"
        np.testing.assert_allclose(
            np.asarray(out[mm_name].values, dtype="float64"),
            np.asarray(out[metre_name].values, dtype="float64") * 1000.0,
            rtol=1e-12, equal_nan=True,
        )


def test_normalise_preserves_raw_and_soil_moisture() -> None:
    ds = tag_step_type(make_accumulated(TWO_DAYS), "accum")
    before_tp = np.asarray(ds["tp"].values, dtype="float64").copy()
    before_soil = np.asarray(ds["swvl1"].values, dtype="float64").copy()
    out = normalize_era5_land_fluxes(ds, mode="auto")

    np.testing.assert_array_equal(
        np.asarray(out["tp"].values, dtype="float64"), before_tp)
    np.testing.assert_array_equal(
        np.asarray(out["swvl1"].values, dtype="float64"), before_soil)
    assert "swvl1_hourly_m" not in out.data_vars


def test_normalise_preserves_sea_mask() -> None:
    ds = tag_step_type(make_accumulated(TWO_DAYS), "accum")
    out = normalize_era5_land_fluxes(ds, mode="auto")
    hourly = np.asarray(
        out["total_precipitation_hourly_m"].values, dtype="float64"
    )
    assert np.all(np.isnan(hourly[:, 0, 0]))


def test_hourly_mode_clamps_tiny_negative() -> None:
    ds = make_hourly_source([1.0, 1.0])
    ds["tp"][0, -1, -1] = -1e-13
    out = normalize_era5_land_fluxes(ds, mode="hourly")
    values = np.asarray(out["total_precipitation_hourly_m"].values,
                        dtype="float64")
    assert np.nanmin(values) >= 0.0


def test_hourly_mode_raises_on_material_negative() -> None:
    ds = make_hourly_source([1.0, 1.0])
    ds["tp"][0, -1, -1] = -0.5
    with pytest.raises(ERA5LandValidationError, match="below the noise"):
        normalize_era5_land_fluxes(ds, mode="hourly")


def test_wind_and_temperature_untouched_by_normalisation() -> None:
    ds = tag_step_type(make_accumulated(ONE_DAY), "accum")
    shape = ds["tp"].shape
    ds["u10"] = (("time", "lat", "lon"), np.full(shape, -4.0))
    ds["t2m"] = (("time", "lat", "lon"), np.full(shape, 290.0))
    ds["u10"].attrs["units"] = "m s**-1"
    ds["t2m"].attrs["units"] = "K"

    out = normalize_era5_land_fluxes(ds, mode="auto")
    assert float(np.nanmin(out["u10"].values)) == pytest.approx(-4.0)
    assert float(np.nanmin(out["t2m"].values)) == pytest.approx(290.0)
    assert out["u10"].attrs["units"] == "m s**-1"
    assert "u10_hourly_m" not in out.data_vars


def test_unknown_mode_rejected() -> None:
    ds = make_hourly_source([1.0])
    with pytest.raises(ERA5LandTemporalSemanticsError, match="Unknown mode"):
        normalize_era5_land_fluxes(ds, mode="weekly")


def test_no_network_during_normalisation(monkeypatch) -> None:
    import socket

    def deny(*a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    ds = tag_step_type(make_accumulated(TWO_DAYS), "accum")
    out = normalize_era5_land_fluxes(ds, mode="auto")
    assert out.attrs["temporal_semantics_mode"] == "cumulative"


def test_real_file_metadata_proves_cumulative() -> None:
    """The actual CDS download must carry the proving metadata."""
    path = (PROJECT_ROOT / "data/raw/era5_land/deaccumulation_validation"
            / "era5_land_accum_20161026.nc")
    if not path.exists():
        pytest.skip("deaccumulation validation file absent")
    ds = read_era5_land(path)
    try:
        mode, evidence = infer_temporal_semantics(ds, ACCUMULATED_VARIABLES)
        assert mode == "cumulative"
        assert "accum" in evidence
        assert ds["swvl1"].attrs.get("GRIB_stepType") == "instant"
    finally:
        ds.close()
