# Tuning and model comparison

**Date:** 3 August 2026 · `scripts/16_tune_and_compare.py`
**Data:** 11,810 catchment-days, 928 positive (7.9%)
**Features:** 15 (11 event-varying, 4 static)

## Results — LOCO, average precision

| held_out   |   test_pos |   baseline |   classify |   regress | best     |
|:-----------|-----------:|-----------:|-----------:|----------:|:---------|
| AQ-C01     |        274 |     0.2613 |     0.5573 |    0.5845 | regress  |
| AQ-C02     |        215 |     0.2048 |     0.7643 |    0.7321 | classify |
| AQ-C03     |        158 |     0.1982 |     0.7782 |    0.7237 | classify |
| AQ-C04     |        139 |     0.1716 |     0.8191 |    0.7221 | classify |
| AQ-C05     |        142 |     0.166  |     0.8253 |    0.7348 | classify |

| | mean AP |
|---|---:|
| rule baseline | 0.2004 |
| classify binary | 0.7488 |
| regress log magnitude | 0.6994 |

**regress − classify: -0.0494** · **best − baseline: +0.5485**

## Why regression was tried

The classifier discards the target at the threshold: a day at 0.0021 mm and one
at 0.19 mm get the same label though they are two orders of magnitude apart.
Regressing `log(sro)` keeps that ordering, and the predicted magnitude is then
calibrated to a probability on the same natural-prevalence set — so both models
run through identical splits and identical metrics.

## How the hyperparameters were chosen

**Nested cross-validation.** Inside each outer LOCO fold the four training
catchments are split leave-one-out again, the 12-point grid
is scored on those inner folds, and only the winner is evaluated on the outer
held-out catchment. The outer fold takes no part in the choice.

Tuning against outer LOCO scores would fit hyperparameters to five numbers and
then report the result as generalisation — the same class of error as a leaked
feature, one level up.

Inner folds keep the catchment split rather than shuffling: static features are
constant per catchment, so a random inner split would select parameters that
reward memorisation.

The grid is small on purpose. With six event-varying features and a label that is
itself modelled, this is a signal problem rather than a fitting problem, and a
large grid would mostly buy variance.
