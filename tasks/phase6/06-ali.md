# Phase 6 — Ali's testing assignment

Read [`00-phase6-plan.md`](00-phase6-plan.md) first. This file contains **no fix, build,
wire, or repoint instructions** — only what to run and where to record the result. If
something fails, write `FAIL` with evidence and move on; do not fix it in this pass.

You carry a wider net than everyone else: the **frontend-rendering half of every
row** in [`00-master-test-matrix.md`](00-master-test-matrix.md), since every feature in
this project ends in a screen. For rows where a teammate already recorded a
`(backend)`-qualified `PASS`, your job is the other half — confirm the screen actually
shows what the backend returns, with real values, not a placeholder or a stale mock.
For rows with no separate backend half (pure frontend features: 3, 6, 11-13, 16-19),
you own the row end to end.

## How to test a frontend-rendered row

1. `docker compose up` (real stack, not `npm run dev` against a mock).
2. Load the actual screen in a browser.
3. Cross-check the on-screen number/label against the API response the backend
   tester already saved as evidence for that row (or, for pure-frontend rows, against
   the real underlying data file).
4. Screenshot. Save under `tasks/phase6/evidence/<id>/frontend.png`.
5. `PASS` only if the screen shows the real value — not "the component renders,"
   `PASS` means "the number a judge would see matches the number the backend produced."

## Rows

Every row in `00-master-test-matrix.md`. Priority order (frontend-only rows first,
since no one else will test them; then the frontend half of every backend-tested row):

| Priority | IDs |
|---|---|
| 1 — frontend-only, no backend half | p4-03, p4-06, p4-11, p4-12, p4-13, p4-16, p4-17, p4-18, p4-19, p4-E |
| 2 — frontend half of rows Pulga already marked `(backend)` `PASS` | p4-07, p4-10, p4-15, p4-A, p4-I, p4-C |
| 3 — frontend half of every other row, as teammates land their backend verdicts | everything else in the matrix |

## The one hard fact to test against, not assume

`tasks/phase5/00-phase5-plan.md` records A3.4 as "🟡 Backend real; frontend still
bypasses it" — `ScenarioDrawer` never actually calls `rainfall_multiplier`/
`transmission_loss_override`. That was the state as of 7 Aug. Test rows p4-07 and
p4-15 (both depend on exactly this wiring) against the *current* build — do not carry
forward the 🟡 as this pass's answer. If it is still bypassing the real parameter,
that is a `FAIL`, recorded fresh, with a screenshot showing the drawer's request not
matching the backend evidence file.

## Definition of done for this file

Every row's frontend half in the master matrix has a `PASS`/`FAIL`/`BLOCKED-NOT-BUILT`
verdict, each with a linked screenshot, recorded by you loading the real screen — not
transcribed from `tasks/phase4/06-ali.md` or `tasks/phase5/06-ali.md`'s prior claims.
