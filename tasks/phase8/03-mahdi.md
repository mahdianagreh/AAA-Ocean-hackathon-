# Phase 8 — Mahdi

**Your page this phase: Page 10 — Honest Limits.** One page, one job, and it is the one
where a design change can quietly change a meaning.

`frontend/src/routes/LimitationsPage.tsx` · route `/limitations`

You own content accuracy here. **Ali implements the UI** — you are not expected to
write frontend code. **Pulga** separately confirms the page still matches its source
documents, `docs/pitch_limitations.md` and `docs/forcing_limitations.md`.

**This is a design and clarity phase.** No new features, no new data, no new endpoints.
If you notice something else worth improving, put it in your final report as a
suggestion — do not act on it inside this phase.

---

## What Ali is building on this page

The full checklist, so you know exactly what is changing under your content:

- [ ] **Give "The one-line version" callout more visual weight** — larger text,
      distinct background tint, positioned as the page's lead statement.
- [ ] **Add a table of contents / jump-navigation** at the top linking to each major
      section.
- [ ] **Style "Ocean current resolution" as a highlighted spotlight card**, distinct
      from the numbered list.
- [ ] **Convert the numbered "things our data cannot tell you" list into an
      accordion.** Each item shows **only its number and bold headline by default**; a
      **Button: expand/collapse toggle** per item reveals the full explanation. **This
      is the single highest-impact change on this page.**
- [ ] **Style "Turn on the ocean-model grid layer to see this rather than read it"** as
      an actionable link/button where applicable.
- [ ] **Keep every word of the actual limitation content unchanged.**

---

## Your specific responsibility on this page

**Confirm the accordion's headlines accurately summarize each full limitation without
losing or distorting meaning — a bad headline here could make a real,
carefully-worded limitation sound like something different once collapsed.**

This is the whole of your assignment, and it is not a proofreading pass. Read it as a
risk: **by default, a visitor to this page will read only the headlines.** The body
text is now behind a click. Every headline therefore has to carry the limitation's
actual force on its own, unexpanded.

### The specific failure you are guarding against

A headline that is *technically true but reassuring* is worse than no headline. Three
concrete ways that happens here:

1. **A detection failure collapsed into a scaling failure.** The runoff label is blind
   where ERA5 is blind — October 2016 is among the misses. A headline reading
   *"Our runoff labels are approximate"* would be a lie of tone: no threshold tuning
   fixes a detection failure, and "approximate" implies it does.
2. **A hard NO-GO collapsed into a soft caveat.** Satellite validation of the demo
   event is a measured no-go — the plume dispersed ~31 h after arrival and the only
   usable passes are +104 h and +128 h. A headline like *"Satellite validation is
   limited"* reads as partial success. It was not partial. It failed, and we can say
   exactly why.
3. **An assumption collapsed into a measurement.** The reef sensitivity weights are
   assumptions pending a marine scientist, not data. A headline that says
   *"sensitivity weights carry uncertainty"* would upgrade an assumption to a measured
   value with error bars. Those are different claims.

### What to actually do

- [ ] **Settle the item count first, with Pulga, before Ali writes a line of the
      accordion.** The page is described as *"9 things our data cannot tell you."*
      [`docs/pitch_limitations.md`](../../docs/pitch_limitations.md) carries **twelve**
      numbered sections:

      | § | limitation |
      |---|---|
      | 1 | Our land cover is a single snapshot from 2021 |
      | 2 | Our soil data is a global model, not Aqaba's soil |
      | 3 | We could not obtain GEBCO, and we say so |
      | 4 | Our bathymetry cannot see the reef shelf |
      | 5 | Our reef sensitivity weights are assumptions, not data |
      | 6 | Allen Coral Atlas maps shallow reef only |
      | 7 | OpenStreetMap tells us what is mapped, not what exists |
      | 8 | What we would fix first, given another week |
      | 9 | Our satellite-based plume validation failed — and we can say exactly why |
      | 10 | Our site-scoring agent is validated on exactly one site |
      | 11 | Our adaptive sampling recommender cannot be demoed as a working feature yet |
      | 12 | Our coral health vision model is a heuristic today, not a trained model |

      Either the page renders a deliberate subset — say which, say why, and make the
      header honest — or the count has drifted and the accordion carries all twelve.
      **A 9-item accordion over a 12-item source silently drops three real
      limitations.** That is the exact failure this page exists to prevent. Note that
      §8 is not a limitation at all but a "what we'd fix next" section — decide
      explicitly whether it belongs inside the accordion or outside it.

- [ ] **Write or approve one headline per item**, and hold each to three tests:
      - **Does it survive alone?** Read it with the body collapsed. Does a reader who
        stops there come away with the *right* worry, at the *right* strength?
      - **Does it keep the hard word?** *Failed*, *assumption*, *cannot*, *not
        measured*, *heuristic*, *one site*, *snapshot*. If a hedge replaced a hard
        word, the headline is wrong.
      - **Does it name the thing, not the feeling?** *"Bathymetry cannot see the reef
        shelf"* beats *"Bathymetry has resolution limits."*

- [ ] **Check the two headlines that are hardest to compress**, specifically:
      - **§9, the satellite validation failure.** It has a sub-finding —
        *"The methodology finding — worth stating on its own"*. Confirm whether that
        sub-finding is strong enough to need its own accordion row rather than being
        buried inside §9's body, where a collapsed view hides it entirely.
      - **§4, the bathymetry limitation.** It is the same underlying fact as the
        per-zone depth caveats being grouped on Page 3. Confirm the two do not now
        state it at different strengths in two places in the product.

- [ ] **Confirm the "one-line version" still leads correctly** once it is enlarged into
      the page's lead statement. It is now the single most-read sentence on the page.
      If it under-states relative to the twelve items behind it, say so now.

- [ ] **Confirm the "Ocean current resolution" spotlight card** is the right item to
      promote out of the numbered list, and that promoting it does not renumber or
      orphan the others. This is your domain — the Gulf is narrower than three cells of
      the best free ocean model, and that fact is load-bearing for how the whole
      exposure output should be read.

- [ ] **Confirm the actionable link's promise.** Ali is turning *"Turn on the
      ocean-model grid layer to see this rather than read it"* into a button that
      navigates to the Dashboard with that layer on. Confirm that layer actually exists
      and actually shows the grid-resolution problem when enabled. A button that
      promises a demonstration and delivers a blank layer is a worse outcome than the
      sentence it replaced.

- [ ] **Confirm nothing is reworded.** The headlines are new UI text and need EN/AR key
      pairs. The bodies are the source documents rendered verbatim. If Ali's
      restructure requires editing a body sentence to fit, that is a stop — the layout
      changes, the content does not.

---

## Your final report

- The settled item count, and the reasoning behind it.
- The approved headline for every accordion item, with the source section it maps to.
- Any headline you rejected and why — that list is the evidence this check was real.
- Confirmation that §9's methodology sub-finding is handled correctly.
- Confirmation that the ocean-model grid layer actually demonstrates what the button
  promises.
- A Suggestions section for anything you noticed and deliberately did not act on.
