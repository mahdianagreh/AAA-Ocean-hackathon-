"""Bake one satellite basemap for the marine AOI, so rendering never needs the network.

WHY A BAKED RASTER RATHER THAN LIVE TILES
-----------------------------------------
The plume map is drawn on real Esri WorldImagery. Fetching those tiles when a request
arrives would put a network call on the demo path, and DoD item 6/9 is "works with
wifi off". A tile server hiccup would then present as a broken prediction.

So this runs ONCE, online, and writes a PNG plus a small JSON sidecar carrying the
bounds it covers. `backend/src/rendering/plume_map.py` reads those two files and needs
neither contextily nor rasterio at request time — which also keeps the API image from
growing a tile stack it only uses once.

PNG + JSON rather than a GeoTIFF is deliberate for the same reason: reading a GeoTIFF
means rasterio in the api image, and all that is actually needed is an image and the
four numbers describing where its corners are.

Run once (needs network):
    ../.venv/bin/python fetch_basemap_raster.py
    ../.venv/bin/python fetch_basemap_raster.py --zoom 14 --pad 0.25

Output (git-ignored, regenerate rather than commit):
    data/processed/basemap/aqaba_marine_esri.jpg
    data/processed/basemap/aqaba_marine_esri.json
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
STEM = "aqaba_marine_esri"

WEB_MERCATOR = "EPSG:3857"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zoom", type=int, default=14,
                        help="tile zoom. 14 is ~9 m/px here — enough to read the "
                             "shoreline without a 100 MB image")
    parser.add_argument("--pad", type=float, default=0.30,
                        help="fraction of the AOI added on every side, so a plume that "
                             "spreads beyond the reef strip still lands on imagery")
    args = parser.parse_args()

    try:
        import contextily as cx
    except ImportError:
        sys.exit("contextily not installed: .venv/bin/pip install contextily")
    from PIL import Image

    from config.spatial import MARINE_AOI

    # Pad in degrees around the marine AOI. The plume can travel past the reef strip and
    # an image that stops at the AOI edge would clip exactly the interesting part.
    w, s, e, n = MARINE_AOI.wsen
    dx, dy = (e - w) * args.pad, (n - s) * args.pad
    w, s, e, n = w - dx, s - dy, e + dx, n + dy
    print(f"fetching Esri WorldImagery  lon {w:.4f}..{e:.4f}  lat {s:.4f}..{n:.4f}  "
          f"zoom {args.zoom}")

    # ll=True: bounds given in lon/lat. The returned extent is in Web Mercator, which is
    # what the renderer draws in.
    img, extent = cx.bounds2img(w, s, e, n, zoom=args.zoom,
                                source=cx.providers.Esri.WorldImagery, ll=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # JPEG, not PNG. This is photographic satellite imagery, so lossless compression buys
    # nothing and costs a great deal: the same tiles came out 59 MB as PNG and a few MB as
    # JPEG at q88, with no visible difference at 9.6 m/px. The image ships inside a
    # container that has to run on a judge's laptop, so an order of magnitude matters.
    png = OUT_DIR / f"{STEM}.jpg"
    Image.fromarray(img[:, :, :3]).save(png, quality=88, optimize=True,
                                        progressive=True)

    # contextily returns extent as (left, right, bottom, top). Stored explicitly by name
    # rather than as a bare tuple — this ordering is not the same as any of the bbox
    # orderings used elsewhere in the project, and a silent reorder here would place
    # every plume in the wrong sea.
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
        "aoi_source": "config.spatial.MARINE_AOI, padded",
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
