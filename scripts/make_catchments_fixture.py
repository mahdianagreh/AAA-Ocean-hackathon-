"""Local TEST FIXTURE standing in for Mahdi's catchments. NOT a deliverable.

Writes data/interim/catchments_FIXTURE_local_test_only.gpkg

WHY THIS IS NOT `catchments_PROVISIONAL.gpkg`
---------------------------------------------
Contract §4 P1 assigns provisional catchments to Mahdi, from HydroBASINS. That
ownership matters: if two people publish catchment sets with the same AQ-C{NN}
IDs and different geometry, every downstream join silently mixes them and the
contract's whole purpose is defeated.

So this file deliberately:
  * lives in data/interim/, never data/processed/vectors/
  * carries FIXTURE in the filename, so the Day-12 `grep PROVISIONAL` gate is
    not the only thing standing between it and the demo
  * exists only so the aggregation pipeline can be run and verified today
    instead of sitting untested until Mahdi's polygons land

aggregate_catchments.py refuses to write to the contract feature paths when it is
running on this file. Delete it once real catchments exist.

The geometry is crude on purpose: five latitude bands over the land strip inland
of the coast. It is not a watershed delineation and must never be shown to
anyone as one.
"""

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.features
from shapely.geometry import box as shp_box
from shapely.geometry import shape
from shapely.ops import unary_union

from config import AOI_CRS_STORAGE, CATCHMENT_ID_FMT, INTERIM, PROCESSED

OUT = INTERIM / "catchments_FIXTURE_local_test_only.gpkg"
DEPTH = PROCESSED / "bathymetry" / "depth_utm36n.tif"
N_CATCHMENTS = 5

# Land strip inland of the Jordanian coast, in UTM 36N. Bounded east so the
# fixture stays near the coast rather than covering the whole desert.
EAST_LIMIT = 706000.0


def land_polygon():
    """Land = elevation above sea level, from the same grid as everything else."""
    with rasterio.open(DEPTH) as src:
        elev = src.read(1)
        land = ((elev > 0) & (elev != src.nodata)).astype("uint8")
        polys = [
            shape(geom)
            for geom, val in rasterio.features.shapes(
                land, mask=land.astype(bool), transform=src.transform
            )
            if val == 1
        ]
        crs = src.crs
    biggest = max(polys, key=lambda p: p.area)  # the mainland, not sand specks
    return biggest, crs


def build():
    land, crs = land_polygon()
    minx, miny, maxx, maxy = land.bounds
    maxx = min(maxx, EAST_LIMIT)

    edges = np.linspace(miny, maxy, N_CATCHMENTS + 1)
    rows = []
    for i in range(N_CATCHMENTS):
        band = shp_box(minx, edges[i], maxx, edges[i + 1])
        geom = land.intersection(band)
        if geom.is_empty:
            continue
        if geom.geom_type == "MultiPolygon":
            geom = unary_union([g for g in geom.geoms if g.area > 1e5])
        rows.append(
            {
                # Contract §2 ID format, so the join key is realistic even though
                # the geometry is not.
                "catchment_id": CATCHMENT_ID_FMT.format(i + 1),
                "id": CATCHMENT_ID_FMT.format(i + 1),
                "name": f"FIXTURE band {i + 1}",
                "is_fixture": True,
                "geometry": geom,
            }
        )

    gdf = gpd.GeoDataFrame(rows, crs=crs)
    gdf["area_km2"] = gdf.geometry.area / 1e6
    return gdf.to_crs(AOI_CRS_STORAGE)


if __name__ == "__main__":
    gdf = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUT, driver="GPKG", layer="catchments")
    print(f"wrote {OUT}")
    print("  THIS IS A TEST FIXTURE, NOT MAHDI'S DELIVERABLE — do not publish it")
    print(gdf[["catchment_id", "name", "area_km2"]].to_string(index=False))
