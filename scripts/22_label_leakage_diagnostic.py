"""How much of Component A's skill is ERA5 predicting itself?

The problem, stated precisely
-----------------------------
The label is ERA5-Land `sro`. It correlates +0.985 with ERA5-Land's own
precipitation, because ERA5's land-surface scheme computes it from that
precipitation. So a model that reconstructs ERA5's rainfall has, for free,
reconstructed the label.

Our features straddle two atmospheres:

    IMERG-sourced   precipitation_mm_day, precip_prior_{1,3,7}d_mm,
                    rain_over_p{50,90,99}, rain_self_percentile, dry_days_before
    ERA5-sourced    soil_moisture_lag{1,3}d, wind_speed_ms,
                    wind_direction_deg, temp_c
    neutral         season_sin/cos, area_km2, slope_mean_deg,
                    drainage_density_km_km2, elongation_ratio

The two rainfall products agree at only r = +0.573. That makes the split a real
experiment rather than a semantic one: IMERG features are an *independent*
observation of the storm, ERA5 features are the label's own weather.

Four models, all LOCO, all identical apart from which columns they see
------------------------------------------------------------------------
    M1  IMERG + neutral        the honest model: independent rainfall -> runoff
    M2  CD- (shipped, 20)      M1 plus the five ERA5 state variables
    M3  ERA5 same-day rain     ONE feature, the label's own forcing = the ceiling
    M4  ERA5 + neutral         no IMERG at all: ERA5 predicting ERA5

Reading it:

    M3 >> M2      the label is essentially ERA5 rain, and 20 engineered
                  features are a lossy proxy for one column we already have.
    M2 >> M1      the ERA5 state variables are carrying label information,
                  not physics. That gain is leakage, not skill.
    M1 ~ M2       the skill is real rainfall->runoff transfer and survives
                  losing every ERA5 input.

Then a tracking test on M2's held-out predictions: do they follow ERA5's
rainfall or IMERG's? The sharp form is incremental R2 - does the model's output
explain ERA5 rainfall BEYOND what its own IMERG input already explains? If it
does, it has learned to correct IMERG toward ERA5, which is a product offset
and not hydrology.

No new data. era5_rain_mm_day comes from scripts/21, already on disk.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

from models import features as FX                     # noqa: E402
from models.imbalance import build_fold               # noqa: E402
from models.predictors import WeightedGBM             # noqa: E402

TRAIN = ROOT / "data/processed/features/training_set_full.parquet"
INTENSITY = ROOT / "data/processed/features/daily_intensity.parquet"
REPORT = ROOT / "reports/model/label_leakage.md"

IMERG = ["precipitation_mm_day", "precip_prior_1d_mm", "precip_prior_3d_mm",
         "precip_prior_7d_mm", "rain_over_p50", "rain_over_p90",
         "rain_over_p99", "rain_self_percentile", "dry_days_before"]
ERA5_STATE = ["soil_moisture_lag1d", "soil_moisture_lag3d", "wind_speed_ms",
              "wind_direction_deg", "temp_c"]
NEUTRAL = ["season_sin", "season_cos", "area_km2", "slope_mean_deg",
           "drainage_density_km_km2", "elongation_ratio"]
ERA5_RAIN = ["era5_rain_mm_day"]


def detection_table(df: pd.DataFrame) -> pd.DataFrame:
    """Does ERA5 mis-SCALE storms, or fail to SEE them? Different diagnoses.

    A ratio conditioned on both products being wet is worthless here: it selects
    the rows where they already agree and duly reports ~1.0. The question is what
    ERA5 does on the days IMERG calls wet.
    """
    out = []
    for thr in (1.0, 5.0, 10.0):
        w = df[df.precipitation_mm_day > thr]
        if not len(w):
            continue
        both = w[w.era5_rain_mm_day > thr]
        out.append({
            "IMERG >": f"{thr:g} mm",
            "n": len(w),
            "ERA5 dry (<0.1mm)": f"{100*(w.era5_rain_mm_day < 0.1).mean():.1f}%",
            f"ERA5 also > thr": f"{100*len(both)/len(w):.1f}%",
            "ratio where both wet": (
                f"{(both.era5_rain_mm_day/both.precipitation_mm_day).median():.2f}"
                if len(both) else "—"),
        })
    return pd.DataFrame(out)


def loco(df, feats, label):
    """Leave-one-catchment-out. Returns per-fold APs and pooled held-out preds."""
    aps, idx, preds = {}, [], []
    for c in sorted(df[FX.GROUP].unique()):
        tr, te = df[df[FX.GROUP] != c], df[df[FX.GROUP] == c]
        f = build_fold(tr, te, feats)
        m = WeightedGBM(scale_pos_weight=f.scale_pos_weight, **FX.PARAMS)
        m.fit(f.fit_X, f.fit_y).calibrate(f.cal_X, f.cal_y)
        p = m.predict_proba(f.test_X)
        aps[c] = average_precision_score(f.test_y, p)
        idx.append(te.index.to_numpy())
        preds.append(p)
    order = np.concatenate(idx)
    out = pd.Series(np.concatenate(preds), index=order).reindex(df.index)
    mean_ap = float(np.mean(list(aps.values())))
    print(f"  {label:28} mean AP {mean_ap:.4f}   "
          + "  ".join(f"{k.split('-')[-1]} {v:.3f}" for k, v in aps.items()))
    return mean_ap, aps, out


def main():
    df = pd.read_parquet(TRAIN).reset_index(drop=True)
    inten = pd.read_parquet(INTENSITY)[["date", "catchment_id", "era5_rain_mm_day"]]
    n0 = len(df)
    df = df.merge(inten, on=["date", "catchment_id"], how="left")
    assert len(df) == n0, "merge changed row count"
    miss = df.era5_rain_mm_day.isna().sum()
    print(f"{len(df):,} rows · {int(df[FX.TARGET].sum())} positive "
          f"({df[FX.TARGET].mean():.1%})")
    print(f"era5_rain_mm_day missing on {miss} rows "
          f"({100*miss/len(df):.2f}%) — left as NaN, never filled\n")

    # ── the correlation that motivates all of this ───────────────────────
    w = df[(df.precipitation_mm_day > 0) & df.era5_rain_mm_day.notna()]
    print("=== the two atmospheres ===")
    for a, b, lbl in [("sro_mm_day", "era5_rain_mm_day", "sro    vs ERA5 rain"),
                      ("sro_mm_day", "precipitation_mm_day", "sro    vs IMERG rain"),
                      ("era5_rain_mm_day", "precipitation_mm_day", "ERA5   vs IMERG rain")]:
        r = df[[a, b]].dropna().corr().iloc[0, 1]
        rs = spearmanr(*df[[a, b]].dropna().values.T).statistic
        print(f"  {lbl:22} pearson {r:+.3f}   spearman {rs:+.3f}")
    ratio = (w.era5_rain_mm_day / w.precipitation_mm_day).median()
    print(f"  ERA5/IMERG on wet days: median ratio {ratio:.3f}  (n={len(w):,})\n")

    det = detection_table(df)
    print("=== it is a DETECTION failure, not a scaling one ===")
    print(det.to_string(index=False))
    print("\n  When ERA5 sees the storm it gets the magnitude about right")
    print("  (median ratio ~1.0). The failure is that it does not see most")
    print("  storms at all — and a conditional 'ratio on days both are wet' hides")
    print("  exactly that, because it selects the subset where they agree.\n")

    miss_rows = df[(df.precipitation_mm_day > 1.0) & (df.era5_rain_mm_day < 0.1)]
    wet_rows = df[df.precipitation_mm_day > 1.0]
    print("=== and the label follows ERA5's blind spot ===")
    print(f"  IMERG-wet (>1 mm) catchment-days:        {len(wet_rows):>5,}  "
          f"target=1 on {int(wet_rows[FX.TARGET].sum()):>4} ({wet_rows[FX.TARGET].mean():.1%})")
    print(f"  ...of those, ERA5 dry (<0.1 mm):         {len(miss_rows):>5,}  "
          f"target=1 on {int(miss_rows[FX.TARGET].sum()):>4} "
          f"({miss_rows[FX.TARGET].mean():.1%})")
    print("  Whenever ERA5 misses a storm the label says 'no runoff', whatever")
    print("  IMERG observed. October 2016 is one of these rows.\n")

    # ── four models ──────────────────────────────────────────────────────
    print("=== LOCO, identical except for which columns each model sees ===")
    res = {}
    res["M1"] = loco(df, IMERG + NEUTRAL, "M1 IMERG + neutral (15)")
    res["M2"] = loco(df, IMERG + ERA5_STATE + NEUTRAL, "M2 CD- shipped (20)")
    sub = df[df.era5_rain_mm_day.notna()].reset_index(drop=True)
    res["M3"] = loco(sub, ERA5_RAIN, "M3 ERA5 rain ONLY (1)")
    res["M4"] = loco(sub, ERA5_RAIN + ERA5_STATE + NEUTRAL, "M4 ERA5 + neutral (12)")

    m1, m2, m3, m4 = (res[k][0] for k in ("M1", "M2", "M3", "M4"))
    print(f"\n  M2 - M1 = {m2-m1:+.4f}   gain from adding 5 ERA5 state variables")
    print(f"  M3 - M2 = {m3-m2:+.4f}   one ERA5 column vs 20 engineered features")
    print(f"  M4 - M1 = {m4-m1:+.4f}   ERA5-only vs IMERG-only")

    # ── tracking test on M2's held-out predictions ───────────────────────
    print("\n=== does the shipped model track ERA5 or IMERG rainfall? ===")
    d = df.assign(p=res["M2"][2]).dropna(
        subset=["p", "era5_rain_mm_day", "precipitation_mm_day"])
    for col, lbl in [("era5_rain_mm_day", "ERA5 rain"),
                     ("precipitation_mm_day", "IMERG rain (its own input)")]:
        rs = spearmanr(d.p, d[col]).statistic
        print(f"  spearman(prediction, {lbl:26}) {rs:+.3f}")

    # Incremental R2: does the prediction explain ERA5 rain beyond IMERG rain?
    y = np.log1p(d.era5_rain_mm_day.to_numpy())
    Xi = np.log1p(d[["precipitation_mm_day"]].to_numpy())
    Xp = np.column_stack([Xi, d.p.to_numpy()])
    r2_i = LinearRegression().fit(Xi, y).score(Xi, y)
    r2_ip = LinearRegression().fit(Xp, y).score(Xp, y)
    print(f"\n  predicting ERA5 rainfall (log1p):")
    print(f"    from IMERG rain alone          R2 {r2_i:.4f}")
    print(f"    from IMERG rain + prediction   R2 {r2_ip:.4f}")
    print(f"    incremental R2 from prediction    {r2_ip-r2_i:+.4f}")
    print("  The prediction sees only IMERG-side inputs in M1, and IMERG plus")
    print("  ERA5 state in M2. Any incremental power over IMERG is the model")
    print("  reconstructing ERA5's atmosphere.")

    write_report(df, res, ratio, len(w), r2_i, r2_ip, d, miss, det,
                 wet_rows, miss_rows)
    print(f"\nwrote {REPORT.relative_to(ROOT)}")


def write_report(df, res, ratio, nwet, r2_i, r2_ip, d, miss, det,
                 wet_rows, miss_rows):
    m1, m2, m3, m4 = (res[k][0] for k in ("M1", "M2", "M3", "M4"))
    rows = []
    for k, lbl, n in [("M1", "IMERG + neutral", 15), ("M2", "CD- shipped", 20),
                      ("M3", "ERA5 same-day rain only", 1),
                      ("M4", "ERA5 + neutral, no IMERG", 12)]:
        rows.append(f"| **{k}** | {lbl} | {n} | {res[k][0]:.4f} |")
    tbl = "\n".join(rows)
    sp_e = spearmanr(d.p, d.era5_rain_mm_day).statistic
    sp_i = spearmanr(d.p, d.precipitation_mm_day).statistic

    verdict = (
        "**The skill is largely real.** M1 keeps most of M2's performance without "
        "seeing any ERA5 input, so the model is transferring independent IMERG "
        "rainfall to runoff rather than reconstructing the label's own forcing."
        if m2 - m1 < 0.05 else
        "**A material share of the skill is the label's own atmosphere.** Adding "
        f"five ERA5 state variables lifts AP by {m2-m1:+.4f}, which is gain from "
        "features drawn from the same product as the label — not from hydrology.")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# How much of Component A is ERA5 predicting itself?

**Date:** 4 August 2026 · `scripts/22_label_leakage_diagnostic.py` ·
companion to `reports/model/label_problem.md`

The label is ERA5-Land `sro`, and it correlates **+0.985** with ERA5-Land's own
precipitation — because ERA5's land-surface scheme computes it from that
precipitation. Any model that reconstructs ERA5's rainfall has reconstructed the
label for free.

Our features straddle two atmospheres, and the two rainfall products agree at
only **r = +0.573**, so the split is a real experiment rather than a semantic one.

| group | columns | source |
|---|---|---|
| IMERG | `precipitation_mm_day`, `precip_prior_{{1,3,7}}d_mm`, `rain_over_p{{50,90,99}}`, `rain_self_percentile`, `dry_days_before` | GPM IMERG — **independent** of the label |
| ERA5 state | `soil_moisture_lag{{1,3}}d`, `wind_speed_ms`, `wind_direction_deg`, `temp_c` | ERA5-Land `swvl1`, `u10`, `v10`, `t2m` — **the label's own weather** |
| neutral | `season_sin/cos`, `area_km2`, `slope_mean_deg`, `drainage_density_km_km2`, `elongation_ratio` | calendar and terrain |

## ERA5 does not mis-scale storms — it fails to see them

This distinction decides what the fix is, and a ratio conditioned on *both*
products being wet hides it completely: that ratio selects the rows where they
already agree and duly reports ≈1.0.

{det.to_markdown(index=False)}

When ERA5 sees a storm it gets the magnitude about right. It simply does not see
most of them — including **{det.iloc[-1]["ERA5 dry (<0.1mm)"]} of the heaviest
IMERG days in the record.**

### And the label inherits the blind spot

| | catchment-days | `target = 1` |
|---|---:|---:|
| IMERG-wet (> 1 mm) | {len(wet_rows):,} | {int(wet_rows[FX.TARGET].sum())} ({wet_rows[FX.TARGET].mean():.1%}) |
| ...of those, **ERA5 dry (< 0.1 mm)** | {len(miss_rows):,} | **{int(miss_rows[FX.TARGET].sum())} ({miss_rows[FX.TARGET].mean():.1%})** |

**{len(miss_rows):,} catchment-days on which IMERG observed real rain are labelled
non-events, because ERA5 did not see the storm.** October 2016 is one of those
rows. This is not a threshold to be tuned — the label is blind wherever its source
product is.

## Four models, LOCO, identical apart from the columns they see

| | features | n | mean AP |
|---|---|---:|---:|
{tbl}

- **M2 − M1 = {m2-m1:+.4f}** — what the five ERA5 state variables add.
- **M3 − M2 = {m3-m2:+.4f}** — one column of the label's own forcing, against 20
  engineered features.
- **M4 − M1 = {m4-m1:+.4f}** — ERA5 predicting ERA5, against independent IMERG
  predicting ERA5.

{verdict}

## Tracking test

Held-out M2 predictions, against each rainfall product:

| | spearman |
|---|---:|
| prediction vs **ERA5** rainfall | {sp_e:+.3f} |
| prediction vs **IMERG** rainfall (its own input) | {sp_i:+.3f} |

The sharper form — does the prediction explain ERA5 rainfall *beyond* what its
own IMERG input already explains?

| predicting ERA5 rainfall (log1p) | R² |
|---|---:|
| from IMERG rainfall alone | {r2_i:.4f} |
| from IMERG rainfall + model prediction | {r2_ip:.4f} |
| **incremental R² from the prediction** | **{r2_ip-r2_i:+.4f}** |

Incremental power here means the model learned to correct IMERG toward ERA5 —
a product offset, not hydrology.

## Caveats

- `era5_rain_mm_day` is missing on {miss} rows and is **left NaN, never filled**;
  M3 and M4 run on the subset where it exists, so their APs are not on identical
  rows to M1/M2.
- All four use the same folds, resampling seed and hyperparameters, so the
  differences are attributable to the feature groups.
- Run-to-run AP variance is **±0.017**. Differences smaller than that are noise,
  and per `reports/model/label_problem.md` the 13-event validation set cannot
  resolve them either.
""")


if __name__ == "__main__":
    main()
