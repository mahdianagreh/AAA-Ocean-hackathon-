# Autopsy: the runoff label is a rainfall mask

**Date:** 4 August 2026 · `scripts/23_label_autopsy.py` · follows
`reports/model/label_leakage.md`

`scripts/22` found that one column of ERA5 rainfall scores AP **0.9785** against
our 20-feature **0.7445**. This is the follow-up question — how much of the label
is rainfall and how much is hydrology — and the answer is **none of it is
hydrology.**

## 1 · A one-line rule reproduces the label

`target = (sro_mm_day > 0.002)`.

| rule                |   accuracy |     F1 |   disagreements |
|:--------------------|-----------:|-------:|----------------:|
| era5_rain > 0.1 mm  |     0.9304 | 0.6905 |             822 |
| era5_rain > 0.25 mm |     0.9738 | 0.8555 |             309 |
| era5_rain > 0.5 mm  |     0.9915 | 0.9433 |             100 |
| era5_rain > 1 mm    |     0.969  | 0.7544 |             366 |
| era5_rain > 2 mm    |     0.9503 | 0.5374 |             587 |

**`era5_rain > 0.5 mm` reproduces the label at F1 0.9433, accuracy
0.9915** — disagreeing on 100 of 11,810
rows. Nothing about infiltration, antecedent moisture, slope or soil survives
into the binary target.

## 2 · The magnitude carries no land-surface response either

If the binary label is a rainfall mask, the magnitude might still hold physics.
It does not. The runoff coefficient `sro / rain` on 562 wet rows:

| p5 | p25 | p50 | p75 | p95 | spread |
|---:|---:|---:|---:|---:|---:|
| 0.0041 | 0.0042 | 0.0042 | 0.0053 | 0.0067 | **1.7×** |

Effectively constant. And its response to catchment state:

| feature | spearman with runoff coefficient |
|---|---:|
| `area_km2` | +0.646 |
| `soil_moisture_lag1d` | +0.263 |
| `soil_moisture_lag3d` | +0.244 |
| `temp_c` | -0.140 |
| `precip_prior_7d_mm` | +0.135 |
| `dry_days_before` | -0.121 |
| `slope_mean_deg` | +0.005 |

The strongest correlate is **`area_km2`** — a static property, and an artifact of
averaging ERA5's ~81 km² cells over 36–65 km² catchments rather than a
hydrological response. Soil moisture, which should dominate an arid
infiltration-controlled system, manages +0.26.

## 3 · The quantity is physically unusable for these wadis

| | value |
|---|---:|
| ERA5-Land runoff coefficient here | **0.42%** |
| Published arid Negev storm coefficients | 5–20% |
| Ratio | **low by 12–47×** |
| Largest `sro` in the entire 2,362-day record | 0.2115 mm |
| Label threshold | 0.002 mm |

A record maximum of 0.21 mm of surface runoff, for a
4,453 km² catchment that discharged 24,400 t of sediment in 2016. **We have been
thresholding numerical noise.**

ERA5-Land is a global reanalysis whose land-surface scheme is not built for
hyper-arid flash-flood catchments; this is a known limitation of the product, not
a bug in our extraction. It belongs in `docs/data_dictionary.md` as a stated
limitation of the source.

## 4 · Why the label cannot be repaired from data on disk

| agreement   |   rows |   positives |   positive_rate |
|:------------|-------:|------------:|----------------:|
| ERA5 only   |    373 |         369 |           0.989 |
| IMERG only  |    678 |          22 |           0.032 |
| both dry    |  10296 |          74 |           0.007 |
| both wet    |    463 |         463 |           1     |

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
