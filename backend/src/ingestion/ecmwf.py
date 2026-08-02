"""
ECMWF IFS / AIFS Open Data ingestion — independent second-opinion forecast + a
GFS-vs-IFS agreement flag for the Aqaba AOI.

Source: ECMWF Open Data (open subset, no registration) via the `ecmwf-opendata` client.
Rolling archive only — do not use this for historical backfill (nizar.md Part 1 §3).

Role: Component A (forecast-mode event detection) — nizar.md Part 1 §3.
Deliverable: backend/src/ingestion/ecmwf.py + the GFS-vs-IFS agreement indicator.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import xarray as xr
from ecmwf.opendata import Client

DOWNLOAD_BBOX = (34.80, 29.25, 35.15, 29.70)  # W, S, E, N — EPSG:4326, tasks/00-contracts.md §1
RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "forecasts" / "ecmwf"
FORECAST_STEPS = list(range(0, 49, 3))  # 48 h lead, 3-hourly — matches the GFS pull

PARAMS = ["tp", "10u", "10v"]


def fetch_ifs_forecast(steps: list[int] | None = None, model: str = "ifs") -> Path:
    """Download the latest available ECMWF open-data forecast (global 0.25 deg) for the
    parameters/steps needed, as a single GRIB2 file. `model` is "ifs" (physics-based) or
    "aifs" (ECMWF's ML-based forecast) — same client, same open subset."""
    steps = steps or FORECAST_STEPS
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    target = RAW_DIR / f"{model}_latest_global.grib2"

    client = Client(source="ecmwf", model=model)
    client.retrieve(
        type="fc",
        stream="oper",
        param=PARAMS,
        step=steps,
        target=str(target),
    )
    return target


def load_aoi_subset(grib_path: Path) -> xr.Dataset:
    w, s, e, n = DOWNLOAD_BBOX
    ds = xr.open_dataset(grib_path, engine="cfgrib", backend_kwargs={"indexpath": ""})
    return ds.sel(longitude=slice(w % 360, e % 360), latitude=slice(n, s))


def _normalize_step_hours(ifs_aoi: xr.Dataset, gfs_aoi: xr.Dataset) -> tuple[xr.Dataset, xr.Dataset]:
    """Both GRIB sources index lead time differently after cfgrib decoding (IFS: `step`
    as timedelta64; GFS: `lead_hour` as int). Normalize both to an integer step-hours
    coordinate named `step` so they can be joined."""
    ifs_norm = ifs_aoi.assign_coords(step=(ifs_aoi["step"] / 1e9 / 3600).astype("int64"))
    gfs_norm = gfs_aoi.drop_vars("step", errors="ignore").rename(lead_hour="step")
    return ifs_norm, gfs_norm


def gfs_vs_ifs_agreement(ifs_aoi: xr.Dataset, gfs_aoi: xr.Dataset) -> xr.Dataset:
    """Simple two-model agreement flag: do GFS and IFS agree on rain/no-rain over the AOI
    at matching lead times? Surfaced in the dashboard as a cheap credibility signal —
    "two independent models agree" is stronger than either model alone."""
    ifs_aoi, gfs_aoi = _normalize_step_hours(ifs_aoi, gfs_aoi)
    ifs_tp = ifs_aoi["tp"].mean(dim=["latitude", "longitude"]) * 1000  # m -> mm
    gfs_tp = gfs_aoi["tp"].mean(dim=["latitude", "longitude"])

    common_steps = sorted(set(ifs_tp["step"].values.tolist()) & set(gfs_tp["step"].values.tolist()))
    ifs_c = ifs_tp.sel(step=common_steps)
    gfs_c = gfs_tp.sel(step=common_steps)

    rain_threshold_mm = 1.0
    ifs_rain = ifs_c > rain_threshold_mm
    gfs_rain = gfs_c > rain_threshold_mm
    agree = ifs_rain == gfs_rain

    return xr.Dataset(
        {
            "ifs_tp_mm": ifs_c,
            "gfs_tp_mm": gfs_c,
            "agree": agree,
        },
        attrs={"rain_threshold_mm": rain_threshold_mm},
    )


def run(cache_path: Path | None = None) -> Path:
    """Fetch the latest IFS open-data run and cache the AOI-subset GRIB locally.
    Rolling archive only — this is a live/near-real-time source, never historical."""
    grib_path = fetch_ifs_forecast()
    ds = load_aoi_subset(grib_path)
    cache_path = cache_path or (RAW_DIR / "latest_ifs_aoi_forecast.nc")
    ds.to_netcdf(cache_path)
    return cache_path


if __name__ == "__main__":
    path = run()
    print(f"Cached IFS AOI subset to {path}")
