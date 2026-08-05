# Ablation sweep — all combinations

**Date:** 4 August 2026 · `scripts/17_ablation_sweep.py`
**Data:** 11,810 catchment-days, 928 positive (7.9%)
**Hyperparameters:** fixed at depth 6 / lr 0.03 / min_child_weight 2.0 — the values
nested CV chose in `16_tune_and_compare.py`, held constant so the comparison isolates
the features rather than confounding them with tuning.

Codes: **C** = climatology-normalised rainfall · **D** = consecutive dry days ·
**W** = label-quality weights.

## Results

| combo   |   n_feat |   mean_AP |   C01_AP |   pooled_AP |   best_F1 |   precision |   recall |   threshold |   mean_Brier |
|:--------|---------:|----------:|---------:|------------:|----------:|------------:|---------:|------------:|-------------:|
| CD-     |       20 |    0.7414 |   0.5931 |      0.6817 |    0.6417 |      0.5976 |   0.6929 |      0.3425 |       0.0403 |
| -D-     |       16 |    0.7397 |   0.5662 |      0.6648 |    0.6265 |      0.5957 |   0.6606 |      0.3732 |       0.0416 |
| C--     |       19 |    0.7359 |   0.587  |      0.6693 |    0.6238 |      0.5883 |   0.6638 |      0.3493 |       0.0412 |
| ---     |       15 |    0.7358 |   0.5531 |      0.6516 |    0.6199 |      0.5831 |   0.6616 |      0.3699 |       0.0427 |
| --W     |       15 |    0.7265 |   0.5438 |      0.6416 |    0.6073 |      0.5751 |   0.6433 |      0.3661 |       0.0433 |
| -DW     |       16 |    0.7262 |   0.5566 |      0.6453 |    0.6136 |      0.5473 |   0.6983 |      0.325  |       0.043  |
| CDW     |       20 |    0.7252 |   0.5755 |      0.6609 |    0.6235 |      0.5719 |   0.6853 |      0.3198 |       0.0417 |
| C-W     |       19 |    0.7236 |   0.5797 |      0.6564 |    0.6151 |      0.5796 |   0.6552 |      0.3359 |       0.0421 |

Rule baseline mean AP: **0.2004**

## Best

| | combo | mean AP | AQ-C01 AP |
|---|---|---:|---:|
| by mean AP | `CD-` | 0.7414 | 0.5931 |
| by AQ-C01 AP | `CD-` | 0.7414 | 0.5931 |

**AQ-C01 is reported separately on purpose.** It carries 96% of the discharge and is
the hardest fold — train on four small catchments, predict the 4,453 km² one. A
combination that raises the mean while lowering C01 is not an improvement for this
project.

### Per fold, best combination

| fold   |     AP |   Brier |
|:-------|-------:|--------:|
| AQ-C01 | 0.5931 |  0.0763 |
| AQ-C02 | 0.7432 |  0.045  |
| AQ-C03 | 0.7675 |  0.0301 |
| AQ-C04 | 0.7959 |  0.0249 |
| AQ-C05 | 0.8076 |  0.0252 |

## What each addition is

**C · climatology normalisation.** LOCO's difficulty is transfer to an unseen
catchment, and absolute millimetres do not transfer — 6 mm on 4,453 km² is not 6 mm
on 36 km². A position in the catchment's own wet-day distribution does.

**D · consecutive dry days.** Arid soil crusts when it bakes, and a crust sheds water
rather than absorbing it, which is why dry antecedent conditions *raise* runoff.
`soil_moisture_lag1d` captures wetness but not the duration of dryness that forms the
crust. Counted strictly before the day, so no same-day leak.

**W · label-quality weights.** AQ-C01's label is a 41-cell ERA5 area mean; the other
four are single cells, three of them nearest-cell point samples with no cell centre
inside the catchment. ERA5-Land is ~81 km² per cell against catchments of 36–65 km².
Weights 1.0 / 0.75 / 0.5 accordingly.

## Not included: more ERA5 months

77 of the ~193 wet-season months for 1998–2025 are on disk, so **120 are missing**.
Each CDS request queues independently, making this a background job measured in hours
rather than something that fits in a sweep. It is the one remaining cheap source of
hard negatives — 656 exist, and they are the binding constraint on the boundary.
