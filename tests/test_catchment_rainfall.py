"""Synthetic tests for catchment rainfall aggregation.

Everything here is built in memory from synthetic geometries and synthetic
rainfall. No project data file is read, no GeoPackage is written, and no
network access occurs. These tests must pass before real catchments exist.
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from shapely.geometry import Polygon, box

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from processing.catchment_rainfall import (  # noqa: E402
    AREA_CRS,
    FLAG_GOOD,
    FLAG_MISSING_DATA,
    FLAG_PARTIAL_COVERAGE,
    FLAG_PROVISIONAL_GEOMETRY,
    PROVISIONAL,
    REAL,
    STORAGE_CRS,
    CatchmentSource,
    CatchmentValidationError,
    MissingCatchmentsError,
    aggregate_catchment_rainfall,
    build_grid_cells,
    build_summary,
    classify_quality,
    compare_with_grid_peak,
    compute_overlaps,
    coverage_by_catchment,
    resolve_catchment_source,
    validate_catchments,
    wettest_windows_per_catchment,
)

# A 2x2 synthetic grid on a clean 0.1-degree lattice near Aqaba.
LAT_CENTERS = [29.25, 29.35]
LON_CENTERS = [34.85, 34.95]
CELL = 0.1
EVENT_ID = "AQ-TEST-01"


def make_grid_dataset(
    values: np.ndarray | None = None,
    n_time: int = 4,
    rolling: bool = True,
) -> xr.Dataset:
    """Synthetic IMERG-shaped dataset with real lat_bnds/lon_bnds.

    `values` may be (time, lat, lon); when omitted each cell gets a distinct
    constant rate so weighting errors are impossible to miss.
    """
    lat = np.array(LAT_CENTERS, dtype="float64")
    lon = np.array(LON_CENTERS, dtype="float64")

    if values is None:
        base = np.array([[1.0, 2.0], [3.0, 4.0]], dtype="float64")
        values = np.repeat(base[None, :, :], n_time, axis=0)
    values = np.asarray(values, dtype="float64")
    n_time = values.shape[0]

    times = np.array(
        [np.datetime64("2016-10-27T00:00:00") + np.timedelta64(30 * i, "m")
         for i in range(n_time)]
    )
    lat_bnds = np.column_stack([lat - CELL / 2, lat + CELL / 2])
    lon_bnds = np.column_stack([lon - CELL / 2, lon + CELL / 2])

    data = {
        "precipitation": (("time", "lat", "lon"), values),
        "precipitation_depth_mm": (("time", "lat", "lon"), values * 0.5),
        "lat_bnds": (("lat", "latv"), lat_bnds),
        "lon_bnds": (("lon", "lonv"), lon_bnds),
    }
    if rolling:
        for name in ("rain_1h_mm", "rain_3h_mm", "rain_6h_mm", "rain_24h_mm"):
            data[name] = (("time", "lat", "lon"), values * 0.5)

    dataset = xr.Dataset(
        data, coords={"time": times, "lat": lat, "lon": lon}
    )
    dataset["precipitation"].attrs["units"] = "mm/hr"
    return dataset


def make_catchments(
    geometries: dict[str, Polygon],
    crs: str = STORAGE_CRS,
) -> gpd.GeoDataFrame:
    frame = gpd.GeoDataFrame(
        {"catchment_id": list(geometries)},
        geometry=list(geometries.values()),
        crs=STORAGE_CRS,
    )
    return frame.to_crs(crs) if crs != STORAGE_CRS else frame


def cell_box(lat_index: int, lon_index: int) -> Polygon:
    """The exact footprint of one synthetic grid cell."""
    lat, lon = LAT_CENTERS[lat_index], LON_CENTERS[lon_index]
    return box(lon - CELL / 2, lat - CELL / 2, lon + CELL / 2, lat + CELL / 2)


def run(dataset: xr.Dataset, catchments: gpd.GeoDataFrame,
        status: str = REAL) -> tuple[pd.DataFrame, pd.DataFrame]:
    cells = build_grid_cells(dataset)
    overlaps = compute_overlaps(cells, catchments)
    frame = aggregate_catchment_rainfall(
        dataset, overlaps, event_id=EVENT_ID, geometry_status=status
    )
    return frame, overlaps


# ---------------------------------------------------------------------------
# grid-cell construction
# ---------------------------------------------------------------------------


def test_grid_cells_use_bounds_not_centres() -> None:
    dataset = make_grid_dataset()
    cells = build_grid_cells(dataset)

    assert len(cells) == 4
    assert cells.crs.to_string() == STORAGE_CRS
    assert (cells["cell_area_m2"] > 0).all()

    first = cells[(cells.lat_index == 0) & (cells.lon_index == 0)].iloc[0]
    west, south, east, north = first.geometry.bounds
    assert east - west == pytest.approx(CELL)
    assert north - south == pytest.approx(CELL)
    # A ~0.1 degree cell near 29N is roughly 11 km x 11 km.
    assert 1.0e8 < float(first.cell_area_m2) < 1.6e8


def test_grid_cells_fall_back_without_bounds() -> None:
    dataset = make_grid_dataset().drop_vars(["lat_bnds", "lon_bnds"])
    cells = build_grid_cells(dataset)
    assert len(cells) == 4
    width = cells.iloc[0].geometry.bounds[2] - cells.iloc[0].geometry.bounds[0]
    assert width == pytest.approx(CELL)


# ---------------------------------------------------------------------------
# overlap geometry
# ---------------------------------------------------------------------------


def test_exact_full_cell_overlap() -> None:
    """A catchment identical to one cell: weight 1, value = that cell."""
    dataset = make_grid_dataset()
    catchments = make_catchments({"AQ-C01": cell_box(0, 0)})
    frame, overlaps = run(dataset, catchments)

    assert len(overlaps) == 1
    row = overlaps.iloc[0]
    assert row.overlap_weight == pytest.approx(1.0, rel=1e-9)
    assert row.coverage_fraction == pytest.approx(1.0, rel=1e-9)
    assert frame["precipitation_mm_hr"].iloc[0] == pytest.approx(1.0)
    assert frame["valid_area_fraction"].iloc[0] == pytest.approx(1.0)
    assert frame["quality_flag"].iloc[0] == FLAG_GOOD


def test_catchment_overlapping_multiple_cells() -> None:
    """A catchment covering all four cells sees all four values."""
    dataset = make_grid_dataset()
    whole = box(
        LON_CENTERS[0] - CELL / 2, LAT_CENTERS[0] - CELL / 2,
        LON_CENTERS[1] + CELL / 2, LAT_CENTERS[1] + CELL / 2,
    )
    frame, overlaps = run(dataset, make_catchments({"AQ-C01": whole}))

    assert len(overlaps) == 4
    # Reprojecting a lon/lat rectangle to UTM curves its edges slightly, so the
    # union of four cell quads differs from one big quad by ~0.01 %. Real, tiny,
    # and inherent to any projected overlay — hence rel=1e-3, not 1e-9.
    assert overlaps["overlap_weight"].sum() == pytest.approx(1.0, rel=1e-3)
    assert overlaps.iloc[0].coverage_fraction == pytest.approx(1.0, rel=1e-3)
    # Cells are 1,2,3,4 with near-equal areas -> mean near 2.5.
    assert frame["precipitation_mm_hr"].iloc[0] == pytest.approx(2.5, rel=1e-3)


def test_partial_cell_overlap_is_area_weighted() -> None:
    """75 % of cell (0,0) plus 25 % of cell (0,1) -> 1*0.75 + 2*0.25 = 1.25."""
    dataset = make_grid_dataset()
    boundary = LON_CENTERS[0] + CELL / 2      # shared edge of cells 0 and 1
    catchment = box(
        boundary - 0.75 * CELL, LAT_CENTERS[0] - CELL / 2,
        boundary + 0.25 * CELL, LAT_CENTERS[0] + CELL / 2,
    )
    cells = build_grid_cells(dataset)
    catchments = make_catchments({"AQ-C01": catchment})
    overlaps = compute_overlaps(cells, catchments)
    frame = aggregate_catchment_rainfall(
        dataset, overlaps, event_id=EVENT_ID, geometry_status=REAL
    )

    weights = dict(
        zip(zip(overlaps.lat_index, overlaps.lon_index),
            overlaps.overlap_weight)
    )
    # The two intended cells dominate; the catchment shares its northern edge
    # with row 1, so reprojection leaves hairline slivers there (~1e-5).
    assert weights[(0, 0)] == pytest.approx(0.75, rel=1e-3)
    assert weights[(0, 1)] == pytest.approx(0.25, rel=1e-3)
    for key, weight in weights.items():
        if key[0] == 1:
            assert weight < 1e-4, f"sliver {key} should be negligible"

    # Exact check: the aggregate equals sum(v*A)/sum(A) using the very areas
    # the module returned — no geometric approximation involved.
    areas = dict(
        zip(zip(overlaps.lat_index, overlaps.lon_index),
            overlaps.intersection_area_m2)
    )
    values = {(0, 0): 1.0, (0, 1): 2.0, (1, 0): 3.0, (1, 1): 4.0}
    expected = (
        sum(values[k] * a for k, a in areas.items()) / sum(areas.values())
    )
    assert frame["precipitation_mm_hr"].iloc[0] == pytest.approx(expected)
    # And the geometric intent: a 75/25 split lands on 1.25 mm/hr.
    assert frame["precipitation_mm_hr"].iloc[0] == pytest.approx(1.25, rel=1e-3)


def test_min_overlap_fraction_drops_slivers_when_requested() -> None:
    """Opt-in threshold removes edge slivers; default keeps them."""
    dataset = make_grid_dataset()
    boundary = LON_CENTERS[0] + CELL / 2
    catchment = make_catchments({"AQ-C01": box(
        boundary - 0.75 * CELL, LAT_CENTERS[0] - CELL / 2,
        boundary + 0.25 * CELL, LAT_CENTERS[0] + CELL / 2,
    )})
    cells = build_grid_cells(dataset)

    kept = compute_overlaps(cells, catchment)
    filtered = compute_overlaps(cells, catchment, min_overlap_fraction=1e-3)

    assert len(kept) == 4, "default keeps geometrically real slivers"
    assert len(filtered) == 2, "threshold removes them"
    assert set(zip(filtered.lat_index, filtered.lon_index)) == {(0, 0), (0, 1)}


def test_area_weighted_mean_respects_unequal_areas() -> None:
    """A lopsided catchment must lean toward the cell it mostly covers."""
    dataset = make_grid_dataset()
    west = LON_CENTERS[0] - CELL / 2
    lopsided = box(
        west, LAT_CENTERS[0] - CELL / 2,
        west + CELL + 0.1 * CELL,   # all of cell 0, only 10 % of cell 1
        LAT_CENTERS[0] + CELL / 2,
    )
    frame, overlaps = run(dataset, make_catchments({"AQ-C01": lopsided}))

    weights = dict(
        zip(zip(overlaps.lat_index, overlaps.lon_index),
            overlaps.intersection_area_m2)
    )
    assert weights[(0, 0)] > weights[(0, 1)] * 5
    value = frame["precipitation_mm_hr"].iloc[0]
    assert 1.0 < value < 1.2, "should sit just above cell 0's value of 1.0"


# ---------------------------------------------------------------------------
# coverage and missing data
# ---------------------------------------------------------------------------


def test_incomplete_coverage_is_reported_not_normalised() -> None:
    """Half the catchment lies outside the grid: coverage ~0.5, not 1.0."""
    dataset = make_grid_dataset()
    east = LON_CENTERS[1] + CELL / 2
    straddling = box(
        east - CELL, LAT_CENTERS[1] - CELL / 2,
        east + CELL, LAT_CENTERS[1] + CELL / 2,
    )
    frame, overlaps = run(dataset, make_catchments({"AQ-C01": straddling}))

    coverage = coverage_by_catchment(overlaps)["AQ-C01"]
    assert coverage == pytest.approx(0.5, rel=0.02)
    assert coverage < 1.0, "coverage must not be normalised to 1"
    assert frame["coverage_fraction"].iloc[0] == pytest.approx(coverage)
    assert FLAG_PARTIAL_COVERAGE in frame["quality_flag"].iloc[0]
    # The value itself still uses only the cells that exist.
    assert np.isfinite(frame["precipitation_mm_hr"].iloc[0])


def test_missing_values_are_not_treated_as_zero() -> None:
    """A NaN cell must be excluded, not counted as 0 mm/hr."""
    base = np.array([[1.0, 2.0], [3.0, 4.0]])
    values = np.repeat(base[None, :, :], 2, axis=0)
    values[:, 0, 0] = np.nan          # drop the cell whose value is 1.0
    dataset = make_grid_dataset(values=values)

    whole = box(
        LON_CENTERS[0] - CELL / 2, LAT_CENTERS[0] - CELL / 2,
        LON_CENTERS[1] + CELL / 2, LAT_CENTERS[1] + CELL / 2,
    )
    frame, _ = run(dataset, make_catchments({"AQ-C01": whole}))

    value = frame["precipitation_mm_hr"].iloc[0]
    # Mean of the three valid cells (2,3,4) = 3.0.
    assert value == pytest.approx(3.0, rel=1e-3)
    # Treating NaN as zero would give (0+2+3+4)/4 = 2.25.
    assert value != pytest.approx(2.25, rel=1e-3)
    assert frame["valid_area_fraction"].iloc[0] == pytest.approx(0.75, rel=0.02)
    assert FLAG_MISSING_DATA in frame["quality_flag"].iloc[0]


def test_all_missing_gives_nan_not_zero() -> None:
    values = np.full((2, 2, 2), np.nan)
    dataset = make_grid_dataset(values=values)
    frame, _ = run(dataset, make_catchments({"AQ-C01": cell_box(0, 0)}))

    assert np.isnan(frame["precipitation_mm_hr"].iloc[0])
    assert frame["valid_area_fraction"].iloc[0] == pytest.approx(0.0)
    assert FLAG_MISSING_DATA in frame["quality_flag"].iloc[0]


# ---------------------------------------------------------------------------
# geometry validation
# ---------------------------------------------------------------------------


def test_invalid_geometry_is_repaired() -> None:
    bowtie = Polygon([(34.80, 29.20), (34.90, 29.30),
                      (34.80, 29.30), (34.90, 29.20)])
    assert not bowtie.is_valid

    frame = gpd.GeoDataFrame(
        {"catchment_id": ["AQ-C01"]}, geometry=[bowtie], crs=STORAGE_CRS
    )
    repaired = validate_catchments(frame, repair_invalid=True)
    assert repaired.geometry.is_valid.all()
    assert repaired["catchment_id"].tolist() == ["AQ-C01"]


def test_invalid_geometry_is_rejected_when_repair_disabled() -> None:
    bowtie = Polygon([(34.80, 29.20), (34.90, 29.30),
                      (34.80, 29.30), (34.90, 29.20)])
    frame = gpd.GeoDataFrame(
        {"catchment_id": ["AQ-C01"]}, geometry=[bowtie], crs=STORAGE_CRS
    )
    with pytest.raises(CatchmentValidationError, match="Invalid geometry"):
        validate_catchments(frame, repair_invalid=False)


def test_duplicate_catchment_ids_are_rejected() -> None:
    frame = gpd.GeoDataFrame(
        {"catchment_id": ["AQ-C01", "AQ-C01"]},
        geometry=[cell_box(0, 0), cell_box(0, 1)],
        crs=STORAGE_CRS,
    )
    with pytest.raises(CatchmentValidationError, match="Duplicate catchment IDs"):
        validate_catchments(frame)


def test_bad_id_format_is_rejected_without_renaming() -> None:
    frame = gpd.GeoDataFrame(
        {"basin": ["catchment_one"]}, geometry=[cell_box(0, 0)],
        crs=STORAGE_CRS,
    )
    with pytest.raises(CatchmentValidationError, match="AQ-C01"):
        validate_catchments(frame)


def test_missing_crs_is_rejected() -> None:
    frame = gpd.GeoDataFrame(
        {"catchment_id": ["AQ-C01"]}, geometry=[cell_box(0, 0)], crs=None
    )
    with pytest.raises(CatchmentValidationError, match="no CRS"):
        validate_catchments(frame)


def test_id_column_detected_from_alternative_name() -> None:
    frame = gpd.GeoDataFrame(
        {"id": ["AQ-C07"]}, geometry=[cell_box(0, 0)], crs=STORAGE_CRS
    )
    validated = validate_catchments(frame)
    assert validated["catchment_id"].tolist() == ["AQ-C07"]


# ---------------------------------------------------------------------------
# CRS handling
# ---------------------------------------------------------------------------


def test_crs_conversion_gives_identical_results() -> None:
    """Input in UTM must aggregate identically to the same input in 4326."""
    dataset = make_grid_dataset()
    geographic = make_catchments({"AQ-C01": cell_box(0, 0)})
    projected = make_catchments({"AQ-C01": cell_box(0, 0)}, crs=AREA_CRS)
    assert projected.crs.to_string() == AREA_CRS

    frame_a, overlaps_a = run(dataset, validate_catchments(geographic))
    frame_b, overlaps_b = run(dataset, validate_catchments(projected))

    assert overlaps_a.iloc[0].catchment_area_m2 == pytest.approx(
        overlaps_b.iloc[0].catchment_area_m2, rel=1e-6
    )
    assert frame_a["precipitation_mm_hr"].iloc[0] == pytest.approx(
        frame_b["precipitation_mm_hr"].iloc[0], rel=1e-9
    )


def test_areas_are_projected_not_degrees() -> None:
    """Catchment area must be in square metres, not square degrees."""
    dataset = make_grid_dataset()
    _, overlaps = run(dataset, make_catchments({"AQ-C01": cell_box(0, 0)}))
    area = float(overlaps.iloc[0].catchment_area_m2)
    assert area > 1.0e8, "a 0.1 degree cell is ~1.2e8 m2, not 0.01"


# ---------------------------------------------------------------------------
# quality flags
# ---------------------------------------------------------------------------


def test_provisional_flag_retained_despite_perfect_coverage() -> None:
    dataset = make_grid_dataset()
    frame, _ = run(
        dataset, make_catchments({"AQ-C01": cell_box(0, 0)}),
        status=PROVISIONAL,
    )
    flag = frame["quality_flag"].iloc[0]
    assert FLAG_PROVISIONAL_GEOMETRY in flag
    assert FLAG_GOOD in flag, "coverage is perfect, so GOOD must also appear"
    assert (frame["source_geometry_status"] == PROVISIONAL).all()


def test_classify_quality_combinations() -> None:
    assert classify_quality(1.0, 1.0, REAL) == FLAG_GOOD
    assert classify_quality(1.0, 1.0, PROVISIONAL) == \
        f"{FLAG_GOOD}|{FLAG_PROVISIONAL_GEOMETRY}"
    assert FLAG_PARTIAL_COVERAGE in classify_quality(1.0, 0.4, REAL)
    assert FLAG_MISSING_DATA in classify_quality(0.5, 1.0, REAL)
    assert FLAG_MISSING_DATA in classify_quality(0.0, 1.0, REAL)
    combined = classify_quality(0.5, 0.5, PROVISIONAL)
    for expected in (FLAG_MISSING_DATA, FLAG_PARTIAL_COVERAGE,
                     FLAG_PROVISIONAL_GEOMETRY):
        assert expected in combined


# ---------------------------------------------------------------------------
# wettest windows
# ---------------------------------------------------------------------------


def test_wettest_window_extraction_and_bounds() -> None:
    """Peak at index 5 of a 30-minute series -> 3 h window ends 03:00Z."""
    values = np.zeros((8, 2, 2))
    values[5, 0, 0] = 10.0
    dataset = make_grid_dataset(values=values)
    frame, _ = run(dataset, make_catchments({"AQ-C01": cell_box(0, 0)}))

    windows = wettest_windows_per_catchment(frame, interval_hours=0.5)
    info = windows["AQ-C01"]["rain_3h_mm"]

    assert info["max_mm"] == pytest.approx(5.0)          # values * 0.5
    assert info["label_timestamp_utc"] == "2016-10-27T02:30:00Z"
    assert info["end_utc"] == "2016-10-27T03:00:00Z"
    assert info["start_utc"] == "2016-10-27T00:00:00Z"
    span = (pd.Timestamp(info["end_utc"]) - pd.Timestamp(info["start_utc"]))
    assert span.total_seconds() / 3600 == pytest.approx(3.0)


def test_wettest_window_all_nan_reports_none() -> None:
    values = np.full((4, 2, 2), np.nan)
    dataset = make_grid_dataset(values=values)
    frame, _ = run(dataset, make_catchments({"AQ-C01": cell_box(0, 0)}))
    windows = wettest_windows_per_catchment(frame)
    assert windows["AQ-C01"]["rain_3h_mm"]["max_mm"] is None


def test_wettest_windows_are_per_catchment() -> None:
    values = np.zeros((6, 2, 2))
    values[1, 0, 0] = 4.0     # early peak in cell (0,0)
    values[4, 1, 1] = 8.0     # later, larger peak in cell (1,1)
    dataset = make_grid_dataset(values=values)
    catchments = make_catchments({
        "AQ-C01": cell_box(0, 0),
        "AQ-C02": cell_box(1, 1),
    })
    frame, _ = run(dataset, catchments)
    windows = wettest_windows_per_catchment(frame)

    assert windows["AQ-C01"]["rain_1h_mm"]["max_mm"] == pytest.approx(2.0)
    assert windows["AQ-C02"]["rain_1h_mm"]["max_mm"] == pytest.approx(4.0)
    assert (windows["AQ-C01"]["rain_1h_mm"]["end_utc"]
            < windows["AQ-C02"]["rain_1h_mm"]["end_utc"])


# ---------------------------------------------------------------------------
# schema, comparison, summary
# ---------------------------------------------------------------------------


def test_parquet_schema_and_utc_timestamps() -> None:
    dataset = make_grid_dataset()
    frame, _ = run(dataset, make_catchments({"AQ-C01": cell_box(0, 0)}))

    for column in (
        "event_id", "timestamp_utc", "catchment_id", "precipitation_mm_hr",
        "precipitation_depth_mm", "rain_1h_mm", "rain_3h_mm", "rain_6h_mm",
        "rain_24h_mm", "coverage_fraction", "valid_area_fraction",
        "quality_flag", "source_geometry_status",
    ):
        assert column in frame.columns, f"missing column {column}"

    assert frame["timestamp_utc"].str.endswith("Z").all()
    assert (frame["event_id"] == EVENT_ID).all()


def test_rows_ordered_by_timestamp_then_catchment() -> None:
    dataset = make_grid_dataset()
    catchments = make_catchments({
        "AQ-C02": cell_box(1, 1),
        "AQ-C01": cell_box(0, 0),
    })
    frame, _ = run(dataset, catchments)
    assert frame[["timestamp_utc", "catchment_id"]].equals(
        frame[["timestamp_utc", "catchment_id"]].sort_values(
            ["timestamp_utc", "catchment_id"], kind="stable"
        ).reset_index(drop=True)
    )


def test_comparison_reports_shift_without_causal_claim() -> None:
    values = np.zeros((6, 2, 2))
    values[4, 0, 0] = 6.0
    dataset = make_grid_dataset(values=values)
    frame, _ = run(dataset, make_catchments({"AQ-C01": cell_box(0, 0)}))
    windows = wettest_windows_per_catchment(frame)

    grid_peak = {
        "window_start_utc": "2016-10-27T00:00:00Z",
        "window_end_utc": "2016-10-27T03:00:00Z",
        "max_mm": 2.0,
    }
    comparison = compare_with_grid_peak(
        windows, grid_peak, flood_arrival_utc="2016-10-28T00:00:00Z"
    )

    assert "no causal claim" in comparison["check_type"]
    entry = comparison["catchment_level"][0]
    # Catchment peak ends 02:30Z, grid peak ends 03:00Z -> 30 minutes EARLIER,
    # so the shift is negative.
    assert entry["peak_time_shift_hours_vs_grid"] == pytest.approx(-0.5)
    assert entry["peak_rainfall_delta_mm_vs_grid"] == pytest.approx(1.0)
    assert entry["peak_ends_before_flood_arrival"] is True
    assert comparison["aggregation_changes_peak_time"] is True
    assert comparison["aggregation_changes_peak_rainfall"] is True


def test_summary_structure_warns_on_provisional() -> None:
    dataset = make_grid_dataset()
    catchments = validate_catchments(
        make_catchments({"AQ-C01": cell_box(0, 0)})
    )
    cells = build_grid_cells(dataset)
    overlaps = compute_overlaps(cells, catchments)
    frame = aggregate_catchment_rainfall(
        dataset, overlaps, event_id=EVENT_ID, geometry_status=PROVISIONAL
    )
    windows = wettest_windows_per_catchment(frame)
    comparison = compare_with_grid_peak(windows, {})

    summary = build_summary(
        EVENT_ID, CatchmentSource(Path("synthetic.gpkg"), PROVISIONAL),
        catchments, cells, overlaps, frame, windows, comparison,
    )

    assert summary["source_geometry_status"] == PROVISIONAL
    assert summary["catchment_count"] == 1
    assert summary["imerg_cell_count"] == 4
    assert summary["overlap_count"] == 1
    assert summary["storage_crs"] == STORAGE_CRS
    assert summary["area_crs"] == AREA_CRS
    assert "coverage_fraction_by_catchment" in summary
    assert any("PROVISIONAL" in w for w in summary["warnings"])
    assert summary["assumptions"], "assumptions must be recorded"


# ---------------------------------------------------------------------------
# dependency resolution
# ---------------------------------------------------------------------------


def test_missing_catchments_raises_actionable_error(tmp_path) -> None:
    with pytest.raises(MissingCatchmentsError) as excinfo:
        resolve_catchment_source(
            tmp_path / "catchments.gpkg",
            tmp_path / "catchments_PROVISIONAL.gpkg",
        )
    message = str(excinfo.value)
    assert "catchments.gpkg" in message
    assert "catchments_PROVISIONAL.gpkg" in message
    assert "P1" in message
    assert "must not be fabricated" in message


def test_real_catchments_preferred_over_provisional(tmp_path) -> None:
    real = tmp_path / "catchments.gpkg"
    provisional = tmp_path / "catchments_PROVISIONAL.gpkg"
    provisional.write_bytes(b"placeholder")
    assert resolve_catchment_source(real, provisional).status == PROVISIONAL

    real.write_bytes(b"placeholder")
    source = resolve_catchment_source(real, provisional)
    assert source.status == REAL
    assert source.path == real
    assert source.is_provisional is False


def test_empty_overlaps_rejected() -> None:
    dataset = make_grid_dataset()
    faraway = box(0.0, 0.0, 0.1, 0.1)
    cells = build_grid_cells(dataset)
    overlaps = compute_overlaps(
        cells, make_catchments({"AQ-C01": faraway})
    )
    assert overlaps.empty
    with pytest.raises(ValueError, match="No catchment/grid overlaps"):
        aggregate_catchment_rainfall(
            dataset, overlaps, event_id=EVENT_ID, geometry_status=REAL
        )


# ---------------------------------------------------------------------------
# offline guarantee
# ---------------------------------------------------------------------------


def test_no_network_access_during_aggregation(monkeypatch) -> None:
    import socket

    def deny(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("network access attempted during pytest")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket.socket, "connect", deny, raising=False)

    dataset = make_grid_dataset()
    catchments = validate_catchments(
        make_catchments({"AQ-C01": cell_box(0, 0),
                         "AQ-C02": cell_box(1, 1)})
    )
    frame, overlaps = run(dataset, catchments)
    windows = wettest_windows_per_catchment(frame)

    assert len(frame) == 2 * dataset["time"].size
    assert len(overlaps) == 2
    assert set(windows) == {"AQ-C01", "AQ-C02"}
