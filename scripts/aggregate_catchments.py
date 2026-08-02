"""Per-catchment land-cover, soil and urban features — the runoff model's inputs.

Produces (only when running on real or provisional catchments):
    data/processed/features/landcover_by_catchment.parquet
    data/processed/features/soil_by_catchment.parquet
    data/processed/features/urban_by_catchment.parquet

Run:  .venv/bin/python scripts/aggregate_catchments.py

CATCHMENT SOURCE RESOLUTION
---------------------------
Mahdi owns the catchment polygons (contract §4 P1). This script takes whichever
of these exists, in order:

  1. data/processed/vectors/catchments.gpkg              (real, final)
  2. data/processed/vectors/catchments_PROVISIONAL.gpkg  (Mahdi's Day-1 seed)
  3. data/interim/catchments_FIXTURE_local_test_only.gpkg (our own test fixture)

On (3) it writes to data/interim/ with a _FIXTURE suffix and REFUSES to touch the
contract feature paths. That distinction is the whole point: the pipeline gets
exercised and verified today, but fixture-derived numbers cannot reach the runoff
model or the demo by accident. When Mahdi publishes, re-run — nothing else
changes, which is exactly the contract's "cost of a rerun is minutes" claim.
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterstats import zonal_stats

from config import (
    AOI_CRS_PROJECTED,
    FEATURES,
    INTERIM,
    PROCESSED,
    VECTORS,
    WORLDCOVER_CLASSES,
)
from soilgrids_units import CONVERSIONS, DEPTHS, load_converted, raw_path

WORLDCOVER_CLIP = INTERIM / "worldcover_terrain_v2_clip.tif"
OSM_GPKG = VECTORS / "osm_aqaba.gpkg"

CATCHMENT_CANDIDATES = [
    (VECTORS / "catchments.gpkg", "real", True),
    (VECTORS / "catchments_PROVISIONAL.gpkg", "provisional", True),
    (INTERIM / "catchments_FIXTURE_local_test_only.gpkg", "fixture", False),
]


def resolve_catchments():
    # An explicit --input wins over the search order: the plan calls this script
    # with a path, and silently ignoring it would be the worst kind of surprise.
    for i, a in enumerate(sys.argv):
        if a == "--input" and i + 1 < len(sys.argv):
            path = Path(sys.argv[i + 1])
            if not path.exists():
                sys.exit(f"--input {path} does not exist")
            gdf = gpd.read_file(path)
            if "catchment_id" not in gdf.columns and "id" in gdf.columns:
                gdf = gdf.rename(columns={"id": "catchment_id"})
            fixture = "FIXTURE" in path.name
            print(f"catchments: {path.name}  [--input, {len(gdf)} features]")
            return gdf, "explicit", not fixture

    for path, kind, publishable in CATCHMENT_CANDIDATES:
        if path.exists():
            gdf = gpd.read_file(path)
            if "catchment_id" not in gdf.columns:
                # Contract §3 names the column `id`; the feature tables join on
                # `catchment_id`. Accept either rather than failing on a rename.
                if "id" in gdf.columns:
                    gdf = gdf.rename(columns={"id": "catchment_id"})
                else:
                    sys.exit(f"{path.name} has neither `catchment_id` nor `id`")
            print(f"catchments: {path.name}  [{kind}, {len(gdf)} features]")
            if not publishable:
                print("  *** FIXTURE MODE — outputs go to data/interim/ with a _FIXTURE")
                print("  *** suffix. The contract feature paths are NOT written.")
            return gdf, kind, publishable

    sys.exit(
        "No catchments found. Mahdi owns catchments_PROVISIONAL.gpkg (contract §4 P1).\n"
        "To exercise this pipeline meanwhile: "
        ".venv/bin/python scripts/make_catchments_fixture.py"
    )


def out_path(stem, publishable):
    if publishable:
        FEATURES.mkdir(parents=True, exist_ok=True)
        return FEATURES / f"{stem}.parquet"
    INTERIM.mkdir(parents=True, exist_ok=True)
    return INTERIM / f"{stem}_FIXTURE.parquet"


def landcover_features(catchments):
    """Per-catchment WorldCover class fractions."""
    stats = zonal_stats(catchments, str(WORLDCOVER_CLIP), categorical=True, nodata=0)

    rows = []
    for cid, stat in zip(catchments["catchment_id"], stats):
        # Total over CLASSIFIED pixels only. Including nodata in the denominator
        # would shrink every fraction by an arbitrary amount near the AOI edge.
        counts = {int(k): v for k, v in (stat or {}).items() if int(k) != 0}
        total = sum(counts.values())
        row = {"catchment_id": cid, "landcover_px_total": total}
        for code, name in WORLDCOVER_CLASSES.items():
            row[f"frac_{name}"] = counts.get(code, 0) / total if total else np.nan

        # Convenience column: the sediment-load proxy signal in one number.
        row["frac_bare_or_sparse"] = row["frac_bare_sparse_vegetation"]
        rows.append(row)

    df = pd.DataFrame(rows)

    frac_cols = [c for c in df.columns if c.startswith("frac_") and c != "frac_bare_or_sparse"]
    sums = df[frac_cols].sum(axis=1)
    assert np.allclose(sums.dropna(), 1.0, atol=1e-6), (
        f"class fractions do not sum to 1 per catchment: {sums.tolist()}"
    )
    return df


def soil_features(catchments):
    """Per-catchment distribution stats for every SoilGrids variable and depth.

    Not just the mean. A catchment mean is a point estimate that hides whether a
    catchment is uniform or wildly heterogeneous, and the runoff model builder
    may well want that variance as a feature — a catchment with clay ranging
    15-55% behaves differently from one uniformly at 35%. Computing the extra
    statistics costs one pass over a 155x188 raster, so there is no reason to
    withhold them and force a re-run later.
    """
    stats_wanted = ["mean", "std", "min", "max", "median", "count"]
    rows = {cid: {"catchment_id": cid} for cid in catchments["catchment_id"]}

    for variable in CONVERSIONS:
        for depth in DEPTHS:
            arr, _ = load_converted(variable, depth)
            with rasterio.open(raw_path(variable, depth)) as src:
                affine = src.transform

            # all_touched: SoilGrids is 250 m, so a small catchment can otherwise
            # contain no cell centre at all and come back as None.
            stats = zonal_stats(
                catchments, arr, affine=affine, stats=stats_wanted,
                nodata=np.nan, all_touched=True,
            )
            base = f"{variable}_{depth.replace('-', '_')}"
            for cid, s in zip(catchments["catchment_id"], stats):
                for stat in stats_wanted:
                    rows[cid][f"{base}_{stat}"] = s[stat]

    df = pd.DataFrame(list(rows.values()))

    # Texture must still close to ~100% after spatial averaging.
    for depth in DEPTHS:
        d = depth.replace("-", "_")
        total = df[f"clay_{d}_mean"] + df[f"sand_{d}_mean"] + df[f"silt_{d}_mean"]
        assert np.allclose(total.dropna(), 100.0, atol=1.0), (
            f"catchment-mean texture at {depth} does not sum to 100: {total.tolist()}"
        )

    assert not df.drop(columns=["catchment_id"]).isna().all(axis=1).any(), (
        "a catchment got no soil data at all — check AOI coverage"
    )
    return df


def urban_features(catchments):
    """Road density and built-up fraction from OSM — the impervious-surface proxy."""
    cat = catchments.to_crs(AOI_CRS_PROJECTED)
    roads = gpd.read_file(OSM_GPKG, layer="roads").to_crs(AOI_CRS_PROJECTED)
    builds = gpd.read_file(OSM_GPKG, layer="buildings").to_crs(AOI_CRS_PROJECTED)
    drains = gpd.read_file(OSM_GPKG, layer="drainage_features").to_crs(AOI_CRS_PROJECTED)

    # Optional layers — added in the expansion pass. Read defensively so an older
    # osm_aqaba.gpkg without them still produces the core features.
    def optional(layer):
        try:
            return gpd.read_file(OSM_GPKG, layer=layer).to_crs(AOI_CRS_PROJECTED)
        except Exception:
            print(f"    (layer {layer!r} absent — column will be NaN)")
            return None

    industrial = optional("industrial")
    infra = optional("infrastructure_lines")
    poi = optional("dive_tourism_poi")

    rows = []
    for _, c in cat.iterrows():
        geom = c.geometry
        area_km2 = geom.area / 1e6

        r = roads[roads.intersects(geom)]
        road_km = r.intersection(geom).length.sum() / 1000.0

        b = builds[builds.intersects(geom)]
        build_m2 = b.intersection(geom).area.sum()

        d = drains[drains.intersects(geom)]
        drain_km = d.intersection(geom).length.sum() / 1000.0

        row = {
            "catchment_id": c["catchment_id"],
            "area_km2": area_km2,
            "road_density_km_per_km2": road_km / area_km2 if area_km2 else np.nan,
            "road_length_km": road_km,
            # OSM footprint fraction. This is an INDEPENDENT estimate of
            # built-up cover from WorldCover's frac_built_up — the two
            # disagreeing is informative, not a bug: OSM maps roofs, while
            # WorldCover's built_up class includes roads, yards and parking.
            "osm_building_frac": build_m2 / geom.area if geom.area else np.nan,
            "osm_building_count": int(len(b)),
            "mapped_drainage_km_per_km2": drain_km / area_km2 if area_km2 else np.nan,
        }

        # Industrial land is a sediment- and contaminant-source proxy distinct
        # from generic built-up: port and phosphate handling sit in these polygons.
        if industrial is not None:
            i = industrial[industrial.intersects(geom)]
            row["industrial_frac"] = (
                i.intersection(geom).area.sum() / geom.area if geom.area else np.nan
            )
        if infra is not None:
            f = infra[infra.intersects(geom)]
            row["infra_line_km_per_km2"] = (
                f.intersection(geom).length.sum() / 1000.0 / area_km2 if area_km2 else np.nan
            )
        if poi is not None:
            row["tourism_poi_count"] = int(poi.within(geom).sum())

        rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    catchments, kind, publishable = resolve_catchments()

    print("\nland cover...")
    lc = landcover_features(catchments)
    p = out_path("landcover_by_catchment", publishable)
    lc.to_parquet(p)
    print(f"  wrote {p.relative_to(p.parents[2])}")
    print(lc[["catchment_id", "frac_bare_sparse_vegetation", "frac_built_up",
              "frac_permanent_water_bodies"]].to_string(index=False))

    print("\nsoil...")
    soil = soil_features(catchments)
    p = out_path("soil_by_catchment", publishable)
    soil.to_parquet(p)
    print(f"  wrote {p.relative_to(p.parents[2])}")
    print(soil[["catchment_id", "clay_0_5cm_mean", "sand_0_5cm_mean",
                "silt_0_5cm_mean", "soc_0_5cm_mean", "bdod_0_5cm_mean"]].to_string(index=False))

    print("\nurban / OSM...")
    urban = urban_features(catchments)
    p = out_path("urban_by_catchment", publishable)
    urban.to_parquet(p)
    print(f"  wrote {p.relative_to(p.parents[2])}")
    print(urban.to_string(index=False))

    print(f"\nall three feature tables written for {len(catchments)} catchments [{kind}]")
    if not publishable:
        print("REMINDER: these are FIXTURE numbers. Re-run once Mahdi publishes.")
