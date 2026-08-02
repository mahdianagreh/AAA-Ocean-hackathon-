"""Backtest metrics for the particle engine -- Component F validation.

05-abd.md Part 3: report arrival-time, duration and peak-timing error against
the Kalman et al. (2025) mooring record, beat at least one baseline, and never
compute a spatial metric (IoU / Dice / centroid distance) for an event that has
no real observed mask. `AQ-2016-10-28` does not -- the Sentinel-2 extraction is
a documented coastline artifact (docs/pitch_limitations.md, docs/event_audit.md),
not ground truth, and `assert_spatial_metrics_allowed` below refuses to let
that mistake happen silently.

This module is written and unit-tested against synthetic inputs before any
real simulation or mooring row exists, per the task file's own instruction, so
that the day both real sides exist, running the comparison is one function call.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, replace
from typing import Sequence

import numpy as np
from shapely.geometry.base import BaseGeometry

# Late import to avoid a hard dependency loop; only used by the *_params helpers.
from models.particle_engine import ConstantCurrentField, ConstantWindField, ParticleEngineParams

#: No real observed plume mask exists for these events -- the satellite
#: extraction is a documented artifact (see module docstring). Spatial metrics
#: computed against it would be meaningless, not merely uncertain.
EVENTS_WITHOUT_REAL_OBSERVED_MASK = frozenset({"AQ-2016-10-28"})

M_PER_DEG_LAT = 110_940.0


class SpatialMetricsNotAllowedError(ValueError):
    """Raised when a spatial metric is requested for an event with no real mask."""


def assert_spatial_metrics_allowed(event_id: str) -> None:
    """Refuse to compute IoU/Dice/centroid distance for an event whose only
    'observed' plume is a documented artifact. Call this before any spatial
    metric, not after -- the point is to fail before producing a number that
    looks like evidence."""
    if event_id in EVENTS_WITHOUT_REAL_OBSERVED_MASK:
        raise SpatialMetricsNotAllowedError(
            f"{event_id} has no real observed plume mask -- the Sentinel-2 extraction is a "
            "documented coastline artifact (docs/pitch_limitations.md), not ground truth. "
            "Report that no spatial metric can be computed; do not compute one against it."
        )


def _meters_between(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Flat-earth distance, consistent with particle_engine's own approximation
    -- adequate at the scale of one Gulf, not a general-purpose geodesic."""
    m_per_deg_lon = 111_320.0 * math.cos(math.radians((lat1 + lat2) / 2.0))
    dx = (lon2 - lon1) * m_per_deg_lon
    dy = (lat2 - lat1) * M_PER_DEG_LAT
    return math.hypot(dx, dy)


# ---------------------------------------------------------------------------
# Deriving a timing signal from a particle cloud (or any concentration series)
# ---------------------------------------------------------------------------


def concentration_time_series(
    lons: np.ndarray,
    lats: np.ndarray,
    active: np.ndarray,
    point_lon: float,
    point_lat: float,
    radius_m: float,
) -> np.ndarray:
    """Fraction of the *original* release within `radius_m` of a point, active
    or not, at each timestep -- `lons`/`lats`/`active` shaped (n_steps+1, n).

    Denominator is the original particle count, not the currently-active
    count: once particles settle or beach they stop contributing, which is
    the point -- a plume that has fully deposited or beached should read as
    "gone", not renormalized back up to 100% of whatever is left.
    """
    n_steps, n_particles = lons.shape
    if n_particles == 0:
        raise ValueError("no particles to measure concentration from")

    m_per_deg_lon = 111_320.0 * math.cos(math.radians(point_lat))
    dx_m = (lons - point_lon) * m_per_deg_lon
    dy_m = (lats - point_lat) * M_PER_DEG_LAT
    within_radius = (dx_m**2 + dy_m**2) <= radius_m**2
    present = within_radius & active
    return present.sum(axis=1) / n_particles


@dataclass(frozen=True)
class TimingSignal:
    """Onset/peak/clear derived from a concentration (or any scalar) series
    against a threshold. Any field is None when the series never crosses the
    relevant threshold -- reported as "never arrived", never coerced to zero
    or to the series' last timestamp."""

    onset_time: dt.datetime | None
    peak_time: dt.datetime | None
    peak_value: float | None
    clear_time: dt.datetime | None

    @property
    def duration_hours(self) -> float | None:
        if self.onset_time is None or self.clear_time is None:
            return None
        return (self.clear_time - self.onset_time).total_seconds() / 3600.0


def detect_onset_clear_peak(
    times: Sequence[dt.datetime],
    values: np.ndarray,
    onset_threshold: float,
    clear_threshold: float | None = None,
) -> TimingSignal:
    """First crossing above `onset_threshold` is onset; the peak is the
    series max at-or-after onset; clear is the first crossing back below
    `clear_threshold` (default = `onset_threshold`) at-or-after the peak.

    A series that starts above threshold and never drops has `clear_time=None`
    -- exactly the honest result for a baseline that only ever grows
    (see `circular_buffer_signal`), not an inflated duration.
    """
    values = np.asarray(values, dtype=np.float64)
    if len(times) != len(values):
        raise ValueError("times and values must be the same length")
    if clear_threshold is None:
        clear_threshold = onset_threshold

    onset_idx = np.argmax(values >= onset_threshold) if (values >= onset_threshold).any() else None
    if onset_idx is None or values[onset_idx] < onset_threshold:
        return TimingSignal(None, None, None, None)

    onset_time = times[onset_idx]
    tail = values[onset_idx:]
    peak_offset = int(np.argmax(tail))
    peak_idx = onset_idx + peak_offset
    peak_time = times[peak_idx]
    peak_value = float(values[peak_idx])

    clear_time = None
    after_peak = values[peak_idx:]
    below = np.where(after_peak < clear_threshold)[0]
    if below.size > 0:
        clear_time = times[peak_idx + int(below[0])]

    return TimingSignal(onset_time=onset_time, peak_time=peak_time, peak_value=peak_value, clear_time=clear_time)


# ---------------------------------------------------------------------------
# Error metrics against the mooring target
# ---------------------------------------------------------------------------


def _hours_between(a: dt.datetime | None, b: dt.datetime | None) -> float | None:
    """Signed hours, b - a. None if either side never happened."""
    if a is None or b is None:
        return None
    return (b - a).total_seconds() / 3600.0


def arrival_time_error_hours(observed_onset: dt.datetime | None, simulated_onset: dt.datetime | None) -> float | None:
    """simulated - observed. Positive = simulation arrives late; negative = early."""
    return _hours_between(observed_onset, simulated_onset)


def duration_error_hours(observed_duration_hours: float | None, simulated_duration_hours: float | None) -> float | None:
    """simulated - observed. None if either duration is undefined (e.g. no clear time)."""
    if observed_duration_hours is None or simulated_duration_hours is None:
        return None
    return simulated_duration_hours - observed_duration_hours


def peak_timing_error_hours(observed_peak: dt.datetime | None, simulated_peak: dt.datetime | None) -> float | None:
    """simulated - observed. Positive = simulated peak lags the mooring's."""
    return _hours_between(observed_peak, simulated_peak)


@dataclass(frozen=True)
class ObjectiveWeights:
    """Weights for `calibration_objective`. Equal weighting by default --
    documented here, not implied, per 05-abd.md's "write the objective
    function down" requirement."""

    arrival: float = 1.0
    duration: float = 1.0
    peak_timing: float = 1.0


def calibration_objective(
    arrival_error_hours: float | None,
    duration_error_hours_: float | None,
    peak_timing_error_hours_: float | None,
    weights: ObjectiveWeights = ObjectiveWeights(),
) -> float:
    """The calibration grid search's objective: a weighted sum of absolute
    hourly errors against the mooring, lower is better.

        objective = w_arrival * |arrival_error|
                  + w_duration * |duration_error|
                  + w_peak * |peak_timing_error|

    A trial whose simulated plume never arrives at the mooring at all (any
    component is None) scores `+inf` -- it cannot be the winner, and it must
    not be silently excluded from the trial log (a run that produces `inf` is
    still a recorded `calibration_trials` row, just never `is_selected`).
    """
    components = (arrival_error_hours, duration_error_hours_, peak_timing_error_hours_)
    if any(c is None for c in components):
        return math.inf
    arrival, duration, peak = components
    return (
        weights.arrival * abs(arrival)
        + weights.duration * abs(duration)
        + weights.peak_timing * abs(peak)
    )


# ---------------------------------------------------------------------------
# Spatial metrics -- gated, for events that DO have a real observed mask
# ---------------------------------------------------------------------------


def iou(geometry_a: BaseGeometry, geometry_b: BaseGeometry) -> float:
    if geometry_a.is_empty or geometry_b.is_empty:
        return 0.0
    intersection = geometry_a.intersection(geometry_b).area
    union = geometry_a.union(geometry_b).area
    return intersection / union if union > 0 else 0.0


def dice(geometry_a: BaseGeometry, geometry_b: BaseGeometry) -> float:
    if geometry_a.is_empty or geometry_b.is_empty:
        return 0.0
    intersection = geometry_a.intersection(geometry_b).area
    denom = geometry_a.area + geometry_b.area
    return (2.0 * intersection) / denom if denom > 0 else 0.0


def centroid_distance_m(geometry_a: BaseGeometry, geometry_b: BaseGeometry) -> float:
    """Both geometries must already be in a metres-based CRS (EPSG:32636 per
    the project's CRS contract) -- this function does not reproject, so a
    caller handing it EPSG:4326 degrees gets a wrong answer with no warning.
    That reprojection responsibility stays with the caller deliberately, so
    the same function works whether the input started as 4326 or was already
    projected upstream."""
    ca, cb = geometry_a.centroid, geometry_b.centroid
    return ca.distance(cb)


# ---------------------------------------------------------------------------
# Baselines -- concept doc §13.6
# ---------------------------------------------------------------------------


def circular_buffer_signal(
    times: Sequence[dt.datetime],
    release_time: dt.datetime,
    release_lon: float,
    release_lat: float,
    target_lon: float,
    target_lat: float,
    growth_rate_m_s: float,
) -> np.ndarray:
    """The simplest baseline: a circle around the outlet growing at a constant
    rate. Value at each time is 1.0 once the circle's radius has reached the
    target point's distance from the release, else 0.0.

    This baseline can only ever produce a `clear_time=None` when run through
    `detect_onset_clear_peak` -- a circle that only grows never un-covers the
    target. That is not a bug in the metric; it is the finding: report the
    baseline's duration error as undefined, not as some invented number.
    """
    distance_m = _meters_between(release_lon, release_lat, target_lon, target_lat)
    elapsed_s = np.array([(t - release_time).total_seconds() for t in times])
    radius_m = np.clip(elapsed_s, 0, None) * growth_rate_m_s
    return (radius_m >= distance_m).astype(np.float64)


def current_only_params(base: ParticleEngineParams) -> ParticleEngineParams:
    """Baseline: current-driven advection only, no windage. Pair with the
    real current interpolator and any wind_fn (it is multiplied by zero)."""
    return replace(base, windage_fraction=0.0)


def wind_only_params(base: ParticleEngineParams) -> ParticleEngineParams:
    """Baseline: wind-driven advection only. Caller must pass
    `ConstantCurrentField(0.0, 0.0)` as `current_fn` -- this function only
    controls the windage weighting, it cannot zero out a real current field
    for you."""
    return replace(base, windage_fraction=1.0)


def fixed_southward_forcing(speed_m_s: float) -> tuple[ConstantCurrentField, ConstantWindField]:
    """Baseline: ignore all real forcing, assume a constant southward current.
    Pair with `windage_fraction=0.0` so the (zero) wind field has no effect."""
    return ConstantCurrentField(0.0, -abs(speed_m_s)), ConstantWindField(0.0, 0.0)


__all__ = [
    "EVENTS_WITHOUT_REAL_OBSERVED_MASK",
    "ObjectiveWeights",
    "SpatialMetricsNotAllowedError",
    "TimingSignal",
    "arrival_time_error_hours",
    "assert_spatial_metrics_allowed",
    "calibration_objective",
    "centroid_distance_m",
    "circular_buffer_signal",
    "concentration_time_series",
    "current_only_params",
    "detect_onset_clear_peak",
    "dice",
    "duration_error_hours",
    "fixed_southward_forcing",
    "iou",
    "peak_timing_error_hours",
    "wind_only_params",
]
