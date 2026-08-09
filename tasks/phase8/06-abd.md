# Phase 8 — Abd

**Your pages this phase: 1 Storm Replay · 7 Validation.** Both render your work — the
particle engine and the mooring calibration — so both fail in the same way if the
numbers on screen drift from the numbers the engine and the mooring actually produced.

You own content accuracy on both. **Ali implements the UI** — you are not expected to
write frontend code.

**This is a design and clarity phase.** No new features, no new data, no new endpoints.
Anything else you notice goes in the final report as a suggestion — do not act on it
inside this phase.

---

## PAGE 1 — Storm Replay
`frontend/src/routes/ReplayPage.tsx`

### What Ali is building on this page

- [ ] **Style the plume-playback frame container**: card radius, shadow, proper
      padding, Montserrat headline for
      *"Predicted sediment plume · [event] · released at [outlet]"*.
- [ ] **Style the legend box** to match the card system — rounded corners, padding,
      **icon swatches instead of plain colour blocks**.
- [ ] **Button: frame-selector control** — currently the row of time-offset buttons at
      the bottom (`+3h`, `+6h`, `+12h` …). Rebuilt as an **equally-sized
      pill/segmented control with a clear Aqua-coloured active state**, fixing the
      current inconsistent sizing and cutoff.
- [ ] **Style the metadata bar** — *"Plume source: particle-engine · Frames: 6 ·
      Basemap: not baked…"* — as a **compact info row with a small icon per item**.
- [ ] **Do not attempt to generate the missing basemap.** It is flagged in the final
      report: `scripts/fetch_basemap_raster.py` must be run separately. **A data
      dependency, not a styling fix.**

### Your specific responsibility on this page

**Confirm the plume-frame metadata — source, frame count, release outlet, timestamp —
is accurate against the real particle engine output before Ali finalizes the redesigned
metadata bar.**

The metadata bar is the only place on this page that tells a viewer *what they are
actually looking at*. Once it is a tidy row of icons it will be read as settled fact.
Check each field against the engine, not against the current screen:

- [ ] **`plume_source`.** The API sends `'stub' | 'particle-engine'`
      ([`live.ts:60`](../../frontend/src/api/live.ts#L60)), and the interface's own
      comment is the standing instruction: *a stub labelled as a stub is honest; shown
      as a forecast, it is not.* Confirm which value the endpoint returns **today** for
      the demo event. If it still says `stub`, the redesigned bar must show `stub` —
      Ali renders what the API says and hard-codes nothing.
- [ ] **`frame_count` vs `frames.length`.** Confirm they agree. The metadata bar shows
      the count; the frame selector renders the array. If a frame fails to bake, those
      two diverge and the bar reports frames that the selector cannot reach.
- [ ] **`outlet_id` — the release outlet.** Confirm it is the outlet the engine actually
      released from, and that it is rendered with its ID intact (`AQ-O01`…`AQ-O05`) —
      these IDs are join keys and are never renamed.
      **If the page can be pointed at `AQ-O04`, it must say so.** `AQ-O04` discharges
      into an **enclosed harbour basin**; a plume released there settles in the basin,
      and it must not be demoed without that stated. Tell Ali whether that warning
      belongs on this page — if it does, it is a `CaveatCard`, not a footnote.
- [ ] **The timestamp / time offsets on the frame selector.** Confirm what `+3h`, `+6h`,
      `+12h` are offsets **from** — release time, event date, or first frame — and that
      the labels match the engine's actual frame cadence rather than an assumed
      three-hourly step. A segmented control with evenly-spaced pills implies evenly
      spaced frames; if the real cadence is uneven, say so before Ali makes them
      uniform.
- [ ] **The headline's `[event]`.** Confirm it renders the real event ID
      (`AQ-YYYY-MM-DD`). And confirm the demo event is described correctly wherever this
      page names it: `AQ-2016-10-28` is the **best-instrumented** documented flood,
      **not the biggest** — February 2006 recorded ~10 kg/m² seafloor deposition against
      Oct 2016's 6 kg/m². Nothing on this page may call it the largest.
- [ ] **`basemap_present`.** Confirm it is `false` today, and confirm the exact honest
      wording the bar should carry. The plume is drawn on **real satellite imagery,
      never generated** — see [`docs/plume_imagery_decision.md`](../../docs/plume_imagery_decision.md).
      With no baked basemap the frames sit on an empty ground, and the UI must say that
      plainly rather than let a styled card imply a map is underneath.
- [ ] **The legend's classes.** Ali is replacing plain colour blocks with icon swatches.
      Confirm what each band actually means in the engine's output — concentration,
      probability, or particle density — and that the legend labels say which. Confirm
      the ramp is the functional hazard ramp, not restyled to brand colours.

---

## PAGE 7 — Validation
`frontend/src/routes/ValidationPage.tsx`

### What Ali is building on this page

The structure here is already reasonable — this is a polish pass plus one real chart.

- [ ] **Apply full theme styling to the existing card layout.**
- [ ] **Style the "Measured quantities" table** matching **Page 2's table treatment**
      (Reef Zones index — Foam White header, clean row dividers, consistent cell
      padding).
- [ ] **Build a real line/area chart** (Marine Teal / Aqua palette) of the measured
      time-series markers — **salinity, turbidity** — against the modelled prediction.
- [ ] **Style "Timeline markers"** as a clean **horizontal/vertical timeline
      component** (icon + timestamp + label), not a plain list.
- [ ] **Style the event-selector dropdown** to match foundation input styling.

### Your specific responsibility on this page

**Confirm the chart's plotted values — salinity anomaly, turbidity peak, elevated
duration, sediment mass total — and their provenance labels (`reported` vs `converted`)
are visually distinguished correctly. This project's own discipline requires
source-vs-derived values never be presented as identical, and that must survive the
redesign.**

This is the page where the rule is easiest to break, because a chart's whole job is to
make different numbers look comparable. Specifically:

- [ ] **Classify every plotted value as `reported` or `converted`, one by one**, and
      hand Ali the list. The four named quantities, with the mooring's published
      figures for reference — Kalman et al. (2025), 250 m offshore the Kinnet Canal at
      13 m depth, sampling every 5 minutes:
      - **salinity anomaly** −1.75 ‰ (19σ)
      - **turbidity peak** 2.18 g/L
      - **elevated duration** ~31 h
      - **sediment mass total** ~24,400 t for `AQ-2016-10-28`
      For each: is that number as the paper reports it, or did we convert units, a
      timezone, or a datum to get it onto this chart? **A paper-reported number, a
      timezone-converted number and a computed number are three different things.**
- [ ] **Confirm the visual distinction is real and legible.** Reported and converted
      must not be the same mark in the same colour with the difference living only in a
      tooltip. Marker shape, line style or an explicit badge — pick with Ali, but the
      distinction has to be visible without interaction, and it has to survive
      greyscale printing and the dark theme.
- [ ] **The modelled series is a third category, not a second measured one.** Confirm
      the chart cannot be read as three measurements. The modelled prediction is our
      output being tested; the mooring is the test. If they are drawn alike, the page
      argues in a circle.
- [ ] **Confirm the timezone on every timestamp.** Local time is
      `ZoneInfo("Asia/Jerusalem")`, never a fixed offset — Oct 2016 falls inside **IDT
      (UTC+3), not IST**. An hour of drift on a 31-hour elevated window is a visible
      error on a chart with hour-resolution markers. Confirm the axis states which zone
      it is in.
- [ ] **Confirm what the timeline markers are** — arrival, peak, decay, and the passes.
      This is where the satellite result belongs and it must not soften: **satellite
      validation of the demo event is a measured NO-GO.** The plume dispersed ~31 h
      after arrival; the only usable passes are **+104 h and +128 h**. Two sensors, no
      plume. Confirm those two passes appear on the timeline as markers **outside** the
      elevated window — drawn correctly, the timeline *shows* why validation failed
      instead of asking the reader to take it on trust. That is the strongest thing on
      this page; make sure the redesign keeps it.
- [ ] **Confirm the event selector's list.** We hold **one** date of **thirteen
      sea-reaching floods since 1994** — the other twelve are in two paywalled papers.
      **February 2013 is not dead**: its mass is confirmed at **21,000 t**, 86 % of the
      demo event, so it is usable for **sediment-mass validation but not for imagery**
      (no exact day, and it predates usable Sentinel-2 and Landsat 8). Confirm which
      events the dropdown offers and that any harness behind it reports honestly against
      a **partial list** rather than scoring against n=1 and calling it validation.
      If the dropdown offers only one event, the page should say why.
- [ ] **Confirm nothing on this page claims exactness.** The Gulf is narrower than three
      cells of the best free ocean model. Output is probabilistic exposure with stated
      confidence, and a clean chart is a strong invitation to forget that.

---

## Your final report

- Page 1: the confirmed values for `plume_source`, `frame_count`, `outlet_id`,
  `basemap_present` and the frame cadence, plus the verdict on whether the `AQ-O04`
  harbour-basin warning belongs on this page.
- Page 7: the per-value `reported` / `converted` classification list handed to Ali, and
  confirmation that the +104 h / +128 h passes render outside the elevated window.
- Confirmation that `scripts/fetch_basemap_raster.py` is flagged as an outstanding data
  dependency, not styled around.
- A Suggestions section for anything you noticed and deliberately did not act on.
