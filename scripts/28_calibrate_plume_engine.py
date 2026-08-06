#!/usr/bin/env python3
"""Calibrate the particle engine against the Kalman et al. (2025) mooring record.

05-abd.md Part 2's grid search, run for real: real HYCOM historical currents
(cached, `ingestion.ocean_currents.get_historical_interpolator`), the real
mooring target (`data/processed/marine/mooring_target_AQ-2016-10-28.json`),
released from `calibration.KINNET_CANAL_OUTLET` at the flood-arrival time
parsed from docs/event_dates.md (never hard-coded here, per that file's rule
1). Wind stays `ConstantWindField(0, 0)` -- no historical marine wind source
exists in this repo (`calibration.py`'s own docstring; GFS/GEFS/ECMWF here are
forecast-only, not a 2016 archive) -- every trial is stamped
`forcing_is_placeholder=True` accordingly.

Writes the winning (diffusion, windage, settling, regime) tuple plus the full
trial log to `data/models/plume_calibration.json` -- the sidecar the API reads
at request time (see `plume_calibration.load_calibrated_params` /
`backend/src/api/main.py`), mirroring how `sediment_anchor.json` is read
rather than baked into a model artifact.

Run: .venv/bin/python scripts/28_calibrate_plume_engine.py
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from api.data_access import flood_arrival_utc  # noqa: E402
from ingestion import ocean_currents as oc  # noqa: E402
from models import plume_forcing as pf  # noqa: E402
from models.calibration import (  # noqa: E402
    KINNET_CANAL_OUTLET,
    load_mooring_target,
    run_calibration_grid_search,
    save_trial_log,
    selected_regime_verdict,
    selected_trial,
)
from models.particle_engine import BathymetrySampler, CoastlineBoundary, ConstantWindField  # noqa: E402

EVENT_DATES = PROJECT_ROOT / "docs" / "event_dates.md"
OUTPUT_PATH = PROJECT_ROOT / "data" / "models" / "plume_calibration.json"
TRIAL_LOG_PATH = PROJECT_ROOT / "data" / "models" / "plume_calibration_trials.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event-id", default="AQ-2016-10-28")
    parser.add_argument("--particle-count", type=int, default=300)
    parser.add_argument("--time-step-minutes", type=float, default=20.0)
    parser.add_argument("--duration-hours", type=float, default=48.0)
    args = parser.parse_args()

    release_time = flood_arrival_utc(args.event_id)
    if release_time is None:
        raise KeyError(f"{args.event_id} has no converted.flood_arrival_utc in {EVENT_DATES}")
    print(f"release_time (parsed from {EVENT_DATES.name}): {release_time.isoformat()}")

    if not oc.RAW_DIR.joinpath("hycom_aoi_AQ-2016-10-28.nc").exists():
        print("caching HYCOM historical currents for the demo event window (network, ~1s)...")
        oc.cache_hycom_historical()

    interpolator = oc.get_historical_interpolator(prefer="hycom")
    current_fn = pf.fast_current_fn(interpolator)
    wind_fn = ConstantWindField(0.0, 0.0)

    mooring_target = load_mooring_target()
    coastline = CoastlineBoundary()
    bathymetry = BathymetrySampler()

    # Physically-informed ranges, not a fishing expedition:
    #   diffusion_m2_s   -- O(1-100) m^2/s is the standard range for coastal
    #                       horizontal eddy diffusivity (Okubo 1971-scale
    #                       reasoning for a plume that stays coherent over ~1 km
    #                       and ~1 day, not the open-ocean fit for basin-scale
    #                       patches over weeks).
    #   windage_fraction -- 1-6% of 10 m wind is the conventional range for
    #                       near-surface drift (search-and-rescue / oil-spill
    #                       literature); 0 isolates current-only transport.
    #   settling_velocity_mm_s -- fine silt to fine sand by Stokes law
    #                       (Kalman et al. 2025 describe fine terrigenous mud).
    diffusion_grid = [1.0, 5.0, 20.0, 60.0]
    windage_grid = [0.0, 0.02, 0.04]
    settling_grid = [0.1, 0.5, 2.0]

    n_trials = len(diffusion_grid) * len(windage_grid) * len(settling_grid) * 2
    print(f"running {n_trials} trials ({args.particle_count} particles, "
          f"{args.duration_hours}h @ {args.time_step_minutes}min)...")

    trials = run_calibration_grid_search(
        event_id=args.event_id,
        release=KINNET_CANAL_OUTLET,
        release_time=release_time,
        mooring_target=mooring_target,
        current_fn=current_fn,
        wind_fn=wind_fn,
        diffusion_grid=diffusion_grid,
        windage_grid=windage_grid,
        settling_grid=settling_grid,
        coastline=coastline,
        bathymetry=bathymetry,
        particle_count=args.particle_count,
        time_step_minutes=args.time_step_minutes,
        duration_hours=args.duration_hours,
        forcing_is_placeholder=True,
        seed=0,
    )

    save_trial_log(trials, TRIAL_LOG_PATH)
    winner = selected_trial(trials)
    verdict = selected_regime_verdict(trials)

    if winner is None:
        print("NO trial's particle cloud ever reached the mooring target within "
              f"{args.duration_hours}h -- every trial scored an infinite objective. "
              "Not writing a calibrated-params file; the API keeps its documented "
              "uncalibrated defaults with that caveat stated.")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({
        "event_id": args.event_id,
        "calibrated_against": "Kalman et al. (2025) mooring, Kinnet Canal release point",
        "release_point_used_for_calibration": "KINNET-CANAL-OUTLET (not AQ-O01/AQ-O05 -- "
                                              "see models.calibration docstring)",
        "current_source": "HYCOM GLBu0.08/expt_91.2 historical archive",
        "forcing_is_placeholder": True,
        "forcing_placeholder_reason": "no historical marine wind source in this repo; "
                                       "wind_fn = ConstantWindField(0, 0)",
        "windage_caveat": "wind_fn is identically (0, 0), so every windage_fraction in the "
                           "grid contributes the same zero drift -- this run's winning "
                           "windage_fraction is a tie-break artifact, not a calibrated value. "
                           "Recalibrate once real historical wind (ERA5-Land u10/v10 for this "
                           "window, per models.calibration's own note) is available.",
        "peak_timing_caveat": "the mooring target's peak time is the onset/clear midpoint "
                               "(mooring_target['_parsed']['peak_is_midpoint_placeholder']), "
                               "not a digitized observation -- peak_timing_error_hours is "
                               "measured against that placeholder, not a reported peak.",
        "selected_regime_verdict": verdict,
        "params": {
            "diffusion_m2_s": winner.diffusion_m2_s,
            "windage_fraction": winner.windage_fraction,
            "settling_velocity_mm_s": winner.settling_velocity_mm_s,
            "transport_regime": winner.transport_regime,
        },
        "objective": winner.objective,
        "arrival_time_error_hours": winner.arrival_time_error_hours,
        "duration_error_hours": winner.duration_error_hours,
        "peak_timing_error_hours": winner.peak_timing_error_hours,
        "n_trials": len(trials),
        "trial_log": str(TRIAL_LOG_PATH.relative_to(PROJECT_ROOT)),
    }, indent=2))

    print(f"winner: {json.dumps(asdict(winner), indent=2, default=str)}")
    print(f"verdict: {verdict}")
    print(f"wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
