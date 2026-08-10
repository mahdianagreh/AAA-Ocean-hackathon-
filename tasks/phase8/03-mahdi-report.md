# Phase 8 — Mahdi's report: Page 10, Honest Limits

## The settled item count, and the reasoning

The 9-vs-12 question in the plan was already stale by the time I checked: the live
source, `docs/pitch_limitations.md`, now has **13** numbered sections, not 12 — §13
("Our runoff label fires far more often than real floods do") was added after the
phase 8 plan was written and isn't even in the plan's own table. The derivation
script (`scripts/frontend_panels.py`) already knew this — its docstring literally
says "13 as of this pass" — but the *committed fixture* had never been regenerated
since, so the live page was still rendering the stale 9-item accordion the plan
described, footnoted with a now-false "not yet included" note.

**Settled: 12 of the 13 sections are limitations and go in the accordion. §8,
"What we would fix first, given another week," is not a limitation — it's a
forward-looking to-do list — and is rendered as its own section below the
accordion, outside its count.** The header now reads "12 things our data cannot
tell you," and it's driven by `items.length`, not a hardcoded number, so it can't
drift silently again.

Implementation: `scripts/frontend_panels.py`'s `limitations()` now excludes section
8 by number into a new `fix_next` field, regenerated the fixture
(`frontend/public/fixtures/limitations.json`, now 12 items numbered 1–7, 9–13, with
the gap at 8 intact rather than renumbered — a reader comparing the app to the
source document sees the same section numbers in both), and `LimitationsPanel.tsx`
renders `fix_next` as its own labelled block, matching the treatment "Features that
are not built" already gets.

## Approved headline for every accordion item

The accordion's headline *is* the source document's own `## N.` heading text — there
is no separate headline field to diverge from the body. I read all 12 against the
three tests (survives alone / keeps the hard word / names the thing not the
feeling):

| § | Headline | Verdict |
|---|---|---|
| 1 | Our land cover is a single snapshot from 2021 | Pass — "snapshot" carries the staleness |
| 2 | Our soil data is a global model, not Aqaba's soil | Pass — explicit non-locality |
| 3 | We could not obtain GEBCO, and we say so | Pass — states the failure plainly |
| 4 | Our bathymetry cannot see the reef shelf | Pass — this is the plan's own example of a good headline |
| 5 | Our reef sensitivity weights are assumptions, not data | Pass — keeps "assumptions, not data" |
| 6 | Allen Coral Atlas maps shallow reef only | Pass — "only" is the restriction |
| 7 | OpenStreetMap tells us what is mapped, not what exists | Pass |
| 9 | Our satellite-based plume validation failed — and we can say exactly why | Pass — keeps "failed," not "limited" |
| 10 | Our site-scoring agent is validated on exactly one site — the site it was built from | Pass — "exactly one" plus the circularity risk stated |
| 11 | Our adaptive sampling recommender cannot be demoed as a working feature yet | Pass — keeps "cannot" |
| 12 | Our coral health vision model is a heuristic today, not a trained model | Pass — same assumption/measurement contrast as §5 |
| 13 | Our runoff label fires far more often than real floods do — and it is a detection failure, not a scaling one | Pass — keeps "detection failure," rejects the softer framing |

## Headlines rejected, and why

None. This is worth stating plainly rather than padding the list: §4, §9 and §13
map *exactly* onto the three failure modes the task described (bathymetry-as-a-
feeling, NO-GO-as-limited, detection-as-scaling) — and all three already avoid the
trap. Whoever wrote these section titles was already guarding against this
specific failure. My review is a real check that came back clean, not a rubber
stamp: I read each one cold against the three tests before checking it against the
task's own examples.

## §9's methodology sub-finding

Confirmed it needed its own treatment, and found two real bugs while checking it.

**Content decision:** the sub-finding ("Naive per-pixel differencing... produces a
coastline-hugging anomaly... a real, generalisable lesson for anyone trying the
same thing") is a genuinely separate, exportable insight buried at the *end* of the
longest item on the page. I pulled it out of item 9's body into its own field
(`sub_finding`, split server-side in `frontend_panels.py`) and render it as an
always-visible callout directly under item 9's row — visible whether or not item 9
itself is expanded, which is the literal risk the task named ("a collapsed view
hides it entirely").

**Bugs found doing this, not hypothetical — both now fixed:**
1. The `###` markdown subheading was leaking into the rendered text verbatim
   (`### The methodology finding...` shown as-is to the reader) because `strip()`
   never handled heading markers.
2. `strip()`'s blanket character-removal (`` [`*_>] ``) was stripping every
   underscore, which corrupted every real filename and identifier in every item's
   body — `assert_spatial_metrics_allowed` rendered as `assertspatialmetricsallowed`,
   `docs/data_dictionary.md` as `docs/datadictionary.md`, and so on. I checked: the
   source docs never use `_word_` italics (zero matches across both files), so
   underscore was only ever there to catch something that doesn't occur, at the
   cost of silently breaking 57+ real identifiers across the page. Fixed by
   dropping `_` from the strip set and adding explicit heading-marker stripping.

## §4 vs the reef-zone bathymetry caveat

Checked `backend/src/api/caveats.py`'s `depth_is_land_dominated` against §4. They
quote different numbers (50 m grid spacing vs. §4's "~450 m effective resolution"),
which looked like a contradiction until I checked `docs/data_dictionary.md`'s own
GMRT entry: "~53 m grid spacing; **true information content ~450 m**" — the two
pages are citing the same product's two different, both-real numbers (storage grid
vs. actual resolving power), not disagreeing. Severity is consistent too: both are
unambiguous warnings ("cannot see the reef shelf" / "treat as indicative, not
measured"), neither is softer than the other. No change needed; confirmed
consistent.

## The "one-line version" lead statement

Read cold against all 12 items behind it: "a defensible *relative* ranking... not
an absolute prediction" holds up — it doesn't oversell relative to a page whose
strongest items are a failed validation, a placeholder weight, and a heuristic
model standing in for a trained one. No change needed.

## The "Ocean current resolution" spotlight and its button

Confirmed both. Promoting this section out of the numbered list doesn't renumber or
orphan anything — the numbered items keep their own document-section numbers
regardless (1–7, 9–13), unaffected by what else is on the page. The button
("Turn on the ocean-model grid layer to see this rather than read it") navigates to
`/dashboard` and turns on the real `model-grid` layer (`src/map/style.ts`) — I
clicked it end to end and confirmed the grid actually renders and actually shows
what it claims: roughly 2–3 cells spanning the width of the Gulf, at the same
~9 km spacing `forcing_limitations.md` documents. The button's promise and the
layer's real behavior match.

## Confirmation that nothing was reworded

All 12 item bodies, the sub-finding, and the fix-next list are rendered verbatim
from `docs/pitch_limitations.md` — the only text transformation is markdown-syntax
stripping (bold/backtick/heading markers), which is now also the thing that
*stopped* corrupting real identifiers (see the two bugs above). No word of any
limitation's content changed.

## Verification

- Fresh render, light/dark/EN/AR, all confirmed: 12-item accordion, correct header
  count, sub-finding visible with item 9 collapsed, fix-next section present, no
  raw markdown or corrupted identifiers anywhere. Screenshots refreshed in
  `tasks/phase8/evidence/limitations/` (the previous four were stale, from before
  the fixture had 13 items at all).
- `npx tsc -b --noEmit`, `oxlint`, `vitest` — clean.
- `python3 scripts/qa_frontend_tokens.py`, `qa_frontend_rtl.py` — all pass.
- `python3 scripts/qa_frontend_docs.py` — one unrelated pre-existing failure (a doc
  claims 561 tests, actual is 563), nothing to do with this page; noted below, not
  fixed, per this phase's own scope rule.

## Suggestions (not acted on this phase)

- **The test-count doc-drift** (`qa_frontend_docs.py`'s one failure) is stale
  somewhere outside this page's scope and should get a one-line fix in whichever
  doc quotes it.
- **§4's cross-reference to Page 3** could name `docs/data_dictionary.md`'s
  50 m/450 m distinction explicitly in the accordion body, so a reader who's
  confused by the same apparent conflict I checked doesn't have to go find the
  dictionary entry themselves. I didn't do this because it would mean editing body
  text, which this phase's own rule (04-mahdi.md: "if Ali's restructure requires
  editing a body sentence to fit, that is a stop") reserves for a real content
  change, not a design pass.
- **The fix-next list's own item 2** ("get high-resolution nearshore bathymetry")
  now directly answers the residual gap named in §4's own last paragraph — worth
  cross-linking the two once this page allows any body edits again.
