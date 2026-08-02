# 12 · Testing and Demo Safety

**Status:** scaffold — filled during Phase 5–6 · **Owner:** Ali

The backend has **336 tests across 13 files** and is still growing. A frontend with no tests would be out of step
with this repo — and the demo runs live in front of judges.

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
