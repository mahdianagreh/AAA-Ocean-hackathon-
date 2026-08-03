# Model card — Component A, runoff risk classifier

**Data:** `training_set_full.parquet` — 11,810 catchment-days, 1998–2022
**Positive:** `sro > 0.002 mm/day` — 928 rows (7.9%)
**Features:** 10

---

## The target, and why it is a threshold

The delivered matrix was 390 rows from the top 100 rainfall days in 27 years, so
99% had runoff — "will there be runoff" was answered before the model saw it. The
full population is assembled from all 77 ERA5 months on disk: 11,810 rows at
7.9% positive.

The threshold is **anchored, not tuned for balance.** The one documented
sediment-delivering flood — October 2016, ≈24,400 t — peaks at 0.00373 mm, the
94.5th percentile of all catchment-days. 0.002 mm sits below it, so the sole piece
of ground truth is comfortably positive rather than marginal.

## Imbalance: two problems, two fixes

At 7.9% positive, `min_child_weight` is a floor on the sum of
hessians in a leaf, and h = p(1−p):

```
base rate 7.9% · h = 0.0724 · a leaf needs ~55 positives to clear min_child_weight=4
base rate 20.0% · h = 0.1600 · a leaf needs ~25 positives to clear min_child_weight=4
```

A leaf needs ~55 positives before it may exist. With 928 positives
across 10 features and 5 catchments, predictive regions holding fewer get
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

| held_out   |   fit_rows |   test_rows |   test_pos |   test_pos_rate |   baseline_AP |   gbm_AP |   gbm_Brier | calibrated   |       A |      B |
|:-----------|-----------:|------------:|-----------:|----------------:|--------------:|---------:|------------:|:-------------|--------:|-------:|
| AQ-C01     |       2540 |        2362 |        274 |          0.116  |        0.2613 |   0.4361 |     0.08472 | True         | -0.6678 | 1.9707 |
| AQ-C02     |       2785 |        2362 |        215 |          0.091  |        0.2048 |   0.5173 |     0.0631  | True         | -0.7468 | 1.8386 |
| AQ-C03     |       2975 |        2362 |        158 |          0.0669 |        0.1982 |   0.5318 |     0.04491 | True         | -0.7559 | 1.7872 |
| AQ-C04     |       3050 |        2362 |        139 |          0.0588 |        0.1716 |   0.5549 |     0.0387  | True         | -0.755  | 1.776  |
| AQ-C05     |       3050 |        2362 |        142 |          0.0601 |        0.166  |   0.5664 |     0.0391  | True         | -0.7366 | 1.8191 |

**mean AP: baseline 0.2004 · gbm 0.5213 · delta +0.3209**

**Verdict: GBM beats the baseline by +0.3209 AP**

### Leakage, measured

Random K-fold AP 0.5138 against LOCO AP 0.5213 — a gap of **-0.0075**. That difference is catchment memorisation with a number on it: static features are constant within a catchment, so a random split lets the model recognise which catchment a row belongs to. Reporting both is stronger than either alone.

## Calibration on the held-out catchment

|   n |   predicted |   observed |
|----:|------------:|-----------:|
| 473 |   0.0208342 |  0.0295983 |
| 472 |   0.0464708 |  0.0508475 |
| 472 |   0.0782161 |  0.0529661 |
| 472 |   0.131152  |  0.101695  |
| 473 |   0.288471  |  0.344609  |

Predicted against observed. A calibrated model tracks the two columns together.

## Feature importance

|                         |   mean_abs_shap |
|:------------------------|----------------:|
| soil_moisture_lag3d     |          0.8226 |
| soil_moisture_lag1d     |          0.7356 |
| precipitation_mm_day    |          0.6311 |
| precip_prior_7d_mm      |          0.4654 |
| precip_prior_1d_mm      |          0.4257 |
| area_km2                |          0.3311 |
| precip_prior_3d_mm      |          0.2647 |
| elongation_ratio        |          0.0371 |
| drainage_density_km_km2 |          0.0222 |
| slope_mean_deg          |          0.0169 |

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
