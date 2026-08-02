"""
Generate the Day-1 provisional seed data that unblocks Nizar's stream without waiting on
Mahdi (outlets) or Abd (observed plume mask) — see tasks/00-contracts.md §4, P2 and P5.

P2 · outlets_PROVISIONAL.gpkg
    One hand-placed point per catchment where a wadi meets the sea. Real coordinates come
    from Mahdi's DEM delineation later; this unblocks the particle engine today. Only
    AQ-O01 (Wadi Yutum, the project's primary demo catchment) is seeded for now — the
    concept doc's example event record (§12.3) uses this exact outlet coordinate.

P5 · observed_plume_PROVISIONAL.gpkg
    A plain ellipse offset from the outlet, standing in for Abd's real satellite-derived
    plume mask. Lets Nizar build and test the entire calibration parameter search before
    any real observation exists. Swapping in Abd's mask later is a file replacement, not
    a rebuild — same schema, same ID.

Neither of these should reach the final demo. Grep the repo for PROVISIONAL before
submission (tasks/00-contracts.md §5, Day 12 gate).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import Point, Polygon

REPO_ROOT = Path(__file__).resolve().parents[1]
VECTORS_DIR = REPO_ROOT / "data" / "processed" / "vectors"
PLUME_DIR = REPO_ROOT / "data" / "processed" / "plume"

STORAGE_CRS = "EPSG:4326"
AREA_CRS = "EPSG:32636"  # UTM 36N, per tasks/00-contracts.md §1

# Concept doc §12.3 example event record uses this as the Wadi Yutum outlet coordinate.
OUTLET_LON, OUTLET_LAT = 34.96, 29.54


def build_outlets_provisional() -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame(
        {
            "id": ["AQ-O01"],
            "catchment_id": ["AQ-C01"],
            "name": ["Wadi Yutum outlet (provisional, hand-placed)"],
        },
        geometry=[Point(OUTLET_LON, OUTLET_LAT)],
        crs=STORAGE_CRS,
    )
    return gdf


def build_synthetic_plume_ellipse(
    outlet_lon: float = OUTLET_LON,
    outlet_lat: float = OUTLET_LAT,
    offset_km: float = 1.5,
    bearing_deg: float = 200.0,  # south-southwest, roughly along the Gulf's long axis
    semi_major_km: float = 2.5,
    semi_minor_km: float = 1.0,
    rotation_deg: float = 200.0,
    n_vertices: int = 72,
) -> gpd.GeoDataFrame:
    """A plain ellipse offset from the outlet in projected (UTM 36N) space, then
    reprojected to EPSG:4326 for storage — matches the schema Abd's real
    observed_plume.gpkg will use (id, event_id, geometry)."""
    outlet = gpd.GeoDataFrame(geometry=[Point(outlet_lon, outlet_lat)], crs=STORAGE_CRS).to_crs(AREA_CRS)
    ox, oy = outlet.geometry.iloc[0].x, outlet.geometry.iloc[0].y

    bearing_rad = np.radians(bearing_deg)
    center_x = ox + offset_km * 1000 * np.sin(bearing_rad)
    center_y = oy + offset_km * 1000 * np.cos(bearing_rad)

    theta = np.linspace(0, 2 * np.pi, n_vertices)
    rot = np.radians(rotation_deg)
    ex = semi_major_km * 1000 * np.cos(theta)
    ey = semi_minor_km * 1000 * np.sin(theta)
    rx = ex * np.cos(rot) - ey * np.sin(rot) + center_x
    ry = ex * np.sin(rot) + ey * np.cos(rot) + center_y

    ellipse = Polygon(zip(rx, ry))
    gdf = gpd.GeoDataFrame(
        {
            "id": ["PLUME-PROVISIONAL-01"],
            "event_id": ["AQ-2016-10-25"],  # placeholder, matches Karam/Abd's primary candidate
            "quality_score": [0.0],
            "source": ["synthetic_ellipse_PROVISIONAL"],
        },
        geometry=[ellipse],
        crs=AREA_CRS,
    ).to_crs(STORAGE_CRS)
    return gdf


def main() -> None:
    VECTORS_DIR.mkdir(parents=True, exist_ok=True)
    PLUME_DIR.mkdir(parents=True, exist_ok=True)

    outlets = build_outlets_provisional()
    outlets_path = VECTORS_DIR / "outlets_PROVISIONAL.gpkg"
    outlets.to_file(outlets_path, driver="GPKG")
    print(f"Wrote {outlets_path} ({len(outlets)} outlet(s))")

    plume = build_synthetic_plume_ellipse()
    plume_path = PLUME_DIR / "observed_plume_PROVISIONAL.gpkg"
    plume.to_file(plume_path, driver="GPKG")
    print(f"Wrote {plume_path} ({len(plume)} polygon(s))")


if __name__ == "__main__":
    main()
