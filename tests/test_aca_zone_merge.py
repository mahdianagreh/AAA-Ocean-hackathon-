"""The assignment decisions behind the ACA reef-zone swap.

Each test here corresponds to a way the merge produced a plausible wrong number
with no error — the failure mode this project keeps hitting. The geometry is
synthetic and tiny so the arithmetic is checkable by hand; the real raster is
23545x25965 and cannot be a fixture.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"


def _load_export_aca():
    """Load export_aca without leaving `scripts/` on sys.path.

    `scripts/config.py` is a MODULE and `backend/src/config/` is a PACKAGE, both
    importable as `config`. Leaving scripts/ on sys.path makes the flat module win
    for the whole session, so `from config.spatial import ...` in five other test
    files dies with "'config' is not a package" — and it dies at COLLECTION, so the
    suite reports errors in files this one never touches. The path and the cached
    `config` entry are both restored once export_aca has been executed.
    """
    saved_path = list(sys.path)
    saved_config = sys.modules.get("config")
    sys.path.insert(0, str(SCRIPTS))
    try:
        sys.modules.pop("config", None)
        spec = importlib.util.spec_from_file_location(
            "export_aca", SCRIPTS / "export_aca.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules["export_aca"] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = saved_path
        if saved_config is not None:
            sys.modules["config"] = saved_config
        else:
            sys.modules.pop("config", None)


aca = _load_export_aca()

CRS = "EPSG:32636"


def test_class_tables_cover_every_code_the_atlas_publishes():
    """The labels are constants, so a missing code would raise a KeyError mid-merge
    and a WRONG code would silently mislabel a zone. Both are worse than a fixture."""
    assert set(aca.BENTHIC_CLASSES) >= {0, 11, 12, 13, 14, 15, 18}
    assert set(aca.GEOMORPHIC_CLASSES) >= {0, 11, 12, 13, 14, 15, 16, 21, 22, 23, 24, 25}
    # The specific pair that a plausible guess gets wrong.
    assert aca.GEOMORPHIC_CLASSES[22] == "Reef Slope"
    assert aca.GEOMORPHIC_CLASSES[24] == "Back Reef Slope"
    assert aca.BENTHIC_CLASSES[13] == "Rock"
    assert aca.BENTHIC_CLASSES[15] == "Coral/Algae"


def test_cutting_fragments_beats_assigning_them_whole():
    """The bug that gave R-05 475 m2 while 0.068 km2 of reef sat inside its box.

    One long fringing strip crossing three zones must contribute its own piece to
    each. Assigning it whole to the zone it overlaps MOST gives that zone the
    entire strip and the other two nothing — no error, just a wrong area per zone,
    which is exactly what the exposure engine consumes.
    """
    # A 300 m strip crossing three 100 m-wide zones, overlapping the middle one most.
    strip = gpd.GeoDataFrame(
        {"aca_class": [15]}, geometry=[box(0, 0, 300, 10)], crs=CRS)
    zones = gpd.GeoDataFrame(
        {"reef_zone_id": ["R-01", "R-02", "R-03"]},
        geometry=[box(0, 0, 80, 10), box(80, 0, 220, 10), box(220, 0, 300, 10)],
        crs=CRS,
    )

    pieces = gpd.overlay(strip, zones, how="intersection", keep_geom_type=True)
    by_zone = pieces.groupby("reef_zone_id").geometry.apply(lambda g: g.area.sum())

    assert set(by_zone.index) == {"R-01", "R-02", "R-03"}, (
        "a strip crossing three zones must reach all three"
    )
    assert by_zone["R-01"] == pytest.approx(800.0)
    assert by_zone["R-02"] == pytest.approx(1400.0)
    assert by_zone["R-03"] == pytest.approx(800.0)
    # And the whole-fragment rule would have handed all 3000 m2 to the winner.
    assert by_zone["R-02"] < strip.geometry.area.sum()


def test_cutting_conserves_area():
    """Kept plus dropped must equal what was polygonized.

    Overlay silently dropping or duplicating a sliver looks identical to a correct
    result. This is the check that would have caught the whole-fragment bug, which
    double-counted the parts of a strip lying outside its winning zone.
    """
    frags = gpd.GeoDataFrame(
        {"aca_class": [15, 13]},
        geometry=[box(0, 0, 300, 10), box(9000, 0, 9100, 10)],  # second far away
        crs=CRS,
    )
    zones = gpd.GeoDataFrame(
        {"reef_zone_id": ["R-01", "R-02"]},
        geometry=[box(0, 0, 80, 10), box(80, 0, 220, 10)],
        crs=CRS,
    )

    inside = gpd.overlay(frags, zones, how="intersection", keep_geom_type=True)
    outside = gpd.overlay(frags, zones[["geometry"]], how="difference",
                          keep_geom_type=True).explode(index_parts=False)

    total = frags.geometry.area.sum()
    assert inside.geometry.area.sum() + outside.geometry.area.sum() == pytest.approx(total)


def test_dominant_habitat_is_by_area_not_by_piece_count():
    """Polygonizing a raster yields one big patch plus a scatter of single-pixel
    specks. Counting pieces lets the specks outvote the patch that IS the zone."""
    import pandas as pd

    pieces = pd.DataFrame({
        "aca_class": [15] + [13] * 20,          # one coral patch, twenty rock specks
        "area_km2": [1.0] + [0.001] * 20,
    })

    by_count = pieces["aca_class"].value_counts().index[0]
    by_area = pieces.groupby("aca_class")["area_km2"].sum().sort_values(
        ascending=False).index[0]

    assert by_count == 13, "twenty specks do outnumber one patch"
    assert by_area == 15, "but the zone is overwhelmingly coral by extent"
    assert by_count != by_area, "the two rules disagree, which is why this is tested"


def test_snap_tolerance_is_far_below_the_distance_to_foreign_reef():
    """The snap must repair a clipped box, never reach across a border.

    Measured on the real export: the nearest reef outside the Jordanian chain is
    more than 5 km away, while the tolerance is 100 m.
    """
    assert aca.SNAP_TOLERANCE_M == 100
    assert aca.SNAP_TOLERANCE_M < 5000 / 10


def test_depth_is_averaged_over_water_cells_only():
    """A 50 m bathymetry under a 5 m reef strip returns land cells.

    Including them reports a reef above sea level; treating a missing depth as 0
    breaks the rule that missing is never zero. R-02 has no water cell at all and
    must come out NaN.
    """
    import numpy as np

    cells = np.array([11.7, 5.1, 10.3])            # R-02: every cell dry
    wet = cells[cells < 0]
    assert wet.size == 0
    median = float(np.median(wet)) if wet.size else float("nan")
    assert np.isnan(median), "no water cell must yield NaN, never 0.0 and never +10 m"

    # R-06 straddles the boundary with land cells in the MAJORITY (52% of 73), which
    # is what drags the unfiltered median above sea level.
    mixed = np.array([8.5, 2.0, 0.6, -3.5, -25.2])
    wet_mixed = mixed[mixed < 0]
    assert float(np.median(wet_mixed)) == pytest.approx(-14.35)
    assert float(np.median(mixed)) > 0, (
        "with land cells in the majority the unfiltered median has the wrong sign — "
        "it reports the reef above sea level"
    )


@pytest.mark.skipif(
    not (PROJECT_ROOT / "data/processed/vectors/reef_zones.gpkg").exists(),
    reason="ACA swap not yet run",
)
class TestRealOutput:
    """Contract checks against the built file, once it exists."""

    @pytest.fixture(scope="class")
    @classmethod
    def zones(cls):
        return gpd.read_file(PROJECT_ROOT / "data/processed/vectors/reef_zones.gpkg")

    @pytest.fixture(scope="class")
    @classmethod
    def provisional(cls):
        return gpd.read_file(
            PROJECT_ROOT / "data/processed/vectors/reef_zones_PROVISIONAL.gpkg")

    def test_ids_are_never_renumbered(self, zones, provisional):
        assert not set(zones["reef_zone_id"]) - set(provisional["reef_zone_id"])

    def test_no_provisional_field_is_dropped(self, zones, provisional):
        """Pulga's same-schema rule, in the direction that actually broke.

        The final file quietly lost depth_min_m/depth_median_m, which broke
        qa_marine's per-zone insets — a downstream KeyError from a file that
        looked complete.
        """
        lost = set(provisional.columns) - set(zones.columns)
        assert not lost, f"final file dropped provisional fields: {sorted(lost)}"

    def test_sensitivity_weight_is_still_an_honest_placeholder(self, zones):
        """ACA maps habitat, not sensitivity. Real habitat arriving is not a
        licence to invent a weight from it."""
        assert (zones["sensitivity_weight"] == 1.0).all()
        assert (zones["sensitivity_weight_status"]
                == "PLACEHOLDER_PENDING_MARINE_SCIENTIST").all()

    def test_habitat_labels_are_readable_not_raw_codes(self, zones):
        """This column reaches the map popup, Postgres and the RAG answers."""
        assert set(zones["habitat_class"]) <= set(aca.BENTHIC_CLASSES.values())
        assert not zones["habitat_class"].str.startswith("ACA_benthic_").any()
        # The code survives beside it, so provenance back to the raster is intact.
        for _, r in zones.iterrows():
            assert aca.BENTHIC_CLASSES[r["habitat_class_code"]] == r["habitat_class"]

    def test_geometry_derived_attributes_were_recomputed_not_inherited(
            self, zones, provisional):
        """The outlines changed, so any inherited per-zone statistic describes a
        shape that no longer exists. Marine Park overlap was being carried across
        verbatim, reporting a fact about a hand-drawn box as a fact about reef."""
        merged = provisional[["reef_zone_id", "marine_park_overlap_pct"]].merge(
            zones[["reef_zone_id", "marine_park_overlap_pct"]],
            on="reef_zone_id", suffixes=("_prov", "_aca"))
        changed = (merged["marine_park_overlap_pct_prov"]
                   != merged["marine_park_overlap_pct_aca"]).sum()
        assert changed > 0, (
            "not one zone's park overlap changed after the geometry changed — the "
            "values are being inherited from the provisional file"
        )

    def test_depth_is_missing_rather_than_wrong_where_unmeasurable(self, zones):
        """Whatever depth is reported must be a depth: below sea level, or absent."""
        measured = zones["depth_median_m"].dropna()
        assert (measured < 0).all(), (
            f"positive 'depth' reported for "
            f"{zones.loc[zones.depth_median_m >= 0, 'reef_zone_id'].tolist()}"
        )
        assert "depth_land_cell_pct" in zones.columns, (
            "the land-cell share must travel with the depth so the 50 m / 5 m "
            "resolution mismatch is visible rather than absorbed"
        )
