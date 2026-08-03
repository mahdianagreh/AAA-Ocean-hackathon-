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
      worker python /app/scripts/13_frontend_basemap.py --out /out

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg  # noqa: E402  — paths and AOIs come from the contract, never literals

# Isobaths. Chosen against the measured range of depth_utm36n.tif (-907 m to
# +1542 m at 50 m): shelf detail where the reef is, then coarse steps into the
# basin, which reaches ~1,800 m further south than this AOI.
ISOBATHS = [-25, -50, -100, -200, -400, -600, -800]

# 3,845 road features are mostly residential and service ways that add nothing
# at these zooms and most of the payload. Keep the network that reads as a city.
MAJOR_ROADS = ("motorway", "trunk", "primary", "secondary", "tertiary",
               "motorway_link", "trunk_link", "primary_link")

COORD_DP = 5          # ~1 m at this latitude

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
    "reef_zones": 5.0,    # small, near-shore, and the subject of the product
    "outlets": 0.0,       # points
    "roads": 12.0,
    "places": 0.0,        # points
    "landuse": 25.0,
    "wadis": 25.0,
    "isobaths": 60.0,     # 50 m source raster; finer is quantisation noise
    "catchments": 120.0,
    "coverage": 0.0,      # a bbox
    "_default": 15.0,
}

ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
LATIN = re.compile(r"[A-Za-z]")


def parse_other_tags(raw):
    """OSM `other_tags` is an hstore string: "name:ar"=>"...","name:en"=>"..."."""
    if not raw:
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
    name = (row.get("name") or "").strip()

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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="output directory for the GeoJSON layers")
    ap.add_argument("--budget-kb", type=int, default=500,
                    help="fail if the total exceeds this (default 500)")
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
    name_coverage(wadis, "wadis")
    write(out, "wadis", wadis, keep=("name_ar", "name_en", "waterway", "intermittent"),
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
    write(out, "places", poi, keep=("name_ar", "name_en", "kind"), report=report)

    # --- the project's own geometry ----------------------------------------
    # These exist because /api/v1/catchments returns attributes plus a single
    # lon/lat point and no polygon at all, and /api/v1/reef-zones is not
    # implemented. Raised as Day-1 ask #8; committed here so the map is not
    # blocked on it, and so the offline pack has them either way.
    write(out, "catchments", gpd.read_file(V / "catchments.gpkg", layer="catchments"),
          keep=("catchment_id", "outlet_id", "area_km2", "provisional"), report=report)

    reef = gpd.read_file(V / "reef_zones_PROVISIONAL.gpkg", layer="reef_zones")
    write(out, "reef_zones", reef,
          keep=("reef_zone_id", "zone_name", "area_km2", "marine_park_overlap_pct",
                "sensitivity_weight", "sensitivity_weight_status", "provisional"),
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
