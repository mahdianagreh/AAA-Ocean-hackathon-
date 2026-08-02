"""ESA WorldCover 10 m -> mosaicked, clipped raster + class composition + asserts.

Produces:
    data/interim/worldcover_terrain_v2_clip.tif   (mosaic of every tile TERRAIN_AOI needs)

Figures live in qa_land.py. This script ASSERTS; qa_land VISUALISES. Keeping one
owner per figure stops two scripts drifting into two pictures of the same claim.

v2, 2 August 2026 — WHY THIS WAS REBUILT
----------------------------------------
The v1 clip used the retired box described in backend/src/config/spatial.py and
covered only ~11.5% of TERRAIN_AOI. Wadi Yutum drains from ~90 km inland, so that
box cut off most of AQ-C01 — the catchment that is 4,453 of the basin's 4,656 km².
Nothing raised: the download succeeded, it just covered the wrong ground. See
docs/aoi_coverage_report_20260802.txt for the measured gap.

The retired coordinates are deliberately NOT repeated here — see the note in
download_soilgrids.py, and tests/test_spatial_contract.py, which enforces it.

TERRAIN_AOI crosses the N27/N30 tile boundary, so this needs TWO tiles. The
required tiles are DERIVED from the AOI rather than hardcoded — a hardcoded tile
list is exactly how v1's northern edge went missing, and a future AOI change would
repeat it silently.

MOSAIC BEFORE CLIP, never clip-then-merge: merging two independently clipped
arrays leaves a seam wherever the clip boundaries disagree by a fraction of a
pixel. `merge(..., bounds=)` does both in one pass and reads only the window it
needs, which matters because each source tile is 36000x36000.

CLASS CODES ARE NOT SEQUENTIAL (10,20,...,95,100). They come from config so the
mapping is stated once. Getting it wrong is the highest-impact silent error here:
the runoff model would train on the wrong class and nothing would crash.
"""

import math

import numpy as np
import rasterio
import rasterio.merge
import matplotlib.colors as mcolors  # colour table for the GeoTIFF palette only

from config import INTERIM, LAND_BBOX, RAW, WORLDCOVER_CLASSES

TILE_DIR = RAW / "worldcover"
CLIP = INTERIM / "worldcover_terrain_v2_clip.tif"
TILE_SPAN_DEG = 3  # ESA ships 3x3 degree tiles named by their lower-left corner

# Rough visual palette, close to ESA's own legend so QA plots are comparable
# against the official viewer.
CLASS_COLORS = {
    10: "#006400", 20: "#ffbb22", 30: "#ffff4c", 40: "#f096ff", 50: "#fa0000",
    60: "#b4b4b4", 70: "#f0f0f0", 80: "#0064c8", 90: "#0096a0", 95: "#00cf75",
    100: "#fae6a0",
}


def required_tiles(bbox=LAND_BBOX):
    """Tile IDs whose 3x3 degree footprints intersect the AOI.

    Derived, not hardcoded. floor(x / 3) * 3 snaps a coordinate down to its tile
    origin; stepping by 3 up to the max covers every band the AOI touches.
    """
    minx, miny, maxx, maxy = bbox
    lon0 = math.floor(minx / TILE_SPAN_DEG) * TILE_SPAN_DEG
    lat0 = math.floor(miny / TILE_SPAN_DEG) * TILE_SPAN_DEG

    names = []
    lat = lat0
    while lat < maxy:
        lon = lon0
        while lon < maxx:
            ns = f"N{lat:02d}" if lat >= 0 else f"S{abs(lat):02d}"
            ew = f"E{lon:03d}" if lon >= 0 else f"W{abs(lon):03d}"
            names.append(f"ESA_WorldCover_10m_2021_v200_{ns}{ew}_Map.tif")
            lon += TILE_SPAN_DEG
        lat += TILE_SPAN_DEG
    return names


def seam_latitudes(bbox=LAND_BBOX):
    """Interior tile boundaries the AOI crosses — where a seam could appear."""
    _, miny, _, maxy = bbox
    lat = math.floor(miny / TILE_SPAN_DEG) * TILE_SPAN_DEG + TILE_SPAN_DEG
    out = []
    while lat < maxy:
        out.append(float(lat))
        lat += TILE_SPAN_DEG
    return out


def mosaic_and_clip():
    tiles = required_tiles()
    print(f"  TERRAIN_AOI needs {len(tiles)} tile(s): "
          f"{', '.join(t.split('_v200_')[1].split('_Map')[0] for t in tiles)}")

    missing = [t for t in tiles if not (TILE_DIR / t).exists()]
    assert not missing, (
        f"missing WorldCover tile(s): {missing}\n"
        "Fetch from https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/<tile>"
    )

    srcs = [rasterio.open(TILE_DIR / t) for t in tiles]
    try:
        # bounds= makes this a mosaic AND a clip in one windowed pass.
        mosaic, transform = rasterio.merge.merge(srcs, bounds=LAND_BBOX)
        meta = srcs[0].meta.copy()
    finally:
        for s in srcs:
            s.close()

    data = mosaic[0]
    meta.update(height=data.shape[0], width=data.shape[1], transform=transform,
                compress="deflate", count=1)

    CLIP.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(CLIP, "w", **meta) as dst:
        dst.write(data, 1)
        # Colour table so the file renders sensibly in QGIS. The band still holds
        # raw class codes — that is what zonal statistics read.
        dst.write_colormap(1, {code: tuple(int(255 * v) for v in mcolors.to_rgb(hexc)) + (255,)
                               for code, hexc in CLASS_COLORS.items()})

    with rasterio.open(CLIP) as chk:
        b = chk.bounds
    minx, miny, maxx, maxy = LAND_BBOX
    tol = 1e-6
    assert (b.left <= minx + tol and b.bottom <= miny + tol
            and b.right >= maxx - tol and b.top >= maxy - tol), (
        f"clip {tuple(round(x, 4) for x in b)} does not cover TERRAIN_AOI {LAND_BBOX}"
    )

    print(f"  wrote {CLIP.name}  {data.shape[1]}x{data.shape[0]} @ 10 m")
    print(f"  bounds {tuple(round(x, 4) for x in b)} covers TERRAIN_AOI")
    return data


def composition(data):
    """Class composition over the whole AOI and over land only."""
    codes, counts = np.unique(data, return_counts=True)
    total = counts.sum()

    unknown = [int(c) for c in codes if c not in WORLDCOVER_CLASSES and c != 0]
    assert not unknown, f"codes absent from WORLDCOVER_CLASSES: {unknown}"

    # The ~74% bare-ground expectation in the concept doc describes LAND. The AOI
    # includes sea, so an AOI-wide bare fraction is diluted and is not the number
    # to sanity-check against.
    water_px = counts[codes == 80].sum() if 80 in codes else 0
    nodata_px = counts[codes == 0].sum() if 0 in codes else 0
    land_total = total - water_px - nodata_px

    print(f"\n  {'class':<26}{'AOI %':>9}{'land %':>9}")
    rows = {}
    for code, count in zip(codes, counts):
        if code == 0:
            continue
        name = WORLDCOVER_CLASSES[int(code)]
        aoi_frac = count / total
        land_frac = np.nan if code == 80 else count / land_total
        rows[name] = (aoi_frac, land_frac)
        land_s = "  (sea)" if code == 80 else f"{land_frac * 100:8.2f}"
        print(f"  {name:<26}{aoi_frac * 100:8.2f} {land_s:>9}")

    return rows, land_total


def sanity_check(rows):
    """The mandatory bare-ground check. A wrong class mapping is silent otherwise."""
    bare_land = rows.get("bare_sparse_vegetation", (np.nan, np.nan))[1]
    print(f"\n  bare/sparse vegetation as a fraction of LAND: {bare_land:.3f}")
    assert bare_land > 0.5, (
        f"bare-ground fraction of land is {bare_land:.3f}, expected well above 0.5 for a "
        "hyper-arid catchment (~0.74 in the concept doc). Re-check WORLDCOVER_CLASSES "
        "against the official ESA legend BEFORE aggregating — a wrong mapping here "
        "silently poisons the runoff model."
    )
    print("  OK bare ground dominates the land surface, consistent with hyper-arid Aqaba")


if __name__ == "__main__":
    print(f"WorldCover v2 — TERRAIN_AOI {LAND_BBOX}")
    data = mosaic_and_clip()
    rows, land_total = composition(data)
    sanity_check(rows)
    print(f"\nland area in AOI: {land_total * 100 / 1e6:,.0f} km2 "
          f"({land_total / data.size * 100:.1f}% of AOI)")
    print(f"seam latitude(s) to check visually: {seam_latitudes()}")
