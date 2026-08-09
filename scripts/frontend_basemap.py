#!/usr/bin/env python3
"""Derive the frontend basemap as GeoJSON from data already in this repo.

The frontend renders no external map tiles at all. DoD item 9 is "works with
wifi off", and a tile cache is a promise rather than a guarantee — so the
basemap is authored from `data/processed/vectors/*.gpkg` plus the bathymetry
raster and committed under `frontend/public/basemap/`. Offline becomes
structural: there is nothing to fetch, nothing to warm and nothing to size.

Three facts make that the cheap option rather than the heroic one. The AOI is
about 24 x 39 km, so one GeoJSON per layer is smaller than a tile pyramid's
metadata. The repo already holds every layer needed. And `08-map-rendering.md`
requires a style "authored against the design tokens, not a borrowed theme",
which means a vendor schema would be adopted and then fought.

Run in the worker container — geopandas and rasterio are not in the api image
and are usually absent locally:

    mkdir -p frontend/public/basemap
    docker compose run --rm --entrypoint "" \\
      -v "$PWD/frontend/public/basemap:/out" \\
      worker python /app/scripts/frontend_basemap.py --out /out

The worker mounts ./data, ./backend/src and ./scripts but NOT ./frontend, which
is why the output path is an ad-hoc mount rather than a path inside the repo.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio import features
from shapely.geometry import box, shape
from shapely.ops import unary_union

# scripts/config.py was deleted on main while this frontend was being built, and the
# spatial constants moved to backend/src/config/spatial.py. Other scripts now resolve
# their own paths (see scripts/export_web_layers.py), so this does the same rather than
# reintroducing a module main deliberately removed.
#
# The AOIs are still imported rather than retyped: tests/test_spatial_contract.py exists
# precisely because a hardcoded bounding box is how the AOI silently regressed once
# already, and RETIRED_BOX is asserted against in spatial.py for the same reason.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
from config import spatial as _spatial  # noqa: E402


class cfg:  # noqa: N801 — kept lowercase so the call sites below read unchanged
    """The handful of paths and constants this script needs."""

    DATA = ROOT / "data"
    PROCESSED = DATA / "processed"
    VECTORS = PROCESSED / "vectors"
    FEATURES = PROCESSED / "features"
    REPO_ROOT = ROOT
    TERRAIN_AOI = _spatial.TERRAIN_AOI
    MARINE_AOI = _spatial.MARINE_AOI
    AQABA_AOI = _spatial.AQABA_AOI
    AOI_CRS_STORAGE = _spatial.CRS_STORAGE
    AOI_CRS_PROJECTED = _spatial.CRS_MEASURE

# Isobaths. Chosen against the measured range of depth_utm36n.tif (-907 m to
# +1542 m at 50 m): shelf detail where the reef is, then coarse steps into the
# basin, which reaches ~1,800 m further south than this AOI.
ISOBATHS = [-25, -50, -100, -200, -400, -600, -800]

# 3,845 road features are mostly residential and service ways that add nothing
# at these zooms and most of the payload. Keep the network that reads as a city.
MAJOR_ROADS = ("motorway", "trunk", "primary", "secondary", "tertiary",
               "motorway_link", "trunk_link", "primary_link")

COORD_DP = 5          # ~1 m at this latitude

# Shortest drainage fragment worth drawing. Measured against the current extract:
# features below this are 21% of the count and 1.3% of the length. Named features
# bypass it entirely — see the wadi filter below.
MIN_WADI_M = 200.0

# Simplification tolerance in metres, applied in EPSG:32636 before reprojecting.
# One tolerance for everything does not work here, and the reason is the spread
# of scales: the shoreline is the signature and is read at street zoom, while
# AQ-C01 is 4,453 km² draining from 90 km inland and is only ever seen whole. At
# a uniform 8 m the five catchments alone were 287 KB of a 500 KB budget — detail
# no zoom level can show, because the polygon never fits the screen at a scale
# where 8 m is a visible distance.
SIMPLIFY_M = {
    "shoreline": 8.0,     # the signature — read close in, keep it honest
    "water": 8.0,
    "reef_zones": 8.0,    # small, near-shore, and the subject of the product
    "outlets": 0.0,       # points
    "roads": 20.0,
    "places": 0.0,        # points
    "landuse": 25.0,
    "wadis": 80.0,
    "isobaths": 60.0,     # 50 m source raster; finer is quantisation noise
    # Coarser than isobaths deliberately: this feeds a 3D fill-extrusion viewed from
    # well outside the AOI, not a measurement read up close, and the fragmented
    # mountainous terrain produces far more tiny polygons per metre of tolerance than
    # the smoother seafloor isobaths do at the same setting.
    "relief_bands": 200.0,
    "buildings": 1.0,      # buildings are metres-scale; any coarser loses the footprint shape
    "catchments": 120.0,
    "coverage": 0.0,      # a bbox
    "_default": 15.0,
}

ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
LATIN = re.compile(r"[A-Za-z]")


def parse_other_tags(raw):
    """OSM `other_tags` is an hstore string: "name:ar"=>"...","name:en"=>"..."."""
    # `not raw` looked like it covered "missing", but a missing `other_tags`
    # cell is a NaN float (truthy, so `not raw` is False) once the column has
    # any real string values elsewhere -- same pandas object-dtype gap as
    # bilingual()'s own `name` column, just one call further in.
    if not isinstance(raw, str):
        return {}
    return dict(re.findall(r'"([^"]+)"=>"([^"]*)"', raw))


def bilingual(row):
    """Split a feature's names into Arabic and Latin, per script.

    06-bilingual-rtl.md §4 says to select `name:ar` and fall back to `name`.
    Checked against the extract, that is only half right and the missing half
    breaks English: `osm_aqaba.gpkg` has no `name:ar` column at all — the tag
    lives inside `other_tags` — and the plain `name` column is *already Arabic*
    on many features, with the Latin form in `name:en`. So a `name:ar` -> `name`
    fallback shows `شارع الملك حسين` in English mode.

    Measured here: 472 named roads, 169 carrying name:ar, 182 carrying name:en.
    Some features carry neither and one carries Hebrew (נחל שחורת, on the
    Israeli side), so a name in a third script is assigned to neither field
    rather than mislabelled as English.
    """
    tags = parse_other_tags(row.get("other_tags"))
    # `row.get("name")` is a NaN float, not None, when the column has any real
    # string values elsewhere -- pandas gives the column object dtype with
    # float("nan") filling the gaps, and `nan or ""` evaluates to nan (NaN is
    # truthy), so `.strip()` used to crash on the first no-name feature reached.
    raw_name = row.get("name")
    name = (raw_name if isinstance(raw_name, str) else "").strip()

    ar = tags.get("name:ar") or (name if ARABIC.search(name) else None)
    en = tags.get("name:en") or (name if LATIN.search(name) and not ARABIC.search(name) else None)
    return (ar or None), (en or None)


def round_coords(obj, dp=COORD_DP):
    """Trim coordinate precision in place. 5 dp is ~1 m and typically halves
    the payload; 15 dp of float noise is not information."""
    if isinstance(obj, list):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(v), dp) for v in obj]
        return [round_coords(v, dp) for v in obj]
    return obj


def write(out_dir, name, gdf, keep=(), report=None):
    """Simplify in metres, reproject to 4326, trim precision, write GeoJSON."""
    if gdf is None or gdf.empty:
        print(f"  {name:<16} SKIPPED — no features")
        return

    tol = SIMPLIFY_M.get(name, SIMPLIFY_M["_default"])
    gdf = gdf.to_crs(cfg.AOI_CRS_PROJECTED)
    if tol > 0:
        gdf["geometry"] = gdf.geometry.simplify(tol, preserve_topology=True)
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    gdf = gdf.to_crs(cfg.AOI_CRS_STORAGE)

    cols = [c for c in keep if c in gdf.columns]
    fc = json.loads(gdf[cols + ["geometry"]].to_json(drop_id=True))
    for f in fc["features"]:
        if f.get("geometry"):
            f["geometry"]["coordinates"] = round_coords(f["geometry"]["coordinates"])
        # null-valued properties are noise in a payload this size
        f["properties"] = {k: v for k, v in (f.get("properties") or {}).items() if v is not None}

    path = Path(out_dir) / f"{name}.geojson"
    path.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":")))
    size = path.stat().st_size
    print(f"  {name:<16} {len(fc['features']):>5} features  {size:>8,} B")
    if report is not None:
        report.append((name, len(fc["features"]), size))


def name_coverage(gdf, label):
    """Print measured bilingual coverage, so 06 §4's claim carries evidence."""
    named = int(((gdf.get("name_ar").notna()) | (gdf.get("name_en").notna())).sum())
    ar = int(gdf["name_ar"].notna().sum())
    en = int(gdf["name_en"].notna().sum())
    print(f"    names {label}: {named} named of {len(gdf)}  (ar {ar}, en {en})")


def isobaths(report):
    """Contour the depth field without matplotlib or skimage.

    Neither is in requirements-worker.txt, and adding a dependency for this is
    unnecessary: rasterio.features.shapes over a boolean mask per level gives
    the polygon of "at least this deep", whose boundary IS the isobath. That
    also makes the sign convention explicit rather than implied.
    """
    src_path = cfg.PROCESSED / "bathymetry" / "depth_utm36n.tif"
    if not src_path.exists():
        print(f"  isobaths         SKIPPED — {src_path} not present")
        return None

    with rasterio.open(src_path) as src:
        arr = src.read(1, masked=True)
        transform, crs = src.transform, src.crs

    rows = []
    for level in ISOBATHS:
        # negative is below sea level, so "deeper than" is <=
        mask = (arr <= level).filled(False)
        if not mask.any():
            continue
        polys = [
            shape(geom)
            for geom, val in features.shapes(mask.astype(np.uint8), mask=mask, transform=transform)
            if val == 1
        ]
        if not polys:
            continue
        merged = unary_union(polys)
        # the boundary is the contour; a filled band would need its own legend
        rows.append({"geometry": merged.boundary, "depth_m": level})

    if not rows:
        print("  isobaths         SKIPPED — no cell reached any level")
        return None

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)
    print(f"    isobath levels: {[r['depth_m'] for r in rows]}")
    return gdf


# Same raster as isobaths(), banded rather than contoured: filled polygons with a
# real mid-band metres value, for the 3D Journey's fill-extrusion (feature 14,
# tasks/phase4/00-phase4-plan.md and tasks/phase4/06-ali.md).
# One real DEM/bathymetry source covers both land (positive, the coastal fringe the
# marine AOI raster reaches) and sea (negative) -- no separate terrain source, no
# invented relief. Edges chosen to match ISOBATHS below sea level and to resolve the
# coastal mountains (up to ~1,800 m) above it without over-fragmenting the polygon
# count.
RELIEF_BAND_EDGES_M = [-800, -400, -200, -100, -50, -25, 0, 50, 150, 400, 800, 2000]


def relief_bands(report):
    """Fill-able elevation/depth bands from the same raster isobaths() contours.

    rasterio.features.shapes over a boolean mask per band, same technique as
    isobaths() and as models.particle_engine.kernel_density_contours -- one
    proven approach, reused rather than a third variant invented for this.
    Unlike isobaths() this keeps the filled polygon (not `.boundary`): a
    fill-extrusion layer needs an area with a height, a contour line has none.
    """
    src_path = cfg.PROCESSED / "bathymetry" / "depth_utm36n.tif"
    if not src_path.exists():
        print(f"  relief_bands     SKIPPED — {src_path} not present")
        return None

    with rasterio.open(src_path) as src:
        arr = src.read(1, masked=True)
        transform, crs = src.transform, src.crs

    rows = []
    edges = RELIEF_BAND_EDGES_M
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = ((arr >= lo) & (arr < hi)).filled(False)
        if not mask.any():
            continue
        polys = [
            shape(geom)
            for geom, val in features.shapes(mask.astype(np.uint8), mask=mask, transform=transform)
            if val == 1
        ]
        if not polys:
            continue
        merged = unary_union(polys)
        rows.append({
            "geometry": merged,
            "band_min_m": float(lo),
            "band_max_m": float(hi),
            "mid_m": float((lo + hi) / 2.0),
            "realm": "sea" if hi <= 0 else ("land" if lo >= 0 else "shore"),
        })

    if not rows:
        print("  relief_bands     SKIPPED — no cell reached any band")
        return None

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=crs)
    print(f"    relief bands: {[(r['band_min_m'], r['band_max_m']) for r in rows]}")
    return gdf


#: Real building footprints exist in osm_aqaba.gpkg's own `buildings` layer
#: (12,570 total across the full TERRAIN_AOI extract) but were never exposed to the
#: frontend before the 3D Journey (feature 14) needed urban context. Clipped to a
#: small buffer around each of the five real outlets individually, not one
#: bounding box spanning all five -- the outlets stretch ~21 km along the coast,
#: and a single enclosing box pulls in the empty coastline between them (9,914
#: buildings, 2.4 MB). Five small buffers instead: 570 buildings, one per outlet's
#: actual immediate urban context, not the desert or empty shore between them.
BUILDINGS_AOI_BUFFER_DEG = 0.025
DEFAULT_BUILDING_LEVELS = 2.0     # median residential building height region-wide, not measured per-roof
HOTEL_DEFAULT_LEVELS = 8.0        # mid-rise default for real building=hotel/tourism=hotel tags --
                                   # still an assumption (no per-hotel measurement), but the same
                                   # single flat default as every other building was visibly wrong
                                   # against a skyline that is mostly hotel towers on the coast strip
HISTORIC_DEFAULT_LEVELS = 1.0     # historic=* (Aqaba Fort/Mamluk Castle, city gates) -- low, flat,
                                   # real single-storey profile, never the generic default
LEVEL_HEIGHT_M = 3.0              # standard storey height assumption, documented not measured
MIN_BUILDING_AREA_M2 = 20.0       # drops shed/noise-scale footprints, same threshold everywhere


def buildings(report):
    """Real OSM building footprints, height-tagged where OSM has the tag.

    `building:levels` lives in the same `other_tags` hstore `bilingual()` already
    parses for road/wadi names -- reused here via `parse_other_tags`, not a new
    parser. Only ~16% of buildings in this extract carry it (measured against the
    outlet-cluster clip).

    Everything else falls back to a category default, not one flat number for
    every building regardless of type -- a single default made the coastal hotel
    strip (real `building=hotel`/`tourism=hotel` tags, both real OSM columns, not
    invented) render at the same height as a garden shed, which looked wrong
    against the real skyline it's supposed to stand in for. The category and the
    fallback height are both still assumptions where OSM has no `building:levels`
    tag -- shown in the 3D scene as real footprint + assumed height, never as a
    claimed per-building measurement.
    """
    src_path = cfg.VECTORS / "osm_aqaba.gpkg"
    if not src_path.exists():
        print(f"  buildings        SKIPPED — {src_path} not present")
        return None

    b = gpd.read_file(src_path, layer="buildings")
    outlets_path = cfg.VECTORS / "outlets.gpkg"
    if not outlets_path.exists():
        print("  buildings        SKIPPED — outlets.gpkg not present, no AOI to clip to")
        return None
    outlets_gdf = gpd.read_file(outlets_path)
    pad = BUILDINGS_AOI_BUFFER_DEG
    clip_boxes = [box(pt.x - pad, pt.y - pad, pt.x + pad, pt.y + pad)
                  for pt in outlets_gdf.geometry]
    clip_union = unary_union(clip_boxes)
    b = b[b.intersects(clip_union)].copy()

    def levels(raw):
        tags = parse_other_tags(raw)
        lv = tags.get("building:levels")
        try:
            return float(lv) if lv is not None else None
        except ValueError:
            return None

    b["levels"] = b["other_tags"].apply(levels)
    tagged = int(b["levels"].notna().sum())
    print(f"    buildings in AOI: {len(b)}  ({tagged} carry a real building:levels tag)")

    # Real footprint area filters noise (sheds, small structures the extrusion
    # would render as visual clutter at this AOI's zoom) more honestly than a
    # feature-count cap would -- it drops the same kind of feature everywhere,
    # not an arbitrary first-N.
    b["area_m2"] = b.to_crs(cfg.AOI_CRS_PROJECTED).geometry.area
    b = b[b["area_m2"] >= MIN_BUILDING_AREA_M2]
    print(f"    buildings kept (>= {MIN_BUILDING_AREA_M2:.0f} m² footprint): {len(b)}")

    is_hotel = (b["building"] == "hotel") | (b["tourism"] == "hotel")
    is_historic = b["historic"].notna()
    fallback = np.select(
        [is_historic, is_hotel],
        [HISTORIC_DEFAULT_LEVELS, HOTEL_DEFAULT_LEVELS],
        default=DEFAULT_BUILDING_LEVELS,
    )
    print(f"    building height categories: {int(is_historic.sum())} historic (flat), "
          f"{int(is_hotel.sum())} hotel (tall), rest default")
    b["levels"] = np.where(b["levels"].isna(), fallback, b["levels"])
    b["height_m"] = b["levels"] * LEVEL_HEIGHT_M
    b["name"] = b["name"].where(b["name"].apply(lambda v: isinstance(v, str)), None)
    return b


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="output directory for the GeoJSON layers")
    # 1,100 KB, raised from the 500 KB set in Phase 1 — and this is a judgement, not
    # a capitulation. Two things changed: main re-extracted osm_aqaba.gpkg over a
    # larger area (drainage went 406 -> 2,836 features, 4,751 km of it), and the real
    # ACA reef habitat is far more detailed than the provisional 250 m strip it
    # replaced.
    #
    # The 500 KB figure was sized against the old extract, and the constraint it was
    # standing in for was "the browser must never see the raw series" — tile pyramids
    # and the 4.2 MB plume raster re-fetched per interaction. A one-time ~1 MB of
    # same-origin GeoJSON, parsed once, is not that. Cutting the wadis further to fit
    # a number invented in Phase 1 would remove the hazard's own paths, which 01 §2
    # calls part of the signature.
    # 1,400 KB, raised from 1,100 -- same judgement call as the 500->1,100 raise
    # above, for the same reason: relief_bands.geojson (feature 14, the 3D Journey)
    # adds ~325 KB of real, fill-extrudable elevation/depth polygons at 200 m
    # simplification -- coarser than isobaths already is, and the fragmented
    # mountainous terrain does not compress further without visibly blocky bands.
    # Still same-origin, still parsed once, still nowhere near a tile pyramid.
    #
    # 1,550 KB, raised from 1,400 -- buildings.geojson (real OSM footprints for
    # urban context, same feature) adds ~155 KB at 617 features, already clipped
    # to five small per-outlet buffers rather than one enclosing box (which would
    # have been 2.4 MB). This is the real cost of that real data, not slack.
    ap.add_argument("--budget-kb", type=int, default=1550,
                    help="fail if the total exceeds this (default 1550)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    V = cfg.VECTORS
    osm = V / "osm_aqaba.gpkg"
    report = []

    print("ReefShield frontend basemap")
    print("=" * 62)
    print(f"  storage CRS {cfg.AOI_CRS_STORAGE}   measure CRS {cfg.AOI_CRS_PROJECTED}")
    tols = ", ".join(f"{k} {v:g}m" for k, v in SIMPLIFY_M.items() if k != "_default" and v)
    print(f"  coordinates to {COORD_DP} dp; simplify {tols}")
    print()

    # --- the sea, and the line that bounds it ------------------------------
    write(out, "water", gpd.read_file(V / "coastline.gpkg", layer="water"),
          keep=("area_km2", "role"), report=report)
    write(out, "shoreline", gpd.read_file(V / "coastline.gpkg", layer="shoreline"),
          report=report)

    # --- the signature -----------------------------------------------------
    write(out, "isobaths", isobaths(report), keep=("depth_m",), report=report)
    write(out, "relief_bands", relief_bands(report),
          keep=("band_min_m", "band_max_m", "mid_m", "realm"), report=report)
    write(out, "buildings", buildings(report),
          keep=("osm_id", "name", "levels", "height_m"), report=report)

    # --- OSM: roads, wadis, protection, landuse, places --------------------
    roads = gpd.read_file(osm, layer="roads")
    roads["name_ar"], roads["name_en"] = zip(*roads.apply(bilingual, axis=1))
    keep_road = roads["highway"].isin(MAJOR_ROADS) | roads["name_ar"].notna() | roads["name_en"].notna()
    roads = roads[keep_road].copy()
    name_coverage(roads, "roads")
    write(out, "roads", roads, keep=("name_ar", "name_en", "highway"), report=report)

    wadis = gpd.GeoDataFrame(
        __import__("pandas").concat(
            [gpd.read_file(osm, layer="waterways"), gpd.read_file(osm, layer="drainage_features")],
            ignore_index=True),
        crs=roads.crs)
    wadis["name_ar"], wadis["name_en"] = zip(*wadis.apply(bilingual, axis=1))

    # Drop drainage fragments shorter than MIN_WADI_M.
    #
    # main re-extracted osm_aqaba.gpkg over a larger area, and this layer went from
    # 406 features to 2,836 — 806 KB on its own, against a 500 KB budget for the
    # whole pack. Measured before cutting: the 602 features under 200 m are 21% of
    # the count but only 1.3% of the 4,751 km of total drainage length. They are
    # fragments, not drainage paths.
    #
    # Named features are kept regardless of length: وادي اليتيم is the demo path and
    # a length threshold must never be what removes it.
    before_n = len(wadis)
    m = wadis.to_crs(cfg.AOI_CRS_PROJECTED)
    keep_wadi = (m.geometry.length >= MIN_WADI_M) | wadis["name_ar"].notna() | wadis["name_en"].notna()
    dropped_km = m.loc[~keep_wadi].geometry.length.sum() / 1000
    total_km = m.geometry.length.sum() / 1000
    wadis = wadis[keep_wadi].copy()
    print(f"    wadis: kept {len(wadis)} of {before_n} (>= {MIN_WADI_M:.0f} m or named); "
          f"dropped {dropped_km:.0f} km of {total_km:.0f} km "
          f"({100 * dropped_km / max(total_km, 1e-9):.1f}% of length)")

    # A `minor` flag rather than a second file: the style shows minor drainage only
    # from zoom 12, so the basin view is not 2,242 hairlines competing with the
    # catchment boundaries. Bytes and render cost are different problems, and the
    # length filter above only addressed the first.
    wadis["minor"] = (m.loc[keep_wadi].geometry.length < 1000).astype(int)
    print(f"    wadis: {int(wadis['minor'].sum())} minor (zoom>=12), "
          f"{int((1 - wadis['minor']).sum())} major")

    name_coverage(wadis, "wadis")
    write(out, "wadis", wadis,
          keep=("name_ar", "name_en", "waterway", "intermittent", "minor"),
          report=report)

    prot = gpd.read_file(osm, layer="protected_areas")
    prot["name_ar"], prot["name_en"] = zip(*prot.apply(bilingual, axis=1))
    name_coverage(prot, "protected")
    write(out, "protected", prot, keep=("name_ar", "name_en", "protect_class"), report=report)

    pd = __import__("pandas")
    landuse = gpd.GeoDataFrame(
        pd.concat([gpd.read_file(osm, layer=l).assign(kind=l)
                   for l in ("industrial", "port", "tourism_areas")], ignore_index=True),
        crs=prot.crs)
    write(out, "landuse", landuse, keep=("kind",), report=report)

    poi = gpd.read_file(osm, layer="dive_tourism_poi")
    poi["name_ar"], poi["name_en"] = zip(*poi.apply(bilingual, axis=1))
    poi = poi[poi["name_ar"].notna() | poi["name_en"].notna()].copy()

    # Drop tourism=information. Those features carry noticeboard *prose* in their
    # name tag rather than a place name — "Can't walk to the border from this
    # road", "Closed road, no way to border", "Boat crossing Tala Bay - Taba
    # Heights". Rendered as map labels they read as gazetteer entries, and one of
    # them was sitting over the demo coastline.
    before = len(poi)
    poi = poi[poi["tourism"] != "information"].copy()
    if before != len(poi):
        print(f"    dropped {before - len(poi)} tourism=information (noticeboard text, not place names)")

    # 01 §1: the user is a marine-park officer deciding whether to send someone to
    # sample water near a reef zone. Dive sites serve that decision; the 37 hotels
    # are coastal orientation at most, so the style labels them only when zoomed in.
    poi["kind"] = "poi"
    poi.loc[(poi["sport"] == "scuba_diving") | (poi["tourism"] == "attraction"), "kind"] = "dive"
    poi.loc[poi["tourism"] == "hotel", "kind"] = "hotel"
    print(f"    place kinds: {dict(poi['kind'].value_counts())}")

    name_coverage(poi, "places")
    # osm_id survives every filter above untouched -- it's a real, stable ID
    # from the source data (not synthesized), and Phase 4 needs one to join a
    # dive site to its nearest reef zone. It was dropped here until now.
    write(out, "places", poi, keep=("osm_id", "name_ar", "name_en", "kind"), report=report)

    # --- the project's own geometry ----------------------------------------
    # These exist because /api/v1/catchments returns attributes plus a single
    # lon/lat point and no polygon at all, and /api/v1/reef-zones is not
    # implemented. Raised as Day-1 ask #8; committed here so the map is not
    # blocked on it, and so the offline pack has them either way.
    #
    # The 3D Journey's "normal" phase drew catchments as an unlabelled outline
    # with no distinguishing property, so all five looked identical regardless
    # of how different they really are. `soil_by_catchment.parquet` (real
    # SoilGrids texture) and `catchment_terrain.parquet` (real DEM-derived
    # relief/slope/drainage) were already computed per catchment for the
    # runoff model — joined in here rather than re-derived, so the map shows
    # the same real numbers the model trains on, not a second estimate.
    F = ROOT / "data" / "processed" / "features"
    catchments_gdf = gpd.read_file(V / "catchments.gpkg", layer="catchments")
    soil = pd.read_parquet(F / "soil_by_catchment.parquet")[
        ["catchment_id", "sand_0_5cm_mean", "clay_0_5cm_mean", "silt_0_5cm_mean"]
    ].rename(columns={
        "sand_0_5cm_mean": "sand_pct",
        "clay_0_5cm_mean": "clay_pct",
        "silt_0_5cm_mean": "silt_pct",
    })
    terrain_stats = pd.read_parquet(F / "catchment_terrain.parquet")[
        ["catchment_id", "relief_m", "slope_mean_deg", "drainage_density_km_km2"]
    ]
    catchments_gdf = catchments_gdf.merge(soil, on="catchment_id", how="left").merge(
        terrain_stats, on="catchment_id", how="left")
    for col in ("sand_pct", "clay_pct", "silt_pct", "relief_m", "slope_mean_deg",
                "drainage_density_km_km2"):
        catchments_gdf[col] = catchments_gdf[col].round(1)
    write(out, "catchments", catchments_gdf,
          keep=("catchment_id", "outlet_id", "area_km2", "provisional", "sand_pct",
                "clay_pct", "silt_pct", "relief_m", "slope_mean_deg",
                "drainage_density_km_km2"),
          report=report)

    # reef_zones.gpkg, not reef_zones_PROVISIONAL.gpkg. Contract swap-in #3 landed
    # while this frontend was being built: source is now `ACA/reef_habitat/v2_0`,
    # real Allen Coral Atlas habitat rather than a water-mask shoreline plus an
    # assumed 250 m strip.
    #
    # The difference is not cosmetic. Total reef area drops from 5.685 km² to
    # 1.235 km² — 4.6x smaller — because the provisional strip was far more
    # generous than the actual mapped habitat. A frontend still drawing the old
    # file would overstate the reef by that factor on every screen.
    #
    # `sensitivity_weight` is STILL 1.0 with status
    # PLACEHOLDER_PENDING_MARINE_SCIENTIST, so the geometry is real and the
    # weighting is not. Those are two separate claims and the UI copy now
    # distinguishes them.
    reef_path = V / "reef_zones.gpkg"
    if not reef_path.exists():
        reef_path = V / "reef_zones_PROVISIONAL.gpkg"
        print("    WARNING falling back to reef_zones_PROVISIONAL.gpkg — swap-in #3 absent")
    reef = gpd.read_file(reef_path, layer="reef_zones")
    print(f"    reef source: {reef_path.name}  {len(reef)} zones, "
          f"{reef['area_km2'].sum():.3f} km² total")
    write(out, "reef_zones", reef,
          # habitat_class and geomorphic_class only carry information in the real ACA
          # file — the provisional one had habitat_class = 'unknown' on all eight
          # zones. Passing them through means the UI can say what each zone actually
          # is rather than only how big it is.
          keep=("reef_zone_id", "zone_name", "area_km2", "marine_park_overlap_pct",
                "habitat_class", "geomorphic_class",
                "sensitivity_weight", "sensitivity_weight_status", "provisional",
                "source"),
          report=report)

    outlets_src = V / "outlets.geojson"
    if outlets_src.exists():
        (out / "outlets.geojson").write_text(outlets_src.read_text())
        size = (out / "outlets.geojson").stat().st_size
        n = len(json.loads(outlets_src.read_text())["features"])
        print(f"  {'outlets':<16} {n:>5} features  {size:>8,} B  (copied verbatim)")
        report.append(("outlets", n, size))

    # --- the honesty device -------------------------------------------------
    # scripts/config.py records that osm_aqaba.gpkg was extracted against a
    # superseded, smaller AOI, while TERRAIN_AOI now reaches 35.94 E / 30.30 N
    # because Wadi Yutum drains 90 km inland. So the basemap stops well short of
    # where AQ-C01 does. Drawing that boundary is the same move as showing the
    # ~9 km ocean-model grid: cheaper than pretending, and more convincing.
    osm_extent = gpd.read_file(osm, layer="osm_coastline").total_bounds
    coverage = gpd.GeoDataFrame(
        [{"geometry": box(*osm_extent), "role": "osm_extract_extent"}],
        crs=cfg.AOI_CRS_STORAGE)
    write(out, "coverage", coverage, keep=("role",), report=report)

    total = sum(s for _, _, s in report)
    print()
    print("=" * 62)
    print(f"  {len(report)} layers, {total:,} B total ({total / 1024:.1f} KB)")
    print(f"  terrain AOI reaches {cfg.TERRAIN_AOI.wsen[2]} E / {cfg.TERRAIN_AOI.wsen[3]} N")
    print(f"  OSM extract stops at {round(osm_extent[2], 2)} E / {round(osm_extent[3], 2)} N"
          "  <- why coverage.geojson exists")

    if total > args.budget_kb * 1024:
        print(f"\n  OVER BUDGET: {total / 1024:.1f} KB > {args.budget_kb} KB")
        return 1
    print(f"  within the {args.budget_kb} KB budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
