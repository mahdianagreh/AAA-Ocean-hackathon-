# Phase 4 close-out — Abd, 6 August 2026

**Scope:** all three items in [`tasks/phase4/05-abd.md`](../tasks/phase4/05-abd.md) —
(1) wire the real particle engine into `/plume/simulate`, (2) the Real Sensor Proof
Overlay's field scope and fit-quality report, (3) swap #4's status — plus, added to
scope on explicit request after these three closed, feature 14's 3D Journey, which
this same work unblocked. All four are documented below alongside the technical
detail behind them: the particle-transport simulation itself, its calibration, the
mooring validation target, and the real 3D scene built on top of all three.

**Everything in this document was checked against a running process, not read off the
source and assumed** — the same discipline `tasks/phase4/05-abd.md`'s own audit used,
and the one this project's `CLAUDE.md` names as the recurring failure mode ("tests can
pass while the product is dead"). Every number below either came out of a live `curl`
against the API, a `pytest` run, or a Playwright browser session against the real
frontend build. Commands are included so any of this can be re-run in under a minute.

**Revision note:** an independent adversarial audit run after this document's first
version found that §2.5's evidence block, while every individual field was accurate,
implied more physical realism than the showcased run actually demonstrates — it never
quoted the response's own `caveats` array, which discloses that the flagship outlet's
simulated transport is diffusion-dominated, not visibly current-driven. §2.5 has been
corrected to show the full caveats array and the measurement that confirms it, and
`docs/model_card.md` and `tasks/phase4/05-abd.md` were corrected the same way. Nothing
about items 2 or 3 was affected.

---

## Contents

1. [Summary table](#1--summary-table)
2. [Item 1 — the particle-transport simulation](#2--item-1--the-particle-transport-simulation)
3. [Item 2 — Real Sensor Proof Overlay](#3--item-2--real-sensor-proof-overlay)
4. [Item 3 — swap #4, the satellite validation NO-GO](#4--item-3--swap-4-the-satellite-validation-no-go)
5. [The 3D Journey (feature 14) — built](#5--the-3d-journey-feature-14--built)
6. [Files changed](#6--files-changed)
7. [Test results](#7--test-results)
8. [Outstanding work — not this file's scope, flagged for its owner](#8--outstanding-work--not-this-files-scope-flagged-for-its-owner)
9. [References](#9--references)

---

## 1 · Summary table

| Item | Task file ask | Status | Evidence |
|---|---|---|---|
| 1 | Replace `SYNTHETIC_STUB` with the real particle engine | ✅ Closed | Live `curl`, §2.5 |
| 2 | Confirm mooring overlay fields; report fit quality honestly | ✅ Closed | `ValidationPanel.tsx`, §3 |
| 3 | State swap #4's status explicitly | ✅ Closed (NO-GO) | `tasks/00-contracts.md` §5, §4 |
| 14 | The 3D Journey (added scope, not originally this file's) | ✅ Built | `Journey3D.tsx`, §5 |

One correction made along the way: the task file's own opening claim — that
`POST /plume/simulate` still returns `is_stub: true` — was accurate for the branch it
was checked against, but stale for current `main`. See §2.1.

---

## 2 · Item 1 — the particle-transport simulation

### 2.1 · Why the task file's finding was stale, not wrong

`tasks/phase4/05-abd.md` opens with a live check from 6 Aug reporting `is_stub: true`.
That check was run against commit `b987e9d` ("distribute the demo-feature audit into
per-person task files"). The commit that actually wires the real engine, `0de8c26`
("replace SYNTHETIC_STUB with the real particle engine", authored 5 Aug 16:43), was a
**sibling** on a different branch at that moment — `git merge-base --is-ancestor 0de8c26
b987e9d` returns false. The two branches joined afterward in merge commit `6de325c`,
which is current `main`. So the audit was correct about the branch it ran against, and
current `main` had already moved past it. Re-verified below against `6de325c` specifically.

### 2.2 · Architecture

The engine lives entirely in
[`backend/src/models/particle_engine.py`](../backend/src/models/particle_engine.py) — a
deliberately lightweight 2D NumPy particle cloud, not a hydrodynamic model
(`OpenDrift` was explicitly ruled out; the concept doc names "team overbuilds full
physics" as a medium-probability, high-impact risk). It is wired into the API at
[`backend/src/api/main.py`](../backend/src/api/main.py) behind two routes:

```
POST /api/v1/plume/simulate        → runs simulate() + kernel_density_contours(), returns PlumeResult
POST /api/v1/exposure/calculate    → calls plume_simulate() internally (same cache, same cloud)
GET  /api/v1/plume/map             → renders the same contours onto real basemap imagery
GET  /api/v1/plume/map/frames      → the animatable timestep list for the same run
```

`exposure_calculate` deliberately does **not** run its own private simulation — it calls
`plume_simulate()` and reuses its TTL cache, so the picture a user sees in `/plume/map`
and the score `/exposure/calculate` produces always come from the *same* particle cloud,
never two independently-simulated ones that happen to agree.

### 2.3 · The physics

Every active particle steps forward once per `time_step_minutes`:

```
position(t+1) = position(t)
    + current-driven advection         u, v = current_fn(lon, lat, t, depth)
    + windage x wind                   windage_fraction x regime_multiplier x (u10, v10)
    + stochastic horizontal diffusion   N(0, sqrt(2 x diffusion_m2_s x dt)) per axis (a random walk)
    + settling / deposition            probabilistic, depth-scaled (see below)
    + reflection off the coastline     candidate step rejected if it leaves water,
                                        then a probabilistic beaching roll
```

Implementation: `simulate()`, lines 308–419 of `particle_engine.py`. Concretely, per
step:

1. **Current + wind** are queried per active particle via the caller-supplied
   `current_fn(lon, lat, time, depth) -> (u, v)` and `wind_fn(lon, lat, time) -> (u10, v10)`
   — a fixed contract so any real forcing (HYCOM, ERA5-Land, a constant test double) is
   a drop-in.
2. **Windage** is `windage_fraction x REGIME_WINDAGE_MULTIPLIER[regime]` — `1.0` for
   `hypopycnal` (wind-exposed, near-surface transport), `0.0` for `hyperpycnal`
   (bottom-hugging flow, decoupled from wind per Katz et al. 2015).
3. **Diffusion** adds an independent Gaussian draw per axis with
   `sigma = sqrt(2 x diffusion_m2_s x dt_seconds)` — a standard 2D random-walk
   approximation of turbulent horizontal spreading.
4. **Coastline reflection**: the candidate position is tested against
   `CoastlineBoundary.in_water()` (a vectorized point-in-polygon test against
   `coastline.gpkg`). A step that would leave water is rejected outright (the particle
   stays put that step); a per-contact `beaching_probability_per_contact` (default
   `0.15`) roll then decides whether that contact permanently beaches it.
5. **Settling**: probability of reaching the bed this step is
   `clip(settling_velocity_m_s x dt_seconds / effective_height, 0, 1)`, where
   `effective_height` is the real local depth (`BathymetrySampler`, from
   `depth_utm36n.tif`) for `hypopycnal` particles, or a fixed `2.0 m` residual for
   `hyperpycnal` ones (modelled as already riding near the bed). A settled particle
   stops advecting permanently — `active`, `settled` and `beached` are tracked as
   separate boolean arrays per particle per step, never coerced into one flag.
6. Everything is vectorized across all currently-active particles per step (`numpy`
   array ops over `idx = np.where(was_active)`) — inactive particles carry their last
   position forward unchanged rather than being dropped from the arrays, so trajectory
   arrays stay a clean `(n_steps+1, n_particles)` shape throughout.

**Contouring**: `kernel_density_contours()` fits a Gaussian KDE over one timestep's
particle positions, peak-normalizes it (max cell = 1.0), and contours it at
`{0.10, 0.25, 0.50, 0.75}`. This is a **relative density**, not a calibrated arrival
probability — the same honesty distinction the (unrelated, satellite-derived)
`plume_segmentation.anomaly_to_probability` already draws, and the API's own response
caveats repeat it on every call.

### 2.4 · Forcing: what's real and what's an honest placeholder

| Input | For `AQ-2016-10-28` | For any other `event_id` |
|---|---|---|
| Currents | **Real** — cached HYCOM `GLBu0.08/expt_91.2` historical archive (`data/raw/currents/hycom_aoi_AQ-2016-10-28.nc`), baked once by `scripts/28_calibrate_plume_engine.py` | `ConstantCurrentField(0, 0)`, with an explicit "no cached historical archive" caveat in the response — never silent |
| Wind | Placeholder (`ConstantWindField(0, 0)`) — no historical marine wind source (ERA5-Land u10/v10 for this window) is in this repo yet | same |
| Release point | Real coordinate from `outlets.gpkg` (`load_release_point`) | same |
| Bathymetry | Real, GMRT-substituted for GEBCO (see `docs/model_card.md`'s data-foundation note) | same |
| Coastline | Real, `coastline.gpkg` | same |

`AQ-O04` (enclosed harbour basin) is refused by `load_release_point` unless the caller
explicitly passes `acknowledge_harbour_caveat=True` — releasing there produces a
confidently wrong plume (sediment settles in the basin, never disperses into the Gulf),
so the engine will not do it silently.

### 2.5 · Live verification (6 Aug 2026)

Run the API exactly as the container does — same entrypoint, same `--app-dir`, so an
import-path bug that would break `docker compose up` cannot hide behind a different test
harness (see `CLAUDE.md`'s own "tests can pass while the product is dead" gotcha):

```bash
source .venv/bin/activate
uvicorn api.main:app --host 127.0.0.1 --port 8321 --app-dir backend/src &
curl -fsS http://127.0.0.1:8321/health
```

```json
{"status":"ok","version":"0.2.0","commit":"6de325c","model_available":true,"data_volume_mounted":true}
```

Plume simulation for the demo event:

```bash
curl -sX POST http://127.0.0.1:8321/api/v1/plume/simulate \
  -H "Content-Type: application/json" \
  -d '{"event_id":"AQ-2016-10-28","outlet_id":"AQ-O02"}'
```

```
is_stub:        false
model_version:  custom_2d-calibrated-AQ-2016-10-28
provenance:      custom_2d particle engine, 1000 particles, 1 day, currents:
                 HYCOM GLBu0.08/expt_91.2 historical archive, cached
                 data/raw/currents/hycom_aoi_AQ-2016-10-28.nc
contours:        24 real polygons
```

**The `caveats` array on that same response, quoted in full because an earlier version
of this document only excerpted the four fields above — an independent adversarial
audit correctly called that out as incomplete:**

```
[warning] is_stub:    Real particle transport ... but still bounded by its forcing.
[warning] contours:   Contour levels are peak-normalized kernel-density thresholds ...
                      not a calibrated arrival probability. The best free ocean current
                      model resolves ~9 km cells across a gulf ...
[info]    geometry:   Bathymetry is GMRT, substituted for GEBCO ...
[warning] contours:   AQ-O02's release point falls on a cell the current grid masks as
                      land (NaN u/v, treated as zero current per simulate()'s own
                      documented nan_to_num rule). This run's transport is diffusion
                      and settling only, not current-driven ...
```

**What that last caveat means for this specific evidence run, measured rather than
inferred from the caveat text alone:** I tracked this run's contour centroids across
all six reported timesteps (3, 6, 9, 12, 18, 24 h) at all four density levels. None
show coherent directional drift — displacement from the release point wobbles
non-monotonically within roughly 15–100 m (e.g. the 0.10 level: 68 m at 6h, 96 m at 9h,
87 m at 12h, 82 m at 18h, 70 m at 24h — up then down, not a heading), the signature of a
random walk, not of advection. **So: this run's `is_stub: false`, its code path, and its
consulted archive are all genuinely real — that literal claim holds — but its
*simulated output* is empirically indistinguishable from a zero-current diffusion run,
because the ~9 km current grid masks the cell under this near-shore release point.**
Checked the other four outlets too: `AQ-O01`, `AQ-O03` and `AQ-O05` carry the identical
caveat; only a release point on a resolved cell would show visible current-driven
drift at this event's horizon. This is a genuine, disclosed physics limitation of a
~9 km global current model this close to shore — not a wiring defect, and not
something to fix as part of this item — but the framing below has been corrected to
not overclaim it.

Exposure calculation for the same event/outlet:

```bash
curl -sX POST http://127.0.0.1:8321/api/v1/exposure/calculate \
  -H "Content-Type: application/json" \
  -d '{"event_id":"AQ-2016-10-28","outlet_id":"AQ-O02","horizon_hours":24}'
```

```
risk_score:        3.30   (risk_level: minimal)
plume_source:      REAL_PARTICLE_ENGINE
model_versions:    { particle_engine: "custom_2d-calibrated-AQ-2016-10-28",
                     runoff_model: "runoff_weighted_gbm_482c7f9_20260805T123309Z",
                     reef_zones: "AllenCoralAtlas-v2_0",
                     bathymetry: "GMRT-substituted-for-GEBCO" }
```

Neither `SYNTHETIC_STUB` nor `stub-0.1` appears anywhere in either response. Both
checks are reproducible by re-running the two commands above.

**Why the score is still "minimal":** that's no longer this item's doing. The exposure
formula multiplies five terms, each ≤ 1; `plume_probability` is now real and
non-trivial (`0.75` at its max contour), but `relative_sediment_intensity` (`0.084`,
Mahdi's term) and `habitat_sensitivity_weight` (still
`PLACEHOLDER_PENDING_MARINE_SCIENTIST`, `1.0`) are the remaining multipliers holding the
product down. Say this explicitly in the demo so the plume engine doesn't get
re-blamed for a ceiling it no longer owns.

### 2.6 · Calibration

`scripts/28_calibrate_plume_engine.py` ran a 72-trial grid search over
`(diffusion_m2_s, windage_fraction, settling_velocity_mm_s, transport_regime)`, scoring
each trial against the Kalman et al. (2025) mooring record at the Kinnet Canal outlet
(`KINNET_CANAL_OUTLET` in `backend/src/models/calibration.py` — deliberately **not**
`AQ-O01`; the paper's canal discharge point is 1.40 km from Mahdi's Jordanian pour point).
The objective is a weighted sum of three timing errors, never a spatial metric:

```
objective = |arrival_time_error_hours| + |duration_error_hours| + |peak_timing_error_hours|
```

Concentration at each timestep is the fraction of the *original* release within 1 km of
the mooring (`concentration_time_series`); onset/peak/clear are the first threshold
crossing, the running max after onset, and the first crossing back below threshold
(`detect_onset_clear_peak`). A trial whose plume never arrives scores `+inf` and is kept
in the trial log regardless — every one of the 72 trials is recorded, not just the
winner.

**The winner**, verbatim from `data/models/plume_calibration.json`:

| Field | Value |
|---|---|
| Selected regime | `hypopycnal` |
| Diffusion | `5.0 m²/s` |
| Settling velocity | `0.1 mm/s` |
| Windage fraction | `0.0` — **a tie-break artifact, not a fit** (see caveat below) |
| Arrival time error | `-6.83 h` (simulated plume arrives ~6.8h early) |
| Duration error | `+4.25 h` (simulated elevated window runs ~4.25h long) |
| Peak timing error | `-22.54 h` (see caveat below) |
| Objective | `33.62 h` |
| Trials | `72` |

**Caveats, carried forward honestly rather than dropped:**

- **Windage is a tie-break, not a calibrated value.** Wind forcing is identically
  `(0, 0)`, so every `windage_fraction` in the grid contributed the same zero drift —
  the winning value only won on iteration-order tie-breaking. Recalibrate once real
  historical wind exists.
- **Peak timing error is large, and it is measured against a placeholder.** The
  mooring's 5-minute series gives a real onset and clear time but not a digitized peak
  timestamp, so the target used is the onset–clear midpoint
  (`peak_is_midpoint_placeholder: true`). `-22.5h` is not a claim the model missed a
  real observed peak by that much.
- **This is a timing-only fit.** The particle engine does not model sediment
  concentration (g/L) or salinity (PSU) — it was never built to — so this calibration
  says nothing about whether modelled *magnitudes* match the mooring, only *when*
  things happened.

### 2.7 · Test coverage

```bash
python -m pytest tests/test_particle_engine.py tests/test_api_contracts.py \
  tests/test_plume_map_render.py tests/test_spatial_contract.py \
  tests/test_run_id_contract.py -q
```

`71 passed, 2 skipped` (6 Aug 2026, against `main` `6de325c`). `test_particle_engine.py`
alone is 23 tests, exercising advection, diffusion, settling, coastline reflection,
beaching, the harbour-basin refusal, and contour generation directly.

---

## 3 · Item 2 — Real Sensor Proof Overlay

### 3.1 · Fields confirmed

`data/processed/marine/mooring_target_AQ-2016-10-28.json` (Kalman et al. 2025) carries
**five** measured fields, not three:

| Field | Value | Provenance |
|---|---|---|
| Peak suspended sediment | `2.18 g/L` | reported |
| Salinity minimum | `38.75 PSU` | reported |
| Salinity anomaly | `-1.75‰` (`19σ`) | reported |
| Sediment mass | `24,400 t` | reported (the anchor mass) |
| Elevated duration | `31.42 h` | derived (differenced from onset/clear timestamps) |

All five are already live in `frontend/src/panels/ValidationPanel.tsx`'s comparison
table. **Recommended sixth field for Pulga's live `/mooring` endpoint** (not yet
exposed anywhere): `transport_regime` — the mooring file's own `calibration_use` block
says the calibration winner's regime should be "stated as a verdict," and it now has
one (`hypopycnal`, §2.6).

### 3.2 · Fit quality — reported honestly, on screen

The gap here wasn't the fit itself (§2.6 shows it was done) — it was that the fit-quality
numbers sat unread in `data/models/plume_calibration.json`. A repo-wide grep before
today's work found zero references to it outside `calibration.py`/`main.py` and a draft
schema proposal. `scripts/frontend_panels.py`'s `validation()` function now reads it
directly and `ValidationPanel.tsx` renders a new "Transport-timing fit (calibration)"
section — screenshot below, both languages e2e-tested — showing all three error terms,
the regime verdict, and every caveat from §2.6 verbatim, not summarized into an
optimistic sentence.

```
Transport-timing fit (calibration)

The particle engine models transport timing, not sediment concentration or
salinity — it cannot fill the rows above. This is the comparison it can make:
onset, duration and peak timing at the mooring, from a 72-trial grid search
over diffusion, windage and settling velocity.

  Arrival time error      -6.83 h
  Duration error          +4.25 h
  Peak timing error      -22.54 h

Selected regime: hypopycnal (diffusion=5.0 m2/s, windage=0.0, settling=0.1 mm/s,
objective=33.622 h)

[peak-timing caveat, windage caveat, wind-placeholder warning — verbatim]
Source: data/models/plume_calibration.json (scripts/28_calibrate_plume_engine.py)
```

This is additive, not a rewrite: the five-row magnitude table above it is unchanged and
its "Modelled" column correctly still reads "No data" — the particle engine has no
sediment-concentration or salinity output to put there, and fabricating one to fill the
cell would be exactly the dishonest match this project's own rules forbid.

### 3.3 · What was verified before shipping it

- `tsc -b --noEmit` — clean.
- `oxlint` / `stylelint` — clean (one pre-existing, unrelated warning).
- `vitest run` — 14/14 unit tests pass.
- `playwright test tests/scene-walk.spec.ts` — both `en` and `ar` full walkthroughs
  pass, including the existing assertions that `"2.18"` and `"NO-GO"` are visible and
  that the panel does **not** claim a revealed satellite plume.
- A real browser screenshot of the rendered panel (Chromium, via Playwright), confirming
  layout, both languages.

### 3.4 · Scope boundary

This closes the **static** validation panel, which reads from a build-time fixture
(`scripts/frontend_panels.py` → `frontend/public/fixtures/validation.json`), regenerated
as part of this work. Pulga's live `GET /api/v1/events/{event_id}/mooring`
(`tasks/phase4/04-pulga.md` item 2) is a different, still-open piece of work — reuse the
same field list and the same caveats from `data/models/plume_calibration.json` rather
than re-deriving them.

---

## 4 · Item 3 — swap #4, the satellite validation NO-GO

**Closed on 2 Aug 2026** (`739195f`, "complete plume-extraction pipeline; final NO-GO
verdict on AQ-2016-10-28") — it just hadn't been marked in `tasks/00-contracts.md` §5,
which is now updated (row 4, ☑, with the full finding written in rather than a bare
checkmark, since a checkbox alone would misrepresent a negative result as an ordinary
swap).

**What the pipeline actually did**
(`backend/src/models/plume_segmentation.py`, `scripts/run_plume_extraction.py`):

1. SCL-based water masking + four spectral indices (NDSSI, NSMI, red/green ratio,
   red-band anomaly) over Sentinel-2 imagery, pulled via Microsoft Planetary Computer
   (no Copernicus/Earth Engine credentials needed for this tile).
2. A baseline composite from 8 clear 2016 scenes, anomaly detection against it, a
   probability raster, then vectorization to a polygon mask.
3. Visual QC against Sentinel-2 (2016-11-02) **and** an independent Landsat 8 pass
   (2016-11-01): **no plume visible in either.**
4. Cross-checked against the mooring: turbidity had already returned to background
   **2.5–3.5 days** before either satellite pass.
5. The one spectral-anomaly signal the pipeline did surface is a documented
   coastline-hugging artifact (confirmed against a same-season baseline and a larger
   coastal buffer, does not go away) — reported as a methodology limitation, not
   presented as a detection.

**Final verdict: NO-GO on image-based validation for `AQ-2016-10-28`, for a real
physical reason** — the plume dispersed faster than the satellite revisit gap, not bad
luck with clouds and not a processing failure. Full methodology in
`docs/event_audit.md` §3 ("Go / no-go — FINAL, pixel-level QC complete").

**Consequences, stated so nobody re-derives or re-litigates them:**

- `backend/src/models/backtest_metrics.py`'s `assert_spatial_metrics_allowed()` refuses
  IoU/Dice/centroid-distance for this event outright — computing one would produce a
  number that looks like evidence and isn't.
- The validation target is the mooring's salinity/turbidity time series instead (§2.6,
  §3).
- The UI already states this correctly — `ValidationPanel.tsx` shows a `NO-GO` badge and
  the physical-null finding on screen, verified live via the e2e suite (§3.3), which
  explicitly asserts the panel does **not** claim a revealed satellite plume.
- The old `observed_plume_PROVISIONAL.gpkg` is left on disk for the audit trail;
  confirmed (`grep -rn`) that nothing in `backend/src/` or `frontend/src/` reads it —
  only `scripts/generate_provisional_seeds.py`, its original generator.

---

## 5 · The 3D Journey (feature 14) — built

**Built on explicit request, updating this section's original verdict.** It first
said "not built this phase, and that's correct, not a gap" — accurate when written:
feature 14 is Ali's row in `tasks/phase4/00-phase4-plan.md`, Abd's plume-cloud slice
explicitly marked deferred, and nothing in items 1-3 required building it. The user
then asked for it directly, outside this file's original scope; built and recorded
here rather than silently, so `tasks/phase4/06-ali.md` isn't contradicted by an
undocumented change elsewhere. See `tasks/phase4/05-abd.md` §1a for the
task-tracking side of this same update.

### What was actually built

A real MapLibre GL 3D scene (`frontend/src/journey/Journey3D.tsx` +
`journeyStyle.ts`), reachable via a new `journey` overlay from the masthead, flying
through the concept doc's own chain — wadi catchment, coastal outlet, plume, reef —
with three controllable stages and a 6-timestep scrubber/autoplay:

- **Terrain + bathymetry**: `scripts/frontend_basemap.py` gained `relief_bands()` —
  the *exact same* `rasterio.features.shapes` technique `isobaths()` already used on
  `depth_utm36n.tif`, kept as filled polygons instead of just the boundary, so they
  are fill-extrudable. 11 real bands, land (up to ~1,800 m) and sea (to -800 m), one
  committed GeoJSON (`frontend/public/basemap/relief_bands.geojson`, ~325 KB after
  raising the basemap's own documented size budget 1,100→1,400 KB with the same
  reasoning the file already uses for its previous raise).
- **The plume**: a new script, `scripts/frontend_journey.py`, derives
  `frontend/public/fixtures/journey3d.json` from a **live run of the real API** —
  `POST /plume/simulate` + `/exposure/calculate` for `AQ-2016-10-28`/`AQ-O02`,
  all 6 real timesteps, the calibrated engine from §2, not a second implementation.
  This answers §"What a genuine volumetric plume cloud would need" below with the
  smaller of the two named tasks: it flattens the real, already-existing 2D KDE
  contours into an extruded 3D surface (height ∝ real probability level). It does
  **not** do the larger one — see below, still true.
- **Reef zones**: real Allen Coral Atlas geometry, coloured by the real exposure
  result this exact run produces (`R-03`, `minimal`); zones never reached carry no
  colour rather than a fabricated zero.
- **The honesty carried through, not smoothed over**: the scene's on-screen caption
  states its 6× vertical exaggeration and that sea depth is drawn as upward relief
  (not sunk below a surface plane) — and surfaces the *identical*
  current-grid-masking caveat from §2.5 verbatim, so the 3D view doesn't imply a more
  dramatic, current-driven plume than the real run actually shows.

Verified, not just built: `tsc -b --noEmit` clean, lint clean, `vitest run` 14/14,
the full Playwright suite 25/25 (including the axe accessibility pass — which caught
a real contrast regression this same work introduced, `text-ink-3` on `bg-surface-2`
in the calibration-fit caveats added earlier in this document, fixed to `text-ink-2`
to match the passing pattern already used elsewhere in the same panel), and both
language variants of `scene-walk`. Screenshotted directly at multiple stages/frames,
not inferred from a green test run.

**Not a finished visual design.** Getting reef/plume extrusions to render above
rather than swallowed inside the relief layer at the same footprint took two rounds
of height tuning (an initial 1,000 m+ offset pushed them outside the camera's
frustum entirely at this pitch — visible in testing, corrected to a few hundred
metres). What ships is functional and honest, not polished; whoever refines feature
14's visual design next inherits real geometry and a real, regenerable fixture, not
a placeholder.

### What exists today that a 3D consumer could use — and what `Journey3D.tsx` actually used

- `GET /api/v1/plume/map/frames` returns the animatable timestep list — `t_hours` and a
  render URL per frame — already time-indexed, already real.
- `PlumeResult.contours` (from `/plume/simulate`) is a set of 2D KDE contour polygons
  per timestep, in EPSG:4326 — a flattened, probability-banded surface, not a raw
  particle cloud. **This is what the new scene extrudes** (via
  `scripts/frontend_journey.py`'s fixture) — confirming the prediction two paragraphs
  down: it was the smaller, presentation-only task.

**What a genuine volumetric 3D plume cloud would still need — unaddressed by this
build, not solved by it:**

- `SimulationResult.lons` / `.lats` (shape `(n_steps+1, n_particles)`) and the
  `active`/`settled`/`beached` boolean arrays already exist **in memory** inside
  `simulate()`'s return value, but nothing currently persists or serves raw per-particle
  positions — only the post-processed 2D contour polygons reach the API. A 3D cloud
  (as opposed to a 3D-rendered 2D contour) would need either a new endpoint that
  streams per-particle positions per timestep, or a client-side reconstruction from a
  denser contour set.
- **Depth is not tracked per particle.** The engine is 2D (lon/lat only); `hyperpycnal`
  vs `hypopycnal` changes *behaviour* (windage, effective settling height) but does not
  give a particle a literal z-coordinate. A 3D cloud that wants to show near-bed vs
  near-surface transport would need that added — it is a real modelling gap, not a
  wiring one, and is a larger piece of work than the deferred label currently implies.
- The `settled`/`beached` distinction is already tracked and could drive a 3D consumer's
  visual state (a particle stops moving and changes appearance) without any new physics.

**Recommendation, made when this section was written, followed when it was built:**
treat "flatten existing contours into a 3D-rendered surface" and "expose real
per-particle depth" as two different-sized tasks. The first is presentation work on
data that already exists — done above. The second is new modelling — still open,
and still a larger piece of work than a visual-polish pass on what exists today.

### Upgrade, same day — the full narrative (rain, buildings, phased playback)

Requested after seeing the first pass render. Full change list and reasoning is in
`tasks/phase4/05-abd.md` §1a's "Upgrade" note (not duplicated here in full to avoid
two copies drifting apart); summary of what's new:

| Added | Real source | Where |
|---|---|---|
| Buildings | `osm_aqaba.gpkg`'s `buildings` layer, 617 kept (clipped to five small per-outlet buffers, not one box spanning all five) | `scripts/frontend_basemap.py` `buildings()` |
| Rain intensity | Real daily rainfall, `event.json`'s `by_catchment` series — 9.21 mm, AQ-C02, 2016-10-27 (the storm's real peak day) | `scripts/frontend_journey.py` `_real_rainfall()` |
| Runoff paths | Real wadi LineStrings spatially joined against the release catchment's real polygon — 54 lines | `scripts/frontend_journey.py` `_real_runoff_lines()` |
| Six-phase narrative | Normal → rain → flood → transport → accumulation → impact, Play/Pause/Reset, reef stays neutral until the impact reveal | `frontend/src/journey/usePhaseTimeline.ts` |
| Modular layers | One file per concern instead of one growing file | `frontend/src/journey/layers/*.ts` |
| Height budget | sqrt-scaled relief (was linear ×6) — compresses -800..+1,800 m to ~53-560 visual metres | `frontend/src/journey/constants.ts` |

**Two real bugs found and fixed by testing exactly the sequence requested**, not
assumed fixed because the code looked right:

1. **A stuck-timeline bug.** Click every phase manually, then Reset, then Play — the
   sequence never advanced past "Normal." Root cause: `frameIndexRef` wasn't cleared on
   returning to `normal`, and the zero-duration phase's advance condition required a
   strictly-positive elapsed time to exceed a zero target, which is never true. Fixed at
   the root in `usePhaseTimeline.ts` (removed the guard, simplified `play()` to one
   resume path for every phase, `normal` included) and re-verified against the identical
   failing sequence — sampled every second through a full autoplay afterward to confirm
   real phase timing, not just that it eventually finished.
2. **A second real WCAG contrast regression**, same class as the one caught in §7's
   test run (`text-ink-3` on `bg-surface-2`, same fix: `text-ink-2`) — this time in the
   calibration-fit caveats added earlier the same day, found by the same axe test run
   against this upgrade, fixed the same way.

Re-verified after the upgrade: `tsc -b --noEmit` clean, lint clean, `vitest run` 14/14,
full Playwright suite 25/25, and the backend suite unaffected (498/51/1, unchanged — no
backend Python was touched by this upgrade). Screenshotted every phase individually
plus two targeted closeups (a denser building cluster with a real named hotel; the
reef-zone reveal at close zoom, where an outline stroke was added because the "minimal"
risk colour alone was too close to the surrounding terrain tones to read as a change).

**Still not a finished visual design**, stated plainly rather than left to be
discovered: the relief bands are markedly smoother than the first pass (sqrt scaling
instead of linear) but still read as stepped/banded terrain, not a smooth continuous
surface. True smooth terrain would need MapLibre's native raster-DEM `setTerrain`
feature, which needs a terrain-RGB tile pyramid this repo does not have — a real,
separately-scoped undertaking, not attempted here because the upgrade's own
instructions were explicit about avoiding a large architectural rewrite unless
genuinely necessary, and the banded-extrusion approach, now re-tuned, meets the bar of
"real, honest, legible" without it.

---

## 6 · Files changed

| File | Change |
|---|---|
| `tasks/phase4/05-abd.md` | Items 1–3 marked closed with live evidence; Definition of Done and dependency table updated |
| `tasks/00-contracts.md` | Swap #4 row marked closed (NO-GO), full finding written into §5 |
| `docs/model_card.md` | Component C rewritten from "stubbed pending wiring" to the real, calibrated, live-verified engine; verification and limitations added |
| `scripts/frontend_panels.py` | `validation()` now reads `data/models/plume_calibration.json` and emits a `calibration_fit` block; CLI summary line added |
| `frontend/src/api/panels.ts` | `Validation.calibration_fit` type added |
| `frontend/src/panels/ValidationPanel.tsx` | New "Transport-timing fit (calibration)" section; docstring updated |
| `frontend/src/i18n/locales/en/common.json`, `.../ar/common.json` | New `validation.*` keys for the calibration-fit section, both languages |
| `frontend/public/fixtures/{validation,corpus,limitations}.json` | Regenerated — `validation.json` gains the calibration data; the other two picked up unrelated upstream doc updates that hadn't been regenerated yet |
| `scripts/frontend_basemap.py` | New `relief_bands()` — real fill-extrudable elevation/depth bands from `depth_utm36n.tif`; basemap size budget raised 1,100→1,400 KB with documented reasoning |
| `frontend/public/basemap/relief_bands.geojson` | New — 11 real relief bands, land and sea |
| `scripts/frontend_journey.py` | New — derives `journey3d.json` from a live run of the real particle engine + exposure endpoints |
| `frontend/public/fixtures/journey3d.json` | New — real plume frames (6 timesteps), real reef exposure, for `AQ-2016-10-28`/`AQ-O02` |
| `frontend/src/journey/Journey3D.tsx`, `journeyStyle.ts` | New — the 3D Journey scene |
| `frontend/src/app/uiStore.ts`, `panels/OverlayHost.tsx`, `shell/Masthead.tsx` | Wired the new `journey` overlay in alongside the existing four |
| `frontend/src/map/style.ts` | One-line fix: a pre-existing `StyleSpecification` cast error, found while verifying the new code, unrelated to this feature otherwise |
| `tasks/phase4/05-abd.md` §1a | The 3D Journey recorded as built-on-request, outside this file's original assigned scope |
| `docs/HANDOFF_abd_2026-08-06.md` §5 | Updated from "not built" to what was actually built |
| `scripts/frontend_basemap.py` `buildings()` | New — real OSM building footprints, real-or-default height; basemap budget raised 1,400→1,550 KB with documented reasoning |
| `frontend/public/basemap/buildings.geojson` | New — 617 real building footprints, clipped to five small per-outlet buffers |
| `scripts/frontend_journey.py` `_real_rainfall()`, `_real_runoff_lines()` | Extended — real daily rainfall (from `event.json`) and real wadi drainage lines (spatial join) for the release catchment |
| `frontend/src/journey/constants.ts` | New — shared height budget (sqrt-scaled) and phase vocabulary |
| `frontend/src/journey/layers/*.ts` | New — one module per concern (relief, buildings, reef, plume, rain, runoff), replacing the single-file style from the first pass |
| `frontend/src/journey/usePhaseTimeline.ts` | New — the six-phase state machine (Play/Pause/Reset), including the fix for the stuck-on-Normal bug found during verification |
| `frontend/src/journey/Journey3D.tsx`, `journeyStyle.ts` | Rewritten to orchestrate the phase timeline against the new modular layers |
| `frontend/src/i18n/locales/{en,ar}/common.json` | `journey.*` keys replaced with the six-phase vocabulary, both languages |

---

## 7 · Test results

```bash
# Backend — full suite, all optional ingestion deps installed, after merging in
# eight teammate commits (main.py alone gained 358 lines)
source .venv/bin/activate && python -m pytest -q
# 498 passed, 51 skipped, 1 xfailed

# Frontend, including the new 3D Journey code
cd frontend
npm run typecheck   # clean (one pre-existing StyleSpecification cast error found and fixed)
npm run lint        # clean (1 pre-existing, unrelated warning)
npm run test        # 14 passed (vitest)
npx playwright test tests/scene-walk.spec.ts tests/hardening.spec.ts   # 25 passed
```

The Playwright run initially returned 1 failure — the automated axe pass flagged
insufficient colour contrast (`text-ink-3` on `bg-surface-2`, 4.38:1 against a 4.5:1
requirement) on three lines in the calibration-fit section added earlier in this
document. Real regression, not a flake: fixed to `text-ink-2`, matching the passing
pattern already used elsewhere in the same panel, then re-ran green.

No regressions found anywhere in the suite. The two backend test files that initially
failed to collect (`test_event_pipeline_config.py`, `test_imerg_ingestion.py`, missing
`earthaccess`) and one that failed outright (`test_era5_land_ingestion.py`, missing
`cdsapi`) were a pre-existing local `.venv` gap in Karam's ingestion modules —
unrelated to anything in this close-out (confirmed via `git log` that neither file has
been touched since well before Phase 3). Installing the two missing packages resolved
all three; the full suite is green.

---

## 8 · Outstanding work — not this file's scope, flagged for its owner

- **`AQ-O01` (96% of discharge, the primary demo outlet) returns zero reef-zone
  intersections** from `/exposure/calculate` at a 24h horizon — live-reproduced twice
  during this close-out. This is the same current-grid-masking limitation documented in
  §2.5 (it is not unique to `AQ-O01` — `AQ-O02`, `AQ-O03` and `AQ-O05` carry the
  identical caveat for this event), and may fully explain the zero result, or may not.
  Not a plume-engine defect; not diagnosed further here. Pulga/Mahdi should check
  before the demo runs on this outlet, and before choosing which outlet to feature if a
  visibly current-driven plume is wanted for the presentation.
- **Pulga's live `GET /api/v1/events/{event_id}/mooring`** is still open — this
  close-out supplies the field scope and fit-quality caveats it should reuse (§3.1,
  §3.2), but does not build the route itself.
- **The 3D Journey's plume-cloud slice** remains deferred by design (§5) — flagged here
  only so the "raw particle positions vs. rendered contours" distinction isn't
  rediscovered from scratch later.
- **`habitat_sensitivity_weight` is still `PLACEHOLDER_PENDING_MARINE_SCIENTIST`** and
  **wind forcing is still a placeholder for every event** — both outside this item's
  scope, both the reason exposure scores stay in the "minimal" band even with a real
  plume engine (§2.5).

---

## 9 · References

- [`tasks/phase4/05-abd.md`](../tasks/phase4/05-abd.md) — the task file this closes out
- [`tasks/phase4/00-phase4-plan.md`](../tasks/phase4/00-phase4-plan.md) — Phase 4 plan and the dependency chain this item gates
- [`tasks/00-contracts.md`](../tasks/00-contracts.md) §5 — swap tracking
- [`docs/model_card.md`](model_card.md) Component C — the model card entry for this engine
- [`docs/event_audit.md`](event_audit.md) §3 — the satellite go/no-go methodology in full
- [`docs/pitch_limitations.md`](pitch_limitations.md) §9 — the judge-facing version of the same finding
- [`docs/mooring_coordinate_derivation.md`](mooring_coordinate_derivation.md) — how the mooring's position was derived
- [`backend/src/models/particle_engine.py`](../backend/src/models/particle_engine.py) — the simulation
- [`backend/src/models/calibration.py`](../backend/src/models/calibration.py) — the calibration grid search
- [`backend/src/models/backtest_metrics.py`](../backend/src/models/backtest_metrics.py) — timing-error metrics and the spatial-metrics refusal
- `data/models/plume_calibration.json`, `data/models/plume_calibration_trials.json` — calibration results, all 72 trials
- `data/processed/marine/mooring_target_AQ-2016-10-28.json` — the validation target
- [`tasks/phase4/06-ali.md`](../tasks/phase4/06-ali.md) — feature 14's original owner and scope
- [`frontend/src/journey/Journey3D.tsx`](../frontend/src/journey/Journey3D.tsx), [`journeyStyle.ts`](../frontend/src/journey/journeyStyle.ts) — the 3D Journey scene
- [`scripts/frontend_journey.py`](../scripts/frontend_journey.py) — derives the scene's plume/exposure fixture
- [`scripts/frontend_basemap.py`](../scripts/frontend_basemap.py) `relief_bands()`, `buildings()` — derives the scene's terrain/bathymetry and building layers
- [`frontend/src/journey/layers/`](../frontend/src/journey/layers/), [`constants.ts`](../frontend/src/journey/constants.ts), [`usePhaseTimeline.ts`](../frontend/src/journey/usePhaseTimeline.ts) — the modular layer/phase architecture from the same-day upgrade
- [`frontend/src/api/event.ts`](../frontend/src/api/event.ts) — the real rainfall series type/loader the upgrade's rain phase reuses
