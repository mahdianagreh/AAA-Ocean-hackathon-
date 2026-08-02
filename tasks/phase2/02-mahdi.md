# Mahdi — Model Layer & DevOps

**Phase 2 · Workstream 2**
**Feeds:** Component C (runoff risk) · Component D (sediment proxy) → the API, the map, the pitch
**Read [`00-phase2-plan.md`](00-phase2-plan.md) first.**

---

## Why your stream matters

Your terrain work is done and it holds up — three independent methods agree on Wadi Yutum's
area within 8%, and you caught three bugs that each produced plausible-looking wrong output.
That is the discipline this next job needs, because **the model is where a hackathon project
most easily lies to itself.**

You own the only thing in this system that is genuinely machine-learned. Everything else is
a formula or physics. So when a judge asks *"what is the AI here?"*, the answer is your
model — and the follow-up will be *"how do you know it works?"* That answer is your
validation harness, not your accuracy number.

You also own Docker, because the demo has to run on a laptop at ABOFA with conference wifi.

---

## Part 1 — Component A · Runoff risk classifier

**This is the only trained model in the project.**

### Input

`data/processed/features/event_catchment_features.parquet` from Karam. One row per
(event × catchment). Take it as soon as it exists, even partially filled — a model trained
on 40 events on Day 5 and retrained on 100 on Day 8 beats one that starts on Day 8.

### Build order

- [ ] **Rule-based baseline first.** A curve-number-inspired runoff index from rainfall
      intensity, antecedent soil moisture, slope and bare fraction. Transparent, no training,
      and it is what the ML model has to beat. If XGBoost cannot beat it, that is a finding
      worth reporting, not hiding.
- [ ] **XGBoost** on the same features.
- [ ] **Probability calibration** — isotonic or Platt. An uncalibrated classifier's 0.8 does
      not mean 80%, and the dashboard displays that number to a user.
- [ ] **SHAP** attribution per prediction. This is what feeds Pulga's explanation endpoint
      and the "top drivers" list on the risk card.

### Validation — both are mandatory

**Leave-one-catchment-out.** Static features (area, slope, drainage density, soil texture)
are *constant per catchment*. With five catchments and a few hundred rows, random
cross-validation lets the model memorise which catchment a row belongs to and report a
beautiful, meaningless score. LOCO is the only honest split. This is a data-design
constraint, not a tuning preference.

**Temporal holdout: train ≤ 2014, test ≥ 2015.** This is what buys the headline:

> *"Trained on data ending in 2014, having never seen October 2016, the model ranks it the
> highest runoff probability in 26 years for Wadi Yutum."*

Checkable, falsifiable, and the strongest single sentence available to the pitch. **If it
does not hold, report that too** — it would most likely mean the ~11 km IMERG cell smoothed
the convective storm that caused the flood, which is a known, documented product limitation
and an interesting result in its own right.

### The label rule you must not break

Karam's matrix uses ERA5-Land surface runoff as the **label**. It must never appear as a
**feature**. If `sro` or `ssro` shows up in your feature list, you have built a tautology
that scores 0.99 and predicts nothing. Assert it in code, not in a comment.

### Model card

Write it as you go, not at the end. It states: features used, label tiers and their basis,
both validation splits with their scores, the daily-screening caveat from Karam's Stage 1,
the ±4% uncertainty on AQ-C01's area, and what the model is **not** capable of.

**Deliverables:** `backend/src/models/runoff_model.py` · `docs/model_card.md` · trained
artifact + `model_versions` row.

---

## Part 2 — Component D · Sediment load proxy

**A formula, not a model. Say so plainly.**

```text
sediment_proxy = bare_fraction
               x slope_term
               x erodibility(clay, sand, soc)
               x runoff_volume
               x drainage_density
               x (1 - transmission_loss)
```

- [ ] Output a relative class — Low / Medium / High / Extreme — not a mass, per concept §10.4.
- [ ] **Anchor it to the one real number available:** ≈24,400 t for October 2016. That gives
      a single-point scale calibration. One point is not a curve. Say that.
- [ ] Write the formula down in the docs with every term defined. A formula nobody can read
      is indistinguishable from a guess.

### Transmission loss — the assumption nobody has modelled yet

Between **13.2% and 98%** of a desert flood soaks into the wadi bed and never reaches the
sea; the Negev range is **20–85%**. The pipeline currently assumes 0% implicitly, which is
the most optimistic possible value and is certainly wrong.

- [ ] Make it an **explicit parameter** with a documented default and range.
- [ ] Expose it as a scenario control so Ali can put a slider on it.

This turns the project's largest hidden assumption into a visible, defensible feature. It
also gives you a good answer to a hard question instead of a silence.

**Deliverables:** `backend/src/models/sediment_proxy.py` · the formula documented in
`docs/model_card.md`.

---

## Part 3 — Model serving

- [ ] A predict function Pulga's API calls: features in → probability, severity, confidence,
      SHAP drivers out.
- [ ] Populate `model_versions` — which model, trained on which event IDs, which
      hyperparameters, which git SHA. Without it a stored prediction is an orphan number that
      cannot be reproduced or explained.
- [ ] Version the artifact in Supabase Storage; the row in Postgres points at it.

---

## Part 4 — Docker

No CI. Compose only.

- [ ] `docker-compose.yml` with: **api** (FastAPI) · **frontend** (React) · **worker**
      (pipeline and simulation jobs) · **db** (Postgres + PostGIS, the *offline mirror*).
- [ ] Normal operation talks to **Supabase Cloud**. The local `db` service is the fallback,
      seeded from a `pg_dump` of Supabase, selected by one environment variable.
- [ ] Build the offline path **now**, not on Day 12. Concept §25 lists "data downloads fail
      during demo" as medium probability / high impact, and ABOFA conference wifi is exactly
      where that lands.
- [ ] `docker compose up` on a clean machine must bring up a working demo with no network.
      Test it by turning wifi off. That is the acceptance criterion.

---

## Part 5 — Finish the outlets

Three of the five are compromised by port infrastructure. The catchments are sound; only the
mouth positions are unreliable.

- [ ] Add `position_confidence` to `outlets.gpkg`: `AQ-O01` plausible · `AQ-O05` good ·
      `AQ-O02`, `AQ-O03`, `AQ-O04` low.
- [ ] Add a `caveat` text column. For `AQ-O04` it says, in full: *discharges into an enclosed
      harbour basin; sediment released here settles in the basin rather than dispersing into
      the Gulf.*
- [ ] Make sure that caveat reaches the API response, not just the file — so it travels into
      the UI and cannot be forgotten.
- [ ] Cross-check the routed channels against Pulga's 27 mapped culverts
      (`docs/osm_dem_conflicts.md` §1). A culvert carries water *through* an embankment the
      DEM routes *around*. This is still open from Phase 1 and it is the one real fix
      available without ASEZA data.

---

## Definition of done

1. Rule baseline **and** calibrated XGBoost, with the baseline's score reported honestly.
2. LOCO **and** temporal-holdout results, both in the model card.
3. A stated verdict on the Oct-2016-ranking claim — held or not held.
4. Sediment proxy formula documented, anchored, with transmission loss exposed.
5. Predict function serving the API; `model_versions` populated.
6. `docker compose up` produces a working demo **with wifi off**.
7. `position_confidence` and the AQ-O04 caveat travelling through to the API.
8. Culvert cross-check done or explicitly deferred with a reason.

## Handoffs

| Teammate | What they get | When |
|---|---|---|
| **Pulga** | predict function + SHAP output | Day 4 for a stub, Day 8 for the real model |
| **Abd** | sediment class per event, to scale particle release | Day 6 |
| **Ali** | risk fields, driver list, transmission-loss parameter range | Day 5 |
| **Everyone** | `docker compose up` | Day 5, then kept working |

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Karam** | the feature matrix | Partially — build the harness and the baseline against a stub first |
| **Nizar** | Supabase connection | For `model_versions` only |
