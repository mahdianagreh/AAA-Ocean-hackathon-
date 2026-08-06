# Ali — Phase 4

> **Update, 6 Aug, from Karam — three things you need before building against them:**
> `/api/v1/events` now serves the real 675-event catalogue (was 5 events, no ranking
> columns, until today). **Use `rank`/`max_daily_mm` for "the" intensity ranking, not
> `max_anomaly_ratio`** — they rank storms differently. The Seasonal Risk Calendar is
> **rainfall intensity, not exposure** (exposure's anchored to one October event, would
> read flat elsewhere). Dive-site POIs in `places.geojson` now carry a real `osm_id` —
> full detail in `01-karam.md`'s update note. Also: the plume is not still a stub
> (Abd's file is stale on this) — `/plume/simulate` already returns real particle-engine
> output, confirmed live.
>
> **Update, 6 Aug, from Abd — this file's own "3D Journey (14)" row below, one thing
> changed under it.** On explicit request, outside this file's original ownership
> split, I built a first pass of the 3D Journey's plume-cloud portion — real terrain/
> bathymetry relief (`scripts/frontend_basemap.py`'s new `relief_bands()`), the real
> calibrated particle engine's contours extruded per real timestep
> (`scripts/frontend_journey.py`, `frontend/src/journey/`), reef zones coloured by
> real exposure. It is functional and honest, not a finished visual design — full
> writeup in `05-abd.md` §1a and `docs/HANDOFF_abd_2026-08-06.md` §5. Your terrain/
> bathymetry half below may now be partially redundant with what's in
> `frontend/src/journey/journeyStyle.ts` — worth checking before duplicating it,
> and the visual-design pass this still needs is yours if you want it.
>
> **Second update, same day.** The user asked for the full rainfall → flood →
> sediment → coastal-impact narrative on top of that first pass. Now built: real
> OSM buildings (`scripts/frontend_basemap.py`'s new `buildings()`, 617 real
> footprints), a real-rainfall-driven rain phase, real wadi runoff paths, and a
> six-phase Play/Pause/Reset timeline (`frontend/src/journey/usePhaseTimeline.ts`).
> Reef zones now stay neutral until the impact phase, then reveal their real
> exposure colour — worth knowing if you build a 2D equivalent of that reveal
> elsewhere, so the two don't quietly disagree on when "impact" is shown. Layer
> code is now one file per concern under `frontend/src/journey/layers/` rather
> than one growing file, if you're extending any single piece of it. Full detail
> in `05-abd.md` §1a's "Upgrade" note and `docs/HANDOFF_abd_2026-08-06.md` §5.

Read [`00-phase4-plan.md`](00-phase4-plan.md) first.

You're on almost every row in the plan's ownership table, and that's not a sign you're
behind — it's that nearly every feature on this list ends in a screen, and you're the
only frontend. What changed since Phase 3: the backend is in genuinely better shape than
last time. `npm run qa` (typecheck + lint + 14 vitest tests) was green when I ran it live
on 6 Aug, the map, time slider, risk cards, driver bars and scenario drawer all still
exist and work, and eight real endpoints answer 200 right now without fixtures. This
phase is mostly composition over data that's already real, plus a few items that
genuinely can't move until a teammate's file lands first.

I've grouped your rows by what's actually blocking them, not by the master list's order,
so you can tell at a glance what to start on today.

---

## Tier 1 — start today, nothing blocking

**8-Hour Countdown (3).** `arrival_window_hours` is real in every exposure response,
`/forecast/latest` gives real lead times to 48h. This is pure composition: `issued_at +
lead_hours` minus `arrival_window_hours[0]`, rendered as a countdown. No new backend
call needed.

**Rain Intensity Ranking (8).** Karam's confirming `/api/v1/events` returns the real
ranking columns (`max_daily_mm`, `mean_daily_mm`, `max_anomaly_ratio`) across all 675
storms and naming the canonical one. Once he does, this is a sort-and-list view — no new
data, just don't start until he's told you which column is "the" ranking; the columns
rank storms differently and picking the wrong one silently produces a defensible-looking
but wrong leaderboard.

**Simple Guess vs Smart Guess (11).** Live right now via `/api/v1/models`:
`baseline_mean_AP: 0.2004` vs `mean_AP: 0.7474`. Pull these two numbers straight into the
UI — nothing to build backend-side.

**Click-to-See-Why (12).** Every `/exposure/calculate` response already carries a full
`formula_terms` dict with real, non-zero values and a human-readable
`relative_sediment_intensity_source` string. If you don't already have an inspector view
that shows this on click, build it now — the data's been ready since the sediment anchor
landed.

**Rainfall Accumulation Chart (16).** `Hyetograph.tsx` likely already covers this — real
rolling 1/3/6/24h columns exist in `catchment_rainfall_daily.parquet`, served through the
existing rainfall endpoints. Confirm the component's already wired; if it's still on
fixture data, flip it.

**The Gap Chart (17), Toughest Coral Fact (18).** Static. No dependency on anyone.
Ship them.

**Named Reef Zone Priority List (A), Coastal Zone Risk Comparison (I).** Both are a sort
and a side-by-side view over the same live exposure data. Check with Pulga (his file,
item 4) whether `/alerts` already gives you what you need or whether you actually need a
dedicated summary endpoint — ask before building against the wrong shape.

**Historical Event Search (G).** 675 real events already live behind `/api/v1/events`.
Karam's confirming the response carries enough per-row detail for a search card without a
second call — once he does, this is a search UI over data that's already there.

---

## Tier 2 — verify, don't rebuild

These are marked done in the plan. Confirm they still work after this phase's backend
changes land; don't spend build time on them unless something's actually broken.

- **Bilingual Assistant (6).** Confirmed live during the audit: real citations, no LLM
  key, deterministic. If `Assistant.tsx` is fully wired already, this needs nothing.
- **Honest Limits Page (13).** `LimitationsPanel.tsx` + `fixtures/limitations.json` (9
  real entries) both confirmed real. Check the Arabic side has the same coverage as
  English — that's the one thing the audit didn't check.
- **One-Line Mission Statement (19).** Already shipped in `fixtures/limitations.json`'s
  `one_line` field. Done.
- **Enclosed Harbor Warning Flag (E).** Confirmed real and traveling through the API —
  `cav.harbour_outlet()` fires a critical caveat for AQ-O04 on every relevant response.
  Confirm `SideRail.tsx` (or wherever outlet caveats render) still surfaces it prominently
  after this phase's other UI changes.

---

## Tier 3 — blocked on a specific teammate, start the parts that aren't

**Storm Replay Mode (1).** Every input except the plume is real right now — rainfall,
runoff, the trained model, non-zero exposure. The plume itself is still Abd's synthetic
stub (`is_stub: true`, confirmed live on 6 Aug). Build the replay timeline and every panel
that isn't the plume shape now; the plume layer will self-upgrade the moment Abd's route
wiring lands, same as it did for the prediction-image endpoint in Phase 3.

**Live Forecast Mode (2).** Nizar's confirming the full cached-forecast → exposure chain
runs clean. Once he confirms, wire the live-mode toggle the same way you did in Phase 3 —
"latest cached run, issued `<time>`," never a network call on stage.

**3D Journey (14).** Terrain and bathymetry are real data right now (`catchments.gpkg`,
`depth_utm36n.tif`) — build that half today. **Do not build the plume-cloud portion until
Abd's route wiring lands** — a 3D-rendered synthetic buffer will look more convincing than
the 2D version currently does, which makes it a worse thing to demo by mistake, not a
better one.

**Superseded, 6 Aug — see the update note at the top of this file.** Abd's route
wiring landed, and a first pass of the plume-cloud portion got built along with it
(`frontend/src/journey/`, real terrain relief + real extruded plume + real reef
exposure). Functional, not a finished visual design — treat this row as "refine,"
not "build from zero."

**What-If Scenario Presets (7) / Judge-Controlled Slider (15).** `ScenarioDrawer.tsx`
exists but its own copy says "not a calibrated model" — accurate today, since it's not
wired to a real recompute. Pulga's adding a bounded rainfall-multiplier endpoint this
phase (his file, item 1). Once it's live, repoint the drawer at
`POST /api/v1/exposure/calculate` and **update the disclaimer copy to match** — don't
ship a real control still captioned as fake, and don't ship it silently as real without
checking the copy either way.

**Top Weather Drivers Explainer (4).** `DriverBars.tsx` already renders `shap_drivers`.
Mahdi's confirming real SHAP values are populated correctly; Pulga's wiring them into
`/explain`. Nothing for you to build once that lands — just confirm the component still
renders correctly with real (rather than hand-typed) driver magnitudes, which may be
larger or differently signed than what you tested against.

**Confidence Meter (5).** `ConfidenceMeter.tsx` exists. Karam and Nizar are fixing the
exceedance threshold this phase. Hold UI changes here until they confirm the number is
real — no point polishing a display for a value that might still be a placeholder.

**Real Sensor Proof Overlay (10).** Pulga's building the read-through endpoint; Abd's
confirming which fields matter (turbidity peak, salinity anomaly, elevated-duration
window). Once both land, build a model-vs-sensor comparison view — this is new UI, not
something existing components cover yet.

**Transmission Loss Reality Check (C).** Mahdi's documenting the valid range; Pulga's
exposing it as a bounded parameter. Once both land, add it as a seventh control (or fold
it into the existing drawer) — same "don't ship the slider before the backend supports
it" rule as item 7/15.

**Culvert & Drainage Correction Map (D).** The data's already exposed —
`culvert_verdict`, `nearest_culvert_m`, `unmodelled_coastal_culverts` are live on
`/api/v1/outlets` right now, including AQ-O02/AQ-O03's real "CANDIDATE CORRECTION"
flags. This needs a map layer, not a backend wait — you can start this one today,
following the pattern of the existing outlet/basemap layers in `style.ts`.

**Dive Site Safety Status (B).** Karam's confirming stable POI IDs in `places.geojson`;
Pulga's writing the nearest-reef-zone join. Once both land, render status badges on the
existing dive-site layer.

**Seasonal Risk Calendar (K).** Karam's writing the month-bucketing script and deciding
rainfall-vs-exposure framing (his file, item 3). Hold the calendar UI until he tells you
which one — building against the wrong definition means redoing the labels, legend and
color scale.

---

## One copy correction you own regardless of backend status

**Post-Storm Damage Estimate (J) is risky as worded, and that's a copy problem as much as
a backend one.** The sediment model is anchored to exactly one real point — 24,400 t,
one storm, one catchment. Mahdi's writing the honest-framing paragraph this phase. When
it arrives: the UI must show a **class** (Low/Medium/High/Extreme) for any event that
isn't the anchor, never a precise tonnage. If a mockup or a slide currently shows "~18,200
tonnes" for a hypothetical storm, that number is fiction dressed as a prediction — flag it
before it ships, not after a judge asks where it came from.

---

## Definition of done

1. Every Tier 1 item shipped — nothing there is waiting on anyone.
2. Every Tier 2 item re-confirmed live, Arabic coverage checked on Honest Limits.
3. Storm Replay and 3D Journey built up to the plume boundary, ready to receive Abd's
   real engine without further rework.
4. What-If / Judge Slider / Transmission Loss all either wired to real endpoints or
   explicitly left with accurate "not yet calibrated" copy — never wired-looking but fake.
5. Post-Storm Damage Estimate shows a class, never a tonnage, for any non-anchor event.
6. **Offline Emergency Mode (H).** `docker compose --profile frontend up`, wifi
   physically off, run at least once — same DoD item as Phase 3, still yours to close.
   Mahdi owns the Docker side of this (his file, item 6); your `wifi-off.offline.spec.ts`
   is the automated proxy, the physical run is the real gate for both of you.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Abd** | real plume in `/plume/simulate` | Landed — a first pass of the 3D cloud shipped with it too (see top-of-file update note); Storm Replay's remaining realism work is unblocked, not built |
| **Pulga** | multiplier endpoint, mooring endpoint, reef-zone summary shape | Partial — ask him which shape now, build UI after |
| **Mahdi** | SHAP confirmation, temporal-holdout number, transmission-loss range, damage-estimate copy | Partial — DriverBars already renders, just needs real data |
| **Nizar** | live-forecast chain confirmed clean, confidence-meter ensemble half | Yes for items 2 and 5's final polish |
| **Karam** | ranking column name, event-search shape, dive-site POI IDs, calendar framing | Yes for A/8, G, B, K specifically |
