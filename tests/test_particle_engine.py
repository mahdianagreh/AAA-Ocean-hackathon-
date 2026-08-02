"""Tests for the Component F particle engine.

Physics tests (advection, diffusion, settling, regime toggle, reflection,
beaching, contouring) are built entirely from synthetic forcing and synthetic
boundaries -- no project data file is read for those, matching this repo's
convention of proving the maths correct before real data exists. A handful of
integration tests at the bottom load the real `outlets.gpkg`/`coastline.gpkg`/
`depth_utm36n.tif` to check the wiring, since those files already exist on
disk and require no network access.
"""

from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from models.particle_engine import (  # noqa: E402
    BathymetrySampler,
    CoastlineBoundary,
    ConstantCurrentField,
    ConstantWindField,
    HARBOUR_BASIN_OUTLETS,
    HarbourBasinReleaseError,
    OUTLETS_PATH,
    ParticleEngineParams,
    ReleasePoint,
    kernel_density_contours,
    load_release_point,
    particle_count_for_sediment_class,
    simulate,
)

RELEASE_TIME = dt.datetime(2016, 10, 28, 6, 50, tzinfo=dt.timezone.utc)


class AlwaysWaterCoastline:
    """Test double: every point is water. Isolates advection/diffusion/
    settling physics from the reflection logic entirely."""

    def in_water(self, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
        return np.ones(np.shape(lon), dtype=bool)


class HalfPlaneCoastline:
    """Test double: water is lon < boundary_lon, land is lon >= boundary_lon."""

    def __init__(self, boundary_lon: float):
        self.boundary_lon = boundary_lon

    def in_water(self, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
        return np.asarray(lon) < self.boundary_lon


class FlatBathymetry:
    """Test double: constant depth everywhere."""

    def __init__(self, depth_m: float):
        self.depth_m_value = depth_m

    def depth_m(self, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
        return np.full(np.shape(lon), self.depth_m_value, dtype=np.float64)


# ---------------------------------------------------------------------------
# ParticleEngineParams validation
# ---------------------------------------------------------------------------


def test_params_rejects_unknown_transport_regime():
    with pytest.raises(ValueError, match="transport_regime"):
        ParticleEngineParams(transport_regime="surface")  # type: ignore[arg-type]


def test_params_rejects_negative_diffusion():
    with pytest.raises(ValueError, match="diffusion_m2_s"):
        ParticleEngineParams(diffusion_m2_s=-1.0)


def test_params_rejects_negative_settling():
    with pytest.raises(ValueError, match="settling_velocity_mm_s"):
        ParticleEngineParams(settling_velocity_mm_s=-1.0)


def test_params_rejects_bad_beaching_probability():
    with pytest.raises(ValueError, match="beaching_probability"):
        ParticleEngineParams(beaching_probability_per_contact=1.5)


def test_params_to_parameters_jsonb_is_the_request_verbatim():
    params = ParticleEngineParams(diffusion_m2_s=2.5, windage_fraction=0.05)
    payload = params.to_parameters_jsonb()
    assert payload["diffusion_m2_s"] == 2.5
    assert payload["windage_fraction"] == 0.05
    assert payload["engine"] == "custom_2d"


# ---------------------------------------------------------------------------
# Sediment-class release scaling
# ---------------------------------------------------------------------------


def test_particle_count_scaling_orders_by_severity():
    base = 1000
    counts = {
        cls: particle_count_for_sediment_class(base, cls)
        for cls in ("low", "medium", "high", "extreme")
    }
    assert counts["low"] < counts["medium"] < counts["high"] < counts["extreme"]


def test_particle_count_scaling_none_is_unscaled():
    assert particle_count_for_sediment_class(1000, None) == 1000


def test_particle_count_scaling_rejects_unknown_class():
    with pytest.raises(ValueError, match="unknown sediment_class"):
        particle_count_for_sediment_class(1000, "catastrophic")


# ---------------------------------------------------------------------------
# Release point / AQ-O04 refusal
# ---------------------------------------------------------------------------


def test_load_release_point_reads_real_outlet_coordinates():
    point = load_release_point("AQ-O01", outlets_path=OUTLETS_PATH)
    assert point.outlet_id == "AQ-O01"
    assert point.catchment_id == "AQ-C01"
    assert math.isclose(point.lon, 34.97073, abs_tol=1e-3)
    assert math.isclose(point.lat, 29.54560, abs_tol=1e-3)
    assert point.caveat is None


def test_load_release_point_refuses_harbour_outlet_by_default():
    assert "AQ-O04" in HARBOUR_BASIN_OUTLETS
    with pytest.raises(HarbourBasinReleaseError, match="harbour"):
        load_release_point("AQ-O04", outlets_path=OUTLETS_PATH)


def test_load_release_point_allows_harbour_outlet_with_acknowledgement():
    point = load_release_point(
        "AQ-O04", outlets_path=OUTLETS_PATH, acknowledge_harbour_caveat=True
    )
    assert point.outlet_id == "AQ-O04"
    assert point.caveat is not None and "harbour" in point.caveat


def test_load_release_point_unknown_outlet_raises():
    with pytest.raises(KeyError):
        load_release_point("AQ-O99", outlets_path=OUTLETS_PATH)


# ---------------------------------------------------------------------------
# Pure advection -- no diffusion, no windage, no settling, open water
# ---------------------------------------------------------------------------


def test_pure_advection_matches_documented_flat_earth_formula():
    release = ReleasePoint(outlet_id="TEST", lon=34.98, lat=29.50, catchment_id="TEST")
    params = ParticleEngineParams(
        diffusion_m2_s=0.0,
        windage_fraction=0.0,
        settling_velocity_mm_s=0.0,
        particle_count=5,
        time_step_minutes=30.0,
        duration_hours=2.0,  # 4 steps
    )
    u_m_s, v_m_s = 0.5, -0.2
    result = simulate(
        release, RELEASE_TIME,
        current_fn=ConstantCurrentField(u_m_s, v_m_s),
        wind_fn=ConstantWindField(0.0, 0.0),
        params=params,
        coastline=AlwaysWaterCoastline(),
        bathymetry=FlatBathymetry(200.0),
        seed=0,
    )
    dt_seconds = params.time_step_minutes * 60.0
    n_steps = int(params.duration_hours * 3600 / dt_seconds)
    m_per_deg_lat = 110_940.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(release.lat))

    expected_lat = release.lat + n_steps * (v_m_s * dt_seconds) / m_per_deg_lat
    expected_lon = release.lon + n_steps * (u_m_s * dt_seconds) / m_per_deg_lon

    assert np.allclose(result.lats[-1], expected_lat, atol=1e-6)
    assert np.allclose(result.lons[-1], expected_lon, atol=1e-6)
    assert result.active[-1].all()
    assert result.times[0] == RELEASE_TIME
    assert len(result.times) == n_steps + 1


def test_zero_forcing_leaves_particles_at_release_point():
    release = ReleasePoint(outlet_id="TEST", lon=35.0, lat=29.4, catchment_id="TEST")
    params = ParticleEngineParams(
        diffusion_m2_s=0.0, windage_fraction=0.0, settling_velocity_mm_s=0.0,
        particle_count=10, time_step_minutes=15.0, duration_hours=1.0,
    )
    result = simulate(
        release, RELEASE_TIME,
        current_fn=ConstantCurrentField(0.0, 0.0),
        wind_fn=ConstantWindField(0.0, 0.0),
        params=params,
        coastline=AlwaysWaterCoastline(),
        bathymetry=FlatBathymetry(200.0),
        seed=1,
    )
    assert np.allclose(result.lons, release.lon)
    assert np.allclose(result.lats, release.lat)


# ---------------------------------------------------------------------------
# Diffusion -- zero-mean random walk
# ---------------------------------------------------------------------------


def test_diffusion_spreads_particles_with_approximately_zero_mean_drift():
    release = ReleasePoint(outlet_id="TEST", lon=35.0, lat=29.4, catchment_id="TEST")
    params = ParticleEngineParams(
        diffusion_m2_s=5.0, windage_fraction=0.0, settling_velocity_mm_s=0.0,
        particle_count=4000, time_step_minutes=15.0, duration_hours=3.0,
    )
    result = simulate(
        release, RELEASE_TIME,
        current_fn=ConstantCurrentField(0.0, 0.0),
        wind_fn=ConstantWindField(0.0, 0.0),
        params=params,
        coastline=AlwaysWaterCoastline(),
        bathymetry=FlatBathymetry(200.0),
        seed=42,
    )
    final_lon, final_lat = result.lons[-1], result.lats[-1]
    assert np.std(final_lon) > 0
    assert np.std(final_lat) > 0
    # zero-mean forcing -> centroid should stay close to the release point,
    # much closer than the spread of individual particles.
    assert abs(final_lon.mean() - release.lon) < np.std(final_lon)
    assert abs(final_lat.mean() - release.lat) < np.std(final_lat)


# ---------------------------------------------------------------------------
# Settling / regime toggle
# ---------------------------------------------------------------------------


def test_settling_reduces_active_count_monotonically():
    release = ReleasePoint(outlet_id="TEST", lon=35.0, lat=29.4, catchment_id="TEST")
    params = ParticleEngineParams(
        diffusion_m2_s=0.0, windage_fraction=0.0, settling_velocity_mm_s=50.0,
        particle_count=500, time_step_minutes=30.0, duration_hours=6.0,
    )
    result = simulate(
        release, RELEASE_TIME,
        current_fn=ConstantCurrentField(0.1, 0.0),
        wind_fn=ConstantWindField(0.0, 0.0),
        params=params,
        coastline=AlwaysWaterCoastline(),
        bathymetry=FlatBathymetry(5.0),  # shallow -> fast settling
        seed=7,
    )
    counts = result.active_particle_count_per_step
    assert (np.diff(counts) <= 0).all(), "active particle count must never increase"
    assert counts[-1] < counts[0], "some particles must have settled by the end"
    assert result.settled.any()


def test_hyperpycnal_regime_zeroes_windage_effect():
    release = ReleasePoint(outlet_id="TEST", lon=35.0, lat=29.4, catchment_id="TEST")
    shared = dict(
        diffusion_m2_s=0.0, settling_velocity_mm_s=0.0,
        particle_count=3, time_step_minutes=30.0, duration_hours=2.0,
    )
    hyper = ParticleEngineParams(windage_fraction=0.5, transport_regime="hyperpycnal", **shared)
    hypo = ParticleEngineParams(windage_fraction=0.5, transport_regime="hypopycnal", **shared)

    kwargs = dict(
        current_fn=ConstantCurrentField(0.0, 0.0),
        wind_fn=ConstantWindField(2.0, 0.0),
        coastline=AlwaysWaterCoastline(),
        bathymetry=FlatBathymetry(200.0),
        seed=3,
    )
    hyper_result = simulate(release, RELEASE_TIME, params=hyper, **kwargs)
    hypo_result = simulate(release, RELEASE_TIME, params=hypo, **kwargs)

    # hyperpycnal: no current, no diffusion, zero windage multiplier -> no motion at all.
    assert np.allclose(hyper_result.lons[-1], release.lon)
    assert np.allclose(hyper_result.lats[-1], release.lat)
    # hypopycnal: same wind, full windage -> particles must have drifted downwind (+lon).
    assert (hypo_result.lons[-1] > release.lon).all()


# ---------------------------------------------------------------------------
# Reflection / beaching
# ---------------------------------------------------------------------------


def test_reflection_keeps_all_particles_in_water():
    release = ReleasePoint(outlet_id="TEST", lon=34.9, lat=29.4, catchment_id="TEST")
    boundary_lon = 35.0
    params = ParticleEngineParams(
        diffusion_m2_s=0.0, windage_fraction=0.0, settling_velocity_mm_s=0.0,
        particle_count=50, time_step_minutes=30.0, duration_hours=10.0,
        beaching_probability_per_contact=0.0,  # never beach -> must keep bouncing
    )
    result = simulate(
        release, RELEASE_TIME,
        current_fn=ConstantCurrentField(2.0, 0.0),  # strong current straight at the "coast"
        wind_fn=ConstantWindField(0.0, 0.0),
        params=params,
        coastline=HalfPlaneCoastline(boundary_lon),
        bathymetry=FlatBathymetry(200.0),
        seed=11,
    )
    assert (result.lons < boundary_lon).all(), "reflection must never let a particle cross onto land"
    assert not result.beached.any()


def test_beaching_is_certain_when_probability_is_one():
    # release point close enough to the boundary that the very first step's
    # advection alone crosses it (u=2.0 m/s * 1800 s ~= 0.037 deg lon at this
    # latitude), so contact -- and therefore beaching -- happens on step 1.
    release = ReleasePoint(outlet_id="TEST", lon=34.99, lat=29.4, catchment_id="TEST")
    params = ParticleEngineParams(
        diffusion_m2_s=0.0, windage_fraction=0.0, settling_velocity_mm_s=0.0,
        particle_count=20, time_step_minutes=30.0, duration_hours=1.0,  # 2 steps
        beaching_probability_per_contact=1.0,
    )
    result = simulate(
        release, RELEASE_TIME,
        current_fn=ConstantCurrentField(2.0, 0.0),
        wind_fn=ConstantWindField(0.0, 0.0),
        params=params,
        coastline=HalfPlaneCoastline(35.0),
        bathymetry=FlatBathymetry(200.0),
        seed=5,
    )
    # first contact with the boundary must beach every particle immediately
    assert result.beached[1].all()
    assert not result.active[1].any()
    # a beached particle's recorded position must itself still be in water
    assert (result.lons[1] < 35.0).all()


# ---------------------------------------------------------------------------
# Kernel-density contouring
# ---------------------------------------------------------------------------


def test_contour_area_grows_as_threshold_drops():
    rng = np.random.default_rng(0)
    lons = rng.normal(35.0, 0.01, size=500)
    lats = rng.normal(29.5, 0.01, size=500)
    contours = kernel_density_contours(lons, lats, levels=(0.10, 0.5, 0.9), grid_size=60)

    def total_area(polys):
        return sum(p.area for p in polys)

    assert total_area(contours[0.10]) >= total_area(contours[0.5]) >= total_area(contours[0.9])
    assert len(contours[0.10]) > 0, "a tight synthetic cloud must produce at least one contour"


def test_contour_level_above_peak_is_empty_not_fabricated():
    rng = np.random.default_rng(1)
    lons = rng.normal(35.0, 0.01, size=200)
    lats = rng.normal(29.5, 0.01, size=200)
    contours = kernel_density_contours(lons, lats, levels=(1.5,), grid_size=40)
    assert contours[1.5] == []


def test_contour_degenerate_cloud_does_not_raise():
    lons = np.full(50, 35.0)
    lats = np.full(50, 29.5)
    contours = kernel_density_contours(lons, lats, levels=(0.5,), grid_size=40)
    assert contours[0.5] == []


# ---------------------------------------------------------------------------
# Integration smoke tests against real project data (no network access)
# ---------------------------------------------------------------------------


def test_simulate_end_to_end_against_real_coastline_and_bathymetry():
    release = load_release_point("AQ-O01")
    params = ParticleEngineParams(
        diffusion_m2_s=1.0, windage_fraction=0.02, settling_velocity_mm_s=0.3,
        particle_count=30, time_step_minutes=30.0, duration_hours=3.0,
    )
    coastline = CoastlineBoundary()
    bathymetry = BathymetrySampler()
    try:
        result = simulate(
            release, RELEASE_TIME,
            current_fn=ConstantCurrentField(-0.1, -0.05),
            wind_fn=ConstantWindField(1.0, 0.0),
            params=params,
            coastline=coastline,
            bathymetry=bathymetry,
            seed=99,
        )
    finally:
        bathymetry.close()

    n_steps = int(params.duration_hours * 3600 / (params.time_step_minutes * 60))
    assert result.lons.shape == (n_steps + 1, params.particle_count)
    assert result.active_particle_count_per_step[0] == params.particle_count
    assert len(result.times) == n_steps + 1
