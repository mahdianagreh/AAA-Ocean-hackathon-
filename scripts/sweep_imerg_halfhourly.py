#!/usr/bin/env python3
"""Stage 2: half-hourly IMERG for the candidate days stage 1 selected.

Stage 1 answers *which days were wet*. It cannot answer *how hard it rained
in any three-hour stretch*, and that is the question that matters: 40 mm
spread over a day does nothing to a wadi, and the same 40 mm in three hours
floods it. Daily totals cannot tell those apart.

So stage 2 pays for 30-minute resolution — but only on the ~100 days worth
the request, rather than the ~10,300 days in the record.

    stage 1   10,321 daily granules      the whole record, screened
    stage 2   ~100 events x ~144         only where intensity matters
              -------------------------------------------------------
              ~3 % of a naive half-hourly sweep of the same period

Window per event
----------------
Each event gets the day before, the day itself, and the day after. The
preceding day is not padding: a trailing 24-hour accumulation ending during
the event needs it, and rainfall that starts late on day D-1 is the same
storm. For AQ-2016-10-28 the literature is explicit — rainfall ran ~66 hours
and the flood reached the sea ~50 hours after it began.

Usage
-----
    python scripts/sweep_imerg_halfhourly.py --dry-run
    python scripts/sweep_imerg_halfhourly.py --max-events 20
    python scripts/sweep_imerg_halfhourly.py --event AQ-2016-10-28

Safe to interrupt: granules already on disk are skipped.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

import pandas as pd  # noqa: E402

from config.spatial import TERRAIN_AOI  # noqa: E402
from ingestion.imerg import (  # noqa: E402
    existing_granules,
    expected_granule_timestamps,
    fetch_imerg_window,
    get_imerg_product,
)

RUN_TYPE = "final"  # half-hourly Final Run — calibrated, training-safe
EVENTS = PROJECT_ROOT / "data" / "processed" / "events" / "events.parquet"
OUTPUT_ROOT = PROJECT_ROOT / "data" / "raw" / "imerg" / "events"
MANIFEST = PROJECT_ROOT / "data" / "processed" / "events" / "halfhourly_sweep_manifest.json"

#: Days of context either side of the candidate day. See "Window per event".
PAD_DAYS = 1

#: Below this share of a window's granules, the event is treated as failed
#: rather than recorded as a partial result — the lesson from Harmony's
#: auto-pause, which returned 1 granule of 365 and called it success.
MIN_EVENT_COMPLETENESS = 0.90

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("stage2")


def event_window(day: pd.Timestamp, pad_days: int) -> tuple[str, str]:
    """Half-hourly window covering the event day plus context either side."""
    start = (day - timedelta(days=pad_days)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end = (day + timedelta(days=pad_days)).replace(hour=23, minute=30, second=0)
    return (
        start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def assert_existing_granules_match_extent(output_dir: Path, bbox) -> None:
    """Refuse to resume into a directory fetched against a different extent.

    Resume matches granules by FILENAME. A granule downloaded against the
    retired bounding box has exactly the same name as the correct one, so a
    naive resume skips it and silently mixes two extents in one dataset —
    every timestamp present, every value real, and the grid quietly different
    between them.

    This is not hypothetical: every existing granule for AQ-2016-10-28 was
    fetched against the old box and covers ~9 % of the terrain AOI.
    """
    if not output_dir.is_dir():
        return
    present = sorted(output_dir.glob("*.nc*"))
    if not present:
        return

    try:
        import xarray as xr

        with xr.open_dataset(present[0], group="Grid", decode_times=False) as ds:
            lat, lon = ds["lat"].values, ds["lon"].values
    except Exception:  # noqa: BLE001 - unreadable sample is not proof of mismatch
        logger.warning("could not read %s to verify its extent", present[0].name)
        return

    west, south, east, north = bbox
    tol = 0.2  # one grid cell plus slack
    matches = (
        abs(float(lon.min()) - west) < tol
        and abs(float(lon.max()) - east) < tol
        and abs(float(lat.min()) - south) < tol
        and abs(float(lat.max()) - north) < tol
    )
    if not matches:
        raise SystemExit(
            f"\n{output_dir} already holds {len(present)} granule(s) covering\n"
            f"  lon {float(lon.min()):.2f}..{float(lon.max()):.2f}  "
            f"lat {float(lat.min()):.2f}..{float(lat.max()):.2f}\n"
            f"but this run requests\n"
            f"  lon {west:.2f}..{east:.2f}  lat {south:.2f}..{north:.2f}\n\n"
            "Resume matches on filename, so those files would be SKIPPED and the\n"
            "dataset would silently mix two extents. Move or delete that\n"
            "directory first — the granules are reproducible.\n"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, default=EVENTS)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--pad-days", type=int, default=PAD_DAYS)
    parser.add_argument("--max-events", type=int, default=0,
                        help="only the top N candidates (0 = all)")
    parser.add_argument("--event", type=str, default="",
                        help="a single event_id, e.g. AQ-2016-10-28")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--chunk-granules", type=int, default=200)
    parser.add_argument(
        "--literature", action="store_true",
        help=("fetch the documented events from docs/event_dates.md instead of "
              "the screened catalogue — they need no screening to be known"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.literature:
        # The literature events do not need the catalogue: their dates are
        # documented, and AQ-2016-10-28 is the event the whole demo is built
        # on. Fetching it early is what lets the ordering anomaly in
        # docs/event_dates.md be resolved over the CORRECT extent — the
        # existing granules for it were pulled against the retired box and
        # cover ~9 % of the terrain AOI.
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "build_event_catalogue",
            PROJECT_ROOT / "scripts" / "build_event_catalogue.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        found = module.literature_dates()
        if not found:
            logger.error("no resolved literature dates in docs/event_dates.md")
            return 1
        catalogue = pd.DataFrame(
            [
                {
                    "event_id": item["event_id"],
                    "date": item["date"],
                    "rank": index + 1,
                    "max_daily_mm": float("nan"),
                    "is_exhaustive": True,  # not screened; taken from the literature
                    "selection_reason": f"literature ({item['source']})",
                }
                for index, item in enumerate(found)
            ]
        )
        logger.info("literature events: %s", ", ".join(catalogue["event_id"]))
    elif not args.events.exists():
        logger.error("%s missing — run scripts/build_event_catalogue.py first",
                     args.events)
        return 1
    else:
        catalogue = pd.read_parquet(args.events)
    if not bool(catalogue.get("is_exhaustive", pd.Series([False])).iloc[0]):
        logger.warning(
            "the catalogue is NOT exhaustive — it was built from a partial "
            "sweep, so these are the best candidates so far, not the best "
            "candidates in the record"
        )

    if args.event:
        catalogue = catalogue[catalogue["event_id"] == args.event]
        if catalogue.empty:
            logger.error("%s is not in the catalogue", args.event)
            return 1
    catalogue = catalogue.sort_values("rank")
    if args.max_events:
        catalogue = catalogue.head(args.max_events)

    product = get_imerg_product(RUN_TYPE)
    per_event = len(
        expected_granule_timestamps(*event_window(pd.Timestamp("2016-10-28", tz="UTC"),
                                                  args.pad_days))
    )

    logger.info("Stage 2 — half-hourly intensity for selected events")
    logger.info("  product     %s v%s (%s)", product["short_name"],
                product["version"], product["collection_id"])
    logger.info("  units       %s", product["rate_units"])
    logger.info("  events      %d", len(catalogue))
    logger.info("  window      +/- %d day(s) -> %d granules each",
                args.pad_days, per_event)
    logger.info("  total       ~%d granules across %d Harmony job(s)",
                per_event * len(catalogue), len(catalogue))

    if args.dry_run:
        for _, row in catalogue.head(10).iterrows():
            start, end = event_window(pd.Timestamp(row["date"]), args.pad_days)
            logger.info("    %-14s %s .. %s  (%.1f mm, rank %d)",
                        row["event_id"], start[:10], end[:10],
                        row["max_daily_mm"], int(row["rank"]))
        logger.info("DRY RUN: nothing fetched")
        return 0

    started = time.time()
    lock = threading.Lock()
    results: list[dict] = []

    def fetch_event(row) -> dict:
        event_id = row["event_id"]
        start, end = event_window(pd.Timestamp(row["date"]), args.pad_days)
        out_dir = args.output_root / event_id
        expected = len(expected_granule_timestamps(start, end))
        assert_existing_granules_match_extent(out_dir, TERRAIN_AOI.wsen)
        t0 = time.time()
        try:
            paths = fetch_imerg_window(
                start_time=start, end_time=end,
                bbox=TERRAIN_AOI.wsen, output_dir=out_dir,
                run_type=RUN_TYPE, max_granules=expected + 10,
                chunk_granules=args.chunk_granules, resume=True,
                skip_unavailable=True,
            )
            complete = len(paths) / max(expected, 1)
            return {
                "event_id": event_id, "window": [start, end],
                "expected": expected, "present": len(paths),
                "completeness": round(complete, 4),
                "seconds": round(time.time() - t0, 1),
                "status": "ok" if complete >= MIN_EVENT_COMPLETENESS else "incomplete",
            }
        except Exception as exc:  # noqa: BLE001 - one event must not end the run
            return {
                "event_id": event_id, "window": [start, end],
                "expected": expected, "present": 0, "completeness": 0.0,
                "seconds": round(time.time() - t0, 1),
                "status": f"failed: {type(exc).__name__}: {exc}",
            }

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(fetch_event, row) for _, row in catalogue.iterrows()]
        for future in as_completed(futures):
            record = future.result()
            with lock:
                results.append(record)
                level = logger.info if record["status"] == "ok" else logger.error
                level("%-14s %3d/%-3d granules (%.0f%%) %5.0fs  %s",
                      record["event_id"], record["present"], record["expected"],
                      100 * record["completeness"], record["seconds"],
                      record["status"])

    ok = [r for r in results if r["status"] == "ok"]
    manifest = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": "2 of 2 — half-hourly intensity",
        "product": {
            "short_name": product["short_name"],
            "collection_id": product["collection_id"],
            "rate_units": product["rate_units"],
        },
        "bbox_wsen": list(TERRAIN_AOI.wsen),
        "pad_days": args.pad_days,
        "events_requested": len(results),
        "events_complete": len(ok),
        "granules_on_disk": sum(r["present"] for r in results),
        "elapsed_minutes": round((time.time() - started) / 60, 1),
        "events": sorted(results, key=lambda r: r["event_id"]),
        "note": (
            "Incomplete events are recorded as incomplete and not silently "
            "accepted. Missing granules are reported, never interpolated."
        ),
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

    logger.info("STAGE 2 DONE: %d/%d event(s) complete, %d granule(s), %.1f min",
                len(ok), len(results), manifest["granules_on_disk"],
                manifest["elapsed_minutes"])
    logger.info("manifest -> %s", MANIFEST.relative_to(PROJECT_ROOT))
    return 0 if len(ok) == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
