"""Tests for the calibration grid search.

The grid-search *mechanics* (correct minimum selection, trial log shape,
infinite-objective handling) are tested with fully synthetic, deterministic
forcing -- diffusion and settling are held at zero so every trial is
bit-reproducible without depending on a random seed. A second group of tests
reads the real mooring target file this workstream built
(`data/processed/marine/mooring_target_AQ-2016-10-28.json`) to check the
loader against the actual numbers on disk.
"""

from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from models.calibration import (  # noqa: E402
    MOORING_TARGET_PATH,
    load_mooring_target,
    run_calibration_grid_search,
    run_single_trial,
    save_trial_log,
    selected_regime_verdict,
    selected_trial,
)
from models.particle_engine import ConstantCurrentField, ConstantWindField, ReleasePoint  # noqa: E402

RELEASE = ReleasePoint(outlet_id="TEST", lon=35.00, lat=29.50, catchment_id="TEST")
RELEASE_TIME = dt.datetime(2016, 10, 28, 6, 50, tzinfo=dt.timezone.utc)
TARGET_LON, TARGET_LAT = 35.00, 29.490985  # ~1000 m due south of RELEASE


class AlwaysWaterCoastline:
    def in_water(self, lon, lat):
        import numpy as np
        return np.ones(np.shape(lon), dtype=bool)


class FlatBathymetry:
    def __init__(self, depth_m: float):
        self.depth_m_value = depth_m

    def depth_m(self, lon, lat):
        import numpy as np
        return np.full(np.shape(lon), self.depth_m_value, dtype=np.float64)


def _synthetic_target_from_windage(windage: float) -> dict:
    """Build a mooring_target dict whose 'true' timing is exactly whatever a
    windage=`windage` trial reports -- so that same trial can be asserted to
    score a (near-)zero objective and win the grid."""
    from models.backtest_metrics import concentration_time_series, detect_onset_clear_peak
    from models.particle_engine import ParticleEngineParams, simulate

    params = ParticleEngineParams(
        diffusion_m2_s=0.0, windage_fraction=windage, settling_velocity_mm_s=0.0,
        particle_count=5, time_step_minutes=5.0, duration_hours=1.0,
    )
    result = simulate(
        RELEASE, RELEASE_TIME,
        current_fn=ConstantCurrentField(0.0, 0.0),
        wind_fn=ConstantWindField(0.0, -1.0),
        params=params,
        coastline=AlwaysWaterCoastline(),
        bathymetry=FlatBathymetry(200.0),
        seed=0,
    )
    concentration = concentration_time_series(
        result.lons, result.lats, result.active,
        point_lon=TARGET_LON, point_lat=TARGET_LAT, radius_m=200.0,
    )
    signal = detect_onset_clear_peak(result.times, concentration, onset_threshold=0.5)
    assert signal.onset_time is not None and signal.clear_time is not None, (
        "fixture windage must be strong enough to actually cross the target radius "
        "and pass beyond it within the 1 h synthetic run"
    )
    return {
        "_parsed": {
            "onset": signal.onset_time,
            "clear": signal.clear_time,
            "duration_hours": signal.duration_hours,
            "peak": signal.peak_time,
            "lon": TARGET_LON,
            "lat": TARGET_LAT,
        }
    }


GRID_KWARGS = dict(
    current_fn=ConstantCurrentField(0.0, 0.0),
    wind_fn=ConstantWindField(0.0, -1.0),
    coastline=AlwaysWaterCoastline(),
    bathymetry=FlatBathymetry(200.0),
    particle_count=5,
    time_step_minutes=5.0,
    duration_hours=1.0,
    concentration_radius_m=200.0,
    onset_threshold=0.5,
    forcing_is_placeholder=True,
)


def test_grid_search_selects_the_windage_that_matches_the_target():
    target = _synthetic_target_from_windage(1.0)
    trials = run_calibration_grid_search(
        event_id="TEST-EVENT",
        release=RELEASE,
        release_time=RELEASE_TIME,
        mooring_target=target,
        diffusion_grid=[0.0],
        windage_grid=[0.2, 0.5, 1.0],
        settling_grid=[0.0],
        regimes=("hypopycnal",),
        **GRID_KWARGS,
    )
    winner = selected_trial(trials)
    assert winner is not None
    assert winner.windage_fraction == pytest.approx(1.0)
    assert winner.objective == pytest.approx(0.0, abs=1e-9)

    others = [t for t in trials if t.windage_fraction != 1.0]
    assert all(t.objective > winner.objective for t in others)
    assert sum(t.is_selected for t in trials) == 1


def test_grid_search_keeps_non_arriving_trials_with_infinite_objective():
    target = _synthetic_target_from_windage(1.0)
    trials = run_calibration_grid_search(
        event_id="TEST-EVENT",
        release=RELEASE,
        release_time=RELEASE_TIME,
        mooring_target=target,
        diffusion_grid=[0.0],
        windage_grid=[0.0, 1.0],  # windage=0.0 with zero current -> never moves, never arrives
        settling_grid=[0.0],
        regimes=("hypopycnal",),
        **GRID_KWARGS,
    )
    never_arrived = [t for t in trials if t.windage_fraction == 0.0]
    assert len(never_arrived) == 1
    assert math.isinf(never_arrived[0].objective)
    assert never_arrived[0].arrival_time_error_hours is None
    assert never_arrived[0].is_selected is False


def test_grid_search_covers_the_full_cartesian_product():
    target = _synthetic_target_from_windage(1.0)
    trials = run_calibration_grid_search(
        event_id="TEST-EVENT",
        release=RELEASE,
        release_time=RELEASE_TIME,
        mooring_target=target,
        diffusion_grid=[0.0, 0.5],
        windage_grid=[0.5, 1.0],
        settling_grid=[0.0],
        regimes=("hypopycnal", "hyperpycnal"),
        **GRID_KWARGS,
    )
    assert len(trials) == 2 * 2 * 1 * 2  # diffusion x windage x settling x regimes
    assert {t.transport_regime for t in trials} == {"hypopycnal", "hyperpycnal"}


def test_selected_regime_verdict_names_the_winning_regime():
    target = _synthetic_target_from_windage(1.0)
    trials = run_calibration_grid_search(
        event_id="TEST-EVENT",
        release=RELEASE,
        release_time=RELEASE_TIME,
        mooring_target=target,
        diffusion_grid=[0.0],
        windage_grid=[1.0],
        settling_grid=[0.0],
        regimes=("hypopycnal",),
        **GRID_KWARGS,
    )
    verdict = selected_regime_verdict(trials)
    assert "hypopycnal" in verdict


def test_selected_regime_verdict_when_nothing_arrived():
    target = _synthetic_target_from_windage(1.0)
    trials = run_calibration_grid_search(
        event_id="TEST-EVENT",
        release=RELEASE,
        release_time=RELEASE_TIME,
        mooring_target=target,
        diffusion_grid=[0.0],
        windage_grid=[0.0],
        settling_grid=[0.0],
        regimes=("hypopycnal",),
        **GRID_KWARGS,
    )
    assert "no regime selected" in selected_regime_verdict(trials)


def test_save_trial_log_round_trips_through_json(tmp_path):
    target = _synthetic_target_from_windage(1.0)
    trials = run_calibration_grid_search(
        event_id="TEST-EVENT",
        release=RELEASE,
        release_time=RELEASE_TIME,
        mooring_target=target,
        diffusion_grid=[0.0],
        windage_grid=[1.0],
        settling_grid=[0.0],
        regimes=("hypopycnal",),
        **GRID_KWARGS,
    )
    out_path = save_trial_log(trials, tmp_path / "trials.json")
    assert out_path.exists()

    import json
    loaded = json.loads(out_path.read_text())
    assert len(loaded) == len(trials)
    assert loaded[0]["event_id"] == "TEST-EVENT"


# ---------------------------------------------------------------------------
# The real mooring target file
# ---------------------------------------------------------------------------


def test_load_mooring_target_reads_the_real_file():
    target = load_mooring_target(MOORING_TARGET_PATH)
    parsed = target["_parsed"]
    assert parsed["onset"] == dt.datetime(2016, 10, 28, 6, 50, tzinfo=dt.timezone.utc)
    assert parsed["clear"] == dt.datetime(2016, 10, 29, 14, 15, tzinfo=dt.timezone.utc)
    assert parsed["duration_hours"] == pytest.approx(31.42, abs=0.01)
    assert parsed["peak_is_midpoint_placeholder"] is True
    assert target["position"]["uncertainty_radius_m"] == 1500


def test_real_mooring_target_never_computes_spatial_metrics():
    target = load_mooring_target(MOORING_TARGET_PATH)
    assert target["calibration_use"]["never_compute"] == ["iou", "dice", "centroid_distance"]
