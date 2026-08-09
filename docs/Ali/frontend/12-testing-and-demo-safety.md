# 12 · Testing and Demo Safety

**Status:** scaffold — filled during Phase 5–6 · **Owner:** Ali

The backend has **561 tests across 37 files** and is still growing. A frontend with no tests would be out of step
with this repo — and the demo runs live in front of judges.

That 561 is a count of `def test_` functions, not a result. Run on 3 Aug 2026 — the first time
anyone had actually run it — the suite stood at 433 tests and gave **421 passed, 4 failed, 49
skipped**. The four failures were a real API contract defect
([`OPEN-ISSUES.md`](../../OPEN-ISSUES.md) item 24); the 49 skips nobody had looked at. Both numbers
belong here, because the gap between them is the point: a grep counts a skipped test and a failing
test as passes, and quoting it is how "the backend has 561 tests" turns into "the backend is fine".

> The headline count was stale at **433 across 20 files** until 8 Aug 2026, when
> `scripts/qa_frontend_docs.py` measured 552 across 36 and failed the build on the mismatch, and
> again on 9 Aug 2026, when the same script measured 561 across 37 (Phase 7 added two cases to
> `test_plume_map_render.py` for core-C's forcing provenance; `test_events_seasonal.py` had already
> landed in the 8 Aug merge). The pass/fail/skip split below it is still the 3 Aug run and has
> **not** been re-measured — it is dated for that reason, and the tests added since are of unknown
> status. A live run right now (`pytest -q`) is the only way to know whether they pass.

---

## The two artefacts

**`/specimen` route.** Every component, every state, **both themes × both directions** — four
combinations on one page. Cheaper than Storybook, and it *is* the RTL QA tool. A primitive that is not
on it has not been checked.

**Playwright scene walk.** One test driving all eight storyboard scenes end to end. Runs in CI and
again before the freeze. If the demo can break on stage, this catches it first.

- [ ] Scene 1 problem · [ ] 2 storm · [ ] 3 land · [ ] 4 marine
- [ ] 5 exposure · [ ] 6 validation · [ ] 7 what-if · [ ] 8 recommendation
- [ ] The same walk, in Arabic
- [ ] The same walk, with the network disabled

## Other coverage

- [ ] Contract tests run against **both** the fixture and HTTP clients, so a drifted fixture fails CI
      rather than surfacing as a blank panel in rehearsal
- [ ] Unit tests for formatting: bidi isolation, tabular numerals, unit handling, `null` vs `0`
- [ ] Automated axe pass

## Demo safety

- [ ] **Deterministic demo mode** — fixed snapshot, seeded scenario, byte-identical every run
- [ ] **Backup video** recorded on Day 12, covering all eight scenes
- [ ] Rehearsed on the actual demo machine at the actual resolution
- [ ] Projector check: the hazard ramp is monotonic in lightness, so it survives bad gamma — verify
      against a real projector rather than trusting the maths
- [ ] Failure plan: what a presenter does if the map does not load

## Day 12 gate

```bash
grep -ri PROVISIONAL frontend/
```

Anything still matching is either swapped or **explicitly declared a known placeholder in the demo**.
No silent placeholders reach the stage.
