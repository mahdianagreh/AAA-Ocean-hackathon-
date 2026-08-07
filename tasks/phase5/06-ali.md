# Ali — Frontend, and the Dashboard Half of Every Phase 5 Feature

**Phase 5 · Workstream 6**
Read [`00-phase5-plan.md`](00-phase5-plan.md) first.

---

## Why this phase matters

You're on every row in this phase, same as every phase before it — not because you're
behind, but because nine new AI features all end in a screen and you're the only
frontend. Three real, specific gaps are yours to close from Phase 2 first; then this
file is organized as **the dashboard slice of B1–B9**, one section each, built against
the API contracts already committed in the repo.

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
      moves to a live call or whether the client-side fixture approach is deliberate
      for offline-mode reasons — right now it reads as an oversight, not a decision.
      Record whichever you pick in `docs/data_dictionary.md`.
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
      existed. **It now does**, live at `GET /api/v1/events/{event_id}/mooring`.
      Repoint the measured side at the live endpoint instead of the fixture, and
      start planning what populates the modelled column once a real simulation run
      exists to compare against — don't leave the panel silently still reading a
      fixture once a live source exists for part of it.

---

## B1 — Plume Segmentation, dashboard slice

- [ ] Confidence heatmap toggle directly on the plume layer.
- [ ] "Flag for human review" action on any auto-generated mask, feeding back into
      the training set.
- [ ] A running counter in the Provenance Panel: "X of Y plume masks now
      auto-segmented, Z still manual" — **this number must be real and visible, not
      smoothed over**; it's likely to be small this phase, and the UI must not imply
      otherwise.
- [ ] Upgrades Storm Replay Mode (feature 1) once wired — confirm it now shows a real
      plume shape for past events, not just the flagship demo.

## B2 — Learned Transmission-Loss, dashboard slice

- [ ] Transmission-loss slider's default position moves to the learned prediction
      instead of a blank midpoint.
- [ ] A tooltip showing the top features driving that catchment's prediction — same
      SHAP-style pattern `DriverBars.tsx` already renders for the runoff model.
- [ ] A comparison chart: this catchment's predicted loss vs. the old Negev proxy
      range.
- [ ] Read `transmission_loss_basis` (`"learned" | "negev_proxy"`) on every render
      and label the slider accordingly — never show a learned-looking default without
      saying which basis produced it.

## B3 — Cross-Site Transfer Learning, dashboard slice

- [ ] A "model maturity" badge per site — validated local events vs. Aqaba's
      baseline, shown honestly.
- [ ] Scaffolding for a future multi-site switcher — same dashboard, different
      coastline, with the maturity comparison built into the switch action itself,
      not a separate screen someone has to remember to check.

## B4 — Site-Scoring Agent, dashboard slice

- [ ] "Score a new coastline" input box — paste coordinates, get back a
      live-generated six-criterion score rendered exactly like the existing
      scorecard table (reuse that component, don't build a second one).
- [ ] A map layer showing auto-scored candidates color-coded by tier.
- [ ] Auto-populates a new row in the research-scan scorecard visualization.
- [ ] Render the "this rubric was validated on exactly one site" limitation next to
      every score — not buried in a tooltip nobody opens.

## B5 — Forensic Report Generator, dashboard slice

- [ ] "Generate Report" button on any completed event.
- [ ] A visible, **un-hideable** draft-status badge on every AI-generated report —
      `ai_drafted` vs. `human_reviewed` must be legible at a glance, not a status you
      have to click into to discover.
- [ ] Wire the report's citations through the same engine powering `/ask`, per
      whichever A6.1 decision you made above.

## B6 — Live Anomaly Detection, dashboard slice

- [ ] A distinct-colored "unusual pattern detected" banner, visually separate from
      the formal risk bands.
- [ ] A rolling sparkline of the live forecast stream with anomalous points marked.
- [ ] **The one design rule that's easy to get wrong here, stated plainly:**
      "early signal, formal threshold not yet crossed" is a different statement from
      "72% of ensemble members agree" — the Confidence Meter and this banner must
      never be visually or textually conflated into one signal.

## B7 — Adaptive Sampling Recommender, dashboard slice

- [ ] Upgrade the existing Named Reef Zone Priority List with "last sampled" and
      "prediction vs. outcome" history.
- [ ] An accuracy-over-time trend chart.
- [ ] **Keep the honesty note in the actual UI copy, not just internal docs:** this
      feature cannot be meaningfully demoed with zero deployment history. Frame it
      as infrastructure for a capability that activates after real-world use — never
      word the copy as if it's a working feature today.

## B8 — Coral Health Vision Model, dashboard slice

- [ ] Photo upload widget per named reef zone.
- [ ] Immediate classification result on upload, feeding a per-zone health trend
      line.
- [ ] A "photos contributed" counter.
- [ ] **A clearly separate, clearly labelled "proposed sensitivity weight update —
      pending scientist review" panel, visually distinct from the live, in-use
      `sensitivity_weight` value.** This is the UI half of this phase's single
      non-negotiable safeguard (Standing Law rule 13) — the panel must make it
      impossible to mistake a proposal for the live number.

## B9 — Culvert/Drainage-Conflict Detector, dashboard slice

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
4. Every B1–B9 dashboard slice above renders against its real backend contract, not
   against a placeholder that's quietly never swapped.
5. Every "keep the honesty note in the UI copy" instruction above (B1, B7, B8
   especially) is checked against the actual shipped copy, not just this checklist.
