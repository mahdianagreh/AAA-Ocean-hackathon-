"""Event-agnostic antecedent feature extraction from normalised ERA5-Land.

Given any ERA5-Land dataset and any event timestamp inside it, produces the
gridded pre-event predictors ReefShield needs: antecedent soil moisture,
prior-window rainfall and runoff totals, and event-time wind and temperature.

Nothing about a particular event is hard-coded. The event time, the offsets and
the window lengths are all arguments.

Policies enforced throughout:

* **UTC only.** Event times must be timezone-aware UTC (or naive, read as UTC)
  and hour-aligned, matching the hourly ERA5-Land axis.
* **Missing is not zero.** NaN hours are excluded from sums, and the fraction
  of the window that was actually usable is reported per feature.
* **No interpolation.** Sea-mask cells stay NaN forever.
* **Full windows by default.** A feature whose window is not fully covered is
  flagged, and by default the extraction refuses to run at all if history is
  short.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)

SOURCE_PRODUCT = "ERA5-Land Hourly"
CANONICAL_TIMEZONE = "UTC"

#: Normalised hourly accumulation variables this module consumes.
PRECIPITATION_VARIABLE = "total_precipitation_hourly_mm"
SURFACE_RUNOFF_VARIABLE = "surface_runoff_hourly_mm"
SUBSURFACE_RUNOFF_VARIABLE = "subsurface_runoff_hourly_mm"
SOIL_MOISTURE_VARIABLE = "swvl1"
U_WIND_VARIABLE = "u10"
V_WIND_VARIABLE = "v10"
TEMPERATURE_VARIABLE = "t2m"

#: Window length (hours) -> feature-name suffix.
WINDOW_SUFFIXES = {24: "24h", 72: "72h", 168: "7d"}

FLAG_GOOD = "GOOD"
FLAG_PARTIAL_WINDOW = "PARTIAL_WINDOW"
FLAG_MISSING_DATA = "MISSING_DATA"
FLAG_NO_DATA = "NO_DATA"

DEFAULT_MINIMUM_VALID_FRACTION = 1.0

#: Meteorological wind direction: the compass bearing the wind blows FROM.
WIND_DIRECTION_CONVENTION = (
    "Meteorological convention: degrees clockwise from north indicating the "
    "direction the wind blows FROM. 0/360 = northerly (from the north), "
    "90 = easterly, 180 = southerly, 270 = westerly. Computed as "
    "(270 - degrees(atan2(v10, u10))) mod 360."
)


class AntecedentFeatureError(ValueError):
    """Raised when features cannot be extracted as requested."""


def _require_utc_hour(value: datetime, label: str = "event_time") -> pd.Timestamp:
    if not isinstance(value, datetime):
        raise AntecedentFeatureError(
            f"{label} must be a datetime, got {type(value).__name__}"
        )
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    elif value.utcoffset() != timedelta(0):
        raise AntecedentFeatureError(
            f"{label} must be UTC, got offset {value.utcoffset()}."
        )
    if value.minute or value.second or value.microsecond:
        raise AntecedentFeatureError(
            f"{label} must be hour-aligned; got {value.isoformat()}."
        )
    return pd.Timestamp(value).tz_localize(None)


def _window_sum(
    array: xr.DataArray,
    times: pd.DatetimeIndex,
    event: pd.Timestamp,
    hours: int,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Sum an interval-end labelled series over (event - hours, event].

    Returns ``(total, valid_fraction, expected_hours)``. NaN hours contribute
    nothing to the total and reduce the valid fraction — they are never read
    as zero rainfall.
    """
    window = (times > event - pd.Timedelta(hours=hours)) & (times <= event)
    selected = np.asarray(array.values, dtype="float64")[window]
    valid = np.isfinite(selected)

    total = np.where(valid, selected, 0.0).sum(axis=0)
    counted = valid.sum(axis=0)
    fraction = counted / float(hours) if hours else np.zeros_like(counted)
    total = np.where(counted > 0, total, np.nan)
    return total, fraction, int(window.sum())


def _at_time(
    array: xr.DataArray, times: pd.DatetimeIndex, moment: pd.Timestamp
) -> np.ndarray:
    matches = np.where(times == moment)[0]
    if matches.size == 0:
        raise AntecedentFeatureError(
            f"Timestamp {moment} is not present in the dataset "
            f"({times[0]} .. {times[-1]})."
        )
    return np.asarray(array.values, dtype="float64")[int(matches[0])]


def extract_antecedent_features(
    dataset: xr.Dataset,
    event_time: datetime,
    *,
    soil_moisture_offsets_hours: Sequence[int] = (24, 72),
    precipitation_windows_hours: Sequence[int] = (24, 72, 168),
    runoff_windows_hours: Sequence[int] = (24, 72, 168),
    state_window_hours: int = 6,
    minimum_valid_fraction: float = DEFAULT_MINIMUM_VALID_FRACTION,
    require_full_windows: bool = True,
) -> xr.Dataset:
    """Extract gridded pre-event predictors for any event timestamp.

    Args:
        dataset: Normalised ERA5-Land dataset on an hourly ``(time, lat, lon)``
            axis, already passed through ``normalize_era5_land_fluxes``.
        event_time: The event moment. UTC, hour-aligned, inside the dataset.
        soil_moisture_offsets_hours: Lags at which to sample soil moisture.
        precipitation_windows_hours: Trailing rainfall windows.
        runoff_windows_hours: Trailing runoff windows.
        state_window_hours: Trailing window for mean wind speed / temperature.
        minimum_valid_fraction: Fraction of a window that must carry data
            before the feature counts as good.
        require_full_windows: Refuse to run when the dataset does not cover
            the longest requested window before `event_time`.

    Returns:
        Dataset of ``(lat, lon)`` features plus per-feature
        ``*_valid_fraction`` and an overall ``quality_flag``.

    Raises:
        AntecedentFeatureError: on a non-UTC or unaligned event time, an event
            outside the dataset, missing required variables, or insufficient
            history when `require_full_windows` is set.
    """
    event = _require_utc_hour(event_time)

    if "time" not in dataset.coords and "time" not in dataset.dims:
        raise AntecedentFeatureError("Dataset has no 'time' coordinate.")
    times = pd.DatetimeIndex(np.atleast_1d(dataset["time"].values))
    if times.size == 0:
        raise AntecedentFeatureError("Dataset has no timestamps.")
    if event < times[0] or event > times[-1]:
        raise AntecedentFeatureError(
            f"event_time {event} lies outside the dataset range "
            f"{times[0]} .. {times[-1]}."
        )

    longest = max(
        [*precipitation_windows_hours, *runoff_windows_hours,
         *soil_moisture_offsets_hours, state_window_hours] or [0]
    )
    history_hours = int((event - times[0]).total_seconds() // 3600)
    if require_full_windows and history_hours < longest:
        raise AntecedentFeatureError(
            f"Only {history_hours} h of history before {event}, but the "
            f"longest requested window needs {longest} h. Extend the dataset "
            "or pass require_full_windows=False to accept partial windows."
        )

    features: dict[str, xr.DataArray] = {}
    fractions: dict[str, np.ndarray] = {}
    dims = ("lat", "lon")
    coords = {"lat": dataset["lat"], "lon": dataset["lon"]}

    def add(name: str, values: np.ndarray, units: str, description: str,
            fraction: np.ndarray | None = None) -> None:
        features[name] = xr.DataArray(
            values, dims=dims, coords=coords,
            attrs={"units": units, "long_name": description,
                   "missing_data_policy": "preserve_nan"},
        )
        if fraction is not None:
            fractions[name] = fraction
            features[f"{name}_valid_fraction"] = xr.DataArray(
                fraction, dims=dims, coords=coords,
                attrs={"units": "1",
                       "long_name": f"Valid data fraction for {name}"},
            )

    # --- antecedent soil moisture (instantaneous state) -----------------
    if SOIL_MOISTURE_VARIABLE in dataset.data_vars:
        shape = tuple(dataset[SOIL_MOISTURE_VARIABLE].shape[1:])
        for offset in soil_moisture_offsets_hours:
            moment = event - pd.Timedelta(hours=int(offset))
            if moment not in times:
                if require_full_windows:
                    raise AntecedentFeatureError(
                        f"Soil-moisture lag of {offset} h needs {moment}, "
                        f"which is outside the dataset ({times[0]} .. "
                        f"{times[-1]})."
                    )
                # Partial windows permitted: unknown lag is NaN, never a
                # substituted nearby value.
                logger.warning(
                    "Soil-moisture lag %s h (%s) outside range — NaN", offset,
                    moment,
                )
                values = np.full(shape, np.nan)
            else:
                values = _at_time(
                    dataset[SOIL_MOISTURE_VARIABLE], times, moment
                )
            fraction = np.isfinite(values).astype("float64")
            add(
                f"soil_moisture_t_minus_{int(offset)}h", values,
                str(dataset[SOIL_MOISTURE_VARIABLE].attrs.get(
                    "units", "m**3 m**-3")),
                f"Volumetric soil water layer 1 at event time minus {offset} h",
                fraction,
            )

    # --- trailing accumulation windows -----------------------------------
    accumulations = [
        (PRECIPITATION_VARIABLE, "precipitation_prior", precipitation_windows_hours),
        (SURFACE_RUNOFF_VARIABLE, "surface_runoff_prior", runoff_windows_hours),
        (SUBSURFACE_RUNOFF_VARIABLE, "subsurface_runoff_prior", runoff_windows_hours),
    ]
    for variable, prefix, windows in accumulations:
        if variable not in dataset.data_vars:
            logger.warning("%s absent — skipping %s features", variable, prefix)
            continue
        for hours in windows:
            suffix = WINDOW_SUFFIXES.get(int(hours), f"{int(hours)}h")
            total, fraction, _ = _window_sum(
                dataset[variable], times, event, int(hours)
            )
            add(
                f"{prefix}_{suffix}_mm", total, "mm",
                f"{prefix.replace('_', ' ')} total over the {hours} h before "
                "the event (interval-end labelling)",
                fraction,
            )

    # --- event-time state -------------------------------------------------
    has_u = U_WIND_VARIABLE in dataset.data_vars
    has_v = V_WIND_VARIABLE in dataset.data_vars
    if has_u:
        u_event = _at_time(dataset[U_WIND_VARIABLE], times, event)
        add("u10_event_time", u_event,
            str(dataset[U_WIND_VARIABLE].attrs.get("units", "m s**-1")),
            "10 m eastward wind component at event time",
            np.isfinite(u_event).astype("float64"))
    if has_v:
        v_event = _at_time(dataset[V_WIND_VARIABLE], times, event)
        add("v10_event_time", v_event,
            str(dataset[V_WIND_VARIABLE].attrs.get("units", "m s**-1")),
            "10 m northward wind component at event time",
            np.isfinite(v_event).astype("float64"))

    if has_u and has_v:
        speed = np.sqrt(u_event ** 2 + v_event ** 2)
        add("wind_speed_event_time", speed, "m s**-1",
            "10 m wind speed at event time = sqrt(u10^2 + v10^2)",
            np.isfinite(speed).astype("float64"))

        direction = (270.0 - np.degrees(np.arctan2(v_event, u_event))) % 360.0
        direction = np.where(np.isfinite(speed), direction, np.nan)
        features["wind_direction_event_time"] = xr.DataArray(
            direction, dims=dims, coords=coords,
            attrs={"units": "degrees", "convention": WIND_DIRECTION_CONVENTION,
                   "long_name": "10 m wind direction at event time"},
        )

    if TEMPERATURE_VARIABLE in dataset.data_vars:
        temperature = _at_time(dataset[TEMPERATURE_VARIABLE], times, event)
        add("temperature_2m_event_time", temperature,
            str(dataset[TEMPERATURE_VARIABLE].attrs.get("units", "K")),
            "2 m air temperature at event time",
            np.isfinite(temperature).astype("float64"))

    # --- trailing state means --------------------------------------------
    if has_u and has_v and state_window_hours > 0:
        window = (times > event - pd.Timedelta(hours=state_window_hours)) & \
                 (times <= event)
        u_series = np.asarray(dataset[U_WIND_VARIABLE].values,
                              dtype="float64")[window]
        v_series = np.asarray(dataset[V_WIND_VARIABLE].values,
                              dtype="float64")[window]
        speeds = np.sqrt(u_series ** 2 + v_series ** 2)
        valid = np.isfinite(speeds)
        counted = valid.sum(axis=0)
        mean_speed = np.where(
            counted > 0,
            np.where(valid, speeds, 0.0).sum(axis=0) / np.maximum(counted, 1),
            np.nan,
        )
        add("mean_wind_speed_prior_state_window", mean_speed, "m s**-1",
            f"Mean 10 m wind speed over the {state_window_hours} h before "
            "the event",
            counted / float(state_window_hours))

    if TEMPERATURE_VARIABLE in dataset.data_vars and state_window_hours > 0:
        window = (times > event - pd.Timedelta(hours=state_window_hours)) & \
                 (times <= event)
        series = np.asarray(dataset[TEMPERATURE_VARIABLE].values,
                            dtype="float64")[window]
        valid = np.isfinite(series)
        counted = valid.sum(axis=0)
        mean_temperature = np.where(
            counted > 0,
            np.where(valid, series, 0.0).sum(axis=0) / np.maximum(counted, 1),
            np.nan,
        )
        add("mean_temperature_prior_state_window", mean_temperature,
            str(dataset[TEMPERATURE_VARIABLE].attrs.get("units", "K")),
            f"Mean 2 m temperature over the {state_window_hours} h before "
            "the event",
            counted / float(state_window_hours))

    if not features:
        raise AntecedentFeatureError(
            "No usable variables found. Expected normalised ERA5-Land fields "
            f"such as {PRECIPITATION_VARIABLE!r} or {SOIL_MOISTURE_VARIABLE!r}."
        )

    # --- overall quality --------------------------------------------------
    stacked = np.stack(list(fractions.values())) if fractions else None
    if stacked is None:
        overall = np.ones(features[next(iter(features))].shape)
    else:
        overall = stacked.min(axis=0)

    # NO_DATA means the cell has nothing at all (e.g. a sea cell), not merely
    # that one long window could not be filled — that is PARTIAL_WINDOW.
    flags = np.full(overall.shape, FLAG_GOOD, dtype=object)
    if stacked is not None:
        any_missing = (stacked < 1.0).any(axis=0)
        nothing_usable = (stacked <= 0).all(axis=0)
        flags[any_missing] = FLAG_MISSING_DATA
        flags[overall < minimum_valid_fraction] = FLAG_PARTIAL_WINDOW
        flags[nothing_usable] = FLAG_NO_DATA
    else:
        flags[overall < minimum_valid_fraction] = FLAG_PARTIAL_WINDOW

    result = xr.Dataset(features)
    result["valid_data_fraction"] = xr.DataArray(
        overall, dims=dims, coords=coords,
        attrs={"units": "1",
               "long_name": "Minimum valid fraction across all features"},
    )
    result["quality_flag"] = xr.DataArray(
        flags.astype(str), dims=dims, coords=coords,
        attrs={"long_name": "Per-cell feature quality"},
    )

    result.attrs.update({
        "event_time_utc": event.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_product": dataset.attrs.get("source_product", SOURCE_PRODUCT),
        "temporal_semantics_mode": dataset.attrs.get(
            "temporal_semantics_mode", "unknown"),
        "temporal_semantics_evidence": dataset.attrs.get(
            "temporal_semantics_evidence", "not recorded"),
        "missing_data_policy": "preserve_nan; missing hours are never zero",
        "feature_window": (
            f"soil moisture offsets {list(soil_moisture_offsets_hours)} h; "
            f"precipitation {list(precipitation_windows_hours)} h; "
            f"runoff {list(runoff_windows_hours)} h; "
            f"state window {state_window_hours} h"
        ),
        "canonical_timezone": CANONICAL_TIMEZONE,
        "wind_direction_convention": WIND_DIRECTION_CONVENTION,
        "interpolation_performed": "no",
        "minimum_valid_fraction": float(minimum_valid_fraction),
        "history_hours_available": int(history_hours),
    })

    logger.info(
        "Extracted %d antecedent features for %s",
        len(result.data_vars), result.attrs["event_time_utc"],
    )
    return result


def antecedent_features_to_dataframe(
    dataset: xr.Dataset,
    event_id: str,
) -> pd.DataFrame:
    """Flatten gridded features to one row per cell, ready for Parquet."""
    if "lat" not in dataset.coords or "lon" not in dataset.coords:
        raise AntecedentFeatureError("Dataset needs lat/lon coordinates.")

    lat = np.asarray(dataset["lat"].values, dtype="float64")
    lon = np.asarray(dataset["lon"].values, dtype="float64")
    lat_grid, lon_grid = np.meshgrid(lat, lon, indexing="ij")

    frame = pd.DataFrame({
        "event_id": event_id,
        "event_time_utc": dataset.attrs.get("event_time_utc"),
        "lat": lat_grid.ravel(),
        "lon": lon_grid.ravel(),
    })
    for name in dataset.data_vars:
        values = np.asarray(dataset[name].values)
        if values.shape != lat_grid.shape:
            continue
        frame[str(name)] = values.ravel()

    ordered = ["event_id", "event_time_utc", "lat", "lon"]
    tail = [c for c in ("valid_data_fraction", "quality_flag")
            if c in frame.columns]
    middle = [c for c in frame.columns if c not in ordered + tail]
    return frame[ordered + middle + tail]


__all__ = [
    "AntecedentFeatureError",
    "WIND_DIRECTION_CONVENTION",
    "antecedent_features_to_dataframe",
    "extract_antecedent_features",
]
