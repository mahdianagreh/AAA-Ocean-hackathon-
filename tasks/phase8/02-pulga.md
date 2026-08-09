# Phase 8 — Pulga

**Your pages this phase: 3, 4, 5, 6, 9 (backend fields), 10 (backend / limitations
docs).** You own the backend, the exposure engine and the RAG layer, so on every one
of these pages your job is to confirm that **what Ali styles matches what the API
actually returns** — before he styles it, not after.

Ali writes the frontend code. You are not expected to write it. You are expected to
make sure he is not styling against guessed fields, and — on Pages 5, 9 and 10 — to
answer three backend questions that block his implementation.

**This is a design and clarity phase.** No new features, no new data, no new endpoints
except where explicitly stated below (Page 5's PDF question, and only if genuinely
required). Anything else you notice goes in the final report as a suggestion.

Standing law from Phase 7 still applies: **every caveat the API sends must render**,
**missing is never zero**, **a number comes from the API or it does not go on screen**.
Phase 8 regroups and restyles caveats. It deletes none and rewords none.

---

## PAGE 3 — Reef Zones (detail page, Caveats section)
`frontend/src/routes/ReefZonePage.tsx`

### What Ali is building on this page

- Every "Warning ·" / "Note ·" block becomes its own card: icon + bold plain-language
  headline + short explanation + source shown as a styled pill.
- The repeated `depth_median_m` warnings for **R-02, R-06, R-07, R-08** are grouped
  into **one** card: *"Bathymetry coverage is limited in zones R-02, R-06, R-07, R-08 —
  treat depth as indicative, not measured,"* with the per-zone percentages as a small
  inline list instead of four separate paragraphs.
- *"Median depth is a bathymetric elevation: a negative value is below sea level"*
  moves into a small inline tooltip / info icon next to the column header.
- Every fact stays unchanged — grouping and presentation only.

### Your specific responsibility on this page

**Verify the grouped bathymetry-warning card still states the correct per-zone
percentages after grouping — 52 % R-06, 74 % R-07, 51 % R-08, and R-02's "no water
cell" case. A grouping error here would misstate real data.**

Two things to check, and one correction the plan already found:

1. **The percentages are computed, not constant.** They come from
   `depth_is_land_dominated()` in
   [`backend/src/api/caveats.py:148`](../../backend/src/api/caveats.py#L148), which
   formats `land_pct` per request into the caveat message. Confirm the values the API
   returns today for R-06, R-07 and R-08 still match 52 % / 74 % / 51 %. If the
   bathymetry inputs have moved since those numbers were quoted, **the API value wins**
   and the card renders whatever the API sent — Ali must parse the number out of the
   caveat rather than typing it into JSX.

2. **R-02 is a different branch and cannot be folded into a percentage list.** In that
   same function, R-02 hits the `depth_median is None` branch — *"no water cell in the
   50 m bathymetry at all, so depth is unavailable. Reported as null, never as 0."*
   That is a **null**, not a percentage. Confirm the grouped card renders it as its own
   line inside the group, worded as the absence it is, and that it never appears as
   `0 %` or gets averaged into the other three.

3. **Confirm the threshold that decides membership of the group.** The warning fires at
   `land_pct >= 50`. If a fourth zone crosses 50 % on the current data, the card's zone
   list must grow — a hard-coded four-zone list would then be wrong. Tell Ali whether
   the group is derived from the caveat set at runtime (it should be) or fixed.

4. **Confirm no caveat is lost in the grouping.** Count the caveats the API sends for a
   zone before and after Ali's change. Same count in, same facts out.

---

## PAGE 4 — Alerts
`frontend/src/routes/AlertsPage.tsx`

### What Ali is building on this page

- The empty state is styled: centred outline icon in Aqua, existing headline and
  explanation in the theme's card style, generous padding.
- **The alert row/card component is designed for future use** — severity badge coloured
  by risk band, reef zone name, timestamp, short summary line, link into the relevant
  event/report — **built even though there is currently no data to render in it**.

### Your specific responsibility on this page

**Confirm the future alert-card component's fields match the actual schema returned by
`GET /api/v1/alerts`, so the component isn't built against guessed fields.**

The frontend's `AlertRow` interface in
[`frontend/src/api/live.ts:72`](../../frontend/src/api/live.ts#L72) currently declares:

| field | type | note to confirm |
|---|---|---|
| `alert_id` | string | |
| `source_run_id` | string | is this what the "link into the relevant event/report" resolves through? |
| `reef_zone_id` | string | Ali needs zone **name**, not id, on the card — confirm where he gets it |
| `risk_level` | `minimal \| low \| moderate \| high \| critical` | drives `BAND_CLASS` |
| `risk_score` | number | |
| `issued_at` | string | |
| `arrival_window_hours` | `[number, number] \| null` | confirm null is legitimate and must render as a gap, never `0–0` |
| `headline_en` | string | |
| `headline_ar` | string | confirm AR headlines are populated, not empty strings |

Confirm each of these still matches the live response. Flag any field the interface
declares that the endpoint no longer sends, and any field the endpoint sends that the
interface does not declare.

Also confirm, for the empty state's wording, the distinction Phase 7 established still
holds on this endpoint: **"no zone was reached"** and **"a zone was reached with
negligible effect"** are different sentences, and `/alerts` returning `[]` legitimately
means the first, not the second.

---

## PAGE 5 — Reports
`frontend/src/routes/ReportsPage.tsx`

### What Ali is building on this page

- Header redesigned: event ID in H2; the **"AI DRAFTED" badge** made visually prominent
  — solid amber/red background, white text, replacing the current thin outline that is
  too easy to miss; generation timestamp and review status as a clean metadata row.
- *"Exposure summary,"* *"Caveats carried with this run,"* and *"Sensor validation"*
  separated into distinct sections with H3 headers and real spacing.
- Every caveat styled with the same card treatment as Page 3.
- Citations collapsed/truncated by default with a **"Show full citation"** expand
  toggle.
- **Button: "Mark as human-reviewed"** — styled as a clear primary action, with a
  designed post-click confirmed state: badge colour change, button disabled with a
  checkmark and *"Reviewed by [name] · [date]"*.
- **Button: "Download PDF"** — themed PDF export: AQABA AQUA AI logo/gradient header
  band, PDF-safe equivalent of the Montserrat styling, same section structure as
  on-screen, footer with generation date and review status.

### Your specific responsibility on this page

**(a) Confirm whether `POST /api/v1/reports/generate` already returns enough structured
data for a client-side PDF export, or whether a dedicated server-side PDF endpoint is
needed. Implement the server-side version only if genuinely required.**

The evidence points to **client-side being sufficient** — confirm or overturn it.
`ReportOut` ([`live.ts:313`](../../frontend/src/api/live.ts#L313)) carries
`report_id`, `event_id`, `status`, `generated_at`, `reviewed_at`, `reviewed_by`, and
`sections[]` where each section is `{title, claims[{text, source}]}`. That is the full
on-screen content in structured form, which is everything the PDF needs. State plainly
whether anything on the rendered page comes from a source **other** than `ReportOut`
— if it does, that is the thing that decides the question. **Do not add an endpoint we
do not need.**

**(b) Confirm the "Mark as human-reviewed" button correctly calls the real backend, not
a local-only state change.**

The route exists —
[`POST /api/v1/reports/{id}/review`](../../backend/src/api/main.py#L2020), wrapped as
`reviewReport(id, reviewedBy)` at
[`live.ts:468`](../../frontend/src/api/live.ts#L468), and it 404s on an unknown report.
Confirm that after Ali's redesign the button:

- posts to that route with a real `reviewed_by` value (confirm where that name comes
  from — the account session, or a prompt),
- re-renders its confirmed state **from the returned `ReportOut`** (`status` flipping
  to `human_reviewed`, plus `reviewed_by` and `reviewed_at`), not from a local
  `useState` flag,
- and that a failed request leaves the badge on `ai_drafted` rather than optimistically
  showing reviewed.

**(c) Confirm the status badge survives into the PDF.** `status` is
`'ai_drafted' | 'human_reviewed'` and the frontend comment is explicit that it is never
defaulted away: *a drafted report shown without this badge is indistinguishable from a
reviewed one, which is the whole risk.* An exported PDF is the easiest place for that
badge to get lost. Check the export, not just the screen.

---

## PAGE 6 — Explain / Ask (Assistant)
`frontend/src/routes/AssistantPage.tsx`

### What Ali is building on this page

- The answer container's width and height are fixed — constrained to ~680–760 px,
  centred, replacing the current full-bleed-with-empty-space layout and unbounded
  scroll.
- The *"This assistant retrieves passages and quotes them…"* disclaimer becomes a
  compact info banner (icon + one line) at the top of every answer.
- Each numbered citation is styled: small numbered badge, quoted passage in a
  blockquote with a Marine Teal left accent border, source file/section as a small
  styled tag beneath.
- The input box and the submit/ask button match the foundation's 48 px input / theme
  button standard.
- The redesigned layout is verified to mirror correctly in Arabic/RTL, not just
  paragraph direction.

### Your specific responsibility on this page

**Confirm the citation numbering and source-tag format matches exactly what
`POST /api/v1/ask` returns, so Ali isn't styling against assumed fields.**

`AskResponse` ([`live.ts:298`](../../frontend/src/api/live.ts#L298)) declares
`answer`, `citations[]`, `language`, `corpus_files_searched`; each `Citation` is
`{source_file, section, excerpt, score}` with `score` nullable.

Confirm specifically:

1. **Where the citation number comes from.** The API sends no citation id — the number
   is the item's **position in the `citations[]` array**. Confirm that, and confirm
   whether the numbers in the `answer` text itself (if the answer contains `[1]`-style
   markers) are **guaranteed to line up with that array order**. If they are not, say
   so loudly — a badge numbered `2` next to the passage the answer calls `[3]` is worse
   than no numbering.
2. **What the source tag should read as.** `source_file` is a repo path. Confirm the
   exact display format Ali should render — path as-is, basename, or
   `basename · section` — and whether `section` is always populated.
3. **`score` is nullable.** Confirm a null score means "not scored" and must render as
   no chip, never as `0`.
4. **The disclaimer text is fixed wording.** Confirm the exact sentence Ali should put
   in the info banner, and that the LLM layer never computes a number — the assistant
   retrieves and quotes.
5. **The corpus exclusion still holds.** `docs/ali/` is not an app surface and is not in
   the RAG corpus. Confirm `GET /api/v1/ask/corpus` still shows it excluded, so no
   citation can ever tag a `docs/ali/` file.
6. **Arabic.** `language` is `'en' | 'ar'`. Confirm what an Arabic answer's citations
   look like — whether `excerpt` comes back in Arabic or stays in the source language —
   so Ali's RTL blockquote handles a mixed-direction passage correctly.

---

## PAGE 9 — Site Scoring (backend fields)
`frontend/src/routes/SiteScorePage.tsx` · content owner on this page is **Karam**

### What Ali is building on this page

- The "Candidate Area" form gets theme styling on the four coordinate inputs, and the
  **"Score site"** button is styled to the primary button standard.
- The flat text list of criteria is **rebuilt as a real scorecard**: plain-language
  criterion name (not the raw `sites.criterion.C1` key), a visual score indicator
  (filled dots or a progress bar out of 2), supporting evidence sentence in smaller
  text, source shown as a small pill.
- The overall score gets prominent visual treatment — large number with a radial/donut
  indicator or filled bar.
- A clearly styled note distinguishes a partial score (*"5 of 6 criteria scored"*) from
  a complete one.

### Your specific responsibility on this page

**(a) Confirm `POST /api/v1/sites/score`'s response fields map correctly to the new
scorecard component.**

`SiteScoreResponse` ([`schemas.py:637`](../../backend/src/api/schemas.py#L637)) returns
`site_id`, `site_name`, `bbox`, `criteria[]`, `narrative`, `caveats[]`. Each
`CriterionScore` is:

| field | type | what the scorecard must do with it |
|---|---|---|
| `criterion` | `C1`…`C6` | **never the headline** — plain-language label leads, raw key is small secondary detail |
| `score` | `float \| null`, `0 ≤ score ≤ 2` | **`None`, not `0.0`, when evidence is absent — a gap is a gap.** Confirm the dots/bar render a null as an empty "not scored" state, never as zero filled dots |
| `status` | `scored \| insufficient_data` | drives the partial-score note |
| `evidence` | `Citation[]` | **non-empty even when `insufficient_data` — the absence itself is cited.** Confirm the scorecard shows that evidence rather than hiding the row |

Confirm the evidence uses the **same `Citation` shape as `/ask`** (it reuses it
verbatim, by design — never a second citation format), so Ali can reuse Page 6's
source-tag styling here.

Also confirm `bbox` ordering for the four form inputs: `(west, south, east, north)`,
the same as `config.spatial.BBox.wsen`. A transposed form silently scores the wrong box
— the exact failure mode this project keeps hitting.

**(b) Confirm why a site can return "5 of 6 criteria scored" — and surface that reason
accurately in the UI rather than leaving it unexplained.**

A criterion returns `status="insufficient_data"` when the requested box falls outside
where that criterion's real evidence source has coverage — the endpoint is deliberately
**not restricted to the Aqaba AOI**, and an out-of-coverage box gets an honest gap
rather than a fabricated score. The six criteria draw on different sources
([`main.py:1915`](../../backend/src/api/main.py#L1915)): OSM drainage (C1), rainfall
climatology per overlapping catchment (C2), reef zones (C3), bathymetry stats (C4), OSM
buildings (C5), and C6 which takes no spatial input.

Write out, per criterion, **the one-sentence plain-language reason** a box can miss it
— that sentence is what Ali renders next to the insufficient-data state. Confirm C2's
special case in particular: it scores from the **catchments the box overlaps**, so a box
overlapping no catchment has nothing to score against.

**(c) Confirm the always-present caveat renders.** Every response carries
`ONE_SITE_CAVEAT` regardless of which box was scored: *"This six-criterion rubric was
built and tuned against exactly one site — Aqaba. A score for any other coordinate is
the rubric's first real test, not a validated instrument."* Confirm it survives the
redesign as a `CaveatCard`, not as small print under the donut.

---

## PAGE 10 — Honest Limits (backend / source documents)
`frontend/src/routes/LimitationsPage.tsx` · content owner on this page is **Mahdi**

### What Ali is building on this page

- *"The one-line version"* callout gets more visual weight — larger text, distinct
  background tint, positioned as the page's lead statement.
- A **table of contents / jump-navigation** at the top links to each major section.
- *"Ocean current resolution"* becomes a highlighted spotlight card, distinct from the
  numbered list.
- **The numbered "things our data cannot tell you" list becomes an accordion.** Each
  item shows only its number and bold headline by default; an expand/collapse toggle
  per item reveals the full explanation. **This is the single highest-impact change on
  this page.**
- *"Turn on the ocean-model grid layer to see this rather than read it"* becomes an
  actionable link/button where applicable.
- Every word of the actual limitation content stays unchanged.

### Your specific responsibility on this page

**Confirm this page's content still matches `docs/pitch_limitations.md` and
`docs/forcing_limitations.md` verbatim after restructuring — the accordion must not
silently diverge from the source documents this page is meant to render.**

The page's own header comment says it renders those two documents and *"cannot"*
diverge from them. After Ali's restructure, prove that is still true:

1. **Settle the item count with Mahdi before Ali builds the accordion.** The page is
   described as *"9 things our data cannot tell you"*.
   [`docs/pitch_limitations.md`](../../docs/pitch_limitations.md) carries **twelve**
   numbered sections — §1 land cover snapshot, §2 global soil model, §3 no GEBCO, §4
   bathymetry cannot see the reef shelf, §5 reef sensitivity weights are assumptions,
   §6 ACA maps shallow reef only, §7 OSM maps what is mapped, §8 what we would fix
   first, §9 satellite plume validation failed, §10 site scoring validated on one site,
   §11 adaptive sampling not demoable, §12 coral vision model is a heuristic.
   Either the page renders a deliberate subset — in which case say which, and why, and
   make the header honest — or the count has drifted and the accordion must carry all
   twelve. **A 9-item accordion over a 12-item source silently drops three real
   limitations**, which is precisely the failure this page exists to prevent.
2. **Confirm the "one-line version" text** Ali is about to enlarge is the current §"The
   one-line version" from the source document, word for word.
3. **Confirm which limitation the "Ocean current resolution" spotlight card carries**,
   and that promoting it out of the numbered list does not renumber or orphan the
   others.
4. **Confirm the forcing-limitations half** still matches
   [`docs/forcing_limitations.md`](../../docs/forcing_limitations.md) — including the
   *permanent* vs *temporary* distinction the page currently draws
   (`limitations.forcingPermanent`), which must not be flattened by the restructure.
5. **Confirm the doc-vs-screen gate still passes.** `python3 scripts/qa_frontend_docs.py`
   checks doc claims against measured values; it must stay green after the accordion
   lands. If the accordion moves content into i18n keys that the gate no longer sees,
   say so — that would be a real loss of enforcement, not a styling detail.
6. **Arabic.** The page currently shows an `arabicPending` note for the source
   documents. Confirm whether that is still accurate, and confirm the **accordion
   headlines** (new UI text, EN/AR both required) are separate from the document bodies
   that note refers to.

---

## Your final report

For each of the six pages above: what you confirmed, what you found wrong, and the
exact field-level answers Ali needs. Call out separately the three decisions that block
him — **the PDF client-vs-server verdict (Page 5), the insufficient-data reasons
(Page 9), and the accordion item count (Page 10)**. End with a Suggestions section for
anything you noticed and deliberately did not act on.
