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
from models.sediment_proxy import (ANCHOR_CATCHMENT, ANCHOR_EVENT,  # noqa: E402
                                   SedimentProxy)

DATA = ROOT / "data/processed/features/training_set_full.parquet"

# Same cutoff as backend/src/models/validation.py's (unused, mismatched-schema)
# temporal_holdout(): train on everything strictly before this year, test on
# everything at or after it.
TEMPORAL_CUTOFF_YEAR = 2015


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


def temporal_holdout(df, feats):
    """Train on data strictly before TEMPORAL_CUTOFF_YEAR, test on everything after.

    A DIFFERENT claim from LOCO, and from the calibration slice above. The
    calibration slice only says the CALIBRATOR has not seen the test rows -
    the classifier trained on all of it. This is the split that lets the
    pitch say "the model never saw October 2016 during training" and mean
    it: 2016 rows are in the test side, not the fit side, full stop.

    `Component D · Runoff Risk Model` calls for exactly this ("train <=2014,
    test >=2015") in tasks/phase2/00-phase2-plan.md - measured here for the
    first time against the shipped CD- configuration. Phase 4 task 2 found
    it existed nowhere: not in reports/, not in model_versions.jsonl. The
    module `backend/src/models/validation.py` has a same-named function, but
    it targets column names (`runoff_label`, `event_time_utc`) this table
    does not have, so it has never actually run against this data - this is
    a fresh implementation on this table's real columns, not a call to it.
    """
    yr = df["date"].dt.year
    tr_raw, te = df[yr < TEMPORAL_CUTOFF_YEAR], df[yr >= TEMPORAL_CUTOFF_YEAR]

    f = build_fold(tr_raw, te, feats)
    m = WeightedGBM(scale_pos_weight=f.scale_pos_weight, **FX.PARAMS)
    m.fit(f.fit_X, f.fit_y).calibrate(f.cal_X, f.cal_y)
    p = m.predict_proba(f.test_X)
    b = RuleBaseline().fit(f.fit_X, f.fit_y).predict_proba(f.test_X)

    te = te.reset_index(drop=True)
    te["p"] = p

    # The headline claim, made checkable: where does the anchor storm rank
    # among AQ-C01's OWN held-out days - not mixed with the other four
    # catchments, which is a different and easier question.
    c1 = te[te[FX.GROUP] == ANCHOR_CATCHMENT].copy()
    c1["rank"] = c1["p"].rank(ascending=False, method="min").astype(int)
    day = ANCHOR_EVENT.removeprefix("AQ-")
    anchor_row = c1[c1["date"].dt.strftime("%Y-%m-%d") == day]

    result = {
        "cutoff_year": TEMPORAL_CUTOFF_YEAR,
        "train_rows": int(len(tr_raw)), "test_rows": int(len(te)),
        "train_pos_rate": round(float(tr_raw[FX.TARGET].mean()), 4),
        "test_pos_rate": round(float(te[FX.TARGET].mean()), 4),
        "AP": float(average_precision_score(f.test_y, p)),
        "baseline_AP": float(average_precision_score(f.test_y, b)),
        "ROC_AUC": float(roc_auc_score(f.test_y, p)),
        "Brier": float(brier_score_loss(f.test_y, p)),
    }
    if not anchor_row.empty:
        r, n = int(anchor_row["rank"].iloc[0]), len(c1)
        result["anchor_catchment"] = ANCHOR_CATCHMENT
        result["anchor_rank_among_catchment_only"] = r
        result["anchor_n_days_in_catchment_test_set"] = n
        result["anchor_percentile"] = round(100 * (1 - r / n), 2)
    return result


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

    print(f"\nTEMPORAL HOLDOUT — train <{TEMPORAL_CUTOFF_YEAR}, test >={TEMPORAL_CUTOFF_YEAR}:")
    th = temporal_holdout(df, feats)
    print(f"  train {th['train_rows']:,} rows ({th['train_pos_rate']:.1%} pos)   "
          f"test {th['test_rows']:,} rows ({th['test_pos_rate']:.1%} pos)")
    print(f"  AP {th['AP']:.4f}   baseline {th['baseline_AP']:.4f}   "
          f"ROC_AUC {th['ROC_AUC']:.4f}   Brier {th['Brier']:.4f}")
    if "anchor_rank_among_catchment_only" in th:
        print(f"  {ANCHOR_EVENT}/{ANCHOR_CATCHMENT} ranks "
              f"{th['anchor_rank_among_catchment_only']} of "
              f"{th['anchor_n_days_in_catchment_test_set']} unseen "
              f"{ANCHOR_CATCHMENT} days ({th['anchor_percentile']}th percentile)")

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
    # Left unanchored on purpose. `k` is a calibration constant, not a learned
    # parameter, and baking it into this artifact would mean rewriting a
    # trained file to store one float every time the anchor is recalibrated -
    # invalidating its git_commit provenance for a change unrelated to
    # training. `scripts/27_anchor_sediment_proxy.py` writes the anchor to a
    # sidecar (`data/models/sediment_anchor.json`) instead; `runoff_model`
    # applies and drift-checks it at load time. Run that script after this one.
    sediment = SedimentProxy()

    metrics = {
        "cv_scheme": "leave_one_catchment_out",
        "temporal_holdout_AP": round(th["AP"], 4),
        "temporal_holdout_baseline_AP": round(th["baseline_AP"], 4),
        "temporal_holdout_ROC_AUC": round(th["ROC_AUC"], 4),
        "temporal_holdout_Brier": round(th["Brier"], 4),
        "temporal_holdout_split": {
            "cutoff_year": th["cutoff_year"], "train_rows": th["train_rows"],
            "test_rows": th["test_rows"], "train_pos_rate": th["train_pos_rate"],
            "test_pos_rate": th["test_pos_rate"],
        },
        "temporal_holdout_anchor_check": (
            {k: th[k] for k in ("anchor_catchment", "anchor_rank_among_catchment_only",
                                "anchor_n_days_in_catchment_test_set", "anchor_percentile")}
            if "anchor_rank_among_catchment_only" in th else None
        ),
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
        "_note": ("mean_AP/pooled_AP/etc. are LOCO - a DIFFERENT split from "
                  "temporal_holdout_AP, and neither is the shipped model's "
                  "own-rows score (not computed, would be meaningless). LOCO "
                  "tests transfer to an unseen CATCHMENT; temporal_holdout "
                  "tests transfer to an unseen TIME PERIOD - specifically, "
                  "that the classifier's training data ends before "
                  f"{TEMPORAL_CUTOFF_YEAR}, which is what licenses any claim "
                  "of the form 'the model never saw this storm during "
                  "training'. Do not quote temporal_holdout_AP as LOCO or "
                  "vice versa."),
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
