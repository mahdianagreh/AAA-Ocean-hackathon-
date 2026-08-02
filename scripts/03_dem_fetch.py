"""M1 - Fetch Copernicus DEM GLO-30, mosaic, clip to terrain AOI, reproject.

Source: Copernicus DEM GLO-30 via the AWS Open Data mirror (public, no auth).
https://registry.opendata.aws/copernicus-dem/

GLO-30 is a SURFACE model - buildings and embankments are in the elevation
values. That matters most near the coast, where the outlets are and where
Aqaba is densest. Expect to hand-correct the last stretch of each channel.

Outputs
-------
  data/raw/dem/<tile>.tif            the four source tiles
  data/raw/dem/cop_glo30_aqaba.tif   mosaic clipped to terrain AOI (EPSG:4326)
  data/processed/dem/dem_utm36n.tif  reprojected to EPSG:32636 at 30 m
"""

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import Resampling, calculate_default_transform, reproject
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/dem"
OUT_MOSAIC = RAW / "cop_glo30_aqaba.tif"
OUT_UTM = ROOT / "data/processed/dem/dem_utm36n.tif"
AOI = ROOT / "data/aoi/terrain_aoi.geojson"

BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
TILES = [
    ("N29", "E034"), ("N29", "E035"),
    ("N30", "E034"), ("N30", "E035"),
]
UTM = "EPSG:32636"
TARGET_RES = 30.0

# Must be set, and must not be 0. Copernicus GLO-30 encodes the sea surface as
# exactly 0.0, so leaving nodata unset makes reprojection fill indistinguishable
# from the Gulf: the tilted data quadrilateral leaves 0-filled wedges in the
# corners of the UTM bounding box, and any "cells <= 0" sea mask then merges the
# real coastline with the raster frame into one 1,080 km2 blob.
NODATA = -9999.0

# DEFLATE only. PREDICTOR=3 (floating-point predictor) is rejected outright by
# the WhiteboxTools GeoTIFF reader, which every downstream hydrology step uses.
CREATE_OPTS = dict(compress="deflate", tiled=True, nodata=NODATA)


def tile_name(lat, lon):
    return f"Copernicus_DSM_COG_10_{lat}_00_{lon}_00_DEM"


def download(lat, lon):
    import urllib.request

    name = tile_name(lat, lon)
    dst = RAW / f"{name}.tif"
    if dst.exists() and dst.stat().st_size > 1_000_000:
        print(f"  have  {name}")
        return dst
    url = f"{BASE}/{name}/{name}.tif"
    print(f"  get   {name} ...", flush=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dst)
    print(f"        {dst.stat().st_size / 1048576:.1f} MB")
    return dst


def main():
    bbox = json.loads(AOI.read_text())["features"][0]["properties"]["bbox"]
    w, s, e, n = bbox
    print(f"terrain AOI: {bbox}\n")

    print("tiles:")
    paths = [download(lat, lon) for lat, lon in TILES]

    print("\nmosaic + clip ...")
    srcs = [rasterio.open(p) for p in paths]
    res = srcs[0].res
    print(f"  source res (deg): {res[0]:.8f} x {res[1]:.8f}")
    mosaic, transform = merge(srcs, bounds=(w, s, e, n), nodata=NODATA)
    meta = srcs[0].meta.copy()
    for src in srcs:
        src.close()

    meta.update(
        driver="GTiff", height=mosaic.shape[1], width=mosaic.shape[2],
        transform=transform, **CREATE_OPTS,
    )
    with rasterio.open(OUT_MOSAIC, "w", **meta) as dst:
        dst.write(mosaic)
    print(f"  wrote {OUT_MOSAIC.relative_to(ROOT)}  {mosaic.shape[2]} x {mosaic.shape[1]} px")

    print("\nreproject to UTM 36N @ 30 m ...")
    with rasterio.open(OUT_MOSAIC) as src:
        dst_transform, dst_w, dst_h = calculate_default_transform(
            src.crs, UTM, src.width, src.height, *src.bounds, resolution=TARGET_RES
        )
        kw = src.meta.copy()
        kw.update(crs=UTM, transform=dst_transform, width=dst_w, height=dst_h,
                  **CREATE_OPTS)
        OUT_UTM.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(OUT_UTM, "w", **kw) as dst:
            reproject(
                source=rasterio.band(src, 1), destination=rasterio.band(dst, 1),
                src_transform=src.transform, src_crs=src.crs,
                src_nodata=NODATA, dst_nodata=NODATA,
                dst_transform=dst_transform, dst_crs=UTM,
                resampling=Resampling.bilinear,
            )
    print(f"  wrote {OUT_UTM.relative_to(ROOT)}  {dst_w} x {dst_h} px")

    with rasterio.open(OUT_UTM) as src:
        a = src.read(1, masked=True)
        print(f"\nelevation  min {a.min():.0f} m   max {a.max():.0f} m   mean {a.mean():.0f} m")
        print(f"nodata: {src.nodata}   valid cells: {(~a.mask).sum() if np.ma.is_masked(a) else a.size:,}")
        print(f"bounds (UTM36N): {[round(v) for v in src.bounds]}")


if __name__ == "__main__":
    main()
