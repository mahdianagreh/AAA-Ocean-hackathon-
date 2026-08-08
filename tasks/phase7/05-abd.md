# Phase 7 — Abd

**Owns:** the particle engine, the plume, the mooring, satellite, the 3D Journey.
**Pages:** `/dashboard/replay/:eventId` · `/dashboard/validation` · the plume layer on
`/dashboard` · the journey overlay.
**Rows:** `core-C`, `p4-01`, `p4-10`, `p4-14`.

Read [`00-phase7-plan.md`](00-phase7-plan.md) and
[`00-design-system.md`](00-design-system.md) first.

Four rows, and they are the four a judge will remember. They are also the four where
this system's honesty is most load-bearing: your engine is real, your forcing is not
complete, and the difference has to be visible without making the work look weak.

---

## The brand, in the two lines you will actually use

Never write a colour — `python3 scripts/qa_frontend_tokens.py` fails on a hex literal
in `frontend/src/`.

```
grounds   bg-canvas  bg-surface  bg-surface-2   borders  border-hairline
ink       text-ink   text-ink-2  text-ink-3     accent   text-accent
hazard    BAND_CLASS from src/api/types.ts
```

Deep Navy `#0A1F4D` · Ocean Blue `#0D3D7A` · Marine Teal `#007A99` · Aqua `#00B7C3`.
Montserrat; numbers through `<ValueWithUnit>`. Radii 8/12/16/20, but **map and chart
chrome keeps `--radius-hairline: 2px`** — an instrument is drawn with a pen.

**Your pattern:** yours are the only full-bleed, image-forward screens in the product.
Let the map and the imagery carry the page; keep chrome to a hairline. The gradient
appears **once** per screen at most. Plume density uses the documented relative-density
scale, never the hazard ramp — they are different quantities and must not look alike.

`frontend/src/journey/layers/*.ts` already carry `token-ok` exemptions for scene
lighting and for strokes read against satellite photography. That precedent covers
new layers of the same kind; it does not cover UI chrome.

---

## Your rows

### `core-C` — the plume, on `/dashboard`

The engine is **real**. `is_stub` is hardcoded `false`; the synthetic-circle stub is
gone. Three qualifications must reach the screen:

- [ ] 🔴 **Always the probability field, never a single trajectory line.** This is a
      documented project rule and `qa_frontend_docs.py` checks no doc endorses a
      trajectory line. The UI must not either.
- [ ] Ocean currents fall back to `ConstantCurrentField(0, 0)` on this checkout —
      `data/raw/currents/` does not exist — and the provenance string literally begins
      `"PLACEHOLDER: ConstantCurrentField(0, 0)"`. **Render that provenance.**
- [ ] **Wind is permanently zero.** `ConstantWindField(0,0)`, because no historical
      marine wind source exists for this basin: forecast products are forecast-only
      and the reanalysis is land-only. The winning `windage_fraction: 0.0` from the
      72-trial calibration is therefore a **tie-break artefact, not a calibrated
      value**. Say so where the parameter is shown.
- [ ] Consequence to state in one sentence: the cloud spreads by **diffusion**, it
      does not drift with a current. Timing and extent are meaningful; **a direction
      read off these frames is not.** You measured this — centroids across six
      timesteps showed ~100 m non-monotonic wobble, no coherent drift.
- [ ] Show `plume_source` verbatim from the API rather than hard-coding a label, so
      it flips by itself if the forcing is ever restored.

### `p4-01` Storm Replay — `/dashboard/replay/:eventId`

A page exists and steps frames. It is not a replay yet.

- [ ] The full sequence: **rainfall → runoff → sediment → plume → exposure**, in
      order, from real outputs. `/plume/map/frames` gives you `t_hours` + a URL per
      frame; `/exposure/calculate` closes the chain.
- [ ] Frames render server-side and take ~5 s. `PlumeMapPanel.tsx` already tracks
      requested-vs-shown step — reuse that pattern rather than blocking the UI.
- [ ] 🔴 **Only `AQ-2016-10-28` runs.** Every other `event_id` returns **HTTP 422**,
      by design: the engine needs a real `flood_arrival_utc` and only the anchor event
      has one resolved. The other candidate is still
      `TO_BE_RESOLVED_FROM_KATZ_2015`.
- [ ] Karam's `/events` links every one of 675 rows here. **Most will 422.** Agree the
      copy with him: the page must say *why* replay is anchor-only, not render an
      empty animation implying a plume shape that was never computed.
- [ ] `AQ-O01` — 96% of discharge — returns **zero** reef-zone intersections at 24 h.
      Undiagnosed since Phase 4. If you demo `AQ-O01`, that fact is on screen.

### `p4-10` Real Sensor Proof Overlay — `/dashboard/validation`

Phase 6 PASS on the backend. The measured side of the panel **still reads a fixture**
(`tasks/phase5/06-ali.md` A6.3, box unchecked) — repoint it.

- [ ] Live `GET /api/v1/events/{event_id}/mooring`. ⚠️ Note the path: it is **not**
      `/api/v1/mooring/{id}`, which several planning docs claim.
- [ ] Real Kalman et al. (2025) record: 250 m offshore the Kinnet Canal, 13 m depth,
      sampling every 5 minutes. Salinity −1.75 ‰ (19σ), turbidity peak 2.18 g/L,
      elevated ~31 h, sediment mass 24,400 t.
- [ ] State the measured numbers **as text as well as in any chart**. A judge should
      be able to read them without interpreting a plot.
- [ ] Every field carries a `provenance` tag — `measured` / `reported` / `converted`
      / `modelled` — and sometimes `uncertainty`. Render both. They are **not all the
      same kind of number** and the panel exists to show that.
- [ ] `series_available` is hardcoded `false`: the five-minute series is not served,
      only summary quantities. Say that rather than drawing a fake trace.
- [ ] Every non-anchor event **404s by design**. That is "no measured record for this
      event", not an error state.
- [ ] The modelled column stays honestly empty with `modelled_blocked_on` — the
      comparison depends on forcing that is placeholder today. Drawing it anyway would
      be measuring our placeholder, not our physics.

### The satellite null result — put it on `/dashboard/validation` as its own section

This is a **finding**, not a gap, and it is one of the strongest things in the project.

- [ ] Satellite validation of the demo event is a **NO-GO — measured, not assumed.**
- [ ] The plume dispersed ~31 h after arrival. The only usable overpasses are **+104 h**
      and **+128 h**. Two sensors, no plume.
- [ ] Frame it as: we checked, and the honest answer is that no image exists — which
      is exactly why the mooring is the validation target and a hand-drawn satellite
      mask is not.

### `p4-14` 3D Journey

Fully built: real Copernicus GLO-30 DEM + bathymetry merged into a Terrain-RGB
pyramid (350 tiles, z7–12, 20.6 MB), real Esri imagery drape, 617 real OSM buildings,
real rainfall-driven rain phase, 54 real wadi runoff LineStrings, six-phase timeline.

- [ ] ⚠️ **Three `journey3d` specs fail on this checkout** because `public/terrain/`
      and `public/basemap-raster/` are gitignored and absent. Regenerate with
      `scripts/tile_terrain_rgb.py` and `scripts/fetch_basemap_raster.py`, or state on
      the overlay that terrain is unavailable and degrade honestly.
- [ ] The 60 fps sample passes in isolation and fails under full-suite load — that is
      machine contention, not a regression. Do not weaken the test to make it green.
- [ ] Phase 4 recorded the journey work as **not pushed to `origin/main`**. Confirm it
      is on the shared branch before anyone plans a demo around it.
- [ ] Re-theme the overlay chrome to the new brand; leave the scene lighting alone.

---

## Done means

- [ ] The plume renders as a probability field with its placeholder-forcing provenance
      on screen
- [ ] Replay plays the full five-stage sequence for the anchor event and explains
      anchor-only clearly for every other event
- [ ] The validation panel reads the live mooring endpoint, with per-field provenance
      and uncertainty
- [ ] The satellite NO-GO has its own named section
- [ ] Terrain assets restored, or their absence stated on the overlay
- [ ] Screenshots under `tasks/phase7/evidence/replay/` and `.../validation/`,
      EN + AR, light + dark
- [ ] `npm run qa` green, `qa_frontend_tokens.py` exit 0
