"""Merge the real DEM (land) and real bathymetry (sea) into one continuous
elevation surface, for the 3D Journey's terrain mesh (feature 14).

Two real rasters, two real resolutions, one seam: the coastline. Bathymetry
(`depth_utm36n.tif`, 50 m, MARINE_AOI) already carries real negative-down sea
depth; the DEM (`dem_utm36n.tif`, 30 m, TERRAIN_AOI, from `03_dem_fetch.py`)
carries real land elevation over a much larger area. Neither should be trusted
for the other's domain: GLO-30 is a *surface* model (buildings/embankments
baked into the value) and encodes open sea as noisy near-zero, not a clean
bathymetric depth; the bathymetry product has no land value worth using once
you are more than a few cells from the coast, and does not cover the far
inland catchment at all.

The real coastline polygon (`coastline.gpkg` layer `water`) decides which
raster wins per cell -- not a value threshold (e.g. "elevation <= 0"), which
is exactly the GLO-30 sea-as-0.0 gotcha `03_dem_fetch.py`'s own docstring
warns about repeating.

Output: data/processed/dem/terrain_merged_utm36n.tif, on the DEM's own 30 m
grid (the DEM's extent is the larger of the two and this feature needs the
inland catchment/wadi corridor, not just the coastal strip bathymetry alone
covers).
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import reproject

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "src"))
from config import spatial as _spatial  # noqa: E402

DEM_PATH = ROOT / "data/processed/dem/dem_utm36n.tif"
BATHY_PATH = ROOT / "data/processed/bathymetry/depth_utm36n.tif"
COASTLINE_PATH = ROOT / "data/processed/vectors/coastline.gpkg"
OUT_PATH = ROOT / "data/processed/dem/terrain_merged_utm36n.tif"

NODATA = -9999.0


def main() -> int:
    if not DEM_PATH.exists():
        print(f"SKIPPED — {DEM_PATH} not present. Run scripts/03_dem_fetch.py first.")
        return 1
    if not BATHY_PATH.exists():
        print(f"SKIPPED — {BATHY_PATH} not present.")
        return 1

    with rasterio.open(DEM_PATH) as dem_src:
        dem = dem_src.read(1)
        dem_transform = dem_src.transform
        dem_crs = dem_src.crs
        dem_shape = dem_src.shape
        dem_nodata = dem_src.nodata

    print(f"DEM: {dem_shape[1]}x{dem_shape[0]} px, {dem_crs}, "
          f"real elevation range {dem[dem != dem_nodata].min():.0f}..{dem[dem != dem_nodata].max():.0f} m")

    # Resample bathymetry onto the DEM's exact grid — bilinear, since depth is
    # a smooth continuous field, not a categorical one.
    with rasterio.open(BATHY_PATH) as bathy_src:
        bathy_resampled = np.full(dem_shape, np.nan, dtype=np.float64)
        reproject(
            source=rasterio.band(bathy_src, 1),
            destination=bathy_resampled,
            src_transform=bathy_src.transform, src_crs=bathy_src.crs,
            src_nodata=bathy_src.nodata,
            dst_transform=dem_transform, dst_crs=dem_crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
    valid_bathy = ~np.isnan(bathy_resampled)
    print(f"Bathymetry resampled onto DEM grid: {valid_bathy.sum():,} valid cells "
          f"of {dem.size:,} ({100 * valid_bathy.sum() / dem.size:.1f}%)")

    # The real coastline water polygon decides the seam — not a value threshold.
    water = gpd.read_file(COASTLINE_PATH, layer="water").to_crs(dem_crs)
    water_mask = rasterize(
        [(geom, 1) for geom in water.geometry if geom is not None and not geom.is_empty],
        out_shape=dem_shape, transform=dem_transform, fill=0, dtype=np.uint8,
    ).astype(bool)
    print(f"Coastline water mask: {water_mask.sum():,} cells "
          f"({100 * water_mask.sum() / dem.size:.1f}% of the DEM's full TERRAIN_AOI extent)")

    dem_valid = dem != dem_nodata
    merged = np.where(dem_valid, dem, NODATA).astype(np.float64)

    # Sea cells: prefer real bathymetry; if the water mask says "sea" but
    # bathymetry has no coverage there (outside MARINE_AOI's own smaller
    # extent), fall back to the DEM's own value rather than fabricating a
    # depth — an honest gap, not an invented one.
    use_bathy = water_mask & valid_bathy
    merged = np.where(use_bathy, bathy_resampled, merged)

    still_gap = water_mask & ~valid_bathy & ~dem_valid
    if still_gap.any():
        print(f"NOTE: {still_gap.sum():,} sea cells have neither real bathymetry nor a "
              f"real DEM value — left as nodata, not filled with an assumed depth.")

    meta = dict(
        driver="GTiff", height=dem_shape[0], width=dem_shape[1],
        count=1, dtype="float64", crs=dem_crs, transform=dem_transform,
        nodata=NODATA, compress="deflate", tiled=True,
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(OUT_PATH, "w", **meta) as dst:
        dst.write(merged, 1)

    valid = merged != NODATA
    print(f"\nWrote {OUT_PATH.relative_to(ROOT)}")
    print(f"  merged elevation range: {merged[valid].min():.0f} .. {merged[valid].max():.0f} m "
          f"({valid.sum():,} valid cells of {merged.size:,})")
    print(f"  measure CRS: {_spatial.CRS_MEASURE} (unchanged — already the DEM's own CRS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
