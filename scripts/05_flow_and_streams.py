"""Stage 1 of real catchment delineation: condition the DEM, derive flow, find
every place a stream reaches the Gulf.

Runs after P2 (04_provisional_outlets.py) and is what eventually replaces it.
Conditioning and flow accumulation are needed whatever we decide about the
catchment set, and the candidate-outlet table is the evidence for that
decision - it shows how many discharge points the 30 m DEM actually resolves
along the coast, against the two that HydroBASINS lumps it into.

Breaching rather than filling: Aqaba's wadis are long and near-flat in their
lower reaches, and sink filling turns those into lakes that then spill in an
arbitrary direction. Least-cost breaching cuts through the blocking cell
instead, which is the right model for a channel a coarse DSM has bridged.

The sea is masked out before conditioning. Left in, breaching routes flow
across the Gulf and every coastal cell reports an enormous upstream area.

Outputs (data/interim/hydro/)
    dem_land.tif          DEM with sea and nodata masked
    dem_breached.tif      conditioned
    d8_pointer.tif        flow direction
    d8_accum.tif          flow accumulation, cells
    streams.tif           extracted stream network
    sea_mask.tif          connected Gulf water body
    outlet_candidates.csv ranked discharge points with upstream area

Usage
    .venv/bin/python scripts/05_flow_and_streams.py
    .venv/bin/python scripts/05_flow_and_streams.py --stream-threshold 500
    .venv/bin/python scripts/05_flow_and_streams.py --force
"""

import argparse
import collections
import csv
import sys
from pathlib import Path

import numpy as np
import rasterio
import whitebox

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hydro_common import read_dem, sea_mask  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEM = ROOT / "data/processed/dem/dem_utm36n.tif"
WORK = ROOT / "data/interim/hydro"

# A stream needs this many upstream cells before we call it a stream.
# 900 cells x 900 m2 = 0.81 km2. Small for a humid basin, appropriate here for
# picking up the short coastal wadis HydroBASINS misses entirely.
STREAM_THRESHOLD = 900

# Report any discharge point draining at least this much, in km2.
MIN_OUTLET_KM2 = 0.5


def run(wbt, label, out_name, fn, *args, force=False, **kwargs):
    """Call a Whitebox tool and verify it actually wrote its output.

    Whitebox returns 0 even when the Rust binary panics, so a missing output
    file is the only reliable failure signal. `out_name` is explicit rather
    than sniffed from the arguments: tool signatures differ, and
    extract_streams takes its threshold in the last position, not its output.
    """
    target = WORK / out_name
    if target.exists() and not force:
        print(f"  {label} - reusing {out_name}")
        return target
    print(f"  {label} ...", flush=True)
    fn(*args, **kwargs)
    if not target.exists():
        wbt.set_verbose_mode(True)
        fn(*args, **kwargs)
        raise SystemExit(f"whitebox failed at '{label}': no {out_name} written")
    return target


def write_land_dem(arr, valid, sea, prof, path):
    """DEM with sea and nodata both set to nodata, for the hydrology chain."""
    nd = prof["nodata"]
    land = np.where(valid & ~sea, arr, nd).astype("float32")
    prof = {**prof, "dtype": "float32", "compress": "deflate", "tiled": True}
    prof.pop("predictor", None)  # WhiteboxTools cannot read PREDICTOR=3
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(land, 1)
    return path


def coast_discharge_points(accum, streams, sea, valid, cell_km2, min_km2):
    """Land stream cells adjacent to the sea: where water leaves the catchment.

    Adjacent stream cells belong to one channel, so keep only the local
    maximum within each connected group - otherwise one wadi mouth reports as
    four separate outlets.
    """
    h, w = accum.shape
    cand = streams & ~sea & valid

    touches = np.zeros_like(cand)
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        shifted = np.zeros_like(sea)
        r0, r1 = max(0, dr), min(h, h + dr)
        c0, c1 = max(0, dc), min(w, w + dc)
        shifted[r0:r1, c0:c1] = sea[r0 - dr:r1 - dr, c0 - dc:c1 - dc]
        touches |= shifted
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
        groups.append((best, float(accum[best]) * cell_km2, len(cells)))

    groups.sort(key=lambda t: -t[1])
    return [g for g in groups if g[1] >= min_km2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream-threshold", type=int, default=STREAM_THRESHOLD)
    ap.add_argument("--min-outlet-km2", type=float, default=MIN_OUTLET_KM2)
    ap.add_argument("--force", action="store_true", help="recompute existing outputs")
    args = ap.parse_args()

    if not DEM.exists():
        raise SystemExit(f"missing {DEM} - run scripts/03_dem_fetch.py first")
    WORK.mkdir(parents=True, exist_ok=True)

    arr, valid, prof = read_dem(DEM)
    with rasterio.open(DEM) as r:
        transform, crs = r.transform, r.crs
        cell_km2 = abs(r.res[0] * r.res[1]) / 1e6

    print("sea mask ...")
    sea = sea_mask(arr, valid, transform, crs)
    print(f"  Gulf: {sea.sum() * cell_km2:,.1f} km2")
    mprof = {**prof, "dtype": "uint8", "nodata": 0, "compress": "deflate"}
    mprof.pop("predictor", None)
    with rasterio.open(WORK / "sea_mask.tif", "w", **mprof) as dst:
        dst.write(sea.astype("uint8"), 1)

    print("\nhydrology chain:")
    land = write_land_dem(arr, valid, sea, prof, WORK / "dem_land.tif")

    wbt = whitebox.WhiteboxTools()
    wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(WORK))

    # fill=False is load-bearing, not a tuning preference. Aqaba's hinterland
    # contains genuine endorheic basins - closed depressions that drain to an
    # internal sink and never reach the Gulf. Filling every remaining
    # depression after breaching forces them to spill toward the coast and
    # silently annexes them to Wadi Yutum:
    #
    #     fill=True   6,282 km2   +34% vs HydroBASINS
    #     fill=False  4,453 km2    -5% vs HydroBASINS
    #
    # HydroBASINS independently flags 1,767 km2 of this system ENDO>0 and
    # gives 4,690 km2 as the area that actually reaches the sea. Runoff volume
    # scales with contributing area, so the inflated figure would have
    # propagated straight into the sediment load and the plume magnitude.
    run(wbt, "breach depressions (least cost, no fill)", "dem_breached.tif",
        wbt.breach_depressions_least_cost, str(land), "dem_breached.tif",
        dist=200, fill=False, force=args.force)
    run(wbt, "d8 flow direction", "d8_pointer.tif",
        wbt.d8_pointer, "dem_breached.tif", "d8_pointer.tif", force=args.force)
    run(wbt, "d8 flow accumulation", "d8_accum.tif",
        wbt.d8_flow_accumulation, "dem_breached.tif", "d8_accum.tif",
        out_type="cells", force=args.force)
    # always recomputed: it is the cheap step and the one we retune
    run(wbt, f"extract streams (>= {args.stream_threshold} cells)", "streams.tif",
        wbt.extract_streams, "d8_accum.tif", "streams.tif",
        args.stream_threshold, force=True)

    with rasterio.open(WORK / "d8_accum.tif") as r:
        accum = r.read(1)
    with rasterio.open(WORK / "streams.tif") as r:
        streams = r.read(1) > 0

    print("\nfinding coastal discharge points ...")
    pts = coast_discharge_points(accum, streams, sea, valid, cell_km2,
                                 args.min_outlet_km2)
    if not pts:
        raise SystemExit("no discharge points found - lower --stream-threshold")

    rows = []
    with rasterio.open(DEM) as r:
        for (rr, cc), km2, ncells in pts:
            x, y = r.xy(rr, cc)
            rows.append({
                "row": rr, "col": cc,
                "utm_x": round(x, 1), "utm_y": round(y, 1),
                "upstream_km2": round(km2, 2),
                "accum_cells": int(accum[rr, cc]),
                "mouth_cells": ncells,
                "elev_m": round(float(arr[rr, cc]), 2),
            })

    out_csv = WORK / "outlet_candidates.csv"
    with open(out_csv, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    total = sum(r["upstream_km2"] for r in rows)
    print(f"\n{len(rows)} discharge points >= {args.min_outlet_km2} km2   "
          f"total upstream {total:,.0f} km2\n")
    print(f"{'#':>3} {'upstream_km2':>13} {'utm_x':>9} {'utm_y':>11} {'elev':>6}")
    for i, r in enumerate(rows[:25], 1):
        print(f"{i:>3} {r['upstream_km2']:>13,.2f} {r['utm_x']:>9.0f} "
              f"{r['utm_y']:>11.0f} {r['elev_m']:>6.1f}")
    if len(rows) > 25:
        print(f"    ... {len(rows) - 25} more")
    print(f"\nwrote {out_csv.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
