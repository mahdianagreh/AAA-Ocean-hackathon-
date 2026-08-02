"""Stage 1 of real catchment delineation: condition the DEM, derive flow, find
every place a stream reaches the Gulf.

This runs before any decision about how many catchments we want. Conditioning
and flow accumulation are needed whatever we choose, and the candidate-outlet
table is the evidence for that choice - it shows how many discharge points the
30 m DEM actually resolves along the Jordanian coast, versus the two that
HydroBASINS lumps it into.

Breaching rather than filling: Aqaba's wadis are long and near-flat in their
lower reaches, and sink filling turns those into lakes that then spill in an
arbitrary direction. Least-cost breaching cuts through the blocking cell
instead, which is the right model for a channel a coarse DSM has bridged.

Outputs (data/interim/hydro/)
    dem_breached.tif      conditioned DEM
    d8_pointer.tif        flow direction
    d8_accum.tif          flow accumulation, cells
    streams.tif           extracted stream network
    sea_mask.tif          connected Gulf water body
    outlet_candidates.csv ranked discharge points with upstream area

Usage
    .venv/bin/python scripts/04_flow_and_outlets.py
    .venv/bin/python scripts/04_flow_and_outlets.py --stream-threshold 500
"""

import argparse
import collections
import csv
from pathlib import Path

import numpy as np
import rasterio
import whitebox

ROOT = Path(__file__).resolve().parent.parent
DEM = ROOT / "data/processed/dem/dem_utm36n.tif"
WORK = ROOT / "data/interim/hydro"

# Copernicus DEM puts sea surface near 0 with a little noise; 1.5 m clears the
# noise without eating the coastal plain, which rises fast here.
SEA_LEVEL_M = 1.5

# A stream needs this many upstream cells before we call it a stream.
# 900 cells x 900 m2 = 0.81 km2. Small for a humid basin, appropriate for
# picking up the short coastal wadis we may be missing.
STREAM_THRESHOLD = 900

# Report any discharge point draining at least this much, in km2.
MIN_OUTLET_KM2 = 0.5


def wbt_setup():
    wbt = whitebox.WhiteboxTools()
    wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(WORK))
    return wbt


def run(wbt, label, fn, *args, **kwargs):
    """Call a Whitebox tool and verify it actually wrote its output.

    Whitebox returns 0 even when the Rust binary panics, so a missing output
    file is the only reliable failure signal. Without this check a broken step
    surfaces hundreds of lines later as a confusing 'file not found'.
    """
    out = kwargs.get("output") or args[-1]
    target = WORK / out
    if target.exists():
        target.unlink()
    print(f"  {label}...")
    fn(*args, **kwargs)
    if not target.exists():
        wbt.set_verbose_mode(True)
        fn(*args, **kwargs)
        raise SystemExit(f"whitebox failed at '{label}' - no {out} written (see above)")
    return target


def prepare_dem_for_wbt():
    """Rewrite the DEM without a floating-point predictor.

    rioxarray/GDAL defaults can write DEFLATE with PREDICTOR=3, which the
    Whitebox GeoTIFF reader rejects outright. Uncompressed costs disk and
    nothing else, and keeps the conditioned chain byte-identical.
    """
    with rasterio.open(DEM) as r:
        prof = r.profile.copy()
        data = r.read(1)
    prof.update(compress=None, predictor=None, tiled=False)
    prof.pop("predictor", None)
    out = WORK / "dem_wbt.tif"
    with rasterio.open(out, "w", **prof) as dst:
        dst.write(data, 1)
    return out


def sea_mask(dem, nodata):
    """Flood-fill the Gulf from the lowest cell on the southern edge.

    Threshold alone would also flag inland sabkha and quarry floors; requiring
    connection to the open sea is what makes this a coastline rather than a
    list of low places.
    """
    h, w = dem.shape
    water = dem <= SEA_LEVEL_M
    if nodata is not None:
        water &= dem != nodata

    # seed: lowest water cell along the bottom edge (the Gulf is due south)
    bottom = np.where(water[h - 1])[0]
    if len(bottom) == 0:
        raise SystemExit(
            "no water cells on the southern edge - check SEA_LEVEL_M or the DEM extent"
        )
    seed = (h - 1, int(bottom[np.argmin(dem[h - 1, bottom])]))

    mask = np.zeros_like(water, dtype=bool)
    q = collections.deque([seed])
    mask[seed] = True
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w and water[rr, cc] and not mask[rr, cc]:
                mask[rr, cc] = True
                q.append((rr, cc))
    return mask


def coast_discharge_points(accum, streams, sea, cell_km2, min_km2):
    """Land stream cells that touch the sea: where water leaves the catchment.

    Adjacent stream cells belong to one channel, so keep only the local maximum
    within each connected group - otherwise a single wadi mouth reports as four
    outlets.
    """
    h, w = accum.shape
    land_stream = streams & ~sea
    touches = np.zeros_like(land_stream, dtype=bool)
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
        shifted = np.zeros_like(sea)
        r0, r1 = max(0, dr), min(h, h + dr)
        c0, c1 = max(0, dc), min(w, w + dc)
        shifted[r0:r1, c0:c1] = sea[r0 - dr:r1 - dr, c0 - dc:c1 - dc]
        touches |= shifted
    cand = land_stream & touches

    # group adjacent candidates, keep the highest-accumulation cell in each
    seen = np.zeros_like(cand, dtype=bool)
    groups = []
    rows, cols = np.where(cand)
    for r, c in zip(rows, cols):
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
        groups.append((best, accum[best] * cell_km2, len(cells)))

    groups.sort(key=lambda t: -t[1])
    return [g for g in groups if g[1] >= min_km2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream-threshold", type=int, default=STREAM_THRESHOLD)
    ap.add_argument("--min-outlet-km2", type=float, default=MIN_OUTLET_KM2)
    args = ap.parse_args()

    if not DEM.exists():
        raise SystemExit(f"missing {DEM} - run scripts/03_dem_fetch.py first")
    WORK.mkdir(parents=True, exist_ok=True)

    wbt = wbt_setup()

    print("hydrology chain:")
    dem_wbt = prepare_dem_for_wbt()

    run(wbt, "breach depressions (least cost)",
        wbt.breach_depressions_least_cost, str(dem_wbt), "dem_breached.tif",
        dist=200, fill=True)
    run(wbt, "d8 flow direction",
        wbt.d8_pointer, "dem_breached.tif", "d8_pointer.tif")
    run(wbt, "d8 flow accumulation",
        wbt.d8_flow_accumulation, "dem_breached.tif", "d8_accum.tif", out_type="cells")
    run(wbt, f"extract streams (threshold {args.stream_threshold} cells)",
        wbt.extract_streams, "d8_accum.tif", "streams.tif", args.stream_threshold)
    print()

    with rasterio.open(DEM) as r:
        dem = r.read(1)
        prof = r.profile
        cell_km2 = abs(r.res[0] * r.res[1]) / 1e6
        nodata = r.nodata

    with rasterio.open(WORK / "d8_accum.tif") as r:
        accum = r.read(1)
    with rasterio.open(WORK / "streams.tif") as r:
        streams = r.read(1) > 0

    print("building sea mask...")
    sea = sea_mask(dem, nodata)
    prof.update(dtype="uint8", nodata=0, count=1, compress="deflate")
    with rasterio.open(WORK / "sea_mask.tif", "w", **prof) as dst:
        dst.write(sea.astype("uint8"), 1)

    print("finding coastal discharge points...\n")
    pts = coast_discharge_points(accum, streams, sea, cell_km2, args.min_outlet_km2)

    with rasterio.open(DEM) as r:
        rows = []
        for (rr, cc), km2, ncells in pts:
            x, y = r.xy(rr, cc)
            rows.append({
                "row": rr, "col": cc,
                "utm_x": round(x, 1), "utm_y": round(y, 1),
                "upstream_km2": round(km2, 2),
                "accum_cells": int(accum[rr, cc]),
                "group_cells": ncells,
                "elev_m": round(float(dem[rr, cc]), 2),
            })

    out_csv = WORK / "outlet_candidates.csv"
    with open(out_csv, "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)

    total = sum(r["upstream_km2"] for r in rows)
    print(f"{len(rows)} discharge points >= {args.min_outlet_km2} km2   "
          f"total upstream {total:,.0f} km2")
    print(f"sea mask: {sea.sum() * cell_km2:,.0f} km2 of water\n")
    print(f"{'#':>3} {'upstream_km2':>13} {'utm_x':>10} {'utm_y':>11} {'elev':>6}")
    for i, r in enumerate(rows[:25], 1):
        print(f"{i:>3} {r['upstream_km2']:>13,.2f} {r['utm_x']:>10.0f} "
              f"{r['utm_y']:>11.0f} {r['elev_m']:>6.1f}")
    if len(rows) > 25:
        print(f"    ... {len(rows) - 25} more in {out_csv.relative_to(ROOT)}")
    print(f"\nwrote {out_csv.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
