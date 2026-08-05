"""Forcing adapters for `particle_engine.simulate()`.

`ocean_currents.CurrentFieldInterpolator.__call__` goes through
`xarray.Dataset.interp`, ~4 ms/call measured against the cached historical HYCOM
grid (data/raw/currents/hycom_aoi_AQ-2016-10-28.nc) -- fine for one lookup, wrong
for this caller: `simulate()` calls `current_fn` once per active particle per
timestep, so a 2,000-particle 24h/15min run is ~192,000 calls, ~13 minutes.

`fast_current_fn` builds a `scipy.interpolate.RegularGridInterpolator` from the
IDENTICAL grid and the SAME linear method, wrapped in the SAME
`current_fn(lon, lat, time, depth) -> (u, v)` signature `particle_engine.py`
documents as the contract. Numerically equivalent to `CurrentFieldInterpolator`
(both are multilinear interpolation over the same points) and no accuracy is
traded for the speedup: the grid itself is the accuracy ceiling here (~9 km,
daily) -- reproducing point lookups on it faster does not make it any coarser
than it already is.
"""

from __future__ import annotations

import datetime as dt
from typing import Callable

import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator

from ingestion.ocean_currents import CurrentFieldInterpolator

CurrentFn = Callable[[float, float, dt.datetime, float], tuple[float, float]]


def _time_to_epoch_seconds(time) -> float:
    """Mirrors `CurrentFieldInterpolator.__call__`'s own tz handling exactly --
    accepts whatever datetime flavor a caller has (tz-aware Timestamp, naive
    datetime, np.datetime64, ISO string) and returns a tz-naive epoch-seconds
    float comparable against the grid's own tz-naive time coordinate."""
    ts = pd.Timestamp(time)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.to_numpy().astype("datetime64[s]").astype(np.float64)


def fast_current_fn(interpolator: CurrentFieldInterpolator) -> CurrentFn:
    """Wrap `interpolator`'s grid in a vectorization-friendly interpolator with
    the exact `current_fn` contract `particle_engine.simulate()` calls.

    Built once per simulation (not per particle, not per step) -- the
    `RegularGridInterpolator` construction cost is paid once; each subsequent
    call is a single small-grid lookup.
    """
    ds = interpolator.dataset
    has_depth = "depth" in ds.dims

    time_axis = np.array([_time_to_epoch_seconds(t) for t in ds["time"].values])
    lat_axis = ds["latitude"].values.astype(np.float64)
    lon_axis = ds["longitude"].values.astype(np.float64)

    if has_depth:
        depth_axis = ds["depth"].values.astype(np.float64)
        depth_min, depth_max = float(depth_axis.min()), float(depth_axis.max())
        u = ds["u"].transpose("time", "depth", "latitude", "longitude").values
        v = ds["v"].transpose("time", "depth", "latitude", "longitude").values
        axes = (time_axis, depth_axis, lat_axis, lon_axis)
    else:
        u = ds["u"].transpose("time", "latitude", "longitude").values
        v = ds["v"].transpose("time", "latitude", "longitude").values
        axes = (time_axis, lat_axis, lon_axis)

    # NaN cells (land-masked, or below the product's shallowest level) pass
    # through untouched -- `simulate()` already does `np.nan_to_num(..., nan=0.0)`
    # on this function's output, same as it does for `CurrentFieldInterpolator`.
    u_interp = RegularGridInterpolator(axes, u, method="linear", bounds_error=False,
                                        fill_value=np.nan)
    v_interp = RegularGridInterpolator(axes, v, method="linear", bounds_error=False,
                                        fill_value=np.nan)

    def _current_fn(lon: float, lat: float, time, depth: float = 0.0) -> tuple[float, float]:
        t = _time_to_epoch_seconds(time)
        if has_depth:
            # Same "clip into the dataset's own depth range" behaviour as
            # `CurrentFieldInterpolator` -- "surface" means the shallowest
            # level this product has, not literally 0 m.
            d = min(max(depth, depth_min), depth_max)
            point = np.array([[t, d, lat, lon]])
        else:
            point = np.array([[t, lat, lon]])
        return float(u_interp(point)[0]), float(v_interp(point)[0])

    return _current_fn


__all__ = ["fast_current_fn"]
