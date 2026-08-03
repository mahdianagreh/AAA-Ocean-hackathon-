#!/usr/bin/env python3
"""Turn daily IMERG granules into per-catchment daily rainfall.

This is where the sweep stops being a pile of files and becomes the thing the
model trains on: one rainfall number per catchment per day, area-weighted
against Mahdi's real 30 m delineation.

Why area-weighted, and not a bounding box
-----------------------------------------
IMERG cells are ~0.1 deg (~107 km2 here). AQ-C01 spans 61 of them and AQ-C05
just 4. A cell that lies half inside a catchment must contribute half its
weight, or small catchments inherit rainfall that fell outside them. The
weights come from real polygon intersection in UTM 36N — never from degrees,
and never from a box.

Missing is never zero
---------------------
A NaN cell contributes to neither the numerator nor the denominator, so a
partly-observed catchment reports the mean of what was actually observed plus
a `valid_area_fraction` saying how much that was. It is never silently
diluted toward zero.

Usage
-----
    python scripts/aggregate_daily_to_catchments.py
    python scripts/aggregate_daily_to_catchments.py --limit 200   # smoke test

Output
------
    data/processed/features/catchment_rainfall_daily.parquet
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

import pandas as pd  # noqa: E402

from config.spatial import CRS_MEASURE, TERRAIN_AOI  # noqa: E402
from ingestion.imerg import (  # noqa: E402
    combine_imerg_subsets,
    get_imerg_product,
    granule_timestamp_from_name,
    precipitation_rate_to_depth,
)
from processing.catchment_rainfall import (  # noqa: E402
    OUTPUT_NAMES_BY_RATE_UNIT,
    aggregate_catchment_rainfall,
    build_grid_cells,
    compute_overlaps,
    coverage_by_catchment,
    load_catchments,
)

RUN_TYPE = "daily_final"
DAILY_DIR = PROJECT_ROOT / "data" / "raw" / "imerg" / "daily_final"
CATCHMENTS = PROJECT_ROOT / "data" / "processed" / "vectors" / "catchments.gpkg"
OUT_PARQUET = (
    PROJECT_ROOT / "data" / "processed" / "features" / "catchment_rainfall_daily.parquet"
)
OUT_SUMMARY = OUT_PARQUET.with_suffix(".summary.json")

#: Granules per read batch. The full record is ~10,300 files; opening them all
#: at once is needless memory pressure when the aggregation is per-timestamp.
BATCH_GRANULES = 400

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aggregate")


def aggregate_batch(paths, catchments, product) -> pd.DataFrame:
    """Aggregate one batch of daily granules to per-catchment rows."""
    combined = combine_imerg_subsets(
        paths, expected_interval_minutes=product["granule_minutes"]
    )

    # mm/day over a 24 h granule: the value already IS the depth. Passing the
    # half-hourly rule here would understate it 48-fold, so both terms come
    # from the registry rather than a literal.
    interval_hours = product["granule_minutes"] / 60.0
    combined = precipitation_rate_to_depth(
        combined,
        interval_hours=interval_hours,
        rate_period_hours=product["rate_period_hours"],
    )

    cells = build_grid_cells(combined)
    overlaps = compute_overlaps(cells, catchments)

    return aggregate_catchment_rainfall(
        combined,
        overlaps,
        event_id="DAILY-SWEEP",
        geometry_status="REAL",
        variables=("precipitation", "precipitation_depth_mm"),
        # The daily product is mm/day. The default column name says mm_hr,
        # which would put a 24x-wrong unit in the schema with a confident
        # label on it.
        output_names=OUTPUT_NAMES_BY_RATE_UNIT[product["rate_units"]],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily-dir", type=Path, default=DAILY_DIR)
    parser.add_argument("--catchments", type=Path, default=CATCHMENTS)
    parser.add_argument("--output", type=Path, default=OUT_PARQUET)
    parser.add_argument("--batch", type=int, default=BATCH_GRANULES)
    parser.add_argument(
        "--limit", type=int, default=0,
        help="only process the first N granules (smoke test)",
    )
    args = parser.parse_args()

    product = get_imerg_product(RUN_TYPE)

    paths = sorted(args.daily_dir.glob("*.nc*"))
    if args.limit:
        paths = paths[: args.limit]
    if not paths:
        logger.error("no daily granules under %s — run scripts/sweep_imerg_daily.py",
                     args.daily_dir)
        return 1

    catchments = load_catchments(args.catchments)
    if catchments["provisional"].any():
        logger.warning("catchments are PROVISIONAL — results are structural only")

    logger.info("Per-catchment daily rainfall")
    logger.info("  granules    %d", len(paths))
    logger.info("  catchments  %d (%s)", len(catchments),
                ", ".join(catchments["catchment_id"]))
    logger.info("  units       %s -> mm via rate_period_hours=%s",
                product["rate_units"], product["rate_period_hours"])
    logger.info("  weighting   area-weighted overlap in %s", CRS_MEASURE)

    # Split into CONTIGUOUS runs before batching. combine_imerg_subsets
    # validates that granule spacing is regular, and it is right to: stitching
    # across a gap would silently concatenate two different periods into one
    # series. But the real record does have gaps — a day genuinely absent from
    # the archive, or a sweep still in progress — so the aggregation groups
    # around them rather than refusing to run.
    step = timedelta(minutes=product["granule_minutes"])
    runs: list[list[Path]] = []
    current: list[Path] = []
    previous = None
    for path in paths:
        stamp = granule_timestamp_from_name(path.name)
        if stamp is None:
            continue
        if previous is not None and stamp - previous != step:
            runs.append(current)
            current = []
        current.append(path)
        previous = stamp
    if current:
        runs.append(current)

    if len(runs) > 1:
        logger.info("  %d contiguous run(s) — the record has gaps, so each is "
                    "aggregated separately rather than stitched", len(runs))

    frames: list[pd.DataFrame] = []
    processed = 0
    for run in runs:
        for start in range(0, len(run), args.batch):
            batch = run[start : start + args.batch]
            frames.append(aggregate_batch(batch, catchments, product))
            processed += len(batch)
            logger.info("  %d/%d granule(s) aggregated", processed, len(paths))

    table = pd.concat(frames, ignore_index=True)
    table = table.sort_values(["timestamp_utc", "catchment_id"]).reset_index(drop=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(args.output, index=False)

    # Coverage is recomputed from the last batch's geometry: it is a property
    # of the grid and the polygons, not of any particular day.
    coverage = coverage_by_catchment(
        compute_overlaps(
            build_grid_cells(
                combine_imerg_subsets(
                    paths[: min(len(paths), 1)],
                    expected_interval_minutes=product["granule_minutes"],
                )
            ),
            catchments,
        )
    )

    depth = table["precipitation_depth_mm_mean"] if (
        "precipitation_depth_mm_mean" in table.columns
    ) else table.get("precipitation_depth_mm")

    summary = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_product": product["short_name"],
        "collection_id": product["collection_id"],
        "native_units": product["rate_units"],
        "granules_used": len(paths),
        "rows": int(len(table)),
        "catchments": sorted(catchments["catchment_id"]),
        "bbox_wsen": list(TERRAIN_AOI.wsen),
        "measurement_crs": CRS_MEASURE,
        "grid_coverage_by_catchment": {k: round(v, 6) for k, v in coverage.items()},
        "date_range_utc": [
            str(table["timestamp_utc"].min()),
            str(table["timestamp_utc"].max()),
        ],
        "caveats": [
            "Daily screening resolution. Sub-daily intensity — what actually "
            "drives a flash flood — requires the half-hourly product (stage 2).",
            "Rainfall over the ~2,000 km2 of endorheic basins is excluded by "
            "the catchment polygons themselves: it never reaches the Gulf.",
            "Missing cells contribute to neither numerator nor denominator; "
            "see valid_area_fraction. Nothing is interpolated.",
        ],
    }
    if depth is not None:
        summary["depth_mm"] = {
            "min": float(depth.min()),
            "max": float(depth.max()),
            "mean": round(float(depth.mean()), 4),
        }

    OUT_SUMMARY.write_text(json.dumps(summary, indent=2) + "\n")

    logger.info("wrote %s (%d rows)", args.output.relative_to(PROJECT_ROOT), len(table))
    logger.info("wrote %s", OUT_SUMMARY.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
