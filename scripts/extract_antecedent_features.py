#!/usr/bin/env python
"""Extract antecedent features for any event time from an ERA5-Land file.

Event-agnostic CLI. The event timestamp, window lengths and input file are all
arguments — nothing about a specific event lives in this script or in the
reusable functions it calls.

Example:

    python scripts/extract_antecedent_features.py \\
      --input data/processed/events/era5_land_hourly_20161026_20161027.nc \\
      --event-time 2016-10-28T00:00:00Z --event-id AQ-2016-10-28 \\
      --output-dir data/processed/events --allow-partial

Reads local files only; performs no download.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from processing.antecedent_features import (  # noqa: E402
    antecedent_features_to_dataframe,
    extract_antecedent_features,
)

RULE = "=" * 76


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).astimezone(timezone.utc)


def int_list(value: str) -> list[int]:
    return [int(v) for v in value.split(",") if v.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--event-time", required=True, type=parse_utc)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--output-dir", type=Path,
                        default=PROJECT_ROOT / "data" / "processed" / "events")
    parser.add_argument("--soil-offsets", type=int_list, default=[24, 72])
    parser.add_argument("--precip-windows", type=int_list,
                        default=[24, 72, 168])
    parser.add_argument("--runoff-windows", type=int_list,
                        default=[24, 72, 168])
    parser.add_argument("--state-window", type=int, default=6)
    parser.add_argument("--min-valid-fraction", type=float, default=1.0)
    parser.add_argument("--allow-partial", action="store_true",
                        help="accept windows the dataset cannot fully cover")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    print(f"\n{RULE}\nANTECEDENT FEATURE EXTRACTION\n{RULE}")
    print(f"  input        : {args.input}")
    print(f"  event id     : {args.event_id}")
    print(f"  event time   : {args.event_time.isoformat()}")
    print(f"  soil offsets : {args.soil_offsets} h")
    print(f"  precip wins  : {args.precip_windows} h")
    print(f"  runoff wins  : {args.runoff_windows} h")
    print(f"  state window : {args.state_window} h")

    if not args.input.exists():
        print(f"\n  MISSING INPUT: {args.input}")
        return 1

    dataset = xr.open_dataset(args.input)
    try:
        features = extract_antecedent_features(
            dataset, args.event_time,
            soil_moisture_offsets_hours=args.soil_offsets,
            precipitation_windows_hours=args.precip_windows,
            runoff_windows_hours=args.runoff_windows,
            state_window_hours=args.state_window,
            minimum_valid_fraction=args.min_valid_fraction,
            require_full_windows=not args.allow_partial,
        )
    finally:
        dataset.close()

    print(f"\n{RULE}\nFEATURES\n{RULE}")
    for name in sorted(features.data_vars):
        if name.endswith("_valid_fraction") or name == "quality_flag":
            continue
        values = np.asarray(features[name].values, dtype="float64") \
            if features[name].dtype.kind == "f" else None
        if values is None:
            continue
        finite = values[np.isfinite(values)]
        units = features[name].attrs.get("units", "")
        if finite.size:
            print(f"  {name:<42} {finite.min():>10.4f} .. {finite.max():<10.4f}"
                  f" mean {finite.mean():>10.4f} {units}")
        else:
            print(f"  {name:<42} all NaN")

    flags, counts = np.unique(
        np.asarray(features["quality_flag"].values).ravel(), return_counts=True
    )
    print(f"\n  quality flags : {dict(zip(flags.tolist(), counts.tolist()))}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame = antecedent_features_to_dataframe(features, args.event_id)
    parquet = args.output_dir / f"{args.event_id}_antecedent_features.parquet"
    frame.to_parquet(parquet, index=False)

    summary = {
        "event_id": args.event_id,
        "event_time_utc": features.attrs["event_time_utc"],
        "input_file": str(args.input),
        "rows": int(len(frame)),
        "feature_count": int(len(features.data_vars)),
        "attributes": {k: str(v) for k, v in features.attrs.items()},
        "quality_flag_counts": {
            str(k): int(v) for k, v in zip(flags.tolist(), counts.tolist())
        },
    }
    summary_path = (
        args.output_dir / f"{args.event_id}_antecedent_features_summary.json"
    )
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(f"\n{RULE}\nOUTPUT\n{RULE}")
    print(f"  parquet : {parquet}  ({parquet.stat().st_size / 1024:.1f} KB, "
          f"{len(frame)} rows)")
    print(f"  summary : {summary_path}")
    print(f"{RULE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
