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
import pathlib

import rasterio
import rasterio.windows
import matplotlib.colors as mcolors  # colour table for the GPKG/GeoTIFF palette only

from pulga_config import DOWNLOAD_BBOX, INTERIM, RAW, WORLDCOVER_CLASSES

WORLDCOVER_DIR = RAW / "worldcover"
CLIP = INTERIM / "worldcover_aqaba_clip.tif"

#: ESA WorldCover ships 3x3 degree tiles named for their SOUTH-WEST corner.
#: The terrain AOI reaches 30.30 N, so it now straddles the N27/N30 boundary and
#: a single tile can no longer cover it — the assert in clip_to_aoi() catches
#: that, and this derives the full set instead of naming one.
TILE_URL = (
    "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    "ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
)


def tiles_for(bbox) -> list[str]:
    """Every 3x3 degree WorldCover tile name intersecting `bbox`."""
    minx, miny, maxx, maxy = bbox
    names = []
    lat = (int(miny) // 3) * 3
    while lat <= maxy:
        lon = (int(minx) // 3) * 3
        while lon <= maxx:
            ns, ew = ("N", "S")[lat < 0], ("E", "W")[lon < 0]
            names.append(f"{ns}{abs(lat):02d}{ew}{abs(lon):03d}")
            lon += 3
        lat += 3
    return names


def ensure_tiles(bbox) -> list[pathlib.Path]:
    """Download any WorldCover tile the AOI needs and is missing."""
    import urllib.request

    WORLDCOVER_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for tile in tiles_for(bbox):
        target = WORLDCOVER_DIR / f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
        if not target.exists() or target.stat().st_size == 0:
            url = TILE_URL.format(tile=tile)
            print(f"  fetching {tile} ...", flush=True)
            try:
                urllib.request.urlretrieve(url, target)
            except Exception as exc:
                target.unlink(missing_ok=True)
                # Not every 3x3 cell exists — WorldCover has no tile over open
                # ocean. A missing tile is only fatal if the AOI needs its land.
                print(f"  {tile}: unavailable ({type(exc).__name__}) — skipped")
                continue
        paths.append(target)
    return paths

# Rough visual palette, close to ESA's own legend so the QA plot is comparable
# against the official viewer.
CLASS_COLORS = {
    10: "#006400", 20: "#ffbb22", 30: "#ffff4c", 40: "#f096ff", 50: "#fa0000",
    60: "#b4b4b4", 70: "#f0f0f0", 80: "#0064c8", 90: "#0096a0", 95: "#00cf75",
    100: "#fae6a0",
}


def clip_to_aoi():
    """Windowed read across every tile the AOI needs, mosaicked.

    Each source tile is 36000x36000, so the read stays windowed. The AOI spans
    two tiles now (it reaches 30.30 N), which is why this merges rather than
    reading one.
    """
    from rasterio.merge import merge

    minx, miny, maxx, maxy = DOWNLOAD_BBOX
    tiles = ensure_tiles(DOWNLOAD_BBOX)
    if not tiles:
        raise SystemExit(f"no WorldCover tile available for {DOWNLOAD_BBOX}")

    handles = [rasterio.open(path) for path in tiles]
    try:
        # Guard kept, now against the UNION of tiles: partial cover would
        # silently truncate the northern or eastern catchments.
        union = (
            min(h.bounds.left for h in handles), min(h.bounds.bottom for h in handles),
            max(h.bounds.right for h in handles), max(h.bounds.top for h in handles),
        )
        assert (union[0] <= minx and union[2] >= maxx
                and union[1] <= miny and union[3] >= maxy), (
            f"tiles {[p.name for p in tiles]} span {union}, which does not cover "
            f"AOI {DOWNLOAD_BBOX}"
        )
        data, transform = merge(handles, bounds=(minx, miny, maxx, maxy))
        data = data[0]
        meta = handles[0].meta.copy()
        meta.update(
            height=data.shape[0], width=data.shape[1],
            transform=transform, compress="deflate",
        )
        print(f"  mosaicked {len(tiles)} tile(s): "
              f"{', '.join(p.name.split('_')[-2] for p in tiles)}")
    finally:
        for h in handles:
            h.close()
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
    print(f"WorldCover source: {len(tiles_for(DOWNLOAD_BBOX))} tile(s) "
          f"{tiles_for(DOWNLOAD_BBOX)}")
    data = clip_to_aoi()
    rows, land_total = composition(data)
    sanity_check(rows)
    print(f"\nland area in AOI: {land_total * 100 / 1e6:.0f} km2 "
          f"({land_total / (data.shape[0] * data.shape[1]) * 100:.1f}% of AOI)")
