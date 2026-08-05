"""
Smoke test / seed utility for the exposure -> Postgres bridge
(backend/src/db/loaders/exposure_runs.py).

No exposure run existed anywhere on disk when this was written — nobody had
called `/exposure/calculate` on this machine yet, so there was nothing to
bridge. This produces one genuine run using the REAL exposure engine
(backend/src/exposure/engine.py) and REAL geometry (outlets.gpkg,
reef_zones.gpkg), so the bridge loader has real data to prove itself against
rather than a hand-built fixture.

The only stand-in is the synthetic concentric-contour generator — but that is
exactly what `/exposure/calculate` itself uses today (`plume_source:
SYNTHETIC_STUB`, per backend/src/api/main.py::_synthetic_contours), so this is
faithful to current production behaviour, not a shortcut around it.

Run: cd backend && .venv/bin/python ../scripts/smoke_test_exposure_bridge.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend" / "src"))
sys.path.insert(0, str(REPO_ROOT / "backend" / "src" / "exposure"))

import geopandas as gpd  # noqa: E402
from shapely.geometry import Point  # noqa: E402

import engine  # noqa: E402
import store  # noqa: E402

REEF_ZONES_GPKG = REPO_ROOT / "data" / "processed" / "vectors" / "reef_zones.gpkg"
OUTLETS_GPKG = REPO_ROOT / "data" / "processed" / "vectors" / "outlets.gpkg"

HORIZON_HOURS = 48
# Same formula as backend/src/api/main.py::_synthetic_contours, reproduced here
# rather than imported — importing main.py would pull in fastapi at module
# scope, which this environment does not have installed.
CONTOUR_HOURS = [3, 6, 12, 24, 36, 48]
CONTOUR_PROBABILITY = {3: 0.9, 6: 0.75, 12: 0.55, 24: 0.35, 36: 0.2, 48: 0.1}
CONTOUR_RADIUS_M = {t: 600 * (t ** 0.5) for t in CONTOUR_HOURS}


def build_synthetic_contours(lon: float, lat: float) -> gpd.GeoDataFrame:
    pt = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(engine.CRS_MEASURE).iloc[0]
    rows = [
        {"t_hours": t, "probability": CONTOUR_PROBABILITY[t],
         "geometry": pt.buffer(CONTOUR_RADIUS_M[t])}
        for t in CONTOUR_HOURS
    ]
    return gpd.GeoDataFrame(rows, crs=engine.CRS_MEASURE)


def main() -> None:
    outlets = gpd.read_file(OUTLETS_GPKG)
    zones = gpd.read_file(REEF_ZONES_GPKG)

    # AQ-O01 (Wadi Yutum) — the project's primary demo outlet, per
    # tasks/phase3/00-phase3-plan.md's geometry contract.
    outlet = outlets[outlets["outlet_id"] == "AQ-O01"].iloc[0]

    contours = build_synthetic_contours(outlet["lon"], outlet["lat"])
    overlay = engine.intersect_plume_with_zones(contours, zones)

    confidence_adjustment = 0.6
    confidence = engine.confidence_label(confidence_adjustment)
    zone_id_col = "reef_zone_id" if "reef_zone_id" in zones.columns else "id"

    results = []
    for zid in sorted(zones[zone_id_col].dropna().unique()):
        summary = engine.summarise_zone(
            zid, overlay,
            relative_sediment_intensity=0.42,
            confidence_adjustment=confidence_adjustment,
            horizon_hours=float(HORIZON_HOURS),
        )
        if summary is None:
            continue
        summary["formula_terms"].update({
            "relative_sediment_intensity_source": "smoke_test_exposure_bridge.py fixed value",
            "confidence_adjustment_reason": "coarse global current model + GMRT-substituted bathymetry",
            "plume_source": "SYNTHETIC_STUB",
            "model_versions": {
                "exposure_engine": "0.2.0",
                "runoff_model": "runoff_weighted_gbm_2194b48_20260803T214757Z",
                "particle_engine": "stub-0.1",
                "reef_zones": "AllenCoralAtlas-v2_0",
                "bathymetry": "GMRT-substituted-for-GEBCO",
            },
        })
        summary["confidence"] = confidence
        results.append(summary)

    if not results:
        print("No reef zone reached — nothing to seed. Check outlet/zone geometry.")
        return

    run_id = store.new_run_id()
    store.save_run(
        run_id=run_id,
        event_id="AQ-2016-10-28",
        outlet_id="AQ-O01",
        results=results,
        model_versions=results[0]["formula_terms"]["model_versions"],
        caveats=[],
    )
    print(f"Seeded exposure run {run_id} with {len(results)} zone result(s) "
          f"into {store.db_path()}")


if __name__ == "__main__":
    main()
