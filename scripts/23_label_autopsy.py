"""The runoff label is not a runoff label. This proves it.

Chain of reasoning, each step measured
--------------------------------------
scripts/22 showed one column of ERA5 rainfall scores AP 0.9785 against our
20-feature 0.7445. That is not "some leakage". This script asks the obvious next
question - how much of the label is rainfall and how much is hydrology - and the
answer is that there is no hydrology in it at all.

1. THE BINARY TARGET IS A RAINFALL MASK.
   `target = (sro_mm_day > 0.002)`. A one-line rule, `era5_rain > 0.5 mm`,
   reproduces it at F1 0.943 / accuracy 0.991. Nothing about infiltration,
   antecedent moisture, slope or soil survives into the binary label.

2. THE MAGNITUDE CARRIES NO LAND-SURFACE RESPONSE EITHER.
   The runoff coefficient sro/rain has p95/p5 = 1.7x - effectively constant.
   Its strongest correlate is `area_km2` (+0.65), a static property and an
   artifact of spatial averaging, not a hydrological response. Soil moisture
   manages +0.26.

3. AND THE QUANTITY IS PHYSICALLY UNUSABLE FOR THESE WADIS.
   The coefficient is 0.45%. Published storm runoff coefficients for arid
   Negev catchments are 5-20% - one to two orders of magnitude higher. The
   largest sro in the entire 2,362-day record is 0.21 mm, and the label
   threshold is 0.002 mm. We have been thresholding numerical noise.

So Component A does not model rainfall-to-runoff. It translates IMERG's
rainfall field into ERA5's rainfall field, and the 0.745 AP is the accuracy of
that translation.

Why the label cannot be repaired from data on disk
--------------------------------------------------
IMERG measures RAINFALL. ERA5 `sro` is the only runoff estimate we hold, and it
is the broken one. Any label derived from IMERG rainfall is a function of our own
feature set - circular, and it would score ~1.0 for exactly the reason M3 did.

There is no third source. A real runoff label needs measured discharge (no gauge
data exists for these wadis) or an independent observation of water reaching the
sea (13 undated literature events, plus satellite plumes - see scripts/24, 25).

What this means for the ML claim
-------------------------------
The concept doc states that only the runoff classifier is trained and everything
else is formula or physics. If the classifier's target is a rainfall mask, then
nothing in the platform is meaningfully trained.

That is fixable, but not by tuning. The defensible options are in the report.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

from models import features as FX                      # noqa: E402

TRAIN = ROOT / "data/processed/features/training_set_full.parquet"
INTENSITY = ROOT / "data/processed/features/daily_intensity.parquet"
REPORT = ROOT / "reports/model/label_autopsy.md"

# Published storm runoff coefficients for arid Negev / Sinai catchments. Used
# only as an order-of-magnitude reference, hence a range and not a point.
NEGEV_RUNOFF_COEF = (0.05, 0.20)
RAIN_RULE_THRESHOLDS = (0.1, 0.25, 0.5, 1.0, 2.0)
STATE_COLS = ["soil_moisture_lag1d", "soil_moisture_lag3d", "dry_days_before",
              "precip_prior_7d_mm", "slope_mean_deg", "area_km2", "temp_c"]


def load() -> pd.DataFrame:
    df = pd.read_parquet(TRAIN)
    inten = pd.read_parquet(INTENSITY)[["date", "catchment_id",
                                        "era5_rain_mm_day"]]
    n0 = len(df)
    df = df.merge(inten, on=["date", "catchment_id"], how="left")
    assert len(df) == n0, "merge changed row count"
    return df


def rainfall_mask_test(df) -> pd.DataFrame:
    """Can a one-line rainfall rule reproduce the label?"""
    rows = []
    for t in RAIN_RULE_THRESHOLDS:
        pred = (df.era5_rain_mm_day > t).astype(int)
        rows.append({
            "rule": f"era5_rain > {t:g} mm",
            "accuracy": accuracy_score(df[FX.TARGET], pred),
            "F1": f1_score(df[FX.TARGET], pred),
            "disagreements": int((pred != df[FX.TARGET]).sum()),
        })
    return pd.DataFrame(rows)


def coefficient_test(df):
    """Does sro/rain vary, and does it respond to catchment state?"""
    w = df[(df.era5_rain_mm_day > 1.0) & (df.sro_mm_day > 0)].copy()
    w["coef"] = w.sro_mm_day / w.era5_rain_mm_day
    q = w.coef.quantile([0.05, 0.25, 0.5, 0.75, 0.95])
    corr = {c: spearmanr(w.coef, w[c], nan_policy="omit").statistic
            for c in STATE_COLS if c in w}
    return w, q, corr


def agreement_table(df, thr=0.5) -> pd.DataFrame:
    """Cross-tabulate the two rainfall products against the label."""
    iw, ew = df.precipitation_mm_day > thr, df.era5_rain_mm_day > thr
    cat = pd.Series(np.select([iw & ew, iw & ~ew, ~iw & ew],
                              ["both wet", "IMERG only", "ERA5 only"],
                              "both dry"), index=df.index)
    g = df.groupby(cat).agg(rows=(FX.TARGET, "size"),
                            positives=(FX.TARGET, "sum"),
                            positive_rate=(FX.TARGET, "mean"))
    g["positive_rate"] = g.positive_rate.round(3)
    return g.reset_index(names="agreement")


def main():
    df = load()
    print(f"{len(df):,} catchment-days · {int(df[FX.TARGET].sum())} positive "
          f"({df[FX.TARGET].mean():.1%})\n")

    print("=== 1. is the binary target just ERA5 rainfall, thresholded? ===")
    mask = rainfall_mask_test(df)
    print(mask.round(4).to_string(index=False))
    best = mask.loc[mask.F1.idxmax()]
    print(f"\n  best one-line rule: {best.rule}  ->  F1 {best.F1:.4f}, "
          f"accuracy {best.accuracy:.4f}")
    print("  There is no hydrology in the binary label. It is a rainfall mask.\n")

    print("=== 2. does the magnitude carry a land-surface response? ===")
    w, q, corr = coefficient_test(df)
    print(f"  runoff coefficient sro/rain on {len(w):,} wet rows:")
    print("   ", "  ".join(f"p{int(k*100)}={v:.4f}" for k, v in q.items()))
    spread = q[0.95] / q[0.05]
    print(f"    p95/p5 spread {spread:.1f}x  -> "
          f"{'varies' if spread > 3 else 'effectively CONSTANT'}")
    print("  response to catchment state:")
    for c, r in sorted(corr.items(), key=lambda kv: -abs(kv[1])):
        print(f"    spearman(coef, {c:22}) {r:+.3f}")
    print("  The strongest correlate is a STATIC property, which is a spatial-")
    print("  averaging artifact rather than a hydrological response.\n")

    print("=== 3. is the quantity physically plausible for these wadis? ===")
    med = float(q[0.5])
    lo, hi = NEGEV_RUNOFF_COEF
    print(f"  ERA5-Land coefficient here      {100*med:.2f}%")
    print(f"  published arid Negev storms     {100*lo:.0f}-{100*hi:.0f}%")
    print(f"  -> low by {lo/med:.0f}-{hi/med:.0f}x")
    print(f"  largest sro in the whole record  {df.sro_mm_day.max():.4f} mm")
    print(f"  label threshold                  0.002 mm")
    print("  We have been thresholding numerical noise.\n")

    print("=== 4. why it cannot be repaired from data on disk ===")
    agr = agreement_table(df)
    print(agr.to_string(index=False))
    print("\n  'ERA5 only' is 98.9% positive and 'IMERG only' is 3.2%. The label")
    print("  tracks ERA5's rainfall and ignores IMERG's entirely. And IMERG")
    print("  measures RAINFALL - so any IMERG-derived label is a function of our")
    print("  own features. Circular. There is no third source on disk.")

    write_report(df, mask, best, q, spread, corr, med, agr, w)
    print(f"\nwrote {REPORT.relative_to(ROOT)}")


def write_report(df, mask, best, q, spread, corr, med, agr, w):
    lo, hi = NEGEV_RUNOFF_COEF
    corr_tbl = "\n".join(
        f"| `{c}` | {r:+.3f} |"
        for c, r in sorted(corr.items(), key=lambda kv: -abs(kv[1])))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# Autopsy: the runoff label is a rainfall mask

**Date:** 4 August 2026 · `scripts/23_label_autopsy.py` · follows
`reports/model/label_leakage.md`

`scripts/22` found that one column of ERA5 rainfall scores AP **0.9785** against
our 20-feature **0.7445**. This is the follow-up question — how much of the label
is rainfall and how much is hydrology — and the answer is **none of it is
hydrology.**

## 1 · A one-line rule reproduces the label

`target = (sro_mm_day > 0.002)`.

{mask.round(4).to_markdown(index=False)}

**`{best.rule}` reproduces the label at F1 {best.F1:.4f}, accuracy
{best.accuracy:.4f}** — disagreeing on {int(best.disagreements)} of {len(df):,}
rows. Nothing about infiltration, antecedent moisture, slope or soil survives
into the binary target.

## 2 · The magnitude carries no land-surface response either

If the binary label is a rainfall mask, the magnitude might still hold physics.
It does not. The runoff coefficient `sro / rain` on {len(w):,} wet rows:

| p5 | p25 | p50 | p75 | p95 | spread |
|---:|---:|---:|---:|---:|---:|
| {q[0.05]:.4f} | {q[0.25]:.4f} | {q[0.5]:.4f} | {q[0.75]:.4f} | {q[0.95]:.4f} | **{spread:.1f}×** |

Effectively constant. And its response to catchment state:

| feature | spearman with runoff coefficient |
|---|---:|
{corr_tbl}

The strongest correlate is **`area_km2`** — a static property, and an artifact of
averaging ERA5's ~81 km² cells over 36–65 km² catchments rather than a
hydrological response. Soil moisture, which should dominate an arid
infiltration-controlled system, manages +0.26.

## 3 · The quantity is physically unusable for these wadis

| | value |
|---|---:|
| ERA5-Land runoff coefficient here | **{100*med:.2f}%** |
| Published arid Negev storm coefficients | {100*lo:.0f}–{100*hi:.0f}% |
| Ratio | **low by {lo/med:.0f}–{hi/med:.0f}×** |
| Largest `sro` in the entire 2,362-day record | {df.sro_mm_day.max():.4f} mm |
| Label threshold | 0.002 mm |

A record maximum of {df.sro_mm_day.max():.2f} mm of surface runoff, for a
4,453 km² catchment that discharged 24,400 t of sediment in 2016. **We have been
thresholding numerical noise.**

ERA5-Land is a global reanalysis whose land-surface scheme is not built for
hyper-arid flash-flood catchments; this is a known limitation of the product, not
a bug in our extraction. It belongs in `docs/data_dictionary.md` as a stated
limitation of the source.

## 4 · Why the label cannot be repaired from data on disk

{agr.to_markdown(index=False)}

**`ERA5 only` is 98.9% positive; `IMERG only` is 3.2%.** The label tracks ERA5's
rainfall and ignores IMERG's observation of the same day almost entirely.

And there is no substitute available. **IMERG measures rainfall, not runoff.** Any
label derived from IMERG rainfall is a function of our own feature set — circular,
and it would score ≈1.0 for exactly the reason the one-column ERA5 model did. We
hold no discharge gauge data for these wadis, and none is known to exist.

## What this does to the ML claim

`CLAUDE.md` states that only the runoff classifier is trained and everything else
is formula or physics. If the classifier's target is a rainfall mask, then
**nothing in the platform is meaningfully trained.** Saying otherwise to a judge
who asks what the label is would be worse than not claiming it.

Three honest routes, none of which is tuning:

**A · Component A becomes physics, like the rest.** Replace the ERA5 target with
an SCS curve-number runoff computed on IMERG rainfall — literature-grounded `CN`
from land cover and soil, `λ = 0.05` for arid initial abstraction. `RuleBaseline`
already implements this. The platform then honestly describes itself as physics +
retrieval, with no trained component. Available immediately, no new data.

**B · Move the ML to where the labels actually are.** The genuinely well-posed
supervised problem in this project is **forecast correction**: predict observed
IMERG catchment rainfall from GFS/GEFS forecast fields. Labels are abundant
(~8,000 days), independent of the features, and the task is real — raw 0.25°
forecast cells are far coarser than a 36–65 km² catchment. `backend/src/ingestion/`
has `gfs.py`, `gefs.py` and `ecmwf.py`, but **no forecast data is on disk**, so
this needs a download. It is Nizar's workstream.

**C · Validate against water actually reaching the sea.** 13 undated literature
events (`scripts/24`) plus ~13 recoverable satellite plumes (`scripts/25`). Too
few to train on; enough to validate a ranker, decisively — see
`reports/model/label_problem.md` for the power calculation.

**A and C are available now. B is the only route that restores a trained model,
and it needs a download that has not started.**
""")


if __name__ == "__main__":
    main()
