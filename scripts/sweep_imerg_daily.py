#!/usr/bin/env python3
"""Stage 1 of the two-stage sweep: daily IMERG Final over the terrain AOI.

Why two stages
--------------
The runoff classifier needs examples. We have exactly **one** event with
ground truth (AQ-2016-10-28, mooring-verified), and one example teaches a
model nothing. Twenty-eight years of IMERG contains every storm that has hit
these catchments since 1998 — that is the training set.

But half-hourly IMERG is 48 granules a day, so 28 years is ~490,000 Harmony
requests. Not possible inside this project's window.

The same product is published daily — one granule per day, ~10,200 for the
whole record. So:

    Stage 1 (this script)  daily, 1998 -> present      10,321 granules
    Stage 2                half-hourly, 3-day window       144 per event
                           -------------------------------------------
                           top 50 events  -> ~17,500 total, about 3.6 %
                           top 100 events -> ~24,700 total, about 5 %

    (Measured, not estimated: the stage-2 dry run reports 144 granules per
    event for a +/-1 day window. An earlier note in this file said ~6,000 for
    stage 2, which assumed 50 events at a smaller window — corrected here
    rather than left to mislead whoever plans the download budget.)

Stage 1 finds *which days were wet*. Stage 2 recovers the sub-daily intensity
that actually drives a flash flood, only for days worth the request.

The caveat, stated here and belonging in the model card
-------------------------------------------------------
Screening on daily totals can under-rank a short, violent burst that lands on
a day with a modest total — and intensity, not daily depth, is what floods a
wadi. Two mitigations: keep a generous top-N rather than a tight one, and
force-include every date named in the literature regardless of rank. Neither
makes the limitation go away; both bound it.

Usage
-----
    python scripts/sweep_imerg_daily.py --start-year 2016 --end-year 2016
    python scripts/sweep_imerg_daily.py                      # full record
    python scripts/sweep_imerg_daily.py --dry-run            # plan only

Safe to interrupt and re-run: granules already on disk are skipped.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from config.spatial import TERRAIN_AOI  # noqa: E402
from ingestion.imerg import (  # noqa: E402
    existing_granules,
    expected_granule_timestamps,
    fetch_imerg_window,
    get_imerg_product,
)

RUN_TYPE = "daily_final"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "imerg" / "daily_final"
MANIFEST = PROJECT_ROOT / "data" / "processed" / "events" / "daily_sweep_manifest.json"

#: IMERG V07 daily Final begins here — two years earlier than the half-hourly
#: record, which starts 2000-06. Confirmed from the CMR collection metadata.
RECORD_START_YEAR = 1998

#: Final Run lags real time by roughly 3.5 months, so the current year is
#: always partial. Requesting past the end of the record is not an error —
#: Harmony simply returns nothing — but it wastes a job per gap.
FINAL_RUN_LAG_DAYS = 120

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sweep")



#: Exit code meaning "I stalled; restart me". The supervisor loop in
#: scripts/run_daily_sweep.sh watches for this.
EXIT_STALLED = 75

#: Below this share of a year's days, treat the year as failed rather than
#: recording a partial result. See the note in sweep_year().
MIN_YEAR_COMPLETENESS = 0.90

#: A Harmony job legitimately sits in the queue for ~25 minutes before it
#: delivers anything, so the stall threshold has to sit well above that.
DEFAULT_STALL_MINUTES = 45


def start_stall_watchdog(output_dir: Path, stall_minutes: float) -> threading.Event:
    """Exit the process if no new granule lands for `stall_minutes`.

    A laptop going to sleep kills the connection mid-download. harmony-py then
    blocks on a socket that is never coming back, and the process stays alive
    doing nothing — which is exactly what happened on 2 Aug: the sweep sat idle
    for 2 h 40 min while looking perfectly healthy.

    Dying loudly is better than hanging quietly. Everything already fetched is
    on disk, and the restart resumes from there.
    """
    stop = threading.Event()
    limit = stall_minutes * 60

    def watch() -> None:
        last_count, last_change = -1, time.time()
        while not stop.is_set():
            count = len(list(output_dir.glob("*.nc*")))
            if count != last_count:
                last_count, last_change = count, time.time()
            elif time.time() - last_change > limit:
                logger.error(
                    "STALLED: no new granule in %.0f min (%d on disk). Exiting "
                    "so the supervisor can restart with resume.",
                    stall_minutes, count,
                )
                os._exit(EXIT_STALLED)
            stop.wait(30)

    threading.Thread(target=watch, daemon=True, name="stall-watchdog").start()
    return stop


def year_bounds(year: int, latest: datetime) -> tuple[str, str]:
    """First and last daily granule start in `year`, clipped to the record."""
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year, 12, 31, tzinfo=timezone.utc)
    if end > latest:
        end = latest
    return (
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def write_manifest(output_dir: Path, first_year: int, last_year: int) -> dict:
    """Record exactly which days are on disk, and which are not."""
    latest = datetime.now(timezone.utc).timestamp() - FINAL_RUN_LAG_DAYS * 86400
    latest_dt = datetime.fromtimestamp(latest, tz=timezone.utc)

    wanted = expected_granule_timestamps(
        datetime(first_year, 1, 1, tzinfo=timezone.utc),
        min(datetime(last_year, 12, 31, tzinfo=timezone.utc), latest_dt),
        granule_minutes=1440,
    )
    present = existing_granules(output_dir)
    missing = [s for s in wanted if s not in present]

    product = get_imerg_product(RUN_TYPE)
    manifest = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": "1 of 2 — daily screening",
        "product": {
            "short_name": product["short_name"],
            "collection_id": product["collection_id"],
            "variable": product["variable"],
            "rate_units": product["rate_units"],
            "granule_minutes": product["granule_minutes"],
        },
        "bbox_wsen": list(TERRAIN_AOI.wsen),
        "years": [first_year, last_year],
        "days_expected": len(wanted),
        "days_present": len(wanted) - len(missing),
        "days_missing": len(missing),
        "completeness_percent": round(
            100.0 * (len(wanted) - len(missing)) / max(len(wanted), 1), 2
        ),
        "missing_days": [s.strftime("%Y-%m-%d") for s in missing[:500]],
        "missing_truncated": len(missing) > 500,
        "note": (
            "Screening resolution only. Sub-daily intensity requires the "
            "half-hourly product — see stage 2. Missing days are reported, "
            "never interpolated."
        ),
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> int:
    now_year = datetime.now(timezone.utc).year
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=RECORD_START_YEAR)
    parser.add_argument("--end-year", type=int, default=now_year)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--chunk-granules", type=int, default=400,
        help=("days per Harmony job (default 400 — a whole year in one job). "
              "Harmony's per-job overhead is ~25 min whether the job covers "
              "60 days or 365, so small chunks multiply the wait."),
    )
    parser.add_argument(
        "--workers", type=int, default=6,
        help=("concurrent Harmony jobs (default 6). Years are independent, so "
              "there is no reason to wait for one before starting the next."),
    )
    parser.add_argument(
        "--stall-minutes", type=float, default=DEFAULT_STALL_MINUTES,
        help=("exit for restart if no granule arrives in this long "
              f"(default {DEFAULT_STALL_MINUTES})"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    latest = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() - FINAL_RUN_LAG_DAYS * 86400,
        tz=timezone.utc,
    )
    product = get_imerg_product(RUN_TYPE)

    logger.info("Stage 1 — daily IMERG Final screening sweep")
    logger.info("  product     %s v%s (%s)",
                product["short_name"], product["version"], product["collection_id"])
    logger.info("  variable    %s   units %s",
                product["variable"], product["rate_units"])
    logger.info("  bbox        %s", TERRAIN_AOI)
    logger.info("  years       %d..%d", args.start_year, args.end_year)
    logger.info("  Final lag   ~%d days, so the record ends near %s",
                FINAL_RUN_LAG_DAYS, latest.date())
    logger.info("  output      %s", args.output_dir.relative_to(PROJECT_ROOT))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    already = len(existing_granules(args.output_dir))
    logger.info("  on disk     %d granule(s) already — these are skipped", already)

    if args.dry_run:
        total = sum(
            len(expected_granule_timestamps(*year_bounds(y, latest),
                                            granule_minutes=1440))
            for y in range(args.start_year, args.end_year + 1)
        )
        n_years = len([y for y in range(args.start_year, args.end_year + 1)
                       if datetime(y, 1, 1, tzinfo=timezone.utc) <= latest])
        logger.info(
            "DRY RUN: %d day(s) across %d Harmony job(s) (one per year), "
            "%d at a time; nothing fetched", total, n_years, args.workers,
        )
        return 0

    years = [
        y for y in range(args.start_year, args.end_year + 1)
        if datetime(y, 1, 1, tzinfo=timezone.utc) <= latest
    ]
    logger.info("  workers     %d concurrent Harmony job(s)", args.workers)
    logger.info(
        "  plan        %d year(s), one job each — measured overhead is ~25 min "
        "per job regardless of size, so whole years beat small chunks",
        len(years),
    )

    watchdog = start_stall_watchdog(args.output_dir, args.stall_minutes)

    started = time.time()
    done_count = 0
    lock = threading.Lock()

    def sweep_year(year: int) -> tuple[int, int, float, str | None]:
        """Fetch one year. Returns (year, days_on_disk, seconds, error)."""
        start, end = year_bounds(year, latest)
        t0 = time.time()
        try:
            paths = fetch_imerg_window(
                start_time=start,
                end_time=end,
                bbox=TERRAIN_AOI.wsen,
                output_dir=args.output_dir,
                run_type=RUN_TYPE,
                max_granules=400,
                chunk_granules=args.chunk_granules,
                resume=True,
                # A day genuinely absent from the archive is a gap to record,
                # not a reason to abandon 28 years of sweep.
                skip_unavailable=True,
            )
            expected = len(
                expected_granule_timestamps(start, end, granule_minutes=1440)
            )
            # A year that comes back mostly empty is a failure, not a result.
            # Harmony's auto-pause returned ONE granule of 365 and reported
            # success; the sweep logged "1 day(s) on disk" and moved on. Days
            # genuinely absent from the archive are rare, so anything under
            # this share means something went wrong upstream.
            if len(paths) < MIN_YEAR_COMPLETENESS * expected:
                return year, len(paths), time.time() - t0, (
                    f"only {len(paths)}/{expected} day(s) returned "
                    f"({100.0 * len(paths) / max(expected, 1):.0f}%) — "
                    "treating as failed rather than accepting a partial year"
                )
            return year, len(paths), time.time() - t0, None
        except Exception as exc:  # noqa: BLE001 - one bad year must not end the run
            return year, 0, time.time() - t0, f"{type(exc).__name__}: {exc}"

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(sweep_year, y): y for y in years}
        for future in as_completed(futures):
            year, n_days, seconds, error = future.result()
            with lock:
                done_count += 1
                if error:
                    logger.error("%d FAILED after %.0fs: %s — continuing",
                                 year, seconds, error)
                else:
                    logger.info(
                        "%d done: %d day(s) on disk, %.0fs  "
                        "[%d/%d years, %.1f min elapsed]",
                        year, n_days, seconds, done_count, len(years),
                        (time.time() - started) / 60,
                    )

    watchdog.set()
    manifest = write_manifest(args.output_dir, args.start_year, args.end_year)
    logger.info(
        "SWEEP COMPLETE: %d/%d days present (%.2f%%), %d missing, %.1f min total",
        manifest["days_present"], manifest["days_expected"],
        manifest["completeness_percent"], manifest["days_missing"],
        (time.time() - started) / 60,
    )
    logger.info("manifest -> %s", MANIFEST.relative_to(PROJECT_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
