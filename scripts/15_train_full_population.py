"""Train Component A on the full population, with the three-way split.

    per fold:  fit (resampled 1:4)  |  calibrate (natural)  |  test (natural)

Runs four things and reports all of them:

  * the rule baseline, which the model must beat and which is reported even
    if it wins
  * the weighted GBM, calibrated on natural prevalence
  * LOCO, five folds, every fold shown
  * plain random K-fold, so the gap against LOCO measures the leakage

Karam's suggestion is the reason for the last one: if random CV scores much
higher than LOCO, that difference IS the catchment memorisation, with a number
on it. Reporting both is a stronger result than either alone.

    .venv/bin/python scripts/15_train_full_population.py
    .venv/bin/python scripts/15_train_full_population.py --event-varying-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

from models import validation                                  # noqa: E402
from models import features as FX          # noqa: E402
from models.imbalance import build_fold, hessian_floor_note     # noqa: E402
from models.predictors import RuleBaseline, WeightedGBM         # noqa: E402

DATA = ROOT / "data/processed/features/training_set_full.parquet"
CARD = ROOT / "docs/model_card.md"

# Same-day `soil_moisture` is EXCLUDED, and this is not a tuning choice.
#
# It is a daily MEAN, so it rises as the day's rain infiltrates - it is
# contemporaneous with the target, not antecedent. Measured against sro:
#
#     soil_moisture        (same day)  r = +0.384
#     soil_moisture_lag1d              r = +0.059
#     soil_moisture_lag3d              r = +0.015
#
# With it in, it was the top driver at 2.21 mean |SHAP| against rainfall's 0.44
# and LOCO AP came out at 0.836. That is the failure Karam warned about: it does
# not look like a bug, it looks like an excellent result. The lags are genuinely
# antecedent and stay.
EVENT_VARYING = [
    "precipitation_mm_day",
    "precip_prior_1d_mm", "precip_prior_3d_mm", "precip_prior_7d_mm",
    "soil_moisture_lag1d", "soil_moisture_lag3d",
    # Extracted from the same ERA5 month files as sro - wind and temperature
    # were simply not being read. Season is cyclical so Dec and Jan sit
    # adjacent: Aqaba's rain is almost all Oct-Mar, and autumn convective
    # storms behave differently from winter frontal ones.
    "wind_speed_ms", "wind_direction_deg", "temp_c",
    "season_sin", "season_cos",
]
# Four only, chosen for a physical reason rather than because they exist.
# Karam measured 115 static columns carrying five distinct values; handing a
# tree all of them lets it identify the catchment instead of learning the
# process. These four are the ones a hydrologist would name.
STATIC = ["area_km2", "slope_mean_deg", "drainage_density_km_km2",
          "elongation_ratio"]


def evaluate(fold, model_factory, calibrate: bool):
    m = model_factory(fold)
    m.fit(fold.fit_X, fold.fit_y)
    if calibrate and hasattr(m, "calibrate"):
        m.calibrate(fold.cal_X, fold.cal_y)
    p = m.predict_proba(fold.test_X)
    s = validation.score(fold.test_y, p)
    return m, p, s


def run_loco(df, feats, args):
    rows, calib_tables, models = [], [], []
    for c in sorted(df.catchment_id.unique()):
        fold = build_fold(df[df.catchment_id != c], df[df.catchment_id == c],
                          feats, neg_per_pos=args.neg_per_pos)
        base, _, sb = evaluate(fold, lambda f: RuleBaseline(), False)
        gbm, p, sg = evaluate(
            fold, lambda f: WeightedGBM(scale_pos_weight=f.scale_pos_weight), True)
        rows.append({
            "held_out": c,
            "fit_rows": fold.composition["fit_rows"],
            "test_rows": fold.composition["test_rows"],
            "test_pos": fold.composition["test_pos"],
            "test_pos_rate": round(fold.composition["test_pos_rate"], 4),
            "baseline_AP": None if sb["ap"] is None else round(sb["ap"], 4),
            "gbm_AP": None if sg["ap"] is None else round(sg["ap"], 4),
            "gbm_Brier": None if sg["brier"] is None else round(sg["brier"], 5),
            "calibrated": gbm.is_calibrated,
            "A": gbm.platt_params["A"], "B": gbm.platt_params["B"],
        })
        calib_tables.append((c, validation.calibration_table(fold.test_y, p)))
        models.append((c, gbm, fold))
        print(f"  {c}: {fold.summary()}")
    return pd.DataFrame(rows), calib_tables, models


def run_random_kfold(df, feats, args, k: int = 5):
    """Deliberately wrong split, run to measure how wrong it is."""
    from sklearn.model_selection import StratifiedKFold

    aps = []
    skf = StratifiedKFold(k, shuffle=True, random_state=20260803)
    for tr_i, te_i in skf.split(df, df.target):
        fold = build_fold(df.iloc[tr_i], df.iloc[te_i], feats,
                          neg_per_pos=args.neg_per_pos)
        _, _, s = evaluate(
            fold, lambda f: WeightedGBM(scale_pos_weight=f.scale_pos_weight), True)
        if s["ap"] is not None:
            aps.append(s["ap"])
    return float(np.mean(aps)) if aps else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--event-varying-only", action="store_true",
                    help="drop the four static features - the ablation")
    ap.add_argument("--neg-per-pos", type=int, default=4)
    args = ap.parse_args()

    df = pd.read_parquet(DATA)
    feats = EVENT_VARYING if args.event_varying_only else EVENT_VARYING + STATIC

    print(f"{len(df):,} rows · {int(df.target.sum()):,} positive "
          f"({df.target.mean():.1%}) · {len(feats)} features"
          f"{' (event-varying only)' if args.event_varying_only else ''}")
    print(f"\nwhy resampling is not cosmetic:")
    print(f"  {hessian_floor_note(df.target.mean(), 4.0)}")
    print(f"  {hessian_floor_note(0.20, 4.0)}")

    print("\nLOCO — five folds:")
    loco, calib_tables, models = run_loco(df, feats, args)
    print()
    print(loco.to_string(index=False))

    b = loco.baseline_AP.dropna().mean()
    g = loco.gbm_AP.dropna().mean()
    print(f"\nmean AP   baseline {b:.4f}   gbm {g:.4f}   delta {g - b:+.4f}")
    verdict = (f"GBM beats the baseline by {g - b:+.4f} AP" if g - b > 0.02
               else f"GBM does NOT clear the baseline ({g - b:+.4f} AP)")
    print(f"verdict: {verdict}")

    print("\nrandom K-fold (the wrong split, run to measure the leakage):")
    rk = run_random_kfold(df, feats, args)
    if rk is not None:
        print(f"  random-CV AP {rk:.4f}  vs  LOCO AP {g:.4f}  "
              f"->  leakage {rk - g:+.4f}")

    print("\ncalibration on the held-out catchment (AQ-C01):")
    print(calib_tables[0][1].to_string(index=False))

    print("\ntop drivers (SHAP, fold AQ-C01):")
    c, gbm, fold = models[0]
    sv = np.abs(gbm.shap_values(fold.test_X)).mean(axis=0)
    imp = pd.Series(sv, index=feats).sort_values(ascending=False)
    print(imp.head(8).round(4).to_string())

    write_card(df, feats, loco, b, g, rk, verdict, calib_tables[0], imp, args)
    print(f"\nwrote {CARD.relative_to(ROOT)}")


def write_card(df, feats, loco, b, g, rk, verdict, calib, imp, args):
    CARD.parent.mkdir(parents=True, exist_ok=True)
    CARD.write_text(f"""# Model card — Component A, runoff risk classifier

**Data:** `training_set_full.parquet` — {len(df):,} catchment-days, 1998–2022
**Positive:** `sro > 0.002 mm/day` — {int(df.target.sum()):,} rows ({df.target.mean():.1%})
**Features:** {len(feats)}{" (event-varying only)" if args.event_varying_only else ""}

---

## The target, and why it is a threshold

The delivered matrix was 390 rows from the top 100 rainfall days in 27 years, so
99% had runoff — "will there be runoff" was answered before the model saw it. The
full population is assembled from all 77 ERA5 months on disk: {len(df):,} rows at
{df.target.mean():.1%} positive.

The threshold is **anchored, not tuned for balance.** The one documented
sediment-delivering flood — October 2016, ≈24,400 t — peaks at 0.00373 mm, the
94.5th percentile of all catchment-days. 0.002 mm sits below it, so the sole piece
of ground truth is comfortably positive rather than marginal.

## Imbalance: two problems, two fixes

At {df.target.mean():.1%} positive, `min_child_weight` is a floor on the sum of
hessians in a leaf, and h = p(1−p):

```
{hessian_floor_note(df.target.mean(), 4.0)}
{hessian_floor_note(0.20, 4.0)}
```

A leaf needs ~55 positives before it may exist. With {int(df.target.sum())} positives
across {len(feats)} features and 5 catchments, predictive regions holding fewer get
pruned before they contribute. **That is a learning problem**, fixed by resampling
to 1:4 plus `scale_pos_weight`.

That fix distorts the loss, so the model no longer emits true probabilities —
**a numbers problem**. Platt's intercept absorbs the base rate, so a calibrator
fitted at 20% encodes a 1-in-5 prior and inflates every output.

Hence the three-way split per fold:

| Stage | Data | Prevalence |
|---|---|---|
| Classifier fit | resampled 1:4, all hard negatives + easy to fill | 20% |
| Calibrator fit | latest 25% by date, unseen by the classifier | natural |
| **Test** | held-out catchment | natural |

The calibration slice is split by **time**, not randomly: consecutive days share a
storm, soil moisture and prior rainfall, so a random cut lets the calibrator score
rows the classifier already knows.

## Results — LOCO, all five folds

{loco.to_markdown(index=False)}

**mean AP: baseline {b:.4f} · gbm {g:.4f} · delta {g - b:+.4f}**

**Verdict: {verdict}**

{"### Leakage, measured" if rk is not None else ""}

{f"Random K-fold AP {rk:.4f} against LOCO AP {g:.4f} — a gap of **{rk - g:+.4f}**. That difference is catchment memorisation with a number on it: static features are constant within a catchment, so a random split lets the model recognise which catchment a row belongs to. Reporting both is stronger than either alone." if rk is not None else ""}

## Calibration on the held-out catchment

{calib[1].to_markdown(index=False)}

Predicted against observed. A calibrated model tracks the two columns together.

## Feature importance

{imp.head(10).round(4).to_frame("mean_abs_shap").to_markdown()}

## What this model cannot do

- **It predicts modelled runoff, not a flood reaching the sea.** The label is
  ERA5-Land surface runoff — ECMWF's land-surface scheme, not an observation.
- **Sub-daily rainfall is unavailable** over the full record, so it trains on daily
  totals. This is a real loss: intensity drives runoff in a hyper-arid catchment,
  and Oct 2016 ranks 14th by daily total against 8th by peak 3-hour intensity.
- **Label quality is not uniform.** AQ-C01 gets 41 ERA5 cells, a genuine area
  mean; the other four get one cell each and three are nearest-cell point samples
  with no cell centre inside the polygon. ERA5-Land is ~81 km² per cell against
  catchments of 36–65 km².
- **Only 656 hard negatives exist** — days with measurable rain and little runoff,
  where the boundary is. They cap what can be learned, and more would need ERA5
  months that are not downloaded.
- **Five catchments is not a sample.** Any pattern across five points could be
  coincidence, and no validation scheme fixes that.
""")


if __name__ == "__main__":
    main()
