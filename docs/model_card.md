# Model card — Component A, runoff risk classifier

**Registered as:** `runoff_weighted_gbm_dc5c1b7_20260805T084212Z` (see
`data/models/model_versions.jsonl`) · **Data:** `training_set_full.parquet` —
11,810 catchment-days, 1998–2022 · **Positive:** `sro > 0.002 mm/day` — 928
rows (7.9%) · **Features:** 20, configuration `CD-`

---

## The target is a threshold, and it is not "reached the sea"

The label is **ERA5-Land surface runoff generation** — a reanalysis model's
land-surface scheme, not an observation and not a flood reaching the coast.
`sro > 0.002 mm/day` is **anchored, not tuned for balance**: the one
documented sediment-delivering flood, October 2016 (≈24,400 t), peaks at
0.00373 mm on AQ-C01, the 94.5th percentile of all catchment-days, so the
sole piece of ground truth sits comfortably positive rather than marginal.

**This label fires 21–78× more often than the literature's sea-reaching
flood rate** (13 documented events since 1994 vs. 928 positives here), and it
is blind on exactly the days ERA5 misses a storm IMERG sees — including the
anchor storm itself. Full write-up: `reports/model/label_problem.md`. Read
"the model predicts runoff" as "the model predicts what ERA5-Land's
reanalysis would have generated," not as "the model predicts a flood."

## How much of the score is leakage, decomposed

`scripts/22_label_leakage_diagnostic.py` splits the 20 features by source and
retrains on each subset:

| model | features | n | mean AP |
|---|---|---:|---:|
| M1 — IMERG + neutral, **no ERA5 input at all** | rainfall, climatology, season, static | 15 | **0.6623** |
| M2 — **CD- shipped** (this model) | + ERA5 antecedent/synoptic state | 20 | **0.7445** (0.7474 reproduced 5 Aug) |
| M3 — one column of ERA5's own same-day rainfall | — | 1 | 0.9785 |
| M4 — ERA5 + neutral, no IMERG | — | 12 | 0.9855 |

**M2 − M1 = +0.082**: five ERA5-state features (`soil_moisture_lag{1,3}d`,
`wind_speed_ms`, `wind_direction_deg`, `temp_c` — ERA5-Land's own `swvl1`,
`u10`/`v10`, `t2m`) contribute about 15% of the model's lift over baseline,
and they are drawn from the same reanalysis run as the label — that is
leakage, at 5× the ±0.017 noise floor (below). Confirmed independently by
SHAP on the shipped model: `wind_direction_deg` and `temp_c` rank 2nd and 3rd
by mean |SHAP|, immediately behind rainfall.

**Quote 0.662, not 0.7445/0.7474, for "predicts runoff from inputs
independent of the label's own atmosphere."** The higher, shipped number is
real and reproducible, but part of it is the model partially reconstructing
ERA5's own weather state rather than learning wadi hydrology.

## Results — LOCO, all five folds (measured 5 Aug 2026)

| held_out | test_rows | test_pos_rate | baseline AP | **gbm AP** | ROC_AUC | Brier |
|:---|---:|---:|---:|---:|---:|---:|
| **AQ-C01** | 2,362 | 11.60% | 0.2613 | **0.6096** | 0.8938 | 0.0765 |
| AQ-C02 | 2,362 | 9.10% | 0.2048 | 0.7521 | 0.9331 | 0.0446 |
| AQ-C03 | 2,362 | 6.69% | 0.1982 | 0.7691 | 0.9683 | 0.0298 |
| AQ-C04 | 2,362 | 5.88% | 0.1716 | 0.8025 | 0.9639 | 0.0247 |
| AQ-C05 | 2,362 | 6.01% | 0.1660 | 0.8035 | 0.9675 | 0.0255 |

**mean AP: baseline 0.2004 · gbm 0.7474 · delta +0.5470**
F1 0.6388 @ threshold 0.3872 · precision 0.628 · recall 0.650

### AQ-C01 is the fold that matters, and it is the weakest one

**AQ-C01 (Wadi Yutum) carries 96% of the system's total discharge** — nearly
every alert this system will ever raise is, in practice, a prediction about
this one catchment. Its LOCO AP, 0.6096, is the lowest of the five and
noticeably below the 0.7474 mean. Reporting only the mean would hide the
model's real weak point behind four catchments that carry almost none of the
project's actual stakes.

**Not being chased further.** Run-to-run AP variance from column-ordering
alone is **±0.017**, measured directly — so on five folds, any delta under
~0.03 cannot be distinguished from noise. AQ-C01's gap to the mean (0.138) is
real and above that floor, but there is no honest way to close it by further
hyperparameter tuning on five data points; the correct response is reporting
it clearly, not tuning against noise.

### Leakage, measured by split design — an open finding, not yet resolved

An earlier config (pre-CD-, mean AP ~0.52) measured random-CV at 0.514 against
LOCO's 0.521 — a gap of only −0.008, reported as evidence the model was not
memorising catchment identity. **That check has not held up against the model
actually shipped.** Re-run on the current CD- configuration (5 Aug 2026):

| split | pooled AP |
|---|---:|
| random 5-fold, stratified | **0.7286** |
| LOCO | **0.6831** |

**Gap +0.0455 — random CV scores higher than LOCO by 2.7× the ±0.017 noise
floor.** This is the direction and rough shape of the exact failure LOCO
exists to catch: static terrain columns (`area_km2`, `slope_mean_deg`,
`drainage_density_km_km2`, `elongation_ratio`) are constant per catchment, so
a random split can let the model partially learn which catchment a row
belongs to rather than the process. **LOCO remains the reported number** for
every metric above because it is the only split that tests transfer to a
genuinely unseen catchment, and this gap is exactly why. Which static
feature(s) drive it has not been isolated — that is follow-up work, not
something this card's numbers already account for.

## Temporal holdout — train ≤2014, test ≥2015 (measured 5 Aug 2026)

| | rows | positive rate |
|---|---:|---:|
| train (≤2014) | 6,300 | 8.0% |
| test (≥2015) | 5,510 | 7.7% |

**Pooled AP 0.5923** vs. baseline 0.2083 · ROC_AUC 0.9158 · Brier 0.0482.

**The headline claim, measured rather than assumed:** trained only on data
through 2014 — October 2016 genuinely unseen — the model's predicted
probability for AQ-C01 on 2016-10-27 ranks **57th of 1,102** held-out AQ-C01
catchment-days from 2015–2022 (**94.83rd percentile**). This is not "the
highest in 26 years" — that framing overstated what a temporal holdout of
2015–2022 can show — but it is a genuine, falsifiable result: the storm that
produced the one documented major sediment event lands in the top 5% of
years the model never trained on, for the one catchment that carries 96% of
discharge.

## Feature importance (SHAP, shipped model, mean |value| over all rows)

| feature | mean \|SHAP\| |
|:---|---:|
| rain_self_percentile | 0.8736 |
| wind_direction_deg | 0.8167 |
| temp_c | 0.7833 |
| precip_prior_1d_mm | 0.4144 |
| season_cos | 0.3239 |
| rain_over_p90 | 0.2833 |
| soil_moisture_lag3d | 0.2456 |
| soil_moisture_lag1d | 0.2441 |
| precip_prior_3d_mm | 0.1915 |
| precipitation_mm_day | 0.1879 |
| season_sin | 0.1876 |
| wind_speed_ms | 0.1851 |
| rain_over_p99 | 0.1737 |
| dry_days_before | 0.1094 |
| precip_prior_7d_mm | 0.1037 |
| area_km2 | 0.0969 |
| slope_mean_deg | 0.0853 |
| rain_over_p50 | 0.0788 |
| drainage_density_km_km2 | 0.0373 |
| elongation_ratio | 0.0124 |

`wind_direction_deg` and `temp_c` — both ERA5-state, both named in the
leakage decomposition above — rank 2nd and 3rd, immediately behind rainfall.
This is independent confirmation of the M2−M1 finding, not a new one.

## What this model cannot do

- **It predicts modelled runoff generation in a reanalysis, not a flood
  reaching the sea**, and part of its score is the model recovering ERA5's
  own weather state rather than learning wadi hydrology — see the leakage
  decomposition above. Quote 0.662 for any claim of the form "predicts from
  independent inputs."
- **AQ-C01 — the catchment carrying 96% of discharge — is the weakest fold**
  (0.6096 vs. 0.7474 mean), and that gap is not being tuned away; see above.
- **The catchment-memorisation check does not currently pass.** Random-CV
  scores 0.0455 above LOCO on the shipped configuration — 2.7× the noise
  floor, and the direction LOCO exists to catch. An earlier, different
  configuration passed this check; the current one has not been re-verified
  clean, and which static feature(s) drive the gap is unresolved. LOCO is
  still what's reported, precisely because of this.
- **Sub-daily rainfall is unavailable** over the full record, so it trains on
  daily totals. This is a real loss: intensity drives runoff in a hyper-arid
  catchment, and Oct 2016 ranks 14th by daily total against 8th by peak
  3-hour intensity.
- **Label quality is not uniform.** AQ-C01 gets 41 ERA5 cells, a genuine area
  mean; the other four get one cell each and three are nearest-cell point
  samples with no cell centre inside the polygon. ERA5-Land is ~81 km² per
  cell against catchments of 36–65 km².
- **Only 656 hard negatives exist** — days with measurable rain and little
  runoff, where the boundary is. They cap what can be learned, and more would
  need ERA5 months that are not downloaded.
- **Five catchments is not a sample.** Any pattern across five points could
  be coincidence, and no validation scheme fixes that.
