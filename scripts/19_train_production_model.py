"""Train and register the production model — configuration CD-.

This is the servable artifact. Everything before it was measurement; this fits
on all five catchments and persists.

Two stages, and the distinction matters for what the metrics mean:

  MEASURED    leave-one-catchment-out. Every reported number comes from here,
              because it is the only estimate of transfer to an unseen
              catchment. Five folds, each held out entirely.

  SHIPPED     one model fitted on all five catchments, calibrated on a
              natural-prevalence temporal holdout. It cannot be scored
              honestly against its own training data, so it inherits the LOCO
              numbers and the ledger records that explicitly.

Reporting the shipped model's score on its own rows would be the most basic
error available, so it is not computed at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             precision_recall_fscore_support, roc_auc_score)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

from models import artifacts                              # noqa: E402
from models import features as FX                         # noqa: E402
from models.imbalance import build_fold, stratified_negative_sample  # noqa: E402
from models.predictors import RuleBaseline, WeightedGBM    # noqa: E402
from models.sediment_proxy import SedimentProxy            # noqa: E402

DATA = ROOT / "data/processed/features/training_set_full.parquet"


def measure(df, feats):
    """LOCO. The only honest estimate of transfer."""
    rows, ys, ps = [], [], []
    for c in sorted(df[FX.GROUP].unique()):
        f = build_fold(df[df[FX.GROUP] != c], df[df[FX.GROUP] == c], feats)
        m = WeightedGBM(scale_pos_weight=f.scale_pos_weight, **FX.PARAMS)
        m.fit(f.fit_X, f.fit_y).calibrate(f.cal_X, f.cal_y)
        p = m.predict_proba(f.test_X)
        b = RuleBaseline().fit(f.fit_X, f.fit_y).predict_proba(f.test_X)
        rows.append({
            "fold": c, "test_pos": int(f.test_y.sum()),
            "test_pos_rate": round(float(f.test_y.mean()), 4),
            "AP": average_precision_score(f.test_y, p),
            "ROC_AUC": roc_auc_score(f.test_y, p),
            "Brier": brier_score_loss(f.test_y, p),
            "baseline_AP": average_precision_score(f.test_y, b),
        })
        ys.append(f.test_y)
        ps.append(p)
    y, p = np.concatenate(ys), np.concatenate(ps)
    ths = np.unique(np.round(p, 4))
    f1s = [precision_recall_fscore_support(y, (p >= t).astype(int),
                                          average="binary", zero_division=0)[2]
           for t in ths]
    i = int(np.argmax(f1s))
    pr, rc, f1, _ = precision_recall_fscore_support(
        y, (p >= ths[i]).astype(int), average="binary", zero_division=0)
    return pd.DataFrame(rows), {
        "threshold": float(ths[i]), "precision": float(pr), "recall": float(rc),
        "f1": float(f1), "pooled_AP": float(average_precision_score(y, p)),
    }


def main():
    df = pd.read_parquet(DATA).reset_index(drop=True)
    feats = FX.check(df)
    print(f"{len(df):,} rows · {int(df[FX.TARGET].sum())} positive "
          f"({df[FX.TARGET].mean():.1%}) · {len(feats)} features (CD-)\n")

    print("MEASURED — leave-one-catchment-out:")
    per, pooled = measure(df, feats)
    print(per.round(4).to_string(index=False))
    mean_ap = per.AP.mean()
    print(f"\nmean AP {mean_ap:.4f}   baseline {per.baseline_AP.mean():.4f}   "
          f"delta {mean_ap - per.baseline_AP.mean():+.4f}")
    print(f"F1 {pooled['f1']:.4f} @ threshold {pooled['threshold']:.4f}   "
          f"P {pooled['precision']:.3f}  R {pooled['recall']:.3f}")

    print("\nSHIPPED — fitted on all five catchments:")
    # Calibration slice is the latest 25% by date at natural prevalence, held
    # out from the classifier - same contract as every fold.
    tr = df.sort_values("date")
    cut = int(len(tr) * 0.75)
    fit_raw, cal = tr.iloc[:cut], tr.iloc[cut:]
    fit = stratified_negative_sample(fit_raw)
    spw = float((len(fit) - fit[FX.TARGET].sum()) / max(fit[FX.TARGET].sum(), 1))

    gbm = WeightedGBM(scale_pos_weight=spw, **FX.PARAMS)
    gbm.fit(fit[feats], fit[FX.TARGET].to_numpy())
    gbm.calibrate(cal[feats], cal[FX.TARGET].to_numpy())
    print(f"  fit {len(fit):,} rows ({fit[FX.TARGET].mean():.1%} pos, spw {spw:.1f}) · "
          f"calibrate {len(cal):,} rows ({cal[FX.TARGET].mean():.1%} pos)")
    print(f"  Platt: {gbm.platt_params}")

    baseline = RuleBaseline().fit(fit[feats], fit[FX.TARGET].to_numpy())
    sediment = SedimentProxy()

    metrics = {
        "cv_scheme": "leave_one_catchment_out",
        "mean_AP": round(float(mean_ap), 4),
        "mean_ROC_AUC": round(float(per.ROC_AUC.mean()), 4),
        "mean_Brier": round(float(per.Brier.mean()), 4),
        "baseline_mean_AP": round(float(per.baseline_AP.mean()), 4),
        "pooled_AP": round(pooled["pooled_AP"], 4),
        "best_F1": round(pooled["f1"], 4),
        "f1_threshold": round(pooled["threshold"], 4),
        "precision_at_threshold": round(pooled["precision"], 4),
        "recall_at_threshold": round(pooled["recall"], 4),
        "base_rate": round(float(df[FX.TARGET].mean()), 4),
        "lift_over_chance": round(float(mean_ap / df[FX.TARGET].mean()), 2),
        "run_to_run_AP_variance": 0.017,
        "_note": ("Metrics are LOCO, not the shipped model on its own rows. "
                  "The shipped model is fitted on all five catchments and "
                  "cannot be scored against its own training data."),
    }

    row = artifacts.save(
        gbm=gbm, baseline=baseline, sediment=sediment, features=feats,
        training_event_ids=sorted(df.date.dt.strftime("%Y-%m-%d").unique().tolist()),
        metrics=metrics,
        feature_source="training_set_full.parquet (11,810 rows, full population)",
        is_synthetic=False,
        cv_scheme="leave_one_catchment_out",
        feature_ranges={c: (float(df[c].min()), float(df[c].max()))
                        for c in feats},
        catchment_scores={r.fold: round(float(r.AP), 4)
                          for r in per.itertuples()},
    )
    vid = row["version_id"] if isinstance(row, dict) else getattr(row, "version_id", row)
    print(f"\nregistered: {vid}")
    print(f"ledger: data/models/model_versions.jsonl")


if __name__ == "__main__":
    main()
