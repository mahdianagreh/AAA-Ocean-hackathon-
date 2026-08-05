# Pulga — Phase 3

Read [`00-phase3-plan.md`](00-phase3-plan.md) first.

Your backend is in better shape than the task list suggests. As of 4 Aug, verified against
the running container: **all 8 GET endpoints answer 200**, `docker compose up` reaches
healthy in ~8 s, the exposure engine produces scores with `formula_terms` stored, and your
43 API contract tests run. Two new render endpoints sit alongside yours.

Three things are left, and one of them is small but blocks a whole screen.

---

## 1 · Seed a stored exposure run — 🟠 small, unblocks `/alerts` ✅ DONE 2026-08-05

`/api/v1/alerts` returns **200 with nothing in it**, because `exposure_runs.sqlite` has no
rows. Technically healthy, useless on screen, and it looks like a bug to anyone demoing it.

- [x] Persist at least one run for `AQ-2016-10-28` so the alerts view has real content.
      `scripts/seed_demo_exposure_run.py` calls the real `/exposure/calculate` route for
      every outlet — 5 runs, 9 zone results — and is re-runnable. Verified against the
      **actual running container** (`docker compose up api`, healthy), not just the venv.
- [x] Runs must be reconstructable: `formula_terms` **and** `model_versions` stored
      together. A score you cannot rebuild six hours later is a number nobody can defend.
      Confirmed via `GET /exposure/runs/{run_id}` on the live container.

**Also fixed while seeding:** `new_run_id()` was emitting `sim_{timestamp}_{uuid8}`,
not the `sim_{ULID}` the ID contract (`tasks/00-contracts.md`) specifies. Replaced with a
real, dependency-free ULID generator — see `backend/src/exposure/store.py`.

**Heads up for Ali/Karam:** every seeded score is 0.0 (sediment unanchored, as expected),
so `GET /alerts` with its **default `min_level=moderate`** returns **empty** — pass
`min_level=minimal` until Mahdi's anchor lands, or the demo will look unseeded when it
isn't.

**Watch out — the write path.** `./data` is mounted read-only on purpose and
`exposure.store` writes SQLite, which is why `/alerts` returned a bare 500 until 4 Aug. It
now writes to a named volume via `REEFSHIELD_EXPOSURE_DB=/app/var/exposure_runs.sqlite`.
Do not relax the read-only mount to make a write succeed.

**Watch out — the scores are all 0.0 right now** and that is not your bug. Mahdi's sediment
term is unanchored, and exposure is a product. Seed the run anyway: the shape is what Ali
needs, and the numbers fill in when the anchor lands.

---

## 2 · `/explain` and `/ask` — no LLM key required ✅ VERIFIED 2026-08-05

Worth stating plainly because it changes the risk: your RAG is **extractive**. It composes
answers from retrieved excerpts and never paraphrases. Your own docstring has it right:

> *"An LLM asked to summarise retrieved text will paraphrase numbers."*

So the assistant **cannot hallucinate a figure**, works fully offline, and needs no key.
`generate_with_llm` is a hook that stays unconfigured. That is a selling point, not a
limitation — say it out loud on the slide.

- [x] `/explain` returning grounded bilingual paragraphs that invent nothing.
      `tests/test_explain_ask_adversarial.py` now calls the live route (not just the
      template function) across 3 catchments × 2 languages.
- [x] `/ask` returning cited answers, citations as a **structured array, never prose**
      (issue #13), in both languages. Confirmed structural on every response, answered
      or refused.
- [x] The corpus is 111 KB of chunks already. `docs/ali/*` is research and pitch material
      and stays **out** of it.
      **Found while checking this:** the exclusion guard (`corpus.EXCLUDED_DIRS`,
      `is_excluded()`) was written for lowercase `docs/ali/`, but the real tracked
      directory is `docs/Ali/` (capital A, 35 files) — the guard silently matched
      nothing real. No live leak resulted (the corpus allowlist never listed a
      docs/Ali path either), but the "second, independent guard" the module's own
      docstring describes wasn't actually guarding anything. Fixed: `is_excluded()`
      is now case-insensitive; `test_ask_citations.py`'s probes now check the real
      path, not just the lowercase one.

- [x] Test it adversarially, not just happy-path. Ask it things the corpus cannot answer and
      confirm it refuses rather than reaches.
      **Found a real gap, not fixed, documented instead:** a question with a
      disqualifying scope word ("...for the **Egyptian** side of the Gulf?") still
      gets answered from Jordan-only content, because `min_term_coverage` weighs
      genuinely-matching terms and cannot recognise one term as scope-*narrowing*
      rather than additive. Recorded as `docs/model_card.md` E-Retrieval limitation
      #3 and pinned as `xfail(strict=True)` in
      `tests/test_explain_ask_adversarial.py` — a real retrieval-design fix, not a
      threshold tweak safe to rush this week.

---

## 3 · Close the seam vocabularies — 🟠 cheap now, expensive on the 12th ✅ DONE 2026-08-05

I have fixed this exact class of bug **three times in three days**: `sediment_class` had
three spellings across three modules, the runoff model returned different keys than the API
read, and the API imported packages in a way only the tests could resolve. Each one
produced plausible output and no error.

One is still open:

- [x] **`position_confidence` has two vocabularies** (issue #7). Same shape. Pick one, pin
      it with a test like `tests/test_sediment_class_vocabulary.py`, and make both sides use
      it.
      **Worse than described:** it wasn't two endpoints disagreeing — `/catchments`
      never had this field at all. The real bug was `/outlets` alone: a hand-typed
      `OUTLET_CONFIDENCE = {"good"/"plausible"/"low"}` dict (written before
      `outlets.geojson` carried real per-outlet confidence) had silently diverged
      from Mahdi's actual DEM/culvert cross-check on 3 of 5 outlets — AQ-O02 and
      AQ-O03's "unmodelled path to the sea" flags read back as merely "plausible",
      and AQ-O05 (a verified natural wadi mouth) also read "plausible" instead of
      "high". Fixed: reads `high`/`low`/`unchecked` straight from the source now.
      Pinned in `tests/test_position_confidence_vocabulary.py`.

Two smaller ones from the same family:

- [x] `/api/v1/outlets` returns a **variable key set** (issue #8). A client cannot type
      against a shape that changes per row.
      **Traced via git history, not guessed:** real in `0b44ed3` (Mahdi,
      2026-08-03 09:48), already fixed same day by `3db873e` (11:42), which
      replaced the dict-comprehension with `response_model=list[OutletOut]` — a
      Pydantic model structurally cannot vary its keys. Never marked closed in
      `docs/OPEN-ISSUES.md`; done now, with the commit evidence recorded there.
      What I found instead, live: the geometry team's richer per-outlet fields
      (`culvert_verdict`, `upstream_km2`, `nearest_culvert_m`, the "CANDIDATE
      CORRECTION" flags) existed on disk but never reached the API at all. Now
      surfaced on `OutletOut`.
- [x] Units never baked into value strings (issue #14) — `Value` wrapper with a unit field,
      so Ali never parses `"2.18 g/L"` out of a string.
      Added `schemas.Value{value, unit, provenance}`. **First version of this fix
      was wrong and was caught before push:** it wrapped `upstream_km2` and
      `nearest_culvert_m` on `Value`, on the assumption nothing consumed them yet.
      `frontend/src/api/types.ts` already declares both as bare `number` — it
      predates this pass — and `SideRail.tsx:147` already reads
      `o.upstream_km2` as one. Wrapping them would have broken that render the
      moment live mode replaced fixtures. `Value.provenance` also originally
      reused this file's unrelated `Provenance{kind,detail}` class instead of the
      frontend's actual `Value.provenance: 'measured'|'reported'|'converted'|'modelled'`
      enum — `ValueWithUnit.tsx` indexes a lookup table with that string, so an
      object would have silently rendered with no data-quality styling. Both
      reverted/fixed: the two outlet fields are bare floats again, matching Ali's
      type exactly, and `Value.provenance` now matches
      `frontend/src/api/types.ts:16` exactly. `Value` itself is correct, tested,
      and ready for the next field that needs it — just not forced onto two that
      already had a fixed, incompatible contract.
      **Also caught while wiring the (now-reverted) version in:** `da.outlets()`
      is `@lru_cache`d, and the route was mutating its cached dicts in place —
      the *second* call to `/outlets` in a running process would have crashed.
      Fixed by copying each row before mutation regardless, since the route may
      grow a field that does need transforming later; a test calls the route
      three times in a row to pin it.

**The rule worth adopting:** a value that crosses a module boundary is a contract, and it
earns the same discipline as `AQ-C01` or `R-03`.

---

## 4 · Keep the caveats travelling as data

This is already right and it is the thing that most distinguishes the API. `/catchments`
returns `position_confidence` and `caveat` per row, including the AQ-O04 harbour warning.
Keep it that way as you add endpoints.

Four caveats that must reach the screen, not a doc:

| | |
|---|---|
| `AQ-O04` | discharges into an **enclosed harbour basin**; 427 m outside the sea polygon |
| `sensitivity_weight` | **1.0 placeholder**, `PLACEHOLDER_PENDING_MARINE_SCIENTIST` |
| `predicted_runoff_m3` | **`None`** — Component A predicts occurrence, not volume. A gap, never a zero |
| `depth_median_m` | can be **`NaN`** (R-02 has no water cell under a 5 m reef strip at 50 m bathymetry) |

---

## Definition of done

1. [x] `/alerts` returns real stored runs with `formula_terms` and `model_versions`.
       Verified on the live container, not just pytest.
2. [x] `/explain` and `/ask` live, bilingual, citations structured, refusing rather than
       guessing. One real refusal gap found and documented (E-Retrieval limitation #3),
       not silently patched over.
3. [x] `position_confidence` single vocabulary, pinned by a test.
4. [x] Every caveat above travels in the payload — reconfirmed live: AQ-O04 harbour
       (critical), sensitivity placeholder (warning), `predicted_runoff_m3: null` with a
       critical gap caveat, `depth_median_m` NaN-not-zero (unchanged, already correct).
5. [x] Your contract tests still green after all of it. 471 passed, 47 skipped (all
       gated on absent git-ignored raw data), 1 `xfail` (the documented, tracked RAG
       gap) — up from the 453/47/0 baseline at the start of this pass.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Mahdi** | anchored sediment | Only for the *numbers*. Seed the run now — the shape is what Ali needs |
| **Abd** | real plume contours | No — the stub has the right shape |
| **Nizar** | Postgres persistence | No — SQLite via the named volume works today |
