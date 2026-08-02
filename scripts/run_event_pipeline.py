#!/usr/bin/env python
"""Run the ReefShield event pipeline from a YAML configuration.

Event-agnostic: the config supplies the event, the box, the time ranges and the
outputs. Modes:

    --dry-run              print the execution plan; download and write nothing
    --offline-process-only reuse local raw files; make no network request
    (default)              fetch what is missing, then process

Nothing sensitive is printed: no credentials, tokens, headers or signed URLs.
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

from config.event_pipeline import (  # noqa: E402
    ConfigError,
    EventPipelineConfig,
    load_event_pipeline_config,
)
from ingestion.era5_land import (  # noqa: E402
    fetch_era5_land_window,
    normalize_era5_land_fluxes,
    read_era5_land,
)
from ingestion.imerg import (  # noqa: E402
    existing_granules,
    expected_granule_timestamps,
    fetch_imerg_window,
    missing_granule_timestamps,
    process_imerg_window,
    wettest_windows,
)
from processing.antecedent_features import (  # noqa: E402
    antecedent_features_to_dataframe,
    extract_antecedent_features,
)

RULE = "=" * 78


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def print_plan(config: EventPipelineConfig) -> dict:
    plan = config.execution_plan()
    print(f"\n{RULE}\nEXECUTION PLAN — {plan['event_id']}\n{RULE}")
    print(f"  description       : {plan['description'].strip()}")
    print(f"  bbox (W,S,E,N)    : {plan['bbox_west_south_east_north']}")
    print(f"  CDS area (N,W,S,E): {plan['cds_area_north_west_south_east']}")

    imerg = plan["sources"].get("imerg")
    if imerg:
        print(f"\n  IMERG [{imerg['run_type']}]  {imerg['short_name']} "
              f"({imerg['collection_id']})")
        print(f"    window          : {imerg['start_utc']} .. {imerg['end_utc']}")
        print(f"    granules        : {imerg['expected_granules']} "
              f"(limit {imerg['max_granules']}, "
              f"{'OK' if imerg['within_limit'] else 'OVER LIMIT'})")
        print(f"    harmony jobs    : ~{imerg['estimated_harmony_jobs']}")
        print(f"    rolling windows : {imerg['rolling_windows_hours']} h")
        print(f"    training-safe   : {imerg['suitable_for_training']}")

    era5 = plan["sources"].get("era5_land")
    if era5:
        print(f"\n  ERA5-Land")
        print(f"    window          : {era5['start_utc']} .. {era5['end_utc']}")
        print(f"    timestamps      : {era5['expected_timestamps']} "
              f"({'OK' if era5['within_limit'] else 'OVER LIMIT'})")
        print(f"    variables       : {era5['variables']}")
        print(f"    semantics mode  : {era5['temporal_semantics_mode']}")
        print(f"    CDS requests    : ~{era5['estimated_cds_requests']} "
              f"({era5['chunk_mode']} chunks)")
        if "antecedent" in era5:
            print(f"    event time      : {era5['antecedent']['event_time_utc']}")

    print(f"\n  paths:")
    for key, value in plan["paths"].items():
        print(f"    {key:<12}: {value}")
    return plan


def run_imerg(config: EventPipelineConfig, offline: bool, manifest: dict) -> None:
    imerg = config.imerg
    raw_dir = config.imerg_raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)

    before = set(existing_granules(raw_dir))
    if offline:
        present = existing_granules(raw_dir)
        paths = [
            present[s] for s in expected_granule_timestamps(
                imerg.start_time, imerg.end_time) if s in present
        ]
        print(f"  offline: reusing {len(paths)} local granule(s)")
    else:
        paths = fetch_imerg_window(
            imerg.start_time, imerg.end_time,
            bbox=config.spatial.imerg_bbox, output_dir=raw_dir,
            run_type=imerg.run_type, max_granules=imerg.max_granules,
            chunk_granules=imerg.chunk_granules, resume=True,
        )
    after = set(existing_granules(raw_dir))
    downloaded = len(after - before)

    expected = len(expected_granule_timestamps(imerg.start_time, imerg.end_time))
    missing = missing_granule_timestamps(
        paths, imerg.start_time, imerg.end_time
    )
    completeness = 100.0 * len(paths) / max(expected, 1)
    print(f"  granules          : {len(paths)}/{expected} "
          f"({completeness:.2f}% complete), {downloaded} downloaded, "
          f"{len(paths) - downloaded} reused")

    if missing and config.validation.fail_on_missing_timestamps:
        raise SystemExit(
            f"  ABORT: {len(missing)} missing granule timestamp(s); first "
            f"{missing[:3]}. Set validation.fail_on_missing_timestamps=false "
            "to accept gaps."
        )
    if completeness < config.validation.minimum_data_completeness:
        raise SystemExit(
            f"  ABORT: completeness {completeness:.2f}% below the configured "
            f"minimum {config.validation.minimum_data_completeness}%."
        )
    if not paths:
        raise SystemExit("  ABORT: no IMERG granules available.")

    dataset = process_imerg_window(
        paths, rolling_windows_hours=imerg.rolling_windows_hours,
        run_type=imerg.run_type, bbox=config.spatial.imerg_bbox,
    )
    peaks = wettest_windows(dataset, imerg.rolling_windows_hours)
    print(f"  wettest windows   :")
    for name, info in peaks.items():
        if info.get("max_mm") is not None:
            print(f"    {name:<12} {info['max_mm']:8.4f} mm  "
                  f"{info['window_start_utc']} -> {info['window_end_utc']}")

    config.processed_dir.mkdir(parents=True, exist_ok=True)
    target = config.processed_dir / f"{config.event_id}_imerg.nc"
    if config.outputs.save_netcdf:
        dataset["time"].encoding.setdefault(
            "units", "seconds since 1980-01-06 00:00:00")
        dataset.to_netcdf(target)
        print(f"  netcdf            : {target} "
              f"({target.stat().st_size / 1024:.1f} KB)")

    manifest["imerg"] = {
        "run_type": imerg.run_type,
        "expected_granules": expected,
        "available_granules": len(paths),
        "downloaded": downloaded,
        "reused": len(paths) - downloaded,
        "missing_timestamps": missing,
        "data_completeness_percent": round(completeness, 4),
        "wettest_windows": peaks,
        "output_netcdf": str(target) if config.outputs.save_netcdf else None,
        "attributes": {k: str(v) for k, v in dataset.attrs.items()},
    }
    dataset.close()


def run_era5(config: EventPipelineConfig, offline: bool, manifest: dict) -> None:
    era5 = config.era5_land
    raw_dir = config.era5_raw_dir
    raw_dir.mkdir(parents=True, exist_ok=True)

    before = {p.name for p in raw_dir.glob("*.nc*")}
    if offline:
        paths = sorted(raw_dir.glob("*.nc*"))
        if not paths:
            fallback = (
                PROJECT_ROOT / "data" / "raw" / "era5_land"
                / "deaccumulation_validation"
            )
            paths = sorted(fallback.glob("*.nc*"))
            print(f"  offline: event dir empty, reusing {len(paths)} file(s) "
                  f"from {fallback.name}")
        else:
            print(f"  offline: reusing {len(paths)} local file(s)")
    else:
        paths = fetch_era5_land_window(
            era5.start_time, era5.end_time, bbox=config.spatial.cds_area,
            variables=era5.variables, output_dir=raw_dir,
            chunk_mode=era5.chunk_mode,
            max_expected_timestamps=era5.max_expected_timestamps,
        )
    after = {Path(p).name for p in raw_dir.glob("*.nc*")}
    downloaded = len(after - before)

    if not paths:
        raise SystemExit("  ABORT: no ERA5-Land files available.")

    parts = [read_era5_land(Path(p)).load() for p in paths]
    combined = xr.concat(
        parts, dim="time", coords="minimal", compat="override"
    ).sortby("time")
    for part in parts:
        part.close()

    normalized = normalize_era5_land_fluxes(
        combined, mode=era5.temporal_semantics_mode,
        negative_tolerance_m=era5.negative_tolerance_m,
    )
    print(f"  files             : {len(paths)} ({downloaded} downloaded)")
    print(f"  timestamps        : {normalized['time'].size}")
    print(f"  semantics         : {normalized.attrs['temporal_semantics_mode']}")

    config.processed_dir.mkdir(parents=True, exist_ok=True)
    target = config.processed_dir / f"{config.event_id}_era5_land.nc"
    if config.outputs.save_netcdf:
        normalized.to_netcdf(target)
        print(f"  netcdf            : {target} "
              f"({target.stat().st_size / 1024:.1f} KB)")

    entry = {
        "expected_timestamps": era5.expected_timestamps,
        "available_timestamps": int(normalized["time"].size),
        "files": len(paths),
        "downloaded": downloaded,
        "reused": len(paths) - downloaded,
        "temporal_semantics_mode": normalized.attrs["temporal_semantics_mode"],
        "temporal_semantics_evidence":
            normalized.attrs["temporal_semantics_evidence"],
        "output_netcdf": str(target) if config.outputs.save_netcdf else None,
    }

    if era5.antecedent is not None:
        features = extract_antecedent_features(
            normalized, era5.antecedent.event_time,
            soil_moisture_offsets_hours=era5.antecedent.soil_moisture_offsets_hours,
            precipitation_windows_hours=era5.antecedent.precipitation_windows_hours,
            runoff_windows_hours=era5.antecedent.runoff_windows_hours,
            state_window_hours=era5.antecedent.state_window_hours,
            minimum_valid_fraction=config.validation.minimum_valid_fraction,
            require_full_windows=config.validation.require_full_antecedent_windows,
        )
        frame = antecedent_features_to_dataframe(features, config.event_id)
        flags, counts = np.unique(
            np.asarray(features["quality_flag"].values).ravel(),
            return_counts=True,
        )
        print(f"  antecedent rows   : {len(frame)}  flags="
              f"{dict(zip(flags.tolist(), counts.tolist()))}")

        parquet = (
            config.processed_dir
            / f"{config.event_id}_antecedent_features.parquet"
        )
        if config.outputs.save_parquet:
            frame.to_parquet(parquet, index=False)
            print(f"  parquet           : {parquet} "
                  f"({parquet.stat().st_size / 1024:.1f} KB)")
        entry["antecedent"] = {
            "event_time_utc": features.attrs["event_time_utc"],
            "feature_count": int(len(features.data_vars)),
            "rows": int(len(frame)),
            "quality_flag_counts": {
                str(k): int(v)
                for k, v in zip(flags.tolist(), counts.tolist())
            },
            "output_parquet": (
                str(parquet) if config.outputs.save_parquet else None
            ),
        }
        features.close()

    manifest["era5_land"] = entry
    normalized.close()
    combined.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline-process-only", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    try:
        config = load_event_pipeline_config(args.config)
    except ConfigError as exc:
        print(f"\nCONFIGURATION ERROR\n{exc}\n")
        return 2

    started = now_utc()
    plan = print_plan(config)

    if args.dry_run:
        print(f"\n{RULE}\n  DRY RUN — nothing downloaded, nothing written.\n"
              f"{RULE}\n")
        return 0

    manifest: dict = {
        "event_id": config.event_id,
        "config_file": str(args.config),
        "mode": "offline-process-only" if args.offline_process_only else "full",
        "started_utc": started,
        "plan": plan,
        "reproducibility": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "xarray": xr.__version__,
            "config_sha_note": "config content is the reproducibility key",
        },
    }

    if config.imerg is not None and config.imerg.enabled:
        print(f"\n{RULE}\nIMERG\n{RULE}")
        run_imerg(config, args.offline_process_only, manifest)

    if config.era5_land is not None and config.era5_land.enabled:
        print(f"\n{RULE}\nERA5-LAND\n{RULE}")
        run_era5(config, args.offline_process_only, manifest)

    manifest["finished_utc"] = now_utc()

    config.processed_dir.mkdir(parents=True, exist_ok=True)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    summary_path = config.processed_dir / f"{config.event_id}_summary.json"
    manifest_path = config.outputs_dir / f"{config.event_id}_manifest.json"
    if config.outputs.save_json:
        summary_path.write_text(json.dumps(manifest, indent=2, default=str) + "\n")
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str) + "\n")

    print(f"\n{RULE}\nOUTPUT\n{RULE}")
    print(f"  summary  : {summary_path}")
    print(f"  manifest : {manifest_path}")
    print(f"{RULE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
