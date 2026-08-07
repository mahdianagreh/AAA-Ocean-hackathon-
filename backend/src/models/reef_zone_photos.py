"""B8 — Coral Health Vision Model: photo storage + the sensitivity-weight
safeguard.

Metadata follows `exposure/store.py`'s SQLite pattern exactly, same as the
other three Phase 5 stores. Image bytes are git-ignored user content, not
reproducible data — stored under `data/raw/reef_photos/<reef_zone_id>/`,
matching this project's existing convention that `data/raw/` holds things
that aren't committed (same directory tier as the DEM/bathymetry rasters,
for a different reason: size/reproducibility there, user-submitted content
here).

THE NON-NEGOTIABLE SAFEGUARD, STRUCTURAL HERE, NOT JUST DOCUMENTED
---------------------------------------------------------------------
`sensitivity_weight` is read from `reef_zones.gpkg` via
`data_access.py::reef_zones()`'s `@lru_cache(maxsize=1)` — a value nothing in
the live request path used to write to. This module keeps that invariant true
by construction: `proposed_sensitivity_weight_for_zone()` computes a proposal
from accumulated photo classifications and returns it as a plain number this
module owns — it never touches `reef_zones.gpkg` and never calls
`data_access.clear_all_caches()`.

**Approval writes a separate override, not the `.gpkg` file itself** — found
while wiring this against the running container, not assumed: `./data` is
mounted **read-only** on purpose (`docker-compose.yml`'s own comment, already
enforced once for `exposure_runs.sqlite`), so a live write to `reef_zones.gpkg`
would succeed on a developer's machine and fail — or silently target the
wrong file — the moment this runs in the actual deployed container. Instead,
`set_override()` writes to `sensitivity_weight_overrides` in *this* SQLite
file (already redirected to the writable `/app/var` volume, same as every
other Phase 5 store), and `data_access.py::reef_zones()` applies it as a
read-time overlay on top of the untouched base geometry. The base `.gpkg`
file is never written by the running API, ever — only the override is, and
every override is additionally logged permanently in
`sensitivity_weight_approvals`. `api.main.approve_sensitivity_weight` is the
**only** function anywhere that calls `set_override()` or
`data_access.clear_all_caches()` for this field — Standing Law rule 13:
propose, never auto-overwrite.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from lib.ulid import new_ulid

_DEFAULT = Path(__file__).resolve().parents[3] / "data" / "outputs" / "reef_zone_photos.sqlite"
PHOTO_DIR = Path(__file__).resolve().parents[3] / "data" / "raw" / "reef_photos"

#: Same shape of gate as B7's MIN_FEEDBACK_FOR_ADJUSTMENT — a proposal from a
#: single photo is noise, not signal.
MIN_PHOTOS_FOR_PROPOSAL = 3

#: A simple, documented mapping from predicted class to an implied sensitivity
#: weight — higher for a compromised reef, exactly the direction real marine
#: sensitivity scoring would move. Not a calibrated relationship; a starting
#: point a marine scientist's review is expected to correct.
IMPLIED_WEIGHT_BY_CLASS = {"healthy": 1.0, "stressed": 1.3, "bleached": 1.6}

SCHEMA = """
CREATE TABLE IF NOT EXISTS reef_zone_photos (
    photo_id         TEXT PRIMARY KEY,
    reef_zone_id     TEXT NOT NULL,
    uploaded_at      TEXT NOT NULL,
    file_path        TEXT NOT NULL,
    predicted_class  TEXT NOT NULL,
    confidence       REAL NOT NULL,
    model_basis      TEXT NOT NULL,
    model_version    TEXT
);
CREATE INDEX IF NOT EXISTS idx_reef_zone_photos_zone ON reef_zone_photos(reef_zone_id);

CREATE TABLE IF NOT EXISTS sensitivity_weight_approvals (
    approval_id       TEXT PRIMARY KEY,
    reef_zone_id      TEXT NOT NULL,
    approved_at       TEXT NOT NULL,
    reviewer          TEXT NOT NULL,
    reasoning         TEXT NOT NULL,
    proposed_value    REAL NOT NULL,
    approved_value    REAL NOT NULL
);

-- The live override itself, kept separate from the permanent approvals log
-- (one row per zone, latest wins) so a caller can ask "what's live right now"
-- without scanning history. Written ONLY by set_override(), below.
CREATE TABLE IF NOT EXISTS sensitivity_weight_overrides (
    reef_zone_id  TEXT PRIMARY KEY,
    value         REAL NOT NULL,
    updated_at    TEXT NOT NULL
);
"""


def db_path() -> Path:
    """Overridable via REEFSHIELD_REEF_PHOTOS_DB so tests never touch real photos."""
    return Path(os.environ.get("REEFSHIELD_REEF_PHOTOS_DB", _DEFAULT))


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


def new_photo_id() -> str:
    """`photo_{ULID}` — new namespace, clear of the five frozen ID schemes."""
    return f"photo_{new_ulid()}"


def photo_dir() -> Path:
    """Overridable via REEFSHIELD_REEF_PHOTOS_DIR, same reasoning as db_path()
    — tests must never write into the real data/raw/reef_photos/ tree."""
    return Path(os.environ.get("REEFSHIELD_REEF_PHOTOS_DIR", PHOTO_DIR))


def save_photo(reef_zone_id: str, image_bytes: bytes, predicted_class: str,
              confidence: float, model_basis: str, model_version: str | None) -> dict:
    photo_id = new_photo_id()
    zone_dir = photo_dir() / reef_zone_id
    zone_dir.mkdir(parents=True, exist_ok=True)
    file_path = zone_dir / f"{photo_id}.jpg"
    file_path.write_bytes(image_bytes)

    uploaded_at = datetime.now(timezone.utc).isoformat()
    with _conn() as con:
        con.execute(
            "INSERT INTO reef_zone_photos VALUES (?,?,?,?,?,?,?,?)",
            (photo_id, reef_zone_id, uploaded_at, str(file_path),
             predicted_class, float(confidence), model_basis, model_version),
        )
    return {
        "photo_id": photo_id, "reef_zone_id": reef_zone_id, "uploaded_at": uploaded_at,
        "predicted_class": predicted_class, "confidence": confidence,
        "model_basis": model_basis, "model_version": model_version,
    }


def photos_for_zone(reef_zone_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM reef_zone_photos WHERE reef_zone_id = ? ORDER BY uploaded_at",
            (reef_zone_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def proposed_sensitivity_weight_for_zone(reef_zone_id: str) -> dict:
    """A rolling average of `IMPLIED_WEIGHT_BY_CLASS` over this zone's recent
    photo classifications. `status="INSUFFICIENT_PHOTOS"` and `value=None`
    below `MIN_PHOTOS_FOR_PROPOSAL` — never a proposal computed from too
    little evidence to mean anything."""
    photos = photos_for_zone(reef_zone_id)
    if len(photos) < MIN_PHOTOS_FOR_PROPOSAL:
        return {"reef_zone_id": reef_zone_id, "proposed_value": None,
                "status": "INSUFFICIENT_PHOTOS", "n_photos": len(photos)}
    implied = [IMPLIED_WEIGHT_BY_CLASS[p["predicted_class"]] for p in photos]
    return {
        "reef_zone_id": reef_zone_id,
        "proposed_value": sum(implied) / len(implied),
        "status": "PROPOSED_PENDING_REVIEW",
        "n_photos": len(photos),
    }


def record_approval(reef_zone_id: str, reviewer: str, reasoning: str,
                    proposed_value: float, approved_value: float) -> str:
    """Permanent log of every sensitivity-weight sign-off — the "logged"
    half of Standing Law rule 13. Called exactly once, from
    `api.main.approve_sensitivity_weight`, immediately after the live
    `reef_zones.gpkg` write it accompanies."""
    approval_id = f"approval_{new_ulid()}"
    with _conn() as con:
        con.execute(
            "INSERT INTO sensitivity_weight_approvals VALUES (?,?,?,?,?,?,?)",
            (approval_id, reef_zone_id, datetime.now(timezone.utc).isoformat(),
             reviewer, reasoning, float(proposed_value), float(approved_value)),
        )
    return approval_id


def set_override(reef_zone_id: str, value: float) -> None:
    """Write the live override — the ONLY function anywhere permitted to do
    so. Called exactly once, from `api.main.approve_sensitivity_weight`,
    immediately after `record_approval()` logs the same action permanently."""
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO sensitivity_weight_overrides VALUES (?,?,?)",
            (reef_zone_id, float(value), datetime.now(timezone.utc).isoformat()),
        )


def get_override(reef_zone_id: str) -> float | None:
    """The live override for one zone, or None if a human has never approved
    one — `data_access.py::reef_zones()` calls this for every zone and
    applies it as a read-time overlay on top of the untouched base
    `reef_zones.gpkg`."""
    with _conn() as con:
        row = con.execute(
            "SELECT value FROM sensitivity_weight_overrides WHERE reef_zone_id = ?",
            (reef_zone_id,),
        ).fetchone()
    return float(row["value"]) if row is not None else None


def all_overrides() -> dict[str, float]:
    """Every live override at once — `reef_zones()` calls this once per
    request rather than once per zone, to avoid N+1 SQLite round-trips."""
    with _conn() as con:
        rows = con.execute("SELECT reef_zone_id, value FROM sensitivity_weight_overrides").fetchall()
    return {r["reef_zone_id"]: float(r["value"]) for r in rows}
