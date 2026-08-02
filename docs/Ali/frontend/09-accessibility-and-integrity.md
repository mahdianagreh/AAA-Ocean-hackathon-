# 09 · Accessibility and Integrity

**Status:** scaffold — filled during Phase 3–5 · **Owner:** Ali

Two concerns in one document because they share a mechanism: **both are about making sure the screen
does not claim more than it can support.** WCAG is honesty about what a person can perceive; the
integrity rules are honesty about what the data can support.

---

## Accessibility

- [ ] WCAG 2.2 AA. Every token pair verified — see [`02-design-tokens.md`](02-design-tokens.md) §2
- [ ] Visible focus on every interactive element, drawn in the signature hairline
- [ ] Full keyboard path through all eight storyboard scenes
- [ ] Bespoke controls (time slider, mode switch, layer toggles) carry real ARIA — built with
      `prototyperai/build-primitive`
- [ ] `prefers-reduced-motion` honoured with equivalents, not with nothing
- [ ] Hit areas ≥ 24 px
- [ ] Colour is never the only channel — the hazard ramp is monotonic in lightness and every fill
      carries a stroke
- [ ] Screen-reader pass in both languages

## Integrity — the rules that outrank visual preference

These come from the carry-over rules in
[`00-phase2-plan.md`](../../../tasks/phase2/00-phase2-plan.md) and from physics.

1. [ ] **Uncertainty renders with the value, or the value does not render.** No bare numbers.
2. [ ] **Measured vs modelled is encoded in form, not hue** — solid / dashed / hatched. It survives
       colour-blindness, greyscale and a photograph of the screen.
3. [ ] **An uncited assistant answer must not render as an answer.** `no_sourced_answer` is a distinct
       state that shows what *was* searched — more useful and more honest than a hedge. Enforced by the
       response union in [`07-data-contracts.md`](07-data-contracts.md) §4.
4. [ ] **Missing is never zero.** A gap renders as a gap.
5. [ ] **The plume is always a contoured field with its caveats stated.** Never a trajectory line,
       and never labelled as a probability — the levels are relative density.
6. [ ] **Provisional data is labelled in the UI**, not only in the repo.
7. [ ] **The map is never the only path to a fact.**
8. [ ] **Never claim exactness.** The Gulf is narrower than three cells of the best free ocean model,
       and the UI says so before a judge finds it.

## The uncited-answer state

Needs designing properly rather than defaulting to an error toast:

- [ ] What renders — what was searched, and why nothing qualified
- [ ] How it differs visually from an answer, at a glance
- [ ] What the user can do next

## Verification

- [ ] Automated axe pass, zero violations
- [ ] Manual keyboard walk of all eight scenes, both directions
- [ ] Screen-reader spot check in AR and EN
- [ ] Every value on screen traceable to a `provenance` field
