"""M2 - Re-run the delineation on NASA SRTM and compare outlet positions.

A delineation error looks exactly like a correct result. Running the same
chain on a second elevation model is the check: where the two agree, the
outlet is probably right; where they diverge, the terrain is ambiguous or one
DEM has an artifact.

  ours       Copernicus GLO-30   TanDEM-X, 2011-2015
  this       NASA SRTM 1 arc-sec  shuttle radar, 2000

Independent missions eleven years apart. SRTM shares a lineage with
HydroRIVERS (used in 08), so this is not a third independent opinion on the
inland network - its value is at the coast, where GLO-30's surface-model
artifacts hurt most and where HydroRIVERS is far too coarse to help.

SRTM is reprojected onto the exact GLO-30 grid so every comparison is
cell-for-cell rather than resampled twice.

Outputs
    data/interim/srtm/           parallel hydrology chain
    reports/srtm/README.md
    reports/srtm/outlet_comparison.csv
"""

import sys
import urllib.request
import gzip
import shutil
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import whitebox
from rasterio.merge import merge
from rasterio.warp import Resampling, reproject
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hydro_common import read_dem, sea_mask  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REF_DEM = ROOT / "data/processed/dem/dem_utm36n.tif"
RAW = ROOT / "data/raw/srtm"
WORK = ROOT / "data/interim/srtm"
OUTDIR = ROOT / "reports/srtm"
OUTLETS = ROOT / "data/processed/vectors/outlets.gpkg"

SKADI = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/{lat}/{tile}.hgt.gz"
TILES = ["N29E034", "N29E035", "N30E034", "N30E035"]
NODATA = -9999.0
STREAM_THRESHOLD = 900
MIN_OUTLET_KM2 = 0.5
SRTM_VOID = -32768


def fetch_srtm():
    RAW.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in TILES:
        hgt = RAW / f"{t}.hgt"
        if not hgt.exists():
            gz = RAW / f"{t}.hgt.gz"
            url = SKADI.format(lat=t[:3], tile=t)
            print(f"  get {t} ...", flush=True)
            urllib.request.urlretrieve(url, gz)
            with gzip.open(gz, "rb") as f_in, open(hgt, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            gz.unlink()
        else:
            print(f"  have {t}")
        paths.append(hgt)
    return paths


def build_srtm_on_ref_grid(paths):
    """Mosaic SRTM and warp it onto the exact GLO-30 grid."""
    srcs = [rasterio.open(p) for p in paths]
    mosaic, transform = merge(srcs)
    src_crs = srcs[0].crs
    for s in srcs:
        s.close()

    arr = mosaic[0].astype("float32")
    arr[arr == SRTM_VOID] = np.nan
    voids = int(np.isnan(arr).sum())
    print(f"  SRTM voids in mosaic: {voids:,}")
    arr = np.where(np.isnan(arr), NODATA, arr)

    with rasterio.open(REF_DEM) as ref:
        prof = ref.profile.copy()
        dst = np.full((ref.height, ref.width), NODATA, dtype="float32")
        reproject(
            source=arr, destination=dst,
            src_transform=transform, src_crs=src_crs, src_nodata=NODATA,
            dst_transform=ref.transform, dst_crs=ref.crs, dst_nodata=NODATA,
            resampling=Resampling.bilinear,
        )
    prof.update(dtype="float32", nodata=NODATA, compress="deflate", tiled=True)
    prof.pop("predictor", None)
    out = WORK / "srtm_utm36n.tif"
    with rasterio.open(out, "w", **prof) as d:
        d.write(dst, 1)
    return out


def run(wbt, label, out_name, fn, *args, **kwargs):
    target = WORK / out_name
    print(f"  {label} ...", flush=True)
    fn(*args, **kwargs)
    if not target.exists():
        raise SystemExit(f"whitebox failed at '{label}'")
    return target


def discharge_points(accum, streams, sea, valid, cell_km2, min_km2):
    import collections
    h, w = accum.shape
    cand = streams & ~sea & valid
    touches = np.zeros_like(cand)
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        sh = np.zeros_like(sea)
        r0, r1 = max(0, dr), min(h, h + dr)
        c0, c1 = max(0, dc), min(w, w + dc)
        sh[r0:r1, c0:c1] = sea[r0 - dr:r1 - dr, c0 - dc:c1 - dc]
        touches |= sh
    cand &= touches

    seen = np.zeros_like(cand)
    groups = []
    for r, c in zip(*np.where(cand)):
        if seen[r, c]:
            continue
        q, cells = collections.deque([(r, c)]), []
        seen[r, c] = True
        while q:
            rr, cc = q.popleft()
            cells.append((rr, cc))
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    a, b = rr + dr, cc + dc
                    if 0 <= a < h and 0 <= b < w and cand[a, b] and not seen[a, b]:
                        seen[a, b] = True
                        q.append((a, b))
        best = max(cells, key=lambda rc: accum[rc])
        groups.append((best, float(accum[best]) * cell_km2))
    groups.sort(key=lambda t: -t[1])
    return [g for g in groups if g[1] >= min_km2]


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    OUTDIR.mkdir(parents=True, exist_ok=True)

    print("fetching SRTM ...")
    paths = fetch_srtm()
    print("\nwarping onto the GLO-30 grid ...")
    srtm = build_srtm_on_ref_grid(paths)

    arr, valid, prof = read_dem(srtm)
    with rasterio.open(srtm) as r:
        transform, crs = r.transform, r.crs
        cell = abs(r.res[0])
    cell_km2 = cell * cell / 1e6

    print("\nsea mask ...")
    sea = sea_mask(arr, valid, transform, crs)
    print(f"  Gulf: {sea.sum() * cell_km2:,.1f} km2   (GLO-30 gave 623.0)")

    land = np.where(valid & ~sea, arr, NODATA).astype("float32")
    lprof = {**prof, "dtype": "float32", "compress": "deflate", "tiled": True}
    lprof.pop("predictor", None)
    with rasterio.open(WORK / "dem_land.tif", "w", **lprof) as d:
        d.write(land, 1)

    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(str(WORK))
    wbt.set_verbose_mode(False)

    print("\nhydrology chain (fill=False, as in 05):")
    run(wbt, "breach depressions", "dem_breached.tif",
        wbt.breach_depressions_least_cost, "dem_land.tif", "dem_breached.tif",
        dist=200, fill=False)
    run(wbt, "d8 pointer", "d8_pointer.tif",
        wbt.d8_pointer, "dem_breached.tif", "d8_pointer.tif")
    run(wbt, "d8 accumulation", "d8_accum.tif",
        wbt.d8_flow_accumulation, "dem_breached.tif", "d8_accum.tif", out_type="cells")
    run(wbt, "extract streams", "streams.tif",
        wbt.extract_streams, "d8_accum.tif", "streams.tif", STREAM_THRESHOLD)

    with rasterio.open(WORK / "d8_accum.tif") as r:
        accum = r.read(1)
    with rasterio.open(WORK / "streams.tif") as r:
        streams = r.read(1) > 0

    print(f"\n  max contributing area: {accum.max() * cell_km2:,.0f} km2"
          f"   (GLO-30 gave 4,453)")

    print("\nfinding discharge points ...")
    pts = discharge_points(accum, streams, sea, valid, cell_km2, MIN_OUTLET_KM2)
    print(f"  {len(pts)} points >= {MIN_OUTLET_KM2} km2   (GLO-30 gave 72)")

    xs, ys, areas = [], [], []
    with rasterio.open(srtm) as r:
        for (rr, cc), km2 in pts:
            x, y = r.xy(rr, cc)
            xs.append(x); ys.append(y); areas.append(km2)
    srtm_pts = gpd.GeoDataFrame(
        {"srtm_km2": areas}, geometry=[Point(x, y) for x, y in zip(xs, ys)], crs=crs
    )

    # ---- compare against the GLO-30 outlets -----------------------------
    ours = gpd.read_file(OUTLETS, layer="outlets").to_crs(crs)
    rows = []
    # Match on the LARGEST SRTM discharge point within the search radius, not
    # the nearest. Wadi Yutum's mouth has a 1.9 km2 gully a few cells away, and
    # nearest-point matching picked that instead of the 2,561 km2 trunk 600 m
    # off - reporting a -100% area difference where the real answer is -42%.
    MATCH_RADIUS_M = 1500
    for _, o in ours.iterrows():
        d = srtm_pts.distance(o.geometry)
        near = srtm_pts[d <= MATCH_RADIUS_M]
        if near.empty:
            i = int(d.idxmin())
        else:
            i = int(near.srtm_km2.idxmax())
        rows.append({
            "outlet_id": o.outlet_id,
            "glo30_km2": round(o.upstream_km2, 2),
            "srtm_km2": round(srtm_pts.srtm_km2.iloc[i], 2),
            "area_diff_pct": round(
                (srtm_pts.srtm_km2.iloc[i] - o.upstream_km2) / o.upstream_km2 * 100, 1),
            "outlet_shift_m": round(float(d.iloc[i]), 0),
            "position_confidence": o.position_confidence,
        })
    cmp = pd.DataFrame(rows)
    cmp.to_csv(OUTDIR / "outlet_comparison.csv", index=False)

    print("\nGLO-30 vs SRTM at each outlet:\n")
    print(cmp.to_string(index=False))
    print(f"\nwrote {(OUTDIR / 'outlet_comparison.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
