"""Every combination of the three cheap improvements, scored on LOCO.

    (1) climatology  rainfall normalised by each catchment's own distribution
    (2) dryspell     consecutive dry days before the event
    (4) weights      per-row label weights reflecting ERA5 label quality

2^3 = 8 combinations. Hyperparameters are FIXED across all of them at the
values nested CV chose in 16 (depth 6, lr 0.03, mcw 2.0), so the comparison
isolates the features. Re-tuning per combination would confound the two and
would also mean 8 x 12 x 4 x 5 fits for a question that does not need them.

Reported per fold, never as a mean alone: AQ-C01 is 96% of the discharge and
the hardest fold, so an improvement that raises the mean while lowering C01 is
not an improvement for this project.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss,
                             precision_recall_fscore_support)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

from models import features as FX          # noqa: E402
from models.imbalance import build_fold                    # noqa: E402
from models.predictors import RuleBaseline, WeightedGBM    # noqa: E402

DATA = ROOT / "data/processed/features/training_set_full.parquet"
REPORT = ROOT / "reports/model/ablation_sweep.md"

BASE = ["precipitation_mm_day", "precip_prior_1d_mm", "precip_prior_3d_mm",
        "precip_prior_7d_mm", "soil_moisture_lag1d", "soil_moisture_lag3d",
        "wind_speed_ms", "wind_direction_deg", "temp_c",
        "season_sin", "season_cos",
        "area_km2", "slope_mean_deg", "drainage_density_km_km2",
        "elongation_ratio"]

CLIMATOLOGY = ["rain_over_p50", "rain_over_p90", "rain_over_p99",
               "rain_self_percentile"]
DRYSPELL = ["dry_days_before"]

PARAMS = dict(max_depth=6, learning_rate=0.03, min_child_weight=2.0)


def loco(df, feats, use_weights: bool):
    """Per-fold metrics. Weights apply to the classifier fit only."""
    rows, ys, ps = [], [], []
    for c in sorted(df.catchment_id.unique()):
        f = build_fold(df[df.catchment_id != c], df[df.catchment_id == c], feats)
        m = WeightedGBM(scale_pos_weight=f.scale_pos_weight, **PARAMS)
        if use_weights:
            # Weights come from the resampled fit rows, aligned by index.
            w = df.loc[f.fit_X.index, "label_weight"].to_numpy()
            m._features = list(f.fit_X.columns)
            from xgboost import XGBClassifier
            m.raw = XGBClassifier(**m.params)
            m.raw.fit(f.fit_X, f.fit_y, sample_weight=w)
        else:
            m.fit(f.fit_X, f.fit_y)
        m.calibrate(f.cal_X, f.cal_y)
        p = m.predict_proba(f.test_X)
        rows.append({"fold": c, "AP": average_precision_score(f.test_y, p),
                     "Brier": brier_score_loss(f.test_y, p)})
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
    per = pd.DataFrame(rows)
    return per, {"mean_AP": per.AP.mean(), "C01_AP": per.loc[per.fold == "AQ-C01", "AP"].iloc[0],
                 "pooled_AP": average_precision_score(y, p),
                 "best_F1": f1, "precision": pr, "recall": rc,
                 "threshold": float(ths[i]), "mean_Brier": per.Brier.mean()}


def main():
    df = pd.read_parquet(DATA).reset_index(drop=True)
    print(f"{len(df):,} rows · {int(df.target.sum())} positive "
          f"({df.target.mean():.1%})\n")

    base_ap = np.mean([
        average_precision_score(
            build_fold(df[df.catchment_id != c], df[df.catchment_id == c], BASE).test_y,
            RuleBaseline().fit(*(lambda f: (f.fit_X, f.fit_y))(
                build_fold(df[df.catchment_id != c], df[df.catchment_id == c], BASE)))
            .predict_proba(build_fold(df[df.catchment_id != c],
                                      df[df.catchment_id == c], BASE).test_X))
        for c in sorted(df.catchment_id.unique())])
    print(f"rule baseline mean AP: {base_ap:.4f}\n")

    results, per_fold = [], {}
    for clim, dry, wts in itertools.product([False, True], repeat=3):
        feats = BASE + (CLIMATOLOGY if clim else []) + (DRYSPELL if dry else [])
        label = "".join([
            "C" if clim else "-", "D" if dry else "-", "W" if wts else "-"])
        per, m = loco(df, feats, wts)
        per_fold[label] = per
        results.append({"combo": label, "n_feat": len(feats),
                        "climatology": clim, "dryspell": dry, "weights": wts,
                        **{k: round(v, 4) for k, v in m.items()}})
        print(f"  {label}  {len(feats):>2} feats  "
              f"mean_AP {m['mean_AP']:.4f}  C01 {m['C01_AP']:.4f}  "
              f"F1 {m['best_F1']:.4f}  P {m['precision']:.3f}  R {m['recall']:.3f}")

    res = pd.DataFrame(results).sort_values("mean_AP", ascending=False)
    print("\n=== ranked by mean AP ===")
    cols = ["combo", "n_feat", "mean_AP", "C01_AP", "pooled_AP", "best_F1",
            "precision", "recall", "threshold", "mean_Brier"]
    print(res[cols].to_string(index=False))

    best = res.iloc[0]
    best_c01 = res.sort_values("C01_AP", ascending=False).iloc[0]
    print(f"\nbest by mean AP : {best.combo}  ({best.mean_AP:.4f})")
    print(f"best by C01 AP  : {best_c01.combo}  ({best_c01.C01_AP:.4f})"
          f"{'   <- SAME' if best.combo == best_c01.combo else '   <- DIFFERENT'}")
    print(f"\nper-fold detail, {best.combo}:")
    print(per_fold[best.combo].round(4).to_string(index=False))

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# Ablation sweep — all combinations

**Date:** 4 August 2026 · `scripts/17_ablation_sweep.py`
**Data:** {len(df):,} catchment-days, {int(df.target.sum())} positive ({df.target.mean():.1%})
**Hyperparameters:** fixed at depth 6 / lr 0.03 / min_child_weight 2.0 — the values
nested CV chose in `16_tune_and_compare.py`, held constant so the comparison isolates
the features rather than confounding them with tuning.

Codes: **C** = climatology-normalised rainfall · **D** = consecutive dry days ·
**W** = label-quality weights.

## Results

{res[cols].to_markdown(index=False)}

Rule baseline mean AP: **{base_ap:.4f}**

## Best

| | combo | mean AP | AQ-C01 AP |
|---|---|---:|---:|
| by mean AP | `{best.combo}` | {best.mean_AP:.4f} | {best.C01_AP:.4f} |
| by AQ-C01 AP | `{best_c01.combo}` | {best_c01.mean_AP:.4f} | {best_c01.C01_AP:.4f} |

**AQ-C01 is reported separately on purpose.** It carries 96% of the discharge and is
the hardest fold — train on four small catchments, predict the 4,453 km² one. A
combination that raises the mean while lowering C01 is not an improvement for this
project.

### Per fold, best combination

{per_fold[best.combo].round(4).to_markdown(index=False)}

## What each addition is

**C · climatology normalisation.** LOCO's difficulty is transfer to an unseen
catchment, and absolute millimetres do not transfer — 6 mm on 4,453 km² is not 6 mm
on 36 km². A position in the catchment's own wet-day distribution does.

**D · consecutive dry days.** Arid soil crusts when it bakes, and a crust sheds water
rather than absorbing it, which is why dry antecedent conditions *raise* runoff.
`soil_moisture_lag1d` captures wetness but not the duration of dryness that forms the
crust. Counted strictly before the day, so no same-day leak.

**W · label-quality weights.** AQ-C01's label is a 41-cell ERA5 area mean; the other
four are single cells, three of them nearest-cell point samples with no cell centre
inside the catchment. ERA5-Land is ~81 km² per cell against catchments of 36–65 km².
Weights 1.0 / 0.75 / 0.5 accordingly.

## Not included: more ERA5 months

77 of the ~193 wet-season months for 1998–2025 are on disk, so **120 are missing**.
Each CDS request queues independently, making this a background job measured in hours
rather than something that fits in a sweep. It is the one remaining cheap source of
hard negatives — 656 exist, and they are the binding constraint on the boundary.
""")
    print(f"\nwrote {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
