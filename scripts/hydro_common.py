"""Shared hydrology helpers.

Exists because two scripts independently defined "the sea" and disagreed:
one thresholded at 0.0 m and took the largest polygon, the other thresholded
at 1.5 m and flood-filled from the southern raster edge. Both were wrong, for
the same reason - see sea_mask below.
"""

import collections

import numpy as np
import rasterio
from pyproj import Transformer

# Copernicus GLO-30 encodes the sea surface as exactly 0.0. Verified on the
# Aqaba mosaic: 1,362,695 cells at exactly 0.0, only 360 cells below it, and
# those are bilinear-resampling artifacts along the water/land edge.
SEA_LEVEL = 0.0

# A point in open water in the head of the Gulf, west of Aqaba's port.
# Seeding from a known sea location is what stops the mask from latching onto
# the raster frame or an inland sabkha. Lon/lat, EPSG:4326.
GULF_SEED_LONLAT = (34.94, 29.47)


def read_dem(path):
    """Return (elevation, valid_mask, profile). Valid excludes nodata."""
    with rasterio.open(path) as src:
        arr = src.read(1)
        prof = src.profile.copy()
        nd = src.nodata
    if nd is None:
        raise SystemExit(
            f"{path} has no nodata value set.\n"
            "Reprojection fill is written as 0, which is also sea level, so the "
            "sea mask cannot tell the Gulf from the raster frame.\n"
            "Re-run scripts/03_dem_fetch.py - it now sets nodata=-9999."
        )
    valid = arr != nd
    return arr, valid, prof


def sea_mask(arr, valid, transform, crs, seed_lonlat=GULF_SEED_LONLAT):
    """Connected body of sea-level water containing a known Gulf point.

    Three failure modes this avoids, all of which bit earlier versions:

    1. Thresholding alone flags inland sabkha and quarry floors as sea.
    2. Taking the largest polygon returns the reprojection nodata frame, which
       at 1,080 km2 dwarfs the Gulf inside this AOI - and worse, the Gulf
       touches the raster's western edge, so the two merge into one blob.
    3. Seeding from a raster edge lands in that same frame.

    Requiring connection to a point known to be open water fixes all three,
    and `valid` keeps nodata out of the flood fill entirely.
    """
    water = (arr <= SEA_LEVEL) & valid

    tf = Transformer.from_crs(4326, crs, always_xy=True)
    x, y = tf.transform(*seed_lonlat)
    inv = ~transform
    col, row = (int(v) for v in inv * (x, y))

    h, w = arr.shape
    if not (0 <= row < h and 0 <= col < w):
        raise SystemExit(f"Gulf seed {seed_lonlat} falls outside the raster")
    if not water[row, col]:
        raise SystemExit(
            f"Gulf seed {seed_lonlat} is not water in this DEM "
            f"(elevation {arr[row, col]:.2f} m). Move the seed into open water."
        )

    mask = np.zeros_like(water, dtype=bool)
    mask[row, col] = True
    q = collections.deque([(row, col)])
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w and water[rr, cc] and not mask[rr, cc]:
                mask[rr, cc] = True
                q.append((rr, cc))
    return mask
