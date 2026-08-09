# Phase 7 — Abd — execution plan

Companion to [`05-abd.md`](05-abd.md). That file says *what* is owed; this one says
*in what order*, *what gates each step*, and *what would make it wrong*.

**Written:** 9 August 2026, against the `e558a60` merge. **Window:** 9 → 13 Aug.

---

## What changed under the task file before you started

`05-abd.md` was written against the pre-merge tree. The 8 Aug merge landed working
versions of two of the four rows. Read this table before you build anything, or you
will rebuild `ValidationPage` from scratch.

| Row | Task file implies | Actually on disk at `e558a60` |
|---|---|---|
| `core-C` plume on `/dashboard` | qualifications not on screen | `PlumeMapPanel.tsx` renders `plume_source` as a form badge. **No currents provenance, no wind note, no diffusion-vs-drift sentence.** Its docstring is stale — says `plume_source` "is `'stub'` today". |
| `p4-01` Replay | "not a replay yet" | `ReplayPage.tsx` — live frames, live exposure, requested-vs-shown split, anchor-only `Empty` branch, forcing note, caveats, model versions. **Missing the rainfall/runoff/sediment stages and the `AQ-O01` zero-intersection statement.** |
| `p4-10` Validation | "still reads a fixture" | **Already live** on `GET /api/v1/events/{id}/mooring`. Per-field provenance + uncertainty, `series_available` false-state, 404-as-not-error, plain-text-before-table, `modelled_blocked_on`, calibration fit. |
| Satellite NO-GO | needs its own section | **Already its own `<Section>`**, driven by `record.satellite` rather than typed copy. |
| `p4-14` Journey | terrain absent, specs fail | `public/terrain/{10,11,12}` and `public/basemap-raster/` **exist on this checkout**. Verify before regenerating. |

**The net effect:** your remaining work is narrower and more surgical than four rows
of unchecked boxes suggest. Spend the saved time on the one thing that is genuinely
blocked, below.

---

## The one blocking dependency — do this first or two phases stall

`core-C` requires the currents-placeholder provenance and the windage tie-break on
screen. Neither is reachable from the frontend today:

- `GET /api/v1/plume/map/frames` ([`main.py:1361`](../../backend/src/api/main.py))
  returns `event_id, outlet_id, frame_count, frames, basemap_present, plume_source`.
  No `provenance`, no `caveats`.
- The string `"PLACEHOLDER: ConstantCurrentField(0, 0) -- no cached historical
  current …"` is built at [`main.py:1121`](../../backend/src/api/main.py) and lands in
  `PlumeResult.provenance[]` — reachable only via `POST /api/v1/plume/simulate`.
- `windage_fraction` lives in `data/models/plume_calibration.json` via
  `_load_plume_calibration()`, and in `PlumeParams` at
  [`particle_engine.py:100`](../../backend/src/models/particle_engine.py).

So **Phase 1 is a backend change**, and it is the critical path. Everything visual in
`core-C` and the forcing panel in `p4-01` waits on it.

---

## Phase 0 — Baseline. Measure, do not assume. (~45 min)

Nothing is built in this phase. Its only product is a written record of what is
actually true on your machine, because every trap in `CLAUDE.md` is a case of
plausible-wrong-output-with-no-error.

1. `pip install -r backend/requirements-api.txt -r backend/requirements-worker.txt`
   (no root manifest — deliberate, Phase 5 A1.4), `cd frontend && npm install`
   (`package.json` changed in the merge).
2. Bring the stack up the way the container does — a green `pytest` is **not**
   evidence the stack runs (`tests/test_api_startup.py` exists because of exactly
   this). Confirm `/api/v1/health` answers.
3. Record the four ground truths, verbatim, into `tasks/phase7/evidence/replay/baseline.md`:
   - `curl -s '.../plume/map/frames?event_id=AQ-2016-10-28&outlet_id=AQ-O01'` →
     does `plume_source` read `particle-engine`? How many frames, and at what `t_hours`?
   - `curl -s -X POST .../plume/simulate` → capture the exact `provenance[]` and
     `caveats[]` strings. **These strings are the copy.** Do not paraphrase them into
     the UI; render them.
   - `curl -s .../events/AQ-2016-10-28/mooring` → confirm 200; then any other event id
     → confirm **404, not 500**.
   - `POST /exposure/calculate` for `AQ-O01` at 24 h → confirm the zero-intersection
     result and capture the caveat that explains it.
4. `npx playwright test journey3d` → record pass/fail **now**, before touching
   anything, so a later failure is attributable.
5. Run both data modes. `VITE_DATA_SOURCE=fixtures` is the default; `=http` is the
   one with two real bugs already found. Your screens must work in both — the demo
   may run in either.

**Gate:** you can state, from captured output rather than memory, what the plume
engine returns, what the mooring returns, and whether the journey specs pass.

---

## Phase 1 — Backend: surface the forcing provenance (~1.5 h) 🔴 critical path

The smallest change that unblocks the frontend. Resist widening it.

1. Add to the `/plume/map/frames` response body, sourced from the same
   `plume_simulate()` call it already makes:
   - `provenance: []` — pass `plume.provenance` through, model-dumped
   - `caveats: []` — likewise
   - `forcing: { currents: <provenance string>, wind: "ConstantWindField(0,0)",
     windage_fraction: <from calibration>, windage_is_tiebreak: true }`
2. `windage_is_tiebreak` is not decoration. `windage_fraction: 0.0` won a 72-trial
   calibration in which **the wind field was identically zero**, so every trial's
   windage term was multiplied by nothing. The winner is an artefact of the tie, not
   a fitted value. The flag is what stops the UI presenting it as calibrated.
3. Mirror the fields into `PlumeFrames` in `frontend/src/api/live.ts` and delete the
   stale "`is 'stub'` today" claim from `PlumeMapPanel`'s docstring.
4. Backend test: assert the frames response carries a non-empty `provenance` and that
   `forcing.currents` starts with `PLACEHOLDER:` on a checkout without
   `data/raw/currents/`.

**Gate:** `pytest -q` no worse than baseline; the new field visible in a live `curl`.

**Trap:** do not hard-code the placeholder string in the new field. Read it from the
same code path that builds it, so the day currents are restored the label flips by
itself. That is the whole point of `plume_source` and it applies here identically.

---

## Phase 2 — `core-C`: the plume on `/dashboard` (~2.5 h)

Now purely frontend. Touches `PlumeMapPanel.tsx`, rendered from
[`SideRail.tsx:292`](../../frontend/src/shell/SideRail.tsx).

1. Render `forcing.currents` **verbatim** — the string begins `PLACEHOLDER:` and that
   prefix doing the work on screen is better than any sentence you would write.
2. Render the wind statement and the windage tie-break note at the point the parameter
   is shown, not in a footer. Design system §6.4: a placeholder is labelled at the
   point of use.
3. One sentence, in both locales: *the cloud spreads by diffusion; it does not drift.
   Timing and extent are meaningful — a direction read off these frames is not.*
   Back it with the measurement you already have: centroids across six timesteps,
   ~100 m non-monotonic wobble, no coherent drift.
4. Keep `plume_source` verbatim from the API. Never hard-code the label.
5. Probability field only. `qa_frontend_docs.py` already fails a doc that endorses a
   trajectory line; the UI must not draw one either. No arrow, no track, no leading
   edge marker.
6. Plume density uses the documented relative-density scale. **Not `BAND_CLASS`.**
   The hazard ramp means risk; density means concentration. If they look alike a
   judge will read one as the other.

**Gate:** `python3 scripts/qa_frontend_tokens.py` exit 0 · `qa_frontend_docs.py`
exit 0 · both locales, both themes visually checked · `npm run qa` green.

**Evidence:** `tasks/phase7/evidence/plume/` — EN/AR × light/dark.

---

## Phase 3 — `p4-01`: Replay becomes a five-stage sequence (~4 h) — largest build

The page steps plume frames and shows exposure. Two of five stages are present.
**Rainfall → runoff → sediment** are missing.

1. Source each earlier stage from a real endpoint. Check `live.ts` first — the plan
   doc's own warning is that three frontend comments claimed endpoints did not exist
   when they did. If a stage genuinely has no endpoint, it renders as a named absence,
   **not** as a stage you quietly drop from the chain. A four-stage chain presented as
   five is the dishonest outcome here.
2. The chain must read in order and look like one sequence, not five unrelated cards.
   `FormulaChain.tsx` landed in the merge — check whether it already expresses this
   before building a second thing that does.
3. Reuse the requested-vs-shown split already in the file. Frames render server-side
   at ~5 s; the UI must not block, and a click must never look like it did nothing.
4. **Anchor-only copy, agreed with Karam.** His `/events` links all 675 rows to
   [`EventsPage.tsx:274`](../../frontend/src/routes/EventsPage.tsx). Most will 422.
   The existing `Empty` branch is the right shape — make the sentence say *why*
   (the engine needs a real `flood_arrival_utc`; only the anchor has one resolved;
   the other candidate is still `TO_BE_RESOLVED_FROM_KATZ_2015`). Never an empty
   animation implying a plume shape that was never computed.
5. **`AQ-O01` returns zero reef-zone intersections at 24 h, undiagnosed since Phase 4,
   and it carries 96 % of discharge.** If `AQ-O01` is on screen, that fact is on
   screen. The nearest zone is 1923 m from the outlet; the largest modelled extent is
   418 m. "Not reached" renders as not reached — never as zero-risk exposure.
6. Add EN **and** AR keys in the same commit as the component. Not a pass at the end.

**Gate:** the five stages render in order for `AQ-2016-10-28` · a non-anchor id
explains itself rather than erroring or animating nothing · caveats rendered, not
swallowed · both data modes · `npm run qa` green.

**Evidence:** `tasks/phase7/evidence/replay/` — EN/AR × light/dark, plus one shot of
the non-anchor 422 state, which is the one a judge is most likely to trigger by
accident.

---

## Phase 4 — `p4-10`: verify, then close the remaining gaps (~2 h)

Mostly a verification phase. The page is built and live. Do not rewrite it.

1. Walk every checkbox in `05-abd.md` against the file and mark each **verified** or
   **owed**. From reading: live endpoint ✓, plain-text-as-well-as-table ✓,
   per-field provenance + uncertainty ✓, `series_available` false-state ✓,
   404-by-design ✓, `modelled_blocked_on` ✓, satellite NO-GO section ✓.
2. Confirm the path is `/api/v1/events/{event_id}/mooring`. Several planning docs
   claim `/api/v1/mooring/{id}`. `live.ts:234` already carries the correction — do not
   let a doc talk you back out of it.
3. Confirm the measured numbers on screen match the response body, digit for digit:
   salinity −1.75 ‰ (19σ), turbidity peak 2.18 g/L, elevated ~31 h, mass 24,400 t,
   250 m offshore the Kinnet Canal at 13 m depth.
4. Satellite section: confirm the verdict, the ~31 h dispersal and the **+104 h /
   +128 h** overpasses come from `record.satellite` rather than typed copy — a hard
   requirement, because the number in the document must be the number on the screen.
5. Frame it as a finding: *we checked, and no image exists — which is exactly why the
   mooring is the validation target and a hand-drawn mask is not.* This is one of the
   strongest things in the project; it should not read as an apology.
6. The modelled column stays honestly empty. Drawing it would measure our placeholder,
   not our physics.

**Gate:** every box either ticked with a line reference or moved to Phase 6 as owed.

**Evidence:** `tasks/phase7/evidence/validation/` — EN/AR × light/dark, plus the
404 no-record state.

---

## Phase 5 — `p4-14`: the 3D Journey (~2 h)

1. `public/terrain/` and `public/basemap-raster/` **are present on this checkout** —
   your Phase 0 spec run says whether the three specs actually fail. If they pass,
   the task file's box is environmental and already satisfied; record that rather
   than regenerating 350 tiles for nothing.
2. If they do fail: regenerate with `scripts/tile_terrain_rgb.py` and
   `scripts/fetch_basemap_raster.py`, **or** state on the overlay that terrain is
   unavailable and degrade honestly. Both are acceptable; a silent broken scene is not.
3. **Do not weaken the 60 fps sample to make it green.** It passes in isolation and
   fails under full-suite load — machine contention, not a regression.
4. Re-theme the overlay chrome to the new brand. **Leave the scene lighting alone.**
   `journey/layers/*.ts` carry `token-ok` exemptions for scene lighting and for
   strokes read against satellite photography; that precedent covers new layers of the
   same kind and does **not** cover UI chrome.
5. Confirm the journey work is on `origin/main`. Phase 4 recorded it as unpushed, and
   a demo planned around an unpushed branch is a demo that dies on someone else's
   laptop. The `e558a60` merge appears to carry it — verify, do not assume.

**Gate:** `npx playwright test journey3d` at or better than the Phase 0 baseline.

---

## Phase 6 — Gates, evidence, honest ledger (~2 h)

1. `npm run qa` green (`typecheck && lint && test`).
2. `python3 scripts/qa_frontend_tokens.py`, `qa_frontend_docs.py`,
   `qa_frontend_rtl.py`, `qa_frontend_freeze.py` — all exit 0.
3. `npx playwright test` — green except documented environmental failures, each named
   with a reason.
4. axe clean across all four theme × language combinations (`hardening.spec.ts`).
   Watch `--ink-3`: it is for `--canvas` and `--surface` only. On `--surface-2` in dark
   it measures 4.17 and fails the build. This has already happened once.
5. Every screenshot filed: `evidence/plume/`, `evidence/replay/`, `evidence/validation/`
   — EN + AR, light + dark. **A row with no artifact is a claim, not a result.**
6. Anything still owed goes on the Honest Limits page with the sentence that states it.
   There is no third outcome between Done and Absent-and-stated.

---

## The five ways this goes wrong

1. **Rebuilding `ValidationPage`.** It is live and correct. Verify it; do not
   regenerate it.
2. **Attempting `core-C` frontend-only.** The provenance is not in the frames payload.
   Phase 1 exists for this reason and cannot be skipped.
3. **Renaming a `data-*` hook while restyling.** Seven Playwright specs target
   `[data-chrome]`, `[data-mode=…]`, `[data-open-overlay=…]`, `[data-risk-card]`,
   `[data-band]`, `[data-time-handle]` and named map layer IDs. Restyle freely;
   **rename nothing.**
4. **Copying a number from the foundation deck.** `frontend/Foundation pages built/`
   is a design canvas. Its `78%`, its `AP 0.5923`, its countdown — all hand-typed.
   Copy the layout, never the value.
5. **Regenerating fixtures casually.** `scripts/frontend_panels.py` pulls unrelated doc
   drift with it; on 8 Aug it changed the limitations count 9 → 12 and broke two specs.
   Own the diff deliberately or do not regenerate.

---

## Sequencing at a glance

```
Phase 0  baseline          0.75 h   ── blocks everything, produces the copy strings
Phase 1  backend forcing   1.5  h   ── 🔴 critical path for Phase 2
Phase 2  core-C plume      2.5  h
Phase 3  p4-01 replay      4    h   ── largest build; needs Karam for copy
Phase 4  p4-10 validation  2    h   ── mostly verification, can run beside Phase 3
Phase 5  p4-14 journey     2    h   ── independent, can run any time after Phase 0
Phase 6  gates + evidence  2    h
                          ────────
                          ~14.75 h
```

Phases 4 and 5 have no dependency on 1–3. If you are short of time, run Phase 5 first
— it may already be done, and knowing that early is worth more than doing it late.
