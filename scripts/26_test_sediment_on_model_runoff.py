"""Test the sediment formula against three different runoff inputs.

Why a third source, not just two
---------------------------------
`scripts/20` fed the sediment formula ERA5's OBSERVED `sro` and October 2016
ranked 193 of 2,362. `scripts/22-23` explained why: ERA5 largely missed that
storm (0.77 mm at p92.6, against IMERG's 9.58 mm at p99.5), so the formula was
scored against a runoff series that never saw the anchor event.

The first version of this script fed the formula `MagnitudeGBM`'s LOCO-predicted
runoff instead, on the theory that the runoff MODEL - unlike ERA5 - "saw" the
storm: its calibrated classification probability crosses the operating
threshold on 2016-10-27 (AQ-C01, AQ-C03 both fire). That test still ranked the
anchor day 176th of 2,362 - barely better than ERA5's 193rd - which looked like
a second falsification of the formula itself.

It was not, and the reason is worth stating plainly: the classifier's
PROBABILITY and `MagnitudeGBM`'s predicted MAGNITUDE are two different
transforms of the same margin score, and only the probability escaped ERA5's
blind spot. The magnitude is fit by direct regression against ERA5's own
`sro_mm_day` (`MagnitudeGBM.fit`, `models/predictors.py`), so out-of-sample it
reproduces something close to ERA5's own tiny value for that date - 0.0067 mm
predicted vs 0.0032-0.0037 mm observed - not the storm intensity IMERG saw
(9.58 mm of rain, mapping to a runoff depth roughly three orders of magnitude
larger). The classifier's "it fired" told us the model recognised the day as
anomalous relative to its own scale; it told us nothing about the absolute mm
value the sediment formula actually multiplies through. Feeding the formula
that magnitude was therefore never free of the label problem it was built to
control for - it inherited the same underestimate through a different model.

This version adds a magnitude source that genuinely is free of it: the
CURVE-NUMBER runoff depth in `RuleBaseline.runoff_depth()`
(`models/predictors.py`), driven directly by `precipitation_mm_day` - confirmed
IMERG-sourced (`processing/catchment_rainfall.py`, never ERA5's `tp`, which
lives separately as `era5_rain_mm_day`) - plus slope, soil moisture and bare
fraction. It is a fixed formula, not fit to `sro` or to any label, so there is
no LOCO fold to run: nothing is trained, so nothing can leak. This is the
first magnitude estimate in this whole line of testing that sees the storm at
the INPUT rather than being asked to reproduce ERA5's verdict on it.

    scripts/20  Q = sro_mm_day              observed ERA5        -> rank 193
    scripts/26  Q = MagnitudeGBM(X)         predicted, fit to sro -> rank 176
    scripts/26  Q = RuleBaseline.runoff_depth(X)   IMERG rain, unfit -> rank ?

Held out, not fitted (the one exception noted above)
-----------------------------------------------------
`MagnitudeGBM`'s Q is a leave-one-catchment-out prediction, so no catchment's
sediment index is computed by a model that trained on that catchment.
`RuleBaseline.runoff_depth()` needs no such split - it has no `fit()` step in
its runoff-depth path, only fixed constants (CN_BASE, IA_RATIO, ...), so
"held out" does not apply and is not claimed for it.

What a pass and a failure each mean
-----------------------------------
PASS  the formula ranks the one documented major sediment event near the top
      of 27 years, driven by a runoff estimate available at forecast time.
      That is not proof the physics is right; it is the absence of the most
      obvious way it could be wrong.

FAIL  with the label problem now understood and controlled for, a failure
      points at the formula itself rather than at its input.

The n=1 caveat does not go away for any source. `k` is anchored on this same
event, so the ranking test is the only part that is independent: the anchor
sets the SCALE, the rank tests the SHAPE. See reports/model/label_problem.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

from models import features as FX                             # noqa: E402
from models.imbalance import build_fold                       # noqa: E402
from models.predictors import MagnitudeGBM, RuleBaseline       # noqa: E402
from models.sediment_proxy import (ANCHOR_CATCHMENT, ANCHOR_EVENT,  # noqa: E402
                                   ANCHOR_MASS_T, CLASSES, TAU_NEGEV,
                                   SedimentParams, SedimentProxy)

TRAIN = ROOT / "data/processed/features/training_set_full.parquet"
OUT = ROOT / "data/processed/features/sediment_model_driven.parquet"
REPORT = ROOT / "reports/model/sediment_test_on_model_runoff.md"

# Same 3-day window as scripts/20: the mooring records turbidity elevated for
# 31.4 h from 06:50 UTC on the 28th, so the published mass spans the 27th-29th.
ANCHOR_WINDOW = ("2016-10-27", "2016-10-29")
MAGNITUDE_COL = "sro_mm_day"


def predict_runoff_loco(df: pd.DataFrame, feats: list[str]) -> pd.Series:
    """LOCO-predicted runoff magnitude in mm. Never in-sample."""
    idx, vals = [], []
    for c in sorted(df[FX.GROUP].unique()):
        tr, te = df[df[FX.GROUP] != c], df[df[FX.GROUP] == c]
        f = build_fold(tr, te, feats)
        # The regressor learns magnitude, so it is fitted on the resampled fit
        # slice's actual sro - not on the binary target.
        y_fit = df.loc[f.fit_X.index, MAGNITUDE_COL].to_numpy(dtype=float)
        m = MagnitudeGBM().fit(f.fit_X, y_fit)
        # margin() is log(sro + EPS); invert to get mm back.
        q = np.exp(m.margin(f.test_X)) - MagnitudeGBM.EPS
        idx.append(te.index.to_numpy())
        vals.append(np.clip(q, 0.0, None))
    return pd.Series(np.concatenate(vals), index=np.concatenate(idx)).reindex(df.index)


def rank_days(df: pd.DataFrame, col: str, k: float):
    """Storm-level ranking: a published sediment mass is a per-event total."""
    daily = df.groupby("date", as_index=False)[col].sum()
    daily["mass_t"] = daily[col] * k
    daily = daily.sort_values(col, ascending=False).reset_index(drop=True)
    daily["rank"] = daily.index + 1
    return daily


def verdict_for(rank: int, n: int) -> str:
    return ("PASS" if rank <= max(5, n * 0.01) else
            "MARGINAL" if rank <= n * 0.05 else "FAIL")


def main():
    df = pd.read_parquet(TRAIN).reset_index(drop=True)
    feats = FX.check(df)
    print(f"{len(df):,} catchment-days · {df.date.nunique():,} days · "
          f"{len(feats)} features\n")

    print("predicting runoff magnitude, leave-one-catchment-out ...")
    df["q_model_mm"] = predict_runoff_loco(df, feats)
    obs, pred = df[MAGNITUDE_COL], df.q_model_mm
    print(f"  observed  sro  median {obs.median():.6f}  max {obs.max():.4f} mm")
    print(f"  predicted Q    median {pred.median():.6f}  max {pred.max():.4f} mm")
    print(f"  spearman(pred, obs) {pred.corr(obs, method='spearman'):+.3f}\n")

    print("computing rule-based CN runoff depth (no fit, no LOCO - a fixed "
          "formula on IMERG rainfall) ...")
    df["q_rule_mm"] = RuleBaseline().runoff_depth(df)
    print(f"  rule-based Q   median {df.q_rule_mm.median():.6f}  "
          f"max {df.q_rule_mm.max():.4f} mm\n")

    sp_obs, sp_mod, sp_rule = SedimentProxy(), SedimentProxy(), SedimentProxy()
    df["sed_observed"] = sp_obs.index(df, obs.to_numpy())
    df["sed_model"] = sp_mod.index(df, pred.to_numpy())
    df["sed_rule"] = sp_rule.index(df, df.q_rule_mm.to_numpy())

    lo, hi = ANCHOR_WINDOW
    win = df[(df.date >= lo) & (df.date <= hi) &
             (df.catchment_id == ANCHOR_CATCHMENT)]
    if win.empty:
        raise SystemExit(f"{ANCHOR_CATCHMENT} absent from {lo}..{hi}")

    print(f"anchor {ANCHOR_EVENT} / {ANCHOR_CATCHMENT}, {lo}..{hi}")
    print(win[["date", MAGNITUDE_COL, "q_model_mm", "q_rule_mm", "sed_observed",
               "sed_model", "sed_rule"]].to_string(index=False))

    sources = (
        ("ERA5 observed sro", "sed_observed", sp_obs),
        ("runoff MODEL, fit to sro (LOCO)", "sed_model", sp_mod),
        ("rule-based CN runoff (IMERG rain, unfit)", "sed_rule", sp_rule),
    )

    results = {}
    for label, col, proxy in sources:
        a = float(win[col].sum())
        if a <= 0:
            print(f"\n{label}: anchor index is {a:.4g} — cannot calibrate")
            continue
        proxy.calibrate_to_anchor(a)
        daily = rank_days(df, col, proxy._k)
        n = len(daily)
        best = daily[(daily.date >= lo) & (daily.date <= hi)].sort_values("rank").iloc[0]
        r = int(best["rank"])
        results[label] = {
            "anchor_index": a, "k": proxy._k, "rank": r, "n": n,
            "pct": 100 * (1 - r / n), "verdict": verdict_for(r, n),
            "daily": daily, "top_mass": float(daily.mass_t.iloc[0]),
        }

    print(f"\n{'='*66}\nFALSIFICATION TEST — where does the one documented event rank?\n{'='*66}")
    print(f"{'runoff source':<42}{'rank':>8}{'of':>8}{'percentile':>13}{'verdict':>10}")
    for label, r in results.items():
        print(f"{label:<42}{r['rank']:>8,}{r['n']:>8,}{r['pct']:>12.2f}%{r['verdict']:>10}")

    # Show the top 10 for whichever source ranked the anchor best - the one
    # that actually earns a closer look.
    winner = min(results, key=lambda k: results[k]["rank"])
    w = results[winner]
    print(f"\ntop 10 days by sediment index, {winner}:")
    print(f"{'rank':>5} {'date':<12} {'index':>12} {'mass_t':>12}")
    for _, row in w["daily"].head(10).iterrows():
        mark = "  <- Oct 2016" if lo <= str(row.date.date()) <= hi else ""
        print(f"{int(row['rank']):>5} {row.date.date()!s:<12} "
              f"{row[w['daily'].columns[1]]:>12.4g} {row.mass_t:>12,.0f}{mark}")
    print(f"\nlargest implied mass {w['top_mass']:,.0f} t against the "
          f"documented {ANCHOR_MASS_T:,.0f} t ({w['top_mass']/ANCHOR_MASS_T:.0f}x)")

    print(f"\ntransmission-loss band on the anchor window, {winner} "
          f"(Negev {TAU_NEGEV[0]:.0%}-{TAU_NEGEV[1]:.0%}):")
    q_col = {"ERA5 observed sro": MAGNITUDE_COL,
             "runoff MODEL, fit to sro (LOCO)": "q_model_mm",
             "rule-based CN runoff (IMERG rain, unfit)": "q_rule_mm"}[winner]
    for t in (0.20, 0.525, 0.85):
        alt = SedimentProxy(SedimentParams(transmission_loss=t))
        alt._k = w["k"]
        mass = float(alt.index(win, win[q_col].to_numpy()).sum() * alt._k)
        star = "  <- default" if abs(t - 0.525) < 1e-9 else ""
        print(f"  tau {t:.3f}  ->  {mass:>12,.0f} t{star}")

    df[["date", "catchment_id", MAGNITUDE_COL, "q_model_mm", "q_rule_mm",
        "sed_observed", "sed_model", "sed_rule"]].to_parquet(OUT, index=False)
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    write_report(df, win, results, winner)
    print(f"wrote {REPORT.relative_to(ROOT)}")


def write_report(df, win, results, winner):
    rows = "\n".join(
        f"| {lbl} | {r['rank']:,} | {r['n']:,} | {r['pct']:.2f}% | **{r['verdict']}** |"
        for lbl, r in results.items())

    w = results[winner]
    daily_col = w["daily"].columns[1]
    t = w["daily"].head(10)[["rank", "date", daily_col, "mass_t"]].copy()
    t["date"] = t.date.dt.date
    t[daily_col] = t[daily_col].round(4)
    t["mass_t"] = t.mass_t.round(0)
    top = t.to_markdown(index=False)

    passed = [lbl for lbl, r in results.items() if r["verdict"] == "PASS"]
    if passed:
        interp = (
            f"**`{passed[0]}` passes**: it puts the one documented major sediment "
            "event at the top of a 27-year record, driven by a runoff estimate "
            "that (a) is available at forecast time and (b) is never fit to "
            "ERA5's `sro` — so it cannot inherit ERA5's underestimate of this "
            "storm the way the other two sources do. **That is not proof the "
            "physics is right** — it is the absence of the most obvious way it "
            "could have been wrong, and it is the first source in this line of "
            "testing to clear that bar.\n\n"
            "The other two both fail, and for a related reason: ERA5's observed "
            "`sro` under-recorded the storm outright (0.77 mm at p92.6 against "
            "IMERG's 9.58 mm at p99.5), and `MagnitudeGBM`'s predicted `sro` is "
            "fit by regression to reproduce that same column — so out-of-sample "
            "it reproduces something close to ERA5's own tiny value for this "
            "date, not the storm intensity IMERG actually saw. The runoff "
            "*classifier*'s calibrated probability does cross its operating "
            "threshold on this date (it correctly flags the day as anomalous "
            "relative to its own scale) — but that probability is a different "
            "model output from the magnitude the sediment formula consumes, and "
            "a high probability does not imply the largest absolute mm value. "
            "Conflating the two was the mistake in the first version of this "
            "test.")
    else:
        interp = (
            "All three runoff sources fail. The label problem is understood and "
            "controlled for in two of them (rule-based CN runoff never touches "
            "ERA5's `sro` at all), so a joint failure now points at the formula "
            "itself, not at its input.")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# Testing the sediment formula against three runoff inputs

**Date:** 5 August 2026 · `scripts/26_test_sediment_on_model_runoff.py`

## Why a third source

`scripts/20` fed the sediment formula ERA5's **observed** `sro` and October 2016
ranked 193 of 2,362 — ERA5 largely missed that storm (0.77 mm at p92.6, against
IMERG's 9.58 mm at p99.5), so the formula was scored against a runoff series
that never saw the anchor event.

The first version of this test fed the formula `MagnitudeGBM`'s LOCO-predicted
magnitude instead, reasoning that the runoff *classifier* "saw" the storm — its
calibrated probability crosses the operating threshold on 2016-10-27. That
reasoning doesn't transfer to the magnitude: `MagnitudeGBM` is fit by direct
regression against ERA5's own `sro_mm_day`, so out-of-sample it reproduces
something close to ERA5's own tiny value for that date (0.0067 mm predicted vs
~0.0037 mm observed) — not the storm intensity IMERG saw. The classifier's
probability and the regressor's magnitude are different transforms of the same
score; only the probability escaped ERA5's blind spot. Feeding the formula that
magnitude never actually controlled for the label problem — it inherited the
same underestimate through a different model. (That conflation was the error in
the version of this report generated before 5 August 2026.)

This version adds a magnitude source that genuinely does not touch ERA5: the
curve-number runoff depth in `RuleBaseline.runoff_depth()`, driven directly by
`precipitation_mm_day` — confirmed IMERG-sourced, never ERA5's `tp` (which is
tracked separately as `era5_rain_mm_day`) — plus slope, soil moisture and bare
fraction. It is a fixed formula with no `fit()` step, so there is no LOCO fold
to run and nothing to leak.

## Result

| runoff source | rank | of | percentile | verdict |
|---|---:|---:|---:|:--|
{rows}

{interp}

## Top 10 days, {winner}

{top}

## What this does and does not establish

- **`k` is anchored on this same event**, so the anchor sets the **scale** and the
  rank tests the **shape**. Only the ranking is independent, for all three
  sources.
- **One measurement.** 24,400 t for October 2016, itself derived from the mooring
  record — so the anchor and any check against it share a source.
- **τ is assumed**, not measured for these wadis. Reported as the 20–85% Negev
  band, never as a point.
- **Relative classes remain the honest output.** A mass is reported only with the
  τ band attached.
- **`training_set_full.parquet` has no `bare_fraction`/soil-texture columns.**
  `SedimentProxy.index()` falls back to the same default for every catchment
  when a column is absent, so the erodibility and bare-fraction terms were
  constant across this whole test — never actually differentiating catchments.
  That doesn't change any of the rankings above (a constant factor cancels in a
  ranking), but it means two of the formula's six terms were never exercised
  here.

The real validation is `scripts/24` against the 13 documented sea-reaching floods,
of which we hold **one date**. See `docs/karam_handoff.md` Request 0.
""")


if __name__ == "__main__":
    main()
