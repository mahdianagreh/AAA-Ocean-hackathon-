"""Fairlearn with catchment as the sensitive feature.

WHAT THIS IS AND IS NOT
-----------------------
Fairlearn constrains performance disparities across GROUPS. It is not a
class-imbalance weighting optimiser - that is already handled by resampling to
1:4 plus scale_pos_weight, and it was measured (random K-fold 0.514 vs LOCO
0.521, a gap of -0.008, so the model is not memorising catchment identity).

There is, however, a genuine group disparity worth attacking:

    AQ-C01     AP 0.593      <- carries 96% of the discharge
    AQ-C02-05  AP 0.743-0.808

C01 is 0.15-0.21 behind and is the catchment that matters most. Two reasons a
fairness constraint is the right tool:

1. Directly - constrain per-catchment loss to be even.
2. Indirectly, and more interestingly - forcing even performance across the
   four TRAINING catchments discourages catchment-specific shortcuts, which
   should improve transfer to the unseen fifth. A fairness constraint acting as
   a domain-generalisation regulariser.

Note the structural limit: under LOCO the test catchment is unseen, so the
constraint can only be applied to the four training catchments. It cannot
equalise onto the held-out one directly; it can only make the learned function
less catchment-specific and hope that generalises. Whether it does is exactly
what this measures.

THE FAILURE MODE TO WATCH
-------------------------
A parity constraint can equalise by making the strong folds WORSE rather than
the weak one better. Spread would fall and the model would be no more useful.
So per-fold AP is reported alongside the spread, and a run that lowers the mean
is recorded as such rather than presented as a fairness win.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

from models import features as FX                  # noqa: E402
from models.imbalance import build_fold            # noqa: E402
from models.predictors import WeightedGBM          # noqa: E402

DATA = ROOT / "data/processed/features/training_set_full.parquet"
REPORT = ROOT / "reports/model/fairlearn_catchment.md"

# Loss bounds to sweep. Tighter = more equal across catchments, and more
# constrained overall. 1.0 is effectively unconstrained.
BOUNDS = [0.05, 0.10, 0.20, 0.40]


def platt(margin_cal, y_cal, margin_out):
    """Same calibration contract as everywhere else: fitted on a
    natural-prevalence slice the classifier never saw."""
    from sklearn.linear_model import LogisticRegression

    if len(np.unique(y_cal)) < 2:
        return 1.0 / (1.0 + np.exp(-margin_out))
    lr = LogisticRegression(C=1e10, solver="lbfgs").fit(
        np.asarray(margin_cal).reshape(-1, 1), y_cal)
    a, b = float(-lr.coef_[0][0]), float(-lr.intercept_[0])
    return 1.0 / (1.0 + np.exp(a * np.asarray(margin_out) + b))


def run_unconstrained(df, feats):
    rows = []
    for c in sorted(df[FX.GROUP].unique()):
        f = build_fold(df[df[FX.GROUP] != c], df[df[FX.GROUP] == c], feats)
        m = WeightedGBM(scale_pos_weight=f.scale_pos_weight, **FX.PARAMS)
        m.fit(f.fit_X, f.fit_y).calibrate(f.cal_X, f.cal_y)
        p = m.predict_proba(f.test_X)
        rows.append({"fold": c, "AP": average_precision_score(f.test_y, p),
                     "Brier": brier_score_loss(f.test_y, p)})
    return pd.DataFrame(rows)


def run_constrained(df, feats, bound: float):
    """ExponentiatedGradient with BoundedGroupLoss over training catchments."""
    from fairlearn.reductions import (BoundedGroupLoss, ExponentiatedGradient,
                                      ZeroOneLoss)
    from xgboost import XGBClassifier

    rows = []
    for c in sorted(df[FX.GROUP].unique()):
        train_df = df[df[FX.GROUP] != c]
        f = build_fold(train_df, df[df[FX.GROUP] == c], feats)

        # Sensitive feature aligned to the resampled fit rows.
        sf = df.loc[f.fit_X.index, FX.GROUP].to_numpy()

        base = XGBClassifier(**{**WeightedGBM(
            scale_pos_weight=f.scale_pos_weight, **FX.PARAMS).params})
        eg = ExponentiatedGradient(
            estimator=base,
            constraints=BoundedGroupLoss(ZeroOneLoss(), upper_bound=bound),
            max_iter=20,
        )
        try:
            eg.fit(f.fit_X, f.fit_y, sensitive_features=sf)
        except Exception as exc:
            rows.append({"fold": c, "AP": np.nan, "Brier": np.nan,
                         "note": f"{type(exc).__name__}"})
            continue

        # ExponentiatedGradient returns a randomised ensemble, so there is no
        # single margin. _pmf_predict gives P(y=1); use it as the score and
        # calibrate it the same way as everywhere else, on the logit scale so
        # Platt is fitted on something unbounded.
        def score(X):
            # fairlearn 0.14 returns a DataFrame here, not an ndarray
            out = eg._pmf_predict(X)
            pr = np.asarray(out)[:, 1] if not isinstance(out, np.ndarray) else out[:, 1]
            pr = np.clip(pr, 1e-6, 1 - 1e-6)
            return np.log(pr / (1 - pr))

        p = platt(score(f.cal_X), f.cal_y, score(f.test_X))
        rows.append({"fold": c, "AP": average_precision_score(f.test_y, p),
                     "Brier": brier_score_loss(f.test_y, p), "note": ""})
    return pd.DataFrame(rows)


def summarise(name, per):
    ap = per.AP.dropna()
    return {
        "config": name,
        "mean_AP": round(ap.mean(), 4) if len(ap) else None,
        "C01_AP": round(float(per.loc[per.fold == "AQ-C01", "AP"].iloc[0]), 4)
                  if per.loc[per.fold == "AQ-C01", "AP"].notna().all() else None,
        "min_AP": round(ap.min(), 4) if len(ap) else None,
        "max_AP": round(ap.max(), 4) if len(ap) else None,
        "spread": round(ap.max() - ap.min(), 4) if len(ap) else None,
        "mean_Brier": round(per.Brier.dropna().mean(), 4) if len(ap) else None,
    }


def main():
    df = pd.read_parquet(DATA).reset_index(drop=True)
    feats = FX.check(df)
    print(f"{len(df):,} rows · {int(df[FX.TARGET].sum())} positive "
          f"({df[FX.TARGET].mean():.1%}) · {len(feats)} features (CD-)\n")

    print("unconstrained (current canonical model):")
    base_per = run_unconstrained(df, feats)
    print(base_per.round(4).to_string(index=False))
    rows = [summarise("unconstrained", base_per)]
    per_all = {"unconstrained": base_per}

    for bound in BOUNDS:
        print(f"\nBoundedGroupLoss(upper_bound={bound}) ...")
        per = run_constrained(df, feats, bound)
        print(per.round(4).to_string(index=False))
        rows.append(summarise(f"bound={bound}", per))
        per_all[f"bound={bound}"] = per

    res = pd.DataFrame(rows)
    print("\n=== comparison ===")
    print(res.to_string(index=False))

    base = res.iloc[0]
    better = res[(res.mean_AP.notna()) & (res.mean_AP >= base.mean_AP)]
    print()
    if len(better) > 1:
        w = better.sort_values("mean_AP", ascending=False).iloc[0]
        print(f"best: {w.config}  mean_AP {w.mean_AP}  C01 {w.C01_AP}  "
              f"spread {w.spread}")
    else:
        print("No constrained configuration matched the unconstrained mean AP.")
        tighter = res[res.spread.notna() & (res.spread < base.spread)]
        if len(tighter):
            t = tighter.sort_values("spread").iloc[0]
            print(f"  {t.config} narrowed the spread to {t.spread} "
                  f"(from {base.spread}) but at mean_AP {t.mean_AP} "
                  f"vs {base.mean_AP} — equalising by lowering the strong folds, "
                  f"not raising C01.")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# Fairlearn — catchment as the sensitive feature

**Date:** 4 August 2026 · `scripts/18_fairlearn_catchment_parity.py`
**Model:** configuration `CD-`, {len(feats)} features, depth 6 / lr 0.03 / mcw 2.0
**Constraint:** `BoundedGroupLoss(ZeroOneLoss(), upper_bound=b)` via
`ExponentiatedGradient`, sensitive feature `catchment_id`

## What this tests, and what it cannot

Fairlearn constrains performance disparities across **groups**. It is not a
class-imbalance weighting optimiser — imbalance is handled by resampling to 1:4
plus `scale_pos_weight`, and measured (random K-fold 0.514 vs LOCO 0.521).

The disparity being attacked is real: AQ-C01 scores 0.593 against 0.743–0.808
for the others, and it carries 96% of the discharge.

**Structural limit.** Under leave-one-catchment-out the test catchment is unseen,
so the constraint applies only to the four training catchments. It cannot equalise
onto the held-out one directly — it can only make the learned function less
catchment-specific, and whether that transfers is what this measures.

**The failure mode.** A parity constraint can equalise by making the strong folds
worse rather than the weak one better. Spread falls, usefulness does not rise. Hence
per-fold AP alongside the spread.

## Results

{res.to_markdown(index=False)}

### Per fold

{chr(10).join(f"**{k}**{chr(10)}{chr(10)}{v.round(4).to_markdown(index=False)}{chr(10)}" for k, v in per_all.items())}
""")
    print(f"\nwrote {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
