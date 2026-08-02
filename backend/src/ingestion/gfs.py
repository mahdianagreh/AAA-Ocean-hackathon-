"""
NOAA GFS ingestion — deterministic forecast rainfall + 10 m wind for the Aqaba AOI.

Source: NOAA GFS on the public AWS Open Data bucket (noaa-gfs-bdp-pds), no credentials
required. Pulls via Herbie, which uses the GRIB .idx sidecar files to byte-range only the
needed messages instead of downloading the full global GRIB2 file.

Role: Component A (forecast-mode event detection) — nizar.md Part 1 §1.
Deliverable: backend/src/ingestion/gfs.py + one cached live forecast for the demo.

Important framing (per nizar.md): this must work on an ordinary dry day. The point is to
show the pipeline ingesting a live forecast and producing a correctly low risk number, not
to only be demoable during a storm.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import xarray as xr
from herbie import Herbie

# Padded download bbox from tasks/00-contracts.md §1 (W, S, E, N — EPSG:4326)
# Make `backend/src` importable whether this module is imported as a
# package, imported by the tests, or run directly as a file.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.spatial import TERRAIN_AOI  # noqa: E402

#: Forecast rainfall drives the catchments, so: terrain extent.
DOWNLOAD_BBOX = TERRAIN_AOI.wsen

RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "forecasts" / "gfs"
FORECAST_HOURS = list(range(0, 49, 3))  # 48 h lead, 3-hourly steps

# GRIB search patterns (Herbie regex against the .idx file)
SEARCH_APCP = ":APCP:surface"                     # total precipitation, accumulated since run start
SEARCH_WIND = ":(?:UGRD|VGRD):10 m above ground"  # 10 m u/v wind components


def _most_recent_cycle(now: dt.datetime | None = None) -> dt.datetime:
    """GFS runs at 00/06/12/18Z, published ~3-4h after cycle time. Round down to the
    most recent cycle that has plausibly already been published."""
    if now is None:
        now = dt.datetime.utcnow()
    published_now = now - dt.timedelta(hours=4)
    cycle_hour = (published_now.hour // 6) * 6
    return published_now.replace(hour=cycle_hour, minute=0, second=0, microsecond=0)


def fetch_gfs_run(cycle: dt.datetime | None = None, max_lookback_cycles: int = 4) -> list[Herbie]:
    """Find the most recent available GFS cycle and download AOI-subset GRIB messages
    (precip + 10m wind) for every forecast hour. Returns the list of per-lead-hour Herbie
    objects with local GRIB subset files already downloaded."""
    if cycle is None:
        cycle = _most_recent_cycle()

    for attempt in range(max_lookback_cycles):
        run_time = cycle - dt.timedelta(hours=6 * attempt)
        objs = []
        try:
            for fh in FORECAST_HOURS:
                H = Herbie(
                    run_time.strftime("%Y-%m-%d %H:%M"),
                    model="gfs",
                    product="pgrb2.0p25",
                    fxx=fh,
                    save_dir=RAW_DIR,
                )
                if not H.grib:
                    raise FileNotFoundError(f"no GRIB index for {run_time} f{fh:03d}")
                H.download(f"{SEARCH_APCP}|{SEARCH_WIND}", verbose=False)
                objs.append(H)
            return objs
        except Exception:
            continue

    raise RuntimeError(
        f"No usable GFS cycle found in the last {max_lookback_cycles} cycles back from {cycle}."
    )


def load_aoi_subset(objs: list[Herbie]) -> xr.Dataset:
    """Open the downloaded GRIB subsets and clip to the padded AOI bbox."""
    w, s, e, n = DOWNLOAD_BBOX
    datasets = []
    for H in objs:
        local_paths = H.get_localFilePath(f"{SEARCH_APCP}|{SEARCH_WIND}")
        paths = [local_paths] if isinstance(local_paths, (str, Path)) else list(local_paths)
        for p in paths:
            if not Path(p).exists():
                continue
            ds = xr.open_dataset(p, engine="cfgrib", backend_kwargs={"indexpath": ""})
            ds = ds.sel(
                longitude=slice(w % 360, e % 360),
                latitude=slice(n, s),  # GFS latitude is typically north-to-south
            )
            ds = ds.expand_dims(lead_hour=[H.fxx])
            datasets.append(ds)
    if not datasets:
        raise RuntimeError("No GRIB subset files were found on disk after download.")
    return xr.concat(datasets, dim="lead_hour", combine_attrs="drop_conflicts")


def run(cache_path: Path | None = None) -> xr.Dataset:
    """End-to-end: fetch latest GFS run, subset to AOI, cache one live forecast to NetCDF.
    Must succeed on any ordinary day regardless of current weather."""
    objs = fetch_gfs_run()
    ds = load_aoi_subset(objs)

    cache_path = cache_path or (RAW_DIR / "latest_gfs_aoi_forecast.nc")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(cache_path)
    return ds


if __name__ == "__main__":
    dataset = run()
    print(dataset)
