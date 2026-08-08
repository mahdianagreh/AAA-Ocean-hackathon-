# Phase 7 — Pulga

**Owns:** the exposure engine, RAG, reports, site scoring, coral health, adaptive
sampling.
**Pages:** `/reef-zones`, `/reef-zones/:id`, `/alerts`, `/reports`, `/sites/score`,
`/assistant`, and the scenario drawer on `/dashboard`.
**Rows:** `core-D`, `core-E`, `p4-06`, `p4-07`, `p4-12`, `p4-15`, `p4-A`, `p4-E`,
`p4-I`, `b4`, `b5`, `b7`, `b8`.

Read [`00-phase7-plan.md`](00-phase7-plan.md) and
[`00-design-system.md`](00-design-system.md) first.

You have the most rows and the most already-passing backends. Phase 6 gave you eight
verdicts; **six of them were backend-only.** Phase 7 is where those become screens.

---

## The brand, in the two lines you will actually use

Never write a colour — `python3 scripts/qa_frontend_tokens.py` fails on a hex literal
in `frontend/src/`.

```
grounds   bg-canvas  bg-surface  bg-surface-2   borders  border-hairline
ink       text-ink   text-ink-2  text-ink-3     accent   text-accent
hazard    BAND_CLASS from src/api/types.ts — never hand-map a band to a colour
```

Deep Navy `#0A1F4D` · Ocean Blue `#0D3D7A` · Marine Teal `#007A99` · Aqua `#00B7C3`
· Foam White `#E6F7FA`. Montserrat; every number through `<ValueWithUnit>`. Radii
8/12/16/20; `<Card>` = white, 20px, hairline, 24px padding. `<PageShell>` + `<Section>`
for every page.

**Your pattern:** you own the screens where a wrong impression is most expensive — a
proposed weight mistaken for a live one, an AI draft mistaken for a reviewed report.
Use **structural** separation, not tonal: separate cards, an explicit `IN USE` /
`NOT IN USE` chip, a badge that cannot be styled away. Colour alone never carries any
of it.

---

## Your rows

### `core-D` + `p4-A` + `p4-I` — `/reef-zones`

The list page is **Done** and is currently the best proof in the app that the data is
real. Do not regress it. What remains:

- [ ] **`p4-I` Coastal Zone Risk Comparison.** Phase 6 finding: only 2 of 5 outlets
      ever reach a zone, and each reaches exactly one — `AQ-O01` none, `AQ-O02` R-03,
      `AQ-O03` R-08, `AQ-O04` none, `AQ-O05` R-08. **One call never returns >1 zone.**
      The comparison view must call all five outlets and assemble client-side.
      `/alerts` alone cannot produce it.
- [ ] `AQ-O01` carries **96% of discharge** and reaches **zero** zones at 24 h. That
      is flagged undiagnosed in Phase 4 and is still open. Show it as a finding on the
      comparison, not as an empty row.

### `p4-12` Click-to-See-Why — `/reef-zones/:id`

Not started. This is the single most convincing thing you can build this phase.

- [ ] Click any score → the full `formula_terms` inspector. 25 real keys, including
      `measure_crs: EPSG:32636`.
- [ ] Show it as a **product**: term × term × term = score, each term labelled with
      where it came from.
- [ ] Two terms are honest placeholders and **say so in the payload** — surface both:
      `intensity = 0.5` when no catchment feature row, and `confidence_adjustment`
      prefixed `PLACEHOLDER 0.6 --` when no GEFS row.
- [ ] `zone_fraction_affected` renders as **a fraction of the named zone**, never a
      bare km². `hardening.spec.ts` fails the build on false-precision phrasing.

### `b8` Coral Health Vision — `/reef-zones/:id` — **the hard safeguard**

Phase 6 PASS end to end. The UI must not undo it.

- [ ] Photo upload → `predicted_class`, `confidence`, **`model_basis`**.
- [ ] When `model_basis === 'heuristic_rule_v1'`: state plainly it is a colour and
      texture heuristic, **not a trained model**, 7 handcrafted features, confidence
      **capped at 0.55**, and that zero labelled reef photos exist in the repo.
      🔴 **Never present it as a CNN or a neural network.**
- [ ] The **proposed** sensitivity weight and the **live** one must be structurally
      inseparable — separate cards, `IN USE` / `NOT IN USE` chips, and one sentence
      saying the proposal changes no score and awaits marine-scientist review.
      This is Standing Law rule 13 from Phase 5 and the phase's single non-negotiable.
- [ ] `proposed_value` is `null` until 3 photos. Render the reason, not a blank.
- [ ] Approval needs `reviewer` + `reasoning` (422 without). There is **no auth** —
      say the name is recorded as typed and is not verified.

### `b7` Adaptive Sampling — `/reef-zones/:id`

Phase 6 PASS **(infrastructure only)**.

- [ ] `adjusted_priority` + `adjusted_priority_status` visible; it can only **dampen**
      (bounded to `[0, risk_score]`).
- [ ] 🔴 The 5 feedback rows in the demo were **synthetic**. Real deployment history
      does not exist. The UI must say "infrastructure, not a working feature today".
      Phase 5 marked this explicitly not demoable.

### `p4-07` + `p4-15` — the scenario drawer on `/dashboard`

Backend PASS on both. The frontend is the known failure.

- [ ] 🔴 **`ScenarioDrawer.tsx` does not call `rainfall_multiplier` or
      `transmission_loss_override` today.** Phase 6 named this: if it is still
      bypassing the real parameter, that is a FAIL. Wire it.
- [ ] Ranges are enforced server-side: multiplier 0.5–2.0, transmission loss
      0.20–0.85. Clamp in the UI too, and show both echoed back in `formula_terms`.
- [ ] Presets (heavy rain / dry season / worst case) set real parameter values.
- [ ] Keep the existing honesty copy: these controls move a transparent index, not a
      re-run model. Scenario mode deliberately falls back to the stand-in index
      because re-deriving a GBM in the browser would be inventing a prediction.

### `core-E` + `p4-06` — `/assistant`

- [ ] ⚠️ The old `panels/Assistant.tsx` answers **entirely client-side against a
      fixture corpus and never calls the backend.** Phase 5 called that "an oversight,
      not a decision". The route page must call the real `POST /api/v1/ask`.
- [ ] Every answer renders with `source_file` + `section` + `excerpt`. **An uncited
      answer must not render as an answer** — show the no-sourced-answer state and
      what was searched (`corpus_files_searched`).
- [ ] There is **no LLM anywhere in this path** — lexical retrieval plus extractive
      composition. `generate_with_llm()` permanently raises `NotImplementedError`.
      Do not describe it as generative.
- [ ] Answers come back in the language asked; full RTL.
- [ ] The corpus excludes `docs/Ali/research/*` deliberately. If a question falls
      outside, say so rather than reaching.

### `b5` — `/reports`

- [ ] `status` badge — `ai_drafted` vs `human_reviewed` — **unmissable and never
      defaulted away.** A drafted report shown without it is the exact risk.
- [ ] `PATCH /reports/{id}/review` is the **only** path to `human_reviewed`.
- [ ] ⚠️ **`GET /api/v1/reports` does not exist.** You cannot list reports. Keep
      session-generated ones in state and **say on the page** that a persistent list
      is unavailable because the backend exposes no list endpoint. Do not fake a list.
- [ ] Every claim renders with its `source` pointer (`exposure_run:sim_…#R-08`,
      `docs/data_dictionary.md §4`, the Kalman citation).
- [ ] "Generate Report" reachable from any completed event.

### `b4` — `/sites/score`

- [ ] Bounding-box input → six criteria C1–C6 with citations.
- [ ] `score` is `float | None`. **`null` renders as "insufficient data", never 0.**
      The Mid-Atlantic control box correctly returns nulls — that behaviour is the
      feature.
- [ ] `C6` takes no data argument and is effectively constant. Do not present it as
      an independent measurement.
- [ ] The **"validated on exactly one site"** caveat ships on every response. Render
      it next to every score, not once at the bottom.

### `p4-E` Enclosed Harbour Warning

- [ ] `AQ-O04` discharges into an enclosed harbour basin; a plume released there
      settles in the basin. The critical caveat fires on every relevant response.
- [ ] Render it wherever `AQ-O04` appears. 🔴 **Do not demo that outlet without it.**

---

## One behaviour you need to design an answer for

`/alerts` is derived from the **single most recent** stored exposure run. Several
pages trigger a run on the default outlet `AQ-O01`, which reaches no zone — so simply
visiting Replay or Validation **empties the alerts feed**. Exposure results are also
TTL-cached, so re-posting identical parameters returns the original `run_id` and never
becomes "latest" again.

- [ ] Decide the product answer: show the run's identity and timestamp on the feed,
      or list recent runs, or pin the feed to a chosen run. `store.recent_runs()`
      exists in `exposure/store.py:191` **but is not routed**.
- [ ] Whatever you choose, the empty state must keep explaining itself. "No zone was
      reached" and "a zone was reached with negligible effect" are different sentences.

---

## Done means

- [ ] The scenario drawer sends real parameters and the response visibly changes
- [ ] `/assistant` calls the live endpoint and never renders an uncited answer
- [ ] Proposed vs live sensitivity weight cannot be confused by anyone, in any theme
- [ ] Every report shows its status badge; the no-list-endpoint fact is on the page
- [ ] `null` site scores read "insufficient data" everywhere
- [ ] The formula inspector shows all 25 terms with both placeholders surfaced
- [ ] Screenshots under `tasks/phase7/evidence/` per page, EN + AR, light + dark
- [ ] `npm run qa` green, `qa_frontend_tokens.py` exit 0
