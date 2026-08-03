"""
Loader: Pulga's land cover, soil, and urban feature tables -> `catchment_surface_features`.

Sources (per data-model.md §3.3, steps 2-8):
    data/processed/features/landcover_by_catchment.parquet
    data/processed/features/soil_by_catchment.parquet
    data/processed/features/urban_by_catchment.parquet

Note: `erodibility_proxy` (data-model.md step 4: "derive from texture + organic
carbon, formula written down") is Pulga's derivation, not present in her delivered
soil table. Left NULL rather than invented here — that formula is hers to write
and document, not mine to guess at.

Idempotent: upserts on `catchment_id` (the table's primary key).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from src.db.client import session_scope

REPO_ROOT = Path(__file__).resolve().parents[4]
FEATURES_DIR = REPO_ROOT / "data" / "processed" / "features"

LANDCOVER_PARQUET = FEATURES_DIR / "landcover_by_catchment.parquet"
SOIL_PARQUET = FEATURES_DIR / "soil_by_catchment.parquet"
URBAN_PARQUET = FEATURES_DIR / "urban_by_catchment.parquet"

LANDCOVER_SOURCE_ID = "esa_worldcover_2021"
LANDCOVER_YEAR = 2021

# Classes counted as "vegetation" for the promoted column — everything that is
# neither bare ground, built-up, water, nor permanent ice.
VEGETATION_CLASSES = [
    "frac_tree_cover", "frac_shrubland", "frac_grassland", "frac_cropland",
    "frac_herbaceous_wetland", "frac_mangroves", "frac_moss_lichen",
]

UPSERT_SQL = text(
    """
    INSERT INTO catchment_surface_features (
        catchment_id, landcover_source_id, landcover_year,
        bare_ground_pct, built_up_pct, vegetation_pct, water_pct, class_fractions,
        clay_pct_0_5, sand_pct_0_5, silt_pct_0_5, soc_g_per_kg_0_5,
        bulk_density_0_5, coarse_fragments_pct_0_5,
        clay_pct_5_15, sand_pct_5_15, silt_pct_5_15,
        road_length_km, building_footprint_km2, impervious_pct_est, is_provisional
    ) VALUES (
        :catchment_id, :landcover_source_id, :landcover_year,
        :bare_ground_pct, :built_up_pct, :vegetation_pct, :water_pct, :class_fractions,
        :clay_pct_0_5, :sand_pct_0_5, :silt_pct_0_5, :soc_g_per_kg_0_5,
        :bulk_density_0_5, :coarse_fragments_pct_0_5,
        :clay_pct_5_15, :sand_pct_5_15, :silt_pct_5_15,
        :road_length_km, :building_footprint_km2, :impervious_pct_est, :is_provisional
    )
    ON CONFLICT (catchment_id) DO UPDATE SET
        landcover_source_id = EXCLUDED.landcover_source_id,
        landcover_year = EXCLUDED.landcover_year,
        bare_ground_pct = EXCLUDED.bare_ground_pct,
        built_up_pct = EXCLUDED.built_up_pct,
        vegetation_pct = EXCLUDED.vegetation_pct,
        water_pct = EXCLUDED.water_pct,
        class_fractions = EXCLUDED.class_fractions,
        clay_pct_0_5 = EXCLUDED.clay_pct_0_5,
        sand_pct_0_5 = EXCLUDED.sand_pct_0_5,
        silt_pct_0_5 = EXCLUDED.silt_pct_0_5,
        soc_g_per_kg_0_5 = EXCLUDED.soc_g_per_kg_0_5,
        bulk_density_0_5 = EXCLUDED.bulk_density_0_5,
        coarse_fragments_pct_0_5 = EXCLUDED.coarse_fragments_pct_0_5,
        clay_pct_5_15 = EXCLUDED.clay_pct_5_15,
        sand_pct_5_15 = EXCLUDED.sand_pct_5_15,
        silt_pct_5_15 = EXCLUDED.silt_pct_5_15,
        road_length_km = EXCLUDED.road_length_km,
        building_footprint_km2 = EXCLUDED.building_footprint_km2,
        impervious_pct_est = EXCLUDED.impervious_pct_est,
        is_provisional = EXCLUDED.is_provisional,
        updated_at = now()
    """
)


def load_surface_features() -> int:
    if not (LANDCOVER_PARQUET.exists() and SOIL_PARQUET.exists() and URBAN_PARQUET.exists()):
        print("SKIP catchment_surface_features: one or more source parquet files missing")
        return 0

    landcover = pd.read_parquet(LANDCOVER_PARQUET).set_index("catchment_id")
    soil = pd.read_parquet(SOIL_PARQUET).set_index("catchment_id")
    urban = pd.read_parquet(URBAN_PARQUET).set_index("catchment_id")

    n = 0
    with session_scope() as session:
        for catchment_id in landcover.index:
            lc = landcover.loc[catchment_id]
            sl = soil.loc[catchment_id]
            ub = urban.loc[catchment_id]

            class_fractions = {
                col.removeprefix("frac_"): float(lc[col])
                for col in lc.index
                if col.startswith("frac_")
            }
            vegetation_pct = sum(lc[c] for c in VEGETATION_CLASSES) * 100.0

            session.execute(
                UPSERT_SQL,
                dict(
                    catchment_id=catchment_id,
                    landcover_source_id=LANDCOVER_SOURCE_ID,
                    landcover_year=LANDCOVER_YEAR,
                    bare_ground_pct=float(lc["frac_bare_sparse_vegetation"]) * 100.0,
                    built_up_pct=float(lc["frac_built_up"]) * 100.0,
                    vegetation_pct=vegetation_pct,
                    water_pct=float(lc["frac_permanent_water_bodies"]) * 100.0,
                    class_fractions=json.dumps(class_fractions),
                    clay_pct_0_5=float(sl["clay_0_5cm_mean"]),
                    sand_pct_0_5=float(sl["sand_0_5cm_mean"]),
                    silt_pct_0_5=float(sl["silt_0_5cm_mean"]),
                    soc_g_per_kg_0_5=float(sl["soc_0_5cm_mean"]),
                    bulk_density_0_5=float(sl["bdod_0_5cm_mean"]),
                    coarse_fragments_pct_0_5=float(sl["cfvo_0_5cm_mean"]),
                    clay_pct_5_15=float(sl["clay_5_15cm_mean"]),
                    sand_pct_5_15=float(sl["sand_5_15cm_mean"]),
                    silt_pct_5_15=float(sl["silt_5_15cm_mean"]),
                    road_length_km=float(ub["road_length_km"]),
                    building_footprint_km2=float(ub["osm_building_frac"]) * float(ub["area_km2"]),
                    # WorldCover's built_up class is the primary impervious estimate;
                    # OSM building footprints are a deliberately separate independent
                    # check (Pulga's own framing), not blended into this column.
                    impervious_pct_est=float(lc["frac_built_up"]) * 100.0,
                    is_provisional=False,
                ),
            )
            n += 1
    return n


if __name__ == "__main__":
    n = load_surface_features()
    print(f"Upserted {n} catchment_surface_features rows.")
