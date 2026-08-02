"""M3 - Validate the extracted stream network against HydroRIVERS.

Nothing independent has checked the inland channel network. The imagery check
in 07 only looked at the two coastal mouths; a trunk misrouted 40 km upstream
would not have shown up there.

HydroRIVERS is a published, hydrologically-conditioned river network from the
HydroSHEDS family.

The two sources are independent acquisitions, which is what gives this test
its force: HydroSHEDS derives from SRTM (2000 shuttle radar), while
Copernicus GLO-30 derives from TanDEM-X (2011-2015). Different satellites,
different instruments, a decade apart.

The one real limit is resolution: ~500 m against our 30 m, so an offset of a
few hundred metres is expected and means nothing, and the reference cannot
confirm channel position at anything finer. MERIT Hydro at 90 m would fix
that and needs an authenticated Earth Engine project.

Comparison is restricted to reaches HydroRIVERS actually maps: its smallest
reaches carry ~10 km2 upstream, so our sub-10 km2 channels have nothing to be
compared against and are excluded rather than counted as mismatches.

Outputs
    reports/streams/README.md
    reports/streams/stream_offsets.csv
    reports/streams/AQ-C01_overlay.jpg
"""

import glob
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from PIL import Image, ImageDraw
from shapely.geometry import Point
from shapely.strtree import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "data/interim/hydro"
CATCH = ROOT / "data/processed/vectors/catchments.gpkg"
OUTDIR = ROOT / "reports/streams"

UTM = 32636
# HydroRIVERS' smallest mapped reaches carry about this much upstream area.
# Comparing our finer channels against a network that never drew them would
# manufacture mismatches.
MIN_UPLAND_KM2 = 10.0
CELL_AREA_KM2 = 900 / 1e6


def find_hydrorivers():
    hits = glob.glob(str(ROOT / "data/raw/hydro/**/HydroRIVERS_v10_eu.shp"), recursive=True)
    if not hits:
        raise SystemExit("HydroRIVERS not found under data/raw/hydro/")
    return hits[0]


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)

    with rasterio.open(WORK / "streams.tif") as s:
        streams = s.read(1) > 0
        transform, crs = s.transform, s.crs
    with rasterio.open(WORK / "d8_accum.tif") as a:
        accum = a.read(1)

    min_cells = int(MIN_UPLAND_KM2 / CELL_AREA_KM2)
    trunk = streams & (accum >= min_cells)
    rr, cc = np.where(trunk)
    print(f"our network: {streams.sum():,} stream cells, "
          f"{trunk.sum():,} carrying >= {MIN_UPLAND_KM2:g} km2")

    xs, ys = rasterio.transform.xy(transform, rr, cc)
    pts = [Point(x, y) for x, y in zip(xs, ys)]

    riv = gpd.read_file(find_hydrorivers(), bbox=(34.75, 29.15, 35.94, 30.30)).to_crs(UTM)
    riv = riv[riv.UPLAND_SKM >= MIN_UPLAND_KM2]
    print(f"HydroRIVERS: {len(riv)} reaches >= {MIN_UPLAND_KM2:g} km2 upstream")

    tree = STRtree(riv.geometry.values)
    idx = tree.nearest(pts)
    dist = np.array([p.distance(riv.geometry.values[i]) for p, i in zip(pts, idx)])

    q = np.percentile(dist, [50, 75, 90, 95, 99])
    print("\noffset from the nearest HydroRIVERS reach:")
    for lab, v in zip(["median", "p75", "p90", "p95", "p99"], q):
        print(f"  {lab:>6}  {v:7.0f} m")
    for thr in (90, 250, 500, 1000):
        print(f"  within {thr:>4} m: {(dist <= thr).mean() * 100:5.1f}%")

    pd.DataFrame({
        "row": rr, "col": cc,
        "accum_cells": accum[rr, cc],
        "upstream_km2": (accum[rr, cc] * CELL_AREA_KM2).round(2),
        "offset_m": dist.round(1),
    }).to_csv(OUTDIR / "stream_offsets.csv", index=False)

    # ---- upstream area at the Wadi Yutum mouth --------------------------
    outl = gpd.read_file(ROOT / "data/processed/vectors/outlets.gpkg",
                         layer="outlets").to_crs(UTM)
    o1 = outl[outl.outlet_id == "AQ-O01"].geometry.iloc[0]
    near = riv.assign(d=riv.distance(o1)).sort_values("d").head(3)
    print("\nupstream area at the Wadi Yutum mouth:")
    print(f"  our DEM                {4453.1:>8,.1f} km2")
    for _, r in near.iterrows():
        print(f"  HydroRIVERS reach      {r.UPLAND_SKM:>8,.1f} km2   "
              f"({r.d:,.0f} m from AQ-O01, order {r.ORD_STRA})")
    print(f"  HydroBASINS exorheic   {4690.0:>8,.1f} km2")

    # ---- overlay for AQ-C01 ---------------------------------------------
    catch = gpd.read_file(CATCH, layer="catchments").to_crs(UTM)
    c1 = catch[catch.catchment_id == "AQ-C01"].geometry.iloc[0]
    minx, miny, maxx, maxy = c1.bounds
    W = 1100
    scale = W / (maxx - minx)
    H = int((maxy - miny) * scale)
    img = Image.new("RGB", (W, H), (16, 20, 24))
    d = ImageDraw.Draw(img)

    def px(x, y):
        return (x - minx) * scale, (maxy - y) * scale

    d.polygon([px(x, y) for x, y in c1.exterior.coords], outline=(90, 110, 125), width=2)

    inside = [(x, y, a) for x, y, a in zip(xs, ys, accum[rr, cc])
              if minx <= x <= maxx and miny <= y <= maxy]
    for x, y, a in inside:
        X, Y = px(x, y)
        d.ellipse([X - 1, Y - 1, X + 1, Y + 1], fill=(0, 190, 255))

    for geom in riv.geometry:
        if geom.intersects(c1):
            for line in (geom.geoms if geom.geom_type == "MultiLineString" else [geom]):
                pts_ = [px(x, y) for x, y in line.coords]
                if len(pts_) > 1:
                    d.line(pts_, fill=(255, 170, 40), width=2)

    d.text((14, 14), "AQ-C01 Wadi Yutum", fill=(240, 240, 240))
    d.text((14, 32), "cyan = our 30 m network   orange = HydroRIVERS ~500 m",
           fill=(190, 190, 190))
    bar = int(10000 * scale)
    d.rectangle([14, H - 30, 14 + bar, H - 26], fill=(255, 255, 255))
    d.text((14, H - 48), "10 km", fill=(255, 255, 255))
    img.save(OUTDIR / "AQ-C01_overlay.jpg", quality=88, optimize=True)
    print(f"\nwrote {(OUTDIR / 'AQ-C01_overlay.jpg').relative_to(ROOT)}")
    print(f"wrote {(OUTDIR / 'stream_offsets.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
