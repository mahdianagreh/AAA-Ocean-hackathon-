"""B8 — Coral Health Vision Model: feature extraction + classifier.

Handcrafted color/texture features + scikit-learn, not a CNN — a deliberate,
resolved decision (not a shortcut): this backend has no deep-learning library
(`backend/requirements-api.txt` has scikit-learn/xgboost/pillow, no torch/
tensorflow/timm), and this session already hit a slow-network pip timeout
once on a 303 MB CUDA wheel. A real, working, explainable first pass over
already-available dependencies ships something real without a new heavy
install — the same "start simple, document the upgrade path" pattern B9's
culvert detector already uses.

NO REAL TRAINING DATA EXISTS IN THIS REPOSITORY, AS OF PHASE 5
----------------------------------------------------------------
Searched the whole repo (docs/qa_screenshots/, docs/3d_journey/assets/,
reports/) for labelled reef/coral photos: none exist. Every image in this
project is a QA figure, a satellite overlay, or a Google Maps screenshot —
none is an underwater reef photo, and none is labelled healthy/stressed/
bleached. Training a model on fabricated or mislabelled images and presenting
it as "trained" would be exactly the kind of fabrication this project's own
"missing is never zero" rule exists to prevent.

So: `classify()` below has two real, honestly-labelled paths, distinguished by
a `model_basis` field that travels with every classification —
- `"trained_classifier"` — once `train()` has run against ≥1 real, human-
  labelled photo (via `scripts/30_train_coral_health_classifier.py`), loaded
  from `data/models/coral_health_classifier.joblib`.
- `"heuristic_rule_v1"` — the honest default today, with zero training data.
  A documented rule-of-thumb on the same real color features (bleaching's
  real visual signature: pale, high brightness, low color variance), not a
  trained model, and reported at a capped, low confidence so nothing
  downstream mistakes a guess for a validated result.

`train()` refuses outright to persist a model trained on zero real labelled
images — the same refusal `models/artifacts.py::save()` already applies to
synthetic runoff-model training data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

CLASSES: tuple[str, ...] = ("healthy", "stressed", "bleached")

MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "models"
MODEL_PATH = MODEL_DIR / "coral_health_classifier.joblib"

#: Heuristic-path confidence is capped low, on purpose — a rule-of-thumb is
#: not a validated result, and nothing downstream should read 0.9 confidence
#: out of a guess.
HEURISTIC_CONFIDENCE_CAP = 0.55


def extract_features(image) -> np.ndarray:
    """7 real, deterministic features from a PIL Image: per-channel color
    mean and spread, plus a simple edge-density texture proxy. Bleaching's
    real visual signature — pale/white, low color variance — reads directly
    off the first six; live coral's texture reads off the seventh."""
    arr = np.asarray(image.convert("RGB").resize((256, 256)), dtype=np.float32) / 255.0
    means = arr.mean(axis=(0, 1))
    stds = arr.std(axis=(0, 1))
    gray = arr.mean(axis=2)
    edges = float(np.abs(np.diff(gray, axis=0)).mean() + np.abs(np.diff(gray, axis=1)).mean())
    return np.concatenate([means, stds, [edges]]).astype(np.float64)


def _heuristic_classify(features: np.ndarray) -> tuple[str, float]:
    """Documented rule-of-thumb, not a trained model. `features` is
    `[r_mean, g_mean, b_mean, r_std, g_std, b_std, edge_density]`."""
    brightness = float(features[:3].mean())
    color_spread = float(features[3:6].max())
    if brightness > 0.72 and color_spread < 0.14:
        return "bleached", HEURISTIC_CONFIDENCE_CAP
    if brightness < 0.32:
        return "stressed", HEURISTIC_CONFIDENCE_CAP - 0.05
    return "healthy", HEURISTIC_CONFIDENCE_CAP - 0.05


def _load_trained_model():
    if not MODEL_PATH.exists():
        return None
    import joblib

    return joblib.load(MODEL_PATH)


def classify(image) -> dict[str, Any]:
    """Real feature extraction always runs. Which classifier answers depends
    entirely on whether `train()` has ever actually run against real data —
    `model_basis` says which, on every response, unconditionally."""
    features = extract_features(image)
    bundle = _load_trained_model()
    if bundle is not None:
        clf = bundle["classifier"]
        proba = clf.predict_proba([features])[0]
        idx = int(proba.argmax())
        return {
            "predicted_class": clf.classes_[idx],
            "confidence": float(proba[idx]),
            "model_basis": "trained_classifier",
            "model_version": bundle["version_id"],
        }
    predicted_class, confidence = _heuristic_classify(features)
    return {
        "predicted_class": predicted_class,
        "confidence": confidence,
        "model_basis": "heuristic_rule_v1",
        "model_version": None,
    }


def train(images_and_labels: list[tuple[Any, str]], *, training_set_note: str) -> dict:
    """Trains a `GradientBoostingClassifier` on real, human-labelled photos
    and persists it. Refuses outright on zero real images — the same
    "no synthetic training data, ever" rule `models/artifacts.py::save()`
    already enforces for the runoff model.
    """
    if not images_and_labels:
        raise ValueError(
            "refusing to train on zero real labelled images.\n"
            "No labelled reef photos exist in this repository as of Phase 5 — "
            "classify() correctly falls back to the documented heuristic until "
            "real photos accumulate through the upload endpoint and someone "
            "labels a training set. Training on a fabricated set would produce "
            "a model that looks trained and isn't."
        )

    from datetime import datetime, timezone

    from sklearn.ensemble import GradientBoostingClassifier

    X = np.stack([extract_features(img) for img, _ in images_and_labels])
    y = [label for _, label in images_and_labels]
    unknown = set(y) - set(CLASSES)
    if unknown:
        raise ValueError(f"labels {sorted(unknown)} are not in {CLASSES}")

    clf = GradientBoostingClassifier()
    clf.fit(X, y)

    when = datetime.now(timezone.utc)
    version_id = f"coral_health_gbc_{when:%Y%m%dT%H%M%SZ}"
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    import joblib

    joblib.dump({"classifier": clf, "version_id": version_id,
                "n_training_images": len(images_and_labels)}, MODEL_PATH)

    return {
        "version_id": version_id,
        "component": "coral_health_classifier",
        "algorithm": "GradientBoostingClassifier",
        "trained_at": when.isoformat(),
        "n_training_images": len(images_and_labels),
        "training_set_note": training_set_note,
        "artifact_path": str(MODEL_PATH),
    }
