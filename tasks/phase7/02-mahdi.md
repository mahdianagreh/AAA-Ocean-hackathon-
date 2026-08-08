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

### `p4-04` Top Weather Drivers — **the one recorded FAIL in Phase 6**

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

- [ ] Decide with Pulga where the vocabulary bridge lives — `DRIVER_PHRASE` or the
      frontend's `driver.*` i18n keys (24 exist already). **Write the decision down.**
- [ ] The bridge must be bilingual. `driver.*` keys exist in both locales; use them.
- [ ] `DriverBars.tsx` shows signed contributions **diverging from a centre line**,
      not a hue pair. Keep that.
- [ ] A driver with no phrase must render its raw name and be visibly incomplete —
      never silently prettified into something that reads authored.

### `core-A` Runoff classifier — `/dashboard` risk cards

- [ ] Cards read live `/runoff/predict`, not `fixtures/predictions.json`.
- [ ] Show `model_version` **or** a provisional flag on every card — a Playwright spec
      already asserts exactly-one-of on all five cards.
- [ ] `predicted_runoff_m3` is deliberately `null` (classifier, not regressor).
      Render the gap; do not compute a substitute.
- [ ] Without a matching `event_id` the API suppresses drivers and attaches a
      **critical** caveat saying the result is fixed and meaningless. Render it.

### `core-B` Sediment proxy — the anchor

- [ ] `relative_sediment_intensity` and `relative_sediment_intensity_source` visible
      in the formula inspector (Pulga's `p4-12` surface — coordinate).
- [ ] State it is a **formula, not a fitted model**, anchored to the documented
      24,400 t event. Nothing in `sediment_proxy.py` is trained.

### `p4-09` "AI Never Saw This Storm" · `p4-11` Simple vs Smart Guess

Both read `GET /api/v1/models`. Build them as one model-honesty panel.

- [ ] `temporal_holdout_AP` (recorded 0.5923) framed as a **temporal holdout** — the
      model never trained on this storm.
- [ ] `baseline_mean_AP` (0.2004) vs `mean_AP` (0.7474), both labelled, both from the
      endpoint.
- [ ] ⚠️ **Quote 0.662, not 0.741**, wherever the claim is "predicts runoff from
      independent inputs" — root `CLAUDE.md` is explicit. Any ERA5-sourced feature
      leaks the label. If you show 0.7474, label it as the shipped CD− set, not as
      independent-input performance.
- [ ] Phase 5 and Phase 6 files quote **different numbers** (0.662 vs 0.5923) for
      overlapping claims. Reconcile from `model_versions.jsonl` and state which is
      which. Do not average them.

### `p4-17` The Gap Chart — `/limitations`

- [ ] Draw the label-frequency gap: our target fires on **3.21%** of calendar days
      against the literature's **0.156%** — 21× too generous, and **78×** on days
      actually sampled.
- [ ] State that it is a **detection** failure, not a scaling one: ERA5 is dry on 35%
      of IMERG-wet days, and October 2016 is among the misses. No threshold fixes it.

### `p4-C` Transmission Loss Reality Check — `/dashboard` drawer

Backend PASS: `transmission_loss_override` echoes exactly.

- [ ] Slider 20–85%, default 0.525, wired to the real parameter (Pulga owns the
      drawer plumbing — you own the honesty framing).
- [ ] State it is a **borrowed Negev proxy**, not measured for these wadis. `b2`
      would have replaced it and was not built.

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

Every checklist box in `tasks/phase5/02-mahdi.md` for these is unchecked. They have
no backend and no data.

- [ ] **Do not build UI for them.** A polished empty card implies a pipeline.
- [ ] Name all four on `/limitations`, each with one sentence saying what it would
      have done and what stands in for it today:
      - `b1` plume segmentation → masks are manual
      - `b2` learned transmission loss → the Negev proxy is in use
      - `b3` cross-site transfer → validated on exactly one site
      - `b9` culvert-conflict detector → the 27 culverts are a manual result
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
