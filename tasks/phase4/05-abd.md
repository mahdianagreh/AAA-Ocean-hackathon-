# Abd — Phase 4

> **All three items below closed 6 Aug 2026 — read this box before the audit that
> follows it, and before re-deriving anything as still open.** The `is_stub: true`
> finding right below was real for the branch it was checked against (`b987e9d`), but
> that branch and the commit that actually wires the real engine (`0de8c26`) were
> siblings on divergent branches at the time — they only merged afterward, into what
> is now `main` (`6de325c`). **Confirmed independently by two people, not just one:**
> Karam live-checked the running container first (`is_stub: false`,
> `model_version: custom_2d-calibrated-AQ-2016-10-28`, real HYCOM currents in
> provenance, differentiated non-zero exposure scores per outlet —
> `AQ-O02`/`AQ-O03`/`AQ-O05` reach a nearby reef zone at `minimal`, `AQ-O01` reaches
> none within 120h). Abd then re-verified the same and went one step further: the
> `AQ-O01` non-result and the flagship `AQ-O02` evidence outlet share the *same*
> cause — both release points sit on a current-grid cell masked as land — and
> `AQ-O02`'s *simulated output* is measurably diffusion-dominated, not visibly
> current-driven, a real and disclosed physics limitation, not a wiring gap (item 1's
> third checkbox has the measurement). Item 1's checklist below is obsolete; items 2
> and 3 are also closed — see their sections for what was actually done. **6 Aug,
> update:** the 3D Journey (feature 14) has now been built on top of this — see §1a
> below. Not this file's assigned scope (it's Ali's row), built on explicit request;
> flagged as such there so ownership stays traceable.

**This is a carry-over, and it's now blocking more than it was in Phase 3.** Read
[`00-phase4-plan.md`](00-phase4-plan.md) first.

I checked `POST /plume/simulate` against the live container on 6 Aug, after the sediment
anchor merged:

```json
{"is_stub": true, "provenance": [{"kind": "stub",
  "detail": "Synthetic sqrt(t) buffers in UTM 36N; not a transport simulation"}]}
```

Same finding as Phase 3, unchanged. `backend/src/models/particle_engine.py` still has
`simulate()`, `kernel_density_contours()` and `load_release_point()` — I ran its own test
suite live, 23/23 pass, and `kernel_density_contours()` returns real `Polygon` objects
when called directly. The API still isn't calling any of it. `main.py` still calls
`_synthetic_contours()`.

The reason this matters more now: sediment is anchored and every score I could produce
live is genuinely non-zero, but it's stuck in the "minimal" band (max 9.05/100) because
`plume_probability` — one of exposure's five multiplied terms — is still a synthetic
placeholder alongside it. Wiring this one route doesn't just fix the plume picture. It's
the thing standing between "minimal everywhere" and scores that can actually move.

---

## 1 · Replace `SYNTHETIC_STUB` with the real particle engine — ✅ closed 6 Aug, live-verified

**Status update, 6 Aug 2026, from Abd:** this audit's finding was stale, not wrong. The
finding ("`is_stub: true`, `main.py still calls _synthetic_contours()`") was accurate for
the branch the audit ran against, but that branch (`b987e9d`) and the commit that actually
does this wiring (`0de8c26`, "replace SYNTHETIC_STUB with the real particle engine") were
siblings on divergent branches at audit time — they only joined in the merge that landed
on `main` afterward (`6de325c`). Re-checked live against current `main`, container-style
(`uvicorn api.main:app --app-dir backend/src`), same method the audit used:

```
POST /api/v1/plume/simulate {"event_id":"AQ-2016-10-28","outlet_id":"AQ-O02"}
→ is_stub: false
→ model_version: custom_2d-calibrated-AQ-2016-10-28
→ provenance: "custom_2d particle engine, 1000 particles, 1 day, 0:00:00,
   currents: HYCOM GLBu0.08/expt_91.2 historical archive, cached
   data/raw/currents/hycom_aoi_AQ-2016-10-28.nc"
→ 24 real contour polygons

POST /api/v1/exposure/calculate {"event_id":"AQ-2016-10-28","outlet_id":"AQ-O02","horizon_hours":24}
→ formula_terms.plume_source: "REAL_PARTICLE_ENGINE"
→ formula_terms.model_versions.particle_engine: "custom_2d-calibrated-AQ-2016-10-28"
```

`tests/test_particle_engine.py`, `tests/test_api_contracts.py`, `tests/test_plume_map_render.py`,
`tests/test_spatial_contract.py`, `tests/test_run_id_contract.py` all green (71 passed, 2
skipped) against this same `main`.

- [x] Wire `/plume/simulate` to the real engine. Done in `0de8c26`; confirmed live above.
- [x] `plume_source` and `model_versions.particle_engine` both read real values. Confirmed
      live above — neither reads `SYNTHETIC_STUB`/`stub-0.1` anymore.
- [x] Advect with real currents — `AQ-2016-10-28` consults the cached HYCOM historical
      archive (see provenance string above), not a synthetic stand-in. Nuance worth
      recording rather than silently generalizing, in two directions:
      - **Across events**: this is real for the one demo event because its archive is
        cached ahead of time (`scripts/28_calibrate_plume_engine.py` bakes it as a
        calibration side effect). Any *other* `event_id` with no cached archive still
        falls back to `ConstantCurrentField(0, 0)` with an explicit "no cached
        historical current archive" caveat in the response
        (`backend/src/api/main.py` `_current_fn_for_event`) — an honest gap, not a
        silent one.
      - **Within this event, at the outlets tested**: "consults a real archive" is not
        the same claim as "visibly advects on it," and I initially conflated the two.
        Checked live for all five outlets — `AQ-O01`, `AQ-O02`, `AQ-O03` and `AQ-O05`
        (`AQ-O04` is the harbour-basin special case) all carry the identical
        `masks as land` caveat, **including `AQ-O02`, the exact outlet quoted as this
        item's evidence above.** I went further than reading the caveat text: I tracked
        that `AQ-O02` run's contour centroids across all six reported timesteps and
        found no coherent directional drift — displacement from the release point
        wobbles non-monotonically within roughly 100 m at every density level, which is
        the signature of diffusion, not advection. So the flagship evidence run in this
        item is genuinely real (`is_stub: false`, real code path, real archive
        consulted, tests green — none of that is false), but its *simulated output* is
        empirically diffusion/settling-dominated, not visibly current-driven, because
        the ~9 km HYCOM cell under the release point is masked. This is a real, honestly
        surfaced physics limitation (the response's own `contours` caveat says so), not
        a wiring defect — but "advects on the real cached HYCOM archive" overclaimed
        what this specific case demonstrates, and I should have checked the caveats
        array before writing that line, not just the headline fields.

**What this closes:** the plume-stub ceiling is gone. Every exposure score for
`AQ-2016-10-28` now multiplies a real `plume_probability` term, and the engine is
genuinely running real physics with real forcing consulted — not a re-skinned stub.
Scores still land in "minimal" band (e.g. `risk_score: 3.30` for R-03) — that is no
longer this item's doing: `relative_sediment_intensity` (0.084, Mahdi's term) and
`habitat_sensitivity_weight` (still `PLACEHOLDER_PENDING_MARINE_SCIENTIST`) are the
remaining multipliers holding the score down. Say this explicitly so nobody re-blames
the plume engine for that part.

Two findings worth flagging to Pulga/Mahdi, outside this item's scope:

1. `AQ-O01` (96% of discharge, the primary demo outlet) returns **zero** reef-zone
   intersections from `/exposure/calculate` at 24h — the same current-grid-masking
   described above (transport is diffusion/settling only there, not current-driven) may
   be why the plume never reaches a zone in the horizon. Worth checking before the
   demo; not diagnosed further here since it's not a plume-engine defect.
2. More generally: at this event's ~9 km current-grid resolution, near-shore release
   points routinely land on a masked cell, so "the plume advects on real currents" is
   not a safe claim for any of this project's five outlets at a 24h horizon without
   checking the specific run's `caveats` array first. Worth deciding, before the demo,
   whether to pick a release point known to sit on a resolved cell for the visually
   current-driven story, or to narrate this limitation openly instead.

**What this one item unblocks, named explicitly so nobody re-derives it:**

- **Storm Replay Mode (feature 1)** goes from muted to fully real the moment this lands —
  every other input for AQ-2016-10-28 is already real.
- **The 3D Journey's plume-cloud portion (feature 14)** should not be built before this —
  Ali's terrain/bathymetry rendering can proceed now, but the cloud itself needs real
  shape, not a synthetic buffer rendered in 3D.
- **Live Forecast Mode (2) and the driver/confidence features (4, 5)** all inherit this
  same ceiling — they'll look muted for a reason that has nothing to do with Nizar's or
  Karam's or Mahdi's work on them.

---

## 1a · The 3D Journey (feature 14) — ✅ built, 6 Aug, on top of item 1

**Not this file's assigned scope** (feature 14 is Ali's row in `00-phase4-plan.md`,
with Abd's slice explicitly marked deferred) **— built anyway, on request.** Recorded
here so ownership stays traceable and Ali's file isn't contradicted by a silent
change elsewhere.

A real, data-driven 3D scene, reachable from the masthead (`journey` overlay),
covering the concept doc's own chain — wadi, outlet, plume, reef — in one flown-through
view:

- **Terrain/bathymetry**: `scripts/frontend_basemap.py`'s new `relief_bands()` vectorizes
  `depth_utm36n.tif` — the same raster `isobaths` already contours — into 11 real,
  fill-extrudable elevation/depth bands (`frontend/public/basemap/relief_bands.geojson`),
  covering both the coastal mountains (up to ~1,800 m) and the seafloor down to -800 m.
  No separate terrain source, no DEM tile pipeline, no invented relief.
- **The plume**: `scripts/frontend_journey.py` derives `frontend/public/fixtures/journey3d.json`
  from a live run of the real particle engine (`POST /plume/simulate` +
  `/exposure/calculate` for `AQ-2016-10-28`/`AQ-O02`, all 6 real timesteps) — the exact
  same calibrated engine item 1 wires in, not a second implementation.
- **Reef zones**: real Allen Coral Atlas geometry, coloured by the real exposure result
  for this run (`R-03`, `minimal`) — zones the plume never reached carry no colour, not
  a fabricated zero-risk tint.
- **Honesty carried through, not left behind**: the scene surfaces the *same*
  current-grid-masking caveat verbatim (§ above) rather than rendering a more dramatic,
  current-driven plume than the real run shows. The on-screen caption states the
  vertical exaggeration (6×) and that sea depth is drawn as upward relief, not sunk
  below a surface plane — so nothing here implies more precision or more drama than
  the underlying data supports.

Verified: `tsc -b --noEmit` clean, `oxlint`/`stylelint` clean, `vitest run` 14/14,
full Playwright suite 25/25 including the axe accessibility pass (one real
contrast regression this work introduced — `text-ink-3` on `bg-surface-2` in the new
calibration-fit caveats — found by that same suite and fixed to `text-ink-2`,
matching the pattern already used elsewhere in the same panel) and the two-language
`scene-walk` walkthrough. Screenshotted directly, not just asserted green.

Not perfected — a first real pass, not a final visual design: extrusion heights
needed two rounds of tuning to keep reef/plume layers from being visually swallowed
inside taller relief blocks at the same footprint, and the result is functional and
honest rather than polished. Whoever picks up feature 14's remaining visual-design
work (Ali's row) inherits real geometry and a real fixture to refine, not a
placeholder.

---

## 2 · Real Sensor Proof Overlay (feature 10) — ✅ closed 6 Aug — fields confirmed, fit quality now on screen

**Status update, 6 Aug 2026, from Abd:**

- [x] **Fields confirmed.** `data/processed/marine/mooring_target_AQ-2016-10-28.json` carries
      five measured fields, not three — the headline three (turbidity peak `2.18 g/L`,
      salinity anomaly `-1.75‰`/`19σ`, elevated duration `31.42h`) plus `salinity_minimum_psu`
      (`38.75`) and `sediment_mass_total_t` (`24,400`, the anchor mass). All five are already
      live in `frontend/src/panels/ValidationPanel.tsx`'s comparison table — nothing missing
      there. **Recommended fourth field for Pulga's route, not yet exposed anywhere:**
      `transport_regime` — the mooring file's own `calibration_use` block says outright "the
      calibration winner's regime should be stated as a verdict," and the calibration now has
      one (`hypopycnal`, see below). Worth a field on his endpoint.
- [x] **Fit quality reported honestly, on screen, not just in a file.** The transport-parameter
      fit (Phase 3 item 2) is done — `scripts/28_calibrate_plume_engine.py`, 72 trials, real
      grid search over diffusion × windage × settling × regime, logged in
      `data/models/plume_calibration.json`. It was sitting unread in that file (grepped the
      whole API/frontend tree — zero references before today). Wired it into
      `scripts/frontend_panels.py`'s `validation()` and added a new "Transport-timing fit
      (calibration)" section to `ValidationPanel.tsx` (both `en`/`ar`, e2e-tested), reporting
      **honestly, including where it doesn't match**:
      - `arrival_time_error_hours: -6.83` (simulated plume arrives ~6.8h early)
      - `duration_error_hours: +4.25` (simulated elevated window runs ~4.25h long)
      - `peak_timing_error_hours: -22.54` (large — but caveated in place: measured against
        the mooring's onset/clear **midpoint**, a documented placeholder, not a digitized
        true peak; not a claim the model is 22.5h wrong against a real observation)
      - Selected regime: `hypopycnal` (diffusion 5.0 m²/s, settling 0.1 mm/s)
      - **Windage caveat surfaced verbatim**: wind forcing is `ConstantWindField(0,0)` (no
        historical wind source in this repo yet — ERA5-Land u10/v10 for this window is the
        designated fix), so the winning `windage_fraction: 0.0` is a tie-break artifact, not
        a calibrated value. The panel does not imply otherwise.
      - This is a **timing-only** comparison and says so on screen — the particle engine
        does not model sediment concentration (g/L) or salinity (PSU), so the five magnitude
        rows above correctly stay "No data" rather than being force-filled with a fabricated
        match.

Note for whoever picks up Pulga's `GET /api/v1/events/{event_id}/mooring` (item 2 of
[`04-pulga.md`](04-pulga.md)): this closes the *static* validation panel, which reads from a
build-time fixture (`scripts/frontend_panels.py` → `frontend/public/fixtures/validation.json`),
not a live route. His endpoint is still open and separate — reuse the same field list and the
same honest caveats from `data/models/plume_calibration.json` rather than re-deriving them.

---

## 3 · Swap #4 — ✅ closed, confirmed in writing 6 Aug

**It closed on 2 Aug (`739195f`) and just hadn't been marked.** Confirming per this item's
own instruction, so it drops off future lists: `tasks/00-contracts.md` §5 row 4 updated to
☑, with the full finding written there rather than a bare checkmark — because this is a
**negative result**, not an ordinary provisional→real swap, and a checkbox alone would
misrepresent that. Summary: the real Sentinel-2/Landsat 8 extraction ran, and the final
verdict is **NO-GO** — no plume visible in either independent satellite pass, a physical
null (turbidity had already returned to background 2.5–3.5 days before either pass), not a
data-quality problem. Full methodology in `docs/event_audit.md` §3 ("Go / no-go — FINAL,
pixel-level QC complete").

The UI already labels this correctly — checked `frontend/src/panels/ValidationPanel.tsx`
live (screenshot, both `en`/`ar`, both e2e scene-walk tests green): it shows a `NO-GO` badge
and states the physical-null finding on screen, and does not claim a revealed satellite
plume (the e2e test `scene-walk.spec.ts` explicitly asserts that claim's absence). Nothing
further needed here. The old `observed_plume_PROVISIONAL.gpkg` is left on disk for the
audit trail; confirmed nothing in `backend/src/` or `frontend/src/` reads it anymore
(only `scripts/generate_provisional_seeds.py`, its original generator).

---

## Definition of done — all four closed, 6 Aug 2026

1. ✅ `/plume/simulate` runs the real particle engine — confirmed live against `main`
   (`6de325c`), container-style (`uvicorn --app-dir backend/src`): `is_stub: false`,
   real HYCOM-forced contours, 71 passed/2 skipped across the plume/particle/contract
   test files. The prior "not running live" finding was accurate for the branch it
   checked; that branch has since merged.
2. ✅ `plume_source` and `model_versions.particle_engine` both read real values
   (`REAL_PARTICLE_ENGINE` / `custom_2d-calibrated-AQ-2016-10-28`) in a live
   `/exposure/calculate` response — confirmed above, not assumed.
3. ✅ Mooring overlay fields confirmed (5 fields live, a 6th recommended for Pulga's
   route); fit quality stated honestly on screen in `ValidationPanel.tsx` — including
   the large, caveated peak-timing error and the windage tie-break artifact, not just
   the numbers that flatter the model.
4. ✅ Swap #4's status stated explicitly: closed, NO-GO, written into
   `tasks/00-contracts.md` §5 and confirmed against the live UI.

## What you depend on

| From | What | Status |
|---|---|---|
| **Nizar** | real current fields for advection | ✅ Resolved for the one demo event — `AQ-2016-10-28` advects on the real cached HYCOM archive, confirmed in the live response's provenance string. Any other `event_id` still degrades honestly to `ConstantCurrentField(0,0)` with an explicit caveat, pending Nizar's broader current-field work. |
| **Pulga** | the mooring endpoint itself | Open, not blocking — his live `GET /api/v1/events/{event_id}/mooring` (04-pulga.md item 2) is separate from the static `ValidationPanel` this file closes. Field scope and fit-quality caveats above are ready for him to reuse. |

## Outside this file's scope, flagged for whoever owns it

`AQ-O01` (96% of discharge, the primary demo outlet) returns **zero** reef-zone
intersections from `/exposure/calculate` at a 24h horizon — live-checked 6 Aug. The
current-grid-masking caveat at that release point (transport is diffusion/settling only,
not current-driven, because the cell reads as land to the ~9 km current grid) may fully
explain it, or it may not. Not a plume-engine defect and not diagnosed further here;
Pulga/Mahdi should check before the demo runs on this outlet.
