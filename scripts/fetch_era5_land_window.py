#!/usr/bin/env python
"""Fetch an arbitrary ERA5-Land window over an arbitrary bounding box.

Event-agnostic CLI wrapper around fetch_era5_land_window(). Nothing about the
October 2016 event is hard-coded; every parameter comes from the command line.

Example:

    python scripts/fetch_era5_land_window.py \\
      --start 2016-10-26T00:00:00Z --end 2016-10-27T23:00:00Z \\
      --north 29.70 --west 34.80 --south 29.25 --east 35.15 \\
      --variables soil_moisture,total_precipitation \\
      --output-dir data/raw/era5_land/example_window

Credentials come from ~/.cdsapirc via cdsapi; none are read or printed here.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from ingestion.era5_land import (  # noqa: E402
    DEFAULT_MAX_EXPECTED_TIMESTAMPS,
    GRID_ALIGNMENT_WARNING,
    fetch_era5_land_window,
    validate_era5_land_window,
)

RULE = "=" * 76


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).astimezone(timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, type=parse_utc)
    parser.add_argument("--end", required=True, type=parse_utc)
    parser.add_argument("--north", required=True, type=float)
    parser.add_argument("--west", required=True, type=float)
    parser.add_argument("--south", required=True, type=float)
    parser.add_argument("--east", required=True, type=float)
    parser.add_argument(
        "--variables", required=True,
        help="comma-separated canonical keys, CDS names or short names",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--chunk-mode", choices=("daily", "monthly"), default="daily"
    )
    parser.add_argument(
        "--max-timestamps", type=int,
        default=DEFAULT_MAX_EXPECTED_TIMESTAMPS,
    )
    parser.add_argument("--allow-over-limit", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="plan and validate only; submit nothing",
    )
    return parser


def data_raw_ignored(path: Path) -> bool:
    try:
        relative = path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        return True          # outside the repo entirely
    done = subprocess.run(
        ["git", "check-ignore", "-q", str(relative / "probe.nc")],
        cwd=PROJECT_ROOT, capture_output=True,
    )
    return done.returncode == 0


def main() -> int:
    args = build_parser().parse_args()
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    variables = [v.strip() for v in args.variables.split(",") if v.strip()]
    bbox = [args.north, args.west, args.south, args.east]
    hours = int((args.end - args.start).total_seconds() // 3600) + 1

    print(f"\n{RULE}\nERA5-LAND WINDOW FETCH\n{RULE}")
    print(f"  start             : {args.start.isoformat()}")
    print(f"  end               : {args.end.isoformat()}")
    print(f"  bbox [N, W, S, E] : {bbox}")
    print(f"  variables         : {variables}")
    print(f"  hourly timestamps : {hours}")
    print(f"  chunk mode        : {args.chunk_mode}")
    print(f"  output dir        : {args.output_dir}")

    if not data_raw_ignored(args.output_dir):
        print(f"\n  ABORT: {args.output_dir} is not ignored by Git.")
        return 1

    if args.dry_run:
        print("\n  DRY RUN — nothing submitted.")
        return 0

    paths = fetch_era5_land_window(
        start_time=args.start, end_time=args.end, bbox=bbox,
        variables=variables, output_dir=args.output_dir,
        chunk_mode=args.chunk_mode, overwrite=args.overwrite,
        max_expected_timestamps=args.max_timestamps,
        allow_over_limit=args.allow_over_limit,
    )

    print(f"\n{RULE}\nFILES\n{RULE}")
    for path in paths:
        print(f"  {path.name}  ({path.stat().st_size / 1024:.1f} KB)")

    report = validate_era5_land_window(
        paths, args.start, args.end, variables, bbox=bbox
    )
    print(f"\n{RULE}\nVALIDATION\n{RULE}")
    for key in ("expected_timestamps", "actual_timestamps",
                "unique_timestamps", "hourly_spacing", "first_utc",
                "last_utc", "variables_present", "variables_unexpected",
                "lat_range", "lon_range"):
        print(f"  {key:<22}: {report[key]}")
    print(f"\n  {GRID_ALIGNMENT_WARNING}")
    print(f"{RULE}\n")

    manifest = args.output_dir / "window_manifest.json"
    manifest.write_text(json.dumps(report, indent=2) + "\n")
    print(f"  manifest -> {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
