# Data requests to Karam — from Mahdi, 4 August 2026

Component A is trained and validated. **LOCO mean AP 0.741 against a rule baseline
of 0.200** — 9.4× the 7.9% base rate. F1 0.642 at threshold 0.343, precision 0.598,
recall 0.693.

I have run out of things I can improve without you. Everything below is a data
request, ranked by expected gain, with the numbers behind each estimate.

**One thing first, because it blocks two of these: the CDS API key is empty.**
`.env` has `CDSAPI_URL` set and `CDSAPI_KEY=''`, and there is no `~/.cdsapirc`.
The 77 ERA5 months on disk were downloaded by someone with working credentials —
either you hold them, or they were rotated after the `.env` leak in `2f0a6d6`.
Nothing in requests 1 or 2 can start until that is resolved.

---

## What I did with what you gave me

Worth reading before the requests, because it changes what "more data" needs to mean.

Your handoff pointed me at `event_catchment_features.parquet` (500 × 139) joined to
`event_antecedents.parquet` — 390 trainable rows at 99% positive. That set cannot
answer "will there be runoff", because it is the top 100 rainfall days in 27 years:
the question is answered before the model sees it.

**The negatives were already on disk.** ERA5-Land ships whole months and 77 are in
`./raw` — 2,331 calendar days, of which 79 were labelled. The extraction had been
pointed at event days only and walked past **2,252 days of runoff in files it had
already opened.** No download.

| | before | after |
|---|---:|---:|
| rows | 390 | **11,810** |
| positive rate | 99.0% | **7.9%** |
| genuine zero-runoff rows | 4 | 5,048 |

`scripts/13_extract_sro_all_days.py` does it. Two things in there you will want:

**The `-1e-10` deaccumulation tolerance is unreachable on dry months.** The worst
"decrease" is a cumulative value going 2.98e-8 → 0, and 2.98e-8 is exactly 2⁻²⁵ —
one float32 tick, the field flickering between zero and the smallest representable
value. Measured on January 2020: 1,244 of 103,277 increments break −1e-10, **none**
break −1e-7. I used 1e-7, still 58× below the median signal of 5.84e-6 m. It never
fired for you because event months carry real runoff, orders of magnitude above the
quantum. **It fires on every dry month** — which is exactly the data the negative
class needs.

**Also: `tp` trips the same check.** I excluded it since rainfall comes from IMERG,
but you will hit it if you deaccumulate all three fields on non-event months.

---

## Request 0 — two papers, and they outrank everything below

**Added 4 August, after the requests below were written.** This one is new, it is
cheap, and it is worth more than the other three combined.

While trying to fix the sediment side I found that **our label is not the thing we
named it.** Full write-up in `reports/model/label_problem.md`; the short version:

- `corr(sro, ERA5 rainfall) = +0.985` — the label is a near-deterministic function
  of ERA5's own precipitation, while `corr(ERA5, IMERG) = +0.573`. A model
  predicting it is partly learning the ERA5↔IMERG offset, not wadi hydrology.
- **ERA5 largely missed October 2016.** 0.77 mm and p92.6, against IMERG's 9.58 mm
  and p99.5. The one storm with a mooring record and a published sediment mass is
  an ordinary damp day in the product our label comes from.
- **It is a detection failure, not a scaling one.** On days IMERG calls wet
  (> 1 mm), ERA5 is essentially dry on **35%** — and on **20% of the heaviest IMERG
  days in the record.** Where it does see a storm the magnitude is about right
  (ratio 0.99), which is why any "ratio on days both are wet" comparison looks
  reassuring and is worthless.
- **The label inherits the blind spot.** Of the 276 catchment-days where IMERG
  observed > 1 mm and ERA5 saw nothing, `target` is positive on **exactly one** —
  against 51.1% on IMERG-wet days generally. Those are real storms labelled as
  non-events.
- Our label fires on **3.21% of calendar days**. Kalman et al. (2025) put
  sea-reaching floods at **0.156%** — 13 events since 1994, *"less than 0.5% of
  days."* **21× too generous.**
- And your sweep matters more than I thought: a model given **one column of ERA5's
  own rainfall** scores AP **0.9785** against our 20-feature 0.7445. Stripping every
  ERA5-sourced feature drops us to **0.6623**. The whole modelling difficulty was
  the ERA5↔IMERG mismatch, not hydrology.

The fix needs the dates of those 13 floods, and they are in two papers we do not
have:

| source | what it holds | identifier |
|---|---|---|
| **Kalman et al. 2020b** | the 1994– flood record behind the 0.17/yr and 1.7/yr rates | *Sedimentology* 67, 3152–3166 · `10.1111/sed.12737` |
| **Katz et al. 2015** | the earlier hyperpycnal event, ≈20,000 t | cited in Kalman 2025 as Katz et al., 2015a/b |

**What I need:** the dated event list — any table, figure or supplementary file
giving *when* each of the 13 floods reached the sea. A screenshot of the table is
enough. If the PDFs are paywalled, HTU library access or an author email
(`akoss.kalman@gmail.com`, listed on the 2025 preprint) both work.

**Why it beats Requests 1–3.** Those three make Component A better at predicting an
ERA5 quantity. This one tells us whether that quantity is the right target at all.
Thirteen dated events cannot *train* a classifier across five catchments — but they
can **validate** one, which is the claim the demo actually needs to make. Right now
we have exactly one event to check against, and it is the anchor itself, so nothing
is independent.

---

## Request 1 — the 120 missing wet-season ERA5 months

**Expected gain: the largest available to me. This is the ask that matters most.**

| | |
|---|---:|
| wet-season months, 1998–2025 (Oct–Apr) | 193 |
| on disk | 73 |
| **missing** | **120** |

### Why it matters more than the row count suggests

The binding constraint on the model is not rows, it is **hard negatives** — days
with measurable rain that produced little runoff. They are where the decision
boundary lives.

| | count |
|---|---:|
| positives | 928 |
| **hard negatives** | **656** |
| easy negatives (dry) | 10,226 |

There are **fewer hard negatives than positives.** I proposed sampling negatives
1:4 with an even hard/easy split and it is arithmetically impossible: a fold needing
1,300 hard negatives has ~510 available, so the achievable mix is 16–21% hard. Every
additional wet-season month adds ~28 days, a handful of which are genuinely
ambiguous. This is the only cheap source of them.

### What to request

Same as the months already on disk — hourly, whole calendar months, seven variables
(`swvl1`, `tp`, `u10`, `v10`, `t2m`, `sro`, `ssro`), `TERRAIN_AOI`. Your
`sweep_era5_land_events.py` and `run_era5_sweep.sh` already do this; the change is
the month list, from event months to all wet-season months.

Land them in `raw/era5_land/events/<year>/` with the existing filename convention
(`era5_land_YYYYMM01T0000_YYYYMMDDT2300.nc`) and my extraction picks them up with
no code change.

**Cost:** ~1 MB per month, so ~120 MB. The bottleneck is CDS queue time, not
bandwidth — hours, unattended.

---

## Request 2 — sub-daily rainfall over the full record

**Expected gain: larger than everything else combined. Also the most expensive.**

The model trains on **daily totals**. In a hyper-arid catchment, intensity generates
runoff, not depth — a day delivering 6 mm in one hour and a day delivering 6 mm over
twelve hours are physically different events and currently **identical** to the model.

Your own ranking is the evidence: **October 2016 is 14th of 100 by daily total and
8th of 83 by peak 3-hour intensity.** You wrote that the event mattered because it
was intense on a dry catchment rather than large. The model cannot see that
distinction at all.

`rain_1h_mm`, `rain_3h_mm`, `rain_6h_mm`, `rain_24h_mm` exist in
`catchment_rainfall_daily.parquet` but are **NaN on all 11,810 rows** — the
half-hourly sweep covered event windows, not 27 years. I dropped them rather than
hand the model four dead columns.

**What I need:** `rain_3h_mm` — peak 3-hour accumulation per catchment-day — over as
much of 1998–2025 as is affordable. If the full record is too expensive, a targeted
subset is still worth having: **412 days have ≥0.5 mm somewhere, 243 have ≥1 mm.**
Sub-daily intensity on those 412 days would cover every day that could plausibly
produce runoff, at a fraction of the cost of the full 10,135.

That is the single highest-value item on this page.

---

## Request 3 — lower the event threshold in the catalogue

**Expected gain: moderate. Cheapest of the three.**

You noted this yourself. The catalogue is the top 100 storms, cut at 3.26 mm daily.
The full record holds far more:

| threshold | days |
|---|---:|
| ≥ 0.5 mm anywhere | **412** |
| ≥ 1 mm | 243 |
| ≥ 3 mm | 86 |

Your estimate was 250–300 storms after merging, roughly 3× current. You also said the
added 1–3 mm events "mostly produce no runoff, which would actually *help*" — that is
exactly right, and it is the same argument as Request 1 from the other direction.

This only matters if the labels come with it, so it pairs with Request 1 rather than
substituting for it.

---

## Not a request, but you should know

**Two leaks I found and removed**, both of which produced a *better*-looking result
than the truth. Flagging them because the same shapes could recur in your pipeline.

**Same-day soil moisture.** A daily mean, so it rises as the day's rain infiltrates —
contemporaneous with the target, not antecedent.

```
soil_moisture       (same day)  r = +0.384
soil_moisture_lag1d             r = +0.059
soil_moisture_lag3d             r = +0.015
```

It was the top driver at 2.21 mean |SHAP| against rainfall's 0.44, and LOCO AP read
**0.836**. Exactly the failure you warned me about: it does not look like a bug, it
looks like an excellent result.

**A broken baseline.** SCS initial abstraction at the textbook `0.2·S` puts Ia at
12.7–20.4 mm, while Aqaba's *maximum* daily rainfall in 27 years is 21.6 mm and the
p99 is 6.9 mm. Q came out zero on 11,798 of 11,810 rows — a constant, whose average
precision is just the base rate. "The model beat the baseline by +0.75" was comparing
against nothing. Ia ratio is now 0.05, the documented arid value, and the baseline
scores 0.200.

**Your leakage check passed.** Random K-fold AP 0.514 against LOCO 0.521 — a gap of
−0.008, so the model is not memorising catchment identity. Reporting both, as you
suggested, is a stronger result than either alone.

**Your DoD item 3 answer is in the model card**, cited as you gave it: not held,
14th by daily total, 8th by peak 3-hour intensity.

**Run-to-run variance is ±0.017 AP** from feature column ordering alone. Any
improvement below ~0.03 cannot be distinguished from noise on five folds. Worth
knowing before either of us reports a small delta as real.

**Fairlearn was tried and abandoned.** With `ZeroOneLoss` at 7.9% prevalence, a
group-parity constraint is trivially satisfied by predicting the majority class
everywhere — mean AP collapsed to 0.234 and two folds landed exactly on their base
rate. Not a tuning problem; the tool is a mismatch. Written up in
`reports/model/fairlearn_catchment.md`.

---

## Summary

| # | Request | Blocked on | Gain |
|---|---|---|---|
| **0** | **Dated flood list from Kalman 2020b + Katz 2015** | **nothing — library access** | **decisive** |
| 1 | 120 wet-season ERA5 months | **CDS key** | large |
| 2 | `rain_3h_mm` over the record (or the 412 wet days) | your sweep | largest of 1–3 |
| 3 | Lower catalogue threshold to ≥0.5 mm | nothing | moderate |

If only one is possible, **make it Request 0.** Requests 1–3 make the model better at
predicting an ERA5 quantity; Request 0 tells us whether that quantity is the right
target. Of the remaining three, Request 2 is the strongest — intensity is the physical
driver of arid runoff and the model is currently blind to it.

What I am doing meanwhile, neither of which needs you: repeated-seed evaluation so we
stop chasing noise, and a classifier–regressor ensemble aimed at AQ-C01, which is the
weakest fold at 0.593 and carries 96% of the discharge.
