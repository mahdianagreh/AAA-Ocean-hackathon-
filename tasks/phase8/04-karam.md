# Phase 8 — Karam

**Your pages this phase: 8 Provenance · 9 Site Scoring (content) · 12 Data Explorer.**

You own content accuracy on all three. **Ali implements the UI** — you are not expected
to write frontend code. On Page 9, **Pulga** separately confirms the backend response
fields; your half is the six criteria's plain-language names.

**This is a design and clarity phase.** No new features, no new data, no new endpoints.
Anything else you notice goes in the final report as a suggestion — do not act on it
inside this phase.

Standing law that bears directly on your three pages: **no fabricated categories, no
raw internal field names on screen, and every claim keeps its evidence.**

---

## PAGE 8 — Provenance
`frontend/src/routes/ProvenancePage.tsx`

### What Ali is building on this page

- [ ] **Redesign the image-detail modal**: proper padding; clear typographic hierarchy
      for the caption — **a short bold summary line + supporting detail**, not one
      dense paragraph; a **metadata row with icons** carrying Generated date,
      Processing chain, and a **Button: "View full resolution"** link.
- [ ] **Design the gallery/grid view** as a proper **thumbnail grid with hover
      states**, and a **filter/grouping by processing chain** — **if that data
      genuinely exists**. **Do not fabricate filter categories not backed by real
      data.**

### Your specific responsibility on this page

**As integration lead and owner of the QA figure manifest, confirm the grouping
categories used for the gallery filter (e.g. Marine, Terrain, Rainfall) match the real
categories in [`docs/qa_screenshots/MANIFEST.md`](../../docs/qa_screenshots/MANIFEST.md),
and confirm no figure is mis-captioned during the redesign.**

Two concrete things, and one correction the plan already found:

1. **The categories in the prompt are not the categories in the manifest.** The example
   grouping — *Marine, Terrain, Rainfall* — is illustrative. The manifest's **actual**
   headings today are:

   | heading | what it holds |
   |---|---|
   | Cross-cutting | |
   | Frontend | |
   | Land chain | |
   | Marine chain | |
   | Phase 2 backend | |
   | Produced by another workstream | |

   Fill in the right-hand column, then decide and tell Ali **which of these become
   user-facing filter chips**. "Phase 2 backend" and "Produced by another workstream"
   are *internal provenance* categories, not things a visitor would filter by — if they
   stay, they need plain-language names; if they go, say explicitly where their figures
   land instead. **A figure that belongs to no visible category disappears from the
   gallery**, and that is a silent loss, not a styling choice.

2. **"Processing chain" must be a real field, not a re-labelled heading.** The modal's
   metadata row promises *Processing chain* as a per-figure fact. Confirm whether that
   is genuinely recorded per figure in the manifest, or whether it is only inferable
   from the section a figure sits under. If it is only the section, say so — Ali should
   render the section it came from, honestly labelled, rather than a fabricated
   per-image chain.

3. **Caption integrity through the split.** Ali is splitting each caption into a bold
   summary line plus supporting detail. Walk the figure list and confirm, per figure,
   that the split does not strip the qualifier that made the caption true — the AOI it
   covers, the date it was generated, whether it shows provisional or final data. A
   caption whose summary line reads *"Reef zones"* over a figure built from
   `reef_zones_PROVISIONAL.gpkg` is a mis-caption, and it is exactly the kind that
   survives review.

4. **Confirm "Generated date" is real per figure**, and flag any figure predating
   **3 Aug 2026** — those may have been produced over the retired bounding box
   `(34.80, 29.25, 35.15, 29.70)`, which cut off ~85 % of Wadi Yutum. A figure drawn
   over the wrong extent looks perfectly fine. `python scripts/check_aoi_coverage.py`
   is the check.

---

## PAGE 9 — Site Scoring (content)
`frontend/src/routes/SiteScorePage.tsx` · backend fields confirmed separately by **Pulga**

### What Ali is building on this page

- [ ] **Redesign the "Candidate Area" form**: theme styling on the four coordinate
      inputs, **Button: "Score site"** styled to the primary button standard.
- [ ] **Rebuild the criteria results display.** Replace the flat text list with a real
      **scorecard**: **plain-language criterion name (not the raw `sites.criterion.C1`
      key)**, a **visual score indicator** (filled dots or a progress bar **out of 2**),
      the **supporting evidence sentence in smaller text**, and the **source shown as a
      small pill**.
- [ ] **Give the overall score prominent visual treatment** — a large number with a
      **radial/donut indicator or filled bar**, consistent with the 6-criterion
      scorecard styling already used in this project's own research materials.
- [ ] **Add a clearly styled note distinguishing a partial score** (*"5 of 6 criteria
      scored"*) **from a complete one.**

### Your specific responsibility on this page

**Confirm the six criteria's plain-language names match exactly the six-criterion
rubric already defined in the project's own research scan (`01-signature.md`), so the
redesigned labels don't drift from the established C1–C6 definitions.**

The labels the backend serves today are in `CRITERION_LABELS` at
[`backend/src/models/site_scoring.py:47`](../../backend/src/models/site_scoring.py#L47):

| key | label as shipped | matches `01-signature.md`? |
|---|---|---|
| C1 | Ephemeral, not perennial, drainage | |
| C2 | Rare but high-intensity rainfall | |
| C3 | Reef or seagrass within a few kilometres | |
| C4 | Narrow shelf or restricted-flushing basin | |
| C5 | Development at the outlet | |
| C6 | Data-poor and unmonitored | |

Fill in the right-hand column against the rubric in the research scan. Then:

1. **If a label has drifted, the rubric wins and the backend constant is what gets
   corrected** — not a second, prettier label typed into the frontend. Two sets of
   names for the same six criteria, one in Python and one in JSX, is how the definition
   quietly forks. Ali renders `CRITERION_LABELS`; you make `CRITERION_LABELS` right.
2. **Approve the short form.** Some labels are long for a scorecard row —
   *"Reef or seagrass within a few kilometres"*. If Ali needs a shortened display form,
   **you** write it, and it must not narrow the criterion (dropping "or seagrass"
   changes what C3 measures). If no faithful short form exists, the row wraps.
3. **The raw key stays visible as small secondary detail.** `C1`…`C6` are how the team
   and the research scan refer to these criteria — the rule is that
   `sites.criterion.C1` must not be the *headline*, not that the key disappears.
4. **Confirm the AR labels.** Six plain-language names need Arabic pairs. They are
   domain terms; they should not be machine-translated without your sign-off.
5. **Confirm the "out of 2" scale is right for a dot indicator.** Scores run `0–2` and
   may be fractional. If the real distribution is `0 / 1 / 2`, three dots are honest; if
   scores land at `1.5`, dots misrepresent and a bar is correct. Tell Ali which.

---

## PAGE 12 — Data Explorer
`frontend/src/routes/DataExplorerPage.tsx`

### What Ali is building on this page

- [ ] **Apply the same full theme pass**, **table styling (Page 2's pattern)**, and
      **card treatment** established across every other page.

### Your specific responsibility on this page

**Confirm the data categories and fields exposed in this explorer are current and match
what's actually queryable in the system today, since this page wasn't captured in the
reviewed screenshots and may have drifted from the current schema.**

This page is new and untracked in `git status` — it has had no review pass at all. Ali
is about to make it look finished, which makes any stale field on it *more* convincing,
not less. Before that happens:

1. **Enumerate what the page currently offers** — every category, every field, every
   filter — and mark each one **live**, **stale**, or **never existed**.
2. **Check each against the real artifact list**, `ARTIFACTS` in
   [`backend/src/api/data_access.py:31`](../../backend/src/api/data_access.py#L31):
   `catchments`, `outlets`, `coastline`, `reef_zones`, `reef_zones_provisional`,
   `bathymetry`, `landcover`, `soil`, `urban`, `rainfall_climatology`,
   `rainfall_daily`, `seasonal_risk_calendar`, `event_catalogue`, `event_dates`,
   `forecast_snapshot`, `data_dictionary`, `osm_buildings`, `osm_drainage`.
   A category the explorer offers that maps to no artifact is a dead end that will look
   like a feature once it is styled.
3. **Confirm every exposed field has a provenance row in
   [`docs/data_dictionary.md`](../../docs/data_dictionary.md).** This page is a data
   surface; a field a user can pull with no documented product ID, version, access date,
   licence and known limitation should not be pullable.
4. **Confirm source-vs-derived labelling survives.** A paper-reported number, a
   timezone-converted number and a computed number are three different things, and an
   explorer is precisely where they get flattened into one column.
5. **Confirm provisional data is named as provisional.** `reef_zones_PROVISIONAL` must
   not surface as plain "reef zones" here — the Day-12 gate is a `grep -ri PROVISIONAL`,
   and a UI label that drops the suffix defeats it.
6. **Confirm nulls render as gaps.** Missing is never zero, and a table is the easiest
   place in the product for a null to become a `0`.

---

## Your final report

- Page 8: the confirmed filter categories, the processing-chain verdict (real field vs
  section-inferred), and any mis-caption found.
- Page 9: the filled-in label comparison table, plus any correction pushed back into
  `CRITERION_LABELS`, and the approved AR names.
- Page 12: the live / stale / never-existed inventory, with anything stale flagged
  before Ali styles it.
- A Suggestions section for anything you noticed and deliberately did not act on.
