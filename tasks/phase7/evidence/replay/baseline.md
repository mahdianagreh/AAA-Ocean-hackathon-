# Phase 7 — Abd — Phase 0 baseline

Captured 9 Aug 2026 against `e558a60`, API run locally on port 8010 (port 8000 was
occupied by an unrelated pre-existing process on this machine, `cv_supervision.api` —
left untouched, not part of this repo).

## Ground truth that changes the plan

**Currents are NOT the placeholder for the anchor event on this checkout.**
`data/raw/currents/hycom_aoi_AQ-2016-10-28.nc` exists (git-ignored raw cache, present
locally). `POST /plume/simulate` for `AQ-2016-10-28`/`AQ-O01` returns
`provenance: [{"kind": "derived", "detail": "custom_2d particle engine, 3000
particles, ... currents: HYCOM GLBu0.08/expt_91.2 historical archive, cached
data/raw/currents/hycom_aoi_AQ-2016-10-28.nc"}]` — real HYCOM, not
`ConstantCurrentField(0,0)`.

This means `ReplayPage.tsx`'s hardcoded `forcingBody` i18n copy —
*"On this build ocean currents fall back to a constant zero field"* — **is
currently false on this checkout.** It was true against a checkout without the
cached `.nc` file, but the string was written as prose rather than read from the API,
so it did not update when the environment did. This is exactly the "plausible,
wrong output with no error" failure mode CLAUDE.md warns about, and it is the reason
Phase 1/2/3 render `provenance[]`/`caveats[]` verbatim rather than writing another
prose sentence.

**Wind is genuinely, unconditionally zero.** Every `/plume/simulate` response
carries the caveat: *"Wind: ConstantWindField(0, 0) — no historical marine wind
source exists in this repo (GFS/GEFS/ECMWF here are forecast-only, not a 2016
archive)."* This part of the task file is correct and stable.

**A more precise reason the anchor plume doesn't drift far exists, and it isn't
"no current data."** `AQ-O01`'s release point falls on a cell the current grid masks
as land (NaN u/v → treated as zero per `simulate()`'s own `nan_to_num` rule). The
API's own caveat: *"This run's transport is diffusion and settling only, not
current-driven, until it drifts onto a resolved cell — a real reason a plume can
stay tight near the outlet even over a long horizon, not evidence that nothing is
happening."* (source: `tasks/nizar.md`). Prefer this verbatim caveat over an invented
sentence — it's more specific and it's already written.

**The windage tie-break disclosure already exists, but only on `/dashboard/validation`.**
`data/models/plume_calibration.json`'s `windage_caveat` field states the tie-break
argument verbatim and `ValidationPage.tsx:254` already renders it. `core-C`/Replay do
not currently display `windage_fraction` as a value anywhere, so there is nothing
un-caveated today — but if Phase 2/3 add a forcing summary that touches windage, it
must carry this same caveat, sourced from the same field, not re-derived.

## Confirmed live, exactly as documented

- `GET /api/v1/events/{event_id}/mooring` — anchor `AQ-2016-10-28` → 200, all 5
  fields match the paper numbers (salinity −1.75‰ σ19, turbidity 2.18 g/L, duration
  31.42 h, mass 24,400 t, `series_available: false`). Non-anchor → **404**, not 500.
- `POST /plume/simulate` / `GET /plume/map/frames` for any non-anchor event id →
  **422**, `"<id> has no converted.flood_arrival_utc in docs/event_dates.md — the
  particle engine needs a real release time and will not guess one."`
- `POST /exposure/calculate` for `AQ-2016-10-28`/`AQ-O01` at 24 h → `results: []`,
  with the exact caveat: *"No reef zone is reached from AQ-O01 within 24 h. The
  nearest zone is R-01 at 1923 m, and the plume's largest modelled extent is 418 m.
  This is reported as no exposure, NOT as zero-risk exposure."* Already rendered by
  `ReplayPage.tsx`'s `Caveats` section when `runCaveats.length > 0` — confirmed
  non-empty for this run, so the number is already on screen. `ExposureRun`'s TS
  interface doesn't declare `caveats`, though (runtime cast in `ReplayPage.tsx:124`)
  — worth a type fix while in the file.
- `/plume/map/frames` for the anchor: 6 frames at `t_hours` 3/6/9/12/18/24,
  `plume_source: "particle-engine"`, `basemap_present: true`. Call takes ~14 s total
  (consistent with "~5 s per frame" — several frames render on first request).

## `/plume/map/frames` does NOT carry provenance/caveats — confirmed gap

Response body is exactly `{event_id, outlet_id, frame_count, frames, basemap_present,
plume_source}`. No `provenance`, no `caveats`, no forcing summary. This is the one
genuine backend gap blocking `core-C` and the Replay forcing note — Phase 1 fixes it.

## journey3d — root cause found and fixed in this session

Three specs failed, but not for the reason `05-abd.md` names. `public/terrain/` and
`public/basemap-raster/` were **not** both absent — `terrain/{7..12}` and
`basemap-raster/aqaba_marine_esri.{jpg,json}` were present. The actual missing file
was `basemap-raster/aqaba_terrain_esri.{jpg,json}` (a *different* pair, from a
*different* script — `scripts/fetch_journey_imagery.py`, not
`fetch_basemap_raster.py`). Vite's dev server returns HTTP 200 with an HTML body for
a missing static file (SPA fallback), so `imagery.ts`'s `if (!res.ok) return null`
guard didn't catch it — `res.json()` threw, and that uncaught page error failed 4 of
5 specs as collateral damage, not because of anything terrain- or phase-related.

Fixed by running `scripts/fetch_journey_imagery.py` (needs network; succeeded) and
copying its output to `frontend/public/basemap-raster/`, exactly per that script's
own docstring. Both files are git-ignored, regenerable — not committed.

Result: `npx playwright test journey3d --workers=1` → **6/6 pass**. Full-parallel run
still drops the last three (frame-rate sample + two "browser closed" timeouts) —
this is the documented machine-contention behaviour, reproduced, not a regression.
Per the task file's own instruction, the test is not weakened.

## Both data-source modes

`VITE_DATA_SOURCE` defaults to `fixtures` under plain `npm run dev` — confirmed via
network trace (`/dashboard` load pulls `basemap/*.geojson` and `fixtures/*.json`
locally, one live call observed to `alerts` on a port already configured via env).
`=http` mode not yet exercised end-to-end for the four owned rows; will be checked
in each phase's own manual pass before filing evidence.
