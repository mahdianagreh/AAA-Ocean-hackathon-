"""
Bridge: local SQLite exposure audit trail -> `simulation_runs` + `reef_exposures`.

`exposure/store.py` deliberately writes to local SQLite, not Postgres, so the
audit trail survives a demo with no network and no credentials (see its
docstring). Postgres is the durable, team-queryable copy of the same runs —
per that same docstring, whether the audit trail should ALSO live in Postgres
"is a deliberate call to make with Nizar, not something to switch silently" in
`store.py` itself. This loader is that call, made as a periodic batch bridge,
never as a change to the live request path in `main.py` (which explicitly
never opens a database connection).

Run this AFTER exercising `/exposure/calculate` for the outlets/zones you want
durable — it reads whatever is currently in the local SQLite file
(REEFSHIELD_EXPOSURE_DB, default data/outputs/exposure_runs.sqlite) via
`store.recent_runs()`/`store.get_run()`, reused directly rather than
re-implementing SQLite reads.

Scope: `simulation_runs` rows created here are bridge markers for a SQLite-
recorded exposure computation, not real particle-engine transport runs — no
real current/wind forcing produced these plumes (`plume_source` is
`SYNTHETIC_STUB` for every run today), so `current_source_id`/`wind_source_id`
are left NULL rather than fabricated. Full `simulation_runs` population from a
real transport run is Abd's task once his engine is wired to real currents.
"""

from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import text

from src.db.client import session_scope

DEMO_EVENT_ID = "AQ-2016-10-28"

UPSERT_SIMULATION_RUN_SQL = text(
    """
    INSERT INTO simulation_runs (
        id, event_id, outlet_id, mode, engine, release_time, status, parameters
    ) VALUES (
        :id, :event_id, :outlet_id, :mode, :engine, :release_time, :status, :parameters
    )
    ON CONFLICT (id) DO UPDATE SET
        event_id = EXCLUDED.event_id,
        outlet_id = EXCLUDED.outlet_id,
        mode = EXCLUDED.mode,
        engine = EXCLUDED.engine,
        release_time = EXCLUDED.release_time,
        status = EXCLUDED.status,
        parameters = EXCLUDED.parameters
    """
)

UPSERT_REEF_EXPOSURE_SQL = text(
    """
    INSERT INTO reef_exposures (
        run_id, reef_zone_id, max_exposure_probability, overlap_km2_at_max,
        exposure_duration_hours, arrival_start, arrival_end,
        arrival_window_hours_low, arrival_window_hours_high, risk_score,
        risk_level, confidence, formula_terms
    ) VALUES (
        :run_id, :reef_zone_id, :max_exposure_probability, :overlap_km2_at_max,
        :exposure_duration_hours, :arrival_start, :arrival_end,
        :arrival_window_hours_low, :arrival_window_hours_high, :risk_score,
        :risk_level, :confidence, :formula_terms
    )
    ON CONFLICT (run_id, reef_zone_id) DO UPDATE SET
        max_exposure_probability = EXCLUDED.max_exposure_probability,
        overlap_km2_at_max = EXCLUDED.overlap_km2_at_max,
        exposure_duration_hours = EXCLUDED.exposure_duration_hours,
        arrival_start = EXCLUDED.arrival_start,
        arrival_end = EXCLUDED.arrival_end,
        arrival_window_hours_low = EXCLUDED.arrival_window_hours_low,
        arrival_window_hours_high = EXCLUDED.arrival_window_hours_high,
        risk_score = EXCLUDED.risk_score,
        risk_level = EXCLUDED.risk_level,
        confidence = EXCLUDED.confidence,
        formula_terms = EXCLUDED.formula_terms
    """
)


def _parse_created_at(created_at: str) -> dt.datetime:
    return dt.datetime.fromisoformat(created_at)


def bridge_exposure_runs(limit: int = 500) -> tuple[int, int]:
    from src.exposure import store  # stdlib-only, no API deps

    n_runs, n_results = 0, 0
    with session_scope() as session:
        zone_areas = {
            r["id"]: float(r["area_km2"])
            for r in session.execute(
                text("SELECT id, area_km2 FROM reef_zones")
            ).mappings().all()
        }

        run_summaries = store.recent_runs(limit=limit)
        for run_summary in run_summaries:
            run = store.get_run(run_summary["run_id"])
            if run is None:
                continue

            release_time = _parse_created_at(run["created_at"])
            mode = "historical" if run["event_id"] == DEMO_EVENT_ID else "scenario"
            plume_source = None
            if run["results"]:
                plume_source = run["results"][0]["formula_terms"].get("plume_source")
            engine_label = (
                "api_synthetic_stub" if plume_source == "SYNTHETIC_STUB" else "unknown"
            )

            session.execute(
                UPSERT_SIMULATION_RUN_SQL,
                dict(
                    id=run["run_id"],
                    event_id=run["event_id"],
                    outlet_id=run["outlet_id"],
                    mode=mode,
                    engine=engine_label,
                    release_time=release_time,
                    status="completed",
                    parameters=json.dumps(
                        {"model_versions": run["model_versions"], "caveats": run["caveats"]}
                    ),
                ),
            )
            n_runs += 1

            for result in run["results"]:
                zone_id = result["reef_zone_id"]
                arrival = result.get("arrival_window_hours")
                arrival_start = (
                    release_time + dt.timedelta(hours=arrival[0]) if arrival else None
                )
                arrival_end = (
                    release_time + dt.timedelta(hours=arrival[1]) if arrival else None
                )
                duration_hours = (arrival[1] - arrival[0]) if arrival else None
                area_km2 = zone_areas.get(zone_id)
                overlap_km2 = (
                    result["zone_fraction_affected"] * area_km2
                    if area_km2 is not None else None
                )
                formula_terms = result["formula_terms"]

                session.execute(
                    UPSERT_REEF_EXPOSURE_SQL,
                    dict(
                        run_id=run["run_id"],
                        reef_zone_id=zone_id,
                        max_exposure_probability=result["max_exposure_probability"],
                        overlap_km2_at_max=overlap_km2,
                        exposure_duration_hours=duration_hours,
                        arrival_start=arrival_start,
                        arrival_end=arrival_end,
                        arrival_window_hours_low=arrival[0] if arrival else None,
                        arrival_window_hours_high=arrival[1] if arrival else None,
                        risk_score=result["risk_score"],
                        risk_level=result["risk_level"],
                        confidence=formula_terms.get("confidence_adjustment"),
                        formula_terms=json.dumps(formula_terms, default=str),
                    ),
                )
                n_results += 1

    return n_runs, n_results


if __name__ == "__main__":
    n_runs, n_results = bridge_exposure_runs()
    print(f"Upserted {n_runs} simulation_runs, {n_results} reef_exposures.")
