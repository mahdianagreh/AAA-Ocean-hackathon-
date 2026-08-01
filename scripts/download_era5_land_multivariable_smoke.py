#!/usr/bin/env python
"""Six-hour, seven-variable ERA5-Land download and validation smoke test.

Proves every ERA5-Land variable ReefShield needs can be requested, downloaded,
normalised and validated together. The window stays inside one calendar day so
the CDS year x month x day x time product yields exactly the hours requested.

Download and inspection only: no antecedent features, no IMERG merge, no
catchment aggregation, no unit conversion.

Idempotent — an existing valid file is inspected and reused, never re-requested
and never deleted. Nothing sensitive is printed: no CDS token, headers, or
signed URLs.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from ingestion.era5_land import (  # noqa: E402
    AREA,
    ERA5_SHORT_NAMES,
    GRID_ALIGNMENT_WARNING,
    build_era5_land_request,
    download_era5_land,
    read_era5_land,
    validate_expected_variables,
)

START = datetime(2016, 10, 27, 0, 0, tzinfo=timezone.utc)
END = datetime(2016, 10, 27, 5, 0, tzinfo=timezone.utc)

VARIABLES = [
    "volumetric_soil_water_layer_1",
    "total_precipitation",
    "surface_runoff",
    "sub_surface_runoff",
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_temperature",
]

EXPECTED_SHORT_NAMES = ["swvl1", "tp", "sro", "ssro", "u10", "v10", "t2m"]
EXPECTED_COUNT = 6
EXPECTED_SHAPE = (6, 5, 4)

DEST = PROJECT_ROOT / "data" / "raw" / "era5_land" / "multivariable_smoke"
OUTPUT = DEST / "era5_land_all_variables_20161027_0000_0500.nc"

#: Variables whose sea mask should match soil moisture's (all land-only).
LAND_ONLY = ("swvl1", "tp", "sro", "ssro", "t2m", "u10", "v10")

RULE = "=" * 76


def data_raw_ignored() -> str | None:
    probe = "data/raw/era5_land/multivariable_smoke/probe.nc"
    done = subprocess.run(
        ["git", "check-ignore", "-v", probe],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    return done.stdout.strip() if done.returncode == 0 else None


def accumulation_hint(name: str, values: np.ndarray, attrs: dict) -> str:
    """Describe how a field varies in time, from observation only.

    Reports what the numbers and metadata show. Makes no claim about ERA5's
    documented accumulation convention — that is a separate decision.
    """
    per_step = [
        float(np.nanmean(values[i])) if np.any(np.isfinite(values[i]))
        else float("nan")
        for i in range(values.shape[0])
    ]
    finite = [v for v in per_step if np.isfinite(v)]
    if not finite:
        return "all-NaN — cannot characterise"
    if all(abs(v - finite[0]) < 1e-15 for v in finite):
        return f"CONSTANT across timestamps (mean {finite[0]:.6g})"

    increasing = all(
        b >= a - 1e-15 for a, b in zip(finite, finite[1:])
    )
    step_note = " ".join(f"{v:.4g}" for v in per_step)
    if increasing:
        return (
            "MONOTONICALLY INCREASING — consistent with a cumulative field; "
            f"per-step means: {step_note}"
        )
    return (
        "VARIES NON-MONOTONICALLY — consistent with a per-step field; "
        f"per-step means: {step_note}"
    )


def main() -> int:
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )

    print(f"\n{RULE}\nERA5-LAND MULTI-VARIABLE SMOKE TEST (6 h, 7 variables)"
          f"\n{RULE}")

    # --- 1. pre-download validation ------------------------------------
    ignore_rule = data_raw_ignored()
    if not ignore_rule:
        print("  ABORT: data/raw is NOT ignored by Git. Nothing requested.")
        return 1
    print(f"  git ignore        : {ignore_rule}")

    DEST.mkdir(parents=True, exist_ok=True)
    existing = sorted(p.name for p in DEST.iterdir() if p.is_file())
    print(f"  existing files    : {len(existing)}"
          f"{' -> ' + str(existing) if existing else ''}")

    request = build_era5_land_request(VARIABLES, START, END, area=AREA)

    expected = request["_expected_timestamp_count"]
    cartesian = request["_cartesian_timestamp_count"]
    print(f"  variables         : {len(request['variable'])}")
    print(f"  expected count    : {expected}")
    print(f"  cartesian count   : {cartesian}")
    print(f"  area [N, W, S, E] : {request['area']}")
    print(f"  data_format       : {request['data_format']}")
    print(f"  download_format   : {request['download_format']}")

    problems = []
    if expected != EXPECTED_COUNT:
        problems.append(
            f"_expected_timestamp_count is {expected}, must be {EXPECTED_COUNT}"
        )
    if cartesian != EXPECTED_COUNT:
        problems.append(
            f"_cartesian_timestamp_count is {cartesian}, must be "
            f"{EXPECTED_COUNT} — the window would over-request"
        )
    if len(request["variable"]) != 7:
        problems.append(
            f"request has {len(request['variable'])} variables, must be 7"
        )
    if list(request["area"]) != list(AREA):
        problems.append(
            f"area is {request['area']}, must be {AREA} in CDS "
            "[North, West, South, East] order"
        )
    if problems:
        print(f"\n{RULE}\nABORTING BEFORE SUBMISSION\n{RULE}")
        for item in problems:
            print(f"  - {item}")
        print("  Nothing requested, nothing written.")
        return 1
    print("  pre-flight checks : ALL PASS")

    # --- 2. download or reuse -------------------------------------------
    if OUTPUT.exists() and OUTPUT.stat().st_size > 0:
        reused = True
        print(f"\n  existing file present "
              f"({OUTPUT.stat().st_size / 1024:.1f} KB) — reusing it. "
              "No CDS request submitted, nothing deleted.")
    else:
        reused = False
        print("\n  submitting one CDS request ...", flush=True)
        download_era5_land(request, OUTPUT, overwrite=False)

    print(f"\n{RULE}\nFILE\n{RULE}")
    print(f"  request status    : {'REUSED (no request)' if reused else 'SUCCEEDED'}")
    print(f"  output path       : {OUTPUT}")
    print(f"  output size       : {OUTPUT.stat().st_size / 1024:.1f} KB")

    # --- 3. inspect through the reader ----------------------------------
    dataset = read_era5_land(OUTPUT)
    try:
        print(f"\n{RULE}\nNORMALISED DATASET\n{RULE}")
        print(f"  dimensions        : {dict(dataset.sizes)}")
        print(f"  coordinates       : {sorted(map(str, dataset.coords))}")

        times = np.atleast_1d(dataset["time"].values)
        stamps = [str(np.datetime_as_string(t, unit="s")) for t in times]
        print(f"  timestamp count   : {len(stamps)}")
        for index, stamp in enumerate(stamps, start=1):
            print(f"    {index}. {stamp}Z")

        gaps = np.diff(times).astype("timedelta64[m]").astype(int).tolist()
        print(f"  spacing (minutes) : {gaps}")
        hourly = all(gap == 60 for gap in gaps)
        ascending = all(b > a for a, b in zip(times, times[1:]))
        unique = len(set(stamps)) == len(stamps)
        print(f"  hourly / sorted / unique : {hourly} / {ascending} / {unique}")

        lat = np.asarray(dataset["lat"].values, dtype="float64")
        lon = np.asarray(dataset["lon"].values, dtype="float64")
        print(f"  latitude          : {lat.min():.3f} -> {lat.max():.3f} "
              f"(n={lat.size}, "
              f"{'ASCENDING' if np.all(np.diff(lat) > 0) else 'NOT ascending'})")
        print(f"  longitude         : {lon.min():.3f} -> {lon.max():.3f} "
              f"(n={lon.size}, "
              f"{'ASCENDING' if np.all(np.diff(lon) > 0) else 'NOT ascending'})")

        # --- 4. variable mapping ---------------------------------------
        print(f"\n{RULE}\nVARIABLE MAPPING\n{RULE}")
        report = validate_expected_variables(dataset, EXPECTED_SHORT_NAMES)
        for short in EXPECTED_SHORT_NAMES:
            canonical = report["mapping"].get(short)
            expected_canonical = ERA5_SHORT_NAMES.get(short)
            mark = "OK " if canonical == expected_canonical else "MISMATCH"
            print(f"  [{mark}] {short:<6} -> {canonical}")
        if report["unexpected"]:
            print(f"  UNEXPECTED science variables (not renamed): "
                  f"{report['unexpected']}")
        else:
            print("  unexpected science variables: NONE")
        if report["unmapped"]:
            print(f"  UNMAPPED short names (reported, not renamed): "
                  f"{report['unmapped']}")

        # --- 3/5. per-variable statistics -------------------------------
        print(f"\n{RULE}\nPER-VARIABLE STATISTICS\n{RULE}")
        masks: dict[str, np.ndarray] = {}
        for short in sorted(map(str, dataset.data_vars)):
            array = dataset[short]
            values = np.asarray(array.values, dtype="float64")
            finite = values[np.isfinite(values)]
            dims = tuple(array.dims)
            shape = tuple(array.shape)
            units = array.attrs.get("units", "not set")
            masks[short] = np.isnan(values)

            print(f"\n  {short}  ->  {report['mapping'].get(short)}")
            print(f"    dims / shape    : {dims} / {shape}"
                  f"{'' if shape == EXPECTED_SHAPE else '   <-- UNEXPECTED'}")
            print(f"    units           : {units}")
            if finite.size:
                print(f"    min / max / mean: {finite.min():.6g} / "
                      f"{finite.max():.6g} / {finite.mean():.6g}")
            else:
                print("    min / max / mean: no valid values")
            print(f"    valid / NaN     : {finite.size} / "
                  f"{int(np.isnan(values).sum())}")

            if short in ("tp", "sro", "ssro"):
                print(f"    time behaviour  : "
                      f"{accumulation_hint(short, values, array.attrs)}")
            if short in ("u10", "v10"):
                negatives = int((finite < 0).sum()) if finite.size else 0
                print(f"    negative values : {negatives} (valid for wind, "
                      "not clamped)")
            if short == "t2m":
                print(f"    kelvin check    : units={units!r}, "
                      f"min={finite.min():.2f} — not converted to Celsius")
            if short == "swvl1":
                zeros = int((finite == 0).sum()) if finite.size else 0
                print(f"    clamped zeros   : {zeros} "
                      f"(noise in [-1e-12, 0) -> 0); min={finite.min():.6g}")

        # --- 6. grid and sea-mask checks --------------------------------
        print(f"\n{RULE}\nSEA MASK AND GRID\n{RULE}")
        reference_name = "swvl1"
        reference = masks.get(reference_name)
        if reference is None:
            print("  swvl1 absent — cannot compare masks")
        else:
            ref_per_cell = reference.any(axis=0)
            print(f"  reference mask ({reference_name}): "
                  f"{int(ref_per_cell.sum())} of {ref_per_cell.size} cells NaN")
            identical, differing = [], []
            for short in sorted(masks):
                if short == reference_name:
                    continue
                per_cell = masks[short].any(axis=0)
                (identical if np.array_equal(per_cell, ref_per_cell)
                 else differing).append(short)
            print(f"  same mask as swvl1 : {identical or 'none'}")
            print(f"  different mask     : {differing or 'none'}")
            rows, cols = np.where(ref_per_cell)
            print("  masked cell coords :")
            for row, col in zip(rows, cols):
                print(f"    lat {lat[row]:.2f}, lon {lon[col]:.2f}")
            print("  interpolation      : NONE — sea cells left as NaN")

        print(f"\n  GRID SAFETY: {GRID_ALIGNMENT_WARNING}")
    finally:
        dataset.close()

    # --- safety ----------------------------------------------------------
    print(f"\n{RULE}\nSAFETY\n{RULE}")
    files = sorted(p.name for p in DEST.iterdir() if p.is_file())
    print(f"  files in folder   : {len(files)}")
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    ).stdout
    leaked = [ln for ln in status.splitlines()
              if ".nc" in ln.lower() or "era5" in ln.lower()]
    print(f"  git sees the data : "
          f"{'YES -> ' + str(leaked) if leaked else 'NO'}")
    print(f"{RULE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
