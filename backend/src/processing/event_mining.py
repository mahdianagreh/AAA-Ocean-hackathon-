"""Rainfall candidate mining from processed IMERG windows.

Ranks extreme rainfall windows across one or more processed datasets and emits
a candidate table with explicit scope metadata.

**Scope honesty is a first-class feature.** Every row records the search scope
it came from and whether that scope was exhaustive. A table built from two demo
windows must never be mistaken for "all historical events", so
``is_exhaustive`` is carried on every row and defaults to False.

Final and Early runs are ranked separately: Early is preliminary and
uncalibrated, so pooling the two would contaminate any threshold derived from
the result.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger(__name__)

#: Rolling variables considered, in ascending window length.
CANDIDATE_VARIABLES = ("rain_1h_mm", "rain_3h_mm", "rain_6h_mm", "rain_24h_mm")

#: Variable used to rank candidates unless overridden.
RANKING_VARIABLE = "rain_3h_mm"

OUTPUT_COLUMNS = (
    "event_id",
    "start_time_utc",
    "end_time_utc",
    "peak_time_utc",
    "rain_1h_mm",
    "rain_3h_mm",
    "rain_6h_mm",
    "rain_24h_mm",
    "historical_percentile",
    "anomaly_score",
    "lat",
    "lon",
    "source_product",
    "run_type",
    "data_completeness",
    "quality_score",
    "candidate_generation_scope",
    "search_scope_start_utc",
    "search_scope_end_utc",
    "is_exhaustive",
)


class EventMiningError(ValueError):
    """Raised when candidates cannot be ranked as requested."""


def _to_datetime_index(values: Any) -> pd.DatetimeIndex:
    """Convert a time coordinate to DatetimeIndex, handling cftime.

    IMERG's epoch pushes xarray onto cftime objects, which pandas cannot
    convert directly. They are formatted and reparsed rather than assumed to be
    numpy datetimes.
    """
    raw = np.atleast_1d(values)
    if raw.size and not isinstance(raw[0], np.datetime64) and hasattr(
        raw[0], "strftime"
    ):
        return pd.DatetimeIndex(
            [pd.Timestamp(t.strftime("%Y-%m-%dT%H:%M:%S")) for t in raw]
        )
    return pd.DatetimeIndex(raw)


def _stamp(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(np.datetime_as_string(value, unit="s")) + "Z"


def rank_rainfall_candidates(
    datasets: Sequence[xr.Dataset],
    *,
    percentile_threshold: float = 95.0,
    minimum_separation_hours: int = 24,
    ranking_variable: str = RANKING_VARIABLE,
    candidate_generation_scope: str = "configured demonstration windows",
    is_exhaustive: bool = False,
) -> pd.DataFrame:
    """Rank extreme rainfall windows across processed IMERG datasets.

    For each dataset the grid maximum of `ranking_variable` is taken at every
    timestamp, peaks above `percentile_threshold` are selected, and peaks
    closer together than `minimum_separation_hours` are collapsed to the
    strongest — so one storm does not produce a dozen near-duplicate rows.

    Args:
        datasets: Processed IMERG datasets carrying rolling accumulations and
            an ``imerg_run_type`` attribute.
        percentile_threshold: Percentile of the per-timestamp maxima above
            which a timestamp is a candidate.
        minimum_separation_hours: Minimum spacing between distinct candidates.
        ranking_variable: Rolling variable used for ranking.
        candidate_generation_scope: Free text describing what was searched.
        is_exhaustive: Whether the search covered the full archive. Keep False
            unless a complete historical sweep was genuinely performed.

    Returns:
        DataFrame with :data:`OUTPUT_COLUMNS`, strongest first.

    Raises:
        EventMiningError: on empty input, a missing ranking variable, or an
            invalid percentile.
    """
    if not datasets:
        raise EventMiningError("No datasets supplied.")
    if not 0 < percentile_threshold < 100:
        raise EventMiningError(
            f"percentile_threshold must be in (0, 100), got "
            f"{percentile_threshold}"
        )

    rows: list[dict] = []
    scope_starts: list[pd.Timestamp] = []
    scope_ends: list[pd.Timestamp] = []

    for dataset in datasets:
        if ranking_variable not in dataset.variables:
            raise EventMiningError(
                f"Dataset lacks {ranking_variable!r}; found "
                f"{sorted(map(str, dataset.data_vars))}"
            )

        run_type = str(dataset.attrs.get("imerg_run_type", "unknown"))
        source_product = str(dataset.attrs.get("source_product", "unknown"))
        completeness = float(
            dataset.attrs.get("data_completeness_percent", float("nan"))
        )
        event_id = str(dataset.attrs.get("event_id", dataset.attrs.get(
            "imerg_short_name", "UNKNOWN")))

        times = _to_datetime_index(dataset["time"].values)
        scope_starts.append(times[0])
        scope_ends.append(times[-1])

        ranked = np.asarray(dataset[ranking_variable].values, dtype="float64")
        per_time = np.nanmax(
            np.where(np.isfinite(ranked), ranked, -np.inf), axis=(1, 2)
        )
        per_time = np.where(np.isfinite(per_time), per_time, np.nan)
        usable = np.isfinite(per_time)
        if not usable.any():
            logger.warning(
                "%s: no complete %s windows; skipped", event_id, ranking_variable
            )
            continue

        finite = per_time[usable]
        threshold = float(np.percentile(finite, percentile_threshold))
        mean = float(finite.mean())
        spread = float(finite.std())

        order = np.argsort(np.where(usable, per_time, -np.inf))[::-1]
        chosen: list[int] = []
        for index in order:
            value = per_time[index]
            # Strictly greater: with a flat baseline the percentile equals the
            # baseline, and ">=" would nominate every quiet timestamp.
            if not np.isfinite(value) or value <= threshold or value <= 0:
                continue
            if any(
                abs((times[index] - times[other]).total_seconds()) / 3600.0
                < minimum_separation_hours
                for other in chosen
            ):
                continue
            chosen.append(int(index))

        for index in chosen:
            slab = np.asarray(
                dataset[ranking_variable].values[index], dtype="float64"
            )
            flat = int(np.nanargmax(slab))
            lat_index, lon_index = np.unravel_index(flat, slab.shape)

            hours = float(
                dataset[ranking_variable].attrs.get("window_hours", 3.0)
            )
            interval = float(
                dataset[ranking_variable].attrs.get("interval_hours", 0.5)
            )
            end = times[index] + pd.Timedelta(hours=interval)
            start = end - pd.Timedelta(hours=hours)

            value = float(per_time[index])
            percentile = float(
                100.0 * (finite <= value).sum() / max(finite.size, 1)
            )
            anomaly = float((value - mean) / spread) if spread > 0 else 0.0

            row: dict = {
                "event_id": event_id,
                "start_time_utc": _stamp(start),
                "end_time_utc": _stamp(end),
                "peak_time_utc": _stamp(times[index]),
                "historical_percentile": round(percentile, 4),
                "anomaly_score": round(anomaly, 6),
                "lat": float(dataset["lat"].values[int(lat_index)]),
                "lon": float(dataset["lon"].values[int(lon_index)]),
                "source_product": source_product,
                "run_type": run_type,
                "data_completeness": completeness,
            }
            for name in CANDIDATE_VARIABLES:
                if name in dataset.variables:
                    values = np.asarray(
                        dataset[name].values[index], dtype="float64"
                    )
                    row[name] = (
                        float(np.nanmax(values))
                        if np.isfinite(values).any() else np.nan
                    )
                else:
                    row[name] = np.nan

            # Quality: completeness, whether the peak is a real signal, and a
            # penalty for preliminary products.
            completeness_score = (
                completeness / 100.0 if np.isfinite(completeness) else 0.5
            )
            run_penalty = 1.0 if run_type == "final" else 0.6
            row["quality_score"] = round(
                float(np.clip(completeness_score * run_penalty, 0.0, 1.0)), 6
            )
            rows.append(row)

    if not rows:
        frame = pd.DataFrame(columns=list(OUTPUT_COLUMNS))
    else:
        frame = pd.DataFrame(rows)

    scope_start = _stamp(min(scope_starts)) if scope_starts else None
    scope_end = _stamp(max(scope_ends)) if scope_ends else None
    frame["candidate_generation_scope"] = candidate_generation_scope
    frame["search_scope_start_utc"] = scope_start
    frame["search_scope_end_utc"] = scope_end
    frame["is_exhaustive"] = bool(is_exhaustive)

    for column in OUTPUT_COLUMNS:
        if column not in frame.columns:
            frame[column] = np.nan
    frame = frame[list(OUTPUT_COLUMNS)]

    if not frame.empty:
        frame = frame.sort_values(
            ranking_variable, ascending=False, kind="stable"
        ).reset_index(drop=True)

    logger.info(
        "Ranked %d candidate(s) across %d dataset(s); exhaustive=%s",
        len(frame), len(datasets), is_exhaustive,
    )
    return frame


def separate_by_run_type(frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split a candidate table by run type so Final and Early never mix."""
    return {
        str(run_type): group.reset_index(drop=True)
        for run_type, group in frame.groupby("run_type", sort=True)
    }


__all__ = [
    "CANDIDATE_VARIABLES",
    "OUTPUT_COLUMNS",
    "EventMiningError",
    "rank_rainfall_candidates",
    "separate_by_run_type",
]
