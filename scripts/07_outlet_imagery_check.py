"""M1 (part 4) - Visual check of DEM-derived outlets against satellite imagery.

GLO-30 is a surface model: buildings, walls and road embankments sit in the
elevation values. The outlets land in the most built-up part of Aqaba, so the
routed channel can run around a structure that water actually passes under.
This renders each outlet on Esri World Imagery with the DEM stream network on
top, so the two can be compared by eye.

What to look for
    - does the modelled channel follow the visible wadi bed?
    - does the mouth sit where the wadi actually meets the water?
    - is the channel routed around a building or embankment?
    - is the outlet on the correct side of a port or breakwater?

Output: reports/outlets/<outlet_id>.png  plus a contact sheet
"""

import math
import sys
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from PIL import Image, ImageDraw
from pyproj import Transformer

ROOT = Path(__file__).resolve().parent.parent
OUTLETS = ROOT / "data/processed/vectors/outlets.gpkg"
STREAMS = ROOT / "data/interim/hydro/streams.tif"
ACCUM = ROOT / "data/interim/hydro/d8_accum.tif"
OUTDIR = ROOT / "reports/outlets"

TILE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
UA = "ReefShield-Aqaba/1.0 (hackathon; outlet verification)"
ZOOM = 16
SPAN_M = 1600          # box side around the outlet
MIN_ACCUM_CELLS = 200  # only draw meaningful channels


def deg2tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    la = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(la)) / math.pi) / 2.0 * n
    return x, y


def tile2deg(x, y, z):
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def fetch_tile(z, x, y, cache):
    p = cache / f"{z}_{x}_{y}.jpg"
    if p.exists():
        return Image.open(p).convert("RGB")
    url = TILE.format(z=z, x=x, y=y)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        p.write_bytes(r.read())
    return Image.open(p).convert("RGB")


def mosaic(lon, lat, z, span_m, cache):
    """Tile mosaic centred on lon/lat, plus a lon/lat -> pixel function."""
    m_per_px = 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)
    half_px = (span_m / m_per_px) / 2
    cx, cy = deg2tile(lon, lat, z)
    x0 = int(math.floor(cx - half_px / 256))
    x1 = int(math.ceil(cx + half_px / 256))
    y0 = int(math.floor(cy - half_px / 256))
    y1 = int(math.ceil(cy + half_px / 256))

    img = Image.new("RGB", ((x1 - x0) * 256, (y1 - y0) * 256))
    for tx in range(x0, x1):
        for ty in range(y0, y1):
            try:
                img.paste(fetch_tile(z, tx, ty, cache), ((tx - x0) * 256, (ty - y0) * 256))
            except Exception as e:  # missing tile is not fatal
                print(f"    tile {z}/{tx}/{ty} failed: {e}")

    def to_px(ln, lt):
        tx, ty = deg2tile(ln, lt, z)
        return (tx - x0) * 256, (ty - y0) * 256

    # crop to the requested span around the centre
    px, py = to_px(lon, lat)
    box = (int(px - half_px), int(py - half_px), int(px + half_px), int(py + half_px))
    crop = img.crop(box)

    def to_px_cropped(ln, lt):
        a, b = to_px(ln, lt)
        return a - box[0], b - box[1]

    return crop, to_px_cropped, m_per_px


def main():
    if not OUTLETS.exists():
        raise SystemExit(f"missing {OUTLETS} - run scripts/06_catchments.py first")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    cache = ROOT / "data/interim/tiles"
    cache.mkdir(parents=True, exist_ok=True)

    outl = gpd.read_file(OUTLETS, layer="outlets").to_crs(4326)

    with rasterio.open(STREAMS) as s:
        streams = s.read(1) > 0
        s_transform, s_crs = s.transform, s.crs
    with rasterio.open(ACCUM) as a:
        accum = a.read(1)

    to_wgs = Transformer.from_crs(s_crs, 4326, always_xy=True)
    panels = []

    for _, row in outl.iterrows():
        lon, lat = row.lon, row.lat
        print(f"{row.outlet_id}  {lon:.5f}, {lat:.5f}")
        img, to_px, m_per_px = mosaic(lon, lat, ZOOM, SPAN_M, cache)
        d = ImageDraw.Draw(img, "RGBA")

        # stream cells within the view
        inv = ~s_transform
        tf_fwd = Transformer.from_crs(4326, s_crs, always_xy=True)
        cx, cy = tf_fwd.transform(lon, lat)
        half = SPAN_M / 2 * 1.3
        c0, r0 = (int(v) for v in inv * (cx - half, cy + half))
        c1, r1 = (int(v) for v in inv * (cx + half, cy - half))
        r0, r1 = max(0, r0), min(streams.shape[0], r1)
        c0, c1 = max(0, c0), min(streams.shape[1], c1)
        sub = streams[r0:r1, c0:c1] & (accum[r0:r1, c0:c1] >= MIN_ACCUM_CELLS)
        rr, cc = np.where(sub)
        for r, c in zip(rr, cc):
            x, y = s_transform * (c0 + c + 0.5, r0 + r + 0.5)
            ln, lt = to_wgs.transform(x, y)
            px, py = to_px(ln, lt)
            a_val = accum[r0 + r, c0 + c]
            rad = 1.5 if a_val < 5000 else (2.5 if a_val < 100000 else 4)
            d.ellipse([px - rad, py - rad, px + rad, py + rad],
                      fill=(0, 200, 255, 190))

        # outlet marker
        px, py = to_px(lon, lat)
        for rad, col in ((16, (255, 60, 0, 255)), (5, (255, 255, 255, 255))):
            d.ellipse([px - rad, py - rad, px + rad, py + rad], outline=col, width=3)

        # scale bar
        bar = int(200 / m_per_px)
        w, h = img.size
        d.rectangle([12, h - 34, 12 + bar, h - 28], fill=(255, 255, 255, 230))
        d.text((12, h - 52), "200 m", fill=(255, 255, 255, 255))
        d.text((12, 12), f"{row.outlet_id}  {row.catchment_id}  "
                         f"{row.upstream_km2:,.1f} km2", fill=(255, 255, 0, 255))

        # JPEG, not PNG: these are satellite photographs and the lossless
        # version is ~5x larger for no visible gain in the annotations.
        out = OUTDIR / f"{row.outlet_id}.jpg"
        img.save(out, quality=88, optimize=True)
        panels.append((row.outlet_id, img))
        print(f"    wrote {out.relative_to(ROOT)}  ({img.size[0]}x{img.size[1]})")

    # contact sheet
    if panels:
        tw = min(p[1].size[0] for p in panels)
        thumbs = [p[1].resize((tw, tw)) for p in panels]
        sheet = Image.new("RGB", (tw * len(thumbs), tw))
        for i, t in enumerate(thumbs):
            sheet.paste(t, (i * tw, 0))
        sheet.thumbnail((2400, 2400))
        sheet.save(OUTDIR / "_contact_sheet.jpg", quality=85, optimize=True)
        print(f"\nwrote {(OUTDIR / '_contact_sheet.jpg').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
