"""Synthetic tests for the backtest metrics module.

Everything here is built from hand-constructed arrays and geometries. No
simulation is run and no real mooring or observed-mask file is read -- this
proves the metric maths correct on its own, per 05-abd.md's explicit
instruction to unit-test this module "against synthetic inputs early, so that
on the day both real sides exist it is one command."
"""

from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import box

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from models.backtest_metrics import (  # noqa: E402
    EVENTS_WITHOUT_REAL_OBSERVED_MASK,
    ObjectiveWeights,
    SpatialMetricsNotAllowedError,
    arrival_time_error_hours,
    assert_spatial_metrics_allowed,
    calibration_objective,
    centroid_distance_m,
    circular_buffer_signal,
    concentration_time_series,
    current_only_params,
    detect_onset_clear_peak,
    dice,
    duration_error_hours,
    fixed_southward_forcing,
    iou,
    peak_timing_error_hours,
    wind_only_params,
)
from models.particle_engine import ConstantCurrentField, ParticleEngineParams  # noqa: E402

T0 = dt.datetime(2016, 10, 28, 6, 50, tzinfo=dt.timezone.utc)


def _times(n: int, step_minutes: float = 30.0) -> list[dt.datetime]:
    return [T0 + dt.timedelta(minutes=step_minutes * i) for i in range(n)]


# ---------------------------------------------------------------------------
# concentration_time_series
# ---------------------------------------------------------------------------


def test_concentration_time_series_counts_particles_within_radius():
    # 2 timesteps, 4 particles. At t=0 all 4 are at the target point; at t=1
    # two have drifted far away.
    lons = np.array([
        [35.00, 35.00, 35.00, 35.00],
        [35.00, 35.00, 35.50, 35.50],
    ])
    lats = np.array([
        [29.50, 29.50, 29.50, 29.50],
        [29.50, 29.50, 29.50, 29.50],
    ])
    active = np.ones_like(lons, dtype=bool)
    frac = concentration_time_series(lons, lats, active, point_lon=35.00, point_lat=29.50, radius_m=1000)
    assert frac[0] == pytest.approx(1.0)
    assert frac[1] == pytest.approx(0.5)


def test_concentration_time_series_denominator_is_original_release_not_active_count():
    # 3 particles at the target, one becomes inactive (settled/beached) at t=1
    # -- the fraction must drop, not renormalize to 1.0 over the remaining 2.
    lons = np.full((2, 3), 35.00)
    lats = np.full((2, 3), 29.50)
    active = np.array([[True, True, True], [False, True, True]])
    frac = concentration_time_series(lons, lats, active, point_lon=35.00, point_lat=29.50, radius_m=500)
    assert frac[0] == pytest.approx(1.0)
    assert frac[1] == pytest.approx(2.0 / 3.0)


def test_concentration_time_series_rejects_empty_particle_set():
    with pytest.raises(ValueError, match="no particles"):
        concentration_time_series(
            np.zeros((2, 0)), np.zeros((2, 0)), np.zeros((2, 0), dtype=bool),
            point_lon=35.0, point_lat=29.5, radius_m=100,
        )


# ---------------------------------------------------------------------------
# detect_onset_clear_peak
# ---------------------------------------------------------------------------


def test_detect_onset_clear_peak_normal_rise_and_fall():
    times = _times(6)
    values = np.array([0.0, 0.2, 0.9, 0.5, 0.1, 0.0])
    signal = detect_onset_clear_peak(times, values, onset_threshold=0.3)
    assert signal.onset_time == times[2]
    assert signal.peak_time == times[2]
    assert signal.peak_value == pytest.approx(0.9)
    assert signal.clear_time == times[4]
    assert signal.duration_hours == pytest.approx((times[4] - times[2]).total_seconds() / 3600.0)


def test_detect_onset_clear_peak_never_crosses_threshold_is_all_none():
    times = _times(5)
    values = np.array([0.0, 0.05, 0.1, 0.05, 0.0])
    signal = detect_onset_clear_peak(times, values, onset_threshold=0.3)
    assert signal.onset_time is None
    assert signal.peak_time is None
    assert signal.clear_time is None
    assert signal.duration_hours is None


def test_detect_onset_clear_peak_monotonic_rise_never_clears():
    """The circular-buffer baseline's shape: 0 then a step up to 1, forever."""
    times = _times(5)
    values = np.array([0.0, 0.0, 1.0, 1.0, 1.0])
    signal = detect_onset_clear_peak(times, values, onset_threshold=0.5)
    assert signal.onset_time == times[2]
    assert signal.clear_time is None
    assert signal.duration_hours is None


def test_detect_onset_clear_peak_rejects_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        detect_onset_clear_peak(_times(3), np.array([0.0, 1.0]), onset_threshold=0.5)


# ---------------------------------------------------------------------------
# Error metrics
# ---------------------------------------------------------------------------


def test_arrival_time_error_sign_convention_late_is_positive():
    observed = T0
    simulated = T0 + dt.timedelta(hours=2)
    assert arrival_time_error_hours(observed, simulated) == pytest.approx(2.0)


def test_arrival_time_error_sign_convention_early_is_negative():
    observed = T0
    simulated = T0 - dt.timedelta(hours=1.5)
    assert arrival_time_error_hours(observed, simulated) == pytest.approx(-1.5)


def test_arrival_time_error_none_when_never_arrived():
    assert arrival_time_error_hours(T0, None) is None
    assert arrival_time_error_hours(None, T0) is None


def test_duration_error_none_when_either_side_undefined():
    assert duration_error_hours(31.4, None) is None
    assert duration_error_hours(None, 10.0) is None
    assert duration_error_hours(31.4, 28.0) == pytest.approx(28.0 - 31.4)


def test_peak_timing_error_matches_arrival_convention():
    observed = T0 + dt.timedelta(hours=10)
    simulated = T0 + dt.timedelta(hours=9)
    assert peak_timing_error_hours(observed, simulated) == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# calibration_objective
# ---------------------------------------------------------------------------


def test_calibration_objective_default_equal_weights():
    value = calibration_objective(2.0, -3.0, 1.0)
    assert value == pytest.approx(2.0 + 3.0 + 1.0)


def test_calibration_objective_respects_custom_weights():
    weights = ObjectiveWeights(arrival=2.0, duration=0.5, peak_timing=1.0)
    value = calibration_objective(1.0, 2.0, 3.0, weights=weights)
    assert value == pytest.approx(2.0 * 1.0 + 0.5 * 2.0 + 1.0 * 3.0)


def test_calibration_objective_is_infinite_when_any_component_missing():
    assert calibration_objective(None, 1.0, 1.0) == math.inf
    assert calibration_objective(1.0, None, 1.0) == math.inf
    assert calibration_objective(1.0, 1.0, None) == math.inf


# ---------------------------------------------------------------------------
# Spatial-metrics gate
# ---------------------------------------------------------------------------


def test_spatial_metrics_refused_for_the_artifact_event():
    assert "AQ-2016-10-28" in EVENTS_WITHOUT_REAL_OBSERVED_MASK
    with pytest.raises(SpatialMetricsNotAllowedError, match="documented coastline artifact"):
        assert_spatial_metrics_allowed("AQ-2016-10-28")


def test_spatial_metrics_allowed_for_an_event_not_on_the_list():
    assert_spatial_metrics_allowed("AQ-2099-01-01")  # must not raise


def test_iou_and_dice_and_centroid_distance_on_known_squares():
    a = box(0, 0, 10, 10)   # area 100
    b = box(5, 0, 15, 10)   # area 100, overlap 50
    assert iou(a, b) == pytest.approx(50 / 150)
    assert dice(a, b) == pytest.approx(2 * 50 / 200)
    assert centroid_distance_m(a, b) == pytest.approx(5.0)


def test_iou_dice_zero_for_disjoint_geometries():
    a = box(0, 0, 1, 1)
    b = box(100, 100, 101, 101)
    assert iou(a, b) == 0.0
    assert dice(a, b) == 0.0


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


def test_circular_buffer_signal_steps_up_at_the_correct_time():
    release_lon, release_lat = 34.97, 29.55
    target_lon, target_lat = 34.97, 29.50  # ~5.5 km south at this latitude
    growth_rate = 1.0  # m/s
    times = _times(200, step_minutes=10.0)
    signal = circular_buffer_signal(
        times, T0, release_lon, release_lat, target_lon, target_lat, growth_rate_m_s=growth_rate,
    )
    assert signal[0] == 0.0
    assert signal[-1] == 1.0
    # monotonic: once covered, always covered (a circle never shrinks)
    assert (np.diff(signal) >= 0).all()


def test_circular_buffer_baseline_has_no_clear_time_therefore_no_duration():
    """The reportable finding: a growing circle cannot predict a duration."""
    times = _times(50, step_minutes=30.0)
    signal = circular_buffer_signal(
        times, T0, 34.97, 29.55, 34.97, 29.50, growth_rate_m_s=5.0,
    )
    detected = detect_onset_clear_peak(times, signal, onset_threshold=0.5)
    assert detected.onset_time is not None
    assert detected.clear_time is None
    assert detected.duration_hours is None


def test_current_only_params_zeroes_windage_and_preserves_other_fields():
    base = ParticleEngineParams(diffusion_m2_s=2.0, windage_fraction=0.5, settling_velocity_mm_s=1.0)
    result = current_only_params(base)
    assert result.windage_fraction == 0.0
    assert result.diffusion_m2_s == 2.0
    assert result.settling_velocity_mm_s == 1.0


def test_wind_only_params_sets_full_windage():
    base = ParticleEngineParams(windage_fraction=0.1)
    result = wind_only_params(base)
    assert result.windage_fraction == 1.0


def test_fixed_southward_forcing_returns_zero_eastward_negative_northward():
    current, wind = fixed_southward_forcing(speed_m_s=1.5)
    u, v = current(35.0, 29.5, T0)
    assert u == pytest.approx(0.0)
    assert v == pytest.approx(-1.5)
    wu, wv = wind(35.0, 29.5, T0)
    assert (wu, wv) == (0.0, 0.0)


def test_fixed_southward_forcing_takes_absolute_value_of_speed():
    current, _ = fixed_southward_forcing(speed_m_s=-2.0)
    _, v = current(35.0, 29.5, T0)
    assert v == pytest.approx(-2.0)
