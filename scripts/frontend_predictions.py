#!/usr/bin/env python3
"""Run the registered model over the demo event and commit the predictions.

This closes OPEN-ISSUES #15. Until now the frontend rendered `runoff_probability`
as a gap and every risk card said "no trained model is registered", because
`data/models/` did not exist. It does now:

    runoff_weighted_gbm_2194b48_20260803T214757Z
    leave-one-catchment-out mean AP 0.7474 against a 0.2004 baseline
    is_synthetic: false, 2,362 training events, 20 features

So the cards can show real model output instead of the transparent stand-in index
they were using. That is a straight upgrade in honesty: a measured prediction with
its own SHAP attributions beats a hand-rolled proxy, however well the proxy was
labelled.

WHY DERIVED RATHER THAN CALLED. The API that serves /api/v1/runoff/predict does not
start — `backend/src/api/main.py` imports `from ..exposure import ...` and dies with
"attempted relative import beyond top-level package" (OPEN-ISSUES #21). Even once it
does, DoD item 9 requires the demo to work with no network and no API, so the
predictions have to exist as a committed artefact regardless. Same pattern as the
basemap: derive in the worker, commit, serve offline.

The feature row comes from training_set_full.parquet, which is the only table
carrying all 20 model features and does cover the demo window — 5 catchments x
5 days.

    docker compose run --rm --no-deps --entrypoint "" \\
      -v "$PWD/frontend/public/fixtures:/out" \\
      worker python /app/scripts/frontend_predictions.py --out /out
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
from models import artifacts, runoff_model  # noqa: E402

EVENT_ID = "AQ-2016-10-28"
WINDOW = ("2016-10-26", "2016-10-30")
TRAINING_SET = ROOT / "data" / "processed" / "features" / "training_set_full.parquet"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    version = artifacts.latest_version()
    if version is None:
        print("  NO MODEL REGISTERED — nothing to derive.")
        print("  The frontend keeps its stand-in index and says so, which is correct.")
        return 1

    feats = list(version["features"])
    d = pd.read_parquet(TRAINING_SET)
    d["date"] = pd.to_datetime(d["date"], utc=True, errors="coerce")
    lo, hi = (pd.Timestamp(x, tz="UTC") for x in WINDOW)
    d = d[(d.date >= lo) & (d.date <= hi)].sort_values(["catchment_id", "date"])

    print("ReefShield frontend predictions")
    print("=" * 66)
    print(f"  model      {version['id']}")
    print(f"  algorithm  {version['algorithm']}   synthetic: {version['is_synthetic']}")
    m = version.get("metrics", {})
    print(f"  cv         {m.get('cv_scheme')}  mean AP {m.get('mean_AP')}  "
          f"baseline {m.get('baseline_mean_AP')}")
    print(f"  rows       {len(d)} ({d.catchment_id.nunique()} catchments x "
          f"{d.date.nunique()} days)")
    print()

    missing = [f for f in feats if f not in d.columns]
    if missing:
        print(f"  ABORT: training set lacks {len(missing)} model features: {missing[:6]}")
        return 1

    by_catchment: dict[str, list] = {}
    failures = 0
    for _, row in d.iterrows():
        payload = {f: (None if pd.isna(row[f]) else float(row[f])) for f in feats}
        payload["catchment_id"] = row["catchment_id"]
        try:
            r = runoff_model.predict_one(payload)
        except Exception as exc:  # noqa: BLE001 — one bad row must not lose the rest
            failures += 1
            print(f"    {row['catchment_id']} {row['date'].date()}  FAILED {type(exc).__name__}")
            continue

        # Only the fields the UI renders, and each with the provenance the model
        # layer itself reports. `is_stub` travels through so a stub prediction can
        # never be mistaken for a trained one downstream.
        by_catchment.setdefault(row["catchment_id"], []).append(
            {
                "t": row["date"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                "is_stub": bool(r.get("is_stub")),
                "runoff_probability": r.get("runoff_probability"),
                # Always null — predict_one() never returns this key. A classifier
                # has no volume to report; the frontend renders the gap rather than
                # omitting the field, so the card states what it does not know.
                "predicted_runoff_m3": r.get("predicted_runoff_m3"),
                "severity": r.get("severity"),
                "confidence": r.get("confidence"),
                "confidence_terms": r.get("confidence_terms"),
                # None unless the sediment proxy is anchored — the model layer
                # returns null rather than a class it cannot support, and that
                # travels to the screen as a gap.
                "sediment_class": r.get("sediment_class"),
                "sediment_index": r.get("sediment_index"),
                "sediment_basis": r.get("sediment_basis"),
                "transmission_loss": r.get("transmission_loss"),
                "drivers": [
                    {
                        "key": a.get("feature"),
                        "contribution": a.get("shap"),
                        # Often null in the model's own output; the UI renders that
                        # as a gap rather than substituting the input value.
                        "value": a.get("value"),
                    }
                    for a in (r.get("feature_attributions") or [])
                ],
            }
        )

    for cid, rows in sorted(by_catchment.items()):
        probs = [f"{x['runoff_probability']:.4f}" for x in rows]
        sev = [x["severity"] for x in rows]
        print(f"  {cid}  p={' '.join(probs)}")
        print(f"          severity={' '.join(sev)}")

    payload = {
        "event_id": EVENT_ID,
        "model": {
            "version_id": version["id"],
            "algorithm": version["algorithm"],
            "is_synthetic": bool(version["is_synthetic"]),
            "cv_scheme": m.get("cv_scheme"),
            "mean_AP": m.get("mean_AP"),
            "baseline_mean_AP": m.get("baseline_mean_AP"),
            "trained_at": version.get("trained_at"),
            "n_training_events": len(version.get("training_event_ids") or []),
            "features": feats,
        },
        "feature_source": str(TRAINING_SET.relative_to(ROOT)),
        # Stated so the UI can say where the numbers came from. These are real model
        # outputs computed offline, not a live call — and not a stand-in either.
        "derivation": "offline: scripts/frontend_predictions.py over the registered artefact",
        "by_catchment": by_catchment,
    }
    (out / "predictions.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))

    size = (out / "predictions.json").stat().st_size
    print()
    print("=" * 66)
    print(f"  {sum(len(v) for v in by_catchment.values())} predictions, "
          f"{failures} failures, {size:,} B")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
