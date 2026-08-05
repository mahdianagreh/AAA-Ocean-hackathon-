"""
Loader: Mahdi's trained model artifacts -> `model_versions`.

Source: data/models/model_versions.jsonl (backend/src/models/artifacts.py's
ledger — one JSON line per registered artifact, alongside its .joblib file).

The jsonl carries three fields with no matching Postgres column
(`feature_source`, `is_synthetic`, `features`) — folded into the existing
`metrics` jsonb rather than dropped or requiring a schema change, same pattern
Phase 2 used for outlets' culvert cross-check data (folded into `method`).

Idempotent: upserts on `id` (the artifact id is already content-addressed —
`runoff_weighted_gbm_<git_commit>_<trained_at>`).
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from src.db.client import session_scope

REPO_ROOT = Path(__file__).resolve().parents[4]
LEDGER = REPO_ROOT / "data" / "models" / "model_versions.jsonl"

UPSERT_SQL = text(
    """
    INSERT INTO model_versions (
        id, component, algorithm, trained_at, training_event_ids, cv_scheme,
        hyperparams, metrics, artifact_path, git_commit
    ) VALUES (
        :id, :component, :algorithm, :trained_at, :training_event_ids, :cv_scheme,
        :hyperparams, :metrics, :artifact_path, :git_commit
    )
    ON CONFLICT (id) DO UPDATE SET
        component = EXCLUDED.component,
        algorithm = EXCLUDED.algorithm,
        trained_at = EXCLUDED.trained_at,
        training_event_ids = EXCLUDED.training_event_ids,
        cv_scheme = EXCLUDED.cv_scheme,
        hyperparams = EXCLUDED.hyperparams,
        metrics = EXCLUDED.metrics,
        artifact_path = EXCLUDED.artifact_path,
        git_commit = EXCLUDED.git_commit
    """
)


def load_model_versions() -> int:
    if not LEDGER.exists():
        print(f"SKIP model_versions: missing {LEDGER}")
        return 0

    n = 0
    with session_scope() as session:
        for line in LEDGER.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)

            metrics = dict(row.get("metrics") or {})
            metrics["feature_source"] = row.get("feature_source")
            metrics["is_synthetic"] = row.get("is_synthetic")
            metrics["features"] = row.get("features")

            session.execute(
                UPSERT_SQL,
                dict(
                    id=row["id"],
                    component=row["component"],
                    algorithm=row.get("algorithm"),
                    trained_at=row.get("trained_at"),
                    training_event_ids=row.get("training_event_ids") or [],
                    cv_scheme=row.get("cv_scheme"),
                    hyperparams=json.dumps(row.get("hyperparams") or {}),
                    metrics=json.dumps(metrics),
                    artifact_path=row.get("artifact_path"),
                    git_commit=row.get("git_commit"),
                ),
            )
            n += 1
    return n


if __name__ == "__main__":
    n = load_model_versions()
    print(f"Upserted {n} model_versions row(s).")
