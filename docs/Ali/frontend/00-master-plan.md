# 00 · Master Plan

**Status:** locked · **Owner:** Ali · **Workstream 6 — Frontend**
**Window:** 2 → 13 August 2026 · **Written:** 2 August 2026

---

## The job

Five people produce numbers that nobody can see. [`06-ali.md`](../../../tasks/phase2/06-ali.md) states
it plainly: **the map is the product.** One screen, three modes, built toward an eight-scene storyboard
that ends on an honest alert.

Two constraints shape every decision:

**You cannot wait for data.** Real endpoints land Day 3, risk fields Day 5, plume layers Day 6. The
shell is built against fixtures from Day 1 and the real endpoints swap in behind an unchanged type
boundary.

**Restraint is half the job.** Concept §25 lists *"dashboard becomes more important than science"* as a
live risk, mitigated by *"freeze UI early and prioritise one validated backtest."* A beautiful UI over
one validated backtest wins; a spectacular UI over five unvalidated map pins does not.

---

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Visual direction** | Hydrographic chart | [`01-design-language.md`](01-design-language.md) |
| **Component foundation** | Radix Primitives, unstyled, plus our own token layer | Nothing inherited visually, so the design language actually lands |
| **Basemap** | Custom MapLibre vector style + cached satellite toggle | On-brand and offline-safe, with the real reef available for the demo |
| **Numerals** | Western digits in both languages, units bidi-isolated | [`06-bilingual-rtl.md`](06-bilingual-rtl.md) §5 |

**Stack.** Vite · React · TypeScript · Tailwind v4 (CSS-first tokens, native OKLCH) · Radix ·
MapLibre GL JS · TanStack Query · Zustand · i18next. App code in `frontend/` at repo root, matching the
concept doc's tree. Runs in Mahdi's Docker Compose alongside the API.

---

## Phases

| Phase | Days | Delivers | Gate |
|---|---|---|---|
| **0 · Language lock** | 3 Aug, half day | Tokens, fonts, three critical glyphs, specimen route | Direction approved. Visual debate closed. |
| **1 · Shell & map skeleton** | 3–4 Aug | Scaffold, token layer, i18n + RTL from the first component, MapLibre base style, layout regions, typed fixture client, Dockerfile into compose | Shell renders AR and EN. Map pans. Container runs. **Arabic labels render with the network off.** |
| **2 · Vertical slice** | 5–6 Aug | All map layers on fixtures, time slider driving them together, one risk card, mode switcher | **Hits the 6 Aug project gate.** Runs end to end. Ugly is acceptable. |
| **3 · The honest panels** | 7–9 Aug | Validation, provenance, limitations, assistant with citations | Every panel renders from real repo artefacts, not mockups. |
| **4 · Scenario & motion** | 7–9 Aug, parallel | Six scenario controls incl. transmission loss, SHAP drivers, confidence, the three orchestrated moments | Time-scrub holds 60fps with every layer live. |
| **5 · Bilingual & hardening** | 10–11 Aug | Full AR copy, RTL audit, empty/error/stale states, offline snapshot, Playwright scene walk green | **Wifi off, all eight scenes run.** |
| **6 · Freeze & demo** | 12–13 Aug | Rehearsal, backup video, deterministic demo mode verified | No new features. Day 12 `PROVISIONAL` gate passes. |

**The 6 August vertical slice is the most important date.** A system integrated on Day 11 has never
been tested.

---

## Day 1 asks — raise before anyone freezes an API

Seven contract details, listed in full with rationale in
[`07-data-contracts.md`](07-data-contracts.md) §1. In brief:

1. Plume as contoured GeoJSON, **not** GeoTIFF — the current file is 4.2 MB → **Abd**
2. Pre-downsampled hyetograph — the table is ~2.3 M rows → **Pulga / Nizar**
3. Figure delivery and thumbnails — 48 MB of PNGs → **Pulga**
4. `/ask` citations as a structured array → **Pulga**
5. SHAP drivers as objects with stable keys → **Mahdi**
6. Confidence as components, not a sentence → **Nizar / Mahdi**
7. Units never baked into value strings → **everyone**

Plus the one item with no engineering fallback:

> **Who writes and reviews the Arabic limitations copy?** Machine-translating scientific caveats is a
> scientific-integrity risk and concept §22.4 scores exactly that.

---

## Dependencies

| From | What | When | Blocked? |
|---|---|---|---|
| **Pulga** | Typed endpoints, stubs acceptable | Day 3 | Yes until then — shell and layout proceed on fixtures |
| **Nizar** | Stable read schema | Day 3 | No |
| **Abd** | Plume layers per timestep | Day 6 | No — stub with a static polygon |
| **Mahdi** | Risk fields + driver list | Day 5 | No — stub |
| **Mahdi** | Compose slot for the frontend container † | Day 2 | No — Dockerfile can land first |
| **Pulga (QA)** | 43 figures + captions | Day 4 | No — already in the repo |

† Not in the task file's table — added here because DoD item 9 requires the frontend to run in Compose.

---

## Storyboard traceability

Concept §15.3, adjusted for what exists. Each scene maps to named components in
[`04-component-inventory.md`](04-component-inventory.md). **A scene with no component by the end of
Phase 4 is a schedule alarm, not a Day 12 surprise.**

| # | Scene | Depends on |
|---|---|---|
| 1 | The problem — narrow coast, steep catchments, reef metres from shore | Base map, catchments, reef zones |
| 2 | A historical storm — select `AQ-2016-10-28` | Event selector |
| 3 | Land prediction — rainfall, runoff probability, activated outlet | Hyetograph, catchment colouring, risk card |
| 4 | Marine prediction — plume at T+3 / +6 / +12 / +24 | Plume layer, time slider, **plume bloom** |
| 5 | Reef exposure — zones shifting low to high | Exposure colouring, legend |
| 6 | Validation — modelled arrival vs the **measured mooring record** | Validation panel |
| 7 | What-if — raise rainfall 20%, rotate the wind | Scenario controls |
| 8 | Recommendation — the alert, with confidence and caveat | Alert card |

> Scene 6 in the concept doc says "reveal the actual post-event satellite plume." **That is
> superseded.** Satellite validation is a null result — both passes were 2.5–3.5 days after the plume
> dispersed. The mooring is the validation target, and the null result is shown as a finding.

---

## Risk register

| Risk | Mitigation |
|---|---|
| **MapLibre's RTL text plugin is registered by URL and the documented examples use a CDN.** Arabic map labels break with wifi off — silently, and only in Arabic. | Self-host, register eagerly at boot, verify in Phase 1 with the network disabled. Highest-value catch in this plan. |
| 48 MB of QA figures | WebP thumbnails at build time, lazy-load, full-res only in the lightbox |
| Plume delivered as raster | Day 1 ask #1. Fallback: contour client-side and accept the cost |
| Arabic subsetting is harder than Latin — shaping limits `unicode-range` splitting | Subset over the glyphs actually used; measure before Phase 5 |
| Radix under `dir="rtl"` — popovers, sliders, menus need per-primitive checks | Every primitive lands on the specimen route in RTL the day it is added |
| **Arabic scientific copy** | Named human reviewer. No technical fallback — raise Day 1 |
| Demo fails live | Deterministic demo mode: fixed snapshot, seeded scenario, byte-identical every run. Plus the recorded backup |
| Attribution missing — OSM, MapLibre, GMRT, Allen Coral Atlas | Persistent map attribution + the Data Sources table. Integrity is scored by §22.4 |
| Icon set eats the shell | Cut line named in advance: three glyphs in Phase 0, the rest in Phase 2 |

---

## Testing

Two artefacts, both cheap and both load-bearing.

**`/specimen` route** — every component, every state, **both themes × both directions**, on one page.
Cheaper than Storybook and it *is* the RTL QA tool. A primitive that is not on it has not been checked.

**Playwright scene walk** — one test driving all eight storyboard scenes end to end. Runs in CI and
again before the freeze. If the demo can break on stage, this catches it first.

---

## Definition of done

From [`06-ali.md`](../../../tasks/phase2/06-ali.md), unchanged:

1. Map with all layers, time slider, three modes.
2. Scenario controls including transmission loss.
3. Risk cards with SHAP drivers and a derived confidence figure.
4. Validation panel: modelled vs measured, plus the satellite null result.
5. Provenance panel: 43 figures + the data-sources table.
6. In-app limitations page.
7. Assistant with visible citations.
8. Bilingual AR/EN with working RTL.
9. Runs in Docker Compose; works with **wifi off** against the offline snapshot.

---

## Out of scope

[`../research/`](../research/) does not become a screen. It backs the market slide and the *"is this
only for Aqaba?"* answer in Q&A. Building it into the UI would spend frontend days on something one
slide already covers.
