#!/usr/bin/env python
"""Near-real-time IMERG Early Run proof.

Resolves the latest available Early Run granule from NASA CMR — wall-clock
"now" is never assumed to equal the latest product time — then retrieves a
small recent window and reports the observed latency.

Early Run output is marked preliminary and unsuitable for training, and is
written to a separate live/ directory so it can never overwrite or mix with
Final Run results.

If Early Run is temporarily unavailable the official metadata result and the
error are recorded, the phase is marked NO-GO, and no data is fabricated.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from ingestion.imerg import (  # noqa: E402
    GRANULE_MINUTES,
    authenticate,
    existing_granules,
    expected_granule_timestamps,
    fetch_imerg_window,
    get_imerg_product,
    process_imerg_window,
)

DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "imerg_early_live_demo.yaml"
RULE = "=" * 78


def resolve_latest_granule(product: dict, lookback_days: int = 5) -> dict:
    """Latest available granule for a product, from CMR metadata only."""
    import requests

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    response = requests.get(
        "https://cmr.earthdata.nasa.gov/search/granules.umm_json",
        params={
            "collection_concept_id": product["collection_id"],
            "temporal": f"{start:%Y-%m-%dT%H:%M:%SZ},{end:%Y-%m-%dT%H:%M:%SZ}",
            "sort_key": "-start_date",
            "page_size": 1,
        },
        timeout=90,
    )
    response.raise_for_status()
    items = response.json().get("items", [])
    if not items:
        raise RuntimeError(
            f"CMR returned no {product['short_name']} granules in the last "
            f"{lookback_days} days."
        )
    umm = items[0]["umm"]
    window = umm["TemporalExtent"]["RangeDateTime"]
    return {
        "granule_name": umm["GranuleUR"],
        "beginning_utc": window["BeginningDateTime"],
        "ending_utc": window["EndingDateTime"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    config = yaml.safe_load(args.config.read_text())
    spatial = config["spatial"]
    live = config["live"]
    bbox = (spatial["west"], spatial["south"], spatial["east"], spatial["north"])
    window_hours = int(live.get("window_hours", 3))
    max_granules = int(live.get("max_granules", 6))
    live_dir = PROJECT_ROOT / live.get("output_dir", "data/processed/live")

    request_time = datetime.now(timezone.utc)
    product = get_imerg_product(live.get("run_type", "early"))

    print(f"\n{RULE}\nIMERG EARLY RUN — NEAR-REAL-TIME PROOF\n{RULE}")
    print(f"  request time utc  : {request_time:%Y-%m-%dT%H:%M:%SZ}")
    print(f"  product           : {product['short_name']} "
          f"({product['collection_id']})")
    print(f"  bbox (W,S,E,N)    : {list(bbox)}")
    print(f"  window            : {window_hours} h, max {max_granules} granules")

    summary: dict = {
        "phase": "imerg_early_near_real_time",
        "request_time_utc": request_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "run_type": product["run_type"],
        "short_name": product["short_name"],
        "collection_id": product["collection_id"],
        "preliminary": True,
        "calibrated_final_product": False,
        "suitable_for_training": False,
        "bbox_west_south_east_north": list(bbox),
        "verdict": "NO-GO",
    }
    live_dir.mkdir(parents=True, exist_ok=True)
    summary_path = live_dir / "imerg_early_latest_summary.json"

    # --- resolve latest availability from official metadata --------------
    try:
        authenticate()
        latest = resolve_latest_granule(product)
    except Exception as exc:  # noqa: BLE001
        summary["metadata_result"] = "unavailable"
        summary["error"] = f"{type(exc).__name__}: {exc}"
        summary["note"] = "No data fabricated. Phase marked NO-GO."
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
        print(f"\n  NO-GO: could not resolve latest Early Run granule.")
        print(f"  {type(exc).__name__}: {str(exc)[:300]}")
        print(f"  recorded in {summary_path}")
        return 1

    latest_start = datetime.fromisoformat(
        latest["beginning_utc"].replace("Z", "+00:00")
    )
    latency_hours = (request_time - latest_start).total_seconds() / 3600.0

    print(f"\n  latest granule    : {latest['granule_name']}")
    print(f"  latest start utc  : {latest_start:%Y-%m-%dT%H:%M:%SZ}")
    print(f"  observed latency  : {latency_hours:.2f} h")

    summary.update({
        "metadata_result": "available",
        "latest_granule_name": latest["granule_name"],
        "latest_product_timestamp_utc": latest_start.strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
        "observed_latency_hours": round(latency_hours, 4),
    })

    # Work backwards from the latest AVAILABLE time, not from wall clock.
    end_time = latest_start
    start_time = end_time - timedelta(
        minutes=GRANULE_MINUTES * (min(max_granules, window_hours * 2) - 1)
    )
    expected = expected_granule_timestamps(start_time, end_time)
    print(f"  retrieval window  : {start_time:%Y-%m-%dT%H:%M:%SZ} .. "
          f"{end_time:%Y-%m-%dT%H:%M:%SZ} ({len(expected)} granules)")

    raw_dir = PROJECT_ROOT / "data" / "raw" / "imerg" / "early_live"
    try:
        paths = fetch_imerg_window(
            start_time, end_time, bbox=bbox, output_dir=raw_dir,
            run_type="early", max_granules=max_granules, chunk_granules=6,
            resume=True, skip_unavailable=True,
        )
    except Exception as exc:  # noqa: BLE001
        summary["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        summary["note"] = (
            "Early Run metadata is available but retrieval failed. No data "
            "fabricated. Phase marked NO-GO."
        )
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
        print(f"\n  NO-GO: retrieval failed — {type(exc).__name__}")
        print(f"  {str(exc)[:300]}")
        print(f"  recorded in {summary_path}")
        return 1

    if not paths:
        summary["error"] = "no granules returned"
        summary["note"] = "No data fabricated. Phase marked NO-GO."
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")
        print("\n  NO-GO: no granules returned.")
        return 1

    # Near-real-time products legitimately have gaps: a granule may not have
    # been produced yet. Report the gap, then process the longest contiguous
    # run so retrieval is still proven. Nothing is interpolated or invented.
    from ingestion.imerg import granule_timestamp_from_name

    available = sorted(
        stamp for stamp in (
            granule_timestamp_from_name(Path(p).name) for p in paths
        ) if stamp is not None
    )
    missing = [
        stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        for stamp in expected if stamp not in set(available)
    ]
    completeness = 100.0 * len(available) / max(len(expected), 1)
    summary["expected_granules"] = len(expected)
    summary["available_granules"] = len(available)
    summary["missing_timestamps"] = missing
    summary["window_completeness_percent"] = round(completeness, 4)

    if missing:
        print(f"\n  MISSING granule(s)  : {len(missing)} -> {missing}")
        print(f"  window completeness : {completeness:.2f} %")
        print("  near-real-time gaps are expected; processing the longest "
              "contiguous run, nothing interpolated")

    step = timedelta(minutes=GRANULE_MINUTES)
    runs, current = [], [available[0]]
    for previous, stamp in zip(available, available[1:]):
        if stamp - previous == step:
            current.append(stamp)
        else:
            runs.append(current)
            current = [stamp]
    runs.append(current)
    longest = max(runs, key=len)
    keep = set(longest)
    usable = [
        p for p in paths
        if granule_timestamp_from_name(Path(p).name) in keep
    ]
    summary["contiguous_run_granules"] = len(usable)
    summary["contiguous_run_start_utc"] = longest[0].strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    summary["contiguous_run_end_utc"] = longest[-1].strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    if missing:
        print(f"  contiguous run      : {len(usable)} granule(s), "
              f"{longest[0]:%H:%M} .. {longest[-1]:%H:%M} UTC")

    dataset = process_imerg_window(
        usable, rolling_windows_hours=(1,) if len(usable) >= 2 else (0.5,),
        run_type="early", bbox=bbox,
    )
    try:
        values = np.asarray(dataset["precipitation"].values, dtype="float64")
        finite = values[np.isfinite(values)]
        lat = np.asarray(dataset["lat"].values, dtype="float64")
        lon = np.asarray(dataset["lon"].values, dtype="float64")
        nonzero = bool(finite.size and (finite > 0).any())

        print(f"\n{RULE}\nRESULT\n{RULE}")
        print(f"  files             : {len(paths)}")
        print(f"  timestamps        : {dataset['time'].size}")
        print(f"  spatial extent    : lat {lat.min():.2f}..{lat.max():.2f}, "
              f"lon {lon.min():.2f}..{lon.max():.2f}")
        print(f"  completeness      : "
              f"{dataset.attrs['data_completeness_percent']:.2f} %")
        print(f"  precipitation     : min {finite.min():.4f} / "
              f"max {finite.max():.4f} / mean {finite.mean():.4f} mm/hr")
        print(f"  non-zero rainfall : {'YES' if nonzero else 'NO'}")
        print(f"  run_type          : {dataset.attrs['imerg_run_type']}")
        print(f"  preliminary       : {dataset.attrs['preliminary']}")
        print(f"  training-safe     : {dataset.attrs['suitable_for_training']}")

        dataset.attrs["preliminary"] = "true"
        dataset.attrs["calibrated_final_product"] = "false"
        dataset.attrs["suitable_for_training"] = "false"
        dataset.attrs["request_time_utc"] = summary["request_time_utc"]
        dataset.attrs["observed_latency_hours"] = latency_hours

        target = live_dir / "imerg_early_latest.nc"
        dataset["time"].encoding.setdefault(
            "units", "seconds since 1980-01-06 00:00:00")
        dataset.to_netcdf(target)

        summary.update({
            "verdict": "GO",
            "retrieval_window_start_utc": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "retrieval_window_end_utc": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "file_count": len(paths),
            "timestamp_count": int(dataset["time"].size),
            "spatial_extent": {
                "lat_min": float(lat.min()), "lat_max": float(lat.max()),
                "lon_min": float(lon.min()), "lon_max": float(lon.max()),
            },
            "data_completeness_percent": float(
                dataset.attrs["data_completeness_percent"]),
            "precipitation_mm_per_hr": {
                "min": float(finite.min()) if finite.size else None,
                "max": float(finite.max()) if finite.size else None,
                "mean": float(finite.mean()) if finite.size else None,
            },
            "non_zero_precipitation_present": nonzero,
            "output_netcdf": str(target),
            "final_run_outputs_touched": False,
        })
    finally:
        dataset.close()

    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\n{RULE}\nOUTPUT\n{RULE}")
    print(f"  netcdf   : {target} ({target.stat().st_size / 1024:.1f} KB)")
    print(f"  summary  : {summary_path}")
    print(f"\n  VERDICT: GO for IMERG Early Run near-real-time retrieval")
    print(f"{RULE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
