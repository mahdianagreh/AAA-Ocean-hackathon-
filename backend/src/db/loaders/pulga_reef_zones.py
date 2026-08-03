"""
Loader: Pulga's reef zones -> `reef_zones`.

Source: resolved by `resolve_reef_zones()` — the real Allen Coral Atlas export
(data/processed/vectors/reef_zones.gpkg) when it exists, otherwise the provisional
derivation. Per tasks/phase2/03-nizar.md §3: "reef_zones_PROVISIONAL.gpkg, then the
real ACA export". The real file landed 2026-08-03; same IDs, same columns, so the
upsert below is unchanged either way and `source_id` records which one was used.

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
_VECTORS = REPO_ROOT / "data" / "processed" / "vectors"

PROVISIONAL_SOURCE_ID = "reef_zones_provisional_derivation"
ACA_SOURCE_ID = "reef_zones_allen_coral_atlas_v2_0"


def resolve_reef_zones() -> tuple[Path, str, bool]:
    """(path, source_id, is_provisional) — prefer the real ACA export.

    The docstring above always said "then the real ACA export"; this implements it.
    The real file landed on 2026-08-03 once Earth Engine auth was completed, and it
    carries the same IDs and the same column names, so the upsert is unchanged —
    which was the point of enforcing schema continuity on the Pulga side.

    Preferring it here matters: otherwise the database keeps serving provisional
    geometry while a real export sits on disk beside it, and nothing would say so.
    """
    real = _VECTORS / "reef_zones.gpkg"
    prov = _VECTORS / "reef_zones_PROVISIONAL.gpkg"
    if real.exists():
        return real, ACA_SOURCE_ID, False
    return prov, PROVISIONAL_SOURCE_ID, True


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
    path, source_id, is_prov = resolve_reef_zones()
    if not path.exists():
        print(f"SKIP reef_zones: neither reef_zones.gpkg nor "
              f"reef_zones_PROVISIONAL.gpkg found in {_VECTORS}")
        return 0

    print(f"reef_zones source: {path.name} "
          f"({'PROVISIONAL' if is_prov else 'real Allen Coral Atlas v2.0'})")
    zones = gpd.read_file(path)
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
                    source_id=source_id,
                    is_provisional=bool(row["provisional"]),
                ),
            )
            n += 1
    return n


if __name__ == "__main__":
    n = load_reef_zones()
    print(f"Upserted {n} reef_zones.")
