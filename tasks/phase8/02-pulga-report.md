# Phase 8 — Pulga's report (Pages 3, 4, 5, 6, 9, 10)

**Role:** backend, exposure engine and RAG. My job on this phase was to confirm that
what Ali styles matches what the API actually returns — before he styles it — and to
answer three decisions that blocked him.

**Method: measured, not read.** Every claim below was checked against a **running
API** (`uvicorn api.main:app --app-dir backend/src`, the container's own import path)
and a **running frontend**, not against source alone. Where a number is quoted, it was
returned by the live endpoint on 11 Aug 2026.

**Verdict: all six pages confirmed. Five real defects found and fixed.** Three of them
were caused by Track B auth landing without the rest of the system being brought with
it — including one that broke the primary action on Page 5 in the live product.

---

## The three blocking decisions, answered

| # | Question | Answer |
|---|---|---|
| **5(a)** | Client-side PDF, or a server-side endpoint? | **Client-side. No new endpoint.** `ReportOut` already carries the full rendered content (`sections[].claims[].text/.source`) plus `status`, `generated_at`, `reviewed_at`, `reviewed_by`. Nothing on the screen comes from any other source. `frontend/src/app/reportPdf.ts` is correct as built. |
| **9(b)** | Why can a site return "5 of 6 criteria scored"? | **It is C6, always, everywhere — including Aqaba.** Not an edge case: `score_c6_data_poor()` takes no spatial input and returns `insufficient_data` for every location by design. 5 of 6 is the permanent maximum, not a coverage failure. |
| **10** | Does the page match the source documents? | **Yes.** 12 limitations rendered against 13 numbered doc sections; the 13th (§8 "What we would fix first") is a roadmap, not a limitation, and is correctly routed to the fixture's separate `fix_next` key. Nothing dropped. |

---

## Defects found and fixed

### 1. Page 5 — the review button was dead in the live product ⚠ highest severity

**Track B protected `PATCH /reports/{id}/review` with `Depends(auth.get_current_user)`.
The frontend was never updated to send a token.**

`reviewReport()` sent `Content-Type` and nothing else → **401** → `tryJson` maps any
non-ok response to `null` → the page showed a generic "failed" notice. The single most
important action on the Reports page could not succeed at all, and the failure did not
say why.

Fixed in `frontend/src/api/live.ts`: an `authHeaders()` helper reads the access token
from the Supabase client **at call time** (not cached — the client refreshes on its own
schedule, and a cached copy starts 401-ing mid-session).

### 2. Page 5 — the reviewer field recorded a different name than it showed

The backend stopped trusting the body: `reviewer_identity = current_user.email or
current_user.sub`, and `req` is marked `noqa: ARG001 — kept for schema compatibility,
not trusted`. But the page still presented a free-text **"Reviewer name"** box.

So a user typed a colleague's name, the audit trail recorded a session email, and
nothing on screen said so. A field whose value is silently discarded is worse than no
field. Replaced with the signed-in identity — displayed because it *is* what gets
recorded — and reviewing is now gated on having a session rather than on a non-empty
string. `reviewReport(id)` no longer takes a reviewer argument at all: **a parameter
the backend ignores is a parameter that lies to its caller.**

### 3. Page 5 — two honest caveats had become false

`reports.reviewerHint` read *"There is no account system, so this name is not
authenticated."* That was true when written and is now the opposite of true. Same for
the `"Reviewer name"` label. Both rewritten, EN and AR. **A caveat that goes stale
becomes a lie in the one place the product cannot afford one.**

### 4. Page 9 — the insufficient-data explanation contradicted its own cited evidence

`sites.insufficientBody` read *"No score is given where the underlying data does not
cover **this area**."* For C6 — the only criterion that ever returns
`insufficient_data` — that is wrong. C6's own cited evidence, rendered directly beneath
it, says *"no automated evidence source exists for this criterion, **for any
location**."* The page asserted a coverage gap and then quoted evidence saying it was
not one.

Reworded to be true in both cases and to point at the citation:
> "No score is given where no evidence source can supply one — the specific reason is
> cited below. A missing score is left missing rather than guessed, and never counted
> as zero."

Also fixed `sites.constantNote`, which rendered as **"C6 · constant, no data
required"** — implying C6 has a fixed score when it has *none*. Now "same for every
site — no automated source exists."

### 5. Page 4 — `caveats` was missing from the shared `AlertRow` type

The live endpoint returns `caveats` on every row. `AlertRow` did not declare it, and
`AlertsPage` patched it back locally as `AlertRow & { caveats?: unknown[] }` with the
comment *"the shared type does not model yet"*. Caveats did render — but a field the
shared type does not admit is one refactor away from being dropped, and the standing
rule is that every caveat the API sends must reach the screen. Added to `AlertRow` as
required; local patch type removed. **The type immediately caught a specimen fixture
that had no `caveats` — which is the point of typing it.**

---

## Six failing backend tests, fixed

The suite was **6 red** on `main` before this work: Track B protected two routes and
left the tests asserting the old contract (`401` where they expected `200`/`404`/`422`).

Added a shared `authed_client` fixture in `tests/conftest.py` that overrides
`auth.get_current_user` and **always removes the override afterwards** — leaving it in
place would silently authenticate every later test and hide exactly the 401s these
routes exist to produce. Signature verification stays `auth.py`'s own concern;
verifying a real ES256 JWT here would mean shipping a signing key or making a network
call from a suite that must run offline.

Rewrote the six to the real contract, and **added two new tests that assert the
protection itself** — without them, every other test could pass against a route that
had quietly stopped requiring a session:

- `test_review_rejects_an_unauthenticated_caller` — 401, **and the report is untouched**
- `test_approve_rejects_an_unauthenticated_caller` — 401, **and the weight stays `PLACEHOLDER_PENDING_MARINE_SCIENTIST`**

Both authenticated tests now send a *deliberately different* name in the body and
assert it is **not** what gets recorded — proving the identity comes from the session.

**558 passed, 47 skipped, 1 xfailed. 0 failed.** (was 550 passed / 6 failed)

---

## PAGE 3 — Reef Zones, caveats section · CONFIRMED

The grouping is implemented on the **index** page, which is correct — that is where the
four near-identical caveats actually co-occur; a single zone's detail page can only
ever show its own.

**Verified against the live `GET /api/v1/reef-zones`:**

| zone | `depth_median_m` | caveat |
|---|---|---|
| R-02 | **`null`** | "no water cell in the 50 m bathymetry **at all** … Reported as null, never as 0" |
| R-06 | −6.37 | **52 %** of cells read as land |
| R-07 | −14.94 | **74 %** |
| R-08 | −13.93 | **51 %** |

**52 / 74 / 51 confirmed exactly as the task file stated**, and R-02 is confirmed to be
the *other* branch (`depth_median is None`), not a percentage. Exactly four zones carry
a depth caveat; R-01/R-03/R-04/R-05 carry none.

The implementation is right for the right reasons: the zone id comes from the **join**,
not parsed from the message text; each message renders **verbatim**; group membership
is derived at runtime from `field.includes('depth')`, so **no hard-coded four-zone
list** — if a fifth zone crosses the `land_pct >= 50` threshold it joins automatically.
Non-depth caveats are deduped by value, satisfying Global Rule 3.

> **One latent fragility, not a defect today.** The group card takes its `severity` and
> `source` from `depthCaveats[0]`. All four currently share `warning` /
> `docs/data_dictionary.md §4`, so it is correct — but it would silently misattribute
> if the branches ever diverge. Noted for whoever touches `depth_is_land_dominated`.

## PAGE 4 — Alerts · CONFIRMED (one fix, above)

`GET /api/v1/alerts` returns **4 live rows** today — the page is not exercising its
empty state in practice. All nine declared fields confirmed present and correctly
typed, plus the undeclared `caveats` (fixed). `arrival_window_hours` confirmed as a
real `[3.0, 24.0]` pair; `headline_ar` confirmed populated, not an empty string.

## PAGE 6 — Explain / Ask · CONFIRMED, no changes needed

- **Citation numbering** is the item's **position in `citations[]`** — the API sends no
  id — and `AssistantPage` says so in a comment at the render site. Correct.
- **Source tag** renders `source_file` + `§ section`. Correct.
- **`score` is nullable** and a null renders **no chip, never a `0`**. Verified in the
  code path.
- **`docs/ali` exclusion holds.** `GET /api/v1/ask/corpus` reports 13 files indexed,
  329 chunks, and **zero** from `docs/ali` — so no citation can ever tag one.

## PAGE 9 — Site Scoring · CONFIRMED (two fixes, above)

Live `POST /api/v1/sites/score` on an Aqaba box returns C1 = 2.0, C2 = 1.0, C3 = 1.0,
C4 = 0.0, C5 = 2.0, **C6 = `null` / `insufficient_data`**.

- `score` is `None`, **not `0.0`**, when absent — and the UI renders an explicit
  "Insufficient data" state, never a zero-filled bar. Confirmed.
- **C4 = 0.0 is a real score, not a gap** — the distinction the null/zero rule exists
  for, and the scorecard renders them differently. Confirmed.
- Evidence is **non-empty even when `insufficient_data`** — the absence itself is
  cited — and the page renders it. Confirmed.
- `maxPossible = scored.length * 2` — the donut is out of **10**, not 12, so the one
  uncomputable criterion does not silently drag the score down. Correct.
- The one-site caveat ships on every response and renders through the shared
  `CaveatCard`. Confirmed.

## PAGE 10 — Honest Limits · CONFIRMED, no changes needed

The 9-vs-12 drift I flagged when writing the plan is **resolved** (Mahdi, `506582d`).
Measured now: `docs/pitch_limitations.md` carries **13** numbered sections; the fixture
renders **12** as limitations and routes §8 to `fix_next`. Every doc section is
accounted for — nothing dropped, nothing invented. `qa_frontend_docs.py` green.

---

## Gates

```
pytest                     558 passed, 47 skipped, 1 xfailed, 0 failed
npm run qa                 typecheck + oxlint + stylelint + 14/14 vitest — green
qa_frontend_tokens.py      exit 0
qa_frontend_rtl.py         exit 0
qa_frontend_docs.py        exit 0
i18n parity                common 468 · nav 28 · pages 227 · tools 315 = 1038 keys, EN/AR exact
render check               6 pages × EN/AR — no [object Object], no untranslated key, no console error
```

Two gates were red before this work and are fixed here, both inherited rather than
mine:

- **`qa_frontend_tokens`** — six `#3fa7c9` hex literals in `Landing.tsx`. Replaced with
  the accent token / `var(--brand-aqua)`.
- **`qa_frontend_rtl`** — flagged `rounded-lg` twice. **The gate was wrong**, not the
  code: `rounded-[lr](?:-…)?` had no trailing boundary, so it matched the `l` of
  Tailwind's *large* radius. Fixed the regex in `scripts/qa_frontend_rtl.py` and
  verified every true positive still matches (`rounded-l`, `rounded-l-md`,
  `rounded-r-xl`). Latent since the gate was written; nothing in `src/` used
  `rounded-lg` until Phase 8.

---

## Suggestions — noticed, deliberately not acted on

1. **`GET /api/v1/reports` does not exist.** The Reports page keeps generated reports in
   session state only, so a refresh loses them and a review cannot be found again by
   anyone but the person who generated it. That is a real gap in an audit trail, but it
   is a new endpoint and this phase forbids one.
2. **`sites.unnamed`** still renders "Unnamed site" — honest there (the name is
   genuinely optional user input and `site_id` is shown beside it), unlike the
   catchment case, which was fixed separately.
3. **`reviewed_by` in `ReviewReportRequest` is now dead weight.** It is required by the
   schema (omitting it is a 422) and ignored by the handler, so the frontend sends a
   placeholder string to satisfy a validator. Worth deleting from the schema once
   nothing else posts it.
4. **`rounded-lg` is off the documented radius scale** (2/8/12/16/20 → `rounded-sm/md/
   card/…`). Left alone rather than silently restyling someone's design.
5. **PyJWT is in `requirements-api.txt` but not in older venvs** — a stale local
   environment fails at import with `ModuleNotFoundError: No module named 'jwt'`, which
   reads as a code bug rather than a missing `pip install`.
