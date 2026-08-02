# 01 · Design Language

**Status:** locked before code · **Owner:** Ali · **Phase:** 0

This document is the *why*. [`02-design-tokens.md`](02-design-tokens.md) is the *what* — the values you
actually type. If the two ever disagree, this one is wrong and should be corrected, because tokens are
validated by script and prose is not.

---

## 1 · The human, the task, the feeling

**Who.** A marine-park officer or an ADC operations lead in Aqaba, at a desk, on a normal day when
nothing is happening. Not a data scientist. They open this because a forecast flagged something, or
because a judge asked them to show it. They read Arabic and English, and they switch between them
without thinking about it.

**What they must accomplish.** Decide whether to act — send someone to sample water near a reef zone,
or advise a dive operator to hold off. That decision is the verb. Everything on screen either serves
it or gets out of the way.

**What it must feel like.** Like a **survey instrument**, not a product. Precise, quiet, and visibly
honest about what it does not know. The Gulf of Aqaba has been charted, sounded and measured for two
centuries; this interface belongs to that lineage, not to the SaaS dashboard lineage.

---

## 2 · The product's world

Explored before any visual thinking, per the routing skill's process.

**Domain.** A rift valley flooded by sea, 15–25 km wide and 1,800 m deep. Fringing coral metres from
the shoreline. Wadi Yutum: 4,453 km² of desert draining from 90 km inland, dry almost always and
catastrophic when it runs. A flood that moved 24,400 tonnes of sediment. A mooring 250 m offshore at
13 m depth, sampling every five minutes for 31 hours. Isobaths, soundings, CTD casts, time series.

**Colour world — what is actually there.** Deep Gulf water reads teal-navy, not "ocean blue," and
turquoise over the reef shelf. Aqaba's granite mountains are rose and ochre, not grey. Flood sediment
is ochre-brown — *the hazard is literally the colour of the hazard*. Salt flats and sand are pale warm
neutrals.

**Signature.** **Isobath hairlines are the structural system.** The same contour language draws panel
dividers, the loading state, the focus ring, and the plume's own density contours. Chrome and data
speak one visual language because on a hydrographic chart they always did. Nothing else in this
project's competitive set looks like a chart, and no other product could justify it.

**The honesty device.** The ~9 km ocean-model grid renders as an optional overlay. The coarseness the
project keeps apologising for in prose becomes something a judge can *see* — two to three cells span
the entire Gulf. Showing it is more convincing than stating it, and it converts our biggest weakness
into evidence of rigour.

---

## 3 · Defaults we are rejecting

Named so they can be caught in review. Any of these appearing is a bug.

| Rejected | Why |
|---|---|
| Navy dashboard + neon cyan + glassmorphic cards | The single most recognisable AI-generated dashboard look |
| Purple-to-blue gradient hero | Same |
| Inter (or Space Grotesk) as the safe choice | No Arabic companion, and it signals default-taking |
| Emoji as layer or section icons | Reads as unserious in a scientific product; breaks in RTL |
| `rounded-xl` cards floating on a gradient | Cards are not our container model — hairlines are |
| Green → yellow → red risk ramp | Fails deuteranopia, and green is wrong for a sediment hazard |
| Centred everything | This is a dense tool; it aligns to a grid, not to a centre line |
| A single confident plume trajectory line | Forbidden. See §6. |

---

## 4 · Colour

Full values and proofs in [`02-design-tokens.md`](02-design-tokens.md). The reasoning:

**Neutrals are biased to the Gulf, not to grey.** Every neutral carries a small chroma at hue 200–215.
A pure grey would read as unconsidered; a neutral that leans very slightly toward the water reads as
chosen, without anyone consciously noticing.

**One accent, and it is not a data colour.** A single teal drawn from shallow reef water, reserved for
interactive and selected states. It is measurably far from every hazard band (distance ≥ 0.78) so it
can never be misread as a risk level.

**The hazard ramp is separate from the accent** and follows concept §14.5's five bands. It runs pale →
sediment ochre → deep vermilion, because ochre is what a Wadi Yutum flood actually *is*. It is
monotonic in lightness, so it survives greyscale, a bad projector, and a photograph of the screen.

### The rule that matters most

> **Measured versus modelled is encoded in form, not hue.**
>
> - **Solid stroke** — measured. The mooring record. A reported number.
> - **Dashed stroke** — modelled. Anything our pipeline produced.
> - **Hatched fill** — an uncertainty envelope.

This falls directly out of carry-over rule 5 in [`00-phase2-plan.md`](../../../tasks/phase2/00-phase2-plan.md):
*a paper-reported number, a timezone-converted number and a number we computed are three different
things and are never presented as one.* Form survives colour-blindness, greyscale printing and
projector gamma. Hue does not. A judge photographing the screen still sees the distinction.

---

## 5 · Typography

**IBM Plex Sans Arabic · IBM Plex Sans · IBM Plex Mono.** One superfamily, self-hosted woff2.

Chosen because it has a **real Arabic companion drawn as part of the family**, so Arabic and English
share weight, rhythm and vertical proportion instead of being two typefaces bolted together. That is
the hard part of a bilingual interface, and most pairings fail it. OFL licensed, so self-hosting is
unambiguous — and self-hosting is mandatory anyway, because a font CDN violates the wifi-off
requirement.

**Mono is not decorative.** Every measurement, coordinate, timestamp and identifier (`AQ-C01`,
`34.97073`, `2.18 g/L`, `T+06:00`) sets in Plex Mono with `font-variant-numeric: tabular-nums`.
Numbers that will be compared must align, and the mono face is what makes a column of readings
scannable.

**Scale.** A minor third (1.2) — this is a dense instrument, not an editorial page, and a dramatic
scale would waste the vertical space the map needs. Weight carries hierarchy more than size does.

**Numerals: Western digits (0–9) in both languages.** Scientific and technical convention in Jordan,
and it keeps tabular figures aligned across a language switch. Units and coordinates are bidi-isolated
so RTL never reorders `2.18 g/L` into `g/L 2.18`. Full rules in
[`06-bilingual-rtl.md`](06-bilingual-rtl.md).

---

## 6 · Rules that are not style preferences

These come from the project's integrity rules and from physics. They are not open to visual
negotiation.

1. **The plume renders as a contoured field with its caveats stated. Never a single trajectory
   line.** The best free ocean model is ~9 km across a gulf 15–25 km wide, and our own release point
   sits on a cell the model masks as land. A confident line would be a claim the data cannot support.
   **And the contour levels are relative density, not calibrated probability** — the engine
   peak-normalises before contouring, so the UI must never label a band as a percentage chance of
   impact. See [`07-data-contracts.md`](07-data-contracts.md) §4.
2. **Uncertainty renders with the value, or the value does not render.** No bare numbers.
3. **An uncited assistant answer must not render as an answer.** Not a warning badge — a different
   state entirely. See [`09-accessibility-and-integrity.md`](09-accessibility-and-integrity.md).
4. **Missing is never zero.** A gap renders as a gap, visibly distinct from a measured zero.
5. **The map is never the only path to a fact.** Everything the map encodes is also reachable as text,
   for keyboard users, screen readers, and anyone looking at a projected screen from the back of a room.
6. **Provisional data is labelled in the UI**, not just in the repo. Reef `sensitivity_weight` is
   `1.0` everywhere, so exposure varies only through the hazard term — the legend must not imply
   zones differ in sensitivity.
7. **`AQ-O04` carries its caveat wherever it appears.** It discharges into an enclosed harbour basin;
   a particle simulation from that coordinate produces a confidently wrong plume.

---

## 7 · Motion

Three orchestrated moments. Everything else is ≤150 ms, opacity and transform only.

| Moment | What happens | Why it earns the budget |
|---|---|---|
| **Time-scrub choreography** | Every time-varying layer, the hyetograph cursor and the risk cards move as one under the slider. Interruptible, spring-settled. | This is the product. A judge dragging the slider and watching rainfall, runoff, plume and exposure move in lockstep understands the system in three seconds. |
| **Plume bloom** | Probability contours expanding T+3 → T+24. | Storyboard Scene 4. The one moment where the science becomes visible. |
| **Mode transition** | Historical → Forecast → Scenario re-lays out rather than cross-fading. | Makes the three modes feel like three views of one system, not three tabs. |

**Not doing:** ambient particles, scroll-jacking, decorative WebGL, animated page entrances, anything
that moves without being asked. Deck.gl earns its place or it does not ship — the task file says
"if it earns its place" and the default answer is no.

Every moment has a `prefers-reduced-motion` equivalent that still communicates the state change.
Details in [`05-motion-system.md`](05-motion-system.md).

---

## 8 · Icons

A custom domain set — catchment, outlet, reef zone, plume, mooring, culvert, dive site — drawn as line
glyphs on the same hairline grid as the isobaths. These concepts have no stock equivalents, and
reaching for a generic droplet or pin would undo the signature.

Lucide for generic UI affordances only (close, chevron, search). **No emoji, ever.**

**Cut line.** If Phase 0 runs long, ship three glyphs — catchment, outlet, reef zone — and finish the
rest as background work in Phase 2. Naming the cut in advance is what stops the icon set eating the
shell.

---

## 9 · How this gets reviewed

At the end of each phase, the test from the routing skill: **read a screenshot with the product name
removed. Could someone identify what it is for?** If the answer is "some kind of dashboard," the
direction has not landed and the phase is not done.

Second test, specific to this project: **could a judge tell, without reading a caption, which numbers
were measured and which were modelled?** If not, rule 5 has been broken somewhere.
