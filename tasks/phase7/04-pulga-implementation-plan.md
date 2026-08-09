# Phase 7 — Pulga · Implementation Plan

Companion to [`04-pulga.md`](04-pulga.md). That file says **what** and **why**; this
one says **in what order, in which file, and how you know it worked.**

Everything below was verified against the running stack on 8 Aug 2026, not read off
a planning doc. Where a payload is quoted, it came out of `curl`.

---

## 0. Ground truth — captured once, so nobody re-derives it

### 0.1 The exposure formula is a product chain, and it closes

```
POST /api/v1/exposure/calculate
{ "event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02", "horizon_hours": 22 }
```

```
raw_score  = plume_probability            0.75
           × relative_sediment_intensity  0.08386194638531504
           × exposure_duration_weight     0.6818181818181818
           × habitat_sensitivity_weight   1.0
           × confidence_adjustment        0.8
           = 0.03430715988490161          ← matches raw_score exactly

risk_score = raw_score × score_scale (100.0) = 3.4307159884901606
risk_level = "minimal"
```

**This multiplies out to the last decimal.** That is the whole of `p4-12`: you are not
inventing an explanation, you are *rendering an identity that already balances*. Show
the five factors, the product, and the scale — and a reader can check your arithmetic
on screen. Almost nothing else in this project is that clean; use it.

### 0.2 The 25 `formula_terms` keys, grouped by the job they do

| Group | Keys |
|---|---|
| **The five factors** | `plume_probability`, `relative_sediment_intensity`, `exposure_duration_weight`, `habitat_sensitivity_weight`, `confidence_adjustment` |
| **The arithmetic** | `raw_score`, `score_scale`, `risk_score`, `risk_level` |
| **Placeholder flags** | `habitat_sensitivity_weight_status` = `PLACEHOLDER_PENDING_MARINE_SCIENTIST` |
| **Geometry** | `zone_fraction_affected`, `max_exposure_probability`, `n_overlay_rows`, `measure_crs` = `EPSG:32636` |
| **Timing** | `arrival_window_hours` `[3.0, 18.0]`, `horizon_hours`, `contour_times_hit` `[3,6,9,12,18]` |
| **Provenance** | `relative_sediment_intensity_source`, `plume_source` = `REAL_PARTICLE_ENGINE`, `model_versions`, `transmission_loss` |
| **Confidence detail** | `confidence_adjustment_reason`, `confidence_members_exceeding` `0`, `confidence_members_total` `30`, `confidence_threshold_value_mm` `2.3467` |

`ExposureResult` also carries, outside `formula_terms`: `reef_zone_id`, `risk_score`,
`risk_level`, `arrival_window_hours`, `max_exposure_probability`,
`zone_fraction_affected`, `confidence`, `adjusted_priority`,
`adjusted_priority_status`, `caveats`.
The run carries `run_id`, `event_id`, `outlet_id`, `created_at`, `results`,
`model_versions`, `caveats`.

### 0.3 Three facts about the code as it stands today

1. **`ScenarioDrawer.tsx` (110 lines) never calls the API.** Its only side effect is
   `setScenario(key, value)` into zustand. Phase 6's FAIL is live and current.
2. **`fetchExposure(eventId, outletId)` hardcodes `horizon_hours: 24`** and sends no
   scenario parameters (`live.ts:100`). It has no way to express them yet.
3. **`ReefZonePage.tsx` contains zero references to `formula_terms`.** `p4-12` is
   genuinely not started.

And one piece of good news the task file understates: **`AssistantPage.tsx` already
calls the live `ask()`** (`line 67`). `core-E` is a hardening job, not a build.

### 0.4 The parameters the API will accept

`backend/src/api/schemas.py:446-447`

```python
rainfall_multiplier:        float       = Field(default=1.0, ge=0.5, le=2.0)
transmission_loss_override: float|None  = Field(default=None, ge=0.20, le=0.85)
```

Both are echoed back in `formula_terms` regardless of whether they were set — which is
exactly what makes the drawer demonstrable.

---

## 1. Build order, and why it is this order

```
WP0  shared primitives ──┬──> WP1  scenario drawer      (fixes the recorded FAIL)
                         │         │
                         │         └──> WP2  formula inspector   (the demo centrepiece)
                         │                    │
                         ├──> WP3  b8 + b7 safeguard  ───────────┘  (shares the zone page)
                         ├──> WP4  reports
                         ├──> WP5  sites
                         ├──> WP6  assistant hardening
                         └──> WP7  alerts + zone comparison
```

Three ordering decisions worth stating:

- **WP1 before WP2.** The formula inspector's most persuasive moment is a slider moving
  and a factor changing. Build the thing that moves first, or you will build the
  inspector twice.
- **WP0 first, always.** Five of your seven packages need the same four primitives. Build
  them once or you will ship five slightly different status badges, which is precisely
  the failure Ali is empowered to reject.
- **WP3 is scheduled early despite being "already PASS".** Phase 6 passed the *backend*
  safeguard. The UI is where it gets undone, and it is the single highest-consequence
  screen you own.

---

## 2. WP0 — Shared primitives (build these first, half a day)

All in `frontend/src/components/`. Every one is used by two or more later packages.

### 2.1 `FormulaChain.tsx`

Renders a product identity as an inspectable chain.

```tsx
interface Factor {
  key: string;            // formula_terms key, e.g. 'plume_probability'
  label: string;          // i18n'd
  value: number;
  source?: string;        // provenance string, if the payload carries one
  placeholder?: string;   // e.g. 'PLACEHOLDER_PENDING_MARINE_SCIENTIST'
}
<FormulaChain factors={Factor[]} product={number} scale={number} result={number} />
```

- Lays out `a × b × c × d × e = raw`, then `raw × scale = score`, wrapping to a
  column on narrow viewports.
- Every number goes through `<ValueWithUnit>`. No exceptions.
- A factor with `placeholder` gets a visible marker **and** its explanation inline —
  not a tooltip. Tooltips do not survive a screenshot, and screenshots are the
  evidence format for this phase.
- **Self-check on render:** compare the product of the factors against `raw_score`
  with a tolerance of `1e-9`. If they disagree, render a loud "these numbers do not
  multiply out" state rather than the chain. That mirrors the backend's own
  number-fidelity guard on `/explain`, and it means a future formula change that this
  component does not understand fails visibly instead of silently.

### 2.2 `StatusBadge.tsx`

One badge component, three uses: report `ai_drafted`/`human_reviewed`, sensitivity
`IN USE`/`NOT IN USE`, adaptive-sampling `NO_FEEDBACK_YET`/`FEEDBACK_APPLIED`.

- Form + text, never colour alone. Filled vs outlined, plus the word.
- **No `variant="subtle"` and no way to hide it.** Take no `className` prop that could
  be used to shrink or mute it. The whole point is that it cannot be styled away.

### 2.3 `PlaceholderNote.tsx`

For any value the API flags as provisional. Takes the flag string and renders the
sentence that goes with it. Keep the mapping in one place so
`PLACEHOLDER_PENDING_MARINE_SCIENTIST` reads identically on `/reef-zones`,
`/reef-zones/:id` and `/limitations`.

### 2.4 `CaveatList.tsx`

Renders a `caveats[]` array. Every page you own receives caveats on the run **and** on
each result; both must surface. Group by severity, keep the API's wording verbatim.

> **i18n note for all four:** keys go in the `tools` namespace (yours), EN + AR, in the
> same commit. `tools.json` is currently 195 keys at exact parity — keep it that way.

---

## 3. WP1 — The scenario drawer actually calls the API

**Row:** `p4-07`, `p4-15` · **Status:** recorded FAIL · **Files:** `live.ts`,
`useLiveExposure.ts`, `ScenarioDrawer.tsx`

### 3.1 Widen `fetchExposure`

```ts
export interface ExposureParams {
  outletId?: string;
  horizonHours?: number;
  rainfallMultiplier?: number;        // 0.5 – 2.0
  transmissionLossOverride?: number;  // 0.20 – 0.85
  reefZoneIds?: string[];
}
export function fetchExposure(eventId: string, p: ExposureParams = {}) { … }
```

Omit `transmission_loss_override` from the body when undefined — do **not** send
`null` and do not send the default. The echo in `formula_terms.transmission_loss`
is how you prove the override took effect, and sending 0.525 explicitly makes
"unchanged" and "overridden to the default" indistinguishable.

### 3.2 Thread scenario through `useLiveExposure`

Add the scenario to the hook's inputs and its `useEffect` deps. Two things to get right:

- **Debounce ~400 ms.** A Radix slider fires on every pixel; an exposure calculation is
  not cheap and the plume behind it is cached per parameter set.
- **Guard against out-of-order responses.** The hook already has a `live` flag for
  unmount; add a request sequence number so a slow early response cannot overwrite a
  fast later one. Dragging a slider is exactly the interaction that produces this.

### 3.3 Map the UI scale to the API scale

The store keeps percentages; the API wants fractions and a multiplier.

| Control | Store | Sent as |
|---|---|---|
| `transmissionLoss` | 20–85 (%) | `transmission_loss_override` = `v / 100` → 0.20–0.85 |
| `rainfallScale` | 50–200 (%) | `rainfall_multiplier` = `v / 100` → 0.5–2.0 |

Clamp in the UI as well as trusting the server. A 422 from a slider is a bad demo.

The other four controls — `antecedentWetness`, `windDirection`, `windSpeed`,
`sedimentLoad` — **have no API parameter.** Do not invent one. Mark them as driving the
client-side stand-in index only, which is what `riskFromSeries` already does with
`scenario.transmissionLoss` (`risk.ts:148`). Two of the six controls are real; say
which.

### 3.4 Presets

| Preset | `rainfallScale` | `transmissionLoss` | Reads as |
|---|---|---|---|
| Dry season | 50 | 85 | Little rain, most of it lost in the bed |
| Heavy rain | 150 | 40 | Big storm, wet bed, more reaches the sea |
| Worst case | 200 | 20 | Maximum rain, minimum loss |

Each preset states its assumption in one line. A preset that just moves sliders is a
toy; a preset that says what it assumes is a scenario.

### 3.5 Acceptance

- [ ] Devtools shows a `POST /exposure/calculate` whose body carries both parameters
- [ ] `formula_terms.transmission_loss` echoes the slider; `rainfall_multiplier` echoes too
- [ ] `risk_score` on screen changes when the slider moves
- [ ] Dragging fast never leaves a stale number (sequence guard)
- [ ] The four non-API controls are visibly labelled as index-only
- [ ] Evidence: `evidence/p4-07/` — request body, response `formula_terms`, before/after screenshots

---

## 4. WP2 — `p4-12` Click-to-See-Why (the centrepiece)

**File:** `ReefZonePage.tsx` · **Depends on:** WP0.1, WP1

### 4.1 Interaction

Every `risk_score` anywhere on the zone page becomes a control that opens the
inspector. Not a hover — a click, keyboard-reachable, `aria-expanded`.

### 4.2 What the panel shows, in order

1. **The chain** — `<FormulaChain>` with the five factors, `raw_score`,
   `score_scale`, `risk_score`.
2. **Per factor, where it came from:**
   - `plume_probability` → `plume_source: REAL_PARTICLE_ENGINE`, plus the
     placeholder-forcing caveat (currents are a constant zero field)
   - `relative_sediment_intensity` → the full
     `relative_sediment_intensity_source` string, verbatim — it names the anchor
     event and the squashing function
   - `exposure_duration_weight` → `contour_times_hit` and `horizon_hours`
   - `habitat_sensitivity_weight` → `<PlaceholderNote>`; this is the unreviewed `1.0`
   - `confidence_adjustment` → `confidence_adjustment_reason` verbatim, plus
     `members_exceeding / members_total` against `threshold_value_mm`
3. **Geometry** — `zone_fraction_affected` **as a fraction of the named zone**
   ("all of Tourist Camp / north Marine Park boundary"), `n_overlay_rows`,
   `measure_crs: EPSG:32636`. 🔴 Never a bare km².
4. **Timing** — `arrival_window_hours` as a window, never a point estimate.
5. **Versions** — `model_versions` for the exposure engine and the runoff model.
6. **Caveats** — `<CaveatList>` for the result and the run.

### 4.3 The two placeholders that must surface

Both announce themselves in the payload; detect them, do not hardcode:

- `intensity = 0.5` when no catchment feature row exists
- `confidence_adjustment` whose reason string begins `PLACEHOLDER 0.6 --` when no
  GEFS row exists

In today's live response neither is active (`confidence_adjustment_reason` is a real
`0/30 GEFS members…` sentence). **Test the placeholder path deliberately** by calling
an outlet/event combination without a feature row — do not assume the branch renders
correctly because you never saw it.

### 4.4 Acceptance

- [ ] Five factors multiply to `raw_score` on screen, verifiable by hand
- [ ] Every factor names its source
- [ ] `zone_fraction_affected` reads as a fraction of the named zone
- [ ] Both placeholder branches rendered and screenshotted
- [ ] `hardening.spec.ts`'s false-precision regex still passes
- [ ] Evidence: `evidence/p4-12/`, EN + AR, light + dark

---

## 5. WP3 — `b8` + `b7` on `/reef-zones/:id` (highest consequence)

### 5.1 The safeguard, structurally

Two cards that **cannot** be read as one. Not two tones of the same card.

```
┌─ Live sensitivity weight ────────┐   ┌─ Proposed weight ────────────────┐
│  [IN USE]                        │   │  [NOT IN USE]                    │
│  1.00                            │   │  1.60                            │
│  Status: PLACEHOLDER_PENDING…    │   │  Status: PROPOSED_PENDING_REVIEW │
│  Every exposure score for this   │   │  From 3 contributed photos.      │
│  zone is multiplied by this.     │   │  Changes no score. Awaits        │
│                                  │   │  marine-scientist review.        │
└──────────────────────────────────┘   └──────────────────────────────────┘
```

- Separate `<Card>`s, separated by real space — never adjacent cells in one table.
- `<StatusBadge>` on both. The words `IN USE` / `NOT IN USE` do the work; colour assists.
- `proposed_value === null` → render **why** (`INSUFFICIENT_PHOTOS`, `n_photos` of 3),
  never an empty slot that reads as zero.
- Verify in **greyscale** before you call it done. Take the screenshot, desaturate it,
  and check a stranger still cannot confuse the two.

### 5.2 The classifier's honesty

On every result where `model_basis === 'heuristic_rule_v1'`, state:

> A colour and texture heuristic, not a trained model. Seven handcrafted features,
> confidence capped at 0.55. No labelled reef photos exist in this repository.

🔴 The words "CNN", "neural network", "deep learning" and "AI vision" must not appear
on this page. Grep for them before you commit.

### 5.3 Approval flow

`POST /reef-zones/{id}/sensitivity-weight/approve` needs `reviewer` + `reasoning` +
`approved_value` (422 without). There is **no authentication anywhere in this system** —
the reviewer name is a free-text string. Say so at the point of entry, not in a footer.

### 5.4 `b7` Adaptive sampling

`adjusted_priority` and `adjusted_priority_status` render next to `risk_score`, with
the rule stated: it can only **dampen**, bounded to `[0, risk_score]`.

🔴 The five feedback rows behind Phase 6's PASS were **synthetic**. Real deployment
history does not exist. The panel says "infrastructure, not a working feature today" —
Phase 5 marked this explicitly not demoable, and a polished panel here would be a
claim the project cannot support.

### 5.5 Acceptance

- [ ] Greyscale screenshot: live vs proposed still unmistakable
- [ ] No CNN/neural-network language anywhere (grep clean)
- [ ] `proposed_value: null` renders its reason
- [ ] Approve without `reasoning` → 422 surfaced as a real message, not a silent no-op
- [ ] `b7` panel carries its "not demoable" sentence
- [ ] Evidence: `evidence/b8/`, `evidence/b7/`

---

## 6. WP4 — `/reports`

- [ ] `<StatusBadge>` on every report, every list row, every detail header.
- [ ] **`GET /api/v1/reports` does not exist.** Session-generated reports live in
      component state, and the page **says** a persistent list is unavailable because
      the backend exposes no list endpoint. Do not fake a list; do not localStorage it
      into looking like one.
- [ ] Lookup by ID remains, since `GET /reports/{id}` works — that is the honest
      escape hatch and it should be visible, not hidden.
- [ ] Every claim renders its `source` pointer. A claim without one is a bug in the
      report, not a display choice — render it as visibly missing.
- [ ] `PATCH /reports/{id}/review` is the only path to `human_reviewed`; the reviewer
      name is unauthenticated and the UI says so.

---

## 7. WP5 — `/sites/score`

- [ ] `score: null` → **"insufficient data"**, never `0`, never `—`. The Mid-Atlantic
      control box returning nulls **is the feature working**; treat it as a first-class
      state and screenshot it as evidence.
- [ ] `C6` takes no data argument and is effectively constant — label it so it is not
      read as an independent measurement.
- [ ] The **"validated on exactly one site"** caveat renders next to every score, not
      once at the bottom of the page.
- [ ] Six criteria, each with its `evidence[]` citations.

---

## 8. WP6 — `/assistant` hardening (not a rebuild)

`AssistantPage.tsx:67` already calls the live `ask()`. What is left:

- [ ] **An answer with `citations.length === 0` must not render as an answer.** Assert
      this in code, not only in review — an early return with the no-sourced-answer
      state.
- [ ] Show `corpus_files_searched` in that state, so a refusal is informative.
- [ ] Pass the current UI language; verify an Arabic question returns and renders RTL.
- [ ] Nowhere on this page may the words "generative", "LLM" or "AI-written" appear.
      It is lexical retrieval plus extractive composition;
      `generate_with_llm()` permanently raises `NotImplementedError`.
- [ ] `docs/Ali/research/*` is deliberately outside the corpus. A question that lands
      there should say so rather than reaching for a loose match.
- [ ] Retire or repoint `panels/Assistant.tsx`, which still answers from the fixture
      corpus. **Two assistants that disagree is worse than one that refuses.**

---

## 9. WP7 — `/alerts` and the zone comparison

### 9.1 The `/alerts` recency problem — decide, then build

`/alerts` derives from the **single most recent** stored exposure run. Several pages
trigger runs on `AQ-O01`, which reaches no zone, so visiting them **empties the feed**.
Results are TTL-cached, so re-posting identical parameters returns the original
`run_id` and never becomes "latest" again.

| Option | Cost | Honesty |
|---|---|---|
| **(a)** Show `run_id` + `created_at` + outlet on the feed header | Frontend only | Good — explains itself |
| **(b)** Route `store.recent_runs()` (`exposure/store.py:191`, exists, unrouted) and list runs | Small backend change | Best |
| **(c)** Pin the feed to a chosen run | Frontend only | Good, more UI |

**(a) is the minimum and should ship regardless.** (b) is the right answer if you can
spare the endpoint. Write the decision down in `04-pulga.md` with the date.

### 9.2 `p4-I` Coastal Zone Risk Comparison

- [ ] Call **all five outlets** and assemble client-side. One call never returns more
      than one zone — `/alerts` alone cannot produce this table.
- [ ] Expected shape today: `AQ-O01` → none · `AQ-O02` → R-03 · `AQ-O03` → R-08 ·
      `AQ-O04` → none · `AQ-O05` → R-08.
- [ ] 🔴 `AQ-O01` carries **96% of discharge** and reaches **zero** zones at 24 h.
      Undiagnosed since Phase 4. Render it as a **named finding on the comparison**,
      not as an empty row a reader will assume is a loading bug.
- [ ] 🔴 `AQ-O04` discharges into an **enclosed harbour basin** (`p4-E`). Its critical
      caveat renders wherever that outlet appears. Do not demo it without.
- [ ] Five sequential calls are slow — fire them concurrently, render each as it lands,
      and show which are still outstanding.

---

## 10. Schedule — 9 to 13 Aug

| Day | Packages | Gate at end of day |
|---|---|---|
| **Sat 9** | WP0 primitives · WP1 scenario drawer | The recorded FAIL is closed; a slider changes a real score |
| **Sun 10** | WP2 formula inspector | The chain multiplies out on screen, both placeholder branches captured |
| **Mon 11** | WP3 `b8` + `b7` | Greyscale test passes; no CNN language; `b7` honesty copy in |
| **Tue 12** | WP4 reports · WP5 sites | Badges unmissable; nulls read "insufficient data" |
| **Wed 13** | WP6 assistant · WP7 alerts + comparison · evidence sweep | All rows Done or explicitly Absent; screenshots filed |

If the week compresses, **cut in this order**: WP7's option (b), then WP5's polish,
then WP2's second placeholder branch. **Never cut WP1 or WP3** — one is a recorded
failure and the other is the safeguard.

---

## 11. Tests to add as you go

| Test | Where | Asserts |
|---|---|---|
| Scenario round-trip | `tests/rebrand-smoke.spec.ts` | Moving the slider changes `risk_score` on screen |
| Formula identity | new vitest unit | Factors multiply to `raw_score` within `1e-9` |
| Badge presence | Playwright | Every report row has a visible status badge |
| Weight separation | Playwright | Live and proposed cards are separate elements with distinct badges |
| Uncited answer | Playwright | A no-citation response renders the refusal state, not an answer |
| Null score | Playwright | `score: null` renders "insufficient data" and never `0` |
| Language forbidden-words | grep in CI | No "CNN", "neural network", "generative", "LLM" on your pages |

Extend the untranslated-key walk in `rebrand-smoke.spec.ts` as you add pages — a
missing translation does not throw, i18next renders the key, and that spec is the only
thing that catches it.

---

## 12. Done means

- [ ] All 13 rows read **Done** in [`00-feature-surface-matrix.md`](00-feature-surface-matrix.md)
- [ ] `npm run qa` green · `npx playwright test` green except the documented
      environmental failures
- [ ] `python3 scripts/qa_frontend_tokens.py` exit 0 — no hex literal, no ad-hoc colour
- [ ] `tools` namespace still at exact EN/AR parity with matching interpolation vars
- [ ] axe clean across all four theme × language combinations
- [ ] Screenshots under `tasks/phase7/evidence/<row-id>/`, EN + AR, light + dark
- [ ] The `/alerts` recency decision is written down and dated
- [ ] Ali has reviewed and not returned any of your rows
