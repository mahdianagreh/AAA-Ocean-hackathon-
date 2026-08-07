"""B7 — Adaptive Sampling Recommender: storage + the blending logic.

Storage follows `exposure/store.py`'s pattern exactly, same as
`candidate_sites.py`/`generated_reports.py`.

THE BLENDING RULE — additive field, never a change to the exposure formula
----------------------------------------------------------------------------
`exposure/engine.py`'s own docstring warns explicitly against adding a new
multiplicative term to `calculate_exposure()`: "any curve we invented here
would change the ranking between zones while looking like a presentation
detail." So `adjusted_priority()` here does **not** touch that formula.
`risk_score` stays exactly what it is today — the pure model output,
byte-identical for every existing test. `adjusted_priority` is a new,
separate value that **defaults to `risk_score` itself** when a zone has
fewer than `MIN_FEEDBACK_FOR_ADJUSTMENT` real sampling outcomes — so "no
feedback yet" isn't a special case a caller has to remember, it's the literal
default value.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from lib.ulid import new_ulid

_DEFAULT = Path(__file__).resolve().parents[3] / "data" / "outputs" / "sampling_feedback.sqlite"

#: A real, documented gate, not a formality — fewer real outcomes than this and
#: any "accuracy" computed from them is noise, not signal.
MIN_FEEDBACK_FOR_ADJUSTMENT = 5

SCHEMA = """
CREATE TABLE IF NOT EXISTS sampling_feedback (
    feedback_id           TEXT PRIMARY KEY,
    reef_zone_id          TEXT NOT NULL,
    run_id                TEXT NOT NULL,
    predicted_risk_score  REAL NOT NULL,
    sampled_at            TEXT NOT NULL,
    outcome               TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sampling_feedback_zone ON sampling_feedback(reef_zone_id);
"""


def db_path() -> Path:
    """Overridable via REEFSHIELD_SAMPLING_FEEDBACK_DB so tests never touch real feedback."""
    return Path(os.environ.get("REEFSHIELD_SAMPLING_FEEDBACK_DB", _DEFAULT))


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


def new_feedback_id() -> str:
    """`feedback_{ULID}` — new namespace, clear of the five frozen ID schemes."""
    return f"feedback_{new_ulid()}"


def save_feedback(reef_zone_id: str, run_id: str, predicted_risk_score: float,
                  outcome: str) -> str:
    feedback_id = new_feedback_id()
    with _conn() as con:
        con.execute(
            "INSERT INTO sampling_feedback VALUES (?,?,?,?,?,?)",
            (feedback_id, reef_zone_id, run_id, float(predicted_risk_score),
             datetime.now(timezone.utc).isoformat(), outcome),
        )
    return feedback_id


def history_for_zone(reef_zone_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM sampling_feedback WHERE reef_zone_id = ? ORDER BY sampled_at",
            (reef_zone_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _historical_accuracy(history: list[dict]) -> float:
    """Fraction of feedback rows marked "confirmed" — the simplest honest
    accuracy proxy, on [0, 1]. A heuristic starting point (per the task's own
    spec: "starts as a simple heuristic/bandit approach, not deep RL"), not a
    calibrated statistic."""
    if not history:
        return 1.0  # unreachable in practice — callers gate on MIN_FEEDBACK first
    confirmed = sum(1 for h in history if h["outcome"] == "confirmed")
    return confirmed / len(history)


def adjusted_priority(reef_zone_id: str, risk_score: float) -> tuple[float, str]:
    """(adjusted_score, status). `status="NO_FEEDBACK_YET"` and
    `adjusted_score == risk_score` exactly whenever there's insufficient
    history — the literal fallback, not an approximation. Once adjusted,
    the accuracy multiplier is bounded to [0, 1], so `adjusted_priority` can
    only ever move DOWN from `risk_score`, never inflate it — a recommender
    with a poor track record dampens its own influence rather than amplifying
    a score with no basis."""
    history = history_for_zone(reef_zone_id)
    if len(history) < MIN_FEEDBACK_FOR_ADJUSTMENT:
        return risk_score, "NO_FEEDBACK_YET"
    accuracy = _historical_accuracy(history)
    return risk_score * accuracy, "FEEDBACK_APPLIED"
