# Phase 7 — Mahdi

**Owns:** terrain, hydrology, the runoff model, culverts, transmission loss, Docker,
offline mode — and the four B-features that do not exist.
**Pages:** the model-honesty surfaces on `/dashboard` · the culvert layer ·
`/limitations` (your half) · `/reports` (damage class).
**Rows:** `core-A`, `core-B`, `p4-04` (with Pulga), `p4-09`, `p4-11`, `p4-17`,
`p4-C`, `p4-D`, `p4-H`, `p4-J`, `b1`, `b2`, `b3`, `b9`.

Read [`00-phase7-plan.md`](00-phase7-plan.md) and
[`00-design-system.md`](00-design-system.md) first.

---

## The brand, in the two lines you will actually use

Never write a colour — `python3 scripts/qa_frontend_tokens.py` fails on a hex literal
in `frontend/src/`.

```
grounds   bg-canvas  bg-surface  bg-surface-2   borders  border-hairline
ink       text-ink   text-ink-2  text-ink-3     accent   text-accent
hazard    BAND_CLASS from src/api/types.ts
```

Deep Navy `#0A1F4D` · Ocean Blue `#0D3D7A` · Marine Teal `#007A99` · Aqua `#00B7C3`
· Foam White `#E6F7FA`. Montserrat; numbers in IBM Plex Mono via `num`. Radii
8/12/16/20, `--radius-hairline: 2px` for map and chart chrome. Cards are `<Card>`.

**Your pattern:** most of your work is *honesty surfaces* — panels whose entire job
is to state a limit clearly. Use `<Card>` with a plain heading, the number through
`<ValueWithUnit>`, and the caveat directly beneath it. No warning triangles, no
amber panels. A limitation stated calmly reads as confidence; a limitation dressed
as an alert reads as a bug.

---

## Your rows

### `p4-04` Top Weather Drivers — **one of Phase 6's two recorded FAILs**

Read `tasks/phase6/04-pulga.md` lines 87–124 before touching this. Precisely:

- `POST /runoff/predict` returns **real** drivers — `rain_self_percentile`,
  `rain_over_p90`, `precip_prior_1d_mm`, `precip_prior_3d_mm`. Your half is real.
- **Nothing threads them into `/explain`.** The caller must hand-assemble the list.
- Fed in with the key `key` → **HTTP 500**, number-fidelity guard, correctly.
- Renamed to `feature` → renders *"…is classified as high risk because rain self
  percentile, rain over p90, precip prior 1d mm and precip prior 3d mm."* No verb.
  **None of the four real names exist in `DRIVER_PHRASE`** (`backend/src/rag/explain.py`,
  7 entries). Every real name falls through to `feature.replace("_"," ")`.
- `tests/test_explain_fidelity.py` only uses hand-typed names that already match, so
  the gap has been invisible since Phase 3.

- [x] Decide with Pulga where the vocabulary bridge lives — `DRIVER_PHRASE` or the
      frontend's `driver.*` i18n keys (24 exist already). **Write the decision down.**
      **Decision (9 Aug 2026, Mahdi — Pulga not reachable live, recorded for review):**
      the bridge lives in backend `DRIVER_PHRASE` (`backend/src/rag/explain.py`), not
      in the frontend's `driver.*` keys. Reason: `driver.*` is 24 short noun-phrase
      axis labels for `DriverBars.tsx`'s bar chart ("Rainfall, previous day") — they
      are not shaped to sit grammatically after "because" in a sentence, and pasting
      them in unchanged just trades one noun-pile for another. `DRIVER_PHRASE` needs
      real verb-bearing clauses. What *is* reused from `driver.*`: the terminology —
      each new entry names the concept with the same words the chart already uses in
      both languages, so a driver is never called one thing in the chart and another
      in the sentence. Added the model's real top-4 drivers
      (`rain_self_percentile`, `rain_over_p90`, `precip_prior_1d_mm`,
      `precip_prior_3d_mm`) to `DRIVER_PHRASE` in both `en`/`ar`.
      Also closed the other half of Phase 6's FAIL repro, which the checklist here
      didn't name but the verdict did: `/runoff/predict`'s `drivers` field is named
      `key` (`DriverOut`), not `feature` — `_driver_clause` now accepts either via a
      `_feature_name()` helper, and `rainfall_percentile` is only required to appear
      in `source_numbers`/the fidelity check when a driver actually consumed `{pct}`
      (previously it was required unconditionally, which is what produced the 500
      when real dynamic drivers — none of which use `{pct}` — were supplied alongside
      it). Verified live: real `/runoff/predict` output for `AQ-C01`/`AQ-2016-10-28`
      fed into `/explain` unmodified now returns 200 with a grammatical EN/AR
      sentence, not the prior 500 or noun-pile. New regression tests:
      `test_real_model_drivers_produce_grammatical_phrases`,
      `test_runoff_predict_driver_shape_is_accepted` in `tests/test_explain_fidelity.py`.
- [x] The bridge must be bilingual. `driver.*` keys exist in both locales; use them.
      Done as part of the decision above — both `en`/`ar` entries added, terminology
      aligned with `driver.*`.
- [ ] `DriverBars.tsx` shows signed contributions **diverging from a centre line**,
      not a hue pair. Keep that. **Untouched** — this row was already correct and
      out of scope for this fix (see note below).
- [x] A driver with no phrase must render its raw name and be visibly incomplete —
      never silently prettified into something that reads authored. Unchanged
      fallback behaviour (`feature.replace("_", " ")`), still covered by
      `test_unknown_driver_is_shown_not_dropped`.

**Scope note:** `DriverBars.tsx` already renders these same four driver names
correctly — `frontend/src/i18n/locales/{en,ar}/common.json`'s `driver.*` bundle
already had all four (`rain_self_percentile`, `rain_over_p90`, `precip_prior_1d_mm`,
`precip_prior_3d_mm`) before this fix, and `RiskCard.tsx` already feeds it real
`/runoff/predict` drivers. The gap was `/explain`'s sentence only. Also worth noting:
**no frontend code calls `/explain` yet** — there is no live UI surface for this
sentence today (checked: zero matches for `explain`/`Explain` in `frontend/src`
besides one unrelated comment). This fix makes the backend integration correct and
tested; wiring an actual `/explain`-consuming panel into the UI is not part of this
row's checklist and was not attempted here.

### `core-A` Runoff classifier — `/dashboard` risk cards

- [x] Cards read live `/runoff/predict`, not `fixtures/predictions.json`.
      **Decision (9 Aug 2026, Mahdi):** "live" does NOT mean a browser-side network
      call — `scripts/frontend_predictions.py`'s own docstring is explicit that
      derive-and-commit is deliberate: DoD item 9 ("works with wifi off") is a hard
      gate, `frontend/tests/wifi-off.offline.spec.ts` DNS-blackholes the browser
      resolver, and `predictions.ts`'s own header comment names the same reason. A
      literal live fetch would break that gate. What "live" means here instead:
      **the committed fixture must reflect the currently-registered model**, not a
      stale one — and it was stale. Fixture said `runoff_weighted_gbm_2194b48_…`
      (3 Aug); the actually-registered model was `runoff_weighted_gbm_6de325c_…`
      (6 Aug) — verified live: started the API, called `/runoff/predict` directly,
      confirmed the registry had moved on. Regenerated
      `frontend/public/fixtures/predictions.json` via the existing script.
      Side finding worth flagging to whoever owns `core-B`: the new fixture's
      `sediment_class` is no longer `null` on any row (was unanchored under the old
      model) — it now reads real classes (`"Low"`/`"High"`/`"Extreme"`), meaning the
      sediment-proxy anchor described in root `CLAUDE.md`'s opening line may already
      be closed as of the 6 Aug model. Nothing in the frontend renders
      `sediment_class` yet (grepped — zero references), so this is inert today, but
      note the casing mismatch before building `core-B`'s UI: the fixture's script
      (`scripts/frontend_predictions.py`) takes the model's raw casing (`"Low"`)
      unmodified, while the live API's `main.py` lowercases it (`"low"`) — the two
      paths disagree and whichever renders it should normalise.
- [x] Show `model_version` **or** a provisional flag on every card — a Playwright spec
      already asserts exactly-one-of on all five cards. Already correctly wired
      (`api/risk.ts`'s `riskFromPredictions`/`riskFromSeries`) before this fix;
      verified still green after the fixture regen —
      `phase2-vertical-slice.spec.ts:117` passes against the new model version.
- [x] `predicted_runoff_m3` is deliberately `null` (classifier, not regressor).
      Render the gap; do not compute a substitute. **Was a real gap**: the field
      didn't exist anywhere in the frontend (typed nowhere in `predictions.ts`,
      never threaded through the fixture script, never rendered on `RiskCard.tsx`)
      — not a rendered gap, just silent absence. Added: the fixture script now
      carries `predicted_runoff_m3` (always `None` — `predict_one()` never returns
      this key, confirmed by reading `backend/src/models/runoff_model.py`), threaded
      through `Prediction`/`RiskCardData`, rendered via the existing `ValueWithUnit`
      gap convention plus a one-line caveat (`risk.predictedVolumeCaveat`, EN+AR)
      stating it's a classifier not a regressor. Updated
      `phase2-vertical-slice.spec.ts:103`'s stale "zero gaps on a real-model card"
      assertion — that invariant predates this field and is now permanently false by
      design; rescoped it to the runoff-probability row specifically, which is what
      the test actually intends to check. Full suite (vitest + the three Playwright
      specs covering this view, 38 tests) verified green after the change.
- [ ] Without a matching `event_id` the API suppresses drivers and attaches a
      **critical** caveat saying the result is fixed and meaningless. Render it.
      **Not done** — out of scope for this pass. The committed fixture is always
      derived with a matching `event_id` (`AQ-2016-10-28`), so this path never
      fires on the demo's real data path; it would only matter for a live caller
      hitting `/runoff/predict` with no `event_id`, and (same finding as `p4-04`)
      no frontend code calls the live endpoint at all today. Flagging rather than
      building speculative UI for a path nothing currently exercises.

### `core-B` Sediment proxy — the anchor

- [x] `relative_sediment_intensity` and `relative_sediment_intensity_source` visible
      in the formula inspector (Pulga's `p4-12` surface — coordinate).
      **Status (9 Aug 2026, Mahdi):** the backend half is solid and *not* stale —
      unlike `core-A`'s fixture, `tasks/phase6/evidence/core-b/
      exposure_calculate_AQ-O02.json` was generated the same day as the current
      `runoff_weighted_gbm_6de325c_…` model (confirmed by reading its own
      `formula_terms.model_versions`), so Phase 6's PASS still holds against the
      live model — re-verification found nothing to fix. Both fields are real and
      present today: `relative_sediment_intensity: 0.0839`,
      `relative_sediment_intensity_source: "sediment_index 13,313 = 0.09x
      AQ-2016-10-28, squashed by r/(1+r) to 0.084 (class Low); anchor maps to
      0.500"`.
      **`p4-12` itself is Pulga's row and reads "Not started"** — I did not build
      it; per the plan file it's the click-to-see-why `formula_terms` inspector at
      `/reef-zones/:id`, a bigger, separately-owned surface. **Coordination note
      for whoever builds it:** both fields are already in every
      `/exposure/calculate` result's `formula_terms` dict today (`main.py`
      populates `relative_sediment_intensity_source` at the point it merges
      `formula_terms` — search that key), so the inspector can read them directly;
      nothing further needs to ship from the model side for p4-12 to consume this.
      One live consumer already exists ahead of p4-12: `SideRail.tsx`'s
      `rail.exposureNote` shows `relative_sediment_intensity` for R-01 today.
- [x] State it is a **formula, not a fitted model**, anchored to the documented
      24,400 t event. Nothing in `sediment_proxy.py` is trained.
      `sediment_proxy.py`'s own docstring already says this in those words
      ("A FORMULA, NOT A MODEL. Nothing here is trained") and always has —
      confirmed by reading it, nothing to change there. The actual gap: **no
      user-facing text stated this anywhere** — `relative_sediment_intensity_source`
      gives real provenance numbers but never says "formula" or "not trained", and
      grepping the frontend and docs for that framing near "sediment" turned up
      nothing. Fixed the one surface that exists today: `rail.exposureNote`
      (EN+AR) now names the anchor mass explicitly (≈24,400 t, previously just
      "the Oct 2016 anchor") and states "a deterministic formula, not a fitted
      model — nothing here is trained." Verified: typecheck clean, full 38-test
      Playwright run (which exercises `SideRail`) still green — no test pinned the
      old string.

### `p4-09` "AI Never Saw This Storm" · `p4-11` Simple vs Smart Guess — **built, 9 Aug 2026**

Both read `GET /api/v1/models`. Built as one model-honesty panel.

- [x] `temporal_holdout_AP` (recorded 0.5923) framed as a **temporal holdout** — the
      model never trained on this storm. Rendered against its own
      `temporal_holdout_baseline_AP` (0.2083), with the split's real
      `cutoff_year`/`train_rows`/`test_rows`, plus a fact from the same ledger
      entry not asked for by name but directly on-topic: the anchor event
      (`AQ-C01`, Oct 2016) ranked at the **93.1st percentile** of risk among 1,102
      unseen days for its own catchment in this held-out set — real supporting
      evidence for the "never saw it, still ranked it high" claim.
- [x] `baseline_mean_AP` (0.2004) vs `mean_AP` (0.7474), both labelled, both from the
      endpoint.
- [x] ⚠️ **Quote 0.662, not 0.741**, wherever the claim is "predicts runoff from
      independent inputs" — root `CLAUDE.md` is explicit. Any ERA5-sourced feature
      leaks the label. If you show 0.7474, label it as the shipped CD− set, not as
      independent-input performance.
      **The 0.662 number does not exist in `model_versions.jsonl` at all** —
      confirmed by reading it. It's `scripts/22_label_leakage_diagnostic.py`'s
      one-off 15-feature ablation (`reports/model/label_problem.md`,
      `docs/model_card.md`), a different, never-shipped model, not a metric of
      this artefact. Added it as its own constant,
      `LABEL_LEAKAGE_ABLATION` in `backend/src/models/runoff_model.py`, included
      in `model_info()`'s response under `label_leakage_ablation` — so it now
      travels with the served model's record with its own `source` field, rather
      than needing to be hardcoded into frontend prose from a report only I had
      read.
- [x] Phase 5 and Phase 6 files quote **different numbers** (0.662 vs 0.5923) for
      overlapping claims. Reconcile from `model_versions.jsonl` and state which is
      which. Do not average them.
      **Reconciled as three numbers, not two** — `mean_AP` (0.7474, LOCO, unseen
      catchment), `temporal_holdout_AP` (0.5923, unseen time period) and
      `label_leakage_ablation.defensible_mean_AP` (0.6623, independent inputs, a
      different model) each answer a different claim; the panel's "Which number
      answers which claim" section states this explicitly with an inline warning
      against averaging or substituting. This exact conflation was already caught
      once, independently, in `tasks/phase6/00-master-test-matrix.md`'s `core-A`
      row ("Finding, not fixed": the row asked to reproduce 0.662 from the ledger
      and it isn't there) — this panel is the fix for that finding, not a new one.

**Architecture decision, matching `core-A`'s:** built as a **committed fixture**
(`frontend/public/fixtures/models.json`, derived by a new `models()` function in
`scripts/frontend_panels.py`), not a live `/api/v1/models` call — DoD item 9
("works with wifi off") applies here exactly as it does to `core-A`'s predictions,
and every other honest panel (`validation.json`, `provenance.json`, etc.) already
follows this pattern. Removed `live.ts`'s `fetchModels()`, which called the live
endpoint directly and had zero callers anywhere in the frontend — dead code left
over from before the fixture pattern was settled; keeping it next to the real,
DoD-compliant path risked someone wiring a live call in later. New overlay panel
`ModelHonestyPanel.tsx`, reachable from the masthead (`data-open-overlay="model"`,
`overlay.model` i18n key, EN "Model honesty"), same `Dialog`-based mechanism as
`Validation`/`Provenance`/`Limitations`/`Assistant`. Added to `hardening.spec.ts`'s
per-overlay axe loop. Verified: typecheck, lint, vitest, and a 39-test Playwright
run (three specs covering the dashboard, all overlays and the axe/keyboard
suites) all green. Screenshots EN/AR × light/dark under
`tasks/phase7/evidence/model-honesty/`.

One real correctness bug caught by actually looking at a screenshot rather than
trusting the automated tests: my first draft of the copy read "trained only on
data through 2015" — wrong, since `model_versions.jsonl`'s own `_note` says
training data *ends before* 2015 (`cutoff_year: 2015` means train ≤2014, test
≥2015). Fixed to "before {{year}}" / "{{year}} onward" in both languages.

### `p4-17` The Gap Chart — `/limitations` — **built, 9 Aug 2026**

- [x] Draw the label-frequency gap: our target fires on **3.21%** of calendar days
      against the literature's **0.156%** — 21× too generous, and **78×** on days
      actually sampled.
      Two-bar chart (`GapBars` in `LimitationsPanel.tsx`), linear-scaled to the
      larger value on purpose — the 0.156% bar reads as a sliver next to 3.21%'s,
      which is the finding, not a rendering problem to fix. Both bars carry their
      exact percentage in text regardless (2 and 3 decimal places respectively,
      matching each number's own source precision — not padded to match each
      other, which would claim a digit the source never gave).
      **Caught and fixed a fabrication while writing this**: my first draft of
      the companion prose item cited "288 of 8,973" days — I had back-calculated
      8,973 from 288/3.21% and presented it as if sourced. It is not; the report
      states only the share, not a total day count. Removed the invented number
      before it reached the fixture. Also caught a wrong script attribution
      (guessed `scripts/22_label_leakage_diagnostic.py` for the 288-day count;
      grepped it, the number isn't in that file — the real source is
      `reports/model/label_problem.md` §3) and fixed it before committing.
- [x] State that it is a **detection** failure, not a scaling one: ERA5 is dry on 35%
      of IMERG-wet days, and October 2016 is among the misses. No threshold fixes it.
      Stated in the panel and in the new item 13 of `docs/pitch_limitations.md`,
      quoting the same figures root `CLAUDE.md`'s label rule section gives: 35%/20%
      ERA5-dry rates, the 276-catchment-days/1-positive check, and the October 2016
      anchor's own ERA5 (0.77 mm, p92.6) vs IMERG (9.58 mm, p99.5) numbers.

**Data path:** `scripts/frontend_panels.py`'s `limitations()` gained a
`label_frequency_gap` structured field (frozen findings from
`reports/model/label_problem.md`, same category as `sediment_proxy.py`'s
`ANCHOR_MASS_T` — not live-computed). Regenerated only `limitations.json`
directly via the function, not the script's full `main()` — running the whole
thing earlier in this session (for an unrelated row) pulled in unrelated
provenance/corpus/sources drift from other people's concurrent doc changes, so
this time I called `limitations()` in isolation and diffed before committing.

**Found in the process, not caused by it:** regenerating surfaced that
`docs/pitch_limitations.md` items 10, 11 and 12 were already written and
committed to the doc but had **never once been in the committed
`limitations.json`** — the fixture was frozen at 9 items while the doc moved to
12. Same "committed fixture goes stale relative to its source" pattern as
`core-A`'s model version, a third occurrence of it in this codebase this phase.
Regenerating picked all three up; `/limitations` now genuinely shows all 13.
Updated `scene-walk.spec.ts`'s hardcoded expectation (`toHaveCount(9)` →
`toHaveCount(13)`) accordingly.

Verified: typecheck, lint, vitest, and a 39-test Playwright run all green.
Screenshots EN/AR × light/dark under `tasks/phase7/evidence/gap-chart/`.

### `p4-C` Transmission Loss Reality Check — `/dashboard` drawer — **fixed, 9 Aug 2026**

Backend PASS: `transmission_loss_override` echoes exactly. The slider itself
(`ScenarioDrawer.tsx`, 20–85%, wired live via `useLiveExposure`) already existed —
Ali/Pulga's plumbing was done. Three real gaps found in my half:

- [x] Slider 20–85%, default 0.525, wired to the real parameter (Pulga owns the
      drawer plumbing — you own the honesty framing).
      **Was wrong.** `uiStore.ts`'s `SCENARIO_DEFAULTS.transmissionLoss` was a
      plain `50`, independently guessed rather than sourced from
      `sediment_proxy.py`'s own `TAU_DEFAULT` (0.525). Fixed to `52.5`. Found and
      fixed the **same** mistake a second time in `api/risk.ts`'s stand-in-index
      fallback constant — its own comment said "midpoint of that range" and then
      used `0.5`, not the actual midpoint 0.525. Two independently-invented
      copies of one constant, both wrong the same way — fixed both to `0.525`,
      one citing the other so they can't drift apart again unnoticed. Verified
      live: `aria-valuenow` on the slider now reads `52.5` on load.
- [x] State it is a **borrowed Negev proxy**, not measured for these wadis. `b2`
      would have replaced it and was not built.
      `scenario.transmissionLossNote` previously read "Measured range is
      20–85%" — technically true (measured in the Negev) but worded exactly like
      the overclaim this project exists to prevent; it never named Negev or said
      "borrowed." Reworded (EN+AR): "The 20–85% range is borrowed from Negev
      desert catchments — not measured for these wadis..."
      **Also closed Phase 6's own unfixed finding**, not asked for by name in
      this checklist but directly on-topic: the code comment above
      `sediment_proxy.TRANSMISSION_LOSS_BASIS` still claimed "learned" was
      unbuilt because no per-catchment measured tau existed to train against.
      That's stale — Karam found real data (Cataldo et al. 2010) and a learned
      model *was* built and tested (7 feature combos × 2 model types, LOSO
      validated) and scored worse than the mean everywhere (negative R²,
      `tasks/mahdis-features-handoff/RESULT_b2_learned_model_tested_and_rejected.md`).
      Rewrote the comment to state the real, stronger finding: tested and
      rejected, not merely unbuilt.

Verified: backend suite (467 passed), frontend typecheck/lint/vitest, and a
39-test Playwright run all green. Screenshots EN/AR × light/dark under
`tasks/phase7/evidence/transmission-loss/`.

### `p4-D` Culvert & Drainage Correction Map — `/dashboard` layer

- [ ] 27 real culverts from `GET /api/v1/outlets`: `culvert_verdict`,
      `nearest_culvert_m`, `unmodelled_coastal_culverts`.
- [ ] `AQ-O02` and `AQ-O03` carry **"CANDIDATE CORRECTION — unmodelled path to the
      sea"**. Show it on the feature, not in a legend.
- [ ] **There is no per-culvert endpoint** — only per-outlet summaries. Do not imply
      a per-culvert dataset you cannot serve.
- [ ] Distances are EPSG:32636. A distance in degrees is wrong; one was overstated by
      14.8% once already.

### `p4-J` Post-Storm Damage Estimate — `/reports`

- [ ] Report a **class** — Low / Medium / High / Extreme — from `sediment_class`.
- [ ] 🔴 **A tonnage number anywhere here for a non-anchor event is an automatic
      FAIL.** `tasks/phase6/02-mahdi.md` line 23. The 24,400 t figure belongs to
      `AQ-2016-10-28` and to no other event.

### `p4-H` Offline Emergency Mode — with Ali

- [ ] `frontend/tests/wifi-off.offline.spec.ts` exists. **Nobody has confirmed it has
      ever been run and passed.** Run it.
- [ ] Then do the physical check: wifi off, load the app, pan the map, switch to
      Arabic. The DNS-blackhole spec is a proxy; the physical run is the gate.
- [ ] Sign it in this file with the date. Both Phase 5 boxes are still `[ ]`.

### `b1`, `b2`, `b3`, `b9` — the four that do not exist

Every checklist box in `tasks/phase5/02-mahdi.md` for these is unchecked. None has a
backend. `b1` and `b9` have no data either; `b2` now does (see below).

- [ ] **Do not build UI for them.** A polished empty card implies a pipeline.
- [ ] Name all four on `/limitations`, each with one sentence saying what it would
      have done and what stands in for it today:
      - `b1` plume segmentation → masks are manual
      - `b2` learned transmission loss → the Negev proxy is in use
      - `b3` cross-site transfer → validated on exactly one site
      - `b9` culvert-conflict detector → the 27 culverts are a manual result

**Two of these moved on 8 Aug — check the handoffs before you write the sentences:**

- **`b2` is no longer data-blocked.** Karam found a real, open-access, multi-catchment
  measured dataset — Cataldo et al. (2010), *The Open Hydrology Journal* — 90 measured
  transmission-loss values across 13 named systems, extracted to
  `tasks/mahdis-features-handoff/data/cataldo_2010_measured_transmission_loss.csv`.
  He is explicit that D10/K are proxies, not B2's exact variables. The honest sentence
  is now "data exists, model not built", **not** "no data exists".
- **`b3` was scoped out on purpose**, not silently dropped. One site is the honest
  state to ship. The limitation sentence must not imply transfer learning was tested
  and failed — it was not attempted, deliberately.
- [ ] Write the sentences here when done, so the matrix can quote them.

---

## Done means

- [ ] `p4-04` renders a grammatical, bilingual driver sentence from real driver names
- [ ] Risk cards read the live model, with version-or-provisional on every card
- [ ] The model-honesty panel quotes the right AP for the right claim
- [ ] No tonnage appears for any non-anchor event, anywhere
- [ ] Wifi-off physically verified and signed with a date
- [ ] Four absent features named on `/limitations`
- [ ] Screenshots under `tasks/phase7/evidence/`, EN + AR, light + dark
- [ ] `npm run qa` green, `qa_frontend_tokens.py` exit 0
