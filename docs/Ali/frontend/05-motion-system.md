# 05 · Motion System

**Status:** scaffold — filled during Phase 4 · **Owner:** Ali

Rationale in [`01-design-language.md`](01-design-language.md) §7. This file holds the values.

---

## Budget

**Three orchestrated moments. Everything else is ≤150 ms, opacity and transform only.**

| Moment | Scene | Notes |
|---|---|---|
| Time-scrub choreography | 3–5 | Every time-varying layer + hyetograph cursor + risk cards move as one |
| Plume bloom | 4 | Contours expanding T+3 → T+24 |
| Mode transition | all | Re-layout, not a cross-fade |

## Rules

- [ ] **Interruptibility first.** A gesture must be reversible mid-flight. A time-scrub that finishes
      its animation before accepting the next input feels broken regardless of how smooth it is.
- [ ] Springs for anything the user drags; duration curves for state changes.
- [ ] Compositor-friendly only — `transform` and `opacity`. No animated `width`, `top`, `filter`.
- [ ] Nothing animates without being asked. No entrance animations, no ambient motion.
- [ ] Deck.gl earns its place or it does not ship.

## Tokens

- [ ] `--dur-instant` / `--dur-fast` / `--dur-base` — to be fixed in Phase 4
- [ ] `--ease-out` / `--ease-spring`
- [ ] Direction-aware transforms use `calc(x * var(--dir))`, never a hard-coded sign

## Reduced motion

Every moment needs an equivalent that still communicates the state change. `prefers-reduced-motion`
must not mean "nothing happens" — the plume still steps through its timesteps, it just cuts rather
than tweens.

- [ ] Time-scrub → instant layer swap, cursor still moves
- [ ] Plume bloom → discrete steps
- [ ] Mode transition → instant re-layout

## Verification

- [ ] DevTools performance trace across a full scrub holds 60fps with every layer live
- [ ] Reduced-motion pass: all eight scenes still readable
