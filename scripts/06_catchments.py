"""M1 (part 3) - Real catchments and outlets from the 30 m DEM.

Consumes the ranked discharge points from 05_flow_and_streams.py, keeps the
Jordanian ones, and delineates a watershed upstream of each.

Catchment set
-------------
Wadi Yutum plus the four largest coastal wadis - five catchments, five
outlets, matching the concept doc's "three to five priority catchments".

This supersedes catchments_PROVISIONAL.gpkg on two counts:

  * that set included a 1,767 km2 endorheic basin that never reaches the sea
  * it lumped several independent coastal wadis into one 376 km2 polygon,
    because HydroBASINS resolves the Jordanian shore as a single strip

Known imbalance: Wadi Yutum is ~96% of the modelled area, so the runoff model
has only four small catchments to learn contrast from. Accepted deliberately -
Wadi Yutum is the one that actually threatens the reefs.

Outputs
    data/processed/vectors/catchments.gpkg
    data/processed/vectors/outlets.gpkg
    data/processed/features/catchment_terrain.parquet
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import whitebox
from rasterio import features
from shapely.geometry import Point, shape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hydro_common import read_dem, sea_mask  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "data/interim/hydro"
DEM = ROOT / "data/processed/dem/dem_utm36n.tif"
ADMIN = ROOT / "data/raw/admin/ne_10m_admin_0_countries.shp"
CANDIDATES = WORK / "outlet_candidates.csv"

OUT_CATCH = ROOT / "data/processed/vectors/catchments.gpkg"
OUT_OUTLET = ROOT / "data/processed/vectors/outlets.gpkg"
OUT_FEAT = ROOT / "data/processed/features/catchment_terrain.parquet"

UTM = 32636
N_CATCHMENTS = 5

# Set by eye against Esri World Imagery - see reports/outlets/README.md.
# Jordan's coast is mostly port and industrial, so for three of five catchments
# there is no natural wadi mouth to find: discharge reaches the sea through
# engineered outfalls whose position is set by drainage design, not terrain.
# The catchments and their areas are sound either way; only the mouth is
# uncertain. Keyed by rank, since IDs are assigned by area below.
POSITION_CONFIDENCE = {
    1: ("high", "engineered Wadi Yutum flood channel, mouth at the shoreline"),
    2: ("low", "routes through the container terminal and reclaimed land"),
    3: ("low", "follows a road corridor between tank farms, lands on a jetty"),
    4: ("low", "DISCHARGES INTO AN ENCLOSED HARBOUR - plume will not disperse "
               "as modelled; do not demo without stating this"),
    5: ("high", "natural braided wadi bed, mouth at the shore, reef offshore"),
}
# Natural Earth 10m coastlines are ~1 km generalised, so a discharge point on
# the real shore can sit up to ~1 km from the polygon. 3 km keeps Jordanian
# mouths while still excluding the Palestinian and Saudi coasts, which are
# 10 km+ away from any Jordanian candidate.
JORDAN_MAX_DIST_M = 3000


def classify_country(pts_utm):
    adm = gpd.read_file(ADMIN, bbox=(34.5, 29.0, 36.0, 30.5)).to_crs(UTM)
    out = []
    for p in pts_utm:
        d = adm.assign(d=adm.distance(p)).sort_values("d").iloc[0]
        out.append((d.ADMIN, float(d.d)))
    return out


def main():
    for p in (CANDIDATES, DEM, ADMIN, WORK / "d8_pointer.tif"):
        if not p.exists():
            raise SystemExit(f"missing {p} - run scripts/05_flow_and_streams.py first")

    df = pd.read_csv(CANDIDATES)
    pts = [Point(x, y) for x, y in zip(df.utm_x, df.utm_y)]
    df[["country", "dist_m"]] = classify_country(pts)

    jo = df[(df.country == "Jordan") & (df.dist_m <= JORDAN_MAX_DIST_M)]
    jo = jo.sort_values("upstream_km2", ascending=False).reset_index(drop=True)
    print(f"discharge points: {len(df)} total, {len(jo)} Jordanian "
          f"({jo.upstream_km2.sum():,.0f} km2)")

    sel = jo.head(N_CATCHMENTS).copy()
    sel["catchment_id"] = [f"AQ-C{i + 1:02d}" for i in range(len(sel))]
    sel["outlet_id"] = [f"AQ-O{i + 1:02d}" for i in range(len(sel))]
    cover = sel.upstream_km2.sum() / jo.upstream_km2.sum() * 100
    print(f"selected {len(sel)}: {sel.upstream_km2.sum():,.0f} km2 "
          f"({cover:.0f}% of the Jordanian coast drainage)\n")

    # ---- delineate ------------------------------------------------------
    pour = gpd.GeoDataFrame(
        sel[["catchment_id"]].assign(pid=range(1, len(sel) + 1)),
        geometry=[Point(x, y) for x, y in zip(sel.utm_x, sel.utm_y)],
        crs=UTM,
    )
    pour_path = WORK / "pour_points.shp"
    pour.to_file(pour_path)

    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(str(WORK))
    wbt.set_verbose_mode(False)
    ws_path = WORK / "watersheds.tif"
    ws_path.unlink(missing_ok=True)
    print("delineating watersheds ...")
    wbt.watershed(d8_pntr="d8_pointer.tif", pour_pts="pour_points.shp",
                  output="watersheds.tif")
    if not ws_path.exists():
        raise SystemExit("whitebox watershed produced no output")

    with rasterio.open(ws_path) as src:
        ws = src.read(1)
        ws_nd = src.nodata
        transform = src.transform
        cell = abs(src.transform.a)
    px = cell * cell

    # whitebox numbers watersheds by pour-point order, 1-based
    arr, valid, prof = read_dem(DEM)
    with rasterio.open(DEM) as r:
        sea = sea_mask(arr, valid, r.transform, r.crs)
    with rasterio.open(WORK / "streams.tif") as r:
        streams = r.read(1) > 0
    with rasterio.open(WORK / "d8_accum.tif") as r:
        accum = r.read(1)

    gy, gx = np.gradient(np.where(valid, arr, np.nan).astype("float64"), cell, cell)
    slope_deg = np.degrees(np.arctan(np.hypot(gx, gy)))

    geoms, feats = [], []
    for i, row in sel.iterrows():
        pid = i + 1
        m = ws == pid
        if not m.any():
            raise SystemExit(f"no watershed cells for {row.catchment_id}")
        land = m & valid & ~sea
        elev = arr[land]
        slp = slope_deg[land]
        slp = slp[np.isfinite(slp)]
        n_stream = int((m & streams).sum())
        area = m.sum() * px / 1e6

        # flow-accumulation statistics across the catchment, not just at the
        # mouth. Mean accumulation is a shape descriptor: an elongated basin
        # concentrates flow late and reads low, a compact one reads high.
        acc_in = accum[m]
        # Distance from the outlet to the furthest cell in the catchment,
        # measured through the grid rather than straight-line - it is a
        # travel-time proxy, and for a basin reaching 90 km inland the
        # difference matters.
        ry, rx = np.where(m)
        oy, ox = int(row.row), int(row.col)
        dist_cells = np.hypot(ry - oy, rx - ox)

        polys = [
            shape(g) for g, v in features.shapes(
                m.astype("uint8"), mask=m, transform=transform
            ) if v == 1
        ]
        geoms.append(max(polys, key=lambda p: p.area) if len(polys) == 1
                     else __import__("shapely.ops", fromlist=["unary_union"]).unary_union(polys))

        feats.append({
            "catchment_id": row.catchment_id,
            "outlet_id": row.outlet_id,
            "area_km2": round(area, 2),
            "elev_min_m": round(float(elev.min()), 1),
            "elev_max_m": round(float(elev.max()), 1),
            "elev_mean_m": round(float(elev.mean()), 1),
            "relief_m": round(float(elev.max() - elev.min()), 1),
            "slope_mean_deg": round(float(slp.mean()), 2),
            "slope_max_deg": round(float(slp.max()), 2),
            "stream_len_km": round(n_stream * cell / 1000, 1),
            "drainage_density_km_km2": round((n_stream * cell / 1000) / area, 3),
            "outlet_accum_cells": int(row.accum_cells),
            "accum_mean_cells": round(float(acc_in.mean()), 1),
            "accum_p95_cells": round(float(np.percentile(acc_in, 95)), 1),
            "dist_to_coast_max_km": round(float(dist_cells.max() * cell / 1000), 2),
            "dist_to_coast_mean_km": round(float(dist_cells.mean() * cell / 1000), 2),
            "elongation_ratio": round(
                float(2 * np.sqrt(area / np.pi) / (dist_cells.max() * cell / 1000)), 3),
        })

    feat = pd.DataFrame(feats)

    catch = gpd.GeoDataFrame(
        sel[["catchment_id", "outlet_id"]].assign(
            area_km2=feat.area_km2.values,
            provisional=False,
            source="Copernicus GLO-30 30 m, D8, endorheic basins preserved",
        ),
        geometry=geoms, crs=UTM,
    )

    conf = [POSITION_CONFIDENCE.get(i + 1, ("unchecked", ""))[0] for i in range(len(sel))]
    note = [POSITION_CONFIDENCE.get(i + 1, ("unchecked", ""))[1] for i in range(len(sel))]
    outl = gpd.GeoDataFrame(
        sel[["outlet_id", "catchment_id", "upstream_km2"]].assign(
            provisional=False,
            method="max flow accumulation at the sea edge",
            position_confidence=conf,
            imagery_note=note,
        ),
        geometry=[Point(x, y) for x, y in zip(sel.utm_x, sel.utm_y)], crs=UTM,
    )
    w = outl.to_crs(4326)
    outl["lon"] = w.geometry.x.round(5)
    outl["lat"] = w.geometry.y.round(5)

    OUT_FEAT.parent.mkdir(parents=True, exist_ok=True)
    catch.to_crs(4326).to_file(OUT_CATCH, driver="GPKG", layer="catchments")
    outl.to_crs(4326).to_file(OUT_OUTLET, driver="GPKG", layer="outlets")
    feat.to_parquet(OUT_FEAT, index=False)

    print(f"wrote {OUT_CATCH.relative_to(ROOT)}")
    print(f"wrote {OUT_OUTLET.relative_to(ROOT)}")
    print(f"wrote {OUT_FEAT.relative_to(ROOT)}\n")
    print(feat.to_string(index=False))
    print()
    print(outl[["outlet_id", "catchment_id", "lon", "lat", "upstream_km2"]].to_string(index=False))

    # delineated area should match the accumulation at the pour point
    print("\ncheck - delineated area vs upstream accumulation:")
    for f, (_, s) in zip(feats, sel.iterrows()):
        diff = (f["area_km2"] - s.upstream_km2) / s.upstream_km2 * 100
        flag = "" if abs(diff) < 2 else "   <-- CHECK"
        print(f"  {f['catchment_id']}  delineated {f['area_km2']:>9,.1f}  "
              f"accum {s.upstream_km2:>9,.1f}  {diff:+6.1f}%{flag}")


if __name__ == "__main__":
    main()
