# Model card — ReefShield Aqaba

**Last updated:** 2026-08-05 · Part of the `/ask` corpus, so anything written here is
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
| **C · Plume transport** | outlet discharge → probability contours | Abd | real engine exists; API wiring stubbed |

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
| `relative_sediment_intensity` | 0–1 | Mahdi's sediment class, normalised | derived (stub today) |
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

**Data:** `training_set_full.parquet` — 11,810 catchment-days, 1998–2022
**Positive:** `sro > 0.002 mm/day` — 928 rows (7.9%)
**Features:** 10

### The target, and why it is a threshold

The delivered matrix was 390 rows from the top 100 rainfall days in 27 years, so
99% had runoff — "will there be runoff" was answered before the model saw it. The
full population is assembled from all 77 ERA5 months on disk: 11,810 rows at
7.9% positive.

The threshold is **anchored, not tuned for balance.** The one documented
sediment-delivering flood — October 2016, ≈24,400 t — peaks at 0.00373 mm, the
94.5th percentile of all catchment-days. 0.002 mm sits below it, so the sole piece
of ground truth is comfortably positive rather than marginal.

### Imbalance: two problems, two fixes

At 7.9% positive, `min_child_weight` is a floor on the sum of
hessians in a leaf, and h = p(1−p):

```
base rate 7.9% · h = 0.0724 · a leaf needs ~55 positives to clear min_child_weight=4
base rate 20.0% · h = 0.1600 · a leaf needs ~25 positives to clear min_child_weight=4
```

A leaf needs ~55 positives before it may exist. With 928 positives
across 10 features and 5 catchments, predictive regions holding fewer get
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

### Results — LOCO, all five folds

| held_out   |   fit_rows |   test_rows |   test_pos |   test_pos_rate |   baseline_AP |   gbm_AP |   gbm_Brier | calibrated   |       A |      B |
|:-----------|-----------:|------------:|-----------:|----------------:|--------------:|---------:|------------:|:-------------|--------:|-------:|
| AQ-C01     |       2540 |        2362 |        274 |          0.116  |        0.2613 |   0.4361 |     0.08472 | True         | -0.6678 | 1.9707 |
| AQ-C02     |       2785 |        2362 |        215 |          0.091  |        0.2048 |   0.5173 |     0.0631  | True         | -0.7468 | 1.8386 |
| AQ-C03     |       2975 |        2362 |        158 |          0.0669 |        0.1982 |   0.5318 |     0.04491 | True         | -0.7559 | 1.7872 |
| AQ-C04     |       3050 |        2362 |        139 |          0.0588 |        0.1716 |   0.5549 |     0.0387  | True         | -0.755  | 1.776  |
| AQ-C05     |       3050 |        2362 |        142 |          0.0601 |        0.166  |   0.5664 |     0.0391  | True         | -0.7366 | 1.8191 |

**mean AP: baseline 0.2004 · gbm 0.5213 · delta +0.3209**

**Verdict: GBM beats the baseline by +0.3209 AP**

#### Leakage, measured

Random K-fold AP 0.5138 against LOCO AP 0.5213 — a gap of **-0.0075**. That difference is catchment memorisation with a number on it: static features are constant within a catchment, so a random split lets the model recognise which catchment a row belongs to. Reporting both is stronger than either alone.

### Calibration on the held-out catchment

|   n |   predicted |   observed |
|----:|------------:|-----------:|
| 473 |   0.0208342 |  0.0295983 |
| 472 |   0.0464708 |  0.0508475 |
| 472 |   0.0782161 |  0.0529661 |
| 472 |   0.131152  |  0.101695  |
| 473 |   0.288471  |  0.344609  |

Predicted against observed. A calibrated model tracks the two columns together.

### Feature importance

|                         |   mean_abs_shap |
|:------------------------|----------------:|
| soil_moisture_lag3d     |          0.8226 |
| soil_moisture_lag1d     |          0.7356 |
| precipitation_mm_day    |          0.6311 |
| precip_prior_7d_mm      |          0.4654 |
| precip_prior_1d_mm      |          0.4257 |
| area_km2                |          0.3311 |
| precip_prior_3d_mm      |          0.2647 |
| elongation_ratio        |          0.0371 |
| drainage_density_km_km2 |          0.0222 |
| slope_mean_deg          |          0.0169 |

### What this model cannot do

- **It predicts modelled runoff, not a flood reaching the sea.** The label is
  ERA5-Land surface runoff — ECMWF's land-surface scheme, not an observation.
- **Sub-daily rainfall is unavailable** over the full record, so it trains on daily
  totals. This is a real loss: intensity drives runoff in a hyper-arid catchment,
  and Oct 2016 ranks 14th by daily total against 8th by peak 3-hour intensity.
- **Label quality is not uniform.** AQ-C01 gets 41 ERA5 cells, a genuine area
  mean; the other four get one cell each and three are nearest-cell point samples
  with no cell centre inside the polygon. ERA5-Land is ~81 km² per cell against
  catchments of 36–65 km².
- **Only 656 hard negatives exist** — days with measurable rain and little runoff,
  where the boundary is. They cap what can be learned, and more would need ERA5
  months that are not downloaded.
- **Five catchments is not a sample.** Any pattern across five points could be
  coincidence, and no validation scheme fixes that.

---

## C · Plume transport (particle engine) — Abd

Real engine at `backend/src/models/particle_engine.py` with its own tests. The API
route `POST /api/v1/plume/simulate` is **stubbed pending wiring**, flagged the same
way. Consumes `depth_utm36n.tif` and `coastline.gpkg`.

Note: `docs/pitch_limitations.md` §9 records that satellite validation of the 2016
plume found nothing, for a documented physical reason — the in-situ mooring shows the
signal lasted ~31 h and both usable satellite passes were 2.5–3.5 days later.

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
