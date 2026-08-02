# 11 · UI Skills Routing

**Status:** complete · **Owner:** Ali · **Phase:** Day 1

Which skill to load for which task. The registry holds **202 skills across 26 categories from 52
authors**, and its own routing rule is **prefer 1, never more than 3 per task**. These are assigned per
phase, not loaded together.

```bash
npx ui-skills list --category <name>
npx ui-skills get <author/slug>          # the owner prefix is required — see §4
```

---

## 1 · The routing table

| Phase | Skill | Why this one |
|---|---|---|
| 0 | `dammyjay93/interface-design` | The spine. Built specifically for dashboards and data interfaces, and its domain → signature process is how the Aqaba direction gets *derived* rather than borrowed. Returns as the review lens in every later phase. |
| 0 | `jakubkrehel/better-colors` | OKLCH, gamut, contrast, dark mode. Non-negotiable when data colours must stay perceptually ordered over a basemap. |
| 0 | `jakubkrehel/better-typography` | Bilingual type scale, variable fonts, tabular figures. |
| 0 | `ibelick/create-design-md` | Turns the above into an evidence-based `DESIGN.md` the whole team can follow. |
| 1 | `emilkowalski/pick-ui-library` | Once, to settle charts and motion libraries deliberately rather than by habit. |
| 1–2 | `vercel-labs/react-best-practices` | Render performance and component architecture. |
| 2 | `prototyperai/build-primitive` | The time slider, mode switcher and layer toggles are bespoke controls needing real ARIA, keyboard and focus management. 5,300 words of exactly that. |
| 3 | **`dataviz`** *(local Claude skill, not ui-skills)* | Hyetograph, mooring time series, SHAP bars, confidence meters, stat tiles. Fills a genuine registry gap — see §3. |
| 4 | `emilkowalski/apple-design` | Springs, velocity handoff, and above all **interruptibility** — the difference between a time-scrubber that feels elite and one that feels laggy. |
| 4–5 | `iart-ai/60fps-animation` | Compositor-friendly motion, essential alongside MapLibre and Deck.gl. |
| 5 | `pbakaus/harden` | Empty states, edge cases, errors, i18n resilience — maps directly onto DoD item 9. |
| 5 | `jakubkrehel/better-accessibility` | Focus, keyboard, ARIA, motion accessibility. |
| 5–6 | `microsoft/playwright-cli` | The eight-scene walk and the pre-freeze regression run. |
| 6 | `jakubkrehel/better-interface` | Final holistic review across accessibility, layout, writing, typography, colour. |

---

## 2 · Deliberately not used

| Excluded | Why |
|---|---|
| All landing-page and marketing skills — `mengto/landing-page`, `mengto/pricing-page`, `elayadesign/landing-page-design`, `danilaa1/compact-landing` | This is a tool, not a campaign. Their guidance optimises conversion flow, which we do not have. |
| All style-preset skills — `mengto/industrial-brutalist-ui`, `leonxlnx/brutalist-skill`, `minimalist-skill`, `soft-skill`, the `taste` cluster | **The important exclusion.** They would substitute a borrowed look for the domain-derived one, which defeats the entire point of the Aqaba direction. |
| All 14 Three.js / Cobe / 3D skills | No 3D. Deck.gl is WebGL but has its own API. |
| All Vue, Nuxt, SwiftUI, React Native, Remotion, Svelte and Next.js skills | Wrong stack. |
| `mattpocock/*`, `tjcages/linear-*` | Process and issue tracking; not the bottleneck in 11 days. |
| `shadcn-ui/shadcn` | Superseded by the Radix decision. |

---

## 3 · Two gaps with no coverage

Searched all 202 by name, description and category:

> **There is no map or geospatial skill, and no RTL or i18n skill in the registry.**

Those are two of this project's hardest problems, which is exactly why
[`08-map-rendering.md`](08-map-rendering.md) and [`06-bilingual-rtl.md`](06-bilingual-rtl.md) exist as
in-house rules rather than as skill invocations.

The registry also has no data-visualisation skill despite 14 skills mentioning charts in passing —
hence `dataviz`, which is a local Claude skill rather than a ui-skills entry.

---

## 4 · Using the CLI

**Two operational notes, both discovered the hard way.**

**Five slug names are owned by two authors each**, and `get` refuses a bare slug for those:

```
$ npx ui-skills get vue-best-practices
Ambiguous skill slug: vue-best-practices
```

Affected: `vue-best-practices`, `vue-router-best-practices`, `vue-testing-best-practices`,
`web-design-guidelines`, `prototype`. **Always pass the owner prefix.**

**`npx ui-skills` may exit 1 with no output.** The package depends on `sharp`, whose native build
fails on some machines, and npx swallows the error. Install skipping build scripts:

```bash
npm i -g --ignore-scripts ui-skills
```
