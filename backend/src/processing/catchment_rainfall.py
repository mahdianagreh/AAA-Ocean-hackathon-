"""Area-weighted aggregation of IMERG grid rainfall onto catchment polygons.

Grid cells are built from the IMERG ``lat_bnds``/``lon_bnds`` so each cell is
its true rectangular footprint — never a centre point. Every area calculation
happens in a projected CRS (:data:`AREA_CRS`); degrees are never treated as
area. Coverage is reported raw and never silently normalised to 100 %.

Missing rainfall is never treated as zero: a cell with NaN contributes no
weight, and the aggregate is divided only by the area that actually had data.
``valid_area_fraction`` records how much of the intersecting area was usable.

This module reads geometry and rainfall; it never writes a GeoPackage.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Iterable, Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import box

logger = logging.getLogger(__name__)

#: Storage/exchange CRS for all vector data.
STORAGE_CRS = "EPSG:4326"
#: Projected CRS used for every area and intersection calculation (UTM 36N).
AREA_CRS = "EPSG:32636"

#: Project catchment ID format, e.g. ``AQ-C01``.
CATCHMENT_ID_PATTERN = re.compile(r"^AQ-C\d{2}$")
#: Column names accepted as the catchment identifier, in priority order.
ID_COLUMN_CANDIDATES = ("catchment_id", "id", "ID", "CATCHMENT_ID", "name")

REAL = "REAL"
PROVISIONAL = "PROVISIONAL"

FLAG_GOOD = "GOOD"
FLAG_PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
FLAG_MISSING_DATA = "MISSING_DATA"
FLAG_PROVISIONAL_GEOMETRY = "PROVISIONAL_GEOMETRY"

GOOD_COVERAGE_THRESHOLD = 0.95
GOOD_VALID_AREA_THRESHOLD = 0.95

#: Rolling accumulation variables and the window each represents, in hours.
WINDOW_HOURS: dict[str, float] = {
    "rain_1h_mm": 1.0,
    "rain_3h_mm": 3.0,
    "rain_6h_mm": 6.0,
    "rain_24h_mm": 24.0,
}

#: Variables aggregated onto catchments.
RAINFALL_VARIABLES: tuple[str, ...] = (
    "precipitation",
    "precipitation_depth_mm",
    *WINDOW_HOURS.keys(),
)

#: Variable whose validity drives ``valid_area_fraction`` and the flags.
BASE_VARIABLE = "precipitation"

#: Output column order for the production Parquet.
PARQUET_COLUMNS: tuple[str, ...] = (
    "event_id",
    "timestamp_utc",
    "catchment_id",
    "precipitation_mm_hr",
    "precipitation_depth_mm",
    "rain_1h_mm",
    "rain_3h_mm",
    "rain_6h_mm",
    "rain_24h_mm",
    "coverage_fraction",
    "valid_area_fraction",
    "quality_flag",
    "source_geometry_status",
)

#: Rename map from dataset variable names to Parquet column names.
#:
#: The default suits the half-hourly products, whose native rate is mm/hr.
#: The DAILY product reports mm/day, so writing its values into a column
#: called `precipitation_mm_hr` would put the wrong unit into the schema and
#: hand the next reader a 24x error with a helpful-looking label on it.
#: Callers on a non-hourly product pass `output_names` instead.
OUTPUT_NAMES = {"precipitation": "precipitation_mm_hr"}

#: Units-correct column names per IMERG rate unit, so no call site invents one.
OUTPUT_NAMES_BY_RATE_UNIT = {
    "mm/hr": {"precipitation": "precipitation_mm_hr"},
    "mm/day": {"precipitation": "precipitation_mm_day"},
}


class MissingCatchmentsError(FileNotFoundError):
    """Raised when neither real nor provisional catchments are available."""


class CatchmentValidationError(ValueError):
    """Raised when catchment geometry or attributes fail validation."""


@dataclass(frozen=True)
class CatchmentSource:
    """Where catchments came from and whether they are real or provisional."""

    path: Path
    status: str

    @property
    def is_provisional(self) -> bool:
        return self.status == PROVISIONAL


# ---------------------------------------------------------------------------
# 1. catchment loading and validation
# ---------------------------------------------------------------------------


def resolve_catchment_source(
    real_path: Path,
    provisional_path: Path,
) -> CatchmentSource:
    """Pick real catchments when present, else provisional ones.

    Raises:
        MissingCatchmentsError: when neither file exists. The message names
            both paths and the owning task so the blocker is actionable.
    """
    real_path, provisional_path = Path(real_path), Path(provisional_path)
    if real_path.exists():
        return CatchmentSource(real_path, REAL)
    if provisional_path.exists():
        return CatchmentSource(provisional_path, PROVISIONAL)

    raise MissingCatchmentsError(
        "No catchment polygons available — cannot aggregate rainfall.\n"
        f"  preferred : {real_path}  (missing)\n"
        f"  fallback  : {provisional_path}  (missing)\n"
        "This is task P1 in tasks/00-contracts.md: clip HydroBASINS level 9 "
        "to the AOI, pick the 5 draining to the Gulf, assign AQ-C01..AQ-C05.\n"
        "Catchments must not be fabricated — real or provisional polygons are "
        "a hard dependency."
    )


def _detect_id_column(frame: gpd.GeoDataFrame) -> str:
    """Find the catchment ID column without ever renaming values."""
    for candidate in ID_COLUMN_CANDIDATES:
        if candidate in frame.columns:
            values = frame[candidate].astype(str)
            if values.str.match(CATCHMENT_ID_PATTERN).all():
                return candidate

    for column in frame.columns:
        if column == frame.geometry.name:
            continue
        values = frame[column].astype(str)
        if values.str.match(CATCHMENT_ID_PATTERN).all():
            return column

    raise CatchmentValidationError(
        "No catchment ID column matching the project format AQ-C01, AQ-C02, "
        f"... Checked {ID_COLUMN_CANDIDATES} then every column. Columns "
        f"present: {[c for c in frame.columns if c != frame.geometry.name]}. "
        "IDs are never renamed automatically — fix them at the source."
    )


def validate_catchments(
    frame: gpd.GeoDataFrame,
    repair_invalid: bool = True,
) -> gpd.GeoDataFrame:
    """Validate IDs, geometry and CRS; return a clean 4326 frame.

    Args:
        frame: Catchment polygons with an ``AQ-C**`` identifier column.
        repair_invalid: Attempt ``make_valid`` on invalid geometries. When
            False, invalid geometry is rejected outright.

    Returns:
        GeoDataFrame in :data:`STORAGE_CRS` with a ``catchment_id`` column.

    Raises:
        CatchmentValidationError: on a missing/duplicate ID, absent CRS,
            empty/null geometry, non-polygon geometry, or unrepairable
            invalid geometry.
    """
    if frame.empty:
        raise CatchmentValidationError("Catchment file contains no features.")

    id_column = _detect_id_column(frame)
    result = frame.copy()
    # Preserve the original values verbatim; only the column label is normalised.
    result["catchment_id"] = result[id_column].astype(str)

    duplicates = sorted(
        result["catchment_id"][result["catchment_id"].duplicated()].unique()
    )
    if duplicates:
        raise CatchmentValidationError(
            f"Duplicate catchment IDs: {duplicates}. Each catchment must "
            "appear exactly once; IDs are not renamed automatically."
        )

    if result.crs is None:
        raise CatchmentValidationError(
            "Catchment layer has no CRS. Expected "
            f"{STORAGE_CRS}; refusing to guess."
        )
    if result.crs.to_string() != STORAGE_CRS:
        logger.warning(
            "Catchments are in %s, not the %s exchange CRS — reprojecting.",
            result.crs.to_string(), STORAGE_CRS,
        )
        result = result.to_crs(STORAGE_CRS)

    if result.geometry.isna().any() or result.geometry.is_empty.any():
        bad = result.loc[
            result.geometry.isna() | result.geometry.is_empty, "catchment_id"
        ].tolist()
        raise CatchmentValidationError(
            f"Null or empty geometry for catchment(s): {bad}"
        )

    invalid_mask = ~result.geometry.is_valid
    if invalid_mask.any():
        bad = result.loc[invalid_mask, "catchment_id"].tolist()
        if not repair_invalid:
            raise CatchmentValidationError(
                f"Invalid geometry for catchment(s): {bad} "
                "(repair_invalid=False)"
            )
        logger.warning("Repairing invalid geometry for %s", bad)
        result.loc[invalid_mask, result.geometry.name] = result.loc[
            invalid_mask, result.geometry.name
        ].make_valid()
        still_invalid = ~result.geometry.is_valid
        if still_invalid.any():
            raise CatchmentValidationError(
                "Geometry could not be repaired for catchment(s): "
                f"{result.loc[still_invalid, 'catchment_id'].tolist()}"
            )

    bad_type = ~result.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
    if bad_type.any():
        offenders = result.loc[bad_type, ["catchment_id"]].assign(
            geom_type=result.loc[bad_type].geometry.geom_type
        )
        raise CatchmentValidationError(
            "Catchments must be polygonal; got "
            f"{offenders.to_dict('records')}"
        )

    logger.info(
        "Validated %d catchments from column %r", len(result), id_column
    )
    return result


def load_catchments(
    path: Path,
    layer: str | None = None,
    repair_invalid: bool = True,
) -> gpd.GeoDataFrame:
    """Read and validate a catchment GeoPackage."""
    frame = gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)
    return validate_catchments(frame, repair_invalid=repair_invalid)


# ---------------------------------------------------------------------------
# 2. IMERG grid-cell footprints
# ---------------------------------------------------------------------------


def build_grid_cells(dataset: xr.Dataset) -> gpd.GeoDataFrame:
    """Build true rectangular footprints for every IMERG cell.

    Uses ``lat_bnds``/``lon_bnds`` when present so each polygon is the cell's
    real extent. Falls back to half-spacing around the centres only when
    bounds are absent, and logs that clearly — centre-point assignment alone
    is never used.

    Returns:
        GeoDataFrame in :data:`STORAGE_CRS` with ``lat_index``, ``lon_index``,
        ``lat_center``, ``lon_center`` and ``geometry``.
    """
    lat = np.asarray(dataset["lat"].values, dtype="float64")
    lon = np.asarray(dataset["lon"].values, dtype="float64")

    if "lat_bnds" in dataset.variables and "lon_bnds" in dataset.variables:
        lat_bounds = np.asarray(dataset["lat_bnds"].values, dtype="float64")
        lon_bounds = np.asarray(dataset["lon_bnds"].values, dtype="float64")
        source = "lat_bnds/lon_bnds"
    else:
        logger.warning(
            "lat_bnds/lon_bnds absent — deriving footprints from centre "
            "spacing. Verify the grid before trusting areas."
        )
        lat_step = float(np.abs(np.diff(lat)).mean()) if lat.size > 1 else 0.1
        lon_step = float(np.abs(np.diff(lon)).mean()) if lon.size > 1 else 0.1
        lat_bounds = np.column_stack([lat - lat_step / 2, lat + lat_step / 2])
        lon_bounds = np.column_stack([lon - lon_step / 2, lon + lon_step / 2])
        source = "centre spacing"

    records = []
    for lat_index in range(lat.size):
        south, north = sorted(lat_bounds[lat_index][:2])
        for lon_index in range(lon.size):
            west, east = sorted(lon_bounds[lon_index][:2])
            records.append({
                "lat_index": lat_index,
                "lon_index": lon_index,
                "lat_center": float(lat[lat_index]),
                "lon_center": float(lon[lon_index]),
                "geometry": box(west, south, east, north),
            })

    cells = gpd.GeoDataFrame(records, crs=STORAGE_CRS)
    cells["cell_area_m2"] = cells.to_crs(AREA_CRS).geometry.area
    if (cells["cell_area_m2"] <= 0).any():
        raise ValueError(
            "Non-positive projected cell area — check lat_bnds/lon_bnds."
        )

    logger.info(
        "Built %d grid-cell footprints from %s", len(cells), source
    )
    return cells


# ---------------------------------------------------------------------------
# 3. overlap weights
# ---------------------------------------------------------------------------


def compute_overlaps(
    cells: gpd.GeoDataFrame,
    catchments: gpd.GeoDataFrame,
    min_overlap_fraction: float = 0.0,
) -> pd.DataFrame:
    """Intersect catchments with grid cells and compute area weights.

    All areas are projected (:data:`AREA_CRS`). ``coverage_fraction`` is the
    share of the catchment covered by intersecting cells and is returned raw —
    incomplete coverage is reported, never rescaled to 1.

    Note on slivers: reprojecting lon/lat rectangles curves their edges, so a
    catchment aligned to a cell boundary picks up hairline intersections with
    the neighbouring cells — typically ~1e-5 of its area. These are kept by
    default because they are geometrically real and numerically irrelevant;
    dropping them needs an explicit threshold rather than a hidden one.

    Args:
        cells: Grid-cell footprints from :func:`build_grid_cells`.
        catchments: Validated catchment polygons.
        min_overlap_fraction: Discard intersections smaller than this fraction
            of the catchment area. ``0.0`` keeps everything. Any value above
            zero removes real (if tiny) overlaps, and the dropped weight is
            logged.

    Returns:
        DataFrame with ``catchment_id``, ``lat_index``, ``lon_index``,
        ``intersection_area_m2``, ``catchment_area_m2``, ``overlap_weight``
        and ``coverage_fraction``.

    Raises:
        ValueError: if a catchment has non-positive projected area, or any
            intersection area is negative.
    """
    cells_projected = cells.to_crs(AREA_CRS)
    catchments_projected = catchments.to_crs(AREA_CRS)

    areas = catchments_projected.geometry.area
    if (areas <= 0).any():
        bad = catchments_projected.loc[areas <= 0, "catchment_id"].tolist()
        raise ValueError(f"Non-positive projected catchment area: {bad}")
    catchment_areas = dict(zip(catchments_projected["catchment_id"], areas))

    pieces = gpd.overlay(
        cells_projected[
            ["lat_index", "lon_index", "lat_center", "lon_center", "geometry"]
        ],
        catchments_projected[["catchment_id", "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    pieces["intersection_area_m2"] = (
        pieces.geometry.area if not pieces.empty
        else pd.Series(dtype="float64")
    )

    if not pieces.empty and (pieces["intersection_area_m2"] < 0).any():
        raise ValueError("Negative intersection area computed.")

    # Drop slivers of exactly zero area; they carry no weight.
    pieces = pieces[pieces["intersection_area_m2"] > 0].copy()

    if pieces.empty:
        # No catchment touches the grid. Return a correctly-typed empty frame
        # so callers get a clear "no overlap" signal, not a KeyError.
        for catchment_id in sorted(catchment_areas):
            logger.warning(
                "Catchment %s does not intersect the IMERG grid at all",
                catchment_id,
            )
        return pd.DataFrame({
            "catchment_id": pd.Series(dtype="object"),
            "lat_index": pd.Series(dtype="int64"),
            "lon_index": pd.Series(dtype="int64"),
            "intersection_area_m2": pd.Series(dtype="float64"),
            "catchment_area_m2": pd.Series(dtype="float64"),
            "overlap_weight": pd.Series(dtype="float64"),
            "coverage_fraction": pd.Series(dtype="float64"),
        })

    overlaps = (
        pieces.groupby(["catchment_id", "lat_index", "lon_index"], as_index=False)
        ["intersection_area_m2"].sum()
    )
    overlaps["catchment_area_m2"] = overlaps["catchment_id"].map(catchment_areas)
    overlaps["overlap_weight"] = (
        overlaps["intersection_area_m2"] / overlaps["catchment_area_m2"]
    )

    if min_overlap_fraction > 0:
        tiny = overlaps["overlap_weight"] < min_overlap_fraction
        if tiny.any():
            logger.warning(
                "Dropping %d overlap(s) below min_overlap_fraction=%g; "
                "total discarded weight %.3e",
                int(tiny.sum()), min_overlap_fraction,
                float(overlaps.loc[tiny, "overlap_weight"].sum()),
            )
            overlaps = overlaps[~tiny].copy()

    coverage = (
        overlaps.groupby("catchment_id")["intersection_area_m2"].sum()
        / pd.Series(catchment_areas)
    ).rename("coverage_fraction")
    overlaps = overlaps.merge(coverage, on="catchment_id", how="left")

    # Catchments with no intersecting cell at all must still be visible.
    missing = set(catchment_areas) - set(overlaps["catchment_id"])
    for catchment_id in sorted(missing):
        logger.warning(
            "Catchment %s does not intersect the IMERG grid at all",
            catchment_id,
        )

    incomplete = coverage[coverage < GOOD_COVERAGE_THRESHOLD]
    if not incomplete.empty:
        logger.warning(
            "Incomplete IMERG coverage (raw, not normalised): %s",
            {k: round(float(v), 4) for k, v in incomplete.items()},
        )

    return overlaps


def coverage_by_catchment(overlaps: pd.DataFrame) -> dict[str, float]:
    """Raw coverage fraction per catchment."""
    return {
        str(row.catchment_id): float(row.coverage_fraction)
        for row in overlaps.drop_duplicates("catchment_id").itertuples()
    }


# ---------------------------------------------------------------------------
# 4. area-weighted aggregation
# ---------------------------------------------------------------------------


def classify_quality(
    valid_area_fraction: float,
    coverage_fraction: float,
    geometry_status: str,
) -> str:
    """Combine data-quality and geometry-provenance flags.

    Provisional geometry always contributes ``PROVISIONAL_GEOMETRY``, even
    when the numbers look perfect — otherwise placeholder polygons would look
    production-ready.
    """
    parts: list[str] = []
    if not np.isfinite(valid_area_fraction) or valid_area_fraction <= 0:
        parts.append(FLAG_MISSING_DATA)
    elif valid_area_fraction < GOOD_VALID_AREA_THRESHOLD:
        parts.append(FLAG_MISSING_DATA)

    if not np.isfinite(coverage_fraction) or \
            coverage_fraction < GOOD_COVERAGE_THRESHOLD:
        parts.append(FLAG_PARTIAL_COVERAGE)

    if not parts:
        parts.append(FLAG_GOOD)

    if geometry_status == PROVISIONAL:
        parts.append(FLAG_PROVISIONAL_GEOMETRY)

    return "|".join(parts)


def aggregate_catchment_rainfall(
    dataset: xr.Dataset,
    overlaps: pd.DataFrame,
    event_id: str,
    geometry_status: str,
    variables: Sequence[str] = RAINFALL_VARIABLES,
    output_names: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Area-weighted catchment rainfall for every timestamp.

    For each catchment and timestamp::

        value = sum(grid_value * intersection_area)
                / sum(intersection_area where grid_value is valid)

    A NaN grid cell contributes neither numerator nor denominator, so missing
    data is never treated as zero. ``valid_area_fraction`` is the share of the
    catchment's intersecting area that had valid data for
    :data:`BASE_VARIABLE`.

    Returns:
        Long-format DataFrame ordered by timestamp then catchment, using the
        :data:`PARQUET_COLUMNS` schema.

    Raises:
        KeyError: if a requested variable is absent from `dataset`.
        ValueError: if `overlaps` is empty.
    """
    if overlaps.empty:
        raise ValueError(
            "No catchment/grid overlaps — nothing to aggregate. Check that "
            "the catchments fall inside the IMERG grid."
        )
    for name in variables:
        if name not in dataset.variables:
            raise KeyError(f"Dataset has no variable {name!r}")

    times = np.atleast_1d(dataset["time"].values)
    timestamps = [
        t.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(t, "strftime")
        else str(np.datetime_as_string(t, unit="s")) + "Z"
        for t in times
    ]

    arrays = {
        name: np.asarray(dataset[name].values, dtype="float64")
        for name in variables
    }

    # Resolved once, at function scope: it is also needed after the loop when
    # building the output schema, and a loop-local binding would break on an
    # empty result set.
    names = OUTPUT_NAMES if output_names is None else output_names

    frames: list[pd.DataFrame] = []
    for catchment_id, group in overlaps.groupby("catchment_id", sort=True):
        lat_index = group["lat_index"].to_numpy(dtype=int)
        lon_index = group["lon_index"].to_numpy(dtype=int)
        areas = group["intersection_area_m2"].to_numpy(dtype="float64")
        total_area = float(areas.sum())
        coverage = float(group["coverage_fraction"].iloc[0])

        record: dict[str, object] = {
            "event_id": event_id,
            "timestamp_utc": timestamps,
            "catchment_id": catchment_id,
            "coverage_fraction": coverage,
            "source_geometry_status": geometry_status,
        }

        valid_fraction = None
        for name in variables:
            values = arrays[name][:, lat_index, lon_index]  # (time, n_cells)
            valid = np.isfinite(values)
            weighted = np.where(valid, values * areas, 0.0).sum(axis=1)
            valid_area = np.where(valid, areas, 0.0).sum(axis=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                mean = np.where(valid_area > 0, weighted / valid_area, np.nan)
            record[names.get(name, name)] = mean
            if name == BASE_VARIABLE:
                valid_fraction = (
                    valid_area / total_area if total_area > 0
                    else np.zeros_like(valid_area)
                )

        if valid_fraction is None:  # BASE_VARIABLE not requested
            valid_fraction = np.ones(len(timestamps))
        record["valid_area_fraction"] = valid_fraction

        frame = pd.DataFrame(record)
        frame["quality_flag"] = [
            classify_quality(float(v), coverage, geometry_status)
            for v in frame["valid_area_fraction"]
        ]
        frames.append(frame)

    result = pd.concat(frames, ignore_index=True)
    result = result.sort_values(
        ["timestamp_utc", "catchment_id"], kind="stable"
    ).reset_index(drop=True)

    # The schema is fixed in order but not in spelling: when a caller renames
    # a column to carry the right unit (mm/day rather than mm/hr), the schema
    # must follow, or the reindex below silently drops the computed values and
    # replaces them with an all-NaN column under the wrong name.
    schema = []
    for column in PARQUET_COLUMNS:
        variable = next(
            (var for var, default in OUTPUT_NAMES.items() if default == column),
            None,
        )
        schema.append(names.get(variable, column) if variable else column)

    for column in schema:
        if column not in result.columns:
            result[column] = np.nan
    return result[schema]


# ---------------------------------------------------------------------------
# 5. wettest windows per catchment
# ---------------------------------------------------------------------------


def wettest_windows_per_catchment(
    frame: pd.DataFrame,
    interval_hours: float = 0.5,
    windows: dict[str, float] | None = None,
) -> dict[str, dict[str, dict]]:
    """Maximum trailing accumulation per catchment, per window length.

    A trailing value labelled *t* covers ``[t + interval - hours, t + interval)``,
    so ``end`` is one interval past the label and ``start`` is ``hours``
    earlier.

    Returns:
        ``{catchment_id: {variable: {start_utc, end_utc, max_mm,
        quality_flag, label_timestamp_utc}}}``. ``max_mm`` is None when every
        value is NaN.
    """
    windows = dict(windows or WINDOW_HOURS)
    step = timedelta(hours=float(interval_hours))
    output: dict[str, dict[str, dict]] = {}

    for catchment_id, group in frame.groupby("catchment_id", sort=True):
        ordered = group.sort_values("timestamp_utc", kind="stable")
        stamps = pd.to_datetime(ordered["timestamp_utc"], utc=True)
        per_variable: dict[str, dict] = {}

        for variable, hours in windows.items():
            if variable not in ordered.columns:
                continue
            values = ordered[variable].to_numpy(dtype="float64")
            if not np.any(np.isfinite(values)):
                per_variable[variable] = {
                    "window_hours": hours,
                    "max_mm": None,
                    "note": "no complete window available",
                }
                continue

            position = int(np.nanargmax(values))
            label = stamps.iloc[position].to_pydatetime()
            end = label + step
            start = end - timedelta(hours=float(hours))
            per_variable[variable] = {
                "window_hours": float(hours),
                "start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_utc": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "label_timestamp_utc": label.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "max_mm": float(values[position]),
                "quality_flag": str(ordered["quality_flag"].iloc[position]),
            }

        output[str(catchment_id)] = per_variable

    return output


# ---------------------------------------------------------------------------
# 6. spatial-consistency comparison
# ---------------------------------------------------------------------------


def compare_with_grid_peak(
    catchment_windows: dict[str, dict[str, dict]],
    grid_peak: dict,
    flood_arrival_utc: str = "2016-10-28T00:00:00Z",
    variable: str = "rain_3h_mm",
) -> dict:
    """Spatial-consistency check: catchment peaks versus the grid-level peak.

    Reports whether aggregation shifts peak time, peak magnitude, and the
    ordering relative to the documented flood arrival. This is a consistency
    check only — it establishes no causal relationship between rainfall and
    the observed flood.
    """
    arrival = pd.Timestamp(flood_arrival_utc)
    grid_end = grid_peak.get("window_end_utc") or grid_peak.get("end_utc")
    grid_start = grid_peak.get("window_start_utc") or grid_peak.get("start_utc")
    grid_mm = grid_peak.get("max_mm") or grid_peak.get("max_rain_3h_mm")

    comparisons = []
    for catchment_id, windows in catchment_windows.items():
        info = windows.get(variable) or {}
        if info.get("max_mm") is None:
            comparisons.append({
                "catchment_id": catchment_id,
                "note": "no complete window",
            })
            continue

        end = pd.Timestamp(info["end_utc"])
        shift_hours = None
        if grid_end:
            shift_hours = (end - pd.Timestamp(grid_end)).total_seconds() / 3600
        delta_mm = (
            float(info["max_mm"]) - float(grid_mm)
            if grid_mm is not None else None
        )
        comparisons.append({
            "catchment_id": catchment_id,
            "catchment_window_start_utc": info["start_utc"],
            "catchment_window_end_utc": info["end_utc"],
            "catchment_max_mm": float(info["max_mm"]),
            "peak_time_shift_hours_vs_grid": (
                round(shift_hours, 4) if shift_hours is not None else None
            ),
            "peak_rainfall_delta_mm_vs_grid": (
                round(delta_mm, 6) if delta_mm is not None else None
            ),
            "peak_ends_before_flood_arrival": bool(end <= arrival),
            "hours_between_peak_end_and_arrival": round(
                (arrival - end).total_seconds() / 3600, 4
            ),
            "quality_flag": info.get("quality_flag"),
        })

    changed_time = any(
        c.get("peak_time_shift_hours_vs_grid") not in (None, 0.0)
        for c in comparisons
    )
    changed_rain = any(
        c.get("peak_rainfall_delta_mm_vs_grid") not in (None, 0.0)
        for c in comparisons
    )
    orderings = {
        c["catchment_id"]: c["peak_ends_before_flood_arrival"]
        for c in comparisons if "peak_ends_before_flood_arrival" in c
    }

    return {
        "check_type": "spatial-consistency check (no causal claim)",
        "variable": variable,
        "flood_arrival_utc": flood_arrival_utc,
        "grid_level": {
            "window_start_utc": grid_start,
            "window_end_utc": grid_end,
            "max_mm": grid_mm,
        },
        "catchment_level": comparisons,
        "aggregation_changes_peak_time": changed_time,
        "aggregation_changes_peak_rainfall": changed_rain,
        "any_catchment_peak_before_flood_arrival": any(orderings.values()),
        "all_catchment_peaks_before_flood_arrival": (
            all(orderings.values()) if orderings else False
        ),
        "ordering_by_catchment": orderings,
    }


# ---------------------------------------------------------------------------
# 8. summary structure
# ---------------------------------------------------------------------------


def build_summary(
    event_id: str,
    source: CatchmentSource,
    catchments: gpd.GeoDataFrame,
    cells: gpd.GeoDataFrame,
    overlaps: pd.DataFrame,
    frame: pd.DataFrame,
    catchment_windows: dict[str, dict[str, dict]],
    comparison: dict,
    extra_warnings: Iterable[str] = (),
) -> dict:
    """Assemble the production summary JSON structure."""
    coverage = coverage_by_catchment(overlaps)
    warnings = list(extra_warnings)

    if source.is_provisional:
        warnings.append(
            "Catchment geometry is PROVISIONAL — every row carries "
            "PROVISIONAL_GEOMETRY. Re-run after real delineation lands "
            "(swap-in item 1 in tasks/00-contracts.md)."
        )
    incomplete = {
        k: round(v, 6) for k, v in coverage.items()
        if v < GOOD_COVERAGE_THRESHOLD
    }
    if incomplete:
        warnings.append(
            "Incomplete IMERG coverage, reported raw and NOT normalised: "
            f"{incomplete}"
        )
    absent = sorted(
        set(catchments["catchment_id"]) - set(overlaps["catchment_id"])
    )
    if absent:
        warnings.append(
            f"Catchments with no IMERG overlap at all: {absent}"
        )

    return {
        "event_id": event_id,
        "catchment_file": str(source.path),
        "source_geometry_status": source.status,
        "catchment_count": int(len(catchments)),
        "catchment_ids": sorted(map(str, catchments["catchment_id"])),
        "imerg_cell_count": int(len(cells)),
        "overlap_count": int(len(overlaps)),
        "storage_crs": STORAGE_CRS,
        "area_crs": AREA_CRS,
        "row_count": int(len(frame)),
        "timestamp_count": int(frame["timestamp_utc"].nunique()),
        "first_timestamp_utc": (
            str(frame["timestamp_utc"].min()) if not frame.empty else None
        ),
        "last_timestamp_utc": (
            str(frame["timestamp_utc"].max()) if not frame.empty else None
        ),
        "coverage_fraction_by_catchment": {
            k: round(v, 6) for k, v in coverage.items()
        },
        "quality_flag_counts": {
            str(k): int(v)
            for k, v in frame["quality_flag"].value_counts().items()
        },
        "wettest_windows_by_catchment": catchment_windows,
        "grid_comparison": comparison,
        "assumptions": [
            "Area-weighted overlap using true cell footprints from "
            "lat_bnds/lon_bnds; no centre-point assignment.",
            f"All areas computed in {AREA_CRS}; geographic degrees never "
            "used as area.",
            "Missing grid values contribute no weight and are never treated "
            "as zero; valid_area_fraction records the usable share.",
            "coverage_fraction is raw and never normalised to 1.",
            "Rolling variables are NaN for the leading intervals of the "
            "series by design (min_periods = full window).",
            "Grid comparison is a spatial-consistency check only; it makes "
            "no causal claim about the observed flood.",
        ],
        "warnings": warnings,
    }
