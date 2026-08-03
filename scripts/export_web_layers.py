"""Export the map layers as GeoJSON for the frontend.

MapLibre cannot read a GeoPackage. Everything in data/processed/vectors/ is .gpkg
except outlets.geojson, so the frontend had no loadable copy of the catchments, the
reef zones, the coastline or the optional OSM layers — the map's entire base.

Two rules this script exists to enforce:

  - **EPSG:4326 for the web, always.** MapLibre expects lon/lat. Areas and distances
    were already computed in EPSG:32636 upstream and travel as attributes, so
    reprojecting here loses nothing; recomputing them here in degrees would be wrong.
  - **Nothing is simplified by default.** A simplified boundary is a different claim
    about where a catchment is. `--simplify` exists for the two layers where browser
    payload genuinely matters (roads, buildings), and it records the tolerance in the
    output so a reader knows the geometry was altered.

Run:  ../.venv/bin/python export_web_layers.py
Out:  data/processed/web/<name>.geojson  (git-ignored — regenerate, do not commit)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VECTORS = PROJECT_ROOT / "data" / "processed" / "vectors"
OUT_DIR = PROJECT_ROOT / "data" / "processed" / "web"

WEB_CRS = "EPSG:4326"

#: (source file, layer, output name). Layers the map needs to draw.
LAYERS = [
    ("catchments.gpkg", "catchments", "catchments"),
    ("reef_zones.gpkg", "reef_zones", "reef_zones"),
    ("coastline.gpkg", "shoreline", "shoreline"),
    ("coastline.gpkg", "water", "water"),
    ("observed_plume.gpkg", "observed_plume", "observed_plume_PROVISIONAL"),
    # Optional layers his task file names explicitly.
    ("osm_aqaba.gpkg", "protected_areas", "marine_park"),
    ("osm_aqaba.gpkg", "dive_tourism_poi", "dive_sites"),
    # NOT named "culverts": this layer is 200 drainage features, of which only 27 are
    # tagged culverts. Calling the file culverts.geojson would put a wrong count on
    # screen and in the Q&A.
    ("osm_aqaba.gpkg", "drainage_features", "drainage_features"),
    ("osm_aqaba.gpkg", "port", "port"),
]

#: Layers heavy enough that a browser notices. Only these accept --simplify.
HEAVY = {"roads", "buildings"}
OPTIONAL_HEAVY = [
    ("osm_aqaba.gpkg", "roads", "roads"),
    ("osm_aqaba.gpkg", "buildings", "buildings"),
]


def export(gdf, name: str, source: str, layer: str, simplify_m: float | None) -> dict:
    import geopandas as gpd  # noqa: F401

    original_crs = str(gdf.crs)
    note = None
    if simplify_m:
        # Simplify in metres, then go back to degrees. Simplifying in degrees applies a
        # different real-world tolerance at every latitude.
        gdf = gdf.to_crs("EPSG:32636")
        gdf["geometry"] = gdf.geometry.simplify(simplify_m, preserve_topology=True)
        note = f"geometry simplified with a {simplify_m} m tolerance in EPSG:32636"

    gdf = gdf.to_crs(WEB_CRS)
    path = OUT_DIR / f"{name}.geojson"
    gdf.to_file(path, driver="GeoJSON")

    kb = path.stat().st_size / 1024
    print(f"  {name:28s} {len(gdf):6d} feature(s)  {kb:8.1f} KB"
          + (f"  [{note}]" if note else ""))
    return {
        "name": name,
        "file": f"data/processed/web/{name}.geojson",
        "source": f"{source}:{layer}",
        "features": int(len(gdf)),
        "size_kb": round(kb, 1),
        "crs": WEB_CRS,
        "source_crs": original_crs,
        "geometry_note": note or "unaltered — no simplification applied",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simplify", type=float, default=None, metavar="METRES",
                        help=f"simplify only {sorted(HEAVY)} by this tolerance in metres")
    parser.add_argument("--include-heavy", action="store_true",
                        help="also export roads and buildings (large)")
    args = parser.parse_args()

    try:
        import geopandas as gpd
    except ImportError:
        sys.exit("geopandas not installed: .venv/bin/pip install geopandas")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    todo = list(LAYERS) + (OPTIONAL_HEAVY if args.include_heavy else [])

    print(f"exporting to {OUT_DIR.relative_to(PROJECT_ROOT)}/ in {WEB_CRS}")
    manifest, skipped = [], []
    for filename, layer, name in todo:
        src = VECTORS / filename
        if not src.exists():
            skipped.append({"name": name, "reason": f"{filename} absent"})
            print(f"  {name:28s} SKIPPED — {filename} absent")
            continue
        try:
            gdf = gpd.read_file(src, layer=layer)
        except Exception as e:
            skipped.append({"name": name, "reason": f"{type(e).__name__}: {e}"})
            print(f"  {name:28s} SKIPPED — {type(e).__name__}")
            continue
        if gdf.empty:
            # An empty layer is reported, never written as an empty file that looks
            # like a successful export.
            skipped.append({"name": name, "reason": "layer has zero features"})
            print(f"  {name:28s} SKIPPED — zero features")
            continue

        tol = args.simplify if (layer in HEAVY and args.simplify) else None
        manifest.append(export(gdf, name, filename, layer, tol))

    (OUT_DIR / "manifest.json").write_text(json.dumps({
        "generated_by": "scripts/export_web_layers.py",
        "crs": WEB_CRS,
        "note": ("Regenerate rather than commit — this directory is git-ignored. "
                 "Areas and distances in the attributes were computed in EPSG:32636 "
                 "upstream; never recompute them from these degree coordinates."),
        "layers": manifest,
        "skipped": skipped,
    }, indent=2) + "\n")

    total = sum(m["size_kb"] for m in manifest)
    print(f"\n{len(manifest)} layer(s), {total:.0f} KB total, "
          f"{len(skipped)} skipped -> manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
