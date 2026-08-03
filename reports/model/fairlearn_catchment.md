# Fairlearn — catchment as the sensitive feature

**Date:** 4 August 2026 · `scripts/18_fairlearn_catchment_parity.py`
**Model:** configuration `CD-`, 20 features, depth 6 / lr 0.03 / mcw 2.0
**Constraint:** `BoundedGroupLoss(ZeroOneLoss(), upper_bound=b)` via
`ExponentiatedGradient`, sensitive feature `catchment_id`

## What this tests, and what it cannot

Fairlearn constrains performance disparities across **groups**. It is not a
class-imbalance weighting optimiser — imbalance is handled by resampling to 1:4
plus `scale_pos_weight`, and measured (random K-fold 0.514 vs LOCO 0.521).

The disparity being attacked is real: AQ-C01 scores 0.593 against 0.743–0.808
for the others, and it carries 96% of the discharge.

**Structural limit.** Under leave-one-catchment-out the test catchment is unseen,
so the constraint applies only to the four training catchments. It cannot equalise
onto the held-out one directly — it can only make the learned function less
catchment-specific, and whether that transfers is what this measures.

**The failure mode.** A parity constraint can equalise by making the strong folds
worse rather than the weak one better. Spread falls, usefulness does not rise. Hence
per-fold AP alongside the spread.

## Results

| config        |   mean_AP |   C01_AP |   min_AP |   max_AP |   spread |   mean_Brier |
|:--------------|----------:|---------:|---------:|---------:|---------:|-------------:|
| unconstrained |    0.7474 |   0.6096 |   0.6096 |   0.8035 |   0.1939 |       0.0402 |
| bound=0.05    |    0.2335 |   0.116  |   0.0601 |   0.516  |   0.4559 |       0.0639 |
| bound=0.1     |    0.2335 |   0.116  |   0.0601 |   0.516  |   0.4559 |       0.0639 |
| bound=0.2     |    0.2352 |   0.116  |   0.0601 |   0.5247 |   0.4645 |       0.0637 |
| bound=0.4     |    0.2387 |   0.116  |   0.0588 |   0.5434 |   0.4845 |       0.0636 |

### Per fold

**unconstrained**

| fold   |     AP |   Brier |
|:-------|-------:|--------:|
| AQ-C01 | 0.6096 |  0.0765 |
| AQ-C02 | 0.7521 |  0.0446 |
| AQ-C03 | 0.7691 |  0.0298 |
| AQ-C04 | 0.8025 |  0.0247 |
| AQ-C05 | 0.8035 |  0.0255 |

**bound=0.05**

| fold   |     AP |   Brier | note   |
|:-------|-------:|--------:|:-------|
| AQ-C01 | 0.116  |  0.1055 |        |
| AQ-C02 | 0.091  |  0.0834 |        |
| AQ-C03 | 0.3843 |  0.0418 |        |
| AQ-C04 | 0.516  |  0.032  |        |
| AQ-C05 | 0.0601 |  0.0567 |        |

**bound=0.1**

| fold   |     AP |   Brier | note   |
|:-------|-------:|--------:|:-------|
| AQ-C01 | 0.116  |  0.1055 |        |
| AQ-C02 | 0.091  |  0.0834 |        |
| AQ-C03 | 0.3843 |  0.0418 |        |
| AQ-C04 | 0.516  |  0.032  |        |
| AQ-C05 | 0.0601 |  0.0567 |        |

**bound=0.2**

| fold   |     AP |   Brier | note   |
|:-------|-------:|--------:|:-------|
| AQ-C01 | 0.116  |  0.1055 |        |
| AQ-C02 | 0.091  |  0.0834 |        |
| AQ-C03 | 0.3843 |  0.0418 |        |
| AQ-C04 | 0.5247 |  0.0312 |        |
| AQ-C05 | 0.0601 |  0.0567 |        |

**bound=0.4**

| fold   |     AP |   Brier | note   |
|:-------|-------:|--------:|:-------|
| AQ-C01 | 0.116  |  0.1055 |        |
| AQ-C02 | 0.091  |  0.0834 |        |
| AQ-C03 | 0.3843 |  0.0418 |        |
| AQ-C04 | 0.0588 |  0.0557 |        |
| AQ-C05 | 0.5434 |  0.0316 |        |

