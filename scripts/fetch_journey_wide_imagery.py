"""Bake a third, wider satellite basemap for the 3D Journey — real ground for
the area a user's own free camera movement can reach beyond `TERRAIN_AOI`.

WHY A THIRD BAKE (this project now has four bakes total across two scenes)
------------------------------------------------------------------------------
`fetch_journey_imagery.py` covers exactly `TERRAIN_AOI` — correct for the
scripted camera, which never leaves it, but a real user can zoom out or pan
past that edge (`layers/terrain.ts`'s own `TERRAIN_MIN_ZOOM` doc has the full
story: the terrain-rgb tile pyramid, and hillshade/colour-relief reading it,
render that void as stretched garbage, not blankness). A flat colour mask
(`terrainVoidMaskFragment`, same file) hides the glitch but reads as an odd
empty rectangle once a user zooms out far enough to see it. This bakes real
Esri WorldImagery over a generously padded box around `TERRAIN_AOI` instead,
so what a user actually sees beyond the sharp AOI is real ground, coarser but
real — the same standard this project holds every other layer to. The colour
mask stays as the last-resort fallback *beyond even this* wider image, for
whatever a camera angle this padding didn't anticipate.

Deliberately flat, not draped on a matching terrain-rgb mesh: no DEM/
bathymetry was ever fetched for this padded ring (that would be a fourth,
much larger hydrology-grade download this project has no use for outside
this one cosmetic gap), so this image gets the same visual treatment
`layers/imagery.ts` already gives both existing bakes — a plain `raster`
layer, not a new elevation source.

Run once (needs network):
    ../.venv/bin/python fetch_journey_wide_imagery.py
    ../.venv/bin/python fetch_journey_wide_imagery.py --pad 1.5 --zoom 10

Output (git-ignored, regenerate rather than commit):
    data/processed/basemap/aqaba_journey_wide_esri.jpg
    data/processed/basemap/aqaba_journey_wide_esri.json

Then copy into the frontend's public dir, same as the other three bakes:
    cp data/processed/basemap/aqaba_journey_wide_esri.{jpg,json} \\
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
STEM = "aqaba_journey_wide_esri"
WEB_MERCATOR = "EPSG:3857"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--zoom", type=int, default=9,
                        help="tile zoom. 9 is ~230-280 m/px over this much larger box -- "
                             "coarse, but this layer is background context beyond the "
                             "sharp AOI image, not a hero shot")
    parser.add_argument("--pad", type=float, default=1.2,
                        help="fraction of TERRAIN_AOI's own width/height added on every "
                             "side. 1.2 roughly triples the total extent -- covers what a "
                             "pitch-60-70, min-zoom camera can see past the AOI edge "
                             "(measured empirically fixing the zoom-out glitch), without "
                             "trying to bake enough to cover literally every angle")
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
    print(f"fetching Esri WorldImagery (wide)  lon {w:.4f}..{e:.4f}  lat {s:.4f}..{n:.4f}  "
          f"zoom {args.zoom}")

    img, extent = cx.bounds2img(w, s, e, n, zoom=args.zoom,
                                 source=cx.providers.Esri.WorldImagery, ll=True)

    if img.shape[0] > 8000 or img.shape[1] > 8000:
        sys.exit(f"wide image is {img.shape[1]}x{img.shape[0]}px -- too close to the "
                 f"WebGL texture ceiling (~8192px/side). Raise --zoom's negative or "
                 f"lower --pad and retry.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{STEM}.jpg"
    Image.fromarray(img[:, :, :3]).save(png, quality=85, optimize=True, progressive=True)

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
        "aoi_source": "config.spatial.TERRAIN_AOI, padded (not draped on any terrain mesh)",
        "provider": "Esri WorldImagery",
        "attribution": "Esri, Maxar, Earthstar Geographics, and the GIS User Community",
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "why": ("Real ground for the area a free-roaming camera can reach beyond the "
                "sharp TERRAIN_AOI bake, replacing a flat colour mask there. Baked once "
                "so rendering needs no network. Regenerate rather than commit."),
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
