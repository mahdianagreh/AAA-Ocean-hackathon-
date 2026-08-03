#!/usr/bin/env python3
"""Re-rank the candidate storms by rainfall INTENSITY, not daily total.

Why
---
Stage 1 ranked 10,135 days by daily depth, because that is all a daily product
can measure. But intensity is what floods a wadi: 17 mm spread evenly over a
day does nothing, and 6 mm concentrated into three hours produces a flood.

The one event we can check against reality says so plainly. Kalman et al.
(2025) report that **82 % of the October 2016 rainfall fell in an 18-hour
spell**, and it moved ~24,400 t of sediment into the Gulf. Ranked by daily
total over its own catchment it sits **27th of 10,135 days** — comfortably
inside the top 0.3 %, but nowhere near the top 3 that `tasks/phase2/01-karam.md`
set as its acceptance test.

That is the daily-screening limitation this project already documented,
showing up on the one event with ground truth. Stage 2 bought half-hourly data
precisely so the ranking need not stop there.

This script does not assume the intensity ranking is kinder to October 2016.
It reports where the event lands either way, because the answer decides
whether daily screening is a sound basis for the training set.

Usage
-----
    python scripts/rank_events_by_intensity.py
    python scripts/rank_events_by_intensity.py --window 3
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

import pandas as pd  # noqa: E402

from config.spatial import TERRAIN_AOI  # noqa: E402
from ingestion.imerg import process_imerg_window  # noqa: E402
from processing.catchment_rainfall import (  # noqa: E402
    aggregate_catchment_rainfall,
    build_grid_cells,
    compute_overlaps,
    load_catchments,
)

EVENTS = PROJECT_ROOT / "data" / "processed" / "events" / "events.parquet"
GRANULE_ROOT = PROJECT_ROOT / "data" / "raw" / "imerg" / "events"
CATCHMENTS = PROJECT_ROOT / "data" / "processed" / "vectors" / "catchments.gpkg"
OUT = PROJECT_ROOT / "data" / "processed" / "events" / "events_by_intensity.parquet"
SUMMARY = OUT.with_suffix(".summary.json")

DEMO_EVENT = "AQ-2016-10-28"
#: Minimum granules before an event's intensity is trusted. A part-downloaded
#: window would understate the peak, which is worse than reporting nothing.
MIN_GRANULES = 130

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
                    datefmt="%H:%M:%S")
logging.getLogger("ingestion.imerg").setLevel(logging.WARNING)
logging.getLogger("processing.catchment_rainfall").setLevel(logging.WARNING)
logger = logging.getLogger("intensity")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", type=int, default=3,
                        help="accumulation window in hours (default 3)")
    args = parser.parse_args()
    column = f"rain_{args.window}h_mm"

    events = pd.read_parquet(EVENTS)
    catchments = load_catchments(CATCHMENTS)
    logger.info("Ranking %d event(s) by peak %d-hour intensity",
                len(events), args.window)

    overlaps = None
    rows, skipped = [], []

    for _, event in events.iterrows():
        event_id = event["event_id"]
        paths = sorted((GRANULE_ROOT / event_id).glob("*.nc*"))
        if len(paths) < MIN_GRANULES:
            skipped.append({"event_id": event_id, "granules": len(paths)})
            continue

        combined = process_imerg_window(
            paths, rolling_windows_hours=(1, args.window, 6, 24),
            run_type="final", bbox=TERRAIN_AOI.wsen,
        )
        if overlaps is None:
            overlaps = compute_overlaps(build_grid_cells(combined), catchments)

        frame = aggregate_catchment_rainfall(
            combined, overlaps, event_id=event_id, geometry_status="REAL",
        )
        peak = frame.groupby("catchment_id")[column].max()
        rows.append({
            "event_id": event_id,
            "date": event["date"],
            "daily_rank": int(event["rank"]),
            "max_daily_mm": float(event["max_daily_mm"]),
            f"peak_{args.window}h_mm": float(peak.max()),
            "peak_catchment": str(peak.idxmax()),
            f"peak_{args.window}h_AQ_C01_mm": float(peak.get("AQ-C01", float("nan"))),
            "granules": len(paths),
        })
        if len(rows) % 20 == 0:
            logger.info("  %d event(s) processed", len(rows))

    if not rows:
        logger.error("no events had enough granules — is stage 2 complete?")
        return 1

    table = pd.DataFrame(rows)
    peak_col = f"peak_{args.window}h_mm"
    table = table.sort_values(peak_col, ascending=False).reset_index(drop=True)
    table["intensity_rank"] = table.index + 1
    table["rank_change"] = table["daily_rank"] - table["intensity_rank"]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(OUT, index=False)

    logger.info("")
    logger.info("Top 8 by peak %d-hour intensity:", args.window)
    logger.info("  %-14s %8s %8s %7s  %s", "event", f"{args.window}h mm",
                "daily mm", "moved", "catchment")
    for _, r in table.head(8).iterrows():
        logger.info("  %-14s %8.2f %8.2f %+7d  %s", r["event_id"], r[peak_col],
                    r["max_daily_mm"], r["rank_change"], r["peak_catchment"])

    demo = table[table["event_id"] == DEMO_EVENT]
    verdict = None
    if not demo.empty:
        d = demo.iloc[0]
        verdict = {
            "daily_rank": int(d["daily_rank"]),
            "intensity_rank": int(d["intensity_rank"]),
            "moved": int(d["rank_change"]),
            f"peak_{args.window}h_mm": round(float(d[peak_col]), 3),
            "max_daily_mm": round(float(d["max_daily_mm"]), 3),
        }
        logger.info("")
        logger.info("%s — the event with ground truth:", DEMO_EVENT)
        logger.info("  by daily total      rank %d", verdict["daily_rank"])
        logger.info("  by %dh intensity     rank %d  (%+d places)",
                    args.window, verdict["intensity_rank"], verdict["moved"])
        logger.info("  peak %dh             %.2f mm", args.window,
                    verdict[f"peak_{args.window}h_mm"])
        logger.info("")
        if verdict["moved"] > 0:
            logger.info("  Intensity ranks it HIGHER than daily total did. That is "
                        "the expected direction: the paper reports 82%% of its "
                        "rainfall in an 18 h spell.")
        else:
            logger.info("  Intensity does NOT rank it higher. Daily screening is "
                        "not obviously understating this event, and the "
                        "acceptance test in the task file needs rethinking "
                        "rather than the ranking.")

    SUMMARY.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_hours": args.window,
        "events_ranked": int(len(table)),
        "events_skipped_incomplete": len(skipped),
        "skipped": skipped[:30],
        "demo_event": verdict,
        "biggest_climbers": table.nlargest(5, "rank_change")[
            ["event_id", "daily_rank", "intensity_rank", "rank_change"]
        ].to_dict("records"),
        "note": (
            "Ranked on peak trailing accumulation per catchment, from "
            "half-hourly Final Run. Daily screening selected these candidates, "
            "so this re-ranks within that pool — an intense storm on a "
            "low-total day that stage 1 never selected cannot appear here. "
            "That residual limitation belongs in the model card."
        ),
    }, indent=2, default=str) + "\n")

    logger.info("wrote %s (%d event(s), %d skipped)",
                OUT.relative_to(PROJECT_ROOT), len(table), len(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
