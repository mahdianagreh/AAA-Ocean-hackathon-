"""Component B — feed the real runoff, anchor the scale, then try to break it.

Three things, in order.

1 · RUNOFF FROM THE RIGHT SOURCE
   `index()` takes Q, and until now every caller passed
   RuleBaseline.runoff_depth() - a curve number whose own initial-abstraction
   parameter had to be corrected from 0.2 to 0.05 before it produced anything
   but zero. Meanwhile ERA5's `sro` is the actual modelled runoff for every
   historical day, and MagnitudeGBM predicts it for days we have no label for.
   The formula was being driven by a hand calculation while a validated
   estimate of the same quantity sat unused beside it.

     historical  ->  sro_mm_day            (observed, what the label uses)
     forecast    ->  MagnitudeGBM          (predicted log-magnitude)

2 · ANCHOR THE SCALE
   calibrate_to_anchor() has existed and been tested since the module was
   written, but no run had computed October 2016's real index, so `k` was never
   set and every class was a within-dataset quantile. Anchoring makes the
   classes absolute and mass_estimate_t() usable.

3 · TRY TO FALSIFY THE FORMULA
   You cannot fit six terms on one measurement. You CAN ask whether the formula
   is obviously wrong: rank all 675 catalogued storms by sediment index and see
   where the one documented major sediment event lands. If Oct 2016 is not near
   the top, the formula has a problem.

   That is the only test the sediment side currently permits, and it is
   falsifiable with data already on disk.

RESULT, AND WHY THE TEST WAS INVALID (added 4 Aug)
   Oct 2016 ranked 193 of 2,362. I read that as the formula missing intensity,
   built scripts/21 to add it, and intensity did not rescue the event either.

   The cause is the label, not the formula. `sro` correlates +0.985 with ERA5's
   own rainfall and only +0.564 with IMERG's, and ERA5 largely MISSED October
   2016 - 0.77 mm at p92.6, against IMERG's 9.58 mm at p99.5. This test scored
   the sediment formula against a runoff series that never saw the anchor storm,
   so a low rank was the only possible outcome regardless of the physics.

   The ranking test is therefore retired as a formula check. See
   reports/model/label_problem.md. Section 3 of the report below is kept for the
   record with that caveat attached, not as evidence against the formula.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

from models.sediment_proxy import (ANCHOR_CATCHMENT, ANCHOR_EVENT,  # noqa: E402
                                   ANCHOR_MASS_T, CLASSES, TAU_NEGEV,
                                   SedimentParams, SedimentProxy)

TRAIN = ROOT / "data/processed/features/training_set_full.parquet"
REPORT = ROOT / "reports/model/sediment_anchor.md"

# The anchor is a 3-day window, not a single day. The mooring records turbidity
# elevated for 31.4 hours from 06:50 UTC on the 28th, so the sediment mass spans
# the 27th-29th and pinning it to one calendar day would understate the index it
# has to match.
ANCHOR_WINDOW = ("2016-10-27", "2016-10-29")


def main():
    df = pd.read_parquet(TRAIN)
    print(f"{len(df):,} catchment-days · {df.date.nunique():,} days\n")

    # ── 1. runoff from sro, not the curve number ─────────────────────────
    sp = SedimentProxy()
    df = df.copy()
    df["sediment_index"] = sp.index(df, df.sro_mm_day.to_numpy())
    print("Q sourced from ERA5 sro (observed), not the SCS curve number")
    print(f"  index range {df.sediment_index.min():.4g} .. "
          f"{df.sediment_index.max():.4g}")

    # ── 2. anchor on the real October 2016 index ────────────────────────
    lo, hi = ANCHOR_WINDOW
    win = df[(df.date >= lo) & (df.date <= hi)]
    anchor_row = win[win.catchment_id == ANCHOR_CATCHMENT]
    if anchor_row.empty:
        raise SystemExit(f"{ANCHOR_CATCHMENT} absent from {lo}..{hi}")
    # Sum over the window: the published mass is a total, not a daily rate.
    anchor_index = float(anchor_row.sediment_index.sum())
    print(f"\nanchor: {ANCHOR_EVENT} / {ANCHOR_CATCHMENT}, {lo}..{hi}")
    print(anchor_row[["date", "sro_mm_day", "sediment_index"]]
          .to_string(index=False))
    print(f"  window index total {anchor_index:.4g}")

    sp.calibrate_to_anchor(anchor_index)
    print(f"  k = {sp._k:.4g} tonnes per index unit  "
          f"(so the window reproduces {ANCHOR_MASS_T:,.0f} t)")

    # ── 3. the falsification test ───────────────────────────────────────
    # Storm-level: sum the index across catchments and across the storm's days,
    # because a published sediment mass is a per-event total.
    daily = df.groupby("date", as_index=False).sediment_index.sum()
    daily["mass_t"] = daily.sediment_index * sp._k
    daily = daily.sort_values("sediment_index", ascending=False).reset_index(drop=True)
    daily["rank"] = daily.index + 1
    n = len(daily)

    anchor_days = daily[(daily.date >= lo) & (daily.date <= hi)]
    best = anchor_days.sort_values("rank").iloc[0]
    print(f"\n=== falsification test: {n:,} days ranked by sediment index ===")
    print(f"{'rank':>6} {'date':<12} {'index':>12} {'mass_t':>10}")
    for _, r in daily.head(10).iterrows():
        mark = "  <- Oct 2016 window" if lo <= str(r.date.date()) <= hi else ""
        print(f"{int(r['rank']):>6} {r.date.date()!s:<12} "
              f"{r.sediment_index:>12.4g} {r.mass_t:>10,.0f}{mark}")

    pct = 100 * (1 - best["rank"] / n)
    print(f"\nOct 2016 best day: rank {int(best['rank'])} of {n:,} "
          f"({pct:.2f}th percentile)")
    verdict = ("PASS" if best["rank"] <= max(5, n * 0.01) else
               "MARGINAL" if best["rank"] <= n * 0.05 else "FAIL")
    print(f"verdict: {verdict}")
    if verdict != "PASS":
        print("  The one documented major sediment event does not rank at the")
        print("  top. The formula, the anchor window, or Q is wrong - this is")
        print("  the result, not something to tune away.")

    # ── 4. tau band, since a point estimate would overstate certainty ────
    print(f"\n=== transmission loss band on the anchor window ===")
    print(f"{'tau':>6} {'in Negev':>9} {'mass_t':>12}")
    for t in (0.0, 0.20, 0.35, 0.525, 0.70, 0.85, 0.95):
        alt = SedimentProxy(SedimentParams(transmission_loss=t))
        alt._k = sp._k          # same scale, different loss assumption
        m = float(alt.index(anchor_row, anchor_row.sro_mm_day.to_numpy()).sum()
                  * alt._k)
        flag = "yes" if TAU_NEGEV[0] <= t <= TAU_NEGEV[1] else "-"
        star = "  <- default" if abs(t - 0.525) < 1e-9 else ""
        print(f"{t:>6.3f} {flag:>9} {m:>12,.0f}{star}")

    # ── classes, now absolute ────────────────────────────────────────────
    cls = sp.classify(df, df.sro_mm_day.to_numpy())
    print(f"\n=== sediment class, anchored ===")
    print(cls.sediment_class.value_counts().reindex(list(CLASSES))
          .fillna(0).astype(int).to_string())
    print(f"basis: {cls.class_basis.iloc[0]}")

    write_report(df, daily, anchor_row, anchor_index, sp, best, n, verdict, cls)
    print(f"\nwrote {REPORT.relative_to(ROOT)}")


def write_report(df, daily, anchor_row, anchor_index, sp, best, n, verdict, cls):
    band = []
    for t in (0.20, 0.525, 0.85):
        alt = SedimentProxy(SedimentParams(transmission_loss=t))
        alt._k = sp._k
        band.append((t, float(alt.index(anchor_row,
                                        anchor_row.sro_mm_day.to_numpy()).sum()
                              * alt._k)))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# Component B — anchored, and tested against the record

**Date:** 4 August 2026 · `scripts/20_sediment_anchor_and_rank.py`

Component B is **a formula, not a model.** Nothing in it is trained. It has two
free parameters and neither is fitted in the machine-learning sense: `k`, the
index→tonnes scale, set from one published measurement; and `τ`, transmission
loss, taken from literature.

```
sediment_index = b · f(θ) · E(clay,sand,silt,SOC) · Q · D · (1 − τ)
```

## 1 · Runoff now comes from the right source

Every caller previously passed `RuleBaseline.runoff_depth()` — a curve number
whose own initial-abstraction parameter had to be corrected from 0.2 to 0.05
before it produced anything but zero. ERA5's `sro` is the actual modelled runoff
for every historical day, and `MagnitudeGBM` predicts it where no label exists.

| use | source of Q |
|---|---|
| historical | `sro_mm_day` — observed, the same quantity the label uses |
| forecast | `MagnitudeGBM` predicted log-magnitude |

The formula was being driven by a hand calculation while a validated estimate of
the same quantity sat unused beside it.

## 2 · The scale is anchored

`calibrate_to_anchor()` had existed and been tested since the module was written,
but no run had computed October 2016's real index — so `k` was unset and every
class was a within-dataset quantile.

**The anchor is a 3-day window, not a single day.** The mooring records turbidity
elevated for 31.4 hours from 06:50 UTC on the 28th, so the mass spans 27–29
October; pinning it to one calendar day would understate the index it has to
match.

{anchor_row[["date", "sro_mm_day", "sediment_index"]].to_markdown(index=False)}

Window index total **{anchor_index:.4g}** → `k` = **{sp._k:.4g}** t per index unit,
which reproduces the published {ANCHOR_MASS_T:,.0f} t.

**One point fixes the scale and cannot validate the shape.** Six terms, one
degree of freedom. Any mass for another event is extrapolation along an
unverified line.

## 3 · Falsification test — **{verdict}**, and the test is invalid

> **Retired 4 August 2026.** This test does not measure the formula. It ranks days
> by a sediment index driven by ERA5 `sro`, and **ERA5 largely missed October
> 2016** — 0.77 mm at p92.6, against IMERG's 9.58 mm at p99.5. `sro` correlates
> +0.985 with ERA5's own rainfall and only +0.564 with IMERG's, so the runoff
> series used here never saw the anchor storm. A low rank was the only available
> outcome whatever the physics. See `reports/model/label_problem.md`.
>
> Kept below for the record, not as evidence against the formula.

You cannot fit six terms on one measurement. You can ask whether the formula is
obviously wrong: rank every day in the record by sediment index and see where the
one documented major sediment event lands.

{daily.head(10)[["rank", "date", "sediment_index", "mass_t"]].to_markdown(index=False)}

**October 2016's best day ranks {int(best['rank'])} of {n:,}.**

{"The formula puts the one documented major sediment event at the top of the record, which is what it should do if the physics is right. That is not proof it is correct — it is the absence of the most obvious way it could have been wrong." if verdict == "PASS" else "The one documented major sediment event does not rank at the top. Either the formula, the anchor window, or the runoff input is wrong. **This is the result, not something to tune away.**"}

## 4 · Transmission loss is a band, not a point

τ is the project's largest single assumption. Between 13% and 98% of a desert
flood infiltrates the wadi bed and never reaches the sea; the Negev range is
20–85%. Reporting one mass would overstate the certainty available.

| τ | mass for the anchor window |
|---:|---:|
| 0.20 (wettest Negev bound) | {band[0][1]:,.0f} t |
| **0.525 (default, Negev midpoint)** | **{band[1][1]:,.0f} t** |
| 0.85 (driest Negev bound) | {band[2][1]:,.0f} t |

The default is the nearest documented analogue, **not** a measurement for these
wadis. Every classified row carries the τ used, so the assumption travels with
the number.

## Output classes, now absolute

{cls.sediment_class.value_counts().reindex(list(CLASSES)).fillna(0).astype(int).rename_axis("class").rename("rows").to_frame().to_markdown()}

Basis: `{cls.class_basis.iloc[0]}`

## What the sediment side still cannot do

- **One measurement.** 24,400 t for Oct 2016. The ≈21,000 t figure for Feb 2013
  has no confirmed date — `docs/event_dates.md` flags it as needing a citation and
  the Phase 2 plan declares that event dead.
- **No independent validation.** The 24,400 t is itself derived from the same
  mooring record, so the anchor and any check against it are not independent.
- **τ is assumed**, not measured for Aqaba.
- **Relative classes are the honest output**, per concept §10.4. A mass is
  reported only with the τ band attached.
""")


if __name__ == "__main__":
    main()
