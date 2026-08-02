# Model card — Component A, runoff risk classifier

**Generated:** `scripts/11_train_runoff_model.py` · commit `962a6a5`
**Feature source:** `stub:synthetic(seed=20260803,n=220)`
**Static features:** excluded (ablation)

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
12 features (0 static, 12 dynamic)
```

Features used (12):

```
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
| rule_baseline  | loco     |            5 | 0.858747 |  0.976705 | 0.0465103 |
| rule_baseline  | temporal |            1 | 0.801966 |  0.966003 | 0.0570824 |
| calibrated_gbm | loco     |            5 | 0.825323 |  0.968429 | 0.0448668 |
| calibrated_gbm | temporal |            1 | 0.796314 |  0.968554 | 0.0508628 |

**Verdict:** GBM does NOT clear the baseline (-0.033 AP)

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
|  84 |   0.020132  |   0        |
|  84 |   0.0202217 |   0        |
|  84 |   0.0203546 |   0        |
|  84 |   0.0323017 |   0.047619 |
|  84 |   0.541723  |   0.619048 |

Predicted against observed. A calibrated model tracks the two columns together.

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
