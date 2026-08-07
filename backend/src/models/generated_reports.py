"""Persistence for B5's forensic report generator. Modeled on
`exposure/store.py`'s pattern exactly — see `candidate_sites.py`'s docstring
for why (same reasoning applies verbatim: local SQLite, no network/credentials
required, schema-fluid JSON-blob sections).

`status` starts as `"ai_drafted"` on every insert and only
`set_reviewed()` — the one and only write path this module exposes for it —
is permitted to change it to `"human_reviewed"`. A generated artifact that
looks finished must carry a visible flag saying it isn't reviewed yet, never
silently upgrade its own trust level.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from lib.ulid import new_ulid

_DEFAULT = Path(__file__).resolve().parents[3] / "data" / "outputs" / "generated_reports.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS generated_reports (
    report_id     TEXT PRIMARY KEY,
    event_id      TEXT NOT NULL,
    generated_at  TEXT NOT NULL,
    status        TEXT NOT NULL,
    sections      TEXT NOT NULL,
    reviewed_at   TEXT,
    reviewed_by   TEXT
);
CREATE INDEX IF NOT EXISTS idx_generated_reports_event ON generated_reports(event_id);
"""


def db_path() -> Path:
    """Overridable via REEFSHIELD_REPORTS_DB so tests never touch real reports."""
    return Path(os.environ.get("REEFSHIELD_REPORTS_DB", _DEFAULT))


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


def new_report_id() -> str:
    """`report_{ULID}` — new namespace, clear of the five frozen ID schemes."""
    return f"report_{new_ulid()}"


def save_draft(report_id: str, event_id: str, sections: list[dict]) -> dict:
    """Every report is born `"ai_drafted"`. There is no argument to make this
    function insert anything else."""
    row = {
        "report_id": report_id,
        "event_id": event_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ai_drafted",
        "sections": sections,
        "reviewed_at": None,
        "reviewed_by": None,
    }
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO generated_reports VALUES (?,?,?,?,?,?,?)",
            (row["report_id"], row["event_id"], row["generated_at"], row["status"],
             json.dumps(sections, sort_keys=True, default=str), None, None),
        )
    return row


def set_reviewed(report_id: str, reviewed_by: str) -> dict | None:
    """The only function in this module that writes `"human_reviewed"`. A
    report that doesn't exist can't be reviewed — returns None rather than
    inventing one."""
    existing = get_report(report_id)
    if existing is None:
        return None
    reviewed_at = datetime.now(timezone.utc).isoformat()
    with _conn() as con:
        con.execute(
            "UPDATE generated_reports SET status = 'human_reviewed', "
            "reviewed_at = ?, reviewed_by = ? WHERE report_id = ?",
            (reviewed_at, reviewed_by, report_id),
        )
    return get_report(report_id)


def get_report(report_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM generated_reports WHERE report_id = ?", (report_id,)
        ).fetchone()
    if row is None:
        return None
    return {
        "report_id": row["report_id"],
        "event_id": row["event_id"],
        "generated_at": row["generated_at"],
        "status": row["status"],
        "sections": json.loads(row["sections"]),
        "reviewed_at": row["reviewed_at"],
        "reviewed_by": row["reviewed_by"],
    }
