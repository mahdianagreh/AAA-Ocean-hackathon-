# Phase 6 — Pure Testing Plan

**Project:** ReefShield Aqaba
**Written:** 7 August 2026
**Window:** freeze already happened (12 Aug in the original schedule, compressed here
to same-day verification before presenting).

This phase builds **nothing**. It verifies what Phases 3–5 already claim to have
built, against the real running system, and writes down exactly what is true right
now — no more, no less.

---

## The one rule that overrides every other instinct in this phase

**If you find something broken, do not fix it.** Write down what you saw, save the
evidence, mark the row, move to the next row. Phase 6 exists precisely because the
last three phases mixed "I built it" with "I confirmed it works" often enough that the
team can no longer tell which claims in `tasks/phase4/*.md` and `tasks/phase5/*.md`
are load-bearing and which are optimistic. Fixing something mid-test re-creates the
exact problem this phase is meant to solve — it does not know what state to compare
against, because *the state is what's being measured*.

If you are a teammate tempted to fix something you find while testing: stop, write
the row as **FAIL** or **BLOCKED-NOT-BUILT**, and open a normal follow-up item instead.
That follow-up is a Phase 7 concern, not a Phase 6 one.

## Standing law for this phase

1. **A test result has exactly three valid states: `PASS`, `FAIL`, or
   `BLOCKED-NOT-BUILT`.** No partial credit, no "mostly works," no 🟡. `BLOCKED-NOT-BUILT`
   means the feature has no real code path to test yet (not "I didn't get to it").
2. **No verdict without evidence.** Evidence is a saved artifact — a curl response
   body, a screenshot, a `pytest` output, a SQL query result — filed under
   `tasks/phase6/evidence/<feature-id>/`. A verdict with no evidence file is not a
   verdict, it is a claim, and this phase exists to stop accepting those.
3. **Test against the real running stack, not against source code.** `docker compose
   up`, then hit the actual container. Reading `main.py` and concluding "this looks
   wired" is exactly the failure mode `tests/test_api_startup.py`'s own history
   (documented in the root `CLAUDE.md`) already caught once — a green suite is not
   evidence the stack runs, and a route existing in a file is not evidence it responds.
4. **Report a verdict for what you personally ran.** Do not transcribe a teammate's
   claim from their Phase 4/5 file as your Phase 6 verdict. If you cannot personally
   run a check (no browser tooling, no access to a service, a live external dependency
   is down), the row is `BLOCKED-NOT-BUILT` with a note saying *why you personally
   couldn't verify it* — never silently copy someone else's prior "✅ Done."
5. **Frontend-rendered features get two verdicts, not one, when the tester is not
   Ali:** a `backend` sub-verdict (does the API this screen depends on return real,
   correct, non-fabricated data) and a `frontend` sub-verdict (does the screen
   actually show it, which only Ali or someone with browser tooling can confirm this
   pass). A row is only fully `PASS` when both sides are `PASS`.
6. **This plan and every per-person file in this phase contain zero fix/build/wire/
   repoint instructions.** If a sentence in one of these files tells someone to change
   code, that sentence is a bug in the plan — flag it, don't act on it.

## What gets tested

Every feature currently tracked anywhere in this repo's task files, in one matrix:
[`00-master-test-matrix.md`](00-master-test-matrix.md). Three groups:

- **Core (5 rows, A–E)** — the five always-on pipeline stages every later feature sits
  on top of: runoff classifier, sediment proxy, plume/particle engine, exposure
  engine, explanation+retrieval (RAG).
- **Phase 4 (30 rows, 1–19 and A–K)** — the dashboard feature audit from
  `tasks/phase4/00-phase4-plan.md`.
- **Phase 5 (9 rows, B1–B9)** — the new AI features from `tasks/phase5/00-phase5-plan.md`.

## Per-person assignment

Each person tests the rows they already own (same ownership map Phase 4/5 already
established — testing your own build first is the fastest way to get a true state,
and cross-checking someone else's claim is Ali's job for the frontend half of
everything, since every row ends in a screen):

- [`01-karam.md`](01-karam.md) — rainfall/climatology chain, Core A's inputs, rows 5, 8, 16, G, K, F(currents-vs test partner)
- [`02-mahdi.md`](02-mahdi.md) — Core A, terrain/hydrology, B1/B2/B3/B9, rows 4, 9, C, D, H, J
- [`03-nizar.md`](03-nizar.md) — Supabase/forecast/currents, B6, rows 2, F, A4-adjacent
- [`04-pulga.md`](04-pulga.md) — Core D/E, B4/B5/B7/B8, rows A, I, and the backend half of 7, 10, 15, C
- [`05-abd.md`](05-abd.md) — Core C (particle engine), rows 1, 10 (sensor side), 14 (plume portion)
- [`06-ali.md`](06-ali.md) — the frontend-rendering half of **every** row in the matrix, plus rows 3, 6, 11-13, 16-19 end to end where there is no separate backend half

## Evidence layout

```
tasks/phase6/evidence/<feature-id>/
    <short-description>.txt      # curl output, pytest output, sql query result
    <short-description>.png      # screenshot, if applicable
```

`<feature-id>` matches the matrix's `#`/letter/B-code exactly (e.g. `core-d`,
`p4-07`, `p4-A`, `b4`).

## Definition of done for Phase 6

Every row in `00-master-test-matrix.md` carries a real verdict (`PASS`/`FAIL`/
`BLOCKED-NOT-BUILT`) with a linked evidence file, filled in by the person who actually
ran the check — not transcribed from an earlier phase's file. Nothing in this phase's
own files instructs anyone to change a single line of product code.
