# How much of Component A is ERA5 predicting itself?

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
| IMERG | `precipitation_mm_day`, `precip_prior_{1,3,7}d_mm`, `rain_over_p{50,90,99}`, `rain_self_percentile`, `dry_days_before` | GPM IMERG — **independent** of the label |
| ERA5 state | `soil_moisture_lag{1,3}d`, `wind_speed_ms`, `wind_direction_deg`, `temp_c` | ERA5-Land `swvl1`, `u10`, `v10`, `t2m` — **the label's own weather** |
| neutral | `season_sin/cos`, `area_km2`, `slope_mean_deg`, `drainage_density_km_km2`, `elongation_ratio` | calendar and terrain |

## ERA5 does not mis-scale storms — it fails to see them

This distinction decides what the fix is, and a ratio conditioned on *both*
products being wet hides it completely: that ratio selects the rows where they
already agree and duly reports ≈1.0.

| IMERG >   |   n | ERA5 dry (<0.1mm)   | ERA5 also > thr   |   ratio where both wet |
|:----------|----:|:--------------------|:------------------|-----------------------:|
| 1 mm      | 779 | 35.4%               | 38.5%             |                   0.99 |
| 5 mm      | 195 | 22.1%               | 22.1%             |                   1.05 |
| 10 mm     |  40 | 20.0%               | 37.5%             |                   1.18 |

When ERA5 sees a storm it gets the magnitude about right. It simply does not see
most of them — including **20.0% of the heaviest
IMERG days in the record.**

### And the label inherits the blind spot

| | catchment-days | `target = 1` |
|---|---:|---:|
| IMERG-wet (> 1 mm) | 779 | 398 (51.1%) |
| ...of those, **ERA5 dry (< 0.1 mm)** | 276 | **1 (0.4%)** |

**276 catchment-days on which IMERG observed real rain are labelled
non-events, because ERA5 did not see the storm.** October 2016 is one of those
rows. This is not a threshold to be tuned — the label is blind wherever its source
product is.

## Four models, LOCO, identical apart from the columns they see

| | features | n | mean AP |
|---|---|---:|---:|
| **M1** | IMERG + neutral | 15 | 0.6623 |
| **M2** | CD- shipped | 20 | 0.7445 |
| **M3** | ERA5 same-day rain only | 1 | 0.9785 |
| **M4** | ERA5 + neutral, no IMERG | 12 | 0.9855 |

- **M2 − M1 = +0.0822** — what the five ERA5 state variables add.
- **M3 − M2 = +0.2340** — one column of the label's own forcing, against 20
  engineered features.
- **M4 − M1 = +0.3232** — ERA5 predicting ERA5, against independent IMERG
  predicting ERA5.

**A material share of the skill is the label's own atmosphere.** Adding five ERA5 state variables lifts AP by +0.0822, which is gain from features drawn from the same product as the label — not from hydrology.

## Tracking test

Held-out M2 predictions, against each rainfall product:

| | spearman |
|---|---:|
| prediction vs **ERA5** rainfall | +0.436 |
| prediction vs **IMERG** rainfall (its own input) | +0.634 |

The sharper form — does the prediction explain ERA5 rainfall *beyond* what its
own IMERG input already explains?

| predicting ERA5 rainfall (log1p) | R² |
|---|---:|
| from IMERG rainfall alone | 0.3163 |
| from IMERG rainfall + model prediction | 0.5240 |
| **incremental R² from the prediction** | **+0.2077** |

Incremental power here means the model learned to correct IMERG toward ERA5 —
a product offset, not hydrology.

## Caveats

- `era5_rain_mm_day` is missing on 0 rows and is **left NaN, never filled**;
  M3 and M4 run on the subset where it exists, so their APs are not on identical
  rows to M1/M2.
- All four use the same folds, resampling seed and hyperparameters, so the
  differences are attributable to the feature groups.
- Run-to-run AP variance is **±0.017**. Differences smaller than that are noise,
  and per `reports/model/label_problem.md` the 13-event validation set cannot
  resolve them either.
