"""Bake the merged terrain surface into Terrain-RGB tiles for MapLibre's
`raster-dem` source and `setTerrain()`, per the team's 3D Journey plan
(`mahdi-3D-implementation-plan.md` §1, §3.1) -- real continuous terrain,
not the fill-extrusion banded blocks the first pass of feature 14 used.

Standard Mapbox Terrain-RGB encoding (`rio_rgbify.encoders.data_to_rgb`,
base=-10000, interval=0.1 -- exactly what MapLibre's raster-dem source calls
the `"mapbox"` encoding), as loose PNG files rather than `.mbtiles`: this
project's offline pack is fully static files (same reasoning as every other
`frontend/public/*` asset), and `.mbtiles` needs a tile-serving process this
repo does not have and DoD item 9 ("works with wifi off") gives no reason to
add.

Run once, offline-capable forever after -- same pattern as
`fetch_basemap_raster.py`:
    ../.venv/bin/python scripts/tile_terrain_rgb.py

Output (git-ignored, regenerate rather than commit -- see .gitignore):
    frontend/public/terrain/{z}/{x}/{y}.png
"""

from __future__ import annotations

from pathlib import Path

import mercantile
import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject, transform_bounds
from rio_rgbify.encoders import data_to_rgb

ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = ROOT / "data/processed/dem/terrain_merged_utm36n.tif"
OUT_DIR = ROOT / "frontend/public/terrain"

#: Covers the camera range this scene actually uses (initial overview ~z9.6 down
#: to close outlet/building views ~z15) without generating tiles finer than the
#: source data (30 m DEM / merged bathymetry) can honestly support -- MapLibre
#: reuses the nearest coarser tile when a closer zoom isn't baked, which is
#: honest (visibly softer, not a fabricated extra level of detail) rather than
#: silently upsampling past what the real data resolves.
MIN_Z = 7
MAX_Z = 12
TILE_SIZE = 256
BASEVAL = -10000.0
INTERVAL = 0.1


def main() -> int:
    if not SRC_PATH.exists():
        print(f"SKIPPED — {SRC_PATH} not present. Run scripts/merge_terrain_bathymetry.py first.")
        return 1

    with rasterio.open(SRC_PATH) as src:
        west, south, east, north = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
        src_data = src.read(1)
        src_transform = src.transform
        src_crs = src.crs
        src_nodata = src.nodata

    print(f"source bounds (WGS84): {west:.4f}, {south:.4f}, {east:.4f}, {north:.4f}")
    tiles = list(mercantile.tiles(west, south, east, north, range(MIN_Z, MAX_Z + 1)))
    print(f"{len(tiles)} candidate tiles across zoom {MIN_Z}-{MAX_Z}")

    written = 0
    skipped_empty = 0
    filled_gap_tiles = 0
    for tile in tiles:
        bounds = mercantile.xy_bounds(tile)
        dst_transform = from_bounds(bounds.left, bounds.bottom, bounds.right, bounds.top, TILE_SIZE, TILE_SIZE)
        dest = np.full((TILE_SIZE, TILE_SIZE), np.nan, dtype=np.float64)
        reproject(
            source=src_data, destination=dest,
            src_transform=src_transform, src_crs=src_crs, src_nodata=src_nodata,
            dst_transform=dst_transform, dst_crs="EPSG:3857", dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
        valid = ~np.isnan(dest)
        if not valid.any():
            skipped_empty += 1
            continue  # entirely outside real data -- no fabricated tile written

        if not valid.all():
            # A small edge-of-real-data gap within an otherwise-real tile (see
            # merge_terrain_bathymetry.py's own "still_gap" report) -- nearest-valid
            # fill so the mesh has no literal hole/cliff-to-infinity at the AOI
            # boundary. A rendering smoothing of a disclosed gap, never a claimed
            # measurement.
            from scipy.ndimage import distance_transform_edt
            idx = distance_transform_edt(~valid, return_distances=False, return_indices=True)
            dest = dest[tuple(idx)]
            filled_gap_tiles += 1

        rgb = data_to_rgb(dest, BASEVAL, INTERVAL)
        out_path = OUT_DIR / str(tile.z) / str(tile.x) / f"{tile.y}.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(np.moveaxis(rgb, 0, -1), mode="RGB").save(out_path)
        written += 1

    total_bytes = sum(f.stat().st_size for f in OUT_DIR.rglob("*.png")) if OUT_DIR.exists() else 0
    print(f"\nwrote {written} tiles ({filled_gap_tiles} with a small edge-of-data gap filled, "
          f"{skipped_empty} skipped as entirely outside real data)")
    print(f"total size: {total_bytes / 1024:.1f} KB")
    print(f"encoding: mapbox (base={BASEVAL}, interval={INTERVAL}) — set this exact pair "
          f"in the MapLibre raster-dem source config")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
