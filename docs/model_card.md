# Model card — ReefShield Aqaba

**Last updated:** 2026-08-02 · Part of the `/ask` corpus, so anything written here is
answerable live and must be defensible live.

This card covers the components that turn data into a displayed number. It is
organised by owner, because a model card that blurs who verified what is not much
use when a judge asks.

| Component | What it does | Owner | State |
|---|---|---|---|
| **D · Exposure engine** | plume + sediment → per-zone risk score | Pulga | **implemented, tested** |
| **E · Explanation** | risk state → grounded bilingual paragraph | Pulga | **implemented, tested** |
| **E · Retrieval (`/ask`)** | technical corpus → cited answers | Pulga | **implemented, tested** |
| **C · Runoff model** | rainfall + catchment features → runoff | Mahdi | stub behind the API |
| **Particle / plume engine** | outlet discharge → probability contours | Abd | real engine exists; API wiring stubbed |

Sections for C and the particle engine are deliberately short — those owners should
fill them in, and writing confident text about someone else's model would be exactly
the kind of unearned claim this card exists to avoid.

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

---

## C · Runoff model — Mahdi

Wired behind `POST /api/v1/runoff/predict`. **Currently a stub**: it returns a
correctly-typed `RunoffPrediction` with `is_stub: true` and a `critical` caveat
saying the numbers are not predictions. Consumes
`landcover_by_catchment.parquet`, `soil_by_catchment.parquet`,
`urban_by_catchment.parquet` — all regenerated 2026-08-02 against the real
5-catchment set. Mahdi to complete.

## Particle / plume engine — Abd

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
