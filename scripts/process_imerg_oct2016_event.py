#!/usr/bin/env python
"""Download and process the literature-constrained October 2016 IMERG window.

Window comes from ``docs/event_dates.md`` -> ``imerg_scan_window_utc``, the
conservative window covering the ~66 h rainfall event reported by
Kalman et al. (2025) (240 half-hourly Harmony subsets as of the 2026-08-07
extension, EXPECTED_GRANULES below is the number that actually governs this,
not this docstring). Retrieves the half-hourly subsets over the Aqaba box,
validates the collection, combines it, derives trailing rolling
accumulations, and reports the actual wettest windows.

Resumable: existing granules are detected by timestamp and never re-requested;
only missing runs are downloaded. No file is ever deleted automatically.

Scope limit: grid cells only — no catchment polygons, no catchment averaging.
Nothing sensitive is printed: no credentials, tokens, cookies, auth headers,
or Harmony result URLs.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from ingestion.imerg import (  # noqa: E402
    DOWNLOAD_BBOX,
    ROLLING_WINDOWS,
    SOURCE_PRODUCT,
    add_rolling_accumulations,
    combine_imerg_subsets,
    download_imerg_subset,
    find_wettest_window,
    precipitation_rate_to_depth,
    read_imerg_subset,
)

EVENT_ID = "AQ-2016-10-28"
CONTRACT = PROJECT_ROOT / "docs" / "event_dates.md"

RAW_DIR = PROJECT_ROOT / "data" / "raw" / "imerg" / "events" / EVENT_ID
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed" / "events"
OUTPUT_NC = PROCESSED_DIR / f"{EVENT_ID}_imerg.nc"
OUTPUT_JSON = PROCESSED_DIR / f"{EVENT_ID}_summary.json"

# Fallback, kept in sync with docs/event_dates.md ->
# primary_event.engineering.imerg_scan_window_utc
# Extended 2026-08-07 (Phase 5, A1.1) -- see docs/event_dates.md's
# imerg_scan_window_utc note for why. These constants are the script's own
# consistency self-check, so they move in lockstep with the contract file's
# end time, not independently of it.
FALLBACK_START = "2016-10-25T00:00:00Z"
FALLBACK_END = "2016-10-30T00:00:00Z"

INTERVAL_MINUTES = 30
INTERVAL_HOURS = 0.5
EXPECTED_GRANULES = 240
EXPECTED_FIRST = "2016-10-25T00:00:00"
EXPECTED_LAST = "2016-10-29T23:30:00"
# (13, 13), not the (5, 4) this constant held before today: that was the grid for
# the RETIRED, narrower AOI box. Every granule on disk -- the original re-pull
# under the corrected TERRAIN_AOI (Phase 2, A1.1) and today's newly-fetched ones
# alike -- already validates as one consistent (13, 13) grid; only this
# self-check constant had not been updated to match since the AOI correction.
EXPECTED_GRID = (13, 13)

# Harmony returns one file per granule; chunk requests so a single job stays
# modest and an interruption loses little work.
CHUNK_GRANULES = 48

ALLOWED_NAMES = {
    "precipitation", "lat", "lon", "time",
    "lat_bnds", "lon_bnds", "time_bnds", "latv", "lonv", "nv",
    "crs", "spatial_ref",
}

GRANULE_RE = re.compile(r"3IMERG\.(\d{8})-S(\d{6})-E\d{6}")
RULE = "=" * 74


# ---------------------------------------------------------------------------
# window + expectations
# ---------------------------------------------------------------------------


def read_scan_window() -> tuple[datetime, datetime, str]:
    """Parse imerg_scan_window_utc from the timing contract.

    The contract states an inclusive hour boundary. A granule starting exactly
    at that instant would add one extra file, so the end is converted to an
    *exclusive* granule-start bound by stepping back one second -- giving
    whatever span and granule count the contract's current start/end implies
    (see EXPECTED_GRANULES/EXPECTED_FIRST/EXPECTED_LAST, which move with it).
    """
    start_raw, end_raw, provenance = FALLBACK_START, FALLBACK_END, "fallback"

    if CONTRACT.exists():
        text = CONTRACT.read_text()
        block = re.search(
            r"imerg_scan_window_utc:\s*\n(?P<body>(?:\s+\w+:.*\n)+)", text
        )
        if block:
            body = block.group("body")
            start_m = re.search(r"start:\s*(\S+)", body)
            end_m = re.search(r"end:\s*(\S+)", body)
            if start_m and end_m:
                start_raw, end_raw = start_m.group(1), end_m.group(1)
                provenance = f"parsed from {CONTRACT.name}"

    start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
    if end.second == 0 and end.microsecond == 0:
        end = end - timedelta(seconds=1)
        provenance += " (inclusive end -> exclusive granule bound, -1 s)"
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc), provenance


def expected_timestamps(start: datetime, end: datetime) -> list[datetime]:
    """Every half-hour granule start inside the window."""
    step = timedelta(minutes=INTERVAL_MINUTES)
    stamps, current = [], start
    while current <= end:
        stamps.append(current)
        current += step
    return stamps


def label(stamp: datetime) -> str:
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# safety + resume
# ---------------------------------------------------------------------------


def data_raw_ignored() -> str | None:
    probe = f"data/raw/imerg/events/{EVENT_ID}/probe.nc"
    done = subprocess.run(
        ["git", "check-ignore", "-v", probe],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    return done.stdout.strip() if done.returncode == 0 else None


def timestamp_from_name(name: str) -> datetime | None:
    match = GRANULE_RE.search(name)
    if not match:
        return None
    date, clock = match.group(1), match.group(2)
    return datetime.strptime(date + clock, "%Y%m%d%H%M%S").replace(
        tzinfo=timezone.utc
    )


def existing_by_timestamp() -> dict[datetime, Path]:
    """Map granule start -> file, from filenames only (no file opening)."""
    if not RAW_DIR.is_dir():
        return {}
    found: dict[datetime, Path] = {}
    for path in sorted(RAW_DIR.glob("*.nc*")):
        stamp = timestamp_from_name(path.name)
        if stamp is not None and path.stat().st_size > 0:
            found.setdefault(stamp, path)
    return found


def contiguous_runs(stamps: list[datetime]) -> list[tuple[datetime, datetime]]:
    """Group sorted timestamps into contiguous half-hour runs."""
    if not stamps:
        return []
    step = timedelta(minutes=INTERVAL_MINUTES)
    runs, run_start, previous = [], stamps[0], stamps[0]
    for stamp in stamps[1:]:
        if stamp - previous != step:
            runs.append((run_start, previous))
            run_start = stamp
        previous = stamp
    runs.append((run_start, previous))
    return runs


def chunked(run: tuple[datetime, datetime]) -> list[tuple[datetime, datetime]]:
    """Split a run so no single Harmony job exceeds CHUNK_GRANULES."""
    step = timedelta(minutes=INTERVAL_MINUTES)
    start, end = run
    chunks, current = [], start
    while current <= end:
        stop = min(current + step * (CHUNK_GRANULES - 1), end)
        chunks.append((current, stop))
        current = stop + step
    return chunks


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------


def validate_collection(files: dict[datetime, Path],
                        wanted: list[datetime]) -> list[str]:
    """Structural checks over the downloaded set. Returns failure messages."""
    problems: list[str] = []

    missing = [s for s in wanted if s not in files]
    if missing:
        shown = ", ".join(label(s) for s in missing[:12])
        more = f" ... and {len(missing) - 12} more" if len(missing) > 12 else ""
        problems.append(
            f"{len(missing)} missing granule(s): {shown}{more}"
        )

    if len(files) != EXPECTED_GRANULES:
        problems.append(
            f"expected {EXPECTED_GRANULES} unique granules, found {len(files)}"
        )

    unique_paths = {p.resolve() for p in files.values()}
    if len(unique_paths) != len(files):
        problems.append("the same file is mapped to more than one timestamp")

    stamps = sorted(files)
    if stamps:
        if label(stamps[0]) != EXPECTED_FIRST + "Z":
            problems.append(
                f"first timestamp is {label(stamps[0])}, expected "
                f"{EXPECTED_FIRST}Z"
            )
        if label(stamps[-1]) != EXPECTED_LAST + "Z":
            problems.append(
                f"last timestamp is {label(stamps[-1])}, expected "
                f"{EXPECTED_LAST}Z"
            )
        step = timedelta(minutes=INTERVAL_MINUTES)
        bad = [
            (label(a), label(b))
            for a, b in zip(stamps, stamps[1:]) if b - a != step
        ]
        if bad:
            problems.append(
                f"{len(bad)} irregular interval(s), first: {bad[0][0]} -> "
                f"{bad[0][1]}"
            )

    return problems


def inspect_files(files: dict[datetime, Path]) -> list[str]:
    """Per-file grid/dimension/variable checks. Returns failure messages."""
    problems: list[str] = []
    reference = None
    for stamp in sorted(files):
        path = files[stamp]
        try:
            dataset = read_imerg_subset(path)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{label(stamp)}: unreadable ({exc})")
            continue
        try:
            dims = tuple(dataset["precipitation"].dims)
            if dims != ("time", "lat", "lon"):
                problems.append(f"{label(stamp)}: dims {dims}")
            grid = (
                tuple(np.round(dataset["lat"].values, 6)),
                tuple(np.round(dataset["lon"].values, 6)),
            )
            if reference is None:
                reference = grid
            elif grid != reference:
                problems.append(f"{label(stamp)}: lat/lon grid differs")
            names = set(map(str, dataset.variables)) | set(
                map(str, dataset.coords))
            unexpected = sorted(names - ALLOWED_NAMES)
            if unexpected:
                problems.append(
                    f"{label(stamp)}: unrelated variables {unexpected}"
                )
        finally:
            dataset.close()
    return problems


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )

    print(f"\n{RULE}\nIMERG EVENT PROCESSING — {EVENT_ID}\n{RULE}")

    start, end, provenance = read_scan_window()
    wanted = expected_timestamps(start, end)

    print(f"  window source     : {provenance}")
    print(f"  start             : {label(start)}")
    print(f"  end               : {label(end)}")
    print(f"  duration          : "
          f"{(end - start).total_seconds() / 3600:.5f} h")
    print(f"  bbox              : {DOWNLOAD_BBOX}")
    print(f"  expected granules : {len(wanted)}")

    # --- requirement 1: hard assertions before any submission -----------
    if len(wanted) > EXPECTED_GRANULES:
        print(f"\n  ABORT: window could yield {len(wanted)} granules, "
              f"limit {EXPECTED_GRANULES}. Nothing submitted.")
        return 1
    assert len(wanted) == EXPECTED_GRANULES, (
        f"expected {EXPECTED_GRANULES} granules, computed {len(wanted)}"
    )

    ignore_rule = data_raw_ignored()
    if not ignore_rule:
        print("\n  ABORT: data/raw is NOT ignored by Git. Nothing downloaded.")
        return 1
    print(f"  git ignore        : {ignore_rule}")

    # --- requirement 2: resume, never re-download, never delete ---------
    present = existing_by_timestamp()
    reused = len(present)
    print(f"  existing granules : {reused} (reused, nothing deleted)")

    missing = [s for s in wanted if s not in present]
    downloaded = 0
    if missing:
        runs = contiguous_runs(missing)
        jobs = [chunk for run in runs for chunk in chunked(run)]
        print(f"  missing granules  : {len(missing)} in {len(runs)} run(s), "
              f"{len(jobs)} Harmony job(s)")
        RAW_DIR.mkdir(parents=True, exist_ok=True)

        for index, (chunk_start, chunk_end) in enumerate(jobs, start=1):
            span = int((chunk_end - chunk_start).total_seconds() // 1800) + 1
            print(f"    job {index}/{len(jobs)}: {label(chunk_start)} .. "
                  f"{label(chunk_end)}  ({span} granules)", flush=True)
            paths = download_imerg_subset(
                start_time=label(chunk_start),
                # exclusive-style end so the next chunk does not overlap
                end_time=label(chunk_end + timedelta(minutes=29, seconds=59)),
                output_dir=RAW_DIR,
                bbox=DOWNLOAD_BBOX,
            )
            downloaded += len(paths)
            print(f"      received {len(paths)} file(s)", flush=True)

        present = existing_by_timestamp()
    else:
        print("  missing granules  : 0 — nothing to download")

    total_bytes = sum(p.stat().st_size for p in present.values())
    print(f"  granules on disk  : {len(present)}")
    print(f"  downloaded now    : {downloaded}")
    print(f"  total raw size    : {total_bytes / (1024 * 1024):.2f} MB")

    # --- requirement 3: validate before any rainfall maths --------------
    print(f"\n{RULE}\nCOLLECTION VALIDATION\n{RULE}")
    problems = validate_collection(present, wanted)
    if not problems:
        problems = inspect_files(present)

    if problems:
        print("  VALIDATION FAILED — stopping before rainfall calculation:")
        for item in problems:
            print(f"    - {item}")
        return 1

    print(f"  [PASS] {EXPECTED_GRANULES} unique files and timestamps")
    print("  [PASS] timestamps ascending, every interval 30 min")
    print(f"  [PASS] first {EXPECTED_FIRST}Z, last {EXPECTED_LAST}Z")
    print("  [PASS] identical lat/lon grid in every file")
    print("  [PASS] dimensions normalise to (time, lat, lon)")
    print("  [PASS] no duplicate timestamps, no unrelated science variables")

    # --- requirement 4: combine ----------------------------------------
    ordered = [present[s] for s in sorted(present)]
    combined = combine_imerg_subsets(
        ordered, expected_interval_minutes=INTERVAL_MINUTES
    )
    combined = precipitation_rate_to_depth(
        combined, interval_hours=INTERVAL_HOURS
    )

    shape = tuple(combined["precipitation"].shape)
    print(f"\n{RULE}\nCOMBINED EVENT\n{RULE}")
    print(f"  precipitation     : {tuple(combined['precipitation'].dims)} "
          f"{shape}")
    if shape != (EXPECTED_GRANULES, *EXPECTED_GRID):
        print(f"  ABORT: expected shape "
              f"{(EXPECTED_GRANULES, *EXPECTED_GRID)}")
        return 1

    rates = np.asarray(combined["precipitation"].values, dtype="float64")
    valid = rates[~np.isnan(rates)]
    print(f"  rate min          : {valid.min():.4f} mm/hr")
    print(f"  rate max          : {valid.max():.4f} mm/hr")
    print(f"  rate mean         : {valid.mean():.4f} mm/hr")
    print(f"  depth variable    : precipitation_depth_mm "
          f"{tuple(combined['precipitation_depth_mm'].shape)}")

    # --- requirement 5: rolling accumulations --------------------------
    result = add_rolling_accumulations(
        combined, windows=ROLLING_WINDOWS, interval_hours=INTERVAL_HOURS
    )

    print(f"\n{RULE}\nROLLING ACCUMULATIONS (trailing, propagate_nan)\n{RULE}")
    for name, count in ROLLING_WINDOWS.items():
        array = result[name]
        finite = np.asarray(array.values, dtype="float64")
        first_valid = int(np.argmax(np.any(np.isfinite(finite), axis=(1, 2))))
        print(f"  {name:<12} intervals={count:<3} "
              f"window={array.attrs['window_hours']:g} h  "
              f"dims={tuple(array.dims)} shape={tuple(array.shape)}  "
              f"first valid index={first_valid}")

    # --- requirement 6: wettest windows --------------------------------
    print(f"\n{RULE}\nWETTEST WINDOWS (derived from IMERG)\n{RULE}")
    wettest = {}
    for name in ROLLING_WINDOWS:
        info = find_wettest_window(result, name,
                                   interval_hours=INTERVAL_HOURS)
        wettest[name] = info
        if info.get("max_mm") is None:
            print(f"  {name:<12} no complete window")
            continue
        print(f"  {name:<12} max {info['max_mm']:.4f} mm  "
              f"{info['window_start_utc']} -> {info['window_end_utc']}  "
              f"lat {info['lat']:.3f} lon {info['lon']:.3f}")

    three_hour = wettest["rain_3h_mm"]

    # --- requirement 8: quality + completeness -------------------------
    depth_values = np.asarray(result["precipitation"].values, dtype="float64")
    missing_mask = np.isnan(depth_values)
    per_step_missing = missing_mask.any(axis=(1, 2))
    times = np.atleast_1d(result["time"].values)
    stamps = [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in times]

    longest_run = current_run = 0
    for flag in per_step_missing:
        current_run = current_run + 1 if flag else 0
        longest_run = max(longest_run, current_run)

    completeness = 100.0 * len(present) / EXPECTED_GRANULES

    print(f"\n{RULE}\nQUALITY AND COMPLETENESS\n{RULE}")
    print(f"  expected granules : {EXPECTED_GRANULES}")
    print(f"  available granules: {len(present)}")
    print(f"  completeness      : {completeness:.2f} %")
    print(f"  valid cells       : {int((~missing_mask).sum())}")
    print(f"  missing cells     : {int(missing_mask.sum())}")
    print(f"  steps with any NaN: {int(per_step_missing.sum())}")
    print(f"  max consecutive   : {longest_run}")
    print("  interpolation     : NONE performed")

    # --- requirement 9: save NetCDF ------------------------------------
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    result.attrs.update({
        "event_id": EVENT_ID,
        "source_product": SOURCE_PRODUCT,
        "processing": (
            "Harmony spatial+variable subset; combined on time; trailing "
            "rolling accumulations with min_periods=interval_count and "
            "propagate_nan; no interpolation; no catchment aggregation"
        ),
        "bbox_west_south_east_north": list(DOWNLOAD_BBOX),
        "scan_window_start_utc": label(start),
        "scan_window_end_utc": label(end),
        "interval_hours": INTERVAL_HOURS,
        "granule_count": len(present),
        "timing_contract": "docs/event_dates.md",
        "spatial_scope": "IMERG grid cells only (no catchment polygons)",
    })
    result["time"].encoding.setdefault(
        "units", "seconds since 1980-01-06 00:00:00"
    )
    result.to_netcdf(OUTPUT_NC)

    # --- requirement 8/9: summary JSON ---------------------------------
    summary = {
        "event_id": EVENT_ID,
        "source_product": SOURCE_PRODUCT,
        "timing_contract": "docs/event_dates.md",
        "scan_window": {
            "start_utc": label(start),
            "end_utc": label(end),
            "duration_hours": round((end - start).total_seconds() / 3600, 5),
            "provenance": provenance,
        },
        "bbox": {
            "west": DOWNLOAD_BBOX[0], "south": DOWNLOAD_BBOX[1],
            "east": DOWNLOAD_BBOX[2], "north": DOWNLOAD_BBOX[3],
        },
        "granules": {
            "expected": EXPECTED_GRANULES,
            "available": len(present),
            "downloaded_this_run": downloaded,
            "reused": reused,
            "completeness_percent": round(completeness, 4),
            "raw_bytes": int(total_bytes),
            "first_timestamp_utc": stamps[0],
            "last_timestamp_utc": stamps[-1],
            "interval_minutes": INTERVAL_MINUTES,
        },
        "grid": {
            "shape_time_lat_lon": list(shape),
            "lat": [round(float(v), 6) for v in result["lat"].values],
            "lon": [round(float(v), 6) for v in result["lon"].values],
        },
        "precipitation_rate_mm_per_hr": {
            "min": float(valid.min()),
            "max": float(valid.max()),
            "mean": float(valid.mean()),
        },
        "quality": {
            "total_valid_cells": int((~missing_mask).sum()),
            "total_missing_cells": int(missing_mask.sum()),
            "timestamps_with_missing_values": [
                stamps[i] for i, flag in enumerate(per_step_missing) if flag
            ],
            "max_consecutive_missing_intervals": int(longest_run),
            "interpolation_performed": False,
            "missing_data_policy": "propagate_nan",
        },
        "wettest_windows": wettest,
        "wettest_3h_window_utc": {
            "start": three_hour.get("window_start_utc"),
            "end": three_hour.get("window_end_utc"),
            "max_rain_3h_mm": three_hour.get("max_mm"),
            "lat": three_hour.get("lat"),
            "lon": three_hour.get("lon"),
            "derivation": (
                "Derived from NASA GPM IMERG V07 over the Aqaba "
                "DOWNLOAD_BBOX, not directly reported by the paper."
            ),
        },
        "scope": {
            "catchment_aggregation_performed": False,
            "global_hdf5_downloaded": False,
        },
    }
    OUTPUT_JSON.write_text(json.dumps(summary, indent=2) + "\n")

    result.close()
    combined.close()

    print(f"\n{RULE}\nOUTPUT\n{RULE}")
    print(f"  netcdf            : {OUTPUT_NC.relative_to(PROJECT_ROOT)} "
          f"({OUTPUT_NC.stat().st_size / 1024:.1f} KB)")
    print(f"  summary json      : {OUTPUT_JSON.relative_to(PROJECT_ROOT)} "
          f"({OUTPUT_JSON.stat().st_size / 1024:.1f} KB)")

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    ).stdout
    leaked = [ln for ln in status.splitlines()
              if ".nc" in ln.lower() or EVENT_ID in ln]
    print(f"  git sees data     : "
          f"{'YES -> ' + str(leaked) if leaked else 'NO'}")
    print(f"{RULE}\n")

    print("WETTEST_3H_START=" + str(three_hour.get("window_start_utc")))
    print("WETTEST_3H_END=" + str(three_hour.get("window_end_utc")))
    print("WETTEST_3H_MM=" + str(three_hour.get("max_mm")))
    print("WETTEST_3H_LAT=" + str(three_hour.get("lat")))
    print("WETTEST_3H_LON=" + str(three_hour.get("lon")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
