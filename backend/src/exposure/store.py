"""Persistence for exposure runs — the audit trail behind every displayed score.

WHY SQLITE, NOW THAT THE SHARED LAYER EXISTS
--------------------------------------------
Correction, 3 Aug 2026: this docstring previously said the shared session layer did
not exist. It does — `backend/src/db/client.py` (Nizar) provides `get_session()` and
`session_scope()` against Supabase Postgres. The standing rule "never open your own
connection" therefore applies, and this module obeys it: it does **not** open a
Postgres connection anywhere.

It still writes exposure runs to a local SQLite file, on purpose:

  * `client.py` raises at import if `SUPABASE_DB_URL` is unset. The exposure audit
    trail has to be writable with no network and no credentials — during tests, and
    during a demo on conference wifi. A run that cannot be persisted is a score that
    cannot be defended, which is the one thing this table exists to prevent.
  * It is a local-first cache, not a competing source of truth. The dashboard reads
    reef zones and catchments from Supabase via Nizar's loaders; nothing else reads
    this file.

Both paths go through exactly one write function and one read function, so pointing
them at `session_scope()` is a change to `save_run` and `get_run` only — no caller
sees a difference. If the audit trail should live in Postgres for the demo, that is a
deliberate call to make with Nizar, not something to switch silently here.

`formula_terms` is stored as JSON rather than exploded into columns on purpose: the
term set will grow as the model gains inputs, and a schema migration is a worse
failure mode mid-hackathon than a JSON blob that is always complete.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
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


# Crockford base32: excludes I, L, O, U to avoid transcription confusion.
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _new_ulid() -> str:
    """A real ULID: 48-bit millisecond timestamp + 80-bit randomness, 26 chars.

    No dependency added for this — it is ~10 lines of bit-shifting, and the run-id
    format is stable enough (tasks/00-contracts.md: `sim_{ULID}`) that pulling in a
    library for it is not worth the extra surface on the api image, which is kept
    deliberately minimal (see main.py's "no geospatial stack" note for the same
    reasoning applied elsewhere).

    Lexicographic sort order matches creation order at millisecond granularity,
    because the timestamp occupies the leading characters — the property
    `new_run_id()`'s old docstring called "sortable-ish" without it actually being
    guaranteed. Two runs in the same millisecond are not ordered relative to each
    other (their random suffix decides), which matches the standard ULID spec and
    is fine here: nothing orders runs at sub-millisecond precision.
    """
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    value = (ts_ms << 80) | secrets.randbits(80)  # 128 significant bits
    # 26 chars * 5 bits = 130 bits; the top 2 bits are always 0 since value has
    # only 128 significant bits — Python's arbitrary-width ints yield 0 for shifts
    # past the top, so no explicit padding is needed.
    return "".join(_CROCKFORD[(value >> (5 * (25 - i))) & 0x1F] for i in range(26))


def new_run_id() -> str:
    """`sim_{ULID}`, per tasks/00-contracts.md's ID contract.

    Previously `sim_{YYYYMMDDTHHMMSS}_{uuid8}` — plausible-looking, and it worked,
    but it was not the format the contract specifies, and nothing enforced the two
    staying in sync. Fixed here rather than in the contract doc: this generator is
    the one non-conformant party, not the published spec.
    """
    return f"sim_{_new_ulid()}"


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
