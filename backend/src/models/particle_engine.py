"""Custom 2D probabilistic particle engine — sediment plume transport.

Component F (05-abd.md Part 1). Deliberately a lightweight NumPy particle cloud,
not a hydrodynamic model: concept doc §25 lists "team overbuilds full physics"
as medium-probability / high-impact, and the MVP is explicitly scoped to 2D
probabilistic particles. Do not import OpenDrift here.

    particle position at t+1 =
        current-driven advection
        + windage x wind
        + stochastic horizontal diffusion
        + settling / deposition
        + reflection off the coastline

Forcing contract: this module calls `current_fn(lon, lat, time, depth) -> (u, v)`
and `wind_fn(lon, lat, time) -> (u10, v10)`. It never reshapes, transposes, or
renames a coordinate on the caller's output — if that is ever needed, the bug is
in the forcing function, not here (05-abd.md's framing for Nizar's interpolator
applies equally to any wind field passed in). `ocean_currents.build_interpolator`
satisfies the current contract directly.

Two release points are supported per the task: `AQ-O01` (Wadi Yutum, 96% of
discharge) and `AQ-O05` (clean natural wadi, reef offshore). `AQ-O04` is refused
by default — it discharges into an enclosed harbour basin and a simulation from
there produces a confidently wrong plume (see `load_release_point`).
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

import geopandas as gpd
import numpy as np
import rasterio
from scipy.stats import gaussian_kde
from shapely import contains_xy
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union
from rasterio.features import shapes as raster_shapes
from rasterio.transform import from_bounds

REPO_ROOT = Path(__file__).resolve().parents[3]
COASTLINE_PATH = REPO_ROOT / "data" / "processed" / "vectors" / "coastline.gpkg"
DEPTH_PATH = REPO_ROOT / "data" / "processed" / "bathymetry" / "depth_utm36n.tif"
OUTLETS_PATH = REPO_ROOT / "data" / "processed" / "vectors" / "outlets.gpkg"

#: ocean_currents.CurrentFieldInterpolator only resolves 0-50 m depth.
MAX_QUERYABLE_DEPTH_M = 50.0

#: AQ-O04 sits inside an enclosed harbour basin (05-abd.md, data_dictionary.md
#: §"Outlet positions"). Sediment released there settles in the basin instead
#: of dispersing into the Gulf -- a confidently wrong plume.
HARBOUR_BASIN_OUTLETS = frozenset({"AQ-O04"})

DEFAULT_RELEASE_OUTLETS = ("AQ-O01", "AQ-O05")

TransportRegime = Literal["hypopycnal", "hyperpycnal"]

#: Katz et al. (2015): hyperpycnal (bottom-hugging) flow is decoupled from
#: wind-driven surface drift. Documented modelling assumption, not a measurement.
REGIME_WINDAGE_MULTIPLIER: dict[TransportRegime, float] = {
    "hypopycnal": 1.0,
    "hyperpycnal": 0.0,
}

#: Hyperpycnal particles are modelled as already riding near the bed, so the
#: "distance left to settle" is a small residual rather than the full water
#: column. This is a documented simplification, not a derived number -- it
#: exists so the settling-probability formula in `_step_settling` has a finite
#: effective height for the hyperpycnal branch instead of double counting the
#: full local depth for a particle that is, by construction, already at the bed.
HYPERPYCNAL_EFFECTIVE_HEIGHT_M = 2.0

#: Sediment-class release scaling (05-abd.md: "Release magnitude scaled by
#: Mahdi's sediment class for the event"). Placeholder multipliers -- swap for
#: Mahdi's real per-event value the moment Component D lands; the values here
#: only need to preserve ordering (more sediment -> more particles) until then.
SEDIMENT_CLASS_PARTICLE_SCALE = {
    "low": 0.5,
    "medium": 1.0,
    "high": 1.5,
    "extreme": 2.0,
}


class HarbourBasinReleaseError(ValueError):
    """Raised when AQ-O04 is requested without explicitly acknowledging the caveat."""


@dataclass(frozen=True)
class ParticleEngineParams:
    """Mirrors the `simulation_runs` columns in data-model.md so a run's
    parameters serialize directly into that table (once it is live)."""

    diffusion_m2_s: float = 1.0
    windage_fraction: float = 0.03
    settling_velocity_mm_s: float = 0.5
    transport_regime: TransportRegime = "hypopycnal"
    particle_count: int = 2000
    time_step_minutes: float = 15.0
    duration_hours: float = 48.0
    beaching_probability_per_contact: float = 0.15
    engine: str = "custom_2d"

    def __post_init__(self) -> None:
        if self.transport_regime not in REGIME_WINDAGE_MULTIPLIER:
            raise ValueError(
                f"transport_regime must be one of {sorted(REGIME_WINDAGE_MULTIPLIER)}, "
                f"got {self.transport_regime!r}"
            )
        if self.diffusion_m2_s < 0 or self.settling_velocity_mm_s < 0:
            raise ValueError("diffusion_m2_s and settling_velocity_mm_s must be >= 0.")
        if self.particle_count < 1:
            raise ValueError("particle_count must be >= 1.")
        if self.time_step_minutes <= 0 or self.duration_hours <= 0:
            raise ValueError("time_step_minutes and duration_hours must be > 0.")
        if not 0.0 <= self.beaching_probability_per_contact <= 1.0:
            raise ValueError("beaching_probability_per_contact must be in [0, 1].")

    def to_parameters_jsonb(self) -> dict:
        """The request verbatim, for `simulation_runs.parameters` -- reproducibility."""
        return {
            "diffusion_m2_s": self.diffusion_m2_s,
            "windage_fraction": self.windage_fraction,
            "settling_velocity_mm_s": self.settling_velocity_mm_s,
            "transport_regime": self.transport_regime,
            "particle_count": self.particle_count,
            "time_step_minutes": self.time_step_minutes,
            "duration_hours": self.duration_hours,
            "beaching_probability_per_contact": self.beaching_probability_per_contact,
            "engine": self.engine,
        }


def particle_count_for_sediment_class(base_count: int, sediment_class: str | None) -> int:
    """Scale release magnitude by Mahdi's sediment class for the event.

    `sediment_class=None` (Component D not run yet for this event) keeps the
    base count unscaled -- an explicit, visible default rather than a silent
    guess at severity.
    """
    if sediment_class is None:
        return base_count
    if sediment_class not in SEDIMENT_CLASS_PARTICLE_SCALE:
        raise ValueError(
            f"unknown sediment_class {sediment_class!r}; expected one of "
            f"{sorted(SEDIMENT_CLASS_PARTICLE_SCALE)} (matches runoff_predictions.sediment_class)"
        )
    return max(1, round(base_count * SEDIMENT_CLASS_PARTICLE_SCALE[sediment_class]))


@dataclass(frozen=True)
class ReleasePoint:
    outlet_id: str
    lon: float
    lat: float
    catchment_id: str
    caveat: str | None = None


def load_release_point(
    outlet_id: str, *, outlets_path: Path = OUTLETS_PATH, acknowledge_harbour_caveat: bool = False
) -> ReleasePoint:
    """Read a real outlet coordinate from Mahdi's `outlets.gpkg`.

    Refuses `AQ-O04` by default -- see `HARBOUR_BASIN_OUTLETS`. Pass
    `acknowledge_harbour_caveat=True` to allow it anyway (e.g. to demonstrate
    the caveat itself); the returned `ReleasePoint.caveat` then carries the
    warning so it travels with the result rather than living only in a comment.
    """
    if outlet_id in HARBOUR_BASIN_OUTLETS and not acknowledge_harbour_caveat:
        raise HarbourBasinReleaseError(
            f"{outlet_id} discharges into an enclosed harbour basin -- sediment settles in "
            "the basin rather than dispersing into the Gulf, producing a confidently wrong "
            "plume (05-abd.md). Pass acknowledge_harbour_caveat=True if this is deliberate."
        )
    gdf = gpd.read_file(outlets_path)
    match = gdf[gdf["outlet_id"] == outlet_id]
    if match.empty:
        raise KeyError(f"{outlet_id!r} not found in {outlets_path}")
    row = match.iloc[0]
    caveat = (
        "AQ-O04 discharges into an enclosed harbour basin; this run is not representative "
        "of open-Gulf dispersion. See 05-abd.md."
        if outlet_id in HARBOUR_BASIN_OUTLETS
        else None
    )
    return ReleasePoint(
        outlet_id=outlet_id,
        lon=float(row["lon"]),
        lat=float(row["lat"]),
        catchment_id=str(row["catchment_id"]),
        caveat=caveat,
    )


class ConstantCurrentField:
    """A uniform, time-invariant current -- for calibration smoke tests and
    unit tests, never for a real run. Same call signature as
    `ocean_currents.CurrentFieldInterpolator` so it is a drop-in substitute."""

    def __init__(self, u_m_s: float, v_m_s: float):
        self.u_m_s = u_m_s
        self.v_m_s = v_m_s

    def __call__(self, lon: float, lat: float, time, depth: float = 0.0) -> tuple[float, float]:
        return self.u_m_s, self.v_m_s


class ConstantWindField:
    """Same role as `ConstantCurrentField`, for the wind term. A real field
    (e.g. cached GFS/ECMWF 10 m u10/v10) is a drop-in replacement -- this
    module only requires `wind_fn(lon, lat, time) -> (u10, v10)`."""

    def __init__(self, u10_m_s: float = 0.0, v10_m_s: float = 0.0):
        self.u10_m_s = u10_m_s
        self.v10_m_s = v10_m_s

    def __call__(self, lon: float, lat: float, time) -> tuple[float, float]:
        return self.u10_m_s, self.v10_m_s


class CoastlineBoundary:
    """Wraps Pulga's `coastline.gpkg` (water polygon + shoreline) for fast,
    vectorized "is this point in water" checks, and the geometry a reflection
    step needs. Loaded once per simulation, not per step."""

    def __init__(self, coastline_path: Path = COASTLINE_PATH):
        water = gpd.read_file(coastline_path, layer="water")
        if water.crs is None or str(water.crs).upper() != "EPSG:4326":
            water = water.to_crs("EPSG:4326")
        self._water_geom = unary_union(water.geometry.values)

    def in_water(self, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
        """Vectorized point-in-water test via shapely 2.x `contains_xy`."""
        return contains_xy(self._water_geom, lon, lat)

    @property
    def water_geometry(self):
        return self._water_geom


class BathymetrySampler:
    """Wraps Pulga's `depth_utm36n.tif` for point depth queries. Returns
    positive-down depth in metres; NaN where the raster has no data (e.g. on
    land), which callers must treat as "unknown", never as zero depth."""

    def __init__(self, depth_path: Path = DEPTH_PATH):
        self._src = rasterio.open(depth_path)
        self._band = self._src.read(1)
        self._nodata = self._src.nodata

    def depth_m(self, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
        """Positive depth in metres (the raster stores negative-down elevation)."""
        pts = gpd.GeoSeries(gpd.points_from_xy(lon, lat), crs="EPSG:4326").to_crs(self._src.crs)
        depths = np.full(len(pts), np.nan, dtype=np.float64)
        for i, pt in enumerate(pts):
            try:
                row, col = self._src.index(pt.x, pt.y)
                if row < 0 or col < 0 or row >= self._band.shape[0] or col >= self._band.shape[1]:
                    continue
                val = self._band[row, col]
            except (IndexError, ValueError):
                continue
            if self._nodata is not None and val == self._nodata:
                continue
            depths[i] = -val  # raster is negative-down; depth is positive-down
        return depths

    def close(self) -> None:
        self._src.close()


@dataclass
class SimulationResult:
    """What a run produces. `lons`/`lats`/`active` are shaped
    (n_steps + 1, particle_count) -- row 0 is the release instant.
    Trajectories belong in Storage as Parquet (data-model.md); this object is
    the in-memory form before that write happens."""

    times: list[dt.datetime]
    lons: np.ndarray
    lats: np.ndarray
    active: np.ndarray  # bool, True while still advecting (not settled/beached)
    settled: np.ndarray  # bool, True once permanently deposited
    beached: np.ndarray  # bool, True once permanently stuck at the shore
    params: ParticleEngineParams
    release: ReleasePoint

    @property
    def active_particle_count_per_step(self) -> np.ndarray:
        return self.active.sum(axis=1)


def _meters_to_degrees(dx_m: np.ndarray, dy_m: np.ndarray, lat_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Local flat-earth conversion, adequate for single-timestep displacements
    at this scale (kilometres, not hundreds of km)."""
    m_per_deg_lat = 110_940.0
    m_per_deg_lon = 111_320.0 * np.cos(np.radians(lat_deg))
    m_per_deg_lon = np.where(np.abs(m_per_deg_lon) < 1e-6, 1e-6, m_per_deg_lon)
    return dx_m / m_per_deg_lon, dy_m / m_per_deg_lat


def simulate(
    release: ReleasePoint,
    release_time: dt.datetime,
    current_fn: Callable[[float, float, dt.datetime, float], tuple[float, float]],
    wind_fn: Callable[[float, float, dt.datetime], tuple[float, float]],
    params: ParticleEngineParams,
    *,
    coastline: CoastlineBoundary | None = None,
    bathymetry: BathymetrySampler | None = None,
    seed: int | None = None,
) -> SimulationResult:
    """Advance `params.particle_count` particles from `release` for
    `params.duration_hours`, at `params.time_step_minutes` resolution.

    All particles start at the exact release point (a point release, per
    05-abd.md); spread comes entirely from the physics, not from a scattered
    initial condition.
    """
    rng = np.random.default_rng(seed)
    n = params.particle_count
    dt_seconds = params.time_step_minutes * 60.0
    n_steps = int(round(params.duration_hours * 3600.0 / dt_seconds))

    coastline = coastline or CoastlineBoundary()
    bathymetry = bathymetry or BathymetrySampler()

    lons = np.full((n_steps + 1, n), release.lon, dtype=np.float64)
    lats = np.full((n_steps + 1, n), release.lat, dtype=np.float64)
    active = np.ones((n_steps + 1, n), dtype=bool)
    settled = np.zeros((n_steps + 1, n), dtype=bool)
    beached = np.zeros((n_steps + 1, n), dtype=bool)
    times = [release_time]

    windage = params.windage_fraction * REGIME_WINDAGE_MULTIPLIER[params.transport_regime]
    diffusion_sigma_m = math.sqrt(2.0 * params.diffusion_m2_s * dt_seconds)
    settling_velocity_m_s = params.settling_velocity_mm_s / 1000.0

    for step in range(1, n_steps + 1):
        t = release_time + dt.timedelta(seconds=dt_seconds * step)
        times.append(t)

        prev_lon, prev_lat = lons[step - 1].copy(), lats[step - 1].copy()
        was_active = active[step - 1].copy()
        idx = np.where(was_active)[0]

        # carry forward state for inactive particles unchanged
        lons[step], lats[step] = prev_lon, prev_lat
        active[step], settled[step], beached[step] = active[step - 1], settled[step - 1], beached[step - 1]

        if idx.size == 0:
            continue

        query_depth = np.zeros(idx.size)
        if params.transport_regime == "hyperpycnal":
            local_depth = bathymetry.depth_m(prev_lon[idx], prev_lat[idx])
            query_depth = np.clip(np.nan_to_num(local_depth, nan=MAX_QUERYABLE_DEPTH_M), 0, MAX_QUERYABLE_DEPTH_M)

        u = np.empty(idx.size)
        v = np.empty(idx.size)
        wu = np.empty(idx.size)
        wv = np.empty(idx.size)
        for k, i in enumerate(idx):
            u[k], v[k] = current_fn(prev_lon[i], prev_lat[i], t, float(query_depth[k]) if query_depth.size else 0.0)
            wu[k], wv[k] = wind_fn(prev_lon[i], prev_lat[i], t)

        u = np.nan_to_num(u, nan=0.0)
        v = np.nan_to_num(v, nan=0.0)

        dx_m = (u + windage * wu) * dt_seconds
        dy_m = (v + windage * wv) * dt_seconds

        if diffusion_sigma_m > 0:
            dx_m = dx_m + rng.normal(0.0, diffusion_sigma_m, size=idx.size)
            dy_m = dy_m + rng.normal(0.0, diffusion_sigma_m, size=idx.size)

        dlon, dlat = _meters_to_degrees(dx_m, dy_m, prev_lat[idx])
        cand_lon = prev_lon[idx] + dlon
        cand_lat = prev_lat[idx] + dlat

        in_water = coastline.in_water(cand_lon, cand_lat)
        final_lon = np.where(in_water, cand_lon, prev_lon[idx])
        final_lat = np.where(in_water, cand_lat, prev_lat[idx])

        blocked = ~in_water
        newly_beached = np.zeros(idx.size, dtype=bool)
        if blocked.any():
            roll = rng.random(idx.size)
            newly_beached = blocked & (roll < params.beaching_probability_per_contact)

        # settling: probability of reaching the bed this step given local depth
        if params.transport_regime == "hyperpycnal":
            effective_height = np.full(idx.size, HYPERPYCNAL_EFFECTIVE_HEIGHT_M)
        else:
            depth_now = bathymetry.depth_m(final_lon, final_lat)
            effective_height = np.nan_to_num(depth_now, nan=MAX_QUERYABLE_DEPTH_M)
            effective_height = np.clip(effective_height, 0.5, None)

        newly_settled = np.zeros(idx.size, dtype=bool)
        if settling_velocity_m_s > 0:
            p_settle = np.clip(settling_velocity_m_s * dt_seconds / effective_height, 0.0, 1.0)
            newly_settled = rng.random(idx.size) < p_settle

        lons[step][idx] = final_lon
        lats[step][idx] = final_lat
        beached[step][idx] = newly_beached
        settled[step][idx] = newly_settled
        active[step][idx] = ~(newly_beached | newly_settled)

    return SimulationResult(
        times=times, lons=lons, lats=lats, active=active, settled=settled, beached=beached,
        params=params, release=release,
    )


def kernel_density_contours(
    lons: np.ndarray,
    lats: np.ndarray,
    *,
    levels: tuple[float, ...] = (0.10, 0.25, 0.50, 0.75),
    grid_size: int = 200,
    padding_deg: float = 0.02,
) -> dict[float, list[Polygon]]:
    """Kernel-density probability field for one timestep's particle cloud,
    contoured at `levels`.

    The density is peak-normalized (max cell = 1.0) before contouring. **This
    is a relative density, not a calibrated arrival probability** -- the same
    honesty distinction plume_segmentation.anomaly_to_probability already
    documents for the (unrelated, satellite-derived) plume raster. Never
    present it as "probability this location floods" without that caveat.

    Returns `{level: [Polygon, ...]}` in EPSG:4326. An empty list for a level
    means no cell reached that density -- report it as such, not as zero
    polygons standing in for "no data".
    """
    if lons.size < 2:
        return {lvl: [] for lvl in levels}

    xmin, xmax = lons.min() - padding_deg, lons.max() + padding_deg
    ymin, ymax = lats.min() - padding_deg, lats.max() + padding_deg
    if xmax <= xmin or ymax <= ymin:
        return {lvl: [] for lvl in levels}

    try:
        kde = gaussian_kde(np.vstack([lons, lats]))
    except np.linalg.LinAlgError:
        # degenerate cloud (all particles coincident) -- KDE is undefined
        return {lvl: [] for lvl in levels}

    grid_x, grid_y = np.meshgrid(
        np.linspace(xmin, xmax, grid_size), np.linspace(ymin, ymax, grid_size)
    )
    density = kde(np.vstack([grid_x.ravel(), grid_y.ravel()])).reshape(grid_x.shape)
    peak = density.max()
    if peak <= 0:
        return {lvl: [] for lvl in levels}
    normalized = density / peak

    transform = from_bounds(xmin, ymin, xmax, ymax, grid_size, grid_size)
    # raster row 0 is the top (max y); meshgrid row 0 is ymin, so flip.
    normalized = np.flipud(normalized)

    result: dict[float, list[Polygon]] = {}
    for level in levels:
        mask = (normalized >= level).astype(np.uint8)
        polygons = [
            shape(geom)
            for geom, value in raster_shapes(mask, mask=mask.astype(bool), transform=transform)
            if value == 1
        ]
        result[level] = polygons
    return result


__all__ = [
    "BathymetrySampler",
    "CoastlineBoundary",
    "ConstantCurrentField",
    "ConstantWindField",
    "DEFAULT_RELEASE_OUTLETS",
    "HARBOUR_BASIN_OUTLETS",
    "HarbourBasinReleaseError",
    "ParticleEngineParams",
    "ReleasePoint",
    "SimulationResult",
    "kernel_density_contours",
    "load_release_point",
    "particle_count_for_sediment_class",
    "simulate",
]
