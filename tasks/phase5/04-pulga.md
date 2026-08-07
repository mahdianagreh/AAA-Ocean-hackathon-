# Pulga — Backend, Exposure Engine, RAG, and Four New AI Features

**Phase 5 · Workstream 4**
Read [`00-phase5-plan.md`](00-phase5-plan.md) first.

---

## Why this phase matters

**Everything on this list is done and live-verified against the running container —
539 tests pass, 0 regressions.** All four Part A items are closed. All four Part B
features are built end to end (model/backend, no dashboard — that's Ali's half by
design). Two deliberate, documented deviations from this file's own sketch (B4 isn't
literally "LLM-driven"; B8 isn't a CNN) and one real deployment bug found and fixed
while wiring B8 against the actual container (a direct `.gpkg` write that would have
failed against the real read-only `./data` mount) are called out inline below, in
writing, not silently substituted.

---

## 0 · Close your Phase 2 items — Day 0/1

- [x] **A3.1 — real ACA export served by `/api/v1/reef-zones`.** Confirmed live: 8
      real zones, heterogeneous area/depth/habitat values, a version marker
      distinguishing real vs. provisional. No action needed.
- [x] **A3.2 — dated `docs/data_dictionary.md` amendment for the ACA swap.**
      Confirmed: §4, "swap-in #3 CLOSED 2026-08-03," with a before/after table. No
      action needed.
- [x] **A3.3 — mooring read-through endpoint.** Confirmed live:
      `GET /api/v1/events/AQ-2016-10-28/mooring` returns the full real payload
      (citation, DOI, position, markers, magnitude fields). No action needed.
- [x] **A3.4 — backend half done and closed; frontend half is explicitly not
      mine.** Fixed a real gap found while documenting: `runoff_predict` echoed
      `transmission_loss` structurally, but `exposure_calculate` applied
      `transmission_loss_override` to the real feature row and then silently
      dropped it from the response — never echoed anywhere. Fixed in
      `main.py::exposure_calculate` (now lands in
      `formula_terms["transmission_loss"]`, mirroring the runoff path exactly);
      live-verified: `transmission_loss_override: 0.3` → response shows
      `formula_terms.transmission_loss == 0.3`. Full contract (field names,
      bounds `[0.5,2.0]`/`[0.20,0.85]`, where each is echoed) documented in
      `docs/data_dictionary.md` §"Scenario engine parameters". New test:
      `tests/test_phase4_scenario_engine.py::test_exposure_calculate_echoes_transmission_loss_too`.
      **`ScenarioDrawer.tsx` still doesn't call either endpoint** — confirmed
      still true, still Ali's item, not touched here.

---

## 1 · B4 — Automated Site-Scoring Agent — ✅ done, with one deliberate spec deviation, stated here in writing

**Model & data**

- [x] **Not literally "LLM-driven."** Checked before building: `rag/answer.py::generate_with_llm()`
      is a permanent stub that always raises `NotImplementedError` — nothing in this
      codebase has ever wired a real generative model, `/explain` and `/ask` both work
      by retrieving/computing real facts and templating them. B4 follows that exact
      pattern (`models/site_scoring.py::narrate_criterion`) rather than being the first
      thing to add a real LLM call. Zero new dependency, zero new API key, and rule 12
      ("the LLM phrases numbers, never computes them") is trivially satisfied since
      there's no generative model in the loop to phrase anything wrong.
- [x] Every score grounded in a specific retrieved/computed fact, cited via the
      existing `Citation` shape — verified live: real drainage-intermittency fraction
      (C1), real rainfall concentration ratio (C2), real projected distance to the
      nearest reef zone (C3), real bathymetry depth range (C4), real OSM building
      count (C5). C6 always reports `insufficient_data` — no geospatial dataset can
      characterise the *absence* of other monitoring infrastructure, for any location,
      including Aqaba.
- [x] Rainfall/climate criteria (C2) read directly from
      `catchment_rainfall_climatology.parquet` — no new ingestion pipeline.

**Backend & storage**

- [x] `POST /api/v1/sites/score` — live, tested against both a real Aqaba box (real
      scores) and a box with zero data coverage (`insufficient_data` on every
      criterion, never a guess). **One schema deviation from this file's own sketch,
      necessary for honesty:** `CriterionScore.score` is `float | None`, not `float` —
      `None`, not a fabricated number, when a criterion has no real evidence for the
      requested box (`status: "scored" | "insufficient_data"` alongside it).
- [x] `candidate_sites` table — `site_{ULID}`, confirmed clear of the five frozen
      schemes. `tests/test_site_id_contract.py` is the matching static guard, mirroring
      `tests/test_run_id_contract.py`'s existing enforcement of `sim_{ULID}`.
- [x] EPSG:32636 reprojection for C3's reef-distance calculation, via a new,
      generalized `config.spatial.local_utm_crs()` (uses
      `geopandas.GeoDataFrame.estimate_utm_crs()` — the first dynamic UTM-zone picker
      in this codebase; everything before this was hardcoded to zone 36N).

**Dashboard sub-features (for Ali to build)**

- A "Score a new coastline" input box: paste coordinates, get back a
  live-generated six-criterion score rendered exactly like the existing scorecard
  table.
- A map layer showing auto-scored candidates color-coded by tier, letting you
  visually scan for new Tier-1 sites instead of researching one region at a time.
- Auto-populates a new row in the research-scan scorecard visualization.

**Limitation to state on the same screen this ships on:** this rubric was built and
tuned against exactly one site — Aqaba. A score for anywhere else is the rubric's
first real test, not a validated instrument. Say this next to the score, not just in
this file.

---

## 2 · B5 — Post-Event Forensic Report Generator — ✅ done

**Model & data**

- [x] Assembles a report from `exposure.store.latest_run()` (real `formula_terms`),
      `data_access.mooring_for()` (real mooring), and `rag.index.retrieve()` (real RAG
      citations) — `models/report_assembly.py`, a pure function, no `api` imports.
- [x] Never computes a new number — verified live for both the anchor event (real,
      populated sections) and a thin non-anchor event (each section states its own
      gap by name — "no exposure run has been stored", "no mooring record exists" —
      not one blanket disclaimer).

**Backend & storage**

- [x] `POST /api/v1/reports/generate` — live, `report_{ULID}`.
- [x] `status` starts `"ai_drafted"` on every insert; `PATCH
      /api/v1/reports/{report_id}/review` (`reviewed_by` required, 422 without it) is
      the **only** code path that can write `"human_reviewed"` —
      `models/generated_reports.py::set_reviewed()` is the only function that does.
      `generated_reports` table, `data/outputs/generated_reports.sqlite`.

**Dashboard sub-features (for Ali to build)**

- "Generate Report" button on any completed event.
- A visible, un-hideable draft-status badge on every AI-generated report.
- Direct integration with the Bilingual Assistant — same citation engine powering
  `/ask` now also sources the report's claims.

**Limitation to state:** the report is only as complete as the event's own data —
for any event other than the anchor storm (`AQ-2016-10-28`), most `formula_terms`
inputs are thinner or absent, and the report must say so per section, not present a
uniformly confident narrative regardless of which event it's about.

---

## 3 · B7 — Adaptive Sampling Recommender — ✅ done

**Model & data**

- [x] Simple heuristic: fraction of logged outcomes marked `"confirmed"`
      (`models/sampling_feedback.py::_historical_accuracy`) — not deep RL, not even a
      bandit yet, matching the task's own "starts simple" framing.
- [x] `POST /api/v1/reef-zones/{id}/feedback` logs `run_id` + `outcome`, validated
      against a real stored exposure run (404 if the run or the zone-in-that-run
      doesn't exist).

**Backend & storage**

- [x] `sampling_feedback` table, `feedback_{ULID}`, `data/outputs/sampling_feedback.sqlite`.
- [x] **Additive field, not a formula change** — checked `exposure/engine.py`'s own
      docstring first, which explicitly warns against folding a new term into
      `calculate_exposure()` ("would change the ranking... while looking like a
      presentation detail"). So `risk_score` is byte-identical to before this feature
      existed; `ExposureResult.adjusted_priority` is a new, separate field that
      **equals `risk_score` exactly** (`adjusted_priority_status: "NO_FEEDBACK_YET"`)
      until `MIN_FEEDBACK_FOR_ADJUSTMENT` (5) real rows exist for that zone — the
      literal default, not an approximation, and tested as such
      (`tests/test_sampling_feedback.py`). Once applied, bounded to `[0, risk_score]` —
      feedback can only dampen the score, never inflate it.

**Dashboard sub-features (for Ali to build)**

- Upgrades the existing Named Reef Zone Priority List with "last sampled" and
  "prediction vs. outcome" history.
- An accuracy-over-time trend chart, showing the recommender's own track record
  improving.

**Honesty note — keep this in the actual UI copy, not just internal docs, exactly as
the user's own spec for this feature demands:** this feature cannot be meaningfully
demoed with zero deployment history. Build the plumbing now; frame it in the pitch as
infrastructure for a capability that activates after real-world use, not a working
feature today. If the UI copy says anything stronger than that before real sampling
history exists, it's overclaiming.

---

## 4 · B8 — Coral Health Vision Model — ✅ done, with one deliberate spec deviation, stated here in writing

**Model & data**

- [x] **Not a CNN.** `backend/requirements-api.txt` had no torch/tensorflow/timm before
      this feature and still doesn't — adding one risked repeating this session's own
      pip-timeout incident (a 303 MB CUDA wheel stalled a Docker build earlier this
      phase). Built instead: 7 handcrafted color/texture features
      (`models/coral_health_classifier.py::extract_features`, Pillow + numpy) +
      `sklearn.ensemble.GradientBoostingClassifier` (already a dependency).
- [x] **Checked first, not assumed: zero real labelled reef photos exist anywhere in
      this repository** (every image here is a QA figure, satellite overlay, or Google
      Maps screenshot). So `classify()` has two honestly-distinguished paths —
      `model_basis: "heuristic_rule_v1"` (documented rule of thumb on real color
      features, capped at 0.55 confidence — the honest state today) vs.
      `"trained_classifier"` (once real training photos exist).
      `scripts/30_train_coral_health_classifier.py` is fully written and runnable, and
      correctly reports "0 training images found, nothing trained" right now — it
      refuses outright to fabricate a training set, the same rule
      `models/artifacts.py::save()` already enforces for the runoff model's
      synthetic-data refusal.

**Backend & storage**

- [x] `POST /api/v1/reef-zones/{id}/photos` — the first multipart file-upload
      endpoint in this backend; live-tested with a real image, returns a real
      classification. (Required one new, small, unavoidable dependency —
      `python-multipart` — FastAPI's `UploadFile` mechanism needs it unconditionally;
      not the CV dependency this deviation avoided.)
- [x] Every classified photo stored (`reef_zone_photos` table,
      `data/outputs/reef_zone_photos.sqlite`; image bytes under
      `data/raw/reef_photos/`, git-ignored — user-submitted content, not reproducible
      data).

**The one non-negotiable design requirement in this entire phase — done, and verified
against the actual deployed container, not just the schema:** `sensitivity_weight =
1.0` / `PLACEHOLDER_PENDING_MARINE_SCIENTIST` (`tasks/00-contracts.md` §5, swap-in #5,
still open) now has a real path toward evidence. `proposed_sensitivity_weight`
(`GET /reef-zones/{id}/photos`) is computed from accumulated classifications and lives
in a wholly separate field — `PLACEHOLDER_PENDING_MARINE_SCIENTIST` is untouched by any
number of photo uploads (tested directly: upload photos, re-check
`GET /reef-zones`, confirm nothing moved). The only way to move a value from proposed
to live is `POST /reef-zones/{id}/sensitivity-weight/approve` (`reviewer`/`reasoning`
required, 422 without them), and every approval is logged permanently in
`sensitivity_weight_approvals`.

**One real design correction made while wiring this against the actual running
container, not assumed from the schema:** the first version of `approve` wrote
`sensitivity_weight` directly into `reef_zones.gpkg` — which works on a developer's
machine and **fails in the deployed container**, because `./data` is mounted
**read-only** on purpose (`docker-compose.yml`'s own comment; this exact class of bug
already happened once before for `exposure_runs.sqlite`). Fixed before it shipped:
`approve` now writes a `sensitivity_weight_overrides` row (in the writable
`reef_zone_photos.sqlite`, redirected to `/app/var` in the container) and
`data_access.py::reef_zones()` applies it as a read-time overlay — the base `.gpkg` is
never rewritten by the running API, ever. Confirmed live against the real container
(not just a local copy): approved a real override, watched `/reef-zones` reflect it,
then confirmed via SHA-256 hash that `reef_zones.gpkg` on disk was byte-for-byte
unchanged before and after.

**Closed the loop fully, on request — this was flagged as out-of-scope once, then
actually fixed:** `exposure_calculate` was passing `engine.HABITAT_SENSITIVITY_PLACEHOLDER`
(the constant, not the per-zone value) into the exposure formula unconditionally, so an
approval changed what `/reef-zones` *displayed* but never once fed into a real
`risk_score`. The exposure engine is squarely Pulga's domain, not a teammate's, so this
was mine to close, not defer. `main.py::exposure_calculate` now reads the real per-zone
value (override included) from `zone_meta` — identical behaviour today, since every
zone's real value equals the placeholder (1.0) until a human actually approves one, and
genuinely different the moment one is: live-verified end to end against the real
container — approved `R-08` to `1.4`, watched `risk_score` move by exactly that factor
and `habitat_sensitivity_weight_status` flip to `SCIENTIST_ASSIGNED` on a real, freshly
computed exposure run. New test:
`tests/test_reef_zone_photos.py::test_an_approved_weight_actually_changes_the_real_exposure_formula`.

**Dashboard sub-features (for Ali to build)**

- Photo upload widget per named reef zone.
- Immediate classification result shown on upload, feeding a per-zone health trend
  line.
- A "photos contributed" counter — cheap engagement mechanic that also grows the
  training set.
- A clearly separate, clearly labelled "proposed sensitivity weight update — pending
  scientist review" panel, distinct from the live, in-use placeholder value.

**Limitation to state:** a CNN trained on however many diver photos accumulate in
five days is not a validated coral-health instrument — its proposals are exactly
that, proposals, and the review step exists because the model's own confidence is not
sufficient grounds to change a number the whole exposure engine multiplies through.

---

## Definition of done

1. [x] A3.4 — backend contract fully documented (`docs/data_dictionary.md`), AND the
   echo gap it revealed is fixed, not just noted.
2. [x] B4 — `POST /api/v1/sites/score` live, every criterion citing real retrieved
   evidence, `candidate_sites` table populated by real scored boxes (tested with
   both an Aqaba box and a zero-coverage box).
3. [x] B5 — `POST /api/v1/reports/generate` live, every generated report carries
   `status: "ai_drafted"` until a human flips it via the one dedicated endpoint, no
   fabricated figures (verified for both the anchor event and a thin event).
4. [x] B7 — `sampling_feedback` table exists; ranking formula falls back cleanly
   with zero history (`adjusted_priority == risk_score` exactly, tested); the "UI
   copy matches the honesty note" half is Ali's (frontend) — the backend-side honesty
   note is in `docs/pitch_limitations.md` §11.
5. [x] B8 — photo endpoint live; `proposed_sensitivity_weight` is a separate field
   from the live `sensitivity_weight`; no code path writes the live field
   automatically — confirmed by SHA-256 hash against the real `reef_zones.gpkg`,
   not just by reading the code.

**Everything above is backend-complete.** What remains is explicitly not mine:
Ali's dashboard sub-features for B4/B5/B7/B8 (listed in each section above), and
`ScenarioDrawer.tsx`'s repoint for A3.4.
