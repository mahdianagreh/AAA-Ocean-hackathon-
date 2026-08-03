"""
Ocean current forcing for the particle engine — Copernicus Marine (primary) + HYCOM
(backup / cross-check), Aqaba AOI, surface + upper depth levels.

Role: Component F (probabilistic marine plume transport) — nizar.md Part 2.

Why surface + upper depths, not surface-only: Katz et al. 2015 found Aqaba flash floods
form hyperpycnal flows — sediment-dense water that sinks and moves along the seabed rather
than floating as a surface plume. Surface currents alone may be the wrong forcing for part
of the sediment mass.

Why two independent sources: the concept doc (§24.3, §25) flags ~1/12 deg (~9 km) ocean
current resolution as the project's single biggest accuracy limit — a gulf only ~15-25 km
wide is barely 2-3 grid cells across. Comparing Copernicus Marine against HYCOM at the
outlet gives an honest measure of forcing uncertainty rather than presenting one model's
current direction as ground truth.

Acceptance (nizar.md): the particle engine calls `interpolator(lon, lat, time, depth)` and
gets u/v back — no manual reshape, transpose, or coordinate-name fix required by the caller.
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(REPO_ROOT / "backend" / ".env")

# Make `backend/src` importable whether this module is imported as a
# package, imported by the tests, or run directly as a file.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.spatial import MARINE_AOI  # noqa: E402

#: Currents are the sea side of the contract: marine extent.
DOWNLOAD_BBOX = MARINE_AOI.wsen
RAW_DIR = REPO_ROOT / "data" / "raw" / "currents"
MAX_DEPTH_M = 50  # "surface plus the upper depth levels" per nizar.md

HYCOM_URL = "https://tds.hycom.org/thredds/dodsC/GLBy0.08/latest"
COPERNICUS_DATASET_ID = "cmems_mod_glo_phy_anfc_0.083deg_PT1H-m"  # GLOBAL_ANALYSISFORECAST_PHY_001_024

# Historical sources for the demo event (AQ-2016-10-28). The "latest"/"anfc" products
# above are rolling windows around the present day and do not reach back to 2016 —
# confirmed empirically, not assumed. These are the correct products for that date:
#   - HYCOM GLBu0.08/expt_91.2: operational analysis, 2016-04-18 to 2018-11-20, 40 depth
#     levels 0-5000m. The "latest" FMRC endpoint has no 2016 data at all.
#   - Copernicus Marine GLORYS12V1 reanalysis (multiyear, not analysis-forecast): has 18
#     depth levels within 0-50m and covers 2016. The "anfc" tier used for live forcing
#     only ships a single ~0.49m surface level — wrong product for this, not a bug in
#     the interpolator.
HYCOM_HISTORICAL_URL = "https://tds.hycom.org/thredds/dodsC/GLBu0.08/expt_91.2/uv3z"
COPERNICUS_HISTORICAL_DATASET_ID = "cmems_mod_glo_phy_my_0.083deg_P1D-m"  # GLOBAL_MULTIYEAR_PHY_001_030

DEMO_EVENT_WINDOW = (dt.datetime(2016, 10, 26), dt.datetime(2016, 10, 31))  # baseline + event + settle


# ---------------------------------------------------------------------------
# HYCOM — backup currents, public OPeNDAP server, no registration required
# ---------------------------------------------------------------------------

def fetch_hycom(window_hours: int = 24, now: dt.datetime | None = None) -> xr.Dataset:
    """Pull u/v currents for the AOI, surface + upper depths, from HYCOM's public THREDDS
    FMRC 'best dataset' endpoint. Lazy-opened via OPeNDAP so only the AOI subset is
    transferred, never the full 2 TB global grid.

    The FMRC 'best dataset' time axis spans historical-through-forecast, so the tail of
    the axis is the *furthest* forecast lead, not necessarily current — select a window
    centered on `now` rather than blindly taking the last N steps."""
    now = now or dt.datetime.utcnow()
    w, s, e, n = DOWNLOAD_BBOX
    ds = xr.open_dataset(HYCOM_URL, drop_variables=["tau"])
    time_window = slice(
        np.datetime64(now - dt.timedelta(hours=window_hours)),
        np.datetime64(now + dt.timedelta(hours=window_hours)),
    )
    sub = (
        ds[["water_u", "water_v"]]
        .sel(lon=slice(w, e), lat=slice(s, n), depth=slice(0, MAX_DEPTH_M), time=time_window)
        .rename({"water_u": "u", "water_v": "v", "lon": "longitude", "lat": "latitude"})
        .load()
    )
    return sub


def cache_hycom(cache_path: Path | None = None) -> Path:
    ds = fetch_hycom()
    cache_path = cache_path or (RAW_DIR / "hycom_aoi_recent.nc")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(cache_path)
    return cache_path


def fetch_hycom_historical(
    start: dt.datetime | None = None, end: dt.datetime | None = None
) -> xr.Dataset:
    """Pull u/v currents for the demo event window from HYCOM's operational-analysis
    archive (GLBu0.08/expt_91.2), not the 'latest' FMRC endpoint — that one is a rolling
    window around today and has no 2016 data. Defaults to DEMO_EVENT_WINDOW."""
    start = start or DEMO_EVENT_WINDOW[0]
    end = end or DEMO_EVENT_WINDOW[1]
    w, s, e, n = DOWNLOAD_BBOX
    ds = xr.open_dataset(HYCOM_HISTORICAL_URL, drop_variables=["tau"])
    sub = (
        ds[["water_u", "water_v"]]
        .sel(
            lon=slice(w, e), lat=slice(s, n), depth=slice(0, MAX_DEPTH_M),
            time=slice(np.datetime64(start), np.datetime64(end)),
        )
        .rename({"water_u": "u", "water_v": "v", "lon": "longitude", "lat": "latitude"})
        .load()
    )
    return sub


def cache_hycom_historical(cache_path: Path | None = None) -> Path:
    ds = fetch_hycom_historical()
    cache_path = cache_path or (RAW_DIR / "hycom_aoi_AQ-2016-10-28.nc")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(cache_path)
    return cache_path


# ---------------------------------------------------------------------------
# Copernicus Marine — primary currents. Requires COPERNICUS_MARINE_USERNAME/PASSWORD,
# not yet provided (backend/.env only has NASA Earthdata creds as of 2026-08-02).
# ---------------------------------------------------------------------------

def copernicus_marine_available() -> bool:
    return bool(os.getenv("COPERNICUS_MARINE_USERNAME")) and bool(
        os.getenv("COPERNICUS_MARINE_PASSWORD")
    )


def fetch_copernicus_marine(window_hours: int = 24, now: dt.datetime | None = None) -> xr.Dataset:
    """Primary current forcing. Structurally identical output to `fetch_hycom` (same
    variable names, same dims) so the interpolator and everything downstream is agnostic
    to which source is active. Raises clearly if credentials aren't configured yet —
    this is intentional: fail loudly rather than silently falling back to HYCOM."""
    if not copernicus_marine_available():
        raise RuntimeError(
            "COPERNICUS_MARINE_USERNAME/PASSWORD not set in backend/.env. "
            "Register at https://data.marine.copernicus.eu/, add the credentials, "
            "then call fetch_copernicus_marine() again — no code change needed."
        )

    import copernicusmarine

    now = now or dt.datetime.utcnow()
    w, s, e, n = DOWNLOAD_BBOX
    ds = copernicusmarine.open_dataset(
        dataset_id=COPERNICUS_DATASET_ID,
        variables=["uo", "vo"],
        minimum_longitude=w,
        maximum_longitude=e,
        minimum_latitude=s,
        maximum_latitude=n,
        minimum_depth=0,
        maximum_depth=MAX_DEPTH_M,
        start_datetime=(now - dt.timedelta(hours=window_hours)).isoformat(),
        end_datetime=(now + dt.timedelta(hours=window_hours)).isoformat(),
        username=os.environ["COPERNICUS_MARINE_USERNAME"],
        password=os.environ["COPERNICUS_MARINE_PASSWORD"],
    )
    ds = ds.rename({"uo": "u", "vo": "v"})
    return ds


def cache_copernicus_marine(cache_path: Path | None = None) -> Path:
    ds = fetch_copernicus_marine()
    cache_path = cache_path or (RAW_DIR / "copernicus_marine_aoi_recent.nc")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(cache_path)
    return cache_path


def fetch_copernicus_marine_historical(
    start: dt.datetime | None = None, end: dt.datetime | None = None
) -> xr.Dataset:
    """Pull u/v currents for the demo event window from the GLORYS12V1 reanalysis
    (multiyear product), not the 'anfc' analysis-forecast tier used for live forcing —
    that one only covers a rolling recent window and ships a single surface depth level.
    This product has 18 real depth levels within 0-50m and reaches back to 2016."""
    if not copernicus_marine_available():
        raise RuntimeError(
            "COPERNICUS_MARINE_USERNAME/PASSWORD not set in backend/.env."
        )

    import copernicusmarine

    start = start or DEMO_EVENT_WINDOW[0]
    end = end or DEMO_EVENT_WINDOW[1]
    w, s, e, n = DOWNLOAD_BBOX
    ds = copernicusmarine.open_dataset(
        dataset_id=COPERNICUS_HISTORICAL_DATASET_ID,
        variables=["uo", "vo"],
        minimum_longitude=w,
        maximum_longitude=e,
        minimum_latitude=s,
        maximum_latitude=n,
        minimum_depth=0,
        maximum_depth=MAX_DEPTH_M,
        start_datetime=start.isoformat(),
        end_datetime=end.isoformat(),
        username=os.environ["COPERNICUS_MARINE_USERNAME"],
        password=os.environ["COPERNICUS_MARINE_PASSWORD"],
    )
    ds = ds.rename({"uo": "u", "vo": "v"})
    return ds


def cache_copernicus_marine_historical(cache_path: Path | None = None) -> Path:
    ds = fetch_copernicus_marine_historical()
    cache_path = cache_path or (RAW_DIR / "copernicus_marine_aoi_AQ-2016-10-28.nc")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(cache_path)
    return cache_path


# ---------------------------------------------------------------------------
# Interpolator — what the particle engine actually calls
# ---------------------------------------------------------------------------

class CurrentFieldInterpolator:
    """Wraps a u/v xarray.Dataset (from either source, same schema) and exposes a single
    `__call__(lon, lat, time, depth=0.0)` -> (u, v) method. No reshape, no transpose, no
    coordinate-name lookup required by the caller — that's the acceptance criterion."""

    def __init__(self, ds: xr.Dataset):
        self._ds = ds

    def __call__(self, lon: float, lat: float, time, depth: float = 0.0):
        ds = self._ds
        # Callers pass whatever datetime flavor they have — np.datetime64 (our own
        # __main__ demo), tz-aware pandas.Timestamp (the particle engine, per
        # models/particle_engine.py's simulate()), tz-naive datetime, or an ISO
        # string. xarray's .interp() only accepts datetime64/naive-datetime-like
        # values against a tz-naive time coordinate — reject a raw tz-aware
        # Timestamp with a TypeError instead of silently mis-comparing. Normalize
        # here so every caller gets the same contract regardless of what they hand in.
        time_ts = pd.Timestamp(time)
        if time_ts.tzinfo is not None:
            time_ts = time_ts.tz_localize(None)
        time = np.datetime64(time_ts)
        # Some Copernicus Marine products (e.g. the hourly-mean surface tier) ship a
        # single depth level. Linearly interpolating a dimension with only one
        # coordinate divides by zero (x_hi - x_lo == 0) and silently returns nan —
        # select nearest instead of interpolating when there's nothing to interpolate
        # between.
        if ds.sizes.get("depth", 1) <= 1:
            ds = ds.sel(depth=depth, method="nearest")
            point = ds.interp(longitude=lon, latitude=lat, time=time, method="linear")
        else:
            # The shallowest level on some products (e.g. GLORYS12V1) is ~0.49 m, not
            # 0.0 m. Requesting depth=0.0 (our "surface" default) then asks xarray to
            # extrapolate *below* the coordinate's minimum, which silently returns nan
            # rather than raising. Clip into the dataset's own depth range first —
            # "surface" means the shallowest level this product has, not literally 0 m.
            depth_min = float(ds["depth"].min())
            depth_max = float(ds["depth"].max())
            depth = min(max(depth, depth_min), depth_max)
            point = ds.interp(longitude=lon, latitude=lat, time=time, depth=depth, method="linear")
        return float(point["u"].values), float(point["v"].values)


def build_interpolator(prefer: str = "copernicus_marine") -> CurrentFieldInterpolator:
    """Primary/backup selection: try Copernicus Marine first, fall back to HYCOM if
    credentials aren't configured yet. Swapping in Copernicus Marine later requires no
    change downstream — the interpolator interface is identical either way."""
    if prefer == "copernicus_marine" and copernicus_marine_available():
        ds = fetch_copernicus_marine()
    else:
        ds = fetch_hycom()
    return CurrentFieldInterpolator(ds)


# ---------------------------------------------------------------------------
# HYCOM vs Copernicus Marine direction comparison — an honest measure of forcing
# uncertainty rather than presenting one model's current direction as ground truth.
# ---------------------------------------------------------------------------

def compare_hycom_vs_copernicus(
    lon: float,
    lat: float,
    time: np.datetime64,
    depth: float = 0.0,
    hycom_path: Path | None = None,
    copernicus_path: Path | None = None,
) -> dict:
    """Query both current sources at the same point/time and report the direction
    and speed disagreement. Requires both to already be cached locally (call
    cache_hycom() / cache_copernicus_marine(), or the *_historical() variants,
    first — pass their returned paths through here for the historical case)."""
    hycom_ds = xr.open_dataset(hycom_path or (RAW_DIR / "hycom_aoi_recent.nc"))
    cm_ds = xr.open_dataset(copernicus_path or (RAW_DIR / "copernicus_marine_aoi_recent.nc"))

    u_h, v_h = CurrentFieldInterpolator(hycom_ds)(lon, lat, time, depth)
    u_c, v_c = CurrentFieldInterpolator(cm_ds)(lon, lat, time)

    result = dict(lon=lon, lat=lat, time=str(time))
    for name, u, v in [("hycom", u_h, v_h), ("copernicus_marine", u_c, v_c)]:
        result[f"{name}_u_ms"] = u
        result[f"{name}_v_ms"] = v
        result[f"{name}_speed_ms"] = float(np.hypot(u, v)) if not np.isnan(u) else None
        result[f"{name}_direction_from_deg"] = (
            float((270 - np.degrees(np.arctan2(v, u))) % 360) if not np.isnan(u) else None
        )

    if result["hycom_direction_from_deg"] is not None and result["copernicus_marine_direction_from_deg"] is not None:
        diff = abs(result["hycom_direction_from_deg"] - result["copernicus_marine_direction_from_deg"])
        result["direction_diff_deg"] = min(diff, 360 - diff)
    else:
        result["direction_diff_deg"] = None
    return result


if __name__ == "__main__":
    hycom_path = cache_hycom()
    print(f"Cached HYCOM AOI subset to {hycom_path}")

    if copernicus_marine_available():
        cm_path = cache_copernicus_marine()
        print(f"Cached Copernicus Marine AOI subset to {cm_path}")
    else:
        print(
            "Copernicus Marine credentials not set — skipped. "
            "Add COPERNICUS_MARINE_USERNAME/PASSWORD to backend/.env to enable."
        )

    interp = build_interpolator()
    now = np.datetime64(dt.datetime.utcnow())

    # The provisional outlet (34.96, 29.54) sits right at the edge of what this ~9 km grid
    # resolves as open water — interpolating there returns nan. This is not a bug; it is
    # the resolution limitation this stream owns, observed directly rather than asserted.
    u_outlet, v_outlet = interp(lon=34.96, lat=29.52, time=now)
    print(f"At provisional outlet (34.96, 29.52): u={u_outlet}, v={v_outlet} "
          f"({'nan — outlet cell is masked/land in this grid' if np.isnan(u_outlet) else 'resolved'})")

    u_mouth, v_mouth = interp(lon=34.90, lat=29.40, time=now)
    print(f"At the gulf mouth, 6 km further offshore (34.90, 29.40): u={u_mouth:.4f} m/s, v={v_mouth:.4f} m/s")

    if copernicus_marine_available():
        comparison = compare_hycom_vs_copernicus(lon=34.90, lat=29.40, time=now)
        print(f"HYCOM vs Copernicus Marine at (34.90, 29.40): {comparison}")

    # --- Historical: the actual demo event window, AQ-2016-10-28 ---
    print("\nFetching historical currents for the demo event (26-31 Oct 2016)...")
    hycom_hist_path = cache_hycom_historical()
    print(f"Cached HYCOM historical AOI subset to {hycom_hist_path}")

    if copernicus_marine_available():
        cm_hist_path = cache_copernicus_marine_historical()
        print(f"Cached Copernicus Marine historical AOI subset to {cm_hist_path}")

        event_time = np.datetime64(dt.datetime(2016, 10, 28, 6, 50))  # mooring peak response
        # (34.90, 29.40) — the live "gulf mouth" point — is not resolved by either
        # historical archive at this date (different grids/masks than the live
        # products). (34.85, 29.30) is the nearest point confirmed resolved by BOTH
        # historical grids simultaneously.
        hist_comparison = compare_hycom_vs_copernicus(
            lon=34.85, lat=29.30, time=event_time,
            hycom_path=hycom_hist_path, copernicus_path=cm_hist_path,
        )
        print(f"HYCOM vs Copernicus Marine at event peak (2016-10-28 06:50): {hist_comparison}")
