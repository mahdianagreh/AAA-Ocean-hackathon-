#!/usr/bin/env python
"""Build the rainfall candidate table from processed IMERG windows.

Scans whatever processed windows are given (or discovered) and writes a ranked
candidate table. The scope is recorded on every row and ``is_exhaustive`` stays
False unless a genuine full-archive sweep was performed — this output must
never be mistaken for a complete historical event catalogue.

Offline: reads local processed files only.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from processing.event_mining import (  # noqa: E402
    rank_rainfall_candidates,
    separate_by_run_type,
)

DEFAULT_OUTPUT = (
    PROJECT_ROOT / "data" / "processed" / "events" / "rainfall_candidates.parquet"
)
RULE = "=" * 78


def discover_processed_windows() -> list[Path]:
    """Processed IMERG NetCDFs already on disk."""
    roots = [
        PROJECT_ROOT / "data" / "processed" / "events",
        PROJECT_ROOT / "data" / "processed" / "live",
    ]
    found: dict[str, Path] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.nc")):
            name = path.name.lower()
            if "imerg" not in name and "early" not in name:
                continue
            # Prefer the event-namespaced copy over any legacy file sitting in
            # the events/ root, so the same window is not ranked twice.
            existing = found.get(path.name)
            if existing is None or len(path.parts) > len(existing.parts):
                found[path.name] = path
    return sorted(found.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="*", type=Path,
                        help="processed IMERG NetCDF files; discovered if omitted")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--percentile", type=float, default=95.0)
    parser.add_argument("--separation-hours", type=int, default=24)
    parser.add_argument("--ranking-variable", default="rain_3h_mm")
    parser.add_argument(
        "--scope", default="configured demonstration windows",
        help="free text describing what was searched",
    )
    parser.add_argument(
        "--exhaustive", action="store_true",
        help="ONLY set after a genuine full-archive sweep",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    inputs = args.inputs or discover_processed_windows()
    print(f"\n{RULE}\nRAINFALL CANDIDATE MINING\n{RULE}")
    print(f"  ranking variable  : {args.ranking_variable}")
    print(f"  percentile        : {args.percentile}")
    print(f"  min separation    : {args.separation_hours} h")
    print(f"  scope             : {args.scope}")
    print(f"  is_exhaustive     : {args.exhaustive}")
    print(f"  inputs            : {len(inputs)}")
    for path in inputs:
        print(f"    {path.relative_to(PROJECT_ROOT)}")

    if not inputs:
        print("\n  No processed IMERG windows found. Nothing to rank.")
        return 1

    datasets, usable = [], []
    for path in inputs:
        dataset = xr.open_dataset(path)
        if args.ranking_variable in dataset.variables:
            datasets.append(dataset)
            usable.append(path)
        else:
            print(f"  skipping {path.name}: no {args.ranking_variable}")
            dataset.close()

    if not datasets:
        print(f"\n  No input carries {args.ranking_variable}.")
        return 1

    try:
        frame = rank_rainfall_candidates(
            datasets,
            percentile_threshold=args.percentile,
            minimum_separation_hours=args.separation_hours,
            ranking_variable=args.ranking_variable,
            candidate_generation_scope=args.scope,
            is_exhaustive=args.exhaustive,
        )
    finally:
        for dataset in datasets:
            dataset.close()

    print(f"\n{RULE}\nCANDIDATES\n{RULE}")
    print(f"  rows              : {len(frame)}")
    if not frame.empty:
        columns = ["event_id", "peak_time_utc", "rain_3h_mm", "rain_24h_mm",
                   "historical_percentile", "anomaly_score", "run_type",
                   "quality_score"]
        available = [c for c in columns if c in frame.columns]
        print(frame[available].head(15).to_string(index=False))

        groups = separate_by_run_type(frame)
        print(f"\n  by run type       : "
              f"{ {k: len(v) for k, v in groups.items()} }")
        print(f"  scope             : {frame['search_scope_start_utc'].iloc[0]}"
              f" .. {frame['search_scope_end_utc'].iloc[0]}")
        print(f"  is_exhaustive     : {bool(frame['is_exhaustive'].iloc[0])}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)

    summary = {
        "output": str(args.output),
        "row_count": int(len(frame)),
        "inputs": [str(p) for p in usable],
        "ranking_variable": args.ranking_variable,
        "percentile_threshold": args.percentile,
        "minimum_separation_hours": args.separation_hours,
        "candidate_generation_scope": args.scope,
        "is_exhaustive": bool(args.exhaustive),
        "run_type_counts": (
            {k: int(len(v)) for k, v in separate_by_run_type(frame).items()}
            if not frame.empty else {}
        ),
        "warning": (
            "is_exhaustive is False: this table covers only the configured "
            "windows and must not be read as a complete historical catalogue."
        ) if not args.exhaustive else None,
    }
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"\n{RULE}\nOUTPUT\n{RULE}")
    print(f"  parquet : {args.output} "
          f"({args.output.stat().st_size / 1024:.1f} KB)")
    print(f"  summary : {summary_path}")
    if not args.exhaustive:
        print("\n  NOTE: is_exhaustive=False — configured windows only, not a "
              "complete historical catalogue.")
    print(f"{RULE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
