"""Persistence for B4's site-scoring agent — every auto-scored coastline, stored
and browsable. Modeled directly on `exposure/store.py`'s pattern (own SQLite
file, env-var override for tests, idempotent schema-on-connect) — see that
module's docstring for why this project keeps this kind of audit trail in
local SQLite rather than the shared Supabase session layer: it has to be
writable with no network and no credentials, same as an exposure run.

`criteria` is stored as a JSON blob, not exploded into six columns, for the
same reason `exposure_results.formula_terms` is: the rubric's own definition
(`docs/Ali/research/01-signature.md`, not part of the app surface, but the
rubric's six criterion keys are) could grow or change, and a schema migration
is a worse failure mode than a JSON blob that is always complete.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from lib.ulid import new_ulid

_DEFAULT = Path(__file__).resolve().parents[3] / "data" / "outputs" / "candidate_sites.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidate_sites (
    site_id     TEXT PRIMARY KEY,
    site_name   TEXT,
    bbox_wsen   TEXT NOT NULL,
    scored_at   TEXT NOT NULL,
    criteria    TEXT NOT NULL,
    narrative   TEXT NOT NULL,
    caveats     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_candidate_sites_scored_at ON candidate_sites(scored_at);
"""


def db_path() -> Path:
    """Overridable via REEFSHIELD_CANDIDATE_SITES_DB so tests never touch real scores."""
    return Path(os.environ.get("REEFSHIELD_CANDIDATE_SITES_DB", _DEFAULT))


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


def new_site_id() -> str:
    """`site_{ULID}` — new namespace, confirmed clear of the five frozen ID
    schemes in tasks/00-contracts.md §2 (AQ-C, AQ-O, R-, AQ-YYYY-MM-DD,
    sim_{ULID}). A candidate site is never an Aqaba entity, so it never
    squats an `AQ-*` ID."""
    return f"site_{new_ulid()}"


def save_score(
    site_id: str,
    site_name: str | None,
    bbox: tuple[float, float, float, float],
    criteria: list[dict],
    narrative: str,
    caveats: list[dict],
) -> str:
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO candidate_sites VALUES (?,?,?,?,?,?,?)",
            (
                site_id,
                site_name,
                json.dumps(list(bbox)),
                datetime.now(timezone.utc).isoformat(),
                json.dumps(criteria, sort_keys=True, default=str),
                narrative,
                json.dumps(caveats, sort_keys=True, default=str),
            ),
        )
    return site_id


def get_score(site_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM candidate_sites WHERE site_id = ?", (site_id,)
        ).fetchone()
    if row is None:
        return None
    return {
        "site_id": row["site_id"],
        "site_name": row["site_name"],
        "bbox": json.loads(row["bbox_wsen"]),
        "scored_at": row["scored_at"],
        "criteria": json.loads(row["criteria"]),
        "narrative": row["narrative"],
        "caveats": json.loads(row["caveats"]),
    }


def recent_scores(limit: int = 20) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT site_id, site_name, bbox_wsen, scored_at FROM candidate_sites "
            "ORDER BY scored_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {"site_id": r["site_id"], "site_name": r["site_name"],
         "bbox": json.loads(r["bbox_wsen"]), "scored_at": r["scored_at"]}
        for r in rows
    ]
