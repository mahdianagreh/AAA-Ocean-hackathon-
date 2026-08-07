#!/usr/bin/env python3
"""Train B8's coral health classifier on real, human-labelled reef photos.

Phase 5, 04-pulga.md item 5 (B8). Reads
`data/raw/reef_photos/_training/{healthy,stressed,bleached}/*.jpg` — a real,
human-sorted training set someone builds by hand, one folder per class.

THIS SCRIPT WILL REFUSE TO RUN TODAY, AND THAT IS CORRECT
------------------------------------------------------------
As of Phase 5, `data/raw/reef_photos/_training/` does not exist: no real,
labelled reef photo has ever been added to this repository (confirmed by
searching the whole tree — every image here is a QA figure or a screenshot,
none is an underwater reef photo). Running this script today reports "0
training images found" and exits without training anything — the honest
outcome, not an error to work around. `models.coral_health_classifier.train()`
refuses outright to persist a model trained on zero real images, the same
rule `models/artifacts.py::save()` already applies to the runoff model.

Once real, labelled photos exist (via the upload endpoint, or dropped in by
hand), re-run this script — it appends a real row to
`data/models/model_versions.jsonl` (`component: "coral_health_classifier"`),
tracked exactly like the runoff GBM's lineage, and `classify()` picks up the
new artifact automatically (models/coral_health_classifier.py::_load_trained_model).

Run: .venv/bin/python scripts/30_train_coral_health_classifier.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

TRAINING_DIR = PROJECT_ROOT / "data" / "raw" / "reef_photos" / "_training"
LEDGER = PROJECT_ROOT / "data" / "models" / "model_versions.jsonl"


def collect_training_images() -> list[tuple[Path, str]]:
    """(path, label) for every real photo under `_training/<class>/`. An
    absent directory is zero images, not an error — the honest starting
    state of this feature."""
    from models.coral_health_classifier import CLASSES

    if not TRAINING_DIR.exists():
        return []
    found = []
    for cls in CLASSES:
        class_dir = TRAINING_DIR / cls
        if not class_dir.exists():
            continue
        for path in sorted(class_dir.glob("*.jpg")) + sorted(class_dir.glob("*.jpeg")):
            found.append((path, cls))
    return found


def main() -> int:
    from PIL import Image

    from models import coral_health_classifier as chc

    pairs = collect_training_images()
    print(f"Found {len(pairs)} real, human-labelled training image(s) under {TRAINING_DIR}")
    if not pairs:
        print(
            "0 training images found — nothing trained. This is the correct, "
            "honest outcome, not a failure to fix: no real labelled reef photo "
            "exists in this repository yet. classify() continues to use the "
            "documented heuristic (model_basis='heuristic_rule_v1') until a "
            "real training set exists here."
        )
        return 0

    images_and_labels = [(Image.open(p), label) for p, label in pairs]
    row = chc.train(
        images_and_labels,
        training_set_note=f"{len(pairs)} real images from {TRAINING_DIR}",
    )

    ledger_row = {
        "id": row["version_id"],
        "component": row["component"],
        "algorithm": row["algorithm"],
        "trained_at": row["trained_at"],
        "training_event_ids": [],
        "cv_scheme": "none — first-pass classifier, no holdout with this few images",
        "hyperparams": {},
        "metrics": {"n_training_images": row["n_training_images"]},
        "artifact_path": row["artifact_path"],
        "git_commit": "unknown",
        "feature_source": row["training_set_note"],
        "is_synthetic": False,
        "features": ["r_mean", "g_mean", "b_mean", "r_std", "g_std", "b_std", "edge_density"],
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as fh:
        fh.write(json.dumps(ledger_row) + "\n")

    print(f"Trained {row['version_id']} on {row['n_training_images']} real images "
         f"-> {row['artifact_path']}")
    print(f"Ledger row appended to {LEDGER}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
