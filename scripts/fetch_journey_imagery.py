"""Bake one satellite basemap for the 3D Journey's terrain drape.

WHY A SECOND BAKE, NOT A REUSE OF fetch_basemap_raster.py's OUTPUT
--------------------------------------------------------------------
`fetch_basemap_raster.py` bakes Esri WorldImagery over `MARINE_AOI` (the sea
strip, ~27 x 33 km) for the 2D plume map — that map never shows land far from
the coast, so a tight crop is correct there. The 3D Journey's terrain mesh
(`scripts/merge_terrain_bathymetry.py`) covers the full `TERRAIN_AOI` (land,
~115 x 128 km, mountains included) and the camera's opening shot (zoom 9.6)
frames most of it, not just the coastal strip. Draping the marine-only image
onto that mesh would leave every mountain textured by the colour-relief
fallback (`layers/terrain.ts`) and only the coastal sliver photo-real — a
visible seam, not a design choice. This bakes the same real, never-generated
Esri WorldImagery (`docs/plume_imagery_decision.md`) over the larger extent
instead, as its own file, so the two use cases can each keep the crop that's
actually right for them.

Run once (needs network):
    ../.venv/bin/python fetch_journey_imagery.py
    ../.venv/bin/python fetch_journey_imagery.py --zoom 13

Output (git-ignored, regenerate rather than commit):
    data/processed/basemap/aqaba_terrain_esri.jpg
    data/processed/basemap/aqaba_terrain_esri.json

Then copy into the frontend's public dir (layers/imagery.ts's own docstring
covers why this second, browser-reachable copy is needed):
    cp data/processed/basemap/aqaba_terrain_esri.{jpg,json} \\
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
STEM = "aqaba_terrain_esri"

WEB_MERCATOR = "EPSG:3857"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zoom", type=int, default=13,
                        help="tile zoom. 13 is ~17 m/px here -- crisp enough for the "
                             "journey's closest camera (zoom ~12.5) without the tile "
                             "count of z14 over an AOI this much larger than the marine one")
    parser.add_argument("--pad", type=float, default=0.0,
                        help="fraction of the AOI added on every side (0 = exactly "
                             "TERRAIN_AOI; the mesh doesn't extend past it either)")
    args = parser.parse_args()

    try:
        import contextily as cx
    except ImportError:
        sys.exit("contextily not installed: .venv/bin/pip install contextily")
    from PIL import Image

    from config.spatial import TERRAIN_AOI

    w, s, e, n = TERRAIN_AOI.wsen
    dx, dy = (e - w) * args.pad, (n - s) * args.pad
    w, s, e, n = w - dx, s - dy, e + dx, n + dy
    print(f"fetching Esri WorldImagery  lon {w:.4f}..{e:.4f}  lat {s:.4f}..{n:.4f}  "
          f"zoom {args.zoom}")

    img, extent = cx.bounds2img(w, s, e, n, zoom=args.zoom,
                                 source=cx.providers.Esri.WorldImagery, ll=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{STEM}.jpg"
    # Same q88 JPEG choice as fetch_basemap_raster.py, same reasoning: photographic
    # imagery loses nothing visible to lossy compression at this resolution, and this
    # file ships inside a container that has to run on a judge's laptop.
    Image.fromarray(img[:, :, :3]).save(png, quality=88, optimize=True, progressive=True)

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
        "pad_fraction": args.pad,
        "aoi_source": "config.spatial.TERRAIN_AOI, padded",
        "provider": "Esri WorldImagery",
        "attribution": "Esri, Maxar, Earthstar Geographics, and the GIS User Community",
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "why": ("Baked once so rendering needs no network. Regenerate rather than "
                "commit; it is derived and large."),
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
