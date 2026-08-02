"""Calibration grid search against the Kalman et al. (2025) mooring record.

05-abd.md Part 2: grid-search diffusion coefficient x windage x settling
velocity, objective = match arrival time, duration and peak timing at the
mooring, every trial recorded, hypopycnal/hyperpycnal run as a toggle with a
stated verdict on which one the calibration selects.

**Real historical current forcing is not available yet -- this is a discovered
gap, not an oversight.** `ocean_currents.build_interpolator` fetches HYCOM's
public FMRC "best dataset" and Copernicus Marine's `ANALYSISFORECAST` product,
both of which serve a rolling recent/forecast window, not October 2016. Feeding
today's current field into a trial and labelling the result "Oct 2016
calibration" would be exactly the kind of fabricated-precision the project's
own rules forbid (docs/event_dates.md, "no fabricated geometry, ever" applies
equally to no fabricated forcing). A real run needs either a historical HYCOM
archive endpoint or Copernicus Marine's `MULTIYEAR` reanalysis product for
2016-10 -- flagged for Nizar, since ocean forcing sourcing is his workstream.

Until that forcing exists, this module is exercised with a synthetic or
explicitly-supplied `current_fn`/`wind_fn` -- the grid search, the objective
function, and the trial log are real and tested; only the Oct-2016 forcing
input is a placeholder, and every trial log this module writes is stamped
`forcing_is_placeholder` so nobody downstream mistakes a wiring smoke test for
a scientific result.
"""

from __future__ import annotations

import datetime as dt
import itertools
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

from models.backtest_metrics import (
    ObjectiveWeights,
    arrival_time_error_hours,
    calibration_objective,
    concentration_time_series,
    detect_onset_clear_peak,
    duration_error_hours,
    peak_timing_error_hours,
)
from models.particle_engine import (
    BathymetrySampler,
    CoastlineBoundary,
    ParticleEngineParams,
    ReleasePoint,
    TransportRegime,
    simulate,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MOORING_TARGET_PATH = REPO_ROOT / "data" / "processed" / "marine" / "mooring_target_AQ-2016-10-28.json"

#: Kinnet Canal outlet, coastline-snapped -- see docs/mooring_coordinate_derivation.md
#: §3 step 1. This is the release point for CALIBRATION specifically. It is
#: deliberately not AQ-O01: the paper places the canal's discharge on the
#: Eilat (Israel) shoreline, 1.40 km from Mahdi's Jordanian pour point (see
#: the derivation doc §0). AQ-O01/AQ-O05 remain the release points for the
#: forward-looking demo scenario, per 05-abd.md -- a different use of this
#: engine, not this one.
KINNET_CANAL_OUTLET = ReleasePoint(
    outlet_id="KINNET-CANAL-OUTLET",
    lon=34.98336,
    lat=29.53956,
    catchment_id="KINNET-TRANSNATIONAL",
    caveat=(
        "Coastline-snapped from a digitized position in Kalman et al. (2025) Fig. 1b, "
        "not a reported coordinate. Uncertainty radius 1.5 km -- "
        "docs/mooring_coordinate_derivation.md."
    ),
)


def load_mooring_target(path: Path = MOORING_TARGET_PATH) -> dict:
    """Read the structured mooring target and parse its ISO timestamps."""
    payload = json.loads(path.read_text())
    timing = payload["timing_utc"]
    payload["_parsed"] = {
        "onset": dt.datetime.fromisoformat(timing["turbidity_onset"].replace("Z", "+00:00")),
        "clear": dt.datetime.fromisoformat(timing["turbidity_cleared"].replace("Z", "+00:00")),
        "duration_hours": timing["elevated_duration_hours"],
        "lon": payload["position"]["lon"],
        "lat": payload["position"]["lat"],
    }
    # The mooring record (5-minute salinity/turbidity samples) does not, on
    # its own, give us a distinct "peak" timestamp separate from onset/clear
    # without digitizing the full curve (docs/mooring_coordinate_derivation.md
    # digitizes the *position*, not the full time series). Until that curve
    # is digitized, peak timing is compared against the reported peak
    # magnitude's approximate timing: mid-event, i.e. the midpoint between
    # onset and clear. This is a documented placeholder, not a reported time.
    onset, clear = payload["_parsed"]["onset"], payload["_parsed"]["clear"]
    payload["_parsed"]["peak"] = onset + (clear - onset) / 2
    payload["_parsed"]["peak_is_midpoint_placeholder"] = True
    return payload


@dataclass(frozen=True)
class CalibrationTrial:
    """Mirrors the (patched, see docs/schema_proposals/mooring_observations_patch.md)
    `calibration_trials` row shape, plus the mooring-specific columns that
    patch adds."""

    event_id: str
    diffusion_m2_s: float
    windage_fraction: float
    settling_velocity_mm_s: float
    transport_regime: TransportRegime
    arrival_time_error_hours: float | None
    duration_error_hours: float | None
    peak_timing_error_hours: float | None
    objective: float
    is_selected: bool
    forcing_is_placeholder: bool


def run_single_trial(
    *,
    event_id: str,
    release: ReleasePoint,
    release_time: dt.datetime,
    mooring_target: dict,
    current_fn: Callable,
    wind_fn: Callable,
    diffusion_m2_s: float,
    windage_fraction: float,
    settling_velocity_mm_s: float,
    transport_regime: TransportRegime,
    coastline: CoastlineBoundary,
    bathymetry: BathymetrySampler,
    particle_count: int = 300,
    time_step_minutes: float = 30.0,
    duration_hours: float = 48.0,
    onset_threshold: float = 0.05,
    concentration_radius_m: float = 1000.0,
    weights: ObjectiveWeights = ObjectiveWeights(),
    forcing_is_placeholder: bool = True,
    seed: int | None = None,
) -> CalibrationTrial:
    """Run one (diffusion, windage, settling, regime) combination and score
    it against the mooring target. Does not set `is_selected` -- that is a
    property of the whole grid, decided by the caller once every trial in the
    sweep has run."""
    params = ParticleEngineParams(
        diffusion_m2_s=diffusion_m2_s,
        windage_fraction=windage_fraction,
        settling_velocity_mm_s=settling_velocity_mm_s,
        transport_regime=transport_regime,
        particle_count=particle_count,
        time_step_minutes=time_step_minutes,
        duration_hours=duration_hours,
    )
    result = simulate(
        release, release_time, current_fn=current_fn, wind_fn=wind_fn, params=params,
        coastline=coastline, bathymetry=bathymetry, seed=seed,
    )
    target = mooring_target["_parsed"]
    concentration = concentration_time_series(
        result.lons, result.lats, result.active,
        point_lon=target["lon"], point_lat=target["lat"], radius_m=concentration_radius_m,
    )
    signal = detect_onset_clear_peak(result.times, concentration, onset_threshold=onset_threshold)

    arrival_err = arrival_time_error_hours(target["onset"], signal.onset_time)
    duration_err = duration_error_hours(target["duration_hours"], signal.duration_hours)
    peak_err = peak_timing_error_hours(target["peak"], signal.peak_time)
    objective = calibration_objective(arrival_err, duration_err, peak_err, weights=weights)

    return CalibrationTrial(
        event_id=event_id,
        diffusion_m2_s=diffusion_m2_s,
        windage_fraction=windage_fraction,
        settling_velocity_mm_s=settling_velocity_mm_s,
        transport_regime=transport_regime,
        arrival_time_error_hours=arrival_err,
        duration_error_hours=duration_err,
        peak_timing_error_hours=peak_err,
        objective=objective,
        is_selected=False,
        forcing_is_placeholder=forcing_is_placeholder,
    )


def run_calibration_grid_search(
    *,
    event_id: str,
    release: ReleasePoint,
    release_time: dt.datetime,
    mooring_target: dict,
    current_fn: Callable,
    wind_fn: Callable,
    diffusion_grid: Iterable[float],
    windage_grid: Iterable[float],
    settling_grid: Iterable[float],
    regimes: tuple[TransportRegime, ...] = ("hypopycnal", "hyperpycnal"),
    coastline: CoastlineBoundary | None = None,
    bathymetry: BathymetrySampler | None = None,
    forcing_is_placeholder: bool = True,
    **trial_kwargs,
) -> list[CalibrationTrial]:
    """The full sweep. Every combination becomes one row in the returned
    trial log, including ones that score `inf` (never arrived) -- those are
    kept, not dropped, per data-model.md §22.4's "every model run stores its
    parameters".

    Exactly one trial is marked `is_selected=True`: the finite-objective
    minimum. Ties are broken by iteration order (first seen), which is
    deterministic given deterministic grids and a fixed seed -- not
    arbitrary, but also not a claim that the tie was resolved on scientific
    grounds.
    """
    coastline = coastline or CoastlineBoundary()
    bathymetry = bathymetry or BathymetrySampler()

    trials: list[CalibrationTrial] = []
    for diffusion, windage, settling, regime in itertools.product(
        diffusion_grid, windage_grid, settling_grid, regimes
    ):
        trial = run_single_trial(
            event_id=event_id, release=release, release_time=release_time,
            mooring_target=mooring_target, current_fn=current_fn, wind_fn=wind_fn,
            diffusion_m2_s=diffusion, windage_fraction=windage, settling_velocity_mm_s=settling,
            transport_regime=regime, coastline=coastline, bathymetry=bathymetry,
            forcing_is_placeholder=forcing_is_placeholder, **trial_kwargs,
        )
        trials.append(trial)

    finite = [t for t in trials if math.isfinite(t.objective)]
    if finite:
        winner = min(finite, key=lambda t: t.objective)
        winner_index = trials.index(winner)
        trials[winner_index] = CalibrationTrial(**{**asdict(winner), "is_selected": True})

    return trials


def selected_trial(trials: list[CalibrationTrial]) -> CalibrationTrial | None:
    for trial in trials:
        if trial.is_selected:
            return trial
    return None


def selected_regime_verdict(trials: list[CalibrationTrial]) -> str:
    """The stated verdict 05-abd.md asks for: which regime did calibration pick."""
    winner = selected_trial(trials)
    if winner is None:
        return "no trial arrived at the mooring within the grid searched -- no regime selected"
    return (
        f"{winner.transport_regime} (diffusion={winner.diffusion_m2_s} m2/s, "
        f"windage={winner.windage_fraction}, settling={winner.settling_velocity_mm_s} mm/s, "
        f"objective={winner.objective:.3f} h)"
    )


def save_trial_log(trials: list[CalibrationTrial], path: Path) -> Path:
    """Local persistence until `calibration_trials` exists in a live Postgres
    (docs/schema_proposals/mooring_observations_patch.md). One JSON object per
    trial, in the same column shape that table will accept."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(t) for t in trials], indent=2, default=str))
    return path


__all__ = [
    "CalibrationTrial",
    "KINNET_CANAL_OUTLET",
    "MOORING_TARGET_PATH",
    "load_mooring_target",
    "run_calibration_grid_search",
    "run_single_trial",
    "save_trial_log",
    "selected_regime_verdict",
    "selected_trial",
]
