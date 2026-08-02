# Pulga — Backend, Exposure Engine & RAG

**Phase 2 · Workstream 4**
**Feeds:** the frontend, and every number a judge will see
**Read [`00-phase2-plan.md`](00-phase2-plan.md) first.**

---

## Why your stream matters

You wrote the most disciplined code in Phase 1 — processing scripts that assert, QA scripts
that visualise, and five silent bugs caught because you insisted every step produce a picture
you had to look at. Two of those bugs were found *by building the figure*, not by reading the
code.

Phase 2 needs exactly that instinct in a new place. The backend is where every number the
user sees gets assembled, and an exposure score that is wrong will look completely normal.

You own three things: the API, the exposure engine, and the retrieval layer that turns the
project's documentation into something a user can interrogate.

---

## 0 · Close your Phase 1 blockers first — Day 1

Both are now unblocked and both are short.

- [ ] **The three feature tables.** `catchments.gpkg` merges on Day 0, so
      `aggregate_catchments.py` runs for real. Delete
      `data/interim/catchments_FIXTURE_local_test_only.gpkg` afterwards.
      → `landcover_by_catchment.parquet`, `soil_by_catchment.parquet`,
      `urban_by_catchment.parquet` at the contract paths, no longer quarantined.
- [ ] **Earth Engine auth + the ACA export.** ~10 minutes of browser OAuth, then
      `export_aca.py submit / status / build`. `verify_against_provisional()` already asserts
      no new IDs appear and no centroid moves more than 5 km — let it do its job.
      → real `reef_zones.gpkg`, closing contract swap #3.

**Watch out:** R-01 and R-02 sit over developed beach and port frontage where reef presence
is doubtful. If ACA yields fewer real zones, per contract §2 the extras are **dropped and
the remaining IDs keep their names**. Never renumber — every stored exposure result joins on
those IDs.

`sensitivity_weight` stays **1.0** and stays labelled `PLACEHOLDER_PENDING_MARINE_SCIENTIST`
in the schema itself. ACA maps habitat, not sensitivity. Do not invent weights.

---

## 1 · FastAPI backend

Endpoints per concept §17:

```text
GET  /api/v1/health
GET  /api/v1/data-sources
GET  /api/v1/catchments               GET /api/v1/catchments/{id}
GET  /api/v1/reef-zones
GET  /api/v1/events                   GET /api/v1/events/{id}
POST /api/v1/runoff/predict
POST /api/v1/plume/simulate
POST /api/v1/exposure/calculate
POST /api/v1/backtests/run            GET /api/v1/backtests/{run_id}
GET  /api/v1/alerts
POST /api/v1/explain
POST /api/v1/ask
```

- [ ] Pydantic models for every request and response. Types are the contract between you and
      Ali; get them fixed early so he is not chasing a moving shape.
- [ ] Read through Nizar's connection layer. Never open your own.
- [ ] Cache expensive outputs — a simulation should not re-run because someone dragged the
      time slider.
- [ ] **Every response that carries a caveat must carry it as data, not documentation.**
      `AQ-O04` discharges into an enclosed harbour; `sensitivity_weight` is a placeholder;
      catchment area has ±4% uncertainty. Those travel in the payload so they reach the
      screen and cannot be forgotten.

**Priority for the 6 August vertical slice:** health · catchments · reef-zones · events ·
one stubbed exposure response. Ali needs shapes to draw against far more than he needs them
to be correct.

---

## 2 · Component D · Exposure engine

Turn a plume forecast into habitat-specific risk.

```text
Exposure = plume_probability
         x relative_sediment_intensity
         x exposure_duration_weight
         x habitat_sensitivity_weight        (= 1.0, placeholder)
         x confidence_adjustment
```

- [ ] Intersect Abd's time-stepped probability contours with the reef zones.
- [ ] Per zone, per run: `risk_score`, `risk_level`, `arrival_window_hours`,
      `max_exposure_probability`, `confidence`.
- [ ] **Store `formula_terms` alongside the score** — every input value that produced it. A
      score you cannot reconstruct six hours later is a number nobody can defend.
- [ ] Risk bands per concept §14.5 (0–20 minimal … 81–100 critical), with the note that
      operational thresholds need marine scientists.

**Watch out — areas and distances.** Every intersection area and every distance is computed
in **EPSG:32636**, never in degrees. You already lost time to this once: culvert distances
measured in EPSG:3857 were overstated by 14.8%. Draw in 3857, measure in 32636.

**Watch out — reef zone widths are a 250 m assumption**, deliberately not derived from depth
contours because the bathymetry's true resolution (~450 m) cannot resolve the Gulf's
drop-off. So `area_km2` is order-of-magnitude, and any exposure figure expressed as
"km² of reef affected" inherits that. Better to express exposure as a *fraction of a named
zone* than as an absolute area.

---

## 3 · Component E · Explanation and RAG

This is where the project's documentation becomes a product surface.

### 3a · Explanation endpoint

- [ ] `POST /explain` takes Mahdi's SHAP output plus model state, returns the concept §10.8
      paragraph in **Arabic and English**.

> *"Wadi Yutum is classified as high risk because forecast 3-hour rainfall exceeds the
> catchment's historical 99th percentile, the upstream terrain is steep, and antecedent soil
> conditions support rapid runoff. The plume ensemble indicates a 72% probability of reaching
> Reef Zone R-04 within 8–12 hours. Confidence is moderate because nearshore currents are
> represented by a coarse global model."*

**The rule, and it is not negotiable:** the LLM phrases numbers it is handed. It never
computes one, never rounds one, never invents one. If the model can change a score, the
system stops being auditable — and that is precisely what a judge will probe.

### 3b · RAG over the technical corpus

- [ ] Ingest, chunk and embed: `data/raw/literature/kalman_et_al_2025_fulltext_ATC1.pdf` ·
      `docs/data_dictionary.md` · `docs/event_dates.md` ·
      `docs/era5_land_temporal_semantics.md` · `docs/era5_land_accumulation_semantics.md` ·
      `docs/pitch_limitations.md` · `docs/forcing_limitations.md` ·
      `docs/osm_dem_conflicts.md` · `docs/qa_screenshots/MANIFEST.md` · `docs/model_card.md`
      · `tasks/00-contracts.md`.
- [ ] `POST /ask` returns an answer **plus the source file and section for every claim**.
      An uncited answer is not shippable.
- [ ] Bilingual — answer in the language asked.

> **`docs/ali/*` is NOT in the corpus.** The MENA and global analogue scan is research and
> pitch material only. It backs the market slide and the *"is this only for Aqaba?"* answer
> in Q&A. It is not an app surface.

**Why this is worth building:** questions like *"how confident are we in the catchment
area?"* or *"why is the reef sensitivity 1.0?"* have real, documented, honest answers in this
repo. Being able to surface them live is the difference between a team that documented its
limitations and a team that can defend them.

---

## Definition of done

1. Three feature tables at the contract paths, fixture deleted.
2. Real `reef_zones.gpkg` from ACA, IDs verified against the provisional set.
3. FastAPI serving every §17 endpoint, typed, cached, with caveats travelling as data.
4. Exposure engine producing scores with `formula_terms` stored.
5. `/explain` returning grounded bilingual paragraphs that invent nothing.
6. `/ask` returning cited answers over the technical corpus, in both languages.
7. `docs/data_dictionary.md` updated with the ACA product version and access date.

## Handoffs

| Teammate | What they get | When |
|---|---|---|
| **Ali** | typed endpoints, even stubbed | **Day 3 — he is blocked without shapes** |
| **Nizar** | real reef zones to load | Day 2 |
| **Karam** | land / soil / urban feature tables | Day 1 |
| **Abd** | the exposure consumer for his probability fields | Day 6 |

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Nizar** | schema + connection layer | **Yes, partly** — build endpoints against fixtures until Day 2 |
| **Mahdi** | predict function + SHAP | **No** — stub it, swap when real |
| **Abd** | plume probability fields | **No** — exposure engine tests against synthetic contours |
