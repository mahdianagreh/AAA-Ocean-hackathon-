# Testing the sediment formula against three runoff inputs

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
| ERA5 observed sro | 193 | 2,362 | 91.83% | **FAIL** |
| runoff MODEL, fit to sro (LOCO) | 176 | 2,362 | 92.55% | **FAIL** |
| rule-based CN runoff (IMERG rain, unfit) | 12 | 2,362 | 99.49% | **PASS** |

**`rule-based CN runoff (IMERG rain, unfit)` passes**: it puts the one documented major sediment event at the top of a 27-year record, driven by a runoff estimate that (a) is available at forecast time and (b) is never fit to ERA5's `sro` — so it cannot inherit ERA5's underestimate of this storm the way the other two sources do. **That is not proof the physics is right** — it is the absence of the most obvious way it could have been wrong, and it is the first source in this line of testing to clear that bar.

The other two both fail, and for a related reason: ERA5's observed `sro` under-recorded the storm outright (0.77 mm at p92.6 against IMERG's 9.58 mm at p99.5), and `MagnitudeGBM`'s predicted `sro` is fit by regression to reproduce that same column — so out-of-sample it reproduces something close to ERA5's own tiny value for this date, not the storm intensity IMERG actually saw. The runoff *classifier*'s calibrated probability does cross its operating threshold on this date (it correctly flags the day as anomalous relative to its own scale) — but that probability is a different model output from the magnitude the sediment formula consumes, and a high probability does not imply the largest absolute mm value. Conflating the two was the mistake in the first version of this test.

## Top 10 days, rule-based CN runoff (IMERG rain, unfit)

|   rank | date       |         sed_rule |   mass_t |
|-------:|:-----------|-----------------:|---------:|
|      1 | 2014-03-09 |      3.16181e+06 |    96133 |
|      2 | 2010-01-18 |      2.74037e+06 |    83319 |
|      3 | 2020-03-12 |      2.0713e+06  |    62977 |
|      4 | 2016-03-26 |      1.73641e+06 |    52795 |
|      5 | 2022-01-01 |      1.68275e+06 |    51163 |
|      6 | 1999-02-07 |      1.63076e+06 |    49582 |
|      7 | 2010-02-25 |      1.16195e+06 |    35328 |
|      8 | 2014-12-09 | 833764           |    25350 |
|      9 | 2022-01-09 | 816403           |    24822 |
|     10 | 2001-04-04 | 774036           |    23534 |

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
