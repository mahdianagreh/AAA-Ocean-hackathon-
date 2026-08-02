"""Identify endorheic basins explicitly and mask them, instead of relying on
`fill=False` as a proxy for them.

The problem this replaces
-------------------------
`breach_depressions_least_cost(fill=False)` leaves closed depressions
unbreached, which approximately preserves endorheic basins. But whether a
given depression survives depends on its depth against the DEM's noise floor,
so the answer moves with the DEM:

    Wadi Yutum contributing area   fill=False   fill=True
      Copernicus GLO-30               4,453       6,282
      NASA SRTM                       2,561       6,413

Same terrain, same method, 1.7x apart. With fill=True the two agree within
2%, which shows the terrain is not in dispute - the conditioning flag is.

The method here
---------------
1. Fill depressions, and take (filled - original) as depression depth.
2. Label connected depressions and keep those above an area AND depth
   threshold. Below it is DEM noise; above it is a real closed basin.
3. SELECTIVE conditioning: use the filled surface everywhere except the
   depressions kept in step 2, which are restored to their original
   elevation. Flow now routes normally across DEM noise but still terminates
   inside the genuine closed basins.
4. Walk the D8 network upstream from those basins. This is the step that
   matters: the sink floors total ~385 km2, but the terrain draining into
   them is several times that, and none of it reaches the sea.
5. Mask that area out, then condition the remainder with fill=True - safe
   now, because the genuine closed basins are already gone.

Step 3 is why the first attempt failed. Filling everything and then tracing
from sink points returns almost nothing: the fill destroys the sinks, so
there is no longer anything draining into them.

The test of whether this worked is not the number itself. It is whether
GLO-30 and SRTM converge, since a deterministic method should not care which
DEM it runs on.

Usage
    .venv/bin/python scripts/10_endorheic_mask.py
    .venv/bin/python scripts/10_endorheic_mask.py --work data/interim/srtm
    .venv/bin/python scripts/10_endorheic_mask.py --min-area 2 --min-depth 5
"""

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import whitebox
from scipy import ndimage
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parent.parent

MIN_DEPRESSION_KM2 = 1.0   # smaller than this is DEM noise, not a playa
MIN_DEPRESSION_M = 2.0     # shallower than this is vertical error
FILL_FLOOR_M = 0.5         # ignore fill below this when labelling


# WhiteboxTools D8 encoding: the value is the direction flow LEAVES a cell.
D8 = {1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1),
      16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)}


def upstream_of(seed, ptr, valid):
    """Every cell whose flow path eventually reaches `seed`.

    Builds the downstream index once, inverts it with an argsort, then does a
    single BFS. Iterating "grow the set until it stops changing" over a
    17-million-cell grid would be correct but far too slow.
    """
    h, w = ptr.shape
    n = h * w
    rows, cols = np.divmod(np.arange(n), w)

    ds = np.full(n, -1, dtype="int64")
    for code, (dr, dc) in D8.items():
        m = (ptr.ravel() == code)
        if not m.any():
            continue
        rr, cc = rows[m] + dr, cols[m] + dc
        ok = (rr >= 0) & (rr < h) & (cc >= 0) & (cc < w)
        idx = np.flatnonzero(m)
        ds[idx[ok]] = rr[ok] * w + cc[ok]

    # invert: sort by downstream target so all upstream cells of a target sit
    # in one contiguous run
    has_ds = ds >= 0
    src = np.flatnonzero(has_ds)
    tgt = ds[src]
    order = np.argsort(tgt, kind="stable")
    src_sorted, tgt_sorted = src[order], tgt[order]

    from collections import deque
    seen = np.zeros(n, dtype=bool)
    q = deque(np.flatnonzero(seed.ravel()).tolist())
    for i in q:
        seen[i] = True
    while q:
        cur = q.popleft()
        lo = np.searchsorted(tgt_sorted, cur, "left")
        hi = np.searchsorted(tgt_sorted, cur, "right")
        for j in src_sorted[lo:hi]:
            if not seen[j]:
                seen[j] = True
                q.append(int(j))
    return seen.reshape(h, w) & valid


def wbt_for(work):
    w = whitebox.WhiteboxTools()
    w.set_working_dir(str(work))
    w.set_verbose_mode(False)
    return w


def need(work, name, wbt, fn, *args, **kwargs):
    p = work / name
    if not p.exists():
        print(f"  {name} ...", flush=True)
        fn(*args, **kwargs)
        if not p.exists():
            raise SystemExit(f"whitebox failed to write {name}")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="data/interim/hydro")
    ap.add_argument("--min-area", type=float, default=MIN_DEPRESSION_KM2)
    ap.add_argument("--min-depth", type=float, default=MIN_DEPRESSION_M)
    args = ap.parse_args()

    work = ROOT / args.work
    land = work / "dem_land.tif"
    if not land.exists():
        raise SystemExit(f"missing {land}")
    print(f"work dir: {args.work}")

    wbt = wbt_for(work)

    with rasterio.open(land) as r:
        orig = r.read(1)
        nd = r.nodata
        prof = r.profile.copy()
        transform, crs = r.transform, r.crs
        px = abs(r.res[0] * r.res[1]) / 1e6
    valid = orig != nd

    # ---- 1-2. find real closed depressions ------------------------------
    need(work, "dem_filled.tif", wbt, wbt.fill_depressions,
         dem="dem_land.tif", output="dem_filled.tif")
    with rasterio.open(work / "dem_filled.tif") as r:
        filled = r.read(1)
    depth = np.where(valid, filled - orig, 0.0)

    lab, n = ndimage.label(depth > FILL_FLOOR_M)
    idx = np.arange(1, n + 1)
    sizes = ndimage.sum_labels(np.ones_like(lab, dtype="float32"), lab, idx) * px
    depths = ndimage.maximum(depth, lab, idx)
    keep = idx[(sizes >= args.min_area) & (depths >= args.min_depth)]
    print(f"\n{n:,} depressions; {len(keep)} above "
          f"{args.min_area} km2 and {args.min_depth} m")
    print(f"  their floors: {sizes[keep - 1].sum():,.1f} km2")

    if len(keep) == 0:
        raise SystemExit("no depressions passed the threshold")

    sig = np.isin(lab, keep)
    pos = ndimage.maximum_position(depth, lab, keep)
    gpd.GeoDataFrame(
        {"sink_id": range(1, len(keep) + 1),
         "floor_km2": sizes[keep - 1].round(2),
         "depth_m": depths[keep - 1].round(1)},
        geometry=[Point(*rasterio.transform.xy(transform, r, c)) for r, c in pos],
        crs=crs,
    ).to_file(work / "sinks.shp")

    # ---- 3. selective conditioning --------------------------------------
    # Filled surface everywhere except the real basins, which keep their
    # original elevation so flow still terminates inside them.
    sel = np.where(valid, np.where(sig, orig, filled), nd).astype("float32")
    sprof = {**prof, "dtype": "float32", "compress": "deflate", "tiled": True}
    sprof.pop("predictor", None)
    with rasterio.open(work / "dem_selective.tif", "w", **sprof) as d:
        d.write(sel, 1)

    for f in ("d8_selective.tif",):
        (work / f).unlink(missing_ok=True)
    print("  d8 on the selectively conditioned DEM ...", flush=True)
    wbt.d8_pointer(dem="dem_selective.tif", output="d8_selective.tif")
    with rasterio.open(work / "d8_selective.tif") as r:
        ptr = r.read(1)

    # ---- 4. walk upstream from the basins -------------------------------
    print("  walking the D8 network upstream ...", flush=True)
    endo = upstream_of(sig, ptr, valid)
    print(f"\nendorheic area: {endo.sum() * px:,.1f} km2 "
          f"({endo.sum() / valid.sum() * 100:.1f}% of land)")
    print(f"  HydroBASINS says 1,767 km2 for the Wadi Yutum system")

    mprof = {**prof, "dtype": "uint8", "nodata": 0, "compress": "deflate"}
    mprof.pop("predictor", None)
    with rasterio.open(work / "endorheic_mask.tif", "w", **mprof) as d:
        d.write(endo.astype("uint8"), 1)

    # ---- 4. condition the exorheic remainder ----------------------------
    exo = np.where(valid & ~endo, orig, nd).astype("float32")
    eprof = {**prof, "dtype": "float32", "compress": "deflate", "tiled": True}
    eprof.pop("predictor", None)
    with rasterio.open(work / "dem_exorheic.tif", "w", **eprof) as d:
        d.write(exo, 1)

    print("\nrouting the exorheic remainder (fill=True is safe now) ...")
    for f in ("exo_breached.tif", "exo_d8.tif", "exo_accum.tif"):
        (work / f).unlink(missing_ok=True)
    wbt.breach_depressions_least_cost(dem="dem_exorheic.tif",
                                      output="exo_breached.tif", dist=200, fill=True)
    wbt.d8_pointer(dem="exo_breached.tif", output="exo_d8.tif")
    wbt.d8_flow_accumulation(i="exo_breached.tif", output="exo_accum.tif",
                             out_type="cells")
    with rasterio.open(work / "exo_accum.tif") as r:
        acc = r.read(1)
    print(f"\nmax contributing area: {acc.max() * px:,.0f} km2")


if __name__ == "__main__":
    main()
