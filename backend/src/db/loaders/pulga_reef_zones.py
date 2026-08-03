"""
Loader: Pulga's reef zones -> `reef_zones`.

Source: data/processed/vectors/reef_zones_PROVISIONAL.gpkg (per
tasks/phase2/03-nizar.md §3 — "reef_zones_PROVISIONAL.gpkg, then the real ACA
export"). Re-run this same loader once the real Allen Coral Atlas export lands at
the same path/filename convention — same IDs, same schema, an upsert either way.

Note: the source has `depth_median_m`, not a mean. Mapped into `mean_depth_m` as
the best available proxy since the schema has one depth column — flagged here
rather than silently presented as an actual mean.

`nearest_outlet_id` / `distance_to_outlet_m` (data-model.md §3.3 step 12) are not
yet computed in the source file and are left NULL rather than derived here —
that computation belongs to Pulga's stream, not this loader.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from sqlalchemy import text

from src.db.client import session_scope

REPO_ROOT = Path(__file__).resolve().parents[4]
REEF_ZONES_GPKG = REPO_ROOT / "data" / "processed" / "vectors" / "reef_zones_PROVISIONAL.gpkg"

PROVISIONAL_SOURCE_ID = "reef_zones_provisional_derivation"

UPSERT_SQL = text(
    """
    INSERT INTO reef_zones (
        id, name, geom, area_km2, habitat_class, mean_depth_m,
        sensitivity_weight, sensitivity_basis, source_id, is_provisional
    ) VALUES (
        :id, :name, ST_Multi(ST_GeomFromText(:geom_wkt, 4326)), :area_km2,
        :habitat_class, :mean_depth_m, :sensitivity_weight, :sensitivity_basis,
        :source_id, :is_provisional
    )
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        geom = EXCLUDED.geom,
        area_km2 = EXCLUDED.area_km2,
        habitat_class = EXCLUDED.habitat_class,
        mean_depth_m = EXCLUDED.mean_depth_m,
        sensitivity_weight = EXCLUDED.sensitivity_weight,
        sensitivity_basis = EXCLUDED.sensitivity_basis,
        source_id = EXCLUDED.source_id,
        is_provisional = EXCLUDED.is_provisional
    """
)


def load_reef_zones() -> int:
    if not REEF_ZONES_GPKG.exists():
        print(f"SKIP reef_zones: missing {REEF_ZONES_GPKG}")
        return 0

    zones = gpd.read_file(REEF_ZONES_GPKG)
    n = 0
    with session_scope() as session:
        for _, row in zones.iterrows():
            session.execute(
                UPSERT_SQL,
                dict(
                    id=row["reef_zone_id"],
                    name=row["zone_name"],
                    geom_wkt=row["geometry"].wkt,
                    area_km2=float(row["area_km2"]),
                    habitat_class=row["habitat_class"],
                    mean_depth_m=float(row["depth_median_m"]),
                    sensitivity_weight=float(row["sensitivity_weight"]),
                    sensitivity_basis=row["sensitivity_weight_status"],
                    source_id=PROVISIONAL_SOURCE_ID,
                    is_provisional=bool(row["provisional"]),
                ),
            )
            n += 1
    return n


if __name__ == "__main__":
    n = load_reef_zones()
    print(f"Upserted {n} reef_zones.")
