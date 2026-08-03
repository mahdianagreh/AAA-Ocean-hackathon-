#!/usr/bin/env python3
"""Antecedent state and runoff labels, per event and catchment.

Turns the ERA5-Land monthly files into the two things the runoff model still
needs:

**Features — the catchment's state before the rain.** Soil moisture at T-24 h
and T-72 h, prior 24/72 h and 7-day rainfall, event-time wind and temperature.
This is the main non-rainfall predictor: dry, crusted desert soil sheds water
rather than absorbing it, so identical rainfall floods one week and does
nothing the next.

**Labels — what the rain actually did.** ERA5-Land surface runoff generated in
the 24 h from the event, area-weighted over the catchment.

The rule
--------
`sro` / `ssro` are the LABEL. They never become features. The output keeps
them in clearly-named `label_*` columns so a careless `df.drop(columns=[...])`
cannot leave them in the feature set by accident.

Usage
-----
    python scripts/extract_event_antecedents.py
    python scripts/extract_event_antecedents.py --only-available   # partial run
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

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402

from ingestion.era5_land import normalize_era5_land_fluxes, read_era5_land  # noqa: E402
from processing.catchment_rainfall import (  # noqa: E402
    compute_overlaps,
    load_catchments,
)

EVENTS = PROJECT_ROOT / "data" / "processed" / "events" / "events.parquet"
ERA5_DIR = PROJECT_ROOT / "data" / "raw" / "era5_land" / "events"
CATCHMENTS = PROJECT_ROOT / "data" / "processed" / "vectors" / "catchments.gpkg"
OUT = (PROJECT_ROOT / "data" / "processed" / "features"
       / "event_antecedents.parquet")
STATUS = OUT.with_suffix(".summary.json")

#: Lags and windows, in hours.
SOIL_LAGS = (24, 72)
RAIN_WINDOWS = (24, 72, 168)
#: Runoff is summed forward from the event start — the response, not the state.
LABEL_WINDOW_HOURS = 24

#: ERA5-Land arrives GRIB-packed, so cumulative fields carry quantisation
#: noise: measured negative increments of exactly -7.45e-9 and -1.49e-8 m,
#: which are packing steps rather than real decreases. The module default of
#: 1e-10 is calibrated for float64 noise and is too tight for real CDS data —
#: docs/era5_land_accumulation_semantics.md §7 says so explicitly and
#: configs/october_2016_demo.yaml already uses this value. Still far below any
#: meteorologically meaningful amount, so a genuine decrease would still raise.
NEGATIVE_TOLERANCE_M = 1.0e-7

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-7s %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger("antecedent")


def era5_for(day: pd.Timestamp) -> list[Path]:
    """Monthly ERA5 files covering the event and its 7-day lookback."""
    wanted = set()
    for offset in range(-9, 2):
        moment = day + pd.Timedelta(days=offset)
        wanted.add((moment.year, moment.month))
    found = []
    for year, month in sorted(wanted):
        found.extend(sorted((ERA5_DIR / f"{year:04d}").glob(
            f"era5_land_{year:04d}{month:02d}*.nc")))
    return found


def catchment_weighted(values: xr.DataArray, weights: dict) -> dict[str, float]:
    """Area-weighted catchment means, ignoring NaN cells entirely.

    ERA5-Land is land-only: sea cells are permanently NaN. They contribute to
    neither the numerator nor the denominator, so a coastal catchment reports
    the mean of the land it actually has rather than a value dragged toward
    zero by the sea.
    """
    out = {}
    for catchment_id, (lat_idx, lon_idx, areas) in weights.items():
        cells = values.values[lat_idx, lon_idx]
        valid = np.isfinite(cells)
        if not valid.any():
            out[catchment_id] = float("nan")
            continue
        out[catchment_id] = float(
            (cells[valid] * areas[valid]).sum() / areas[valid].sum()
        )
    return out


def label_distribution(table: pd.DataFrame, label_columns: list[str]) -> dict:
    """Publish the label's shape so the target definition is an informed choice.

    Whoever trains on this file has to pick a target formulation, and the obvious
    pick is wrong. Within the candidate set — already the top ~1 % of days by
    rainfall — almost every storm produces *some* ERA5 runoff, so a binary
    "did runoff occur" target is ~98 % positive: predicting yes always scores ~98 %
    and learns nothing. That is the same tautology the label rule guards against,
    reached from the other direction, and it would not look like a bug. It would
    look like a good score.

    The magnitude does vary — about 19x between the median and the maximum within a
    single catchment — so the usable formulations are regression on the value (log
    scale, it spans four orders of magnitude) or a binary split at a percentile of
    the candidate set. The percentile balances are given so that choice needs no
    further computation.
    """
    import numpy as np

    out = {}
    for col in label_columns:
        raw = table[col]
        v = raw.dropna()
        if v.empty:
            out[col] = {"non_missing": 0, "note": "no values — ERA5 months absent"}
            continue
        pct = {f"p{p}": round(float(np.percentile(v, p)), 6)
               for p in (10, 25, 50, 75, 90, 99)}
        out[col] = {
            "rows": int(len(raw)),
            "missing": int(raw.isna().sum()),
            "exactly_zero": int((v == 0).sum()),
            "greater_than_zero": int((v > 0).sum()),
            "fraction_positive_at_zero_threshold": round(float((v > 0).mean()), 4),
            "percentiles_mm": pct,
            "binary_balance_at_percentile": {
                f"p{p}": round(float((v > np.percentile(v, p)).mean()), 3)
                for p in (50, 75, 90)
            },
            "per_catchment_median_mm": {
                k: round(float(x), 6) for k, x in
                table.dropna(subset=[col]).groupby("catchment_id")[col].median().items()
            },
        }
    out["target_warning"] = (
        "Do NOT use `> 0` as a classification target. Within the candidate set it is "
        "~98 % positive, so the majority-class model scores ~98 % and predicts nothing. "
        "Use regression on the magnitude (log scale — it spans four orders of "
        "magnitude) or a binary split at a candidate-set percentile; p50 gives a 50/50 "
        "split. Whichever is chosen, the threshold is a modelling decision and belongs "
        "in the model card, not buried in a script."
    )
    out["leakage_warning"] = (
        "Per-catchment medians order monotonically with catchment area (AQ-C01 largest "
        "and wettest, AQ-C05 smallest and driest). Combined with static features that "
        "are constant per catchment, random CV will memorise catchment identity. This is "
        "why leave-one-catchment-out AND a temporal holdout are both mandatory."
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only-available", action="store_true",
                        help="skip events whose ERA5 months are not downloaded")
    args = parser.parse_args()

    events = pd.read_parquet(EVENTS)
    events["date"] = pd.to_datetime(events["date"], utc=True)
    catchments = load_catchments(CATCHMENTS)

    rows, skipped = [], []
    weights_cache = None

    for _, event in events.iterrows():
        day = event["date"]
        files = era5_for(day)
        if not files:
            skipped.append({"event_id": event["event_id"],
                            "reason": "no ERA5 months downloaded yet"})
            continue

        try:
            # Each file goes through read_era5_land rather than
            # xr.open_mfdataset: the reader normalises latitude to ascending,
            # preserves the sea mask, and records the units. open_mfdataset
            # would skip all of that — and needs dask, which this environment
            # does not have. Concatenating afterwards keeps the normalisation.
            parts = [read_era5_land(path) for path in files]
            dataset = (
                parts[0] if len(parts) == 1
                else xr.concat(parts, dim="time").sortby("time")
            )
            dataset = normalize_era5_land_fluxes(
                dataset, mode="auto",
                negative_tolerance_m=NEGATIVE_TOLERANCE_M,
            )
        except Exception as exc:  # noqa: BLE001
            skipped.append({"event_id": event["event_id"],
                            "reason": f"{type(exc).__name__}: {exc}"})
            continue

        if weights_cache is None:
            grid = xr.Dataset(coords={"lat": dataset["lat"], "lon": dataset["lon"]})
            from processing.catchment_rainfall import build_grid_cells
            overlaps = compute_overlaps(build_grid_cells(grid), catchments)
            weights_cache = {}
            for catchment_id, group in overlaps.groupby("catchment_id"):
                weights_cache[catchment_id] = (
                    group["lat_index"].to_numpy(int),
                    group["lon_index"].to_numpy(int),
                    group["intersection_area_m2"].to_numpy(float),
                )
            logger.info("weights built for %d catchment(s)", len(weights_cache))

        times = pd.to_datetime(dataset["time"].values, utc=True)

        def at(moment, name):
            idx = int(np.argmin(np.abs(times - moment)))
            if abs((times[idx] - moment).total_seconds()) > 3600:
                return None
            return dataset[name].isel(time=idx)

        def total(name, start, stop):
            mask = (times > start) & (times <= stop)
            if not mask.any():
                return None
            return dataset[name].isel(time=np.where(mask)[0]).sum("time", skipna=False)

        record_base = {"event_id": event["event_id"], "event_date": day}

        for catchment_id in sorted(weights_cache):
            record_base.setdefault(catchment_id, None)

        per_catchment: dict[str, dict] = {
            cid: dict(record_base, catchment_id=cid) for cid in weights_cache
        }
        for cid in per_catchment:
            per_catchment[cid].pop(cid, None)
            for other in weights_cache:
                per_catchment[cid].pop(other, None)

        # --- features: state before the rain -------------------------------
        for lag in SOIL_LAGS:
            field = at(day - timedelta(hours=lag), "swvl1")
            values = catchment_weighted(field, weights_cache) if field is not None \
                else {c: float("nan") for c in weights_cache}
            for cid, value in values.items():
                per_catchment[cid][f"soil_moisture_t_minus_{lag}h"] = value

        for hours in RAIN_WINDOWS:
            field = total("total_precipitation_hourly_mm", day - timedelta(hours=hours), day)
            values = catchment_weighted(field, weights_cache) if field is not None \
                else {c: float("nan") for c in weights_cache}
            label = {24: "24h", 72: "72h", 168: "7d"}[hours]
            for cid, value in values.items():
                per_catchment[cid][f"precipitation_prior_{label}_mm"] = value

        for name, column in (("u10", "u10_event_time"), ("v10", "v10_event_time"),
                             ("t2m", "temperature_2m_event_time")):
            field = at(day, name)
            values = catchment_weighted(field, weights_cache) if field is not None \
                else {c: float("nan") for c in weights_cache}
            for cid, value in values.items():
                per_catchment[cid][column] = value

        # --- labels: what the rain did -------------------------------------
        for name, column in (("surface_runoff_hourly_mm", "label_surface_runoff_mm"),
                             ("subsurface_runoff_hourly_mm", "label_subsurface_runoff_mm")):
            field = total(name, day, day + timedelta(hours=LABEL_WINDOW_HOURS))
            values = catchment_weighted(field, weights_cache) if field is not None \
                else {c: float("nan") for c in weights_cache}
            for cid, value in values.items():
                per_catchment[cid][column] = value

        rows.extend(per_catchment.values())
        dataset.close()
        logger.info("%-14s %d catchment(s)", event["event_id"], len(per_catchment))

    if not rows:
        logger.error("no events could be processed — is the ERA5 sweep still running?")
        return 1

    table = pd.DataFrame(rows)
    for column in ("u10_event_time", "v10_event_time"):
        if column not in table:
            table[column] = float("nan")
    table["wind_speed_event_time"] = np.hypot(table["u10_event_time"],
                                              table["v10_event_time"])
    # Meteorological convention: the bearing the wind blows FROM.
    table["wind_direction_event_time"] = (
        270.0 - np.degrees(np.arctan2(table["v10_event_time"],
                                      table["u10_event_time"]))
    ) % 360.0

    table = table.sort_values(["event_id", "catchment_id"]).reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(OUT, index=False)

    label_columns = [c for c in table.columns if c.startswith("label_")]

    summary = {
        "label_distribution": label_distribution(table, label_columns),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows": int(len(table)),
        "events_processed": int(table["event_id"].nunique()),
        "events_skipped": len(skipped),
        "skipped": skipped[:50],
        "label_columns": label_columns,
        "label_window_hours": LABEL_WINDOW_HOURS,
        "soil_lags_hours": list(SOIL_LAGS),
        "rain_windows_hours": list(RAIN_WINDOWS),
        "notes": [
            "ERA5-Land is land-only; sea cells are permanently NaN and "
            "contribute to neither numerator nor denominator.",
            "Runoff columns are prefixed label_ so they cannot be mistaken "
            "for features. They are the target, never an input.",
            "Wind direction is meteorological — the bearing the wind blows FROM.",
            "DO NOT BINARISE AT > 0. See label_distribution.target_warning: "
            "almost every candidate storm produces some ERA5 runoff, so "
            "'did runoff occur' is ~98 % positive and a model predicting "
            "'yes' always would score ~98 % while learning nothing. The "
            "discriminating question is MAGNITUDE, not occurrence.",
        ],
    }
    STATUS.write_text(json.dumps(summary, indent=2, default=str) + "\n")

    logger.info("wrote %s — %d row(s), %d event(s), %d skipped",
                OUT.relative_to(PROJECT_ROOT), len(table),
                table["event_id"].nunique(), len(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
