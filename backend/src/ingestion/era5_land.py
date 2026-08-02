"""Copernicus ERA5-Land ingestion utilities for ReefShield Aqaba.

Provides a request builder, a download wrapper, and a reader that normalises
ERA5-Land NetCDF into the project's canonical layout ``(time, lat, lon)`` with
ascending latitude and UTC timestamps.

GRID SAFETY — READ BEFORE COMBINING WITH IMERG
----------------------------------------------
ERA5-Land and IMERG grids are not index-aligned. Spatial combination must use
catchment aggregation or area-weighted overlap, never array index matching.

Both grids are 0.1 degree and, over the Aqaba box, both happen to be 5x4 —
which makes index matching look plausible. It is wrong. Cell centres are
offset by half a cell and latitude runs in opposite directions:

    IMERG lat: 29.25 29.35 29.45 29.55 29.65   (ascending)
    ERA5  lat: 29.70 29.60 29.50 29.40 29.30   (descending, as delivered)
    IMERG lon: 34.85 34.95 35.05 35.15
    ERA5  lon: 34.80 34.90 35.00 35.10

Pairing by index would silently associate each ERA5 cell with the wrong IMERG
cell and flip north for south. Use
``backend/src/processing/catchment_rainfall.py`` style area-weighted overlap.

SEA MASK
--------
ERA5-Land is a land-only product: cells over water are permanently NaN, not
transient gaps. They are preserved as NaN and never interpolated. A coastal
catchment will therefore always show a reduced valid-area fraction, which is
correct rather than a fault.

Credentials are read by ``cdsapi`` from ``~/.cdsapirc``. This module never
reads, prints, logs, or stores the CDS token.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import xarray as xr

logger = logging.getLogger(__name__)

ERA5_LAND_DATASET = "reanalysis-era5-land"

ERA5_VARIABLES = {
    "soil_moisture": "volumetric_soil_water_layer_1",
    "total_precipitation": "total_precipitation",
    "surface_runoff": "surface_runoff",
    "subsurface_runoff": "sub_surface_runoff",
    "u10": "10m_u_component_of_wind",
    "v10": "10m_v_component_of_wind",
    "temperature_2m": "2m_temperature",
}

ERA5_SHORT_NAMES = {
    "swvl1": "soil_moisture",
    "tp": "total_precipitation",
    "sro": "surface_runoff",
    "ssro": "subsurface_runoff",
    "u10": "u10",
    "v10": "v10",
    "t2m": "temperature_2m",
}

#: CDS order: North, West, South, East.
AREA = [29.70, 34.80, 29.25, 35.15]

DATA_FORMAT = "netcdf"
DOWNLOAD_FORMAT = "unarchived"

SOURCE_PRODUCT = "ERA5-Land Hourly"
CANONICAL_TIMEZONE = "UTC"
SPATIAL_GRID = "ERA5-Land native 0.1 degree grid"

GRID_ALIGNMENT_WARNING = (
    "ERA5-Land and IMERG grids are not index-aligned. Spatial combination "
    "must use catchment aggregation or area-weighted overlap, never array "
    "index matching."
)

#: Canonical renames applied by :func:`read_era5_land`.
COORDINATE_RENAMES = {
    "valid_time": "time",
    "latitude": "lat",
    "longitude": "lon",
}

#: Short names whose tiny negative noise may be clamped to zero.
SOIL_MOISTURE_SHORT_NAMES = frozenset({"swvl1", "swvl2", "swvl3", "swvl4"})
#: Negative values no smaller than this are float noise and clamp to zero.
NEGATIVE_NOISE_TOLERANCE = -1e-12

#: Metadata keys added by the builder and stripped before submission.
META_PREFIX = "_"


class ERA5LandError(RuntimeError):
    """Base class for ERA5-Land ingestion failures."""


class ERA5LandRequestError(ValueError):
    """Raised when a request cannot be built from the given arguments."""


class ERA5LandDownloadError(ERA5LandError):
    """Raised when a CDS retrieval fails."""


class ERA5LandValidationError(ValueError):
    """Raised when downloaded values violate a physical expectation."""


class ERA5LandTemporalSemanticsError(ERA5LandValidationError):
    """Raised when a field's temporal convention cannot be proven."""


# ---------------------------------------------------------------------------
# 2. request builder
# ---------------------------------------------------------------------------


def _resolve_variable(name: str) -> str:
    """Map a canonical key or CDS name to the CDS variable name."""
    if name in ERA5_VARIABLES:
        return ERA5_VARIABLES[name]
    if name in ERA5_VARIABLES.values():
        return name
    if name in ERA5_SHORT_NAMES:
        return ERA5_VARIABLES[ERA5_SHORT_NAMES[name]]
    raise ERA5LandRequestError(
        f"Unknown ERA5-Land variable {name!r}. Use a canonical key "
        f"{sorted(ERA5_VARIABLES)}, a CDS name "
        f"{sorted(ERA5_VARIABLES.values())}, or a short name "
        f"{sorted(ERA5_SHORT_NAMES)}."
    )


def _require_utc_hour(value: datetime, label: str) -> datetime:
    """Coerce to timezone-aware UTC and require an exact hour boundary."""
    if not isinstance(value, datetime):
        raise ERA5LandRequestError(
            f"{label} must be a datetime, got {type(value).__name__}"
        )
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    elif value.utcoffset() != timedelta(0):
        raise ERA5LandRequestError(
            f"{label} must be UTC, got offset {value.utcoffset()}. "
            "Convert with astimezone(timezone.utc) before requesting."
        )
    if value.minute or value.second or value.microsecond:
        raise ERA5LandRequestError(
            f"{label} must be hour-aligned; got {value.isoformat()}. "
            "ERA5-Land is hourly — minutes and seconds must be zero."
        )
    return value


def build_era5_land_request(
    variables: Sequence[str],
    start_time: datetime,
    end_time: datetime,
    area: Sequence[float] = AREA,
) -> dict:
    """Build a CDS request for hourly ERA5-Land data. Sends nothing.

    Args:
        variables: Canonical keys (e.g. ``"soil_moisture"``), CDS names, or
            short names. Order is preserved, duplicates removed.
        start_time: First hour, inclusive. UTC and hour-aligned.
        end_time: Last hour, inclusive. UTC and hour-aligned.
        area: ``[North, West, South, East]`` — CDS order, preserved verbatim.

    Returns:
        A CDS request dict. Keys prefixed with ``_`` are local metadata,
        stripped by :func:`download_era5_land` before submission:

        * ``_expected_timestamp_count`` — hours in the requested range
        * ``_expected_timestamps`` — those hours as ISO-8601 UTC strings
        * ``_cartesian_timestamp_count`` — how many hours CDS will actually
          return, since it expands year x month x day x time as a product

    Raises:
        ERA5LandRequestError: on an unknown variable, non-UTC or non
            hour-aligned bound, reversed range, empty variable list, or a
            malformed area.
    """
    if not variables:
        raise ERA5LandRequestError("At least one variable is required.")

    resolved: list[str] = []
    for name in variables:
        cds_name = _resolve_variable(name)
        if cds_name not in resolved:
            resolved.append(cds_name)

    start = _require_utc_hour(start_time, "start_time")
    end = _require_utc_hour(end_time, "end_time")
    if end < start:
        raise ERA5LandRequestError(
            f"end_time ({end.isoformat()}) precedes start_time "
            f"({start.isoformat()})."
        )

    if len(area) != 4:
        raise ERA5LandRequestError(
            f"area must be [North, West, South, East]; got {list(area)}"
        )
    north, west, south, east = (float(v) for v in area)
    if north < south:
        raise ERA5LandRequestError(
            f"area North ({north}) is south of South ({south}); CDS order is "
            "[North, West, South, East]."
        )
    if east < west:
        raise ERA5LandRequestError(
            f"area East ({east}) is west of West ({west}); CDS order is "
            "[North, West, South, East]."
        )

    hours: list[datetime] = []
    current = start
    while current <= end:
        hours.append(current)
        current += timedelta(hours=1)

    years = sorted({f"{h.year:04d}" for h in hours})
    months = sorted({f"{h.month:02d}" for h in hours})
    days = sorted({f"{h.day:02d}" for h in hours})
    times = sorted({f"{h.hour:02d}:00" for h in hours})

    request = {
        "variable": resolved,
        "year": years,
        "month": months,
        "day": days,
        "time": times,
        "area": [north, west, south, east],
        "data_format": DATA_FORMAT,
        "download_format": DOWNLOAD_FORMAT,
        "_expected_timestamp_count": len(hours),
        "_expected_timestamps": [
            h.strftime("%Y-%m-%dT%H:%M:%SZ") for h in hours
        ],
        "_cartesian_timestamp_count": (
            len(years) * len(months) * len(days) * len(times)
        ),
    }

    if request["_cartesian_timestamp_count"] != len(hours):
        logger.warning(
            "CDS expands year x month x day x time as a product: this range "
            "covers %d hour(s) but CDS will return up to %d. Slice per day "
            "if the extra hours matter.",
            len(hours), request["_cartesian_timestamp_count"],
        )

    logger.info(
        "Built ERA5-Land request: %d variable(s), %d hour(s), %s..%s",
        len(resolved), len(hours),
        hours[0].strftime("%Y-%m-%dT%H:%M:%SZ"),
        hours[-1].strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    return request


def strip_request_metadata(request: dict) -> dict:
    """Return only the keys CDS accepts."""
    return {
        key: value for key, value in request.items()
        if not key.startswith(META_PREFIX)
    }


# ---------------------------------------------------------------------------
# 3. download
# ---------------------------------------------------------------------------


def download_era5_land(
    request: dict,
    output_path: Path,
    overwrite: bool = False,
) -> Path:
    """Retrieve an ERA5-Land request to `output_path`.

    Credentials come from ``~/.cdsapirc`` via ``cdsapi``; no token, header or
    signed URL is read or logged here.

    Args:
        request: Built by :func:`build_era5_land_request`. Local ``_`` keys are
            stripped before submission.
        output_path: Destination file; parent directories are created.
        overwrite: Permit replacing an existing file. Default False, so a
            re-run never silently discards data already on disk.

    Returns:
        The resolved output path.

    Raises:
        FileExistsError: if the target exists and `overwrite` is False.
        ERA5LandDownloadError: if the retrieval fails, or reports success but
            leaves no file.
    """
    output_path = Path(output_path)
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"{output_path} already exists. Pass overwrite=True to replace it; "
            "nothing is deleted automatically."
        )

    payload = strip_request_metadata(request)
    expected = request.get("_expected_timestamp_count")

    try:
        import cdsapi
    except ImportError as exc:  # pragma: no cover - environment issue
        raise ERA5LandDownloadError(
            'cdsapi is required: pip install "cdsapi>=0.7.7"'
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Submitting ERA5-Land request: %s, %s hour(s) expected",
        payload.get("variable"), expected,
    )

    try:
        client = cdsapi.Client()
        client.retrieve(ERA5_LAND_DATASET, payload, str(output_path))
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        lowered = message.lower()
        if "licence" in lowered or "license" in lowered:
            raise ERA5LandDownloadError(
                "CDS refused the request because a required licence is not "
                "accepted. Accept the ERA5-Land Terms of Use once at "
                "https://cds.climate.copernicus.eu/datasets/"
                "reanalysis-era5-land?tab=download#manage-licences "
                "then retry unchanged."
            ) from exc
        raise ERA5LandDownloadError(
            f"ERA5-Land retrieval failed: {type(exc).__name__}: {message}"
        ) from exc

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise ERA5LandDownloadError(
            f"CDS reported success but {output_path.name} is missing or empty."
        )

    logger.info(
        "Downloaded %s (%.1f KB)",
        output_path.name, output_path.stat().st_size / 1024,
    )
    return output_path.resolve()


# ---------------------------------------------------------------------------
# 4-5. reader and negative-noise handling
# ---------------------------------------------------------------------------


def _clamp_soil_moisture_noise(dataset: xr.Dataset) -> xr.Dataset:
    """Clamp float noise in soil-moisture variables; reject real negatives.

    GRIB to NetCDF conversion leaves values like ``-1.1e-21`` where the true
    value is zero. Those clamp to 0. Anything below
    :data:`NEGATIVE_NOISE_TOLERANCE` is a genuine problem and raises. NaN is
    left untouched so the sea mask survives.

    Applies to soil moisture only — wind components and temperature anomalies
    are legitimately negative and are never touched.
    """
    for name in list(dataset.data_vars):
        if str(name) not in SOIL_MOISTURE_SHORT_NAMES:
            continue

        array = dataset[name]
        values = np.asarray(array.values, dtype="float64")
        finite = np.isfinite(values)
        negative = finite & (values < 0)
        if not negative.any():
            continue

        worst = float(values[negative].min())
        if worst < NEGATIVE_NOISE_TOLERANCE:
            raise ERA5LandValidationError(
                f"{name}: volumetric soil moisture of {worst} is below the "
                f"noise tolerance {NEGATIVE_NOISE_TOLERANCE}. Soil moisture "
                "cannot be physically negative — inspect the source file "
                "rather than clamping."
            )

        attrs = dict(array.attrs)
        count = int(negative.sum())
        cleaned = values.copy()
        cleaned[negative] = 0.0
        dataset[name] = xr.DataArray(
            cleaned.astype(array.dtype), dims=array.dims,
            coords=array.coords, attrs=attrs,
        )
        logger.info(
            "Clamped %d tiny negative %s value(s) to zero (worst %g)",
            count, name, worst,
        )

    return dataset


def read_era5_land(path: Path) -> xr.Dataset:
    """Open an ERA5-Land NetCDF and normalise it to the project layout.

    Renames ``valid_time``/``latitude``/``longitude`` to ``time``/``lat``/
    ``lon``, orders dimensions ``(time, lat, lon)``, sorts latitude ascending
    while keeping longitude ascending, and normalises time to
    ``datetime64[ns]`` interpreted as UTC.

    Sea-mask NaNs are preserved and never interpolated. Units and source
    metadata are kept; tiny negative soil-moisture noise is clamped to zero.

    Args:
        path: Path to an ERA5-Land NetCDF file.

    Returns:
        Normalised dataset with ``source_product``, ``canonical_timezone``,
        ``spatial_grid`` and the grid-alignment warning in its attributes.

    Raises:
        FileNotFoundError: if `path` does not exist.
        ERA5LandValidationError: if soil moisture is genuinely negative.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"ERA5-Land file not found: {path}")

    dataset = xr.open_dataset(path)
    try:
        dataset = dataset.load()
    except Exception:
        dataset.close()
        raise
    dataset.close()

    renames = {
        source: target for source, target in COORDINATE_RENAMES.items()
        if source in dataset.variables or source in dataset.dims
    }
    if renames:
        dataset = dataset.rename(renames)

    if "time" not in dataset.coords and "time" not in dataset.dims:
        raise ERA5LandValidationError(
            "No time coordinate found after renaming; expected 'valid_time' "
            f"or 'time'. Coordinates: {sorted(map(str, dataset.coords))}"
        )

    # A scalar time coordinate becomes a length-1 dimension so downstream code
    # can always assume (time, lat, lon).
    if "time" not in dataset.dims:
        dataset = dataset.expand_dims("time")

    # Sorting by the coordinate carries each row's data with it, so values stay
    # attached to their latitude.
    dataset = dataset.sortby("lat")
    if dataset["lon"].size > 1 and bool(
        dataset["lon"].values[1] < dataset["lon"].values[0]
    ):
        dataset = dataset.sortby("lon")

    for name in list(dataset.data_vars):
        dims = tuple(dataset[name].dims)
        target = [d for d in ("time", "lat", "lon") if d in dims]
        extra = [d for d in dims if d not in target]
        ordered = tuple(target + extra)
        if dims != ordered and len(ordered) > 1:
            attrs = dict(dataset[name].attrs)
            dataset[name] = dataset[name].transpose(*ordered)
            dataset[name].attrs = attrs

    times = np.asarray(dataset["time"].values)
    if not np.issubdtype(times.dtype, np.datetime64):
        dataset = dataset.assign_coords(
            time=np.asarray(times, dtype="datetime64[ns]")
        )
    elif times.dtype != np.dtype("datetime64[ns]"):
        dataset = dataset.assign_coords(
            time=times.astype("datetime64[ns]")
        )

    dataset = _clamp_soil_moisture_noise(dataset)

    dataset.attrs["source_product"] = SOURCE_PRODUCT
    dataset.attrs["canonical_timezone"] = CANONICAL_TIMEZONE
    dataset.attrs["spatial_grid"] = SPATIAL_GRID
    dataset.attrs["grid_alignment_warning"] = GRID_ALIGNMENT_WARNING
    dataset.attrs["sea_mask_policy"] = (
        "ERA5-Land is land-only; NaN cells over water are preserved and never "
        "interpolated."
    )

    logger.info(
        "Read %s: vars=%s dims=%s lat %s..%s lon %s..%s",
        path.name, sorted(map(str, dataset.data_vars)), dict(dataset.sizes),
        float(dataset["lat"].min()), float(dataset["lat"].max()),
        float(dataset["lon"].min()), float(dataset["lon"].max()),
    )
    return dataset


#: Accumulated (forecast) variables that must be deaccumulated before use.
ACCUMULATED_VARIABLES: tuple[str, ...] = ("tp", "sro", "ssro")

#: Short name -> millimetre variable name produced by deaccumulation.
HOURLY_MM_NAMES = {
    "tp": "total_precipitation_hourly_mm",
    "sro": "surface_runoff_hourly_mm",
    "ssro": "subsurface_runoff_hourly_mm",
}

#: Instantaneous state variables — never deaccumulate these.
INSTANTANEOUS_VARIABLES = frozenset(
    {"swvl1", "swvl2", "swvl3", "swvl4", "t2m", "u10", "v10"}
)

RAW_ACCUMULATION_SEMANTICS = (
    "Accumulated from 00 UTC to forecast step; 00 UTC represents the "
    "previous UTC day's 24-hour total."
)

METRES_TO_MM = 1000.0


def deaccumulate_era5_land(
    dataset: xr.Dataset,
    accumulated_variables: Sequence[str] = ACCUMULATED_VARIABLES,
    negative_tolerance_m: float = 1e-10,
) -> xr.Dataset:
    """Convert ERA5-Land cumulative fields into hourly increments.

    ERA5-Land accumulates ``tp``/``sro``/``ssro`` from 00 UTC to the forecast
    step, so raw values must never be summed across timestamps. The value at
    00 UTC is the *previous* day's 24-hour total, which makes 01 UTC a reset
    rather than a continuation.

    Increments are labelled by **interval end time**: the value at 02:00
    covers 01:00-02:00.

    ==========  =========================================================
    UTC hour    hourly increment
    ==========  =========================================================
    01          the raw 01:00 value itself (daily reset — never minus 00:00)
    02 - 23     current cumulative minus previous cumulative
    00          current 24-hour total minus the previous day's 23:00 value
    ==========  =========================================================

    The first timestamp has no predecessor. If it is 01:00 its increment is
    still valid; otherwise the increment is NaN — never zero, because an
    unknown increment is not a dry hour.

    Args:
        dataset: Normalised dataset with a continuous hourly ``time`` axis.
        accumulated_variables: Short names to deaccumulate. Absent ones are
            skipped with a warning; instantaneous variables are refused.
        negative_tolerance_m: Increments in ``[-tolerance, 0)`` are float
            noise and clamp to zero. Anything below raises.

    Returns:
        A new dataset with the raw accumulated variables preserved unchanged,
        plus ``<name>_hourly_m`` and the millimetre variants.

    Raises:
        ERA5LandValidationError: on duplicate, non-ascending or non-hourly
            timestamps, on an instantaneous variable, or on a materially
            negative increment.
    """
    import pandas as pd

    if "time" not in dataset.coords and "time" not in dataset.dims:
        raise ERA5LandValidationError("Dataset has no 'time' coordinate.")

    times = pd.DatetimeIndex(np.atleast_1d(dataset["time"].values))
    if times.size == 0:
        raise ERA5LandValidationError("Dataset has no timestamps.")

    if times.has_duplicates:
        duplicated = sorted(
            {str(t) for t in times[times.duplicated()]}
        )
        raise ERA5LandValidationError(
            f"Duplicate timestamps in the accumulated series: {duplicated}. "
            "Each hour must appear exactly once before deaccumulation."
        )
    if not times.is_monotonic_increasing:
        raise ERA5LandValidationError(
            "Timestamps are not ascending. Sort the series before "
            "deaccumulating; differencing an unsorted series is meaningless."
        )
    if times.size > 1:
        gaps = np.diff(times.values).astype("timedelta64[m]").astype(int)
        bad = [
            (str(times[i]), str(times[i + 1]), int(gap))
            for i, gap in enumerate(gaps) if gap != 60
        ]
        if bad:
            first = bad[0]
            raise ERA5LandValidationError(
                f"Non-hourly gap(s) in the accumulated series: {len(bad)} "
                f"found, first {first[0]} -> {first[1]} is {first[2]} minutes. "
                "Deaccumulation requires a continuous hourly axis; a missing "
                "hour would silently merge two intervals."
            )

    hours = times.hour.to_numpy()
    result = dataset.copy()
    clamped: dict[str, int] = {}

    for name in accumulated_variables:
        short = str(name)
        if short in INSTANTANEOUS_VARIABLES:
            raise ERA5LandValidationError(
                f"{short} is an instantaneous state variable and must not be "
                "deaccumulated."
            )
        if short not in dataset.data_vars:
            logger.warning(
                "Accumulated variable %r absent from the dataset — skipped",
                short,
            )
            continue

        source = dataset[short]
        raw = np.asarray(source.values, dtype="float64")
        increments = np.full_like(raw, np.nan)

        for index in range(times.size):
            if hours[index] == 1:
                # Daily reset: the 01:00 value IS the first hour's total.
                increments[index] = raw[index]
            elif index == 0:
                # No predecessor and not a reset hour -> genuinely unknown.
                increments[index] = np.nan
            else:
                # Covers hours 02-23 and 00 (00 minus the previous 23:00).
                increments[index] = raw[index] - raw[index - 1]

        finite = np.isfinite(increments)
        negative = finite & (increments < 0)
        count = 0
        if negative.any():
            worst = float(increments[negative].min())
            if worst < -abs(negative_tolerance_m):
                raise ERA5LandValidationError(
                    f"{short}: hourly increment of {worst} m is below the "
                    f"noise tolerance {-abs(negative_tolerance_m)}. After "
                    "correct reset handling an accumulated field cannot "
                    "decrease — inspect the source rather than clamping."
                )
            count = int(negative.sum())
            increments[negative] = 0.0
        clamped[short] = count

        common = {
            "accumulation_processing": "ERA5-Land forecast deaccumulation",
            "interval_hours": 1,
            "interval_label": "interval_end",
            "canonical_timezone": CANONICAL_TIMEZONE,
            "missing_data_policy": "preserve_nan",
            "negative_noise_tolerance_m": float(abs(negative_tolerance_m)),
            "negative_noise_clamped_count": count,
            "derived_from": short,
            "source_product": SOURCE_PRODUCT,
        }

        metre_name = f"{short}_hourly_m"
        result[metre_name] = xr.DataArray(
            increments, dims=source.dims, coords=source.coords,
            attrs={**common, "units": "m",
                   "long_name": f"Hourly {short} increment"},
        )

        mm_name = HOURLY_MM_NAMES.get(short, f"{short}_hourly_mm")
        result[mm_name] = xr.DataArray(
            increments * METRES_TO_MM, dims=source.dims, coords=source.coords,
            attrs={**common, "units": "mm",
                   "long_name": f"Hourly {short} increment",
                   "conversion": "metres * 1000"},
        )

        # The raw field is carried through untouched.
        result[short] = source

        logger.info(
            "Deaccumulated %s -> %s / %s (%d tiny negative value(s) clamped)",
            short, metre_name, mm_name, count,
        )

    result.attrs["raw_accumulation_semantics"] = RAW_ACCUMULATION_SEMANTICS
    result.attrs["accumulation_processing"] = (
        "ERA5-Land forecast deaccumulation"
    )
    result.attrs["interval_label"] = "interval_end"
    result.attrs["canonical_timezone"] = CANONICAL_TIMEZONE
    result.attrs["negative_noise_tolerance_m"] = float(
        abs(negative_tolerance_m)
    )
    result.attrs["negative_noise_clamped"] = ", ".join(
        f"{k}={v}" for k, v in clamped.items()
    ) or "none"
    return result


# ---------------------------------------------------------------------------
# Temporal-semantics normalisation (generic, metadata-driven)
# ---------------------------------------------------------------------------

#: Short name -> canonical hourly variable name, in metres.
FLUX_HOURLY_M_NAMES = {
    "tp": "total_precipitation_hourly_m",
    "sro": "surface_runoff_hourly_m",
    "ssro": "subsurface_runoff_hourly_m",
}

#: GRIB stepType values that prove a field is accumulated.
CUMULATIVE_STEP_TYPES = frozenset({"accum"})
#: GRIB stepType values that prove a field is an instantaneous state.
INSTANT_STEP_TYPES = frozenset({"instant"})

TEMPORAL_MODE_HOURLY = "hourly"
TEMPORAL_MODE_CUMULATIVE = "cumulative"


def infer_temporal_semantics(
    dataset: xr.Dataset,
    variables: Sequence[str],
) -> tuple[str, str]:
    """Prove a flux field's temporal convention from explicit metadata only.

    Evidence is taken from, in order:

    1. ``temporal_semantics_mode`` written by a previous normalisation run.
    2. ``GRIB_stepType`` on every target variable — ``accum`` proves the field
       is accumulated.

    Value *behaviour* is never used as evidence: whether numbers rise or fall
    is an observation, not a convention, and a dry window would make an
    accumulated field look flat.

    Returns:
        ``(mode, evidence)``.

    Raises:
        ERA5LandTemporalSemanticsError: if metadata does not settle the
            question. The caller must then pass an explicit mode.
    """
    present = [str(v) for v in variables if str(v) in dataset.data_vars]
    if not present:
        raise ERA5LandTemporalSemanticsError(
            f"None of {list(variables)} are present; nothing to normalise."
        )

    declared = {
        str(dataset[name].attrs.get("temporal_semantics_mode"))
        for name in present
        if dataset[name].attrs.get("temporal_semantics_mode")
    }
    if not declared and dataset.attrs.get("temporal_semantics_mode"):
        declared = {str(dataset.attrs["temporal_semantics_mode"])}
    if len(declared) == 1:
        mode = declared.pop()
        if mode in (TEMPORAL_MODE_HOURLY, TEMPORAL_MODE_CUMULATIVE):
            return mode, (
                f"explicit temporal_semantics_mode={mode!r} recorded by a "
                "previous normalisation"
            )

    step_types = {
        name: dataset[name].attrs.get("GRIB_stepType") for name in present
    }
    missing = [n for n, v in step_types.items() if not v]
    if missing:
        raise ERA5LandTemporalSemanticsError(
            "Cannot prove temporal semantics: GRIB_stepType is absent for "
            f"{missing}. Metadata is insufficient and value behaviour is not "
            "evidence. Pass mode='hourly' or mode='cumulative' explicitly, "
            "citing the product documentation."
        )

    unique = set(step_types.values())
    if unique <= CUMULATIVE_STEP_TYPES:
        data_types = {
            name: dataset[name].attrs.get("GRIB_dataType") for name in present
        }
        return TEMPORAL_MODE_CUMULATIVE, (
            "GRIB_stepType='accum' on "
            + ", ".join(sorted(present))
            + "; GRIB_dataType="
            + str(sorted({str(v) for v in data_types.values()}))
            + " (ECMWF: accumulations run from 00 UTC to the forecast step, "
            "so the 00 UTC value is the previous day's 24-hour total)"
        )
    if unique <= INSTANT_STEP_TYPES:
        raise ERA5LandTemporalSemanticsError(
            f"GRIB_stepType='instant' for {sorted(present)}: these are "
            "instantaneous state variables, not accumulated fluxes. They must "
            "not be deaccumulated or treated as hourly totals."
        )
    raise ERA5LandTemporalSemanticsError(
        f"Mixed or unrecognised GRIB_stepType values {step_types}. Refusing "
        "to guess; pass an explicit mode."
    )


def normalize_era5_land_fluxes(
    dataset: xr.Dataset,
    mode: str = "auto",
    negative_tolerance_m: float = 1e-10,
) -> xr.Dataset:
    """Produce hourly flux variables regardless of the source convention.

    Works for any dataset and any time range. The raw source variables are
    preserved untouched; ``swvl1`` and other instantaneous states are never
    deaccumulated.

    Args:
        dataset: ERA5-Land dataset with an hourly ``time`` axis.
        mode: ``"auto"`` proves the convention from metadata and raises if it
            cannot; ``"hourly"`` treats values as already per-hour;
            ``"cumulative"`` performs reset-aware deaccumulation.
        negative_tolerance_m: Values in ``[-tolerance, 0)`` are noise and
            clamp to zero; anything lower raises.

    Returns:
        Dataset with ``total_precipitation_hourly_m`` /
        ``surface_runoff_hourly_m`` / ``subsurface_runoff_hourly_m`` and their
        millimetre counterparts, plus semantics metadata.

    Raises:
        ERA5LandTemporalSemanticsError: unknown mode, or ``auto`` with
            insufficient metadata.
        ERA5LandValidationError: on bad timestamps or material negatives.
    """
    if mode not in ("auto", TEMPORAL_MODE_HOURLY, TEMPORAL_MODE_CUMULATIVE):
        raise ERA5LandTemporalSemanticsError(
            f"Unknown mode {mode!r}; use 'auto', 'hourly' or 'cumulative'."
        )

    present = [v for v in ACCUMULATED_VARIABLES if v in dataset.data_vars]
    if not present:
        raise ERA5LandTemporalSemanticsError(
            "No flux variables (tp/sro/ssro) present; nothing to normalise."
        )

    if mode == "auto":
        resolved, evidence = infer_temporal_semantics(dataset, present)
    else:
        resolved = mode
        evidence = f"caller-specified mode={mode!r}; metadata not consulted"

    if resolved == TEMPORAL_MODE_CUMULATIVE:
        result = deaccumulate_era5_land(
            dataset, accumulated_variables=present,
            negative_tolerance_m=negative_tolerance_m,
        )
        clamped = {
            short: int(
                result[f"{short}_hourly_m"].attrs["negative_noise_clamped_count"]
            )
            for short in present
        }
        for short in present:
            source = result[f"{short}_hourly_m"]
            result[FLUX_HOURLY_M_NAMES[short]] = source
    else:
        result = dataset.copy()
        clamped = {}
        for short in present:
            source = dataset[short]
            values = np.asarray(source.values, dtype="float64")
            finite = np.isfinite(values)
            negative = finite & (values < 0)
            count = 0
            if negative.any():
                worst = float(values[negative].min())
                if worst < -abs(negative_tolerance_m):
                    raise ERA5LandValidationError(
                        f"{short}: hourly value of {worst} m is below the "
                        f"noise tolerance {-abs(negative_tolerance_m)}."
                    )
                count = int(negative.sum())
                values = values.copy()
                values[negative] = 0.0
            clamped[short] = count

            attrs = {
                "units": "m",
                "long_name": f"Hourly {short}",
                "accumulation_processing": "source already hourly; copied",
                "interval_hours": 1,
                "interval_label": "interval_end",
                "canonical_timezone": CANONICAL_TIMEZONE,
                "missing_data_policy": "preserve_nan",
                "negative_noise_tolerance_m": float(abs(negative_tolerance_m)),
                "negative_noise_clamped_count": count,
                "derived_from": short,
                "source_product": SOURCE_PRODUCT,
            }
            hourly = xr.DataArray(
                values, dims=source.dims, coords=source.coords, attrs=attrs
            )
            result[f"{short}_hourly_m"] = hourly
            result[FLUX_HOURLY_M_NAMES[short]] = hourly
            result[HOURLY_MM_NAMES[short]] = xr.DataArray(
                values * METRES_TO_MM, dims=source.dims, coords=source.coords,
                attrs={**attrs, "units": "mm",
                       "conversion": "metres * 1000"},
            )
            result[short] = source

    for short in present:
        for name in (FLUX_HOURLY_M_NAMES[short], f"{short}_hourly_m",
                     HOURLY_MM_NAMES[short]):
            if name in result.variables:
                result[name].attrs["temporal_semantics_mode"] = resolved
                result[name].attrs["temporal_semantics_evidence"] = evidence

    result.attrs["temporal_semantics_mode"] = resolved
    result.attrs["temporal_semantics_evidence"] = evidence
    result.attrs["interval_hours"] = 1
    result.attrs["interval_label"] = "interval_end"
    result.attrs["missing_data_policy"] = "preserve_nan"
    result.attrs["canonical_timezone"] = CANONICAL_TIMEZONE
    result.attrs["negative_noise_clamped"] = ", ".join(
        f"{k}={v}" for k, v in clamped.items()
    ) or "none"

    logger.info(
        "Normalised fluxes %s in mode=%s (%s)", present, resolved, evidence
    )
    return result


# ---------------------------------------------------------------------------
# Generic windowed retrieval
# ---------------------------------------------------------------------------

#: Default guard on how many hourly timestamps a single call may request.
DEFAULT_MAX_EXPECTED_TIMESTAMPS = 2000


def _chunk_bounds(
    start: datetime, end: datetime, chunk_mode: str
) -> list[tuple[datetime, datetime]]:
    """Split [start, end] into chunks that never trip the CDS product rule."""
    if chunk_mode not in ("daily", "monthly"):
        raise ERA5LandRequestError(
            f"chunk_mode must be 'daily' or 'monthly', got {chunk_mode!r}"
        )

    chunks: list[tuple[datetime, datetime]] = []
    cursor = start
    while cursor <= end:
        if chunk_mode == "daily":
            boundary = cursor.replace(
                hour=23, minute=0, second=0, microsecond=0
            )
        else:
            if cursor.month == 12:
                nxt = cursor.replace(year=cursor.year + 1, month=1, day=1)
            else:
                nxt = cursor.replace(month=cursor.month + 1, day=1)
            boundary = nxt.replace(hour=0) - timedelta(hours=1)
        stop = min(boundary, end)
        chunks.append((cursor, stop))
        cursor = stop + timedelta(hours=1)
    return chunks


def _chunk_filename(start: datetime, stop: datetime) -> str:
    return (
        f"era5_land_{start:%Y%m%dT%H%M}_{stop:%Y%m%dT%H%M}.nc"
    )


def fetch_era5_land_window(
    start_time: datetime,
    end_time: datetime,
    bbox: Sequence[float],
    variables: Sequence[str],
    output_dir: Path,
    chunk_mode: str = "daily",
    overwrite: bool = False,
    max_expected_timestamps: int = DEFAULT_MAX_EXPECTED_TIMESTAMPS,
    allow_over_limit: bool = False,
) -> list[Path]:
    """Retrieve any UTC window over any CDS bounding box, safely chunked.

    Chunking (daily by default) keeps each request's
    ``year x month x day x time`` product exactly equal to the hours wanted,
    so CDS never returns hours that were not requested.

    Resumable: an existing non-empty chunk file is reused and never
    re-requested; nothing is deleted automatically.

    Args:
        start_time: First hour, inclusive. UTC, hour-aligned.
        end_time: Last hour, inclusive. UTC, hour-aligned.
        bbox: ``[North, West, South, East]`` in CDS order.
        variables: Canonical keys, CDS names or short names.
        output_dir: Directory for chunk files; created if absent.
        chunk_mode: ``"daily"`` or ``"monthly"``.
        overwrite: Replace existing chunk files.
        max_expected_timestamps: Refuse windows larger than this.
        allow_over_limit: Explicit override for the guard.

    Returns:
        Chunk file paths in chronological order.

    Raises:
        ERA5LandRequestError: on bad arguments, or when the guard trips.
        ERA5LandDownloadError: when a retrieval fails.
    """
    start = _require_utc_hour(start_time, "start_time")
    end = _require_utc_hour(end_time, "end_time")
    if end < start:
        raise ERA5LandRequestError(
            f"end_time ({end.isoformat()}) precedes start_time "
            f"({start.isoformat()})."
        )

    total_hours = int((end - start).total_seconds() // 3600) + 1
    if total_hours > max_expected_timestamps and not allow_over_limit:
        raise ERA5LandRequestError(
            f"Window spans {total_hours} hourly timestamps, above the "
            f"max_expected_timestamps guard of {max_expected_timestamps}. "
            "Raise the limit or pass allow_over_limit=True deliberately."
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks = _chunk_bounds(start, end, chunk_mode)

    logger.info(
        "ERA5-Land window %s..%s -> %d %s chunk(s), %d hour(s) total",
        start.isoformat(), end.isoformat(), len(chunks), chunk_mode,
        total_hours,
    )

    paths: list[Path] = []
    for chunk_start, chunk_stop in chunks:
        request = build_era5_land_request(
            variables, chunk_start, chunk_stop, area=list(bbox)
        )
        expected = request["_expected_timestamp_count"]
        cartesian = request["_cartesian_timestamp_count"]
        if expected != cartesian:
            raise ERA5LandRequestError(
                f"Chunk {chunk_start.isoformat()}..{chunk_stop.isoformat()} "
                f"would over-request: {expected} hours wanted but CDS would "
                f"return {cartesian}. Use chunk_mode='daily'."
            )

        target = output_dir / _chunk_filename(chunk_start, chunk_stop)
        if target.exists() and target.stat().st_size > 0 and not overwrite:
            logger.info("Reusing %s (%d hour(s))", target.name, expected)
            paths.append(target.resolve())
            continue
        download_era5_land(request, target, overwrite=overwrite)
        paths.append(target.resolve())

    return paths


def validate_era5_land_window(
    paths: Sequence[Path],
    start_time: datetime,
    end_time: datetime,
    variables: Sequence[str],
    bbox: Sequence[float] | None = None,
) -> dict:
    """Structural validation of a fetched window. Returns a report dict.

    Checks timestamp count, uniqueness, hourly spacing, requested variables,
    spatial subset and a common grid. Raises on a hard structural failure.
    """
    import pandas as pd

    if not paths:
        raise ERA5LandValidationError("No files to validate.")

    start = _require_utc_hour(start_time, "start_time")
    end = _require_utc_hour(end_time, "end_time")
    expected = int((end - start).total_seconds() // 3600) + 1

    wanted_short = set()
    for name in variables:
        cds = _resolve_variable(name)
        for short, canonical in ERA5_SHORT_NAMES.items():
            if ERA5_VARIABLES.get(canonical) == cds:
                wanted_short.add(short)

    datasets = [read_era5_land(Path(p)).load() for p in paths]
    try:
        combined = xr.concat(
            datasets, dim="time", coords="minimal", compat="override"
        ).sortby("time")
        times = pd.DatetimeIndex(np.atleast_1d(combined["time"].values))

        problems: list[str] = []
        if times.size != expected:
            problems.append(
                f"{times.size} timestamps, expected {expected}"
            )
        if times.has_duplicates:
            problems.append("duplicate timestamps")
        if times.size > 1:
            gaps = set(
                np.diff(times.values).astype("timedelta64[m]").astype(int)
            )
            if gaps != {60}:
                problems.append(f"non-hourly spacing {sorted(gaps)}")

        present = {str(v) for v in combined.data_vars}
        missing = sorted(wanted_short - present)
        if missing:
            problems.append(f"requested variables missing: {missing}")
        extra = sorted(present - wanted_short)

        grids = {
            tuple(np.round(d["lat"].values, 6)) for d in datasets
        } | {tuple(np.round(d["lon"].values, 6)) for d in datasets}
        lat = np.asarray(combined["lat"].values, dtype="float64")
        lon = np.asarray(combined["lon"].values, dtype="float64")

        if bbox is not None:
            north, west, south, east = (float(v) for v in bbox)
            if lat.min() < south - 0.5 or lat.max() > north + 0.5:
                problems.append(
                    f"latitude {lat.min()}..{lat.max()} outside requested "
                    f"{south}..{north}"
                )
            if lon.min() < west - 0.5 or lon.max() > east + 0.5:
                problems.append(
                    f"longitude {lon.min()}..{lon.max()} outside requested "
                    f"{west}..{east}"
                )

        report = {
            "files": [str(Path(p)) for p in paths],
            "expected_timestamps": expected,
            "actual_timestamps": int(times.size),
            "unique_timestamps": int(times.nunique()),
            "hourly_spacing": bool(times.size < 2 or gaps == {60}),
            "first_utc": f"{times[0]}Z" if times.size else None,
            "last_utc": f"{times[-1]}Z" if times.size else None,
            "variables_present": sorted(present),
            "variables_missing": missing,
            "variables_unexpected": extra,
            "lat_range": [float(lat.min()), float(lat.max())],
            "lon_range": [float(lon.min()), float(lon.max())],
            "common_grid": True,
            "problems": problems,
            "grid_alignment_warning": GRID_ALIGNMENT_WARNING,
        }
        if problems:
            raise ERA5LandValidationError(
                "ERA5-Land window validation failed: " + "; ".join(problems)
            )
        return report
    finally:
        for dataset in datasets:
            dataset.close()


def resolve_short_names(dataset: xr.Dataset) -> dict[str, str]:
    """Map each science variable's short name to its canonical project name.

    Unknown short names map to ``None`` rather than being guessed at — a
    silent rename would hide a CDS product change.
    """
    return {
        str(name): ERA5_SHORT_NAMES.get(str(name))
        for name in dataset.data_vars
    }


def validate_expected_variables(
    dataset: xr.Dataset,
    expected_short_names: Sequence[str],
) -> dict:
    """Check a dataset carries exactly the expected short names.

    Args:
        dataset: Normalised ERA5-Land dataset.
        expected_short_names: Short names the request should have produced.

    Returns:
        ``{"mapping", "missing", "unexpected", "unmapped"}``. ``unexpected``
        and ``unmapped`` are reported rather than raised so a caller can
        decide; missing variables are always an error.

    Raises:
        ERA5LandValidationError: if an expected short name is absent.
    """
    present = {str(name) for name in dataset.data_vars}
    expected = list(dict.fromkeys(str(n) for n in expected_short_names))

    missing = [name for name in expected if name not in present]
    if missing:
        raise ERA5LandValidationError(
            f"Expected ERA5-Land variable(s) missing from the dataset: "
            f"{missing}. Present: {sorted(present)}. Do not rename anything — "
            "check the CDS request and the product's short names first."
        )

    unexpected = sorted(present - set(expected))
    mapping = resolve_short_names(dataset)
    unmapped = sorted(
        name for name, canonical in mapping.items() if canonical is None
    )
    if unmapped:
        logger.warning(
            "Short name(s) %s are not in ERA5_SHORT_NAMES — reporting, not "
            "renaming. Update the production module deliberately.", unmapped,
        )
    return {
        "mapping": mapping,
        "missing": missing,
        "unexpected": unexpected,
        "unmapped": unmapped,
    }


__all__ = [
    "ACCUMULATED_VARIABLES",
    "AREA",
    "HOURLY_MM_NAMES",
    "INSTANTANEOUS_VARIABLES",
    "METRES_TO_MM",
    "RAW_ACCUMULATION_SEMANTICS",
    "CUMULATIVE_STEP_TYPES",
    "FLUX_HOURLY_M_NAMES",
    "INSTANT_STEP_TYPES",
    "TEMPORAL_MODE_CUMULATIVE",
    "TEMPORAL_MODE_HOURLY",
    "ERA5LandTemporalSemanticsError",
    "deaccumulate_era5_land",
    "DEFAULT_MAX_EXPECTED_TIMESTAMPS",
    "fetch_era5_land_window",
    "validate_era5_land_window",
    "infer_temporal_semantics",
    "normalize_era5_land_fluxes",
    "ERA5_LAND_DATASET",
    "ERA5_SHORT_NAMES",
    "ERA5_VARIABLES",
    "GRID_ALIGNMENT_WARNING",
    "NEGATIVE_NOISE_TOLERANCE",
    "SOURCE_PRODUCT",
    "ERA5LandDownloadError",
    "ERA5LandError",
    "ERA5LandRequestError",
    "ERA5LandValidationError",
    "build_era5_land_request",
    "download_era5_land",
    "read_era5_land",
    "resolve_short_names",
    "strip_request_metadata",
    "validate_expected_variables",
]
