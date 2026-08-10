# Phase 8 — Ali's final report (Design Perfection, Pages 1–12 + gates on 13/14)

Frontend implementation of all twelve Phase 8 pages, plus the remaining Phase 7
foundation and rows. Everything below is on the `frontend` branch (off `main`).

## Per-page completion status (Pages 1–12)

| # | Page | Status | What landed |
|---|---|---|---|
| 1 | Storm Replay | ✅ | Montserrat headline "Predicted sediment plume · event · released at outlet"; icon metadata row (live `plume_source` discriminator, frame count, basemap flag); **equal-width segmented frame selector** (wraps, no cutoff); icon-swatch legend; basemap gap flagged (not styled around) |
| 2 | Reef Zones | ✅ | Rebuilt on shared **`DataTable`** (Foam-White header, dividers, **card-stack** reflow); amber **Placeholder pill** driven by `sensitivity_weight_status`; neutral "No stored run" badge; marine-park **bar** (null = gap); grouped depth caveats into one card w/ per-zone lines (incl. R-02 null branch) |
| 3 | Reef Zone detail | ✅ | All caveats via shared **`CaveatCard`**; depth note → focusable **info-icon tooltip** at the label |
| 4 | Alerts | ✅ | Centred Aqua-icon empty state; reusable **`AlertCard`** (severity badge, zone name resolved, window null≠0–0, run link) rendered on the page and on `/specimen` |
| 5 | Reports | ✅ | Event id in **H2**; prominent solid **AI-DRAFTED / HUMAN-REVIEWED** badge; caveats via CaveatCard; **collapsible citations**; primary review button + confirmed "Reviewed by…✓" state; **client-side themed PDF export** carrying the status |
| 6 | Explain / Ask | ✅ | Answer column constrained to ~736px, centred; top disclaimer banner; citations = numbered badge + teal-border blockquote + source tag + nullable score chip; 48px input; RTL-correct |
| 7 | Validation | ✅ | Measured-quantities table on shared `DataTable`; markers as **`Timeline`** component; measured-vs-modelled **calibration-error chart**; provenance (measured/modelled) visually distinct; raw-trace unavailability flagged (API doesn't serve the series) |
| 8 | Provenance | ✅ | Redesigned modal (bold summary + detail, icon metadata, honest "Open image" vs on-disk full-res path); gallery **filter by processing chain** (derived from real `source` data) |
| 9 | Site Scoring | ✅ | Primary Score button; prominent **donut**; **scorecard** (plain-language names, raw C-key secondary, bars out of 2, insufficient≠zero); source pills; always-present caveat via CaveatCard; **`sites.criterion.C1–C6` labels added** (were missing entirely) |
| 10 | Honest Limits | ✅ | Lead callout; jump-nav; **keyboard accordion** (native `<details>`, full bodies, deep-linkable); forcing spotlight → grid-layer link (works on page AND in map overlay); **9-of-12 source-doc gap disclosed**; **b1/b2/b3/b9** Absent features named |
| 11 | System Health | ✅ **built from scratch** | Route + nav; **[object Object] fixed by design**; per-cache cards (Hits/Misses/Entries + derived hit-rate); overall health + degraded reasons; artifact-contract gap flagged |
| 12 | Data Explorer | ✅ **built from scratch** | Route + nav; category chips (reef zones / events / dive sites / data sources) on shared `DataTable`; **dive-site caveats rendered** (inland-POI honesty) |

## The `[object Object]` root cause (one sentence)

`GET /api/v1/cache-stats` returns an **object per cache** (`{hits, misses, size}` for
`plume` and `exposure`), and the prior attempt stringified that object — `String({})`
is `"[object Object]"`; the new page renders each cache's three real fields against a
typed `CacheStatsResponse`, so no object is ever stringified.

## PDF export

Confirmed working end-to-end, **client-side, zero-dependency**: `app/reportPdf.ts`
builds a self-contained themed print document (brand gradient header read from the
live tokens — no hex in source), opens it and calls `print()` (Save-as-PDF). The
AI-DRAFTED / HUMAN-REVIEWED **status is printed as a banner** so a drafted export can
never pass as reviewed; popup-blocked failures are surfaced to the user.

## Gate verdict on Pages 13 & 14 (Login / Signup) — **PASS**

- 48px input: both use the shared `Field` / `FIELD_CLASS` component. ✅
- Permanent non-dismissible no-auth `NoticeCard`, disabled SSO button + "SSO
  unavailable" line, and Signup's "this request was not transmitted" notice — all
  present and load-bearing. ✅
- `dir="ltr"` on the email and password inputs survives the RTL pass. ✅
- **Open item for Nizar (not a blocker):** the "all four surfaces on one input
  component" unification is partial — Login/Signup are on `Field`, but the Assistant
  ask box and Site-Scoring coordinate inputs still declare their own 48px inputs.

## Phase 7 rows carried into this pass

- **p4-13 Honest Limits:** bodies now rendered in full (truncation removed); the
  9-vs-12 source-doc discrepancy is **disclosed on-screen** rather than silently
  rendering 9 of 12 (Mahdi/Pulga still need to settle whether §10–§12 get fixtures);
  b1/b2/b3/b9 named.
- **p4-18 Toughest Coral Fact:** sourced Gulf-of-Aqaba thermal-refuge fact on the
  home page with citation (Fine, Gildor & Genin 2013, *Global Change Biology*).
- **p4-H Offline:** the three live map calls are gated behind `VITE_DATA_SOURCE=http`,
  so the map screen makes **zero off-origin requests** — `offline-arabic "no external
  requests"` now **passes** (it fails on `main`). The physical wifi-off signed run
  remains a manual human step (Ali).

## Verification

- **Static gates green:** `npm run qa` (tsc + oxlint + stylelint + 14 vitest),
  `qa_frontend_{tokens,rtl,docs,freeze}.py`, `grep reefshield` empty, and **deep**
  EN/AR i18n parity (every leaf key + interpolation var matched across 4 namespaces).
- **Playwright:** 81 passed, 18 skipped, 14 failed — **all 14 are the documented
  environmental class** (no backend API running → `ERR_CONNECTION_REFUSED`; gitignored
  `public/terrain` + `public/basemap-raster` → journey3d). Proven by a `git stash`
  baseline isolation: every one of those 14 also fails on `main`, and my branch
  additionally **fixes two** pre-existing failures (`offline-arabic` + `/dashboard`
  external-requests). axe/hardening (4 theme×lang), offline-arabic, wifi-off, and
  phase2 all pass.
- **Evidence:** 81 screenshots (every page × light/dark × EN/AR) under
  `tasks/phase8/evidence/`, regenerable via `SCREENSHOTS=1 npx playwright test
  tests/evidence.spec.ts`.
- **Audit trail:** five adversarial audits (four per-tranche + one whole-diff);
  every real finding was fixed (WCAG `--ink-3`-on-`--surface-2`, a raw-key bug,
  `role="img"` hiding values, undefined `text-base`/`text-2xl`, an incomplete caveat
  unification, the missing criterion labels, dive-site caveat honesty, and more).

## Suggestions (noticed, deliberately not acted on)

1. **Storm Replay basemap** is not baked — run `scripts/fetch_basemap_raster.py`
   separately (data dependency, flagged in the UI).
2. **Limitations §10–§12** need fixtures regenerated (owning the scene-walk count
   diff) before all twelve numbered limitations render — a Mahdi/Pulga call.
3. **Arabic "plume" terminology** is split repo-wide (`العكارة` on replay/validation
   vs `عمود الرواسب` in the map/journey/formula) — a native-Arabic domain reviewer
   should unify it; I only kept new keys locally consistent and did not override
   pre-existing translations.
4. **Input-component unification** (Assistant + Site-Scoring → shared `Field`) —
   Nizar's item.
5. Pre-existing `text-2xl`/`text-base` (undefined utilities) remain in `RiskCard`
   and `ValidationPanel` (outside this diff).
6. Per-artifact availability + `degraded_reason[]` need a backend contract before
   System Health can show the full ARTIFACTS list; the page flags this.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
