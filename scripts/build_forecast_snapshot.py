"""
Freeze the latest GFS/GEFS forecast run into a committed JSON snapshot the API
serves with zero network calls at request time.

Why a file, not a live Postgres query: `docker-compose.yml`'s own header notes
that talking to Supabase Cloud is itself a network dependency, and the Phase 3
demo requirement is "wifi off" (tasks/phase3/00-phase3-plan.md line 90: "Live
means latest cached forecast"). `forecast_pipeline.py` (which does query live
GFS/GEFS and writes to Postgres) is the reproducibility/refresh mechanism, run
ahead of the demo whenever a fresher snapshot is wanted — this script is the
one-time freeze step that turns its *output* into something a clean clone can
serve offline.

Output path (data/processed/forecasts/, NOT gitignored — unlike data/raw/*) is
picked up by backend/src/api/data_access.py::forecast_snapshot().

Run: cd backend && .venv/bin/python ../scripts/build_forecast_snapshot.py
Requires SUPABASE_DB_URL in backend/.env (reads Postgres once, at build time only).
"""

from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import text  # noqa: E402

from src.db.client import session_scope  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "data" / "processed" / "forecasts" / "latest_snapshot.json"


def _row_to_dict(row) -> dict:
    d = dict(row)
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            d[k] = v.isoformat()
        elif isinstance(v, Decimal):
            d[k] = float(v)
    return d


def build_snapshot() -> dict:
    with session_scope() as session:
        runs = session.execute(
            text(
                "SELECT DISTINCT ON (model) model, id, reference_time, n_members, max_lead_hours "
                "FROM forecast_runs ORDER BY model, reference_time DESC"
            )
        ).mappings().all()
        runs_by_model = {r["model"]: _row_to_dict(r) for r in runs}

        gfs_run_id = runs_by_model.get("gfs", {}).get("id")
        gfs_rainfall = []
        if gfs_run_id:
            gfs_rainfall = [
                _row_to_dict(r)
                for r in session.execute(
                    text(
                        "SELECT catchment_id, lead_hours, rain_mm, wind_speed_ms, "
                        "wind_direction_deg FROM forecast_catchment_rainfall "
                        "WHERE forecast_run_id = :run_id AND member = 0 "
                        "ORDER BY catchment_id, lead_hours"
                    ),
                    {"run_id": gfs_run_id},
                ).mappings().all()
            ]

        gefs_run_id = runs_by_model.get("gefs", {}).get("id")
        exceedance = []
        anomalies = []
        if gefs_run_id:
            exceedance = [
                _row_to_dict(r)
                for r in session.execute(
                    text(
                        "SELECT catchment_id, window_hours, threshold_mm, threshold_source, "
                        "members_total, members_exceeding, exceedance_prob FROM forecast_exceedance "
                        "WHERE forecast_run_id = :run_id ORDER BY catchment_id"
                    ),
                    {"run_id": gefs_run_id},
                ).mappings().all()
            ]
            # B6 -- Live Anomaly Detection. Percentile-relative, not a z-score
            # (catchment_rainfall_climatology only has percentiles) -- see
            # backend/src/processing/anomaly_detection.py's docstring.
            anomalies = [
                _row_to_dict(r)
                for r in session.execute(
                    text(
                        "SELECT catchment_id, window_hours, rain_mm, climatology_p50, "
                        "climatology_p99, climatology_p99_9, percentile_band, anomaly_score, "
                        "is_anomalous, computed_at FROM forecast_anomalies "
                        "WHERE forecast_run_id = :run_id ORDER BY catchment_id"
                    ),
                    {"run_id": gefs_run_id},
                ).mappings().all()
            ]

    return {
        "models": runs_by_model,
        "gfs_catchment_rainfall": gfs_rainfall,
        "gefs_exceedance": exceedance,
        "gefs_anomalies": anomalies,
    }


def main() -> None:
    snapshot = build_snapshot()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
    print(f"Wrote {OUT_PATH}")
    for model, run in snapshot["models"].items():
        print(f"  {model}: issued {run['reference_time']} (run {run['id']})")


if __name__ == "__main__":
    main()
