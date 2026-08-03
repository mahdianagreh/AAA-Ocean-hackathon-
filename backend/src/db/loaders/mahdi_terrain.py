"""
Loader: Mahdi's terrain & hydrology outputs -> `catchments`, `outlets`.

Sources (per tasks/phase2/03-nizar.md §3):
    data/processed/vectors/catchments.gpkg
    data/processed/vectors/outlets.gpkg
    data/processed/features/catchment_terrain.parquet

Idempotent: every write is an upsert keyed on the primary key (`id`), so re-running
after Mahdi publishes an updated file is a single command, not a manual diff.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from sqlalchemy import text

from src.db.client import session_scope

REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "data" / "processed"

CATCHMENTS_GPKG = DATA_DIR / "vectors" / "catchments.gpkg"
OUTLETS_GPKG = DATA_DIR / "vectors" / "outlets.gpkg"
TERRAIN_PARQUET = DATA_DIR / "features" / "catchment_terrain.parquet"

DEM_SOURCE_ID = "cop_dem_glo30"

# The only catchment with a documented human name so far (tasks/phase2/00-phase2-plan.md).
# Left blank rather than invented for the other four.
CATCHMENT_NAMES = {"AQ-C01": "Wadi Yutum"}

UPSERT_CATCHMENT_SQL = text(
    """
    INSERT INTO catchments (
        id, name, geom, area_km2, perimeter_km, mean_elev_m, relief_m,
        mean_slope_deg, max_slope_deg, drainage_density_km_km2, stream_length_km,
        longest_flowpath_km, max_flow_accum_cells, dem_source_id,
        delineation_method, notes, is_provisional
    ) VALUES (
        :id, :name, ST_Multi(ST_GeomFromText(:geom_wkt, 4326)), :area_km2, :perimeter_km,
        :mean_elev_m, :relief_m, :mean_slope_deg, :max_slope_deg,
        :drainage_density_km_km2, :stream_length_km, :longest_flowpath_km,
        :max_flow_accum_cells, :dem_source_id, :delineation_method, :notes,
        :is_provisional
    )
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        geom = EXCLUDED.geom,
        area_km2 = EXCLUDED.area_km2,
        perimeter_km = EXCLUDED.perimeter_km,
        mean_elev_m = EXCLUDED.mean_elev_m,
        relief_m = EXCLUDED.relief_m,
        mean_slope_deg = EXCLUDED.mean_slope_deg,
        max_slope_deg = EXCLUDED.max_slope_deg,
        drainage_density_km_km2 = EXCLUDED.drainage_density_km_km2,
        stream_length_km = EXCLUDED.stream_length_km,
        longest_flowpath_km = EXCLUDED.longest_flowpath_km,
        max_flow_accum_cells = EXCLUDED.max_flow_accum_cells,
        dem_source_id = EXCLUDED.dem_source_id,
        delineation_method = EXCLUDED.delineation_method,
        notes = EXCLUDED.notes,
        is_provisional = EXCLUDED.is_provisional,
        updated_at = now()
    """
)

UPSERT_OUTLET_SQL = text(
    """
    INSERT INTO outlets (id, catchment_id, geom, method, is_provisional)
    VALUES (:id, :catchment_id, ST_GeomFromText(:geom_wkt, 4326), :method, :is_provisional)
    ON CONFLICT (id) DO UPDATE SET
        catchment_id = EXCLUDED.catchment_id,
        geom = EXCLUDED.geom,
        method = EXCLUDED.method,
        is_provisional = EXCLUDED.is_provisional
    """
)


def _delineation_method(source_note: str) -> str:
    """Mahdi's `source` string names the DEM and algorithm in prose, e.g.
    'Copernicus GLO-30 30 m, D8, endorheic basins preserved'. Extract the short
    method code without inventing detail the source doesn't state."""
    return "d8" if "D8" in source_note else source_note


def load_catchments() -> int:
    if not CATCHMENTS_GPKG.exists() or not TERRAIN_PARQUET.exists():
        print(f"SKIP catchments: missing {CATCHMENTS_GPKG} or {TERRAIN_PARQUET}")
        return 0

    catchments = gpd.read_file(CATCHMENTS_GPKG)
    terrain = pd.read_parquet(TERRAIN_PARQUET)
    merged = catchments.merge(terrain, on="catchment_id", suffixes=("", "_terrain"))

    # Perimeter is not shipped by either source file — derive it here in the
    # project's projected CRS (UTM 36N), per tasks/00-contracts.md's CRS rule:
    # area/distance maths only in EPSG:32636, never in degrees.
    perimeters_km = catchments.to_crs("EPSG:32636").geometry.length / 1000.0

    n = 0
    with session_scope() as session:
        for idx, row in merged.iterrows():
            session.execute(
                UPSERT_CATCHMENT_SQL,
                dict(
                    id=row["catchment_id"],
                    name=CATCHMENT_NAMES.get(row["catchment_id"]),
                    geom_wkt=row["geometry"].wkt,
                    area_km2=float(row["area_km2"]),
                    perimeter_km=float(perimeters_km.iloc[idx]),
                    mean_elev_m=float(row["elev_mean_m"]),
                    relief_m=float(row["relief_m"]),
                    mean_slope_deg=float(row["slope_mean_deg"]),
                    max_slope_deg=float(row["slope_max_deg"]),
                    drainage_density_km_km2=float(row["drainage_density_km_km2"]),
                    stream_length_km=float(row["stream_len_km"]),
                    longest_flowpath_km=float(row["dist_to_coast_max_km"]),
                    max_flow_accum_cells=int(row["outlet_accum_cells"]),
                    dem_source_id=DEM_SOURCE_ID,
                    delineation_method=_delineation_method(row["source"]),
                    notes=row["source"],
                    is_provisional=bool(row["provisional"]),
                ),
            )
            n += 1
    return n


def load_outlets() -> int:
    if not OUTLETS_GPKG.exists():
        print(f"SKIP outlets: missing {OUTLETS_GPKG}")
        return 0

    outlets = gpd.read_file(OUTLETS_GPKG)
    n = 0
    with session_scope() as session:
        for _, row in outlets.iterrows():
            method = (
                f"{row['method']} (confidence: {row['position_confidence']})"
                + (f" — {row['imagery_note']}" if row.get("imagery_note") else "")
            )
            session.execute(
                UPSERT_OUTLET_SQL,
                dict(
                    id=row["outlet_id"],
                    catchment_id=row["catchment_id"],
                    geom_wkt=row["geometry"].wkt,
                    method=method,
                    is_provisional=bool(row["provisional"]),
                ),
            )
            n += 1
    return n


def run() -> None:
    n_catchments = load_catchments()
    print(f"Upserted {n_catchments} catchments.")
    n_outlets = load_outlets()
    print(f"Upserted {n_outlets} outlets.")


if __name__ == "__main__":
    run()
