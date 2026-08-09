# Model card — ReefShield Aqaba

**Last updated:** 2026-08-06 · Part of the `/ask` corpus, so anything written here is
answerable live and must be defensible live.

This card covers the components that turn data into a displayed number. It is
organised by owner, because a model card that blurs who verified what is not much
use when a judge asks.

Component letters are the ones fixed in
[`tasks/phase2/00-phase2-plan.md`](../tasks/phase2/00-phase2-plan.md) §"What is
actually machine-learned" — **A** runoff classifier, **B** sediment proxy, **C**
plume transport, **D** exposure score, **E** LLM layer. **A is the only trained
model.**

| Component | What it does | Owner | State |
|---|---|---|---|
| **D · Exposure engine** | plume + sediment → per-zone risk score | Pulga | **implemented, tested** |
| **E · Explanation** | risk state → grounded bilingual paragraph | Pulga | **implemented, tested** |
| **E · Retrieval (`/ask`)** | technical corpus → cited answers | Pulga | **implemented, tested** |
| **A · Runoff classifier** | rainfall + catchment features → runoff probability | Mahdi | **implemented, LOCO-validated** |
| **C · Plume transport** | outlet discharge → probability contours | Abd | **implemented, wired live** — near-shore current-grid masking limits realism at the demo outlets, see below |

The section for C is deliberately short — that owner should fill it in, and writing
confident text about someone else's model would be exactly the kind of unearned
claim this card exists to avoid.

---

## D · Exposure engine

### What it computes

```text
Exposure = plume_probability
         × relative_sediment_intensity
         × exposure_duration_weight
         × habitat_sensitivity_weight     (= 1.0, placeholder)
         × confidence_adjustment

risk_score = min(100, Exposure × 100)
```

Implementation: [`backend/src/exposure/engine.py`](../backend/src/exposure/engine.py).

### Why ×100 and not some other scaling

Every factor is already dimensionless on [0, 1], so their product is on [0, 1] and
×100 maps it onto the 0–100 risk bands with **no reshaping at all**. No exponent, no
logistic, no normalisation against observed events.

That restraint is the point. Any curve we invented here would change the *ranking*
between reef zones while looking like a presentation detail, and we have no
validation data to justify one curve over another. `score_scale` is stored in
`formula_terms` on every run so the multiplication is auditable rather than implied.

**Consequence, stated plainly:** because five factors on [0, 1] multiply, scores
cluster low. A zone with 0.8 plume probability, 0.5 sediment intensity, 0.875
duration and 0.6 confidence scores 21 — "low" — despite being squarely in the
plume's path. The bands are calibrated for a product of five uncertain terms, not
for intuition, and **operational thresholds require marine-scientist input.**

### Inputs and where each comes from

| Term | Range | Source | Kind |
|---|---|---|---|
| `plume_probability` | 0–1 | Abd's contoured particle field | derived |
| `relative_sediment_intensity` | 0–1 | Mahdi's anchored sediment index, normalised | derived (real for AQ-2016-10-28/AQ-C01, the only event/catchment with a training-set feature row today; placeholder 0.5 otherwise) |
| `exposure_duration_weight` | 0–1 | span of contour timestamps ÷ horizon | derived |
| `habitat_sensitivity_weight` | 1.0 | **team placeholder** | **assumed** |
| `confidence_adjustment` | 0–1 | GEFS ensemble spread | derived (stub today) |

### Risk bands

0–20 minimal · 20–40 low · 40–60 moderate · 60–80 high · 80–100 critical
(concept §14.5). A reasonable default, **not validated policy.** Every API response
carrying `risk_level` also carries a caveat saying so.

### What the engine refuses to do

These are asserted, not conventions:

- **A missing input raises.** `None` or `NaN` in any factor is a `ValueError`, never
  a silent zero. A gap is reported as a gap.
- **An out-of-range input raises.** No clamping — clamping a 1.4 probability to 1.0
  would hide an upstream bug behind a plausible score.
- **An unreached zone returns `None`, not a 0 score.** "The plume never got here" and
  "the plume got here and the risk is zero" are different statements.
- **Areas and distances are computed only in EPSG:32636.** `_assert_measure_crs`
  rejects any other frame. This workstream shipped a 14.8% error from measuring in
  EPSG:3857 once; the guard exists so it cannot recur at a higher-stakes layer.

### Auditability

Every run persists `formula_terms` for every zone —
[`backend/src/exposure/store.py`](../backend/src/exposure/store.py). The store
**refuses** a result whose `formula_terms` is empty. Stored alongside: the five
factors, `raw_score`, `score_scale`, `risk_score`, `risk_level`, the sensitivity
placeholder status, `zone_fraction_affected`, the arrival window, the contour
timestamps actually hit, and `measure_crs`.

So "why is R-04 at 81?" is a database lookup, not a re-derivation.

### Verification

[`tests/test_exposure_engine.py`](../tests/test_exposure_engine.py), 12 checks,
including the two cross-checks the plan requires by name:

1. **Circular-buffer baseline.** Three zones at 500 m / 1500 m / 3000 m from one
   outlet under growing contours. Scores must fall and arrival times must rise with
   distance: measured **33.75 → 17.5 → 5.0** and **3 h → 6 h → 12 h**. A structural
   error in the overlay would break the monotonicity.
2. **Hand-computed spot check.** One score worked out by hand against the engine's,
   agreeing to **< 1e-12**.

### Known limitations

1. **`habitat_sensitivity_weight` is 1.0 for every zone** — a placeholder labelled
   `PLACEHOLDER_PENDING_MARINE_SCIENTIST` in the data file, the API schema, and every
   response. Allen Coral Atlas maps habitat, not sensitivity.
2. **Reef zone area is real geometry, but covers optically shallow reef only.**
   Corrected 2026-08-03: the outline is now Allen Coral Atlas v2.0's own 5 m benthic
   polygons — **1.235 km² across the 8 zones**, not the 5.69 km² the earlier
   hand-drawn 250 m strips claimed, a 4.6× difference that also reordered the
   per-zone ranking. An absolute km² is therefore defensible now. Exposure is still
   reported as `zone_fraction_affected` rather than an absolute area, but for a
   different reason: the Atlas maps optically shallow reef, so anything below the
   depth its imagery penetrates is outside the mapped zone and outside the fraction.
   *Anything computed against the provisional areas is an overestimate, not merely
   imprecise.*
3. **No validation against an observed exposure outcome.** Nobody has measured what
   sediment actually reached which reef in 2013 or 2016, so the engine is internally
   consistent and physically plausible, not empirically calibrated.
4. **`exposure_duration_weight` is only as fine as the contour timestamps.** With one
   snapshot it falls back to a single time step rather than collapsing to zero, which
   is documented in the code and visible in `formula_terms`.

---

## E · Explanation endpoint

Implementation: [`backend/src/rag/explain.py`](../backend/src/rag/explain.py).

### The rule

**The generator phrases numbers it is handed. It never computes, rounds, or invents
one.** If the phrasing layer can change a score, the system stops being auditable.

### How that is guaranteed rather than hoped for

The shipped generator is a **deterministic template**, not a language model. There is
no API key, no temperature, no sampling. `_num()` renders the value it was given and
drops only a trailing `.0`, because "72.0%" and "72%" are the same number.

One subtlety worth recording. Converting a probability to a percent by
`probability * 100` is *not* safe here: in IEEE-754, `0.0725 * 100` is
`7.249999999999999`, and since the rule forbids rounding that away it would render on
screen verbatim. `to_percent()` therefore shifts the decimal representation exactly
(`Decimal(str(p)) * 100`), giving `7.25`. No digit the caller supplied is altered —
the fix was to avoid introducing the artefact rather than to round it off.

`generate_with_llm` exists as a hook and raises `NotImplementedError`. If it is ever
enabled, the number-fidelity test applies to it too.

### Verification

[`tests/test_explain_fidelity.py`](../tests/test_explain_fidelity.py) — 27 checks.
For **both** languages, every number in `source_numbers` must appear verbatim in the
returned text, including adversarial values (`71.8`, `0.0725`, `99.95`) chosen because
they are what a rounding bug would mangle. English and Arabic are asserted to carry
**identical numbers** for the same input; only the prose changes.

### Known limitations

1. **Template coverage is finite.** Seven SHAP driver features have curated clauses;
   an unrecognised feature falls back to its raw name rather than being dropped,
   because a driver we cannot phrase is still a driver.
2. **Arabic is a translation of the frame, not of the sources.** The corpus is
   English; an Arabic answer quotes English excerpts. See `docs/rag_limitations.md`.

---

## E · Retrieval (`/ask`)

Implementation: [`backend/src/rag/index.py`](../backend/src/rag/index.py),
[`corpus.py`](../backend/src/rag/corpus.py), [`answer.py`](../backend/src/rag/answer.py).

### Design

Local **BM25 lexical retrieval**. No external embedding service, deliberately:

1. Citations must be exact — lexical retrieval returns the literal chunk it scored,
   so an excerpt is verbatim source text and can be checked character-for-character.
2. It is deterministic and offline — same question, same citations, on conference
   wifi with no API key.
3. It has no failure mode that produces a confident answer from nothing.

Answers are **composed from the retrieved excerpts by quotation**, so an uncited
answer is structurally impossible: no chunks means nothing to quote, and the endpoint
returns the honest refusal in the language asked.

### Corpus

An explicit allowlist of 13 files, never a glob. `docs/ali/*` (market and analogue
research) and `docs/schema_proposals/*` are excluded, and exclusion is enforced in
`resolve()` independently of the list — a recursive glob would pick them up silently,
and an answer about reef exposure citing a market-sizing document would be actively
misleading.

Missing corpus files are **reported**, not silently skipped, so a renamed doc cannot
quietly shrink what `/ask` can answer.

### Verification

[`tests/test_ask_citations.py`](../tests/test_ask_citations.py) — 16 checks: every
answer carries ≥1 citation; every citation names a file that exists on disk; every
excerpt is verbatim; nothing under `docs/ali/` is ever retrieved; an unanswerable
question refuses rather than confabulates.

### Known limitations

1. **Lexical retrieval misses paraphrase.** `SYNONYMS` bridges the vocabulary gap for
   terms this corpus actually uses; a question phrased entirely outside that
   vocabulary will retrieve nothing and get the refusal.
2. **Answers quote; they do not synthesise.** Ask "why is sensitivity 1.0" and you
   get the passages that say so, not a rewritten essay. That is the intended
   trade-off.
3. **A disqualifying scope word used to not disqualify — fixed 2026-08-05.**
   `min_term_coverage` (0.4, `index.py:233`) was built to reject a question whose
   only shared word is unrelated — the retired "airspeed velocity of an unladen
   swallow" control, which matched a chunk about ocean current *velocity*. It had
   no way to weigh one scope-narrowing term against several genuinely-matching
   ones: a question naming a neighbouring country (the same three this corpus's
   own `reef_scope_is_jordan()` caveat names as deliberately excluded water — see
   `docs/data_dictionary.md` §4) could match on unrelated shared words like
   "reef"/"sensitivity"/"weight" and answer with Jordan-only figures as if the
   country qualifier had been satisfied rather than contradicted, because overall
   coverage stayed comfortably above 0.4 on the other terms alone.
   `index._SCOPE_EXCLUSIVE_TERMS` closes this specifically: those three country
   names are treated as disqualifying rather than merely additive — a chunk that
   does not itself name the same country is rejected outright, regardless of its
   score on everything else. Deliberately excludes the flood's own event name
   (a neighbouring city, not a country), which is legitimate corpus vocabulary,
   not a scope boundary.
   *A documentation note on how this was found: an earlier version of this very
   entry quoted the disqualifying country name inside a worked example, which put
   that word into the indexed corpus and made the exact repro question
   self-answering — a chunk `_SCOPE_EXCLUSIVE_TERMS` would have to be able to
   contain the disqualifying term for the fix's own rule to let it through. Same
   class of contamination as the retired swallow control. This paragraph
   deliberately does not spell the three country names out for that reason.*

---

## A · Runoff risk classifier — Mahdi

Wired behind `POST /api/v1/runoff/predict`, which serves the **real model when a
trained artifact is registered** in `data/models/model_versions.jsonl`, and falls
back to the typed stub — `is_stub: true` plus a `critical` caveat — only when
nothing is. Consumes `landcover_by_catchment.parquet`, `soil_by_catchment.parquet`,
`urban_by_catchment.parquet`.

**Registered as:** `runoff_weighted_gbm_dc5c1b7_20260805T084212Z` · **Data:**
`training_set_full.parquet` — 11,810 catchment-days, 1998–2022 · **Positive:**
`sro > 0.002 mm/day` — 928 rows (7.9%) · **Features:** 20, configuration `CD-`

### The target is a threshold, and it is not "reached the sea"

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

### How much of the score is leakage, decomposed

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
leakage, at 5× the ±0.017 noise floor. Confirmed independently by SHAP on the
shipped model: `wind_direction_deg` and `temp_c` rank 2nd and 3rd by mean
|SHAP|, immediately behind rainfall.

**Quote 0.662, not 0.7445/0.7474, for "predicts runoff from inputs
independent of the label's own atmosphere."** The higher, shipped number is
real and reproducible, but part of it is the model partially reconstructing
ERA5's own weather state rather than learning wadi hydrology.

### Imbalance: two problems, two fixes

At 7.9% positive, `min_child_weight` is a floor on the sum of
hessians in a leaf, and h = p(1−p):

```
base rate 7.9% · h = 0.0724 · a leaf needs ~55 positives to clear min_child_weight=4
base rate 20.0% · h = 0.1600 · a leaf needs ~25 positives to clear min_child_weight=4
```

A leaf needs ~55 positives before it may exist. With 928 positives
across 20 features and 5 catchments, predictive regions holding fewer get
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

### Results — LOCO, all five folds (measured 5 Aug 2026)

| held_out | test_rows | test_pos_rate | baseline AP | **gbm AP** | ROC_AUC | Brier |
|:---|---:|---:|---:|---:|---:|---:|
| **AQ-C01** | 2,362 | 11.60% | 0.2613 | **0.6096** | 0.8938 | 0.0765 |
| AQ-C02 | 2,362 | 9.10% | 0.2048 | 0.7521 | 0.9331 | 0.0446 |
| AQ-C03 | 2,362 | 6.69% | 0.1982 | 0.7691 | 0.9683 | 0.0298 |
| AQ-C04 | 2,362 | 5.88% | 0.1716 | 0.8025 | 0.9639 | 0.0247 |
| AQ-C05 | 2,362 | 6.01% | 0.1660 | 0.8035 | 0.9675 | 0.0255 |

**mean AP: baseline 0.2004 · gbm 0.7474 · delta +0.5470**
F1 0.6388 @ threshold 0.3872 · precision 0.628 · recall 0.650

This supersedes an earlier, pre-CD- measurement (10 features, mean AP 0.5213)
that circulated in an earlier version of this card — that configuration is no
longer what's registered or served.

#### AQ-C01 is the fold that matters, and it is the weakest one

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

#### Leakage, measured by split design — an open finding, not yet resolved

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

### Temporal holdout — train ≤2014, test ≥2015 (measured 6 Aug 2026, `scripts/19`)

Now computed by `scripts/19_train_production_model.py` and recorded in
`model_versions.jsonl["metrics"]` as `temporal_holdout_AP` and
`temporal_holdout_anchor_check` — not just narrative in this card. This is a
different claim from the calibration slice above: that slice only shows the
*calibrator* hasn't seen the test rows; this shows the *classifier's* training
data ends before 2015, full stop — which is what licenses a claim of the form
"the model never saw this storm during training."

| | rows | positive rate |
|---|---:|---:|
| train (≤2014) | 6,300 | 8.0% |
| test (≥2015) | 5,510 | 7.7% |

**Pooled AP 0.5923** vs. baseline 0.2083 · ROC_AUC 0.9158 · Brier 0.0482.

**The headline claim, measured rather than assumed:** trained only on data
through 2014 — October 2016 genuinely unseen — the model's predicted
probability for AQ-C01 on the canonical anchor date, **`AQ-2016-10-28`**,
ranks **76th of 1,102** held-out AQ-C01 catchment-days from 2015–2022
(**93.1st percentile**). (An earlier check against 2016-10-27 — the day
IMERG recorded the storm's peak rainfall, one day before the ID's date —
found 57th/94.83rd; this version deliberately checks the *documented* event
ID rather than whichever nearby day ranks best, which is the more defensible
number to quote even though it is very slightly lower.) This is not "the
highest in 26 years" — that framing overstated what a temporal holdout of
2015–2022 can show — but it is a genuine, falsifiable result: the storm that
produced the one documented major sediment event lands in the top 5% of
years the model never trained on, for the one catchment that carries 96% of
discharge.

### Calibration on the held-out catchment

|   n |   predicted |   observed |
|----:|------------:|-----------:|
| 473 |   0.0208342 |  0.0295983 |
| 472 |   0.0464708 |  0.0508475 |
| 472 |   0.0782161 |  0.0529661 |
| 472 |   0.131152  |  0.101695  |
| 473 |   0.288471  |  0.344609  |

Predicted against observed. A calibrated model tracks the two columns together.
**Not yet regenerated against the CD- configuration** — this table predates
the 20-feature model above and should be treated as illustrative of the
calibration *method*, not as this model's own numbers.

### Feature importance (SHAP, shipped model, mean |value| over all rows)

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

### Per-prediction attributions (`feature_attributions`) — confirmed 6 Aug 2026

`predict_one()` returns real TreeSHAP values per request, e.g. for the anchor storm:
`rain_self_percentile +0.996`, `rain_over_p90 +0.774`, `precip_prior_1d_mm +0.602`,
`precip_prior_3d_mm -0.513` — a coherent story for that day. `feature_attributions_status`
is `None` on success and an error string when TreeSHAP itself fails (`shap` not
installed); the caller renders "drivers unavailable" from the status, never a chart of
zeros, since a zero-SHAP bar reads as "the model says none of these matter."

**`status: None` does not mean the attributions are meaningful.** A request built from
a couple of scenario fields (e.g. `rainfall_mm_3h`) rather than a full row from
`da.training_row()` never actually reaches the model's 20 real features — every one is
NaN — and TreeSHAP runs cleanly on that anyway, returning a fixed set of "drivers"
identical across every catchment tested. `feature_attributions_status` cannot
distinguish this from a real explanation, because SHAP did not fail. Full write-up:
`docs/HANDOFF_pulga_2026-08-06.md`. **Only wire a driver chart to `feature_attributions`
when the request came from `da.training_row()`** — never from a hand-built scenario
request.

### What this model cannot do

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

---

## B · Sediment-load proxy — Mahdi

**A formula, not a model.** Nothing in `backend/src/models/sediment_proxy.py` is
fitted; every term is either a physical quantity or an explicit, documented
assumption.

```text
sediment_index = bare_fraction × slope_term(θ) × erodibility(clay, sand, silt, soc)
                × Q × drainage_density × (1 − transmission_loss)
```

`Q` (runoff volume) comes from `RuleBaseline.runoff_depth()` — a curve-number
formula driven directly by IMERG rainfall, never fit to any label. `scripts/26`
found this is the only runoff input that ranks the one documented sediment
event (Oct 2016, ≈24,400 t) near the top of 27 years (12th of 2,362 days); both
ERA5-derived alternatives fail (176th, 193rd) because they inherit ERA5's
underestimate of that storm.

Anchored on that one measurement via a sidecar file
(`data/models/sediment_anchor.json`, written by
`scripts/27_anchor_sediment_proxy.py`) rather than baked into the trained
artifact — `k` is a calibration constant, not a learned parameter, and the
sidecar is re-verified against a drift check every time the model loads.
Confirmed live against the running API 6 Aug: `relative_sediment_intensity:
0.084`, `sediment_class: High` for the anchor event, non-zero for the first
time in the project.

### Transmission loss — the biggest un-measured assumption, and its bounds

`transmission_loss` (τ) is the fraction of a flood's water — and the sediment
it carries — that soaks into the dry wadi streambed before ever reaching the
coast. Nobody has measured this for Aqaba's wadis directly, so it is an
explicit, exposed parameter rather than a silent zero (the pipeline's
implicit assumption before this module existed, which is the most optimistic
value available and certainly wrong).

| range | value | use |
|---|---|---|
| `TAU_LITERATURE` | 13.2%–98% | full range across arid catchments generally — includes environments nothing like Aqaba |
| **`TAU_NEGEV`** | **20%–85%** | **the closest studied desert analog — bound any UI slider to this** |
| `TAU_DEFAULT` | 52.5% | the Negev midpoint; nearest documented setting, not a local measurement |

**Wired as a request parameter** (Pulga, A3.4): `transmission_loss_override`
(`schemas.py`, bounded `[0.20, 0.85]` — the Negev range, not the wider literature
range) threads through to `SedimentProxy.with_transmission_loss(tau)`. Full
write-up: `docs/HANDOFF_transmission_loss_2026-08-06.md`.

**A learned, per-catchment alternative was tested and rejected (8 Aug).**
`transmission_loss_basis: "learned" | "negev_proxy"` (Phase 5, B2) ships
unconditionally as `"negev_proxy"` — not because no data existed, but because
real data was found (Cataldo et al. 2010, 12 real systems, 58 usable storm
events with a genuine 0-1 fractional loss derived from the paper's own
regression equations) and a learned model built against it scored **worse than
predicting the mean** under leave-one-system-out validation, for every feature
combination tried. Transmission loss is dominated by storm-to-storm dynamics
this dataset doesn't capture, not by static catchment characteristics. Full
result: `tasks/mahdis-features-handoff/RESULT_b2_learned_model_tested_and_rejected.md`,
reproducible via `scripts/31_test_learned_transmission_loss.py`.

### What this formula cannot do

- **One measurement anchors the scale, not the shape.** The formula has six
  terms and a single documented mass constrains one degree of freedom, so any
  tonnage for a different event is an extrapolation along an unverified
  curve. Relative classes (`Low`/`Medium`/`High`/`Extreme`) are the honest
  output. **Verified 6 Aug (Phase 4 task 5):** no API path emits a tonnage
  figure for any event, anchor or otherwise — only `sediment_index`
  (unbounded, unitless) and `sediment_class`. UI copy for Ali:
  `docs/HANDOFF_ali_2026-08-06_tonnage.md`.
- **Two of six terms are currently inert.** `training_set_full.parquet` has
  no `bare_fraction`/soil-texture columns, so the bare-fraction and
  erodibility terms fall back to the same default for every catchment — the
  formula does not yet differentiate catchments by surface type, only by
  slope, drainage density, area, and `Q`.
- **τ is a literature analog, not a local measurement**, and is reported with
  its range attached for exactly that reason.

---

## C · Plume transport (particle engine) — Abd

**Wired and live as of 6 Aug 2026** (`0de8c26`; confirmed live against `main` `6de325c`
during the Phase 4 audit closeout — the API previously stubbed this route, and that is
no longer true, independently confirmed by both Abd and Karam). `POST
/api/v1/plume/simulate` calls the real engine at
`backend/src/models/particle_engine.py` unconditionally and always returns
`is_stub: false`; `POST /api/v1/exposure/calculate` reuses the same run.
`plume_source: REAL_PARTICLE_ENGINE`, and `model_versions.particle_engine` names the
calibrated build (`custom_2d-calibrated-AQ-2016-10-28`), not `stub-0.1`. Consumes
`depth_utm36n.tif` and `coastline.gpkg`.

**Physics.** A 2D probabilistic particle cloud (deliberately not a hydrodynamic
model — concept doc §25 names "team overbuilds full physics" as a risk to avoid).
Every active particle steps forward each `time_step_minutes` as:

```
position(t+1) = position(t)
    + current-driven advection         [current_fn(lon, lat, t, depth)]
    + windage x wind                   [wind_fn x windage_fraction x regime multiplier]
    + stochastic horizontal diffusion  [N(0, sqrt(2 x diffusion_m2_s x dt)) per axis]
    + settling / deposition            [probabilistic, depth-scaled]
    + reflection off the coastline     [rejected step + probabilistic beaching]
```

`transport_regime` (`hypopycnal`/`hyperpycnal`) toggles two things at once, per Katz et
al. (2015): hyperpycnal (bottom-hugging) flow zeroes the windage multiplier (decoupled
from wind-driven surface drift) and treats the particle as already near the bed for
settling purposes. Contours are peak-normalized kernel-density levels of the particle
cloud at each requested timestep (`kernel_density_contours`) — a **relative density**,
explicitly not a calibrated arrival probability.

**Currents.** `AQ-2016-10-28` consults a real, offline-cached HYCOM `GLBu0.08/expt_91.2`
historical archive (`_current_fn_for_event` in `main.py`) — not a synthetic stand-in.
Any other `event_id` with no cached archive falls back honestly to
`ConstantCurrentField(0, 0)`; `caveats.particle_engine_forcing()` states which of the
two was used on every single response, so a caller never has to guess.

**Say this precisely, not more than this:** "consults a real archive" is not the same
claim as "visibly advects on it," and for this project's own outlets it usually is not
the same result. At `AQ-O01` **and** `AQ-O02` — the second is the outlet this card's own
live-verification evidence uses — the ~9 km HYCOM cell under the release point reads
NaN u/v (masked as land), so `simulate()` correctly falls back to zero current there per
its documented `nan_to_num` rule. Measured directly: tracking that `AQ-O02` run's
contour centroids across all six reported timesteps shows **no coherent directional
drift** — displacement from the release point wobbles non-monotonically within roughly
100 m at every density level, the signature of a random walk (diffusion), not of
current-driven advection. The response is honest about this (see the `contours` caveat
quoted in `docs/HANDOFF_abd_2026-08-06.md` §2.5) — the point here is that a reader of
just the headline numbers (`is_stub: false`, a real archive named in `provenance`)
would not learn it without reading the caveats array too. Treat "the plume visibly
moves with the current" as unverified for both demo outlets at this event's horizon
until a release point that lands on a resolved cell is used, or the current grid is
swapped for a finer one.

**Calibration.** `scripts/28_calibrate_plume_engine.py` ran a 72-trial grid search
(diffusion × windage × settling × regime) against the Kalman et al. (2025) mooring
record, scoring on timing only — arrival, duration, peak — and never a spatial metric.
No IoU/Dice/centroid distance exists or ever will for this event;
`backend/src/models/backtest_metrics.py`'s `assert_spatial_metrics_allowed` refuses to
compute one (see "Known limitations" #5 below). Winner: `hypopycnal`, diffusion
`5.0 m²/s`, settling `0.1 mm/s`,
arrival error `-6.83h`, duration error `+4.25h`, peak-timing error `-22.54h` (large, but
measured against a documented onset/clear-midpoint placeholder, not a digitized true
peak). Wind forcing is still `ConstantWindField(0,0)` — no historical wind source is in
this repo yet — so the winning `windage_fraction: 0.0` is a tie-break artifact, not a
calibrated value. Full numbers in `data/models/plume_calibration.json`, reported
honestly on screen in `ValidationPanel.tsx`'s "Transport-timing fit" section, not just
in a file.

Note: `docs/pitch_limitations.md` §9 records that satellite validation of the 2016
plume found nothing, for a documented physical reason — the in-situ mooring shows the
signal lasted ~31 h and both usable satellite passes were 2.5–3.5 days later.

### Verification

`tests/test_particle_engine.py` (23 checks) plus the live-endpoint checks folded into
`tests/test_api_contracts.py` — 475 passed / 51 skipped / 1 xfailed across the full
suite as of 6 Aug 2026. Live-curled against a container-equivalent process
(`uvicorn api.main:app --app-dir backend/src`), not inferred from source reading alone.

### Known limitations

1. **One demo event has real currents; every other event degrades to a documented
   placeholder.** Only `AQ-2016-10-28` has a cached HYCOM archive baked ahead of time.
2. **Wind forcing is a placeholder for every event**, calibrated or not — `windage`
   numbers should not be read as scientifically fitted until real historical wind
   (ERA5-Land u10/v10) is wired in.
3. **The current grid can mask a release point as land — at every outlet tested so
   far, not just one.** The ~9 km HYCOM cell under the release point reads NaN u/v
   (treated as zero current per `simulate()`'s own `nan_to_num` rule) at `AQ-O01`,
   `AQ-O02`, `AQ-O03` and `AQ-O05` alike for this event. Confirmed by measurement, not
   just by the caveat text: `AQ-O02`'s contour centroids show no coherent directional
   drift across any of the six reported timesteps, only non-monotonic ~15–100 m wobble
   at every density level — the signature of diffusion, not advection. Transport stays
   diffusion/settling-only until the plume drifts onto a resolved cell, which does not
   happen within this event's 24 h horizon at the demonstrated diffusion rate. Surfaced
   as a response caveat, not silently absorbed — but a reader of only the headline
   fields (`is_stub`, `model_version`, `provenance`) will miss it unless the `caveats`
   array is read too.
4. **Peak-timing calibration error is measured against a proxy, not an observation** —
   the mooring's 5-minute series gives onset/clear directly but not a digitized peak
   timestamp, so peak timing is scored against the onset–clear midpoint.
5. **No spatial (IoU/Dice/centroid) validation exists or ever will for this event** —
   the Sentinel-2/Landsat-8 extraction returned a final NO-GO (`docs/event_audit.md`
   §3, `docs/pitch_limitations.md` §9); the codebase actively refuses to compute one
   (`backend/src/models/backtest_metrics.py`'s `assert_spatial_metrics_allowed`).

---

## F · Coral health vision model — Pulga (Phase 5, B8)

**Handcrafted color/texture features + `sklearn.ensemble.GradientBoostingClassifier`,
not a CNN.** `backend/requirements-api.txt` has no torch/tensorflow/timm — only
scikit-learn, xgboost, pillow — and this project already hit a slow-network pip
timeout once on a 303 MB CUDA wheel earlier this phase. Seven real features per
photo (`models/coral_health_classifier.py::extract_features`): per-channel RGB mean
and standard deviation, plus a simple edge-density texture proxy.

**No real training data exists in this repository, and `classify()` says so
honestly on every response.** Every image already in this project (QA figures,
satellite overlays, Google Maps screenshots) was checked — none is an underwater
reef photo, none is labelled healthy/stressed/bleached. So today, every
classification carries `model_basis: "heuristic_rule_v1"`: a documented rule of
thumb on the same real color features (bleaching's real visual signature — pale,
high brightness, low color variance), capped at 0.55 confidence, **not** a trained
model. `scripts/30_train_coral_health_classifier.py` exists and is fully runnable,
but reports "0 training images found, nothing trained" until a real, human-labelled
set is added under `data/raw/reef_photos/_training/{healthy,stressed,bleached}/` —
`models/coral_health_classifier.py::train()` refuses outright to persist a model
trained on zero real images, the same rule `models/artifacts.py::save()` already
enforces for the runoff GBM's synthetic-data refusal. Once real training images
exist, a trained artifact lands in `data/models/coral_health_classifier.joblib`
with its own `model_versions.jsonl` row (`component: "coral_health_classifier"`),
and `model_basis` flips to `"trained_classifier"` automatically — no code change
needed to pick it up.

**The one thing this component can never do, by construction:** classifications
never touch the live `sensitivity_weight` `/reef-zones` serves. They accumulate into
a separate `proposed_sensitivity_weight` field (`GET /reef-zones/{id}/photos`), and
only a human calling `POST /reef-zones/{id}/sensitivity-weight/approve` — naming a
reviewer and reasoning, both required — can move a value from proposed to live,
logged permanently in `sensitivity_weight_approvals`. See
`docs/data_dictionary.md`'s Phase 5 artifacts section for the full mechanism.

**Once approved, it is genuinely live, not just displayed.** `exposure_calculate`
used to feed the exposure formula a hardcoded placeholder unconditionally — an
approval changed what `/reef-zones` showed but never once entered a real
`risk_score`. Fixed: the formula now reads the same real per-zone value (override
included) that `/reef-zones` displays, so a marine-scientist-approved weight moves
the actual exposure score by exactly that factor, live-verified end to end
against the running container.

---

## Data foundation

Full provenance, licences and per-source limitations:
[`docs/data_dictionary.md`](data_dictionary.md). Judge-facing summary:
[`docs/pitch_limitations.md`](pitch_limitations.md).

Two things a reader of this card should know without having to open those:

- **Bathymetry is GMRT, substituted for GEBCO**, whose every programmatic route is
  closed. Cross-checked against NOAA NCEI (0.2 m on the basin minimum) and against
  OSM's independent coastline (62 m median). Effective resolution ~450 m regardless of
  the 50 m grid spacing. The file is named `gmrt_aqaba.tif`, not `gebco_aqaba.tif`.
- **The AOI was wrong and was corrected on 2026-08-02.** The pre-v2 download box cut
  off most of Wadi Yutum, the catchment that is 4,453 of the basin's 4,656 km². Land
  cover, soil and OSM were all re-pulled. Evidence:
  `docs/aoi_coverage_report_20260802.txt` — 19 files short before, 7 after, each
  remaining one explained as correct-by-construction.

## Bugs caught, and how

Ten so far across both phases, every one with a figure or a test. Five were found
**by building the artifact rather than by reading the code**, which is the argument
for the discipline: reef zones placed on dry land, mixed NaN/−32768 nodata that would
have turned particle positions into non-numbers, undeclared 0-nodata read as
zero-clay soil, 1.46 ha of double-counted reef, distances measured in the wrong
projection and overstated by 14.8%, and — this phase — a module-name collision that
made a whole test file fail depending on alphabetical ordering.
