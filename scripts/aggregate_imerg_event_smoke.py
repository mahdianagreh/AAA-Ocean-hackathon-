#!/usr/bin/env python
"""Combine the six IMERG smoke-test granules and accumulate 3-hour rainfall.

Reads only files already on disk — this script makes NO network request and
downloads nothing. Produces a single NetCDF with the ``mm/hr`` rate series
preserved alongside the accumulated depth.

Scope limit: no catchment averaging, no rolling windows, no Parquet.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from ingestion.imerg import (  # noqa: E402
    calculate_rainfall_accumulation,
    combine_imerg_subsets,
)

SOURCE_DIR = PROJECT_ROOT / "data" / "raw" / "imerg" / "event_smoke_3h"
OUTPUT_FILE = PROJECT_ROOT / "data" / "processed" / "events" / "event_smoke_3h.nc"

EXPECTED_FILES = 6
INTERVAL_HOURS = 0.5
OUTPUT_VARIABLE = "rain_3h_mm"

RULE = "=" * 72


def discover_inputs() -> list[Path]:
    """Exactly the expected number of NetCDF granules, or refuse to run."""
    if not SOURCE_DIR.is_dir():
        raise FileNotFoundError(f"Input directory missing: {SOURCE_DIR}")
    files = sorted(p for p in SOURCE_DIR.glob("*.nc*") if p.is_file())
    if len(files) != EXPECTED_FILES:
        raise ValueError(
            f"Expected exactly {EXPECTED_FILES} NetCDF files in "
            f"{SOURCE_DIR}, found {len(files)}."
        )
    return files


def main() -> int:
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )

    print(f"\n{RULE}\nIMERG 3-HOUR ACCUMULATION (offline — no downloads)\n{RULE}")

    files = discover_inputs()
    print(f"  input directory   : {SOURCE_DIR.relative_to(PROJECT_ROOT)}")
    print(f"  input files       : {len(files)}")

    combined = combine_imerg_subsets(files, expected_interval_minutes=30)

    stamps = [t.strftime("%Y-%m-%dT%H:%M:%SZ")
              for t in np.atleast_1d(combined["time"].values)]
    gaps = [
            int((b - a).total_seconds() // 60)
            for a, b in zip(np.atleast_1d(combined["time"].values),
                            np.atleast_1d(combined["time"].values)[1:])
    ]

    print(f"\n{RULE}\nCOMBINED DATASET\n{RULE}")
    print("  ordered timestamps:")
    for index, stamp in enumerate(stamps, start=1):
        print(f"    {index}. {stamp}")
    print(f"  precipitation dims: {tuple(combined['precipitation'].dims)}")
    print(f"  precipitation shape: {tuple(combined['precipitation'].shape)}")
    print(f"  time spacing      : "
          f"{', '.join(f'{g} min' for g in gaps)}")

    result = calculate_rainfall_accumulation(
        combined,
        interval_hours=INTERVAL_HOURS,
        output_variable=OUTPUT_VARIABLE,
    )

    rain = result[OUTPUT_VARIABLE]
    values = np.asarray(rain.values, dtype="float64")
    valid = values[~np.isnan(values)]

    print(f"\n{RULE}\nACCUMULATION\n{RULE}")
    print(f"  variable          : {OUTPUT_VARIABLE}")
    print(f"  dims / shape      : {tuple(rain.dims)} / {tuple(rain.shape)}")
    print(f"  units             : {rain.attrs['units']}")
    print(f"  accumulation_hours: {rain.attrs['accumulation_hours']}")
    print(f"  interval_hours    : {rain.attrs['interval_hours']}")
    print(f"  interval_count    : {rain.attrs['interval_count']}")
    print(f"  window_start_utc  : {rain.attrs['window_start_utc']}")
    print(f"  window_end_utc    : {rain.attrs['window_end_utc']}")
    print(f"  minimum           : {valid.min():.6f} mm")
    print(f"  maximum           : {valid.max():.6f} mm")
    print(f"  mean              : {valid.mean():.6f} mm")
    print(f"  cells > 0         : {int((valid > 0).sum())} of {values.size}")

    if valid.size and valid.max() > 0:
        flat = int(np.nanargmax(values))
        row, col = np.unravel_index(flat, values.shape)
        print(f"  maximum cell      : lat {float(rain['lat'][row]):.3f}, "
              f"lon {float(rain['lon'][col]):.3f} "
              f"(index lat={row}, lon={col})")
    else:
        print("  maximum cell      : n/a — no rainfall above zero")

    # --- mathematical validation --------------------------------------
    print(f"\n{RULE}\nMATHEMATICAL VALIDATION\n{RULE}")
    manual = np.zeros(values.shape, dtype="float64")
    rates = np.asarray(combined["precipitation"].values, dtype="float64")
    for step in range(rates.shape[0]):
        manual += rates[step] * INTERVAL_HOURS
    difference = np.abs(np.nan_to_num(values) - np.nan_to_num(manual))
    max_difference = float(difference.max())
    tolerance = float(np.finfo(np.float32).eps) * max(
        1.0, float(np.nanmax(np.abs(manual))) if manual.size else 1.0
    )
    print(f"  rain_3h_mm == sum(precipitation * {INTERVAL_HOURS}) over "
          f"{rates.shape[0]} steps")
    print(f"  max absolute difference : {max_difference:.10g}")
    print(f"  float32 tolerance       : {tolerance:.3g}")
    print(f"  within tolerance        : "
          f"{'YES' if max_difference <= max(tolerance, 1e-9) else 'NO'}")

    # --- save ----------------------------------------------------------
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    encoded = result.copy()
    # cftime coordinates need explicit encoding for a clean round-trip.
    encoded["time"].encoding.setdefault(
        "units", "seconds since 1980-01-06 00:00:00"
    )
    encoded.to_netcdf(OUTPUT_FILE)
    result.close()
    combined.close()

    size_kb = OUTPUT_FILE.stat().st_size / 1024
    print(f"\n{RULE}\nOUTPUT\n{RULE}")
    print(f"  path              : {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    print(f"  size              : {size_kb:.1f} KB")

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    ).stdout
    leaked = [ln for ln in status.splitlines()
              if ".nc" in ln.lower() or "event_smoke" in ln]
    print(f"  git sees output   : "
          f"{'YES -> ' + str(leaked) if leaked else 'NO'}")
    print("  downloads         : NONE — every input read from local disk")
    print(f"{RULE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
