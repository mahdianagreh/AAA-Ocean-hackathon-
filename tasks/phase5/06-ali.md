# Ali — Frontend, and the Dashboard Half of Every Phase 5 Feature

**Phase 5 · Workstream 6**
**Feeds:** everyone — the QA read on whether each backend contract actually renders
**Depends on:** Mahdi, Nizar, Pulga — every section below names exactly what and when
Read [`00-phase5-plan.md`](00-phase5-plan.md) first.

---

## Why this phase matters

You're on every row in this phase, same as every phase before it — not because you're
behind, but because nine new AI features all end in a screen and you're the only
frontend. Three real, specific gaps are yours to close from Phase 2 first; then this
file is organized as **the dashboard slice of B1–B9**, one section each, so you can
tell at a glance what you're building and which teammate's file has the backend
contract behind it.

---

## 0 · Close your Phase 2 items — Day 0/1

- [x] **A6.1 — live vs. stubbed endpoint map.** Confirmed and mapped: **live fetch**
      today — `/api/v1/exposure/calculate`, `/api/v1/plume/map/frames`,
      `/api/v1/alerts` (all in `frontend/src/api/live.ts`). **Static fixture**
      (default) — runoff predictions, catchments/outlets/reef-zones,
      event series/catalogue, provenance/limitations/validation/sources/corpus.
      **One real, specific gap found here:** `/ask` is answered entirely
      **client-side against the fixture `corpus.json`** — there is no live call to
      the backend's `/ask` route at all, even though it exists and is tested
      (`tests/test_ask_citations.py`). Decide explicitly this phase whether `/ask`
      moves to a live call (the backend already supports it) or whether the
      client-side fixture approach is deliberate for offline-mode reasons — right
      now it reads as an oversight, not a decision, and B5's forensic report
      generator (Pulga's file) explicitly wants to reuse the same citation engine
      `/ask` uses, so this decision has downstream consequences this phase, not just
      cosmetic ones.
- [ ] **A6.2 — wifi-off Playwright test executed.** `frontend/tests/wifi-off.offline.spec.ts`
      exists and is well-targeted (a real `chromium-offline` Playwright project with
      a DNS-blackhole launch flag) — but whether it has ever actually been run and
      passed is not something a file listing can confirm. Run it this phase, and
      separately do the manual physical check (`docker compose --profile frontend up`,
      wifi physically off) — the spec's own comment says the manual run is the real
      gate, the automated spec only catches regressions between now and freeze.
- [ ] **A6.3 — Validation Panel wired to mooring.** `ValidationPanel.tsx` already
      renders the measured side correctly from the mooring fixture, with the
      modelled column intentionally `null` and a `modelled_blocked_on` field naming
      what it's waiting on — this was the right call while no real mooring endpoint
      existed. **It now does** (Pulga's A3.3, live at
      `GET /api/v1/events/{event_id}/mooring`). Repoint the measured side at the
      live endpoint instead of the fixture, and start planning what populates the
      modelled column once a real simulation run exists to compare against — don't
      leave the panel silently still reading a fixture once a live source exists for
      part of it.

---

## B1 — Plume Segmentation, dashboard slice (backend: Mahdi, [`02-mahdi.md`](02-mahdi.md) §1)

- [ ] Confidence heatmap toggle directly on the plume layer.
- [ ] "Flag for human review" action on any auto-generated mask, feeding back into
      the training set.
- [ ] A running counter in the Provenance Panel: "X of Y plume masks now
      auto-segmented, Z still manual" — **this number must be real and visible, not
      smoothed over**; per Mahdi's own limitation note, it's likely to be small this
      phase, and the UI must not imply otherwise.
- [ ] Upgrades Storm Replay Mode (feature 1) once wired — confirm with whoever owns
      that view that it now shows a real plume shape for past events, not just the
      flagship demo.

## B2 — Learned Transmission-Loss, dashboard slice (backend: Mahdi, [`02-mahdi.md`](02-mahdi.md) §2)

- [ ] Transmission-loss slider's default position moves to the learned prediction
      instead of a blank midpoint.
- [ ] A tooltip showing the top features driving that catchment's prediction — same
      SHAP-style pattern `DriverBars.tsx` already renders for the runoff model.
- [ ] A comparison chart: this catchment's predicted loss vs. the old Negev proxy
      range.
- [ ] Read `transmission_loss_basis` (`"learned" | "negev_proxy"`) on every render
      and label the slider accordingly — never show a learned-looking default without
      saying which basis produced it.

## B3 — Cross-Site Transfer Learning, dashboard slice (backend: Mahdi, [`02-mahdi.md`](02-mahdi.md) §3)

- [ ] A "model maturity" badge per site — validated local events vs. Aqaba's
      baseline, shown honestly.
- [ ] Scaffolding for a future multi-site switcher — same dashboard, different
      coastline, with the maturity comparison built into the switch action itself,
      not a separate screen someone has to remember to check.

## B4 — Site-Scoring Agent, dashboard slice (backend: Pulga, [`04-pulga.md`](04-pulga.md) §1)

- [ ] "Score a new coastline" input box — paste coordinates, get back a
      live-generated six-criterion score rendered exactly like the existing
      scorecard table (reuse that component, don't build a second one).
- [ ] A map layer showing auto-scored candidates color-coded by tier.
- [ ] Auto-populates a new row in the research-scan scorecard visualization.
- [ ] Render the "this rubric was validated on exactly one site" limitation next to
      every score, per Pulga's spec — not buried in a tooltip nobody opens.

## B5 — Forensic Report Generator, dashboard slice (backend: Pulga, [`04-pulga.md`](04-pulga.md) §2)

- [ ] "Generate Report" button on any completed event.
- [ ] A visible, **un-hideable** draft-status badge on every AI-generated report —
      `ai_drafted` vs. `human_reviewed` must be legible at a glance, not a status you
      have to click into to discover.
- [ ] Wire the report's citations through the same engine powering `/ask` — depends
      on the A6.1 decision above about whether `/ask` goes live this phase.

## B6 — Live Anomaly Detection, dashboard slice (backend: Nizar, [`03-nizar.md`](03-nizar.md) §1)

- [ ] A distinct-colored "unusual pattern detected" banner, visually separate from
      the formal risk bands.
- [ ] A rolling sparkline of the live forecast stream with anomalous points marked.
- [ ] **The one design rule that's easy to get wrong here, stated plainly:**
      "early signal, formal threshold not yet crossed" is a different statement from
      "72% of ensemble members agree" — the Confidence Meter and this banner must
      never be visually or textually conflated into one signal.

## B7 — Adaptive Sampling Recommender, dashboard slice (backend: Pulga, [`04-pulga.md`](04-pulga.md) §3 — you're also named "with" on this one)

- [ ] Upgrade the existing Named Reef Zone Priority List with "last sampled" and
      "prediction vs. outcome" history.
- [ ] An accuracy-over-time trend chart.
- [ ] **Keep the honesty note in the actual UI copy, verbatim in spirit, not just in
      this file:** this feature cannot be meaningfully demoed with zero deployment
      history. Frame it as infrastructure for a capability that activates after
      real-world use — never word the copy as if it's a working feature today.

## B8 — Coral Health Vision Model, dashboard slice (backend: Pulga, CV: Mahdi, [`04-pulga.md`](04-pulga.md) §4)

- [ ] Photo upload widget per named reef zone.
- [ ] Immediate classification result on upload, feeding a per-zone health trend
      line.
- [ ] A "photos contributed" counter.
- [ ] **A clearly separate, clearly labelled "proposed sensitivity weight update —
      pending scientist review" panel, visually distinct from the live, in-use
      `sensitivity_weight` value.** This is the UI half of this phase's single
      non-negotiable safeguard (Standing Law rule 13) — the panel must make it
      impossible to mistake a proposal for the live number.

## B9 — Culvert/Drainage-Conflict Detector, dashboard slice (backend: Mahdi, [`02-mahdi.md`](02-mahdi.md) §4)

- [ ] A map layer showing detected conflicts as clickable pins.
- [ ] DEM-vs-OSM shown side by side on click.
- [ ] Render `position_confidence` updates with their evidence visibly attached —
      never show a `"low"` → `"high"` change without the click-through to why.

---

## Definition of done

1. A6.1 — the `/ask` live-vs-fixture decision is made explicitly and stated in
   `docs/data_dictionary.md` or an equivalent doc, not left ambiguous.
2. A6.2 — the wifi-off Playwright spec has been run and passed this phase, and the
   manual physical check has been done at least once.
3. A6.3 — `ValidationPanel`'s measured side reads from the live mooring endpoint.
4. Every B1–B9 dashboard slice above renders against its real backend contract once
   that teammate's Day 3–4 handoff lands — not against a placeholder that's quietly
   never swapped.
5. Every "keep the honesty note in the UI copy" instruction above (B1, B7, B8
   especially) is checked against the actual shipped copy, not just this checklist.

---

## Handoffs

| Teammate | What they get | When |
|---|---|---|
| **Pulga** | Confirmation of the A6.1 `/ask` live-vs-fixture decision, since it affects B5's citation wiring | Day 2 |
| **Everyone** | A running QA note on which B-feature dashboards are live vs. still waiting on a backend contract, so nobody discovers a gap at freeze | Ongoing, updated daily |

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Mahdi** | B1 confidence/review-flag API, B2 basis flag + SHAP-style feature endpoint, B3 maturity-badge data, B9 conflict-pin GeoJSON | Yes, partly — build each dashboard slice against a stub shape now, wire live when his Day 4 handoff lands |
| **Mahdi** | `terrain_merged_utm36n.tif` + baked Terrain-RGB tiles, before `JourneyScene.tsx`'s `raster-dem` source has anything real to load | Yes — the 3D Journey's terrain layer cannot start until his Day 2 handoff lands |
| **Nizar** | `forecast_anomalies` schema + the confidence-meter framing rule | Yes, partly — same stub-then-wire approach, his Day 3 handoff |
| **Pulga** | B4 score endpoint + citation shape, B5 report endpoint + draft-status contract, B7 feedback schema + honesty-copy requirement, B8 photo endpoint + the two-field safeguard contract | Yes, partly — same pattern, Day 3–4 |
