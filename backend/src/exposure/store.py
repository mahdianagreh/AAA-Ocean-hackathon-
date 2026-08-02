"""Persistence for exposure runs — the audit trail behind every displayed score.

WHY SQLITE AND NOT THE PROJECT DATABASE
---------------------------------------
The standing rule is: never open your own connection, import the shared session
layer. That layer does not exist in this repo yet (`backend/src/db/session.py` is
absent), and the rule exists to stop two Postgres connection pools diverging under
load — not to stop anything being persisted at all.

So this module deliberately does NOT open a Postgres connection. It writes to a
local SQLite file through stdlib `sqlite3`, behind a small interface with exactly
one write path and one read path. When the shared session layer lands, swapping is
a matter of reimplementing `save_run` and `get_run` against it; nothing upstream
sees a difference, because callers only ever touch those two functions.

`formula_terms` is stored as JSON rather than exploded into columns on purpose: the
term set will grow as the model gains inputs, and a schema migration is a worse
failure mode mid-hackathon than a JSON blob that is always complete.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parents[3] / "data" / "outputs" / "exposure_runs.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS exposure_runs (
    run_id          TEXT PRIMARY KEY,
    event_id        TEXT NOT NULL,
    outlet_id       TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    model_versions  TEXT NOT NULL,
    caveats         TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exposure_results (
    run_id                    TEXT NOT NULL,
    reef_zone_id              TEXT NOT NULL,
    risk_score                REAL NOT NULL,
    risk_level                TEXT NOT NULL,
    max_exposure_probability  REAL NOT NULL,
    zone_fraction_affected    REAL NOT NULL,
    arrival_start_hours       REAL,
    arrival_end_hours         REAL,
    confidence                TEXT NOT NULL,
    formula_terms             TEXT NOT NULL,
    PRIMARY KEY (run_id, reef_zone_id),
    FOREIGN KEY (run_id) REFERENCES exposure_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_results_zone ON exposure_results(reef_zone_id);
CREATE INDEX IF NOT EXISTS idx_runs_event   ON exposure_runs(event_id);
"""


def db_path() -> Path:
    """Overridable via REEFSHIELD_EXPOSURE_DB so tests never touch real runs."""
    return Path(os.environ.get("REEFSHIELD_EXPOSURE_DB", _DEFAULT))


@contextmanager
def _conn():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def new_run_id() -> str:
    """Sortable-ish, unique, and obviously a run id in a log line."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"sim_{stamp}_{uuid.uuid4().hex[:8]}"


def save_run(
    run_id: str,
    event_id: str,
    outlet_id: str,
    results: list[dict],
    model_versions: dict,
    caveats: list[dict] | None = None,
) -> str:
    """Persist a run and every per-zone result, formula_terms included.

    Refuses to store a result without formula_terms. A score with no reconstruction
    trail is precisely what this table exists to prevent, so accepting one "just
    this once" would defeat the point.
    """
    created = datetime.now(timezone.utc).isoformat()
    for r in results:
        if not r.get("formula_terms"):
            raise ValueError(
                f"result for {r.get('reef_zone_id')!r} has no formula_terms — refusing "
                "to store a score that cannot be reconstructed"
            )

    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO exposure_runs VALUES (?,?,?,?,?,?)",
            (run_id, event_id, outlet_id, created,
             json.dumps(model_versions, sort_keys=True),
             json.dumps(caveats or [], sort_keys=True)),
        )
        con.executemany(
            "INSERT OR REPLACE INTO exposure_results VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    run_id,
                    r["reef_zone_id"],
                    float(r["risk_score"]),
                    r["risk_level"],
                    float(r["max_exposure_probability"]),
                    float(r["zone_fraction_affected"]),
                    (r["arrival_window_hours"][0] if r.get("arrival_window_hours") else None),
                    (r["arrival_window_hours"][1] if r.get("arrival_window_hours") else None),
                    r.get("confidence", "moderate"),
                    json.dumps(r["formula_terms"], sort_keys=True, default=str),
                )
                for r in results
            ],
        )
    return run_id


def get_run(run_id: str) -> dict | None:
    """Reconstruct a stored run, formula_terms parsed back to dicts."""
    with _conn() as con:
        run = con.execute(
            "SELECT * FROM exposure_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if run is None:
            return None
        rows = con.execute(
            "SELECT * FROM exposure_results WHERE run_id = ? ORDER BY reef_zone_id",
            (run_id,),
        ).fetchall()

    return {
        "run_id": run["run_id"],
        "event_id": run["event_id"],
        "outlet_id": run["outlet_id"],
        "created_at": run["created_at"],
        "model_versions": json.loads(run["model_versions"]),
        "caveats": json.loads(run["caveats"]),
        "results": [
            {
                "reef_zone_id": r["reef_zone_id"],
                "risk_score": r["risk_score"],
                "risk_level": r["risk_level"],
                "max_exposure_probability": r["max_exposure_probability"],
                "zone_fraction_affected": r["zone_fraction_affected"],
                "arrival_window_hours": (
                    (r["arrival_start_hours"], r["arrival_end_hours"])
                    if r["arrival_start_hours"] is not None else None
                ),
                "confidence": r["confidence"],
                "formula_terms": json.loads(r["formula_terms"]),
            }
            for r in rows
        ],
    }


def recent_runs(limit: int = 20, event_id: str | None = None,
                outlet_id: str | None = None) -> list[dict]:
    sql = "SELECT run_id, event_id, outlet_id, created_at FROM exposure_runs"
    where, params = [], []
    if event_id:
        where.append("event_id = ?")
        params.append(event_id)
    if outlet_id:
        where.append("outlet_id = ?")
        params.append(outlet_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _conn() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def latest_run(event_id: str | None = None, outlet_id: str | None = None) -> dict | None:
    """The most recent run, optionally scoped to a scenario.

    /alerts uses this rather than an unqualified "latest run". Without the scope, an
    alert list could silently describe a different scenario than the one just
    requested — an exposure response served from cache does not write a new run, so
    "newest row in the table" is not the same thing as "what the user last asked
    about". An alert that quietly belongs to another outlet is worse than no alert.
    """
    runs = recent_runs(1, event_id=event_id, outlet_id=outlet_id)
    return get_run(runs[0]["run_id"]) if runs else None


def latest_results(event_id: str | None = None,
                   outlet_id: str | None = None) -> tuple[list[dict], str | None]:
    """(results, source_run_id). The run id travels so an alert is traceable."""
    run = latest_run(event_id=event_id, outlet_id=outlet_id)
    if run is None:
        return [], None
    return run["results"], run["run_id"]
