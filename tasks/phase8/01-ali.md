# Phase 8 — Ali

**You implement the UI on all twelve pages in this phase.** Every other person on this
phase confirms content accuracy for their own domain; you write the frontend code for
every page below.

**Pages you own the implementation of:** all twelve.
1 Storm Replay · 2 Reef Zones (index) · 3 Reef Zone detail (Caveats) · 4 Alerts ·
5 Reports · 6 Explain/Ask · 7 Validation · 8 Provenance · 9 Site Scoring ·
10 Honest Limits · 11 System Health · 12 Data Explorer.

**The Dashboard is out of scope.** It got its premium pass in commit `0c335af` and is
the reference standard the other twelve are being brought up to.

**No new features, no new data, no new endpoints** beyond the two narrow backend items
named on Pages 5 and 11. Anything else you notice goes in the Suggestions section of
your final report, not into the code.

---

## Global rules — you apply these on all twelve pages

1. Every wall of plain paragraph text becomes structured content — cards, accordions,
   badges, icons, or a table.
2. Every caveat block gets one consistent treatment: **icon (⚠ Warning / ℹ Note) +
   bold headline + explanation + source as a small pill**. Never plain inline gray
   text. Build this once as a shared `CaveatCard` and use it on Pages 3, 5, 9 and
   anywhere else caveats render.
3. Repeated, near-identical caveats are grouped into **one** card, never repeated.
4. No raw internal field names visible to the user — `sites.criterion.C1` becomes
   "Ephemeral drainage," with the raw key kept only as small secondary detail.
5. No page renders `[object Object]` or any other unserialized raw value.
6. Fix data/asset dependencies where genuinely possible; where not, **flag explicitly
   rather than styling around it**.

## Standing law still in force from Phase 7

- **No hex literals.** Tokens only, from [`../phase7/00-design-system.md`](../phase7/00-design-system.md).
  `python3 scripts/qa_frontend_tokens.py` exits 0 before you push.
- **`--ink-3` never on `--surface-2`** — 4.17 contrast in dark, axe fails the build.
- **The hazard ramp is functional, never rebranded.** Use `BAND_CLASS` from
  `src/api/types.ts` for every severity colour. Do not make it blue to match the brand.
- **EN and AR keys land in the same commit as the component.** Every new accordion
  headline, pill, tooltip and button label in this phase is a new key pair across
  `common` / `nav` / `pages` / `tools`, kept at exact parity.
- **A number comes from the API or it does not go on screen.** Phase 8 adds no numbers.
- **Missing is never zero.** Nulls render as a visible gap via `ValueWithUnit`.
- **Every caveat the API sends still renders after your restructure.** You regroup and
  restyle. You delete none and you reword none.
- **Screenshot per page, light + dark, EN + AR**, or the row is not Done.

### Gates before every merge

```bash
cd frontend && npm run qa               # tsc + oxlint + stylelint + vitest
npx playwright test                     # 7 suites + the rebrand smoke walk
python3 scripts/qa_frontend_tokens.py
python3 scripts/qa_frontend_rtl.py
python3 scripts/qa_frontend_docs.py
```

---

## PAGE 1 — Storm Replay
`frontend/src/routes/ReplayPage.tsx` · content confirmed by **Abd**

- [ ] **Style the plume-playback frame container**: card radius, shadow, proper
      padding, Montserrat headline for
      *"Predicted sediment plume · [event] · released at [outlet]"*.
- [ ] **Style the legend box** to match the card system — rounded corners, padding,
      **icon swatches instead of plain colour blocks**.
- [ ] **Button: frame-selector control.** Currently the row of time-offset buttons at
      the bottom (`+3h`, `+6h`, `+12h` …). Rebuild as an **equally-sized
      pill/segmented control** with a clear Aqua-coloured active state. Fix the
      current inconsistent sizing and the cutoff.
- [ ] **Style the metadata bar** — *"Plume source: particle-engine · Frames: 6 ·
      Basemap: not baked…"* — as a **compact info row with a small icon per item**.
      The fields come from `PlumeFrames` in `src/api/live.ts`: `plume_source`,
      `frame_count`, `basemap_present`, `event_id`, `outlet_id`.
      `plume_source` is a live `'stub' | 'particle-engine'` discriminator — render
      what the API says, never a hard-coded label.
- [ ] **Do not attempt to generate the missing basemap yourself.** Flag in the final
      report that `scripts/fetch_basemap_raster.py` must be run separately. This is a
      **data dependency, not a styling fix**, and the UI must say the basemap is not
      baked rather than hide the gap behind styling.

---

## PAGE 2 — Reef Zones (index / list)
`frontend/src/routes/ReefZonesPage.tsx` · content confirmed by **Pulga**

**This page's table treatment is the pattern Pages 7 and 12 reuse. Build it as a
shared component.**

- [ ] **Redesign the data table**: Foam White header background, clean row dividers,
      consistent cell padding.
- [ ] **Replace** the plain *"Sensitivity weight: 1.00 / Placeholder…"* text with an
      **amber "Placeholder" pill** next to the number; move the explanatory sentence
      into a **tooltip**. The status comes from `ReefZoneRow.sensitivity_weight_status`
      (`'PLACEHOLDER_PENDING_MARINE_SCIENTIST' | 'SCIENTIST_ASSIGNED'`) — the pill is
      driven by that field, not by comparing the weight to 1.00.
- [ ] **Style "Current exposure: No stored run"** as a **neutral gray badge/pill**.
- [ ] **Style "Marine park overlap"** as a small **horizontal bar or percentage
      badge** (`marine_park_overlap_pct`, nullable — a null is a gap, not 0 %).
- [ ] **Confirm responsive reflow on narrow viewports with a real affordance** — a
      visible scroll cue or a card-stack breakpoint, **not silent horizontal scroll**.

---

## PAGE 3 — Reef Zone detail, Caveats section
`frontend/src/routes/ReefZonePage.tsx` · content confirmed by **Pulga**

- [ ] **Convert every "Warning ·" / "Note ·" block into its own card**: icon + bold
      plain-language headline + short explanation + **source as a styled pill**. This
      is the shared `CaveatCard`; `severity` drives the icon and accent.
- [ ] **Group the repeated `depth_median_m` warnings** for R-02, R-06, R-07 and R-08
      into **one** card:
      *"Bathymetry coverage is limited in zones R-02, R-06, R-07, R-08 — treat depth
      as indicative, not measured,"* with the **per-zone percentages as a small inline
      list** instead of four separate paragraphs.
      **The percentages are API values, not constants.** They are computed per request
      in `backend/src/api/caveats.py` → `depth_is_land_dominated`. Read each zone's
      number out of the caveat the API sent; do not type them into JSX.
      **R-02 is a different branch** — it has *no water cell at all* and its depth is
      null. It is not a percentage. Render it as its own line inside the grouped card:
      *"R-02 — no water cell in the 50 m bathymetry; depth unavailable."*
- [ ] **Move** *"Median depth is a bathymetric elevation: a negative value is below sea
      level"* into a small **inline tooltip / info icon next to the column header**.
- [ ] **Keep every fact unchanged.** This is a grouping and presentation task only. No
      caveat is dropped, merged away, or reworded.

---

## PAGE 4 — Alerts
`frontend/src/routes/AlertsPage.tsx` · content confirmed by **Pulga**

- [ ] **Style the empty state**: centred **outline icon in Aqua**, the existing
      headline and explanation in the theme's card style, generous padding.
      Keep the honest distinction Phase 7 established: *"no zone was reached"* and
      *"a zone was reached with negligible effect"* are different sentences.
- [ ] **Design the alert row/card component for future use** — build it even though
      there is currently no data to render in it. Fields, from `AlertRow` in
      `src/api/live.ts` (`GET /api/v1/alerts`):
      - **severity badge** coloured by risk band — `risk_level`
        (`minimal | low | moderate | high | critical`) through `BAND_CLASS`, plus
        `risk_score`
      - **reef zone name** — `reef_zone_id`, resolved to its zone name
      - **timestamp** — `issued_at`
      - **short summary line** — `headline_en` / `headline_ar`, picked by active locale
      - **arrival window** — `arrival_window_hours` is `[number, number] | null`;
        null renders as a gap, never as `0–0`
      - **link into the relevant event/report** — via `source_run_id`
      Render the component in the page's storybook/specimen route so it is reviewable
      with no live data.

---

## PAGE 5 — Reports
`frontend/src/routes/ReportsPage.tsx` · content confirmed by **Pulga**

- [ ] **Redesign the header**: event ID in **H2**; **Button/badge: "AI DRAFTED"**
      indicator made visually prominent — **solid amber/red background, white text**.
      It is currently a thin outline that is far too easy to miss. Driven by
      `ReportOut.status` (`'ai_drafted' | 'human_reviewed'`), never defaulted away.
      Generation timestamp (`generated_at`) and review status as a clean metadata row.
- [ ] **Separate** *"Exposure summary,"* *"Caveats carried with this run,"* and
      *"Sensor validation"* into clearly distinct sections with **H3 headers and real
      spacing**. These arrive as `ReportOut.sections[].title`.
- [ ] **Style every caveat using the same `CaveatCard` treatment as Page 3.**
- [ ] **Style citations as collapsed/truncated by default** with a
      **Button: "Show full citation"** expand toggle.
- [ ] **Button: "Mark as human-reviewed"** — style as a clear **primary action**, and
      design its **post-click confirmed state**: badge colour change, button becomes
      **disabled with a checkmark** and *"Reviewed by [name] · [date]"*.
      It calls the **real backend** — `reviewReport()` →
      `POST /api/v1/reports/{id}/review` — and re-renders from the returned
      `ReportOut` (`status`, `reviewed_by`, `reviewed_at`). **Not a local-only state
      change.**
- [ ] **Button: "Download PDF"** — export the report as a **themed PDF**: AQABA AQUA AI
      logo/gradient header band, PDF-safe equivalent of the Montserrat styling, the
      same section structure as on-screen, footer with generation date and review
      status. **Implement client-side** — `ReportOut` already carries the full
      structured content (`sections[].claims[].text` / `.source`), so no server-side
      endpoint is needed unless Pulga's file says otherwise.
      The PDF must carry the **AI-DRAFTED / HUMAN-REVIEWED status visibly**; a drafted
      report exported without it is indistinguishable from a reviewed one.

---

## PAGE 6 — Explain / Ask (Assistant)
`frontend/src/routes/AssistantPage.tsx` · content confirmed by **Pulga**

- [ ] **Fix the answer container's width and height** — constrain to **~680–760 px,
      centred**, replacing the current full-bleed-with-empty-space layout and
      unbounded scroll.
- [ ] **Style the** *"This assistant retrieves passages and quotes them…"* **disclaimer
      as a compact info banner** (icon + one line) at the **top of every answer**.
- [ ] **Style each numbered citation**: small **numbered badge**, quoted passage in a
      **blockquote with a Marine Teal left accent border**, source file/section as a
      **small styled tag beneath**. Fields come from `Citation` in `src/api/live.ts`
      (`POST /api/v1/ask`): `source_file`, `section`, `excerpt`, `score`. The number is
      the citation's **position in the `citations[]` array** — the API sends no id.
      `score` is nullable; a null score shows no score chip rather than `0`.
- [ ] **Style the input box and Button: submit/ask** to the foundation's **48 px input
      / theme button** standard.
- [ ] **Verify the redesigned layout mirrors correctly in Arabic/RTL** — the citation
      badge, the blockquote accent border and the source tag all flip. Not just
      paragraph direction. Use logical properties; `python3 scripts/qa_frontend_rtl.py`
      stays green.

---

## PAGE 7 — Validation
`frontend/src/routes/ValidationPage.tsx` · content confirmed by **Abd**

The structure here is already reasonable — this is a polish pass plus one real chart.

- [ ] **Apply full theme styling to the existing card layout.**
- [ ] **Style the "Measured quantities" table** matching **Page 2's table treatment**
      (same shared component).
- [ ] **Build a real line/area chart** (Marine Teal / Aqua palette) of the measured
      time-series markers — **salinity, turbidity** — against the modelled prediction.
- [ ] **Style "Timeline markers"** as a clean **horizontal/vertical timeline
      component** (icon + timestamp + label), not a plain list.
- [ ] **Style the event-selector dropdown** to match foundation input styling.
- [ ] **Source vs derived must survive the redesign.** Every plotted value carries a
      provenance label — `reported` vs `converted` — and the two must be **visually
      distinguished**, not rendered identically. This is a hard project rule, not a
      preference. Abd confirms the assignment per value.

---

## PAGE 8 — Provenance
`frontend/src/routes/ProvenancePage.tsx` · content confirmed by **Karam**

- [ ] **Redesign the image-detail modal**: proper padding; clear typographic hierarchy
      for the caption — **short bold summary line + supporting detail**, not one dense
      paragraph; **metadata row with icons** (Generated date, Processing chain,
      **Button: "View full resolution"** link).
- [ ] **Design the gallery/grid view** as a proper **thumbnail grid with hover
      states**, and a **filter/grouping by processing chain** — *only if that data
      genuinely exists*. **Do not fabricate filter categories not backed by real
      data.** The real groups come from `docs/qa_screenshots/MANIFEST.md`, whose actual
      headings today are: **Cross-cutting · Frontend · Land chain · Marine chain ·
      Phase 2 backend · Produced by another workstream.** Karam confirms the final
      grouping before you wire the filter.

---

## PAGE 9 — Site Scoring
`frontend/src/routes/SiteScorePage.tsx` · content confirmed by **Karam**, backend by **Pulga**

- [ ] **Redesign the "Candidate Area" form**: theme styling on the four coordinate
      inputs, **Button: "Score site"** styled to the **primary button standard**.
      The four inputs are the `bbox` tuple in `(west, south, east, north)` order —
      the same ordering as `config.spatial.BBox.wsen`. Label them so the user cannot
      transpose them.
- [ ] **Rebuild the criteria results display.** Replace the flat text list with a real
      **scorecard**:
      - **plain-language criterion name**, not the raw `sites.criterion.C1` key. The
        six names, verbatim from `backend/src/models/site_scoring.py` `CRITERION_LABELS`:
        | key | label |
        |---|---|
        | C1 | Ephemeral, not perennial, drainage |
        | C2 | Rare but high-intensity rainfall |
        | C3 | Reef or seagrass within a few kilometres |
        | C4 | Narrow shelf or restricted-flushing basin |
        | C5 | Development at the outlet |
        | C6 | Data-poor and unmonitored |
        Keep `C1`…`C6` as **small secondary detail** next to the label — the raw key
        stays visible as a reference, just not as the headline.
      - a **visual score indicator** — filled dots or a progress bar **out of 2**
        (`score` is `0–2`, and is **`null`, not `0`, when evidence is absent**)
      - the **supporting evidence sentence in smaller text** (`evidence[].excerpt`)
      - the **source as a small pill** (`evidence[].source_file` / `.section`)
- [ ] **Give the overall score prominent visual treatment** — large number with a
      **radial/donut indicator or filled bar**, consistent with the 6-criterion
      scorecard styling already used in this project's own research materials.
- [ ] **Add a clearly styled note distinguishing a partial score from a complete one** —
      *"5 of 6 criteria scored"* vs all six. A criterion with
      `status: 'insufficient_data'` renders as an explicit **"insufficient data"** state
      with its cited reason, **never as a zero-filled dot row**. Pulga supplies the
      accurate reason text; surface it in the UI rather than leaving it unexplained.
- [ ] **Render the always-present caveat** — the rubric was built and tuned against
      exactly one site — using the same `CaveatCard` as Page 3.

---

## PAGE 10 — Honest Limits
`frontend/src/routes/LimitationsPage.tsx` · content confirmed by **Mahdi**, docs by **Pulga**

- [ ] **Give "The one-line version" callout more visual weight** — larger text,
      distinct background tint, positioned as the page's **lead statement**.
- [ ] **Add a table of contents / jump-navigation** at the top linking to each major
      section.
- [ ] **Style "Ocean current resolution" as a highlighted spotlight card**, distinct
      from the numbered list.
- [ ] **Convert the numbered "things our data cannot tell you" list into an
      accordion.** Each item shows **only its number and bold headline by default**; a
      **Button: expand/collapse toggle** per item reveals the full explanation. **This
      is the single highest-impact change on this page.**
      Keyboard-operable, `aria-expanded` correct, and the deep-linked item from the
      table of contents opens expanded.
      **Item count follows the source document, not the current header.** The page
      header says nine; `docs/pitch_limitations.md` carries twelve numbered sections.
      Mahdi and Pulga settle the count before you build — do not silently render 9 of
      12.
- [ ] **Style "Turn on the ocean-model grid layer to see this rather than read it"** as
      an **actionable link/button** where applicable — it should navigate to the
      Dashboard with that layer enabled.
- [ ] **Keep every word of the actual limitation content unchanged.** The accordion
      headlines are new UI text and need EN/AR keys; the bodies are the source
      documents rendered verbatim.

---

## PAGE 11 — System Health & Diagnostics
`frontend/src/routes/SystemHealthPage.tsx` · content confirmed by **Nizar**

- [ ] **Fix the `[object Object]` rendering bug.** "Memory & Cache Stats" currently
      shows literally `[object Object]` for both **Plume** and **Exposure**.
      **Root cause, already located:**
      [SystemHealthPage.tsx:85](../../frontend/src/routes/SystemHealthPage.tsx#L85)
      renders `{typeof value === 'number' ? value.toLocaleString() : String(value)}`
      while iterating `Object.entries(cacheStats)`. But
      `GET /api/v1/cache-stats`
      ([main.py:2031](../../backend/src/api/main.py#L2031)) returns
      `{"plume": PLUME_CACHE.stats(), "exposure": EXPOSURE_CACHE.stats()}`, and
      `TTLCache.stats()`
      ([data_access.py:855](../../backend/src/api/data_access.py#L855)) returns
      **`{"hits": int, "misses": int, "size": int}`**. Each value is therefore an
      **object**, and `String({})` is `"[object Object]"`.
      **Fix:** render each cache as its own card with its three real fields —
      **Hits · Misses · Entries (`size`)** — plus a derived hit-rate if you show one,
      computed in the component, labelled as derived. Type the response instead of
      `Record<string, unknown>` so this cannot recur. Nizar confirms the field list.
- [ ] **Redesign "Artifact Availability"** from a flat two-column list into **grouped,
      categorized status cards** with a consistent **status badge per item**. The keys
      come from `ARTIFACTS` in
      [data_access.py:31](../../backend/src/api/data_access.py#L31); group them by what
      each artifact actually is — Nizar confirms the final grouping. The real keys are:
      `catchments`, `outlets`, `coastline`, `reef_zones`, `reef_zones_provisional`,
      `bathymetry`, `landcover`, `soil`, `urban`, `rainfall_climatology`,
      `rainfall_daily`, `seasonal_risk_calendar`, `event_catalogue`, `event_dates`,
      `forecast_snapshot`, `data_dictionary`, `osm_buildings`, `osm_drainage`.
      Also render the raw key as small secondary detail — an operator needs it to know
      which file to go fix.
- [ ] **Keep the "Overall Health" OK badge treatment**, confirming it matches the final
      theme pass. `degraded_reason[]` stays fully rendered when non-empty.

---

## PAGE 12 — Data Explorer
`frontend/src/routes/DataExplorerPage.tsx` · content confirmed by **Karam**

- [ ] **Apply the same full theme pass**, **table styling (Page 2's pattern)**, and
      **card treatment** established across every other page.
      This page is new and was not captured in the reviewed screenshots — Karam
      confirms the categories and fields it exposes are current before you finalize.

---

## PAGES 13 & 14 — Sign in and Request access — **you do not implement these**
`frontend/src/routes/Login.tsx` · `frontend/src/routes/Signup.tsx`

**Nizar owns these two end to end** — content, backend and frontend — because they rest
on Supabase. You hold the **cross-cutting gates** on them exactly as you do everywhere
else: tokens, i18n parity, RTL, axe, and the right to reject a merge that breaks the
design system. You write no code on them.

Three things to watch for when they reach you for review:

- [ ] **The 48 px input component.** Both files currently declare their own local
      `const FIELD = 'h-12 w-full rounded-md border bg-surface px-4 …'` — the
      foundation input hand-copied twice. Nizar is lifting it into the shared component
      you are already using on Page 6's ask box and Page 9's coordinate form. **Make
      sure all four surfaces end up on one component**, not four near-identical copies.
- [ ] **The permanent notice must still be there.** Both screens carry a
      non-dismissible notice stating there is no auth backend, plus a deliberately
      disabled SSO button and a "not transmitted" paragraph on Signup's confirmation.
      **These are load-bearing honest claims, not unfinished UI.** If a diff removes or
      softens any of them without a working session behind it, reject it — that is the
      one review call on these pages that is unambiguously yours to make.
- [ ] **`dir="ltr"` on the email and password inputs is intentional** and must survive
      your RTL pass. An email address and a password are LTR strings even in an Arabic
      UI.

---

## Your final report

Per-page status for Pages 1–12, the `[object Object]` root cause in one sentence,
confirmation the PDF export works end to end, your gate verdict on Pages 13 and 14, and
a **Suggestions** section for everything you noticed and deliberately did not build.
