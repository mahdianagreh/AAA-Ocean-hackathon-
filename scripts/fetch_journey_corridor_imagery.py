"""Bake a second, sharper satellite basemap for the 3D Journey's closer camera
phases (flood, sediment transport, accumulation, coastal impact).

WHY A THIRD BAKE (this project now has three: MARINE_AOI for the 2D plume map,
TERRAIN_AOI for the journey's wide establishing shots, and this one)
------------------------------------------------------------------------------
`fetch_journey_imagery.py` covers the full `TERRAIN_AOI` at zoom 12 (~38 m/px)
so it survives as one WebGL texture (a zoom-13 attempt at that extent decoded
to 7168x8192px and the browser refused to load it — a real failure hit this
session, not a hypothetical one). That resolution is fine for the opening wide
shot, but every closer phase's camera sits over one small area near the
release outlet, and 38 m/px reads as soft there. This bakes a second image
over just that real area -- the release outlet and its catchment's real
centroid, padded -- at a much higher zoom, small enough to stay far under the
texture ceiling. `layers/imagery.ts` loads both; the corridor image is stacked
above the full-AOI one in the style, so it simply draws over the coarser
image wherever it covers, with no per-phase source-swapping logic needed.

Run once (needs network):
    ../.venv/bin/python fetch_journey_corridor_imagery.py
    ../.venv/bin/python fetch_journey_corridor_imagery.py --zoom 14

Output (git-ignored, regenerate rather than commit):
    data/processed/basemap/aqaba_journey_corridor_esri.jpg
    data/processed/basemap/aqaba_journey_corridor_esri.json

Then copy into the frontend's public dir, same as the other two bakes:
    cp data/processed/basemap/aqaba_journey_corridor_esri.{jpg,json} \\
       frontend/public/basemap-raster/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

OUT_DIR = PROJECT_ROOT / "data" / "processed" / "basemap"
STEM = "aqaba_journey_corridor_esri"
WEB_MERCATOR = "EPSG:3857"

#: Same outlet the whole 3D Journey fixture is built around
#: (frontend_journey.py's OUTLET_ID) -- not retyped as a literal there, this
#: is a second, independent script and the project's own "ask the file,
#: don't retype" rule applies to script-to-script literals too, so this is
#: read from the real committed outlets layer below, not hardcoded twice.
OUTLET_ID = "AQ-O02"

#: Degrees padded around the release outlet and its catchment's real
#: centroid -- generous enough to cover the flood/transport/accumulation/
#: impact cameras' framing (all centred on or near this outlet, per
#: Journey3D.tsx's own flyTo calls), not the whole TERRAIN_AOI.
PAD_DEG = 0.05


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zoom", type=int, default=14,
                        help="tile zoom. 14 is ~9.5 m/px here -- 4x sharper than the "
                             "full-AOI bake, and this area is small enough that even "
                             "z14 stays far under the WebGL texture-size ceiling")
    args = parser.parse_args()

    try:
        import contextily as cx
    except ImportError:
        sys.exit("contextily not installed: .venv/bin/pip install contextily")
    import geopandas as gpd
    from PIL import Image

    outlets = gpd.read_file(PROJECT_ROOT / "data" / "processed" / "vectors" / "outlets.gpkg")
    outlet = outlets[outlets["outlet_id"] == OUTLET_ID].iloc[0]
    catchments = gpd.read_file(PROJECT_ROOT / "data" / "processed" / "vectors" / "catchments.gpkg")
    catchment = catchments[catchments["outlet_id"] == OUTLET_ID].iloc[0]
    centroid = catchment.geometry.centroid

    lons = [outlet["lon"], centroid.x]
    lats = [outlet["lat"], centroid.y]
    w, e = min(lons) - PAD_DEG, max(lons) + PAD_DEG
    s, n = min(lats) - PAD_DEG, max(lats) + PAD_DEG
    print(f"corridor around outlet {OUTLET_ID}: lon {w:.4f}..{e:.4f}  lat {s:.4f}..{n:.4f}  "
          f"zoom {args.zoom}")

    img, extent = cx.bounds2img(w, s, e, n, zoom=args.zoom,
                                 source=cx.providers.Esri.WorldImagery, ll=True)

    if img.shape[0] > 8000 or img.shape[1] > 8000:
        sys.exit(f"corridor image is {img.shape[1]}x{img.shape[0]}px -- too close to the "
                 f"WebGL texture ceiling (~8192px/side). Lower --zoom and retry.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{STEM}.jpg"
    Image.fromarray(img[:, :, :3]).save(png, quality=90, optimize=True, progressive=True)

    left, right, bottom, top = extent
    meta = {
        "stem": STEM,
        "image": f"{STEM}.jpg",
        "crs": WEB_MERCATOR,
        "extent_note": "left/right/bottom/top in EPSG:3857 metres, matplotlib order",
        "left": float(left), "right": float(right),
        "bottom": float(bottom), "top": float(top),
        "width_px": int(img.shape[1]), "height_px": int(img.shape[0]),
        "zoom": args.zoom,
        "aoi_source": f"outlet {OUTLET_ID} + its catchment's real centroid, padded {PAD_DEG} deg",
        "provider": "Esri WorldImagery",
        "attribution": "Esri, Maxar, Earthstar Geographics, and the GIS User Community",
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "why": ("Sharper imagery for the journey's closer camera phases. Baked once so "
                "rendering needs no network. Regenerate rather than commit."),
    }
    (OUT_DIR / f"{STEM}.json").write_text(json.dumps(meta, indent=2) + "\n")

    mb = png.stat().st_size / 1e6
    m_per_px = (right - left) / img.shape[1]
    print(f"wrote {png.relative_to(PROJECT_ROOT)}  "
          f"{img.shape[1]}x{img.shape[0]} px, {mb:.1f} MB, {m_per_px:.1f} m/px")
    print(f"wrote {(OUT_DIR / f'{STEM}.json').relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
