#!/usr/bin/env python
"""Aggregate processed IMERG rainfall onto project catchments.

Reads the processed event NetCDF and the catchment polygons, computes
area-weighted catchment rainfall, and writes the Parquet + summary JSON.

Downloads nothing. Writes no GeoPackage — catchments are a hard input and are
never fabricated. When neither the real nor the provisional catchment file
exists the script stops with an actionable dependency error and writes nothing.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import numpy as np
import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from processing.catchment_rainfall import (  # noqa: E402
    MissingCatchmentsError,
    aggregate_catchment_rainfall,
    build_grid_cells,
    build_summary,
    compare_with_grid_peak,
    compute_overlaps,
    coverage_by_catchment,
    load_catchments,
    resolve_catchment_source,
    wettest_windows_per_catchment,
)

EVENT_ID = "AQ-2016-10-28"
INTERVAL_HOURS = 0.5
FLOOD_ARRIVAL_UTC = "2016-10-28T00:00:00Z"

EVENT_NC = PROJECT_ROOT / "data" / "processed" / "events" / f"{EVENT_ID}_imerg.nc"
EVENT_SUMMARY = (
    PROJECT_ROOT / "data" / "processed" / "events" / f"{EVENT_ID}_summary.json"
)

VECTOR_DIR = PROJECT_ROOT / "data" / "processed" / "vectors"
REAL_CATCHMENTS = VECTOR_DIR / "catchments.gpkg"
PROVISIONAL_CATCHMENTS = VECTOR_DIR / "catchments_PROVISIONAL.gpkg"

OUTPUT_PARQUET = (
    PROJECT_ROOT / "data" / "processed" / "events"
    / f"{EVENT_ID}_catchment_rainfall.parquet"
)
OUTPUT_JSON = (
    PROJECT_ROOT / "data" / "processed" / "events"
    / f"{EVENT_ID}_catchment_summary.json"
)

RULE = "=" * 74


def grid_level_peak() -> dict:
    """The grid-level wettest 3 h result recorded by the event processing."""
    if not EVENT_SUMMARY.exists():
        return {}
    payload = json.loads(EVENT_SUMMARY.read_text())
    wettest = payload.get("wettest_windows", {}).get("rain_3h_mm", {})
    if wettest:
        return wettest
    return payload.get("wettest_3h_window_utc", {})


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    print(f"\n{RULE}\nCATCHMENT RAINFALL AGGREGATION — {EVENT_ID}\n{RULE}")

    if not EVENT_NC.exists():
        print(f"  MISSING INPUT: {EVENT_NC}")
        print("  Run scripts/process_imerg_oct2016_event.py first.")
        return 1
    print(f"  rainfall input    : {EVENT_NC.relative_to(PROJECT_ROOT)}")

    # --- hard dependency: catchment polygons ---------------------------
    print(f"  preferred vectors : "
          f"{REAL_CATCHMENTS.relative_to(PROJECT_ROOT)}")
    print(f"  fallback vectors  : "
          f"{PROVISIONAL_CATCHMENTS.relative_to(PROJECT_ROOT)}")
    try:
        source = resolve_catchment_source(
            REAL_CATCHMENTS, PROVISIONAL_CATCHMENTS
        )
    except MissingCatchmentsError as exc:
        print(f"\n{RULE}\nMISSING DEPENDENCY — STOPPING\n{RULE}")
        print(str(exc))
        print(f"{RULE}")
        print("  No outputs written. No GeoPackage created. "
              "Nothing downloaded.")
        print(f"{RULE}\n")
        return 2

    print(f"  using             : {source.path.relative_to(PROJECT_ROOT)}")
    print(f"  geometry status   : {source.status}")

    catchments = load_catchments(source.path)
    print(f"  catchments        : {len(catchments)} "
          f"({', '.join(sorted(map(str, catchments['catchment_id'])))})")

    dataset = xr.open_dataset(EVENT_NC)
    try:
        cells = build_grid_cells(dataset)
        print(f"  imerg cells       : {len(cells)}")

        overlaps = compute_overlaps(cells, catchments)
        print(f"  overlaps          : {len(overlaps)}")

        coverage = coverage_by_catchment(overlaps)
        print(f"\n{RULE}\nCOVERAGE (raw, not normalised)\n{RULE}")
        for catchment_id in sorted(coverage):
            print(f"  {catchment_id:<10} {coverage[catchment_id] * 100:7.3f} %")

        frame = aggregate_catchment_rainfall(
            dataset, overlaps,
            event_id=EVENT_ID, geometry_status=source.status,
        )
        print(f"\n{RULE}\nAGGREGATED\n{RULE}")
        print(f"  rows              : {len(frame)}")
        print(f"  timestamps        : {frame['timestamp_utc'].nunique()}")
        print(f"  quality flags     : "
              f"{dict(frame['quality_flag'].value_counts())}")

        windows = wettest_windows_per_catchment(
            frame, interval_hours=INTERVAL_HOURS
        )
        print(f"\n{RULE}\nWETTEST WINDOWS PER CATCHMENT\n{RULE}")
        for catchment_id in sorted(windows):
            print(f"  {catchment_id}")
            for variable, info in windows[catchment_id].items():
                if info.get("max_mm") is None:
                    print(f"    {variable:<12} no complete window")
                    continue
                print(f"    {variable:<12} {info['max_mm']:8.4f} mm  "
                      f"{info['start_utc']} -> {info['end_utc']}  "
                      f"[{info['quality_flag']}]")

        comparison = compare_with_grid_peak(
            windows, grid_level_peak(),
            flood_arrival_utc=FLOOD_ARRIVAL_UTC,
        )
        print(f"\n{RULE}\nSPATIAL-CONSISTENCY CHECK (no causal claim)\n{RULE}")
        grid = comparison["grid_level"]
        print(f"  grid 3 h peak     : {grid.get('max_mm')} mm  "
              f"{grid.get('window_start_utc')} -> {grid.get('window_end_utc')}")
        print(f"  changes peak time : "
              f"{comparison['aggregation_changes_peak_time']}")
        print(f"  changes peak rain : "
              f"{comparison['aggregation_changes_peak_rainfall']}")
        print(f"  any peak before flood arrival : "
              f"{comparison['any_catchment_peak_before_flood_arrival']}")
        print(f"  all peaks before flood arrival: "
              f"{comparison['all_catchment_peaks_before_flood_arrival']}")

        summary = build_summary(
            EVENT_ID, source, catchments, cells, overlaps, frame,
            windows, comparison,
        )

        OUTPUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(OUTPUT_PARQUET, index=False)
        OUTPUT_JSON.write_text(json.dumps(summary, indent=2) + "\n")
    finally:
        dataset.close()

    print(f"\n{RULE}\nOUTPUT\n{RULE}")
    print(f"  parquet           : {OUTPUT_PARQUET.relative_to(PROJECT_ROOT)} "
          f"({OUTPUT_PARQUET.stat().st_size / 1024:.1f} KB)")
    print(f"  summary json      : {OUTPUT_JSON.relative_to(PROJECT_ROOT)} "
          f"({OUTPUT_JSON.stat().st_size / 1024:.1f} KB)")

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    ).stdout
    leaked = [ln for ln in status.splitlines()
              if ".parquet" in ln or "catchment_summary" in ln]
    print(f"  git sees data     : "
          f"{'YES -> ' + str(leaked) if leaked else 'NO'}")
    print("  downloads         : NONE")
    print(f"{RULE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
