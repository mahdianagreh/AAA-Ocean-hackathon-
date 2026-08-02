"""The aggregation pipeline against Mahdi's REAL catchment polygons.

Until 2 August 2026 `catchment_rainfall.py` had 31 tests and had never once
run on real geometry — only synthetic fixtures. `catchment_integration_status.json`
recorded the reason honestly: the file did not exist, and no polygon was
fabricated to paper over it.

It exists now. These tests are the evidence that the pipeline actually works
on it, rather than the assumption that it would.

Skipped when the data is absent, so a fresh clone still passes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from config.spatial import TERRAIN_AOI  # noqa: E402

CATCHMENTS = PROJECT_ROOT / "data" / "processed" / "vectors" / "catchments.gpkg"
DAILY_DIR = PROJECT_ROOT / "data" / "raw" / "imerg" / "daily_final"

#: From the delineation, recorded in tasks/00-contracts.md §2.
EXPECTED_AREAS_KM2 = {
    "AQ-C01": 4453.08,
    "AQ-C02": 64.85,
    "AQ-C03": 59.90,
    "AQ-C04": 42.67,
    "AQ-C05": 35.64,
}


@pytest.fixture(scope="module")
def catchments():
    if not CATCHMENTS.exists():
        pytest.skip("real catchments.gpkg absent")
    from processing.catchment_rainfall import load_catchments

    return load_catchments(CATCHMENTS)


@pytest.fixture(scope="module")
def daily_granule() -> Path:
    if not DAILY_DIR.is_dir():
        pytest.skip("daily IMERG granules absent — run scripts/sweep_imerg_daily.py")
    found = sorted(DAILY_DIR.glob("*.nc*"))
    if not found:
        pytest.skip("daily IMERG directory is empty")
    return found[0]


def test_real_catchments_pass_validation(catchments):
    """Five catchments, contract IDs, storage CRS, no invalid geometry."""
    assert len(catchments) == 5
    assert catchments.crs.to_epsg() == 4326
    assert set(catchments["catchment_id"]) == set(EXPECTED_AREAS_KM2)
    assert catchments.geometry.is_valid.all()


def test_real_catchments_are_not_provisional(catchments):
    assert not catchments["provisional"].any()


def test_recorded_areas_match_a_projected_recomputation(catchments):
    """Areas must come from UTM 36N, never from degrees.

    A 1 % tolerance covers polygon-simplification differences between the
    delineation and this recomputation; a degrees-based area would be out by
    orders of magnitude, not one percent.
    """
    projected = catchments.to_crs(32636)
    for _, row in catchments.join(
        projected.geometry.area.rename("computed_m2")
    ).iterrows():
        recorded = EXPECTED_AREAS_KM2[row["catchment_id"]]
        computed = row["computed_m2"] / 1e6
        assert computed == pytest.approx(recorded, rel=0.01), (
            f"{row['catchment_id']}: recorded {recorded} km², "
            f"recomputed {computed:.2f} km²"
        )


def test_catchments_lie_inside_the_terrain_aoi(catchments):
    """If they do not, the rainfall sweep is not covering the catchments."""
    west, south, east, north = catchments.total_bounds
    assert west >= TERRAIN_AOI.west and south >= TERRAIN_AOI.south
    assert east <= TERRAIN_AOI.east and north <= TERRAIN_AOI.north


def test_grid_cells_are_a_regular_tenth_degree(daily_granule):
    """Daily granules carry no lat_bnds/lon_bnds, so footprints are derived
    from centre spacing. This asserts that fallback is exact rather than
    approximately right — an area-weighted mean depends on it."""
    from ingestion.imerg import read_imerg_subset
    from processing.catchment_rainfall import build_grid_cells

    cells = build_grid_cells(read_imerg_subset(daily_granule))
    bounds = cells.geometry.bounds
    widths = bounds.maxx - bounds.minx
    heights = bounds.maxy - bounds.miny
    assert widths.min() == pytest.approx(0.1, abs=1e-6)
    assert widths.max() == pytest.approx(0.1, abs=1e-6)
    assert heights.min() == pytest.approx(0.1, abs=1e-6)
    assert heights.max() == pytest.approx(0.1, abs=1e-6)


def test_every_catchment_is_fully_covered_by_the_grid(catchments, daily_granule):
    """Partial coverage means a catchment mean is taken over a subset of its
    own area — the exact silent error the old bounding box produced."""
    from ingestion.imerg import read_imerg_subset
    from processing.catchment_rainfall import (
        build_grid_cells,
        compute_overlaps,
        coverage_by_catchment,
    )

    cells = build_grid_cells(read_imerg_subset(daily_granule))
    coverage = coverage_by_catchment(compute_overlaps(cells, catchments))

    assert set(coverage) == set(EXPECTED_AREAS_KM2)
    for catchment_id, fraction in coverage.items():
        # Measured deviations are ~3e-5: intersection-area rounding between
        # the catchment polygons and the cell footprints, not real missing
        # area. 0.1 % is loose enough to ignore that and still tight enough
        # to catch genuine partial coverage, which the retired bounding box
        # would have shown as ~9 %.
        assert fraction == pytest.approx(1.0, abs=1e-3), (
            f"{catchment_id} is only {fraction:.2%} covered by the IMERG grid"
        )


def test_wadi_yutum_spans_many_cells_the_others_few(catchments, daily_granule):
    """A shape check on the join: AQ-C01 is ~70x the area of AQ-C05, so it
    must touch far more 0.1 deg cells. Catches a silently empty join."""
    from ingestion.imerg import read_imerg_subset
    from processing.catchment_rainfall import build_grid_cells, compute_overlaps

    cells = build_grid_cells(read_imerg_subset(daily_granule))
    overlaps = compute_overlaps(cells, catchments)
    counts = overlaps.groupby("catchment_id").size()

    assert counts["AQ-C01"] > 40
    assert counts["AQ-C05"] < 15
    assert counts["AQ-C01"] > 4 * counts["AQ-C05"]
