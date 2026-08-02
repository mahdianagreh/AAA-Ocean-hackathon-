# Model card — Component A, runoff risk classifier

**Generated:** `scripts/11_train_runoff_model.py` · commit `531dd23`
**Feature source:** `stub:synthetic(seed=20260803,n=220)`
**Static features:** included

> ## THIS CARD DESCRIBES A SYNTHETIC RUN
> The feature matrix does not exist yet — every rainfall granule has to be
> re-pulled against the corrected AOI first. Numbers below come from a stub
> with a known generating rule, and exist to prove the harness works.
> **They are not results about Aqaba.**

---

## Data

```
1100 rows, 5 catchments, 220 events
132 positive (12.0%), tiers {'silver': 1100}
29 features (17 static, 12 dynamic)
```

Features used (29):

```
  area_km2
  relief_m
  slope_mean_deg
  slope_max_deg
  drainage_density_km_km2
  dist_to_coast_max_km
  dist_to_coast_mean_km
  elongation_ratio
  accum_mean_cells
  accum_p95_cells
  bare_fraction
  built_up_fraction
  clay_pct
  sand_pct
  silt_pct
  soc_g_kg
  road_density_km_km2
  rain_1h_mm
  rain_3h_mm
  rain_6h_mm
  rain_24h_mm
  rain_3h_percentile
  anomaly_score
  soil_moisture_t24h
  soil_moisture_t72h
  precip_prior_72h_mm
  precip_prior_7d_mm
  wind_speed_ms
  temp_2m_c
```

**Label:** `runoff_label`, binary. Silver tier is ERA5-Land surface runoff exceeding
that catchment's own p99 within 24 h of the rainfall window — a *modelled* quantity
from ECMWF's land-surface scheme, not an observation. The single gold event is held
back and never trained on.

**`sro` and `ssro` are labels, never features.** Asserted in
`backend/src/models/schema.py`, not left as a comment.

---

## Results

| model          | split    |   folds_used |       AP |   ROC_AUC |     Brier |
|:---------------|:---------|-------------:|---------:|----------:|----------:|
| rule_baseline  | loco     |            5 | 0.860958 |  0.977031 | 0.0436359 |
| rule_baseline  | temporal |            1 | 0.812881 |  0.969192 | 0.0537436 |
| calibrated_gbm | loco     |            5 | 0.814006 |  0.968284 | 0.044954  |
| calibrated_gbm | temporal |            1 | 0.760234 |  0.963599 | 0.0562209 |

**Verdict:** GBM does NOT clear the baseline (-0.047 AP)

Both predictors run through identical splits and identical metrics. If the rule
baseline wins, that is the reported result — a four-line formula matching gradient
boosting on a few hundred rows is a plausible outcome, not a failure to hide.

### Why these splits

**Leave-one-catchment-out.** Static terrain features are constant within a catchment,
so a random split lets the model recognise which catchment a row belongs to and score
beautifully while learning nothing. A data-design constraint, not a tuning preference.

The five folds are not equally informative: AQ-C01 is 96% of the drainage and carries
most positive labels. **All folds are reported; the mean alone would hide that.**

**Temporal holdout**, train ≤2014 / test ≥2015, so October 2016 is genuinely unseen.

### Why these metrics

Average precision leads, because floods are rare and accuracy is meaningless when
"never" scores well. Brier score measures the probability itself, which is what the
dashboard shows a user. ROC-AUC is reported but not led with — it stays flattering
under imbalance.

Any fold with fewer than 5 positives is flagged; its metrics are noise.

---

## Calibration

Platt scaling on the raw margin, fitted by internal cross-validation on the training fold only — never the test fold.

|   n |   predicted |   observed |
|----:|------------:|-----------:|
|  84 |   0.0200878 |   0        |
|  84 |   0.0201952 |   0        |
|  84 |   0.0203525 |   0        |
|  84 |   0.0256289 |   0.047619 |
|  84 |   0.545384  |   0.619048 |

Predicted against observed. A calibrated model tracks the two columns together.

---

## Component D — sediment load proxy

**A formula, not a model.** Nothing here is trained.

```
sediment_index = b · f(θ) · E(clay, sand, silt, SOC) · Q · D · (1 − τ)
```

| Term | Meaning | Source |
|---|---|---|
| `b` | bare fraction, 0–1 — the erodible surface | ESA WorldCover |
| `f(θ)` | slope term, `(θ/12°)^1.3` — transport capacity | GLO-30 |
| `E` | erodibility from soil texture — what is detachable | SoilGrids |
| `Q` | runoff volume in m³ — the carrier | Component A baseline |
| `D` | drainage density, km/km² — channel access | GLO-30 |
| `τ` | transmission loss — what never arrives | **assumption, see below** |

Output is a **relative class**, not a mass, per concept §10.4.

| class   |   rows |
|:--------|-------:|
| Low     |    550 |
| Medium  |    330 |
| High    |    165 |
| Extreme |     55 |

Basis: WITHIN-DATASET QUANTILES - no anchor, class is relative only

### The anchor

One published measurement exists: **≈24,400 t** for AQ-2016-10-28 (Kalman et al. 2025).
It fixes the index→tonnes **scale**. It cannot validate the **shape** — a single point
constrains one degree of freedom and the formula has six terms. **One point is not a
curve.** Any mass reported for another event is extrapolation along an unverified line,
and `mass_estimate_t()` refuses to run until anchored rather than returning a
comfortable number.

### Transmission loss — the project's largest assumption, now visible

Between **13.2% and 98%** of a desert flood infiltrates the wadi bed and never reaches
the sea. The Negev, the nearest studied analogue, is **20–85%**. Everything before this
module implied **τ = 0** — the most optimistic value available, and certainly wrong.

Default **τ = 0.525**, the Negev midpoint. Chosen because it is the nearest
documented setting, *not* because it is measured here. It is not.

|   transmission_loss | in_negev_range   | is_default   |       mean_index |   vs_tau_zero |
|--------------------:|:-----------------|:-------------|-----------------:|--------------:|
|               0     | False            | False        |      2.43259e+06 |         1     |
|               0.2   | True             | False        |      1.94608e+06 |         0.8   |
|               0.35  | True             | False        |      1.58119e+06 |         0.65  |
|               0.525 | True             | True         |      1.15548e+06 |         0.475 |
|               0.7   | True             | False        | 729778           |         0.3   |
|               0.85  | True             | False        | 364889           |         0.15  |
|               0.95  | False            | False        | 121630           |         0.05  |

τ enters as the linear factor (1 − τ), so the whole curve follows from one evaluation.
Every classified row carries the τ used, so the assumption travels with the number
instead of living in a document.

---

## What this model cannot do

- **It does not predict a flood reaching the sea.** It predicts the Silver label —
  modelled runoff anomaly. One event has ground truth, and it is held out.
- **Five catchments is not a sample.** Any pattern across five points could be
  coincidence, and no validation scheme fixes that.
- **AQ-C01's area carries ±4%** from separating endorheic basins from DEM artifacts.
  Per-catchment totals inherit it.
- **It says nothing about the sea.** Transport is Component C; this feeds it a
  sediment class, nothing more.
- **The sediment proxy is not calibrated**, only anchored at one point, and its τ is
  assumed rather than measured for these wadis.
