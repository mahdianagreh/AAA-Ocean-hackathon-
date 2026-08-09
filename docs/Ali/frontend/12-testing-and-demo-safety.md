# 12 · Testing and Demo Safety

**Status:** scaffold — filled during Phase 5–6 · **Owner:** Ali

The backend has **559 tests across 37 files** and is still growing. A frontend with no tests would be out of step
with this repo — and the demo runs live in front of judges.

That 559 is a count of `def test_` functions, not a result. Run on 3 Aug 2026 — the first time
anyone had actually run it — the suite stood at 433 tests and gave **421 passed, 4 failed, 49
skipped**. The four failures were a real API contract defect
([`OPEN-ISSUES.md`](../../OPEN-ISSUES.md) item 24); the 49 skips nobody had looked at. Both numbers
belong here, because the gap between them is the point: a grep counts a skipped test and a failing
test as passes, and quoting it is how "the backend has 559 tests" turns into "the backend is fine".

> This headline has now gone stale twice and been corrected twice, both times by
> `scripts/qa_frontend_docs.py` failing the build on the mismatch rather than by anyone noticing:
> **433 across 20 files** until 8 Aug 2026, then **552 across 36** until 9 Aug. It is 559/37 as of
> 9 Aug 2026. The pass/fail/skip split above is still the 3 Aug run and has **not** been
> re-measured — it is dated for that reason, and the **126 tests added since** are of unknown
> status. The measured figure on 9 Aug was 552 passed / 47 skipped / 1 xfailed, which does not
> reconcile with 559 collected; nobody has reconciled it, and this note is the honest record of
> that rather than an average of the two.

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
