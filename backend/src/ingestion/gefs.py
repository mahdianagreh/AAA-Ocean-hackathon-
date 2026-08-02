"""
NOAA GEFS ingestion — ensemble exceedance probability for the Aqaba AOI.

Source: NOAA GEFS on the public AWS Open Data bucket (noaa-gefs-pds), no credentials
required. Pulled via Herbie, one GRIB subset per ensemble member per lead hour.

Role: Component A (forecast-mode event detection) — nizar.md Part 1 §2.
This is the highest-value item in the Nizar stream: it turns the dashboard's confidence
number from a guess into "N% of ensemble members exceed the catchment's 3h rainfall
threshold" — a defensible statement, not a vibe.

Watch out: GEFS is coarse for local convection — it tells you about synoptic-scale
uncertainty, not whether a single thunderstorm cell lands on Wadi Yutum or 10 km away.

NOTE: exceedance is computed at the AOI grid-cell level for now. Per-catchment thresholds
(from Karam) and per-catchment polygons (from Mahdi) are not yet in this repo — swap
`DEFAULT_RAIN_3H_THRESHOLD_MM` for Karam's real per-catchment percentile the moment his
`rainfall_candidates.parquet` lands, per tasks/00-contracts.md.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import numpy as np
import xarray as xr
from herbie import Herbie

# Make `backend/src` importable whether this module is imported as a
# package, imported by the tests, or run directly as a file.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.spatial import TERRAIN_AOI  # noqa: E402

#: Ensemble rainfall over the catchments: terrain extent.
DOWNLOAD_BBOX = TERRAIN_AOI.wsen

RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "forecasts" / "gefs"
FORECAST_HOURS = list(range(3, 49, 3))  # 3-hourly APCP is an accumulation-since-last-step field
N_MEMBERS = 30  # gep01..gep30; control (gec00) excluded from the probability count by convention

SEARCH_APCP = ":APCP:surface"

# Placeholder — replace with Karam's real per-catchment 99th-percentile 3h rainfall (mm)
# the moment data/processed/events/rainfall_candidates.parquet exists.
DEFAULT_RAIN_3H_THRESHOLD_MM = 15.0


def _most_recent_cycle(now: dt.datetime | None = None) -> dt.datetime:
    if now is None:
        now = dt.datetime.utcnow()
    published_now = now - dt.timedelta(hours=5)  # GEFS lags GFS publication slightly
    cycle_hour = (published_now.hour // 6) * 6
    return published_now.replace(hour=cycle_hour, minute=0, second=0, microsecond=0)


def fetch_gefs_members(
    cycle: dt.datetime | None = None,
    n_members: int = N_MEMBERS,
    forecast_hours: list[int] | None = None,
    max_lookback_cycles: int = 4,
) -> dict[int, list[Herbie]]:
    """Download AOI-relevant APCP GRIB subsets for every member x lead hour.
    Returns {member_number: [Herbie objects per lead hour]}."""
    if cycle is None:
        cycle = _most_recent_cycle()
    forecast_hours = forecast_hours or FORECAST_HOURS

    for attempt in range(max_lookback_cycles):
        run_time = cycle - dt.timedelta(hours=6 * attempt)
        members: dict[int, list[Herbie]] = {}
        try:
            for member in range(1, n_members + 1):
                objs = []
                for fh in forecast_hours:
                    H = Herbie(
                        run_time.strftime("%Y-%m-%d %H:%M"),
                        model="gefs",
                        member=member,
                        product="atmos.5",
                        fxx=fh,
                        save_dir=RAW_DIR,
                    )
                    if not H.grib:
                        raise FileNotFoundError(f"no GRIB index for member {member} f{fh:03d}")
                    H.download(SEARCH_APCP, verbose=False)
                    objs.append(H)
                members[member] = objs
            return members
        except Exception:
            continue

    raise RuntimeError(
        f"No usable GEFS cycle found in the last {max_lookback_cycles} cycles back from {cycle}."
    )


def _member_aoi_precip(objs: list[Herbie]) -> xr.DataArray:
    """Mean AOI 3h accumulated precip per lead hour for one ensemble member."""
    w, s, e, n = DOWNLOAD_BBOX
    slices = []
    for H in objs:
        local_paths = H.get_localFilePath(SEARCH_APCP)
        paths = [local_paths] if isinstance(local_paths, (str, Path)) else list(local_paths)
        for p in paths:
            if not Path(p).exists():
                continue
            ds = xr.open_dataset(p, engine="cfgrib", backend_kwargs={"indexpath": ""})
            ds = ds.sel(longitude=slice(w % 360, e % 360), latitude=slice(n, s))
            aoi_mean = ds["tp"].mean(dim=["latitude", "longitude"])
            slices.append(aoi_mean.expand_dims(lead_hour=[H.fxx]))
    return xr.concat(slices, dim="lead_hour")


def exceedance_probability(
    members: dict[int, list[Herbie]], threshold_mm: float = DEFAULT_RAIN_3H_THRESHOLD_MM
) -> xr.Dataset:
    """Fraction of ensemble members whose 3h AOI-mean precip exceeds the catchment threshold,
    per lead hour. This is what feeds `event_probability` in the Component A output."""
    per_member = [_member_aoi_precip(objs).assign_coords(member=m) for m, objs in members.items()]
    stacked = xr.concat(per_member, dim="member")
    exceeds = (stacked > threshold_mm).astype(float)
    prob = exceeds.mean(dim="member")
    return xr.Dataset(
        {
            "exceedance_probability": prob,
            "ensemble_mean_precip_mm": stacked.mean(dim="member"),
            "ensemble_max_precip_mm": stacked.max(dim="member"),
        },
        attrs={"threshold_mm": threshold_mm, "n_members": len(members)},
    )


def run(threshold_mm: float = DEFAULT_RAIN_3H_THRESHOLD_MM, cache_path: Path | None = None) -> xr.Dataset:
    members = fetch_gefs_members()
    result = exceedance_probability(members, threshold_mm=threshold_mm)

    cache_path = cache_path or (RAW_DIR / "latest_gefs_exceedance.nc")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_netcdf(cache_path)
    return result


if __name__ == "__main__":
    ds = run()
    print(ds)
    print(f"\nexceedance_probability at F03: {float(ds['exceedance_probability'].isel(lead_hour=0)):.2f}")
