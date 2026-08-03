#!/usr/bin/env python3
"""ERA5-Land for the candidate events: antecedent state, and the labels.

Two jobs, from one download
---------------------------
1. **Antecedent features.** Soil moisture at T-24 h and T-72 h, prior 24/72 h
   and 7-day rainfall, event-time wind and temperature. Dry, crusted desert
   soil sheds water rather than absorbing it, so antecedent state is the main
   non-rainfall predictor of whether a given storm floods.

2. **The labels.** Surface runoff (`sro`) is what turns 100 candidate days
   into a trainable target.

Why only the event months, and why that is the better design
------------------------------------------------------------
This pulls the 84 months containing a candidate event plus its 7-day
lookback, not all 336 months of the record. That is 75 % cheaper, but cost is
not the reason.

The candidates are already the top ~1 % of days by rainfall. Label them
against a percentile of the WHOLE record and almost every one clears it — the
target comes out ~95 % positive and the model learns nothing from it. Labelled
*within* the candidate set, the target answers the question that actually
matters: **among storms, which ones generated runoff, and which soaked into
the wadi bed?**

That is the transmission-loss question — 13 % to 98 % of a desert flood never
reaches the sea — and it is the discriminating signal, not a nuisance.

Recorded here because it is a deviation from the plan in
tasks/phase2/01-karam.md, which specified a whole-record percentile.

The rule that keeps it honest
-----------------------------
`sro` and `ssro` are LABELS. They must never appear as features. Using a
variable as both builds a tautology that scores 0.99 and predicts nothing.

Two things NOT to try, both measured on 2 Aug 2026
--------------------------------------------------
**More workers.** CDS limits concurrent jobs per user and *rejects* the
surplus rather than queueing it. Ten workers produced twenty consecutive
`400 Bad Request` failures and poisoned the queue for several minutes. Four
worked; two is used here for margin.

**Whole-year requests.** Twelve monthly requests queue twelve times, so one
yearly request looked like an obvious 12x saving. CDS refuses it outright:
`403 Forbidden — cost limits exceeded, your request is too large`. Monthly is
the largest granularity this variable count is allowed.

The download is slow because CDS queues each job for 8-16 minutes regardless
of size, and there is no lever on our side that changes that. It is slow and
correct; both attempts to make it fast made it broken.

Usage
-----
    python scripts/sweep_era5_land_events.py --dry-run
    python scripts/sweep_era5_land_events.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

import pandas as pd  # noqa: E402

from config.spatial import TERRAIN_AOI  # noqa: E402
from ingestion.era5_land import fetch_era5_land_window  # noqa: E402

EVENTS = PROJECT_ROOT / "data" / "processed" / "events" / "events.parquet"
OUTPUT = PROJECT_ROOT / "data" / "raw" / "era5_land" / "events"
MANIFEST = PROJECT_ROOT / "data" / "processed" / "events" / "era5_sweep_manifest.json"

#: Antecedent features look back 7 days; take 9 for margin so a window that
#: opens near a month boundary is still fully covered.
LOOKBACK_DAYS = 9

#: Features (state) plus labels (runoff). Kept in one list because they come
#: from one request — but they are NOT interchangeable downstream.
FEATURE_VARIABLES = (
    "soil_moisture",
    "total_precipitation",
    "u10",
    "v10",
    "temperature_2m",
)
LABEL_VARIABLES = ("surface_runoff", "subsurface_runoff")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("era5")


def months_needed(events: pd.DataFrame, lookback_days: int) -> list[tuple[int, int]]:
    """Distinct (year, month) covering every event window and its lookback."""
    days = pd.to_datetime(events["date"], utc=True)
    months: set[tuple[int, int]] = set()
    for day in days:
        for offset in range(-lookback_days, 2):
            moment = day + pd.Timedelta(days=offset)
            months.add((moment.year, moment.month))
    return sorted(months)


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1, 0, tzinfo=timezone.utc)
    if month == 12:
        nxt = datetime(year + 1, 1, 1, 0, tzinfo=timezone.utc)
    else:
        nxt = datetime(year, month + 1, 1, 0, tzinfo=timezone.utc)
    return start, nxt - pd.Timedelta(hours=1).to_pytimedelta()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, default=EVENTS)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--lookback-days", type=int, default=LOOKBACK_DAYS)
    parser.add_argument(
        "--workers", type=int, default=2,
        help=("concurrent CDS jobs (default 2). CDS REJECTS surplus concurrent "
              "jobs rather than queueing them — 10 workers had every request "
              "rejected on 2 Aug 2026. Do not raise this."),
    )
    parser.add_argument("--max-months", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.events.exists():
        logger.error("%s missing — run scripts/build_event_catalogue.py first",
                     args.events)
        return 1

    events = pd.read_parquet(args.events)
    months = months_needed(events, args.lookback_days)
    if args.max_months:
        months = months[: args.max_months]

    variables = list(FEATURE_VARIABLES) + list(LABEL_VARIABLES)

    logger.info("ERA5-Land for candidate events")
    logger.info("  events      %d", len(events))
    logger.info("  months      %d (of 336 in the record — event windows only)",
                len(months))
    logger.info("  variables   %d: %s", len(variables), ", ".join(variables))
    logger.info("  labels      %s  (never used as features)",
                ", ".join(LABEL_VARIABLES))
    logger.info("  extent      %s", TERRAIN_AOI)
    logger.info("  output      %s", args.output_dir.relative_to(PROJECT_ROOT))

    if args.dry_run:
        for year, month in months[:8]:
            start, end = month_bounds(year, month)
            logger.info("    %04d-%02d  %s .. %s", year, month,
                        start.date(), end.date())
        logger.info("DRY RUN: %d CDS request(s); nothing fetched", len(months))
        return 0

    args.output_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    lock = threading.Lock()
    results: list[dict] = []

    def fetch_month(year: int, month: int) -> dict:
        start, end = month_bounds(year, month)
        t0 = time.time()
        try:
            paths = fetch_era5_land_window(
                start_time=start, end_time=end,
                # CDS wants [North, West, South, East]. The parameter is
                # called `bbox`, which reads like W,S,E,N — passing that
                # ordering is caught by era5_land's own validator, but ask the
                # contract for the right ordering rather than relying on being
                # caught.
                bbox=TERRAIN_AOI.cds_area, variables=variables,
                output_dir=args.output_dir / f"{year:04d}",
                chunk_mode="monthly", overwrite=False,
            )
            return {"month": f"{year:04d}-{month:02d}", "files": len(paths),
                    "seconds": round(time.time() - t0, 1), "status": "ok"}
        except Exception as exc:  # noqa: BLE001 - one month must not end the run
            return {"month": f"{year:04d}-{month:02d}", "files": 0,
                    "seconds": round(time.time() - t0, 1),
                    "status": f"failed: {type(exc).__name__}: {exc}"}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch_month, y, m) for y, m in months]
        for future in as_completed(futures):
            record = future.result()
            with lock:
                results.append(record)
                level = logger.info if record["status"] == "ok" else logger.error
                level("  %s  %d file(s) %6.0fs  %s  [%d/%d]",
                      record["month"], record["files"], record["seconds"],
                      record["status"], len(results), len(months))

    ok = [r for r in results if r["status"] == "ok"]
    manifest = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": "antecedent features and runoff labels for the candidate events",
        "bbox_wsen": list(TERRAIN_AOI.wsen),
        "lookback_days": args.lookback_days,
        "feature_variables": list(FEATURE_VARIABLES),
        "label_variables": list(LABEL_VARIABLES),
        "months_requested": len(results),
        "months_complete": len(ok),
        "elapsed_minutes": round((time.time() - started) / 60, 1),
        "months": sorted(results, key=lambda r: r["month"]),
        "scope_note": (
            "Event months only, not the whole record. The candidates are "
            "already the top ~1 % of days by rainfall, so labelling them "
            "against a whole-record percentile would make the target ~95 % "
            "positive and uninformative. Labelled within the candidate set, "
            "the target separates storms that generated runoff from storms "
            "that soaked into the wadi bed — the transmission-loss question, "
            "which is the discriminating signal."
        ),
        "label_rule": (
            "surface_runoff and subsurface_runoff are LABELS ONLY. Using them "
            "as features builds a tautology that scores near-perfectly and "
            "predicts nothing."
        ),
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

    logger.info("ERA5 SWEEP DONE: %d/%d month(s), %.1f min",
                len(ok), len(results), manifest["elapsed_minutes"])
    logger.info("manifest -> %s", MANIFEST.relative_to(PROJECT_ROOT))
    return 0 if len(ok) == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
