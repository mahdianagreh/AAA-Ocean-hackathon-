"""Cached forecast snapshot — the network-free demo path.

Phase 3's outcome sentence requires `docker compose up` to work with wifi off.
`data_access.forecast_snapshot()` is the read path `GET /api/v1/forecast/latest`
depends on; this asserts that path never opens a socket, the same convention
already used in test_era5_land_ingestion.py / test_imerg_ingestion.py.

Scoped to data_access rather than the full FastAPI app: the API's own
dependencies (fastapi, xgboost, shap, geopandas — see requirements-api.txt) are a
separate install from this repo's default test environment. The endpoint itself
(backend/src/api/main.py::forecast_latest) is a thin wrapper around this function
with no additional I/O, so this is the meaningful boundary to test.

Run: .venv/bin/python -m pytest tests/test_forecast_snapshot.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.src.api import data_access as da  # noqa: E402

SNAPSHOT_FIXTURE = {
    "models": {
        "gfs": {"id": "gfs_2026-08-03T00Z", "reference_time": "2026-08-03T00:00:00+00:00",
                 "n_members": 1, "max_lead_hours": 48},
        "gefs": {"id": "gefs_2026-08-03T00Z", "reference_time": "2026-08-03T00:00:00+00:00",
                  "n_members": 30, "max_lead_hours": 48},
    },
    "gfs_catchment_rainfall": [
        {"catchment_id": "AQ-C01", "lead_hours": 3, "rain_mm": 0.0,
         "wind_speed_ms": 1.2, "wind_direction_deg": 210.0},
    ],
    "gefs_exceedance": [
        {"catchment_id": "AQ-C01", "window_hours": 24, "threshold_mm": 2.9613,
         "threshold_source": "catchment_rainfall_climatology p99, window_hours=24, imerg_v07_final",
         "members_total": 30, "members_exceeding": 0, "exceedance_prob": 0.0},
    ],
}


def _deny(*args, **kwargs):
    raise AssertionError("network access attempted during pytest")


def test_forecast_snapshot_reads_file_only_no_network(tmp_path, monkeypatch):
    import socket

    monkeypatch.setattr(socket, "socket", _deny)
    monkeypatch.setattr(socket, "create_connection", _deny)
    monkeypatch.setattr(socket.socket, "connect", _deny, raising=False)

    snapshot_path = tmp_path / "latest_snapshot.json"
    snapshot_path.write_text(json.dumps(SNAPSHOT_FIXTURE))

    monkeypatch.setitem(da.ARTIFACTS, "forecast_snapshot", snapshot_path)
    da.forecast_snapshot.cache_clear()

    result = da.forecast_snapshot()
    assert result is not None
    assert result["models"]["gfs"]["reference_time"] == "2026-08-03T00:00:00+00:00"
    assert result["gefs_exceedance"][0]["catchment_id"] == "AQ-C01"

    da.forecast_snapshot.cache_clear()


def test_forecast_snapshot_missing_file_returns_none_not_a_fabricated_default(
    tmp_path, monkeypatch
):
    monkeypatch.setitem(da.ARTIFACTS, "forecast_snapshot", tmp_path / "does_not_exist.json")
    da.forecast_snapshot.cache_clear()

    assert da.forecast_snapshot() is None

    da.forecast_snapshot.cache_clear()
