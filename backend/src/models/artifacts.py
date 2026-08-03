"""Persisting a trained model, and recording what it was.

Two halves of one idea: the bytes go to storage, the description goes to a
row, and the row points at the bytes. Same split `raster_assets` uses for
rasters - the database stays an index and never holds a blob.

Until Supabase is live (Nizar, workstream 3) the "row" is a line in
data/models/model_versions.jsonl with exactly the columns of the
`model_versions` table, so landing it later is an INSERT and not a redesign.

IMMUTABILITY IS THE WHOLE CONTRACT. A stored prediction references a version
id; if the bytes behind that id ever change, every prediction that cited it
becomes unreproducible while still looking fine. So retraining mints a new id
and saving over an existing one is refused.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = ROOT / "data/models"
LEDGER = MODEL_DIR / "model_versions.jsonl"

# Concept §10 numbers the components: A is rainfall event detection, C is the
# runoff risk model. tasks/phase2/02-mahdi.md heads Part 1 "Component A" and
# the generated card follows it, but that file's own summary line says
# "Feeds: Component C". Recorded as C to match the concept doc, which is what
# the schema and every cross-reference key off. One line to flip if the team
# decides otherwise.
COMPONENT = "C"


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


@dataclass
class ModelVersion:
    """One row of `model_versions`. Field names are the column names."""

    id: str
    component: str
    algorithm: str
    trained_at: str
    training_event_ids: list[str]
    cv_scheme: str
    hyperparams: dict[str, Any]
    metrics: dict[str, Any]
    artifact_path: str
    git_commit: str
    feature_source: str
    is_synthetic: bool
    features: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def _portable_path(path: Path) -> str:
    """Repo-relative when the artifact is inside the repo, absolute otherwise.

    Relative is preferable - the ledger stays valid when the checkout moves.
    But MODEL_DIR is not guaranteed to sit under ROOT: Docker will mount a
    volume for it, and relative_to() raises rather than falling back. load()
    handles both, because `ROOT / "/abs"` resolves to the absolute path.
    """
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _new_version_id(algorithm: str, sha: str, when: datetime) -> str:
    """Unique, sortable, and traceable to a commit.

    Not `runoff_xgb_v3`: a hand-incremented counter needs someone to remember
    to increment it, and forgetting silently overwrites a version other rows
    already reference.
    """
    return f"runoff_{algorithm}_{sha}_{when:%Y%m%dT%H%M%SZ}"


def save(
    *,
    gbm,
    baseline,
    sediment,
    features: list[str],
    training_event_ids: list[str],
    metrics: dict[str, Any],
    feature_source: str,
    is_synthetic: bool,
    cv_scheme: str = "leave_one_catchment_out + temporal_holdout",
    feature_ranges: dict[str, tuple[float, float]] | None = None,
    catchment_scores: dict[str, float] | None = None,
) -> ModelVersion:
    """Write the artifact and its ledger row. Returns the row.

    Synthetic runs are refused outright rather than quarantined. A card can
    carry a banner; a `.joblib` cannot, and the whole point of an artifact is
    that something later loads it without reading the provenance.
    """
    if is_synthetic:
        raise ValueError(
            "refusing to persist a model trained on synthetic rows.\n"
            "An artifact is loaded by code, not read by a person, so a banner "
            "cannot travel with it. Train on the real feature matrix; the stub "
            "exists to exercise the harness, not to produce a servable model."
        )

    import joblib

    when = datetime.now(timezone.utc)
    sha = git_sha()
    vid = _new_version_id(getattr(gbm, "name", "gbm"), sha, when)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # Version ids are second-resolution, so two saves in the same second - a
    # hyperparameter sweep, a retry - would otherwise collide. Never overwrite:
    # a stored prediction references this id, and replacing the bytes behind it
    # silently invalidates that prediction. Mint the next free id instead.
    path = MODEL_DIR / f"{vid}.joblib"
    for n in range(2, 100):
        if not path.exists():
            break
        vid = f"{_new_version_id(getattr(gbm, 'name', 'gbm'), sha, when)}-{n}"
        path = MODEL_DIR / f"{vid}.joblib"
    else:
        raise FileExistsError(
            f"cannot find a free version id near {vid} after 98 attempts - "
            f"something is writing to {MODEL_DIR} in a loop."
        )

    joblib.dump(
        {
            "version_id": vid,
            "gbm": gbm,
            "baseline": baseline,
            "sediment": sediment,
            "features": features,
            "feature_ranges": feature_ranges or {},
            "catchment_scores": catchment_scores or {},
            "is_calibrated": bool(getattr(gbm, "is_calibrated", False)),
        },
        path,
        compress=3,
    )

    row = ModelVersion(
        id=vid,
        component=COMPONENT,
        algorithm=getattr(gbm, "name", "gbm"),
        trained_at=when.isoformat(),
        training_event_ids=sorted(set(training_event_ids)),
        cv_scheme=cv_scheme,
        hyperparams=dict(getattr(gbm, "params", {})),
        metrics=metrics,
        artifact_path=_portable_path(path),
        git_commit=sha,
        feature_source=feature_source,
        is_synthetic=False,
        features=list(features),
    )
    with LEDGER.open("a") as fh:
        fh.write(json.dumps(row.to_row()) + "\n")
    return row


def list_versions() -> list[dict[str, Any]]:
    if not LEDGER.exists():
        return []
    return [json.loads(line) for line in LEDGER.read_text().splitlines() if line.strip()]


def latest_version() -> dict[str, Any] | None:
    rows = list_versions()
    return rows[-1] if rows else None


def load(version_id: str | None = None) -> dict[str, Any]:
    """Load a bundle by id, or the most recent one.

    Raises with an actionable message rather than returning None, because the
    caller is an API request handler and a silent None becomes a 500 with no
    explanation.
    """
    rows = list_versions()
    if not rows:
        raise FileNotFoundError(
            "no trained model has been registered.\n"
            f"Ledger: {LEDGER.relative_to(ROOT)} (absent or empty)\n\n"
            "Train one once Karam's feature matrix lands:\n"
            "    .venv/bin/python scripts/11_train_runoff_model.py\n\n"
            "To develop against the shape of a response without a model:\n"
            "    REEFSHIELD_MODEL_SOURCE=stub"
        )

    row = rows[-1] if version_id is None else next(
        (r for r in rows if r["id"] == version_id), None)
    if row is None:
        known = ", ".join(r["id"] for r in rows[-5:])
        raise KeyError(f"unknown model version {version_id!r}. Recent: {known}")

    import joblib

    path = ROOT / row["artifact_path"]
    if not path.exists():
        raise FileNotFoundError(
            f"{row['id']} is registered but its artifact is missing: {path}\n"
            "The ledger and storage have diverged - do not fall back to another "
            "version, because the prediction would be attributed to the wrong one."
        )
    bundle = joblib.load(path)
    bundle["row"] = row
    return bundle
