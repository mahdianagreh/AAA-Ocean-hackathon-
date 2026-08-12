"""Persistence for Phase 9's response-recommendation swarm. Modeled on
`exposure/store.py` and `generated_reports.py` exactly: local SQLite, no
network/credentials required on the request path (`api/main.py`'s own docstring —
"Nothing here opens a database connection"). The four tables mirror
`supabase/migrations/20260811090000_response_recommendations.sql` field-for-field;
a Postgres row is the team-durable copy, synced later by a batch bridge
(`db/loaders/response_recommendations.py`, same shape as `db/loaders/exposure_runs.py`)
— never written from the live request path itself.

`status` only ever moves forward: running -> proposed -> judge_approved|judge_rejected
-> finalized. No function in this module can move it backward.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from lib.ulid import new_ulid

_DEFAULT = (
    Path(__file__).resolve().parents[3] / "data" / "outputs" / "response_recommendations.sqlite"
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS response_recommendations (
    id                      TEXT PRIMARY KEY,
    run_id                  TEXT NOT NULL,
    event_id                TEXT,
    triggered_by            TEXT NOT NULL,
    triggered_by_user       TEXT,
    min_risk_level_override TEXT,
    severity_brief          TEXT NOT NULL,
    final_recommendation    TEXT,
    status                  TEXT NOT NULL,
    rounds_used             INTEGER,
    converged               INTEGER,
    model                   TEXT NOT NULL,
    created_at              TEXT NOT NULL,
    completed_at            TEXT
);
CREATE INDEX IF NOT EXISTS idx_response_recommendations_run
    ON response_recommendations(run_id);

CREATE TABLE IF NOT EXISTS recommendation_turns (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id  TEXT NOT NULL,
    round               INTEGER NOT NULL,
    agent_role          TEXT NOT NULL,
    content             TEXT NOT NULL,
    evidence_cited      TEXT,
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recommendation_turns_rec
    ON recommendation_turns(recommendation_id, round);

CREATE TABLE IF NOT EXISTS recommendation_verdicts (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id  TEXT NOT NULL,
    verdict             TEXT NOT NULL,
    evidence_cited      TEXT,
    reasoning           TEXT NOT NULL,
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recommendation_verdicts_rec
    ON recommendation_verdicts(recommendation_id);

CREATE TABLE IF NOT EXISTS recommendation_gaps (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id  TEXT NOT NULL,
    gap_description     TEXT NOT NULL,
    severity            TEXT,
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_recommendation_gaps_rec
    ON recommendation_gaps(recommendation_id);
"""

_VALID_STATUS = {"running", "proposed", "judge_approved", "judge_rejected", "finalized"}
_VALID_TRIGGER = {"auto", "human_override"}


def db_path() -> Path:
    """Overridable via REEFSHIELD_RECOMMENDATIONS_DB so tests never touch the real file."""
    return Path(os.environ.get("REEFSHIELD_RECOMMENDATIONS_DB", _DEFAULT))


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


def new_recommendation_id() -> str:
    return f"rec_{new_ulid()}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_recommendation(
    run_id: str,
    event_id: str | None,
    triggered_by: str,
    severity_brief: dict,
    model: str,
    triggered_by_user: str | None = None,
    min_risk_level_override: str | None = None,
) -> dict:
    """Insert the row in `status: "running"` — the row the trigger endpoint returns
    before the swarm has produced anything. Refuses an unrecognised `triggered_by`
    rather than storing an audit trail that itself can't be trusted."""
    if triggered_by not in _VALID_TRIGGER:
        raise ValueError(f"triggered_by must be one of {_VALID_TRIGGER}, got {triggered_by!r}")
    if triggered_by == "human_override" and not triggered_by_user:
        raise ValueError("human_override requires triggered_by_user")

    rec_id = new_recommendation_id()
    created_at = _now()
    with _conn() as con:
        con.execute(
            "INSERT INTO response_recommendations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rec_id, run_id, event_id, triggered_by, triggered_by_user,
                min_risk_level_override, json.dumps(severity_brief, default=str),
                None, "running", None, None, model, created_at, None,
            ),
        )
    return get_recommendation(rec_id)


def add_turn(
    recommendation_id: str, round: int, agent_role: str, content: str,
    evidence_cited: list[str] | None = None,
) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO recommendation_turns "
            "(recommendation_id, round, agent_role, content, evidence_cited, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (recommendation_id, round, agent_role, content,
             json.dumps(evidence_cited or []), _now()),
        )


def add_verdict(
    recommendation_id: str, verdict: str, reasoning: str,
    evidence_cited: list[str] | None = None,
) -> None:
    if verdict not in ("approved", "rejected"):
        raise ValueError(f"verdict must be approved|rejected, got {verdict!r}")
    with _conn() as con:
        con.execute(
            "INSERT INTO recommendation_verdicts "
            "(recommendation_id, verdict, evidence_cited, reasoning, created_at) "
            "VALUES (?,?,?,?,?)",
            (recommendation_id, verdict, json.dumps(evidence_cited or []), reasoning, _now()),
        )


def add_gap(recommendation_id: str, gap_description: str, severity: str | None = None) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO recommendation_gaps "
            "(recommendation_id, gap_description, severity, created_at) VALUES (?,?,?,?)",
            (recommendation_id, gap_description, severity, _now()),
        )


def update_status(
    recommendation_id: str,
    status: str,
    final_recommendation: str | None = None,
    rounds_used: int | None = None,
    converged: bool | None = None,
    complete: bool = False,
) -> dict | None:
    """The only write path for `status`, `final_recommendation`, `rounds_used`,
    `converged`. `complete=True` also stamps `completed_at` — set only on the call
    that moves status to its terminal value (`finalized`, or an earlier failure)."""
    if status not in _VALID_STATUS:
        raise ValueError(f"status must be one of {_VALID_STATUS}, got {status!r}")
    existing = get_recommendation(recommendation_id)
    if existing is None:
        return None

    fields, params = ["status = ?"], [status]
    if final_recommendation is not None:
        fields.append("final_recommendation = ?")
        params.append(final_recommendation)
    if rounds_used is not None:
        fields.append("rounds_used = ?")
        params.append(rounds_used)
    if converged is not None:
        fields.append("converged = ?")
        params.append(1 if converged else 0)
    if complete:
        fields.append("completed_at = ?")
        params.append(_now())
    params.append(recommendation_id)

    with _conn() as con:
        con.execute(
            f"UPDATE response_recommendations SET {', '.join(fields)} WHERE id = ?",
            params,
        )
    return get_recommendation(recommendation_id)


def get_recommendation(recommendation_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM response_recommendations WHERE id = ?", (recommendation_id,)
        ).fetchone()
        if row is None:
            return None
        turns = con.execute(
            "SELECT * FROM recommendation_turns WHERE recommendation_id = ? "
            "ORDER BY round, id", (recommendation_id,),
        ).fetchall()
        verdicts = con.execute(
            "SELECT * FROM recommendation_verdicts WHERE recommendation_id = ? "
            "ORDER BY id", (recommendation_id,),
        ).fetchall()
        gaps = con.execute(
            "SELECT * FROM recommendation_gaps WHERE recommendation_id = ? "
            "ORDER BY id", (recommendation_id,),
        ).fetchall()

    return {
        "id": row["id"],
        "run_id": row["run_id"],
        "event_id": row["event_id"],
        "triggered_by": row["triggered_by"],
        "triggered_by_user": row["triggered_by_user"],
        "min_risk_level_override": row["min_risk_level_override"],
        "severity_brief": json.loads(row["severity_brief"]),
        "final_recommendation": row["final_recommendation"],
        "status": row["status"],
        "rounds_used": row["rounds_used"],
        "converged": bool(row["converged"]) if row["converged"] is not None else None,
        "model": row["model"],
        "created_at": row["created_at"],
        "completed_at": row["completed_at"],
        "turns": [
            {
                "round": t["round"],
                "agent_role": t["agent_role"],
                "content": t["content"],
                "evidence_cited": json.loads(t["evidence_cited"] or "[]"),
                "created_at": t["created_at"],
            }
            for t in turns
        ],
        "verdicts": [
            {
                "verdict": v["verdict"],
                "evidence_cited": json.loads(v["evidence_cited"] or "[]"),
                "reasoning": v["reasoning"],
                "created_at": v["created_at"],
            }
            for v in verdicts
        ],
        "gaps": [
            {
                "gap_description": g["gap_description"],
                "severity": g["severity"],
                "created_at": g["created_at"],
            }
            for g in gaps
        ],
    }


def recent_recommendations(limit: int = 20, run_id: str | None = None) -> list[dict]:
    sql = "SELECT id FROM response_recommendations"
    params: list = []
    if run_id:
        sql += " WHERE run_id = ?"
        params.append(run_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _conn() as con:
        ids = [r["id"] for r in con.execute(sql, params).fetchall()]
    return [get_recommendation(i) for i in ids]
