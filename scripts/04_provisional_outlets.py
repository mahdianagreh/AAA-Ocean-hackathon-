"""P2 - Provisional coastal outlets for Aqaba.

Placeholder release points so Nizar's particle engine has somewhere to emit
from on Day 1. Coordinates are approximate and WILL be replaced by
DEM-derived pour points (highest flow accumulation crossing the coast).
The IDs are final; the positions are not.

Method
------
The contract suggests hand-clicking these off satellite imagery. Since the
30 m DEM is already downloaded, we can do better and stay reproducible:

  1. Sea mask from the DEM - Copernicus GLO-30 sets ocean to exactly 0.
     Shared with 05 via hydro_common, seeded from a point in open water.
  2. Take the boundary of that mask as the coastline.
  3. Intersect each terminal catchment with that coastline.
  4. Place the outlet at the midpoint of the longest coastal segment.

Midpoint is a stand-in for "where the main channel exits", which needs flow
accumulation to answer properly - that is 05's job. Good enough to build
against, not good enough to ship. It is weakest for AQ-C05, which fronts
about 15 km of coast, so its midpoint could be kilometres from the real mouth.

Only TERMINAL catchments get an outlet; the rest drain through them.

CAVEAT on `serves`: it is grouped straight from the catchment table, so
AQ-O01 currently claims AQ-C01..C04. AQ-C01 is endorheic - HydroBASINS flags
its subtree ENDO=1/2 with NEXT_SINK pointing at itself, and excludes its
1,767 km2 from the terminal basin's UP_AREA. It does not reach the sea and
should not be attributed to this outlet. Fix belongs in 02, where the
catchment set is built.

Output: data/processed/vectors/outlets_PROVISIONAL.gpkg
"""

import sys
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio import features
from shapely.geometry import shape
from shapely.ops import linemerge, unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hydro_common import read_dem, sea_mask  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEM = ROOT / "data/processed/dem/dem_utm36n.tif"
CATCH = ROOT / "data/processed/vectors/catchments_PROVISIONAL.gpkg"
OUT = ROOT / "data/processed/vectors/outlets_PROVISIONAL.gpkg"

UTM = 32636

# terminal catchment -> outlet id. Everything else drains through these.
TERMINALS = {
    "AQ-C04": "AQ-O01",   # Wadi Yutum system, head of the Gulf
    "AQ-C05": "AQ-O02",   # independent basin south of Aqaba city
}


def sea_polygon(dem_path):
    """The Gulf, as a polygon, from the shared sea mask.

    Excluding the reprojection fill is necessary but not sufficient: the Gulf
    reaches the western limit of the terrain AOI, so "largest polygon" can
    still pick up whatever else survives the threshold. hydro_common.sea_mask
    seeds from a point known to be open water instead, which is unambiguous.
    """
    with rasterio.open(dem_path) as src:
        transform, crs = src.transform, src.crs
    arr, valid, _ = read_dem(dem_path)
    mask = sea_mask(arr, valid, transform, crs).astype("uint8")

    polys = [
        shape(geom)
        for geom, val in features.shapes(mask, mask=mask.astype(bool), transform=transform)
        if val == 1
    ]
    if not polys:
        raise SystemExit("sea mask is empty - check the Gulf seed in hydro_common")
    polys.sort(key=lambda p: p.area, reverse=True)
    print(f"  Gulf: {polys[0].area / 1e6:.1f} km2"
          f"{f' (+{len(polys) - 1} detached fragments ignored)' if len(polys) > 1 else ''}")
    return polys[0], crs


def main():
    for p in (DEM, CATCH):
        if not p.exists():
            raise SystemExit(f"missing {p}")

    print("sea mask from DEM ...")
    sea, crs = sea_polygon(DEM)
    coast = sea.boundary

    catch = gpd.read_file(CATCH, layer="catchments").to_crs(UTM)

    rows = []
    for cid, oid in TERMINALS.items():
        geom = catch.loc[catch.catchment_id == cid, "geometry"]
        if geom.empty:
            raise SystemExit(f"{cid} not in {CATCH.name}")
        seg = coast.intersection(geom.iloc[0].buffer(0))
        if seg.is_empty:
            raise SystemExit(f"{cid} does not touch the coastline")

        merged = linemerge(unary_union(seg)) if seg.geom_type != "LineString" else seg
        parts = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
        parts = [p for p in parts if p.geom_type == "LineString"]
        parts.sort(key=lambda p: p.length, reverse=True)
        longest = parts[0]
        pt = longest.interpolate(0.5, normalized=True)

        rows.append({
            "outlet_id": oid,
            "terminal_catchment": cid,
            "coast_len_km": round(longest.length / 1000, 2),
            "n_segments": len(parts),
            "provisional": True,
            "method": "midpoint of longest coastal segment (DEM sea mask)",
            "geometry": pt,
        })
        print(f"  {oid}  <- {cid}   coastal segment {longest.length / 1000:.2f} km"
              f"  ({len(parts)} segment{'s' if len(parts) != 1 else ''})")

    out = gpd.GeoDataFrame(rows, geometry="geometry", crs=UTM)
    wgs = out.to_crs(4326)
    out["lon"] = wgs.geometry.x.round(5)
    out["lat"] = wgs.geometry.y.round(5)

    # which catchments drain to each outlet, for the handoff note
    served = catch.groupby("outlet_id").catchment_id.apply(lambda s: ",".join(sorted(s)))
    out["serves"] = out.outlet_id.map(served)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_crs(4326).to_file(OUT, driver="GPKG", layer="outlets")

    print(f"\nwrote {OUT.relative_to(ROOT)}")
    print(out.drop(columns="geometry").to_string(index=False))


if __name__ == "__main__":
    main()
