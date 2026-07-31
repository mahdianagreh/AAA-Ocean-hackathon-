"""ESA WorldCover 10 m -> clipped raster + class composition + sanity assert.

Produces:
    data/interim/worldcover_aqaba_clip.tif

Figures live in qa_land.py. This script ASSERTS; qa_land VISUALISES. Keeping one
owner for each figure avoids two scripts drifting into two different pictures of
the same claim.

The per-catchment fractions live in aggregate_catchments.py, because they need
Mahdi's catchment polygons. Everything here needs only the AOI box.

CLASS CODES ARE NOT SEQUENTIAL (10,20,...,95,100). They come from config so the
mapping is stated once. Getting this wrong is the single highest-impact silent
error in this workstream: the runoff model would train on a bare-ground fraction
that is simply the wrong class, and nothing would crash.
"""

import numpy as np
import rasterio
import rasterio.windows
import matplotlib.colors as mcolors  # colour table for the GPKG/GeoTIFF palette only

from config import DOWNLOAD_BBOX, INTERIM, RAW, WORLDCOVER_CLASSES

TILE = RAW / "worldcover" / "ESA_WorldCover_10m_2021_v200_N27E033_Map.tif"
CLIP = INTERIM / "worldcover_aqaba_clip.tif"

# Rough visual palette, close to ESA's own legend so the QA plot is comparable
# against the official viewer.
CLASS_COLORS = {
    10: "#006400", 20: "#ffbb22", 30: "#ffff4c", 40: "#f096ff", 50: "#fa0000",
    60: "#b4b4b4", 70: "#f0f0f0", 80: "#0064c8", 90: "#0096a0", 95: "#00cf75",
    100: "#fae6a0",
}


def clip_to_aoi():
    """Windowed read — the source tile is 36000x36000, do not read it whole."""
    minx, miny, maxx, maxy = DOWNLOAD_BBOX
    with rasterio.open(TILE) as src:
        # Guard: a tile that does not fully cover the AOI would silently truncate
        # the eastern or western catchments.
        b = src.bounds
        assert b.left <= minx and b.right >= maxx and b.bottom <= miny and b.top >= maxy, (
            f"tile {b} does not cover AOI {DOWNLOAD_BBOX} — another tile is needed"
        )

        win = rasterio.windows.from_bounds(minx, miny, maxx, maxy, src.transform)
        data = src.read(1, window=win)
        meta = src.meta.copy()
        meta.update(
            height=data.shape[0], width=data.shape[1],
            transform=src.window_transform(win), compress="deflate",
        )
    CLIP.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(CLIP, "w", **meta) as dst:
        dst.write(data, 1)
        # Keep a colour table so the file renders sensibly when someone opens it
        # in QGIS. The band still holds raw class codes — that is what any
        # zonal-statistics call reads.
        dst.write_colormap(
            1,
            {code: tuple(int(255 * v) for v in mcolors.to_rgb(hexcolor)) + (255,)
             for code, hexcolor in CLASS_COLORS.items()},
        )
    print(f"  wrote {CLIP.name}  {data.shape[1]}x{data.shape[0]} @ 10 m")
    return data


def composition(data):
    """Class composition over the whole AOI and over land only."""
    codes, counts = np.unique(data, return_counts=True)
    total = counts.sum()

    unknown = [int(c) for c in codes if c not in WORLDCOVER_CLASSES and c != 0]
    assert not unknown, f"codes absent from WORLDCOVER_CLASSES: {unknown}"

    # Water is a legitimate class, but the ~74% bare-ground expectation in the
    # concept doc describes LAND catchments. The AOI is ~23% sea, so an AOI-wide
    # bare fraction is diluted and is not the number to sanity-check against.
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
    """The mandatory bare-ground check. Wrong class mapping is silent otherwise."""
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
    print(f"WorldCover source: {TILE.name}")
    data = clip_to_aoi()
    rows, land_total = composition(data)
    sanity_check(rows)
    print(f"\nland area in AOI: {land_total * 100 / 1e6:.0f} km2 "
          f"({land_total / (data.shape[0] * data.shape[1]) * 100:.1f}% of AOI)")
