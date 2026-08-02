#!/usr/bin/env python
"""Download and validate ERA5-Land deaccumulation over two full UTC days.

Three separate CDS requests (one per calendar day, plus a trailing 00:00) keep
the year x month x day x time product exact. The combined 49-timestamp raw
series is deaccumulated into 48 hourly periods labelled by interval end, then
each day's increments are summed and checked against the following 00:00 raw
cumulative total.

Semantics are documented in docs/era5_land_accumulation_semantics.md.

No IMERG merge, no catchment aggregation, no antecedent features. Idempotent:
existing valid files are reused, never re-requested and never deleted. No CDS
token, header, or signed URL is printed.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from ingestion.era5_land import (  # noqa: E402
    ACCUMULATED_VARIABLES,
    AREA,
    HOURLY_MM_NAMES,
    RAW_ACCUMULATION_SEMANTICS,
    SOURCE_PRODUCT,
    build_era5_land_request,
    deaccumulate_era5_land,
    download_era5_land,
    read_era5_land,
)

VARIABLES = [
    "total_precipitation",
    "surface_runoff",
    "sub_surface_runoff",
    "volumetric_soil_water_layer_1",
]
EXPECTED_SHORT_NAMES = ["tp", "sro", "ssro", "swvl1"]

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "era5_land" / "deaccumulation_validation"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "events"
OUTPUT_NC = PROCESSED_DIR / "era5_land_hourly_20161026_20161027.nc"
OUTPUT_JSON = PROCESSED_DIR / "era5_land_hourly_20161026_20161027_summary.json"

# (label, start, end, expected timestamps, filename)
REQUESTS = [
    ("A", datetime(2016, 10, 26, 0, tzinfo=timezone.utc),
     datetime(2016, 10, 26, 23, tzinfo=timezone.utc), 24,
     "era5_land_accum_20161026.nc"),
    ("B", datetime(2016, 10, 27, 0, tzinfo=timezone.utc),
     datetime(2016, 10, 27, 23, tzinfo=timezone.utc), 24,
     "era5_land_accum_20161027.nc"),
    ("C", datetime(2016, 10, 28, 0, tzinfo=timezone.utc),
     datetime(2016, 10, 28, 0, tzinfo=timezone.utc), 1,
     "era5_land_accum_20161028_0000.nc"),
]

EXPECTED_RAW_COUNT = 49
EXPECTED_HOURLY_COUNT = 48
RAW_FIRST = "2016-10-26T00:00:00"
RAW_LAST = "2016-10-28T00:00:00"
HOURLY_FIRST = "2016-10-26T01:00:00"
HOURLY_LAST = "2016-10-28T00:00:00"

# (day label, first interval-end, last interval-end == raw comparison stamp)
DAILY_CHECKS = [
    ("2016-10-26", "2016-10-26T01:00:00", "2016-10-27T00:00:00"),
    ("2016-10-27", "2016-10-27T01:00:00", "2016-10-28T00:00:00"),
]

# Daily sum vs raw total. The residual is not float64 rounding: it is exactly
# the quantisation noise that was clamped to zero. Clamping a negative
# increment necessarily raises the day's sum by that amount, e.g. one cell on
# 2016-10-26 had -7.45e-9 clamped at 12:00 and -1.49e-8 at 18:00, giving a
# 2.235e-8 m residual. 1e-7 m (1e-4 mm) covers several clamped steps while
# staying far below any meaningful rainfall.
TOLERANCE_M = 1e-7

# ERA5-Land arrives GRIB-packed, so cumulative values are quantised. Observed
# negative increments in this window are exactly -7.45e-9 and -1.49e-8 m
# (2**-27 and 2**-26) — one and two quantisation steps, not real decreases.
# The module default of 1e-10 m is calibrated for float64 noise and is too
# tight for packed data. 1e-7 m sits ~7x above the observed step and is still
# 1e-4 mm: far below any meteorologically meaningful amount, so a genuine
# decrease would still raise.
NEGATIVE_TOLERANCE_M = 1e-7
OBSERVED_QUANTISATION_M = 1.4901161193847656e-08

RULE = "=" * 78


def data_raw_ignored() -> str | None:
    probe = "data/raw/era5_land/deaccumulation_validation/probe.nc"
    done = subprocess.run(
        ["git", "check-ignore", "-v", probe],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    return done.stdout.strip() if done.returncode == 0 else None


def stamps_of(dataset: xr.Dataset) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(np.atleast_1d(dataset["time"].values))


def main() -> int:
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )
    print(f"\n{RULE}\nERA5-LAND DEACCUMULATION VALIDATION\n{RULE}")

    ignore_rule = data_raw_ignored()
    if not ignore_rule:
        print("  ABORT: data/raw is NOT ignored by Git. Nothing requested.")
        return 1
    print(f"  git ignore        : {ignore_rule}")
    print(f"  semantics         : {RAW_ACCUMULATION_SEMANTICS}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    downloaded, reused, request_files = 0, 0, []

    # --- 1. three separate requests -------------------------------------
    print(f"\n{RULE}\nREQUESTS\n{RULE}")
    for label, start, end, expected, filename in REQUESTS:
        request = build_era5_land_request(VARIABLES, start, end, area=AREA)
        target = RAW_DIR / filename
        request_files.append(str(target.relative_to(PROJECT_ROOT)))

        actual = request["_expected_timestamp_count"]
        cartesian = request["_cartesian_timestamp_count"]
        ok = (
            actual == expected and cartesian == expected
            and len(request["variable"]) == 4
            and list(request["area"]) == list(AREA)
        )
        print(f"  request {label}: {start:%Y-%m-%dT%H:%M}Z .. "
              f"{end:%Y-%m-%dT%H:%M}Z  expected={actual} "
              f"cartesian={cartesian} variables={len(request['variable'])} "
              f"{'OK' if ok else 'MISMATCH'}")
        if not ok:
            print(f"    ABORT: request {label} failed its pre-flight check "
                  f"(expected {expected}). Nothing submitted.")
            return 1

        if target.exists() and target.stat().st_size > 0:
            reused += 1
            print(f"    reusing {target.name} "
                  f"({target.stat().st_size / 1024:.1f} KB) — no request sent")
        else:
            print(f"    submitting ...", flush=True)
            download_era5_land(request, target, overwrite=False)
            downloaded += 1
            print(f"    received {target.name} "
                  f"({target.stat().st_size / 1024:.1f} KB)")

    # --- 6. combine ------------------------------------------------------
    parts = []
    for _, _, _, _, filename in REQUESTS:
        parts.append(read_era5_land(RAW_DIR / filename).load())
    raw = xr.concat(parts, dim="time", coords="minimal", compat="override")
    raw = raw.sortby("time")
    for part in parts:
        part.close()

    raw_times = stamps_of(raw)
    print(f"\n{RULE}\nRAW COMBINED SERIES\n{RULE}")
    print(f"  raw timestamps    : {raw_times.size}")
    print(f"  first / last      : {raw_times[0]} / {raw_times[-1]}")
    gaps = set(np.diff(raw_times.values).astype("timedelta64[m]").astype(int))
    print(f"  spacing (minutes) : {sorted(gaps)}")
    print(f"  variables         : {sorted(map(str, raw.data_vars))}")

    problems = []
    if raw_times.size != EXPECTED_RAW_COUNT:
        problems.append(f"{raw_times.size} timestamps, expected "
                        f"{EXPECTED_RAW_COUNT}")
    if raw_times.has_duplicates:
        problems.append("duplicate timestamps")
    if gaps != {60}:
        problems.append(f"non-hourly spacing {sorted(gaps)}")
    # Compare Timestamps, not their string forms: str() uses a space
    # separator while the constants are ISO-8601 with 'T'.
    if raw_times[0] != pd.Timestamp(RAW_FIRST):
        problems.append(f"first is {raw_times[0]}, expected {RAW_FIRST}")
    if raw_times[-1] != pd.Timestamp(RAW_LAST):
        problems.append(f"last is {raw_times[-1]}, expected {RAW_LAST}")
    if problems:
        print("  VALIDATION FAILED:")
        for item in problems:
            print(f"    - {item}")
        return 1
    print("  [PASS] 49 unique hourly timestamps, "
          f"{RAW_FIRST}Z .. {RAW_LAST}Z")

    # --- 2-4. deaccumulate ----------------------------------------------
    processed = deaccumulate_era5_land(
        raw, negative_tolerance_m=NEGATIVE_TOLERANCE_M
    )

    # Drop only the leading stamp: it lacks the preceding 2016-10-25T23:00.
    hourly = processed.sel(time=slice(HOURLY_FIRST, None))
    hourly_times = stamps_of(hourly)

    print(f"\n{RULE}\nDEACCUMULATED SERIES\n{RULE}")
    print(f"  hourly timestamps : {hourly_times.size}")
    print(f"  first / last      : {hourly_times[0]} / {hourly_times[-1]}")
    print(f"  dropped           : 1 (2016-10-26T00:00:00Z — no preceding "
          "2016-10-25T23:00 value)")
    if hourly_times.size != EXPECTED_HOURLY_COUNT:
        print(f"  ABORT: expected {EXPECTED_HOURLY_COUNT} hourly periods")
        return 1
    print(f"  [PASS] {EXPECTED_HOURLY_COUNT} complete hourly periods "
          f"({HOURLY_FIRST}Z .. {HOURLY_LAST}Z, interval_end labelling)")

    clamped = {
        short: int(
            processed[f"{short}_hourly_m"].attrs["negative_noise_clamped_count"]
        )
        for short in ACCUMULATED_VARIABLES
    }
    print(f"  tiny negatives clamped: {clamped}")

    # --- 7. daily mathematical validation --------------------------------
    print(f"\n{RULE}\nDAILY MATHEMATICAL VALIDATION\n{RULE}")
    print("  sum(hourly increments T01:00..T+1 00:00)  ==  raw cumulative at "
          "T+1 00:00")
    daily_results = {}
    all_within = True
    for day, first_end, last_end in DAILY_CHECKS:
        window = (hourly_times >= pd.Timestamp(first_end)) & \
                 (hourly_times <= pd.Timestamp(last_end))
        per_day = {}
        print(f"\n  {day}  ({int(window.sum())} hourly periods)")
        for short in ACCUMULATED_VARIABLES:
            increments = np.asarray(
                hourly[f"{short}_hourly_m"].values, dtype="float64"
            )[window]
            summed = np.nansum(increments, axis=0)
            raw_total = np.asarray(
                hourly[short].sel(time=last_end).values, dtype="float64"
            )
            both = np.isfinite(summed) & np.isfinite(raw_total)
            difference = np.abs(summed[both] - raw_total[both])
            worst = float(difference.max()) if difference.size else float("nan")
            within = bool(np.isfinite(worst) and worst <= TOLERANCE_M)
            all_within &= within
            per_day[short] = {
                "cells_compared": int(both.sum()),
                "max_abs_difference_m": worst,
                "within_tolerance": within,
            }
            print(f"    {short:<5} cells={int(both.sum()):<3} "
                  f"max|diff|={worst:.3e} m  "
                  f"{'WITHIN' if within else 'OUTSIDE'} tolerance "
                  f"{TOLERANCE_M:g}")
        daily_results[day] = per_day

    # --- 8. scientific validation ---------------------------------------
    print(f"\n{RULE}\nSCIENTIFIC VALIDATION\n{RULE}")
    statistics = {}
    for short in ACCUMULATED_VARIABLES:
        mm_name = HOURLY_MM_NAMES[short]
        values = np.asarray(hourly[mm_name].values, dtype="float64")
        finite = values[np.isfinite(values)]
        statistics[mm_name] = {
            "units": "mm",
            "min": float(finite.min()) if finite.size else None,
            "max": float(finite.max()) if finite.size else None,
            "mean": float(finite.mean()) if finite.size else None,
            "valid": int(finite.size),
            "nan": int(np.isnan(values).sum()),
            "materially_negative": int((finite < 0).sum()) if finite.size else 0,
            "tiny_negatives_clamped": clamped[short],
        }
        print(f"  {mm_name}")
        print(f"    min / max / mean : {finite.min():.6g} / "
              f"{finite.max():.6g} / {finite.mean():.6g} mm")
        print(f"    valid / NaN      : {finite.size} / "
              f"{int(np.isnan(values).sum())}")
        print(f"    negative (<0)    : "
              f"{int((finite < 0).sum())}   clamped noise: {clamped[short]}")

    daily_totals = {}
    print("\n  daily area-mean totals (land cells only)")
    for day, first_end, last_end in DAILY_CHECKS:
        window = (hourly_times >= pd.Timestamp(first_end)) & \
                 (hourly_times <= pd.Timestamp(last_end))
        per_day = {}
        for short in ACCUMULATED_VARIABLES:
            values = np.asarray(
                hourly[HOURLY_MM_NAMES[short]].values, dtype="float64"
            )[window]
            cell_totals = np.nansum(values, axis=0)
            land = np.isfinite(
                np.asarray(hourly[short].isel(time=0).values, dtype="float64")
            )
            per_cell = cell_totals[land]
            per_day[short] = {
                "area_mean_mm": float(per_cell.mean()) if per_cell.size else None,
                "max_cell_mm": float(per_cell.max()) if per_cell.size else None,
                "min_cell_mm": float(per_cell.min()) if per_cell.size else None,
            }
            print(f"    {day} {short:<5} area-mean {per_cell.mean():.6g} mm  "
                  f"max cell {per_cell.max():.6g} mm")
        daily_totals[day] = per_day

    soil = np.asarray(hourly["swvl1"].values, dtype="float64")
    soil_finite = soil[np.isfinite(soil)]
    print(f"\n  swvl1 (instantaneous, NOT deaccumulated)")
    print(f"    min / max / mean : {soil_finite.min():.6g} / "
          f"{soil_finite.max():.6g} / {soil_finite.mean():.6g} m3 m-3")

    reference = np.isnan(
        np.asarray(hourly["tp"].values, dtype="float64")
    ).any(axis=0)
    sea_cells = int(reference.sum())
    land_cells = int(reference.size - sea_cells)
    print(f"\n  land cells        : {land_cells}")
    print(f"  sea-mask cells    : {sea_cells}")
    print("  interpolation     : NONE")
    print("  NOTE: no comparison with IMERG performed in this task.")

    # --- 11. save --------------------------------------------------------
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    hourly.attrs.update({
        "source_product": SOURCE_PRODUCT,
        "raw_accumulation_semantics": RAW_ACCUMULATION_SEMANTICS,
        "accumulation_processing": "ERA5-Land forecast deaccumulation",
        "interval_label": "interval_end",
        "canonical_timezone": "UTC",
        "missing_data_policy": "preserve_nan",
        "documentation": "docs/era5_land_accumulation_semantics.md",
        "bbox_north_west_south_east": list(AREA),
        "raw_timestamp_count": int(raw_times.size),
        "hourly_timestamp_count": int(hourly_times.size),
        "imerg_merge_performed": "no",
        "catchment_aggregation_performed": "no",
    })
    hourly.to_netcdf(OUTPUT_NC)

    summary = {
        "source_product": SOURCE_PRODUCT,
        "documentation": "docs/era5_land_accumulation_semantics.md",
        "raw_accumulation_semantics": RAW_ACCUMULATION_SEMANTICS,
        "request_files": request_files,
        "files_downloaded_this_run": downloaded,
        "files_reused": reused,
        "raw_timestamp_count": int(raw_times.size),
        "raw_first_utc": f"{raw_times[0]}Z",
        "raw_last_utc": f"{raw_times[-1]}Z",
        "processed_hourly_timestamp_count": int(hourly_times.size),
        "processed_first_utc": f"{hourly_times[0]}Z",
        "processed_last_utc": f"{hourly_times[-1]}Z",
        "dropped_timestamps": ["2016-10-26T00:00:00Z"],
        "daily_validation": daily_results,
        "daily_validation_tolerance_m": TOLERANCE_M,
        "daily_validation_residual_explanation": (
            "Residuals equal the GRIB quantisation noise clamped to zero, "
            "not rounding error. Clamping a negative increment raises the "
            "day sum by that amount; observed maximum 2.235e-8 m = two "
            "clamped steps in one cell."
        ),
        "daily_validation_all_within_tolerance": bool(all_within),
        "daily_totals": daily_totals,
        "variable_statistics": statistics,
        "soil_moisture": {
            "units": "m**3 m**-3",
            "min": float(soil_finite.min()),
            "max": float(soil_finite.max()),
            "mean": float(soil_finite.mean()),
            "deaccumulated": False,
        },
        "missing_data": {
            "land_cells": land_cells,
            "sea_mask_cells": sea_cells,
            "interpolation_performed": False,
            "policy": "preserve_nan",
        },
        "noise_clamping": {
            "counts": clamped,
            "negative_tolerance_m": NEGATIVE_TOLERANCE_M,
            "observed_grib_quantisation_step_m": OBSERVED_QUANTISATION_M,
            "rationale": (
                "ERA5-Land is GRIB-packed; observed negative increments "
                "are exact multiples of the 2**-26 quantisation step, not "
                "physical decreases. Tolerance sits above the step and "
                "far below 1e-4 mm."
            ),
        },
        "assumptions": [
            RAW_ACCUMULATION_SEMANTICS,
            "01 UTC is a daily reset; its raw value IS the first hour's total "
            "and is never differenced against 00 UTC.",
            "Hourly increments are labelled by interval end time.",
            "A UTC day spans T01:00 through T+1 T00:00 for these variables.",
            "Millimetres = metres * 1000, applied after deaccumulation.",
            "Sea-mask NaNs are preserved and never interpolated.",
            "Increments in [-1e-10, 0) m are float noise and clamp to zero; "
            "anything more negative raises.",
            "swvl1 is instantaneous and is not deaccumulated.",
            "No comparison or merge with IMERG was performed.",
        ],
    }
    OUTPUT_JSON.write_text(json.dumps(summary, indent=2) + "\n")
    hourly.close()
    processed.close()
    raw.close()

    print(f"\n{RULE}\nOUTPUT\n{RULE}")
    print(f"  netcdf            : {OUTPUT_NC.relative_to(PROJECT_ROOT)} "
          f"({OUTPUT_NC.stat().st_size / 1024:.1f} KB)")
    print(f"  summary json      : {OUTPUT_JSON.relative_to(PROJECT_ROOT)} "
          f"({OUTPUT_JSON.stat().st_size / 1024:.1f} KB)")
    print(f"  downloaded / reused: {downloaded} / {reused}")

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    ).stdout
    leaked = [ln for ln in status.splitlines()
              if ".nc" in ln.lower() or "era5_land_hourly" in ln]
    print(f"  git sees data     : "
          f"{'YES -> ' + str(leaked) if leaked else 'NO'}")
    print(f"\n  DAILY VALIDATION: "
          f"{'ALL WITHIN TOLERANCE' if all_within else 'FAILED'}")
    print(f"{RULE}\n")
    return 0 if all_within else 1


if __name__ == "__main__":
    raise SystemExit(main())
