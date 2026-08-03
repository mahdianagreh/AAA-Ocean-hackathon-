"""Compare three predictors, with hyperparameters tuned honestly.

    rule_baseline    SCS curve number, nothing fitted
    weighted_gbm     classify the binary target
    magnitude_gbm    regress log(sro), then calibrate to a probability

TUNING WITHOUT CHEATING
-----------------------
Hyperparameters are chosen by NESTED cross-validation. Inside each outer LOCO
fold, the four training catchments are themselves split leave-one-out, the grid
is scored on those inner folds, and only the winner is fitted and evaluated on
the outer held-out catchment.

The outer test fold is never involved in the choice. Tuning against outer LOCO
scores would fit hyperparameters to five numbers and report the result as
generalisation - which is the same class of error as the leaked feature, one
level up.

Inner folds preserve the catchment split rather than shuffling, because static
features are constant per catchment and a random inner split would pick
parameters that reward memorisation.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

from models import features as FX          # noqa: E402
from models.imbalance import build_fold                                # noqa: E402
from models.predictors import MagnitudeGBM, RuleBaseline, WeightedGBM  # noqa: E402

DATA = ROOT / "data/processed/features/training_set_full.parquet"
REPORT = ROOT / "reports/model/tuning.md"

EVENT_VARYING = ["precipitation_mm_day", "precip_prior_1d_mm",
                 "precip_prior_3d_mm", "precip_prior_7d_mm",
                 "soil_moisture_lag1d", "soil_moisture_lag3d",
                 # from the same ERA5 files, previously unread
                 "wind_speed_ms", "wind_direction_deg", "temp_c",
                 "season_sin", "season_cos"]
STATIC = ["area_km2", "slope_mean_deg", "drainage_density_km_km2",
          "elongation_ratio"]
FEATS = EVENT_VARYING + STATIC

# Deliberately small. With 6 event-varying features and a noisy label this is a
# signal problem, not a fitting problem - a large grid would mostly buy
# variance. 12 combinations x 4 inner folds x 5 outer folds = 240 fits.
GRID = {
    "max_depth": [3, 4, 6],
    "learning_rate": [0.03, 0.08],
    "min_child_weight": [2.0, 8.0],
}


def grid_points():
    keys = list(GRID)
    for vals in itertools.product(*(GRID[k] for k in keys)):
        yield dict(zip(keys, vals))


def score_params(train_df, params, kind: str) -> float:
    """Mean inner-LOCO average precision for one parameter set."""
    aps = []
    for c in sorted(train_df.catchment_id.unique()):
        inner_tr = train_df[train_df.catchment_id != c]
        inner_te = train_df[train_df.catchment_id == c]
        if inner_te.target.sum() < 5 or inner_tr.target.sum() < 20:
            continue
        f = build_fold(inner_tr, inner_te, FEATS)
        if kind == "classify":
            m = WeightedGBM(scale_pos_weight=f.scale_pos_weight, **params)
            m.fit(f.fit_X, f.fit_y)
        else:
            mag = inner_tr.sort_values("date")
            cut = int(len(mag) * 0.75)
            fit_rows = mag.iloc[:cut]
            m = MagnitudeGBM(**params)
            m.fit(fit_rows[FEATS], fit_rows.sro_mm_day.to_numpy())
        m.calibrate(f.cal_X, f.cal_y)
        p = m.predict_proba(f.test_X)
        if len(np.unique(f.test_y)) > 1:
            aps.append(average_precision_score(f.test_y, p))
    return float(np.mean(aps)) if aps else float("nan")


def main():
    df = pd.read_parquet(DATA)
    print(f"{len(df):,} rows · {int(df.target.sum())} positive "
          f"({df.target.mean():.1%}) · {len(FEATS)} features")
    print(f"grid: {len(list(grid_points()))} combinations, nested inner-LOCO\n")

    rows, chosen = [], []
    for c in sorted(df.catchment_id.unique()):
        train_df = df[df.catchment_id != c]
        test_df = df[df.catchment_id == c]
        fold = build_fold(train_df, test_df, FEATS)

        base = RuleBaseline().fit(fold.fit_X, fold.fit_y)
        ap_base = average_precision_score(fold.test_y,
                                          base.predict_proba(fold.test_X))

        best = {}
        for kind in ("classify", "regress"):
            scored = [(score_params(train_df, g, kind), g) for g in grid_points()]
            scored = [(s, g) for s, g in scored if not np.isnan(s)]
            scored.sort(key=lambda t: -t[0])
            best[kind] = scored[0]

        # classifier with its chosen params
        pc = best["classify"][1]
        mc = WeightedGBM(scale_pos_weight=fold.scale_pos_weight, **pc)
        mc.fit(fold.fit_X, fold.fit_y).calibrate(fold.cal_X, fold.cal_y)
        ap_c = average_precision_score(fold.test_y, mc.predict_proba(fold.test_X))

        # regressor with its chosen params
        pr = best["regress"][1]
        tr_sorted = train_df.sort_values("date")
        cut = int(len(tr_sorted) * 0.75)
        fit_rows = tr_sorted.iloc[:cut]
        mr = MagnitudeGBM(**pr)
        mr.fit(fit_rows[FEATS], fit_rows.sro_mm_day.to_numpy())
        mr.calibrate(fold.cal_X, fold.cal_y)
        ap_r = average_precision_score(fold.test_y, mr.predict_proba(fold.test_X))

        rows.append({"held_out": c, "test_pos": int(fold.test_y.sum()),
                     "baseline": round(ap_base, 4),
                     "classify": round(ap_c, 4), "regress": round(ap_r, 4),
                     "best": "regress" if ap_r > ap_c else "classify"})
        chosen.append({"held_out": c,
                       "classify_params": pc, "classify_inner_AP": round(best["classify"][0], 4),
                       "regress_params": pr, "regress_inner_AP": round(best["regress"][0], 4)})
        print(f"  {c}: baseline {ap_base:.4f} · classify {ap_c:.4f} · regress {ap_r:.4f}")

    res = pd.DataFrame(rows)
    print()
    print(res.to_string(index=False))
    b, c_, r = res.baseline.mean(), res["classify"].mean(), res.regress.mean()
    print(f"\nmean AP   baseline {b:.4f}   classify {c_:.4f}   regress {r:.4f}")
    print(f"  regress vs classify: {r - c_:+.4f}")
    print(f"  best vs baseline   : {max(c_, r) - b:+.4f}")

    print("\nchosen hyperparameters per outer fold (from inner CV only):")
    for row in chosen:
        print(f"  {row['held_out']}  classify {row['classify_params']} "
              f"(inner AP {row['classify_inner_AP']})")
        print(f"            regress  {row['regress_params']} "
              f"(inner AP {row['regress_inner_AP']})")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# Tuning and model comparison

**Date:** 3 August 2026 · `scripts/16_tune_and_compare.py`
**Data:** {len(df):,} catchment-days, {int(df.target.sum())} positive ({df.target.mean():.1%})
**Features:** {len(FEATS)} ({len(EVENT_VARYING)} event-varying, {len(STATIC)} static)

## Results — LOCO, average precision

{res.to_markdown(index=False)}

| | mean AP |
|---|---:|
| rule baseline | {b:.4f} |
| classify binary | {c_:.4f} |
| regress log magnitude | {r:.4f} |

**regress − classify: {r - c_:+.4f}** · **best − baseline: {max(c_, r) - b:+.4f}**

## Why regression was tried

The classifier discards the target at the threshold: a day at 0.0021 mm and one
at 0.19 mm get the same label though they are two orders of magnitude apart.
Regressing `log(sro)` keeps that ordering, and the predicted magnitude is then
calibrated to a probability on the same natural-prevalence set — so both models
run through identical splits and identical metrics.

## How the hyperparameters were chosen

**Nested cross-validation.** Inside each outer LOCO fold the four training
catchments are split leave-one-out again, the {len(list(grid_points()))}-point grid
is scored on those inner folds, and only the winner is evaluated on the outer
held-out catchment. The outer fold takes no part in the choice.

Tuning against outer LOCO scores would fit hyperparameters to five numbers and
then report the result as generalisation — the same class of error as a leaked
feature, one level up.

Inner folds keep the catchment split rather than shuffling: static features are
constant per catchment, so a random inner split would select parameters that
reward memorisation.

The grid is small on purpose. With six event-varying features and a label that is
itself modelled, this is a signal problem rather than a fitting problem, and a
large grid would mostly buy variance.
""")
    print(f"\nwrote {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
