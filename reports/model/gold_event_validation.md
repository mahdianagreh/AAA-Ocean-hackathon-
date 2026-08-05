# Gold-event validation — `imerg_rain` ranker

**Date:** 4 August 2026 · `scripts/24_gold_event_validation.py`

**PARTIAL — 1 of 13 dates known.** This is not a validation run.

The ERA5 runoff target is a rainfall mask (`reports/model/label_autopsy.md`), so
no metric against it means what we said it meant. The only trustworthy reference
is a day sediment is **documented** to have reached the sea. Kalman et al. (2025)
says 13 such days exist since 1994:

> "The flood was the 13th flood recorded since records began in 1994"

13 positives cannot train anything. They validate decisively, because the
null is brutal — see the power table below.

## Where the confirmed events rank

| date | rank of 2,362 | percentile |
|---|---:|---:|
| 2016-10-28 | 20 | 0.85% |



## recall@K

| budget                               |   K |   hits |   of_confirmed |   E[hits] |   lift |     p |
|:-------------------------------------|----:|-------:|---------------:|----------:|-------:|------:|
| literature base rate (13 in 22.8 yr) |   4 |      0 |              1 |     0.022 |    0   | 1     |
| literature daily-probability ceiling |  12 |      0 |              1 |     0.066 |    0   | 1     |
| 1% of days                           |  24 |      1 |              1 |     0.132 |    7.6 | 0.125 |
| 5% of days                           | 118 |      1 |              1 |     0.649 |    1.5 | 0.487 |

`E[hits]` and `p` are computed against the full **13**-event set, not only
the dates we happen to hold — otherwise one lucky confirmed date would read as
significance.

## Power against a random ranker

| budget                               |   K days |   E[hits] by chance |   hits for p<0.05 |   hits for p<0.001 |
|:-------------------------------------|---------:|--------------------:|------------------:|-------------------:|
| literature base rate (13 in 22.8 yr) |        4 |               0.022 |                 1 |                  2 |
| literature daily-probability ceiling |       12 |               0.066 |                 2 |                  3 |
| 1% of days                           |       24 |               0.132 |                 2 |                  3 |
| 5% of days                           |      118 |               0.649 |                 3 |                  5 |

At the literature's own base rate, a random ranker expects **0.016 hits**. Two
hits is p < 0.001. This is why a 13-event gold set is worth chasing even
though it can never train a model.

## Precision is not computed, deliberately

These are floods documented on the ISRAELI side. Our five catchments are Jordanian. A day absent from this list is NOT a confirmed negative - it may be an Aqaba-side flood that nobody recorded. Precision is therefore not computable against this set; recall and rank are.

## What would make this a real validation

12 of 13 dates are still missing, held in:

- **Kalman et al. (2020b)** — 10.1111/sed.12737 — the 1994- flood record behind the 0.17/yr and 1.7/yr rates
- **Katz et al. (2015)** — None — the earlier hyperpycnal plume event, approx 20,000 t

`docs/karam_handoff.md` Request 0. A screenshot of the event table is enough.
