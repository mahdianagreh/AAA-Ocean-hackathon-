# Component B — anchored, and tested against the record

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

| date                |   sro_mm_day |   sediment_index |
|:--------------------|-------------:|-----------------:|
| 2016-10-27 00:00:00 |  0.00372888  |       5946.16    |
| 2016-10-28 00:00:00 |  0.00343999  |       5485.49    |
| 2016-10-29 00:00:00 |  1.09033e-06 |          1.73867 |

Window index total **1.143e+04** → `k` = **2.134** t per index unit,
which reproduces the published 24,400 t.

**One point fixes the scale and cannot validate the shape.** Six terms, one
degree of freedom. Any mass for another event is extrapolation along an
unverified line.

## 3 · Falsification test — **FAIL**, and the test is invalid

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

|   rank | date                |   sediment_index |   mass_t |
|-------:|:--------------------|-----------------:|---------:|
|      1 | 2010-01-18 00:00:00 |         351728   |   750623 |
|      2 | 2014-03-09 00:00:00 |         250693   |   535004 |
|      3 | 2015-10-26 00:00:00 |         157869   |   336909 |
|      4 | 2022-01-09 00:00:00 |         117839   |   251479 |
|      5 | 2020-03-13 00:00:00 |         111846   |   238691 |
|      6 | 2020-03-14 00:00:00 |         110249   |   235283 |
|      7 | 2016-03-26 00:00:00 |          96455   |   205845 |
|      8 | 2020-02-25 00:00:00 |          95288.9 |   203356 |
|      9 | 2015-02-21 00:00:00 |          92109.5 |   196571 |
|     10 | 2007-02-03 00:00:00 |          91636.1 |   195561 |

**October 2016's best day ranks 193 of 2,362.**

The one documented major sediment event does not rank at the top. Either the formula, the anchor window, or the runoff input is wrong. **This is the result, not something to tune away.**

## 4 · Transmission loss is a band, not a point

τ is the project's largest single assumption. Between 13% and 98% of a desert
flood infiltrates the wadi bed and never reaches the sea; the Negev range is
20–85%. Reporting one mass would overstate the certainty available.

| τ | mass for the anchor window |
|---:|---:|
| 0.20 (wettest Negev bound) | 41,095 t |
| **0.525 (default, Negev midpoint)** | **24,400 t** |
| 0.85 (driest Negev bound) | 7,705 t |

The default is the nearest documented analogue, **not** a measurement for these
wadis. Every classified row carries the τ used, so the assumption travels with
the number.

## Output classes, now absolute

| class   |   rows |
|:--------|-------:|
| Low     |  11512 |
| Medium  |    150 |
| High    |     54 |
| Extreme |     94 |

Basis: `banded against AQ-2016-10-28 (≈24,400 t)`

## What the sediment side still cannot do

- **One measurement.** 24,400 t for Oct 2016. The ≈21,000 t figure for Feb 2013
  has no confirmed date — `docs/event_dates.md` flags it as needing a citation and
  the Phase 2 plan declares that event dead.
- **No independent validation.** The 24,400 t is itself derived from the same
  mooring record, so the anchor and any check against it are not independent.
- **τ is assumed**, not measured for Aqaba.
- **Relative classes are the honest output**, per concept §10.4. A mass is
  reported only with the τ band attached.
