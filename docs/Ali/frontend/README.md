# ReefShield Aqaba — Frontend

**Workstream 6 · Ali** · Build documentation for the bilingual React + MapLibre interface.

> **Scope.** This folder is **build documentation**. It is not in the RAG corpus.
> [`../research/`](../research/) is a different thing entirely — pitch and market material that does
> not become a screen.

**Task file:** [`06-ali.md`](../../../tasks/phase2/06-ali.md) ·
**Phase plan:** [`00-phase2-plan.md`](../../../tasks/phase2/00-phase2-plan.md)

---

## Start here

1. [`00-master-plan.md`](00-master-plan.md) — phases, gates, dependencies, and the seven Day 1 asks
2. [`01-design-language.md`](01-design-language.md) — the direction and *why*
3. [`02-design-tokens.md`](02-design-tokens.md) — the values you type

---

## The set

**Locked before code.** These five are expensive to retrofit, so they were finished first.

| Doc | What it settles |
|---|---|
| [`00-master-plan.md`](00-master-plan.md) | Phases, gates, dependencies, risk register, Day 1 asks |
| [`01-design-language.md`](01-design-language.md) | Domain, signature, rejected defaults, the rules that are not style preferences |
| [`02-design-tokens.md`](02-design-tokens.md) | Validated OKLCH palette, type, space, theme switching |
| [`06-bilingual-rtl.md`](06-bilingual-rtl.md) | AR/EN architecture, logical properties, numerals, the MapLibre RTL plugin |
| [`07-data-contracts.md`](07-data-contracts.md) | Every endpoint as a type, fixtures, the swap plan |

**Grows with the build.** Scaffolded with what is already decided; filled as each phase lands.

| Doc | Filled during |
|---|---|
| [`03-information-architecture.md`](03-information-architecture.md) | Phase 1–2 |
| [`04-component-inventory.md`](04-component-inventory.md) | Phase 2–4 |
| [`05-motion-system.md`](05-motion-system.md) | Phase 4 |
| [`08-map-rendering.md`](08-map-rendering.md) | Phase 1–2 |
| [`09-accessibility-and-integrity.md`](09-accessibility-and-integrity.md) | Phase 3–5 |
| [`10-performance-and-offline.md`](10-performance-and-offline.md) | Phase 5 |
| [`11-skills-routing.md`](11-skills-routing.md) | complete |
| [`12-testing-and-demo-safety.md`](12-testing-and-demo-safety.md) | Phase 5–6 |

---

## The short version

**Direction:** hydrographic chart. The Gulf's bathymetry is the structural language — isobath
hairlines draw the dividers, the loading state, the focus ring, and the plume's own contours.

**Stack:** Vite · React · TypeScript · Tailwind v4 · Radix (unstyled) · MapLibre GL JS · TanStack
Query · Zustand · i18next. App code in `frontend/` at repo root.

**Five things that are not open to negotiation:**

1. The plume renders as a contoured field with its caveats stated. **Never a trajectory line, and
   never labelled as a probability** — the levels are relative density, not calibrated chance.
2. Uncertainty renders with the value, or the value does not render.
3. Measured vs modelled is encoded in **form** — solid, dashed, hatched — not hue.
4. An uncited assistant answer must not render as an answer.
5. RTL from the first component, not a late translation pass.

**The date that matters most:** 6 August, the vertical slice. Ugly and end to end beats polished and
integrated on Day 11.
