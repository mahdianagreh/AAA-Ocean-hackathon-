# Abd — Phase 3

> **Update, 5 Aug — done for you, while you'd pushed nothing:** item 1 below,
> `SYNTHETIC_STUB` → your real particle engine, is wired into
> `/plume/simulate`, `/plume/map` and `/plume/map/frames`. Nothing in
> `particle_engine.py` changed — `simulate()` and `kernel_density_contours()`
> were already correct and are called exactly as you wrote them.
>
> What landed, across four commits on `main`: `backend/src/models/plume_forcing.py`
> (a `RegularGridInterpolator` rebuild of `ocean_currents.CurrentFieldInterpolator`'s
> grid, same method, verified byte-identical output, ~40x faster — `simulate()`
> calls `current_fn` per-particle-per-step, and `.interp()`'s ~4 ms/call would have
> been ~13 minutes for a 2,000-particle run); `scripts/28_calibrate_plume_engine.py`,
> which ran your Part 2 grid search for real against the cached HYCOM historical
> archive and the real mooring target, and wrote the winner to
> `data/models/plume_calibration.json` (hypopycnal, diffusion 5 m²/s, settling
> 0.1 mm/s — objective 33.6h; windage came back a tie-break artifact since wind
> is still `ConstantWindField(0,0)`, not a calibrated value, see the file's own
> `windage_caveat`); `main.py`'s `_real_contours()`, which resolves the release
> point, the flood-arrival release time (parsed from `docs/event_dates.md`, never
> hard-coded), the calibrated params, and real HYCOM currents where a cached
> archive exists (only `AQ-2016-10-28` — `_current_fn_for_event` falls back to a
> labelled `ConstantCurrentField(0,0)` placeholder for anything else, never a
> guess).
>
> **A finding worth knowing before you build on this**: `AQ-O01` (96% of
> discharge) sits on a current-grid cell HYCOM masks as land — `current_fn`
> returns NaN there, so that release is diffusion-and-settling-only, no
> current-driven transport, and the modelled plume does not reach any reef zone
> within 120h. It's now a surfaced caveat (`contours` field, "release point
> falls on a masked cell"), not a silent gap. `AQ-O02`, `AQ-O03` and `AQ-O05` do
> reach a nearby zone at `minimal`. Worth deciding whether the demo leads with
> `AQ-O01` (the honest "we looked and it's not close enough to score" result) or
> one of the others (a visible, non-trivial exposure score) — that's a framing
> call, not something I changed the physics to produce.
>
> Pull before touching `main.py`'s plume/exposure sections, `caveats.py`, or
> `ocean_currents.py` (added a `.dataset` property) — all changed.

**Your stub is now visible in a picture, and that changes the priority.** Read
[`00-phase3-plan.md`](00-phase3-plan.md) first.

Look at this before anything else:

```bash
API_PORT=8100 docker compose up -d api
curl "localhost:8100/api/v1/plume/map?event_id=AQ-2016-10-28&outlet_id=AQ-O01&clip_to_sea=false" -o raw.png
```

That image puts the plume over Aqaba's **city centre, the airport and a golf course**.
Because the synthetic stub returns concentric `sqrt(t)` buffers around the release point
with no knowledge of the coastline. In JSON it looked like six perfectly reasonable
polygons. Drawn on real imagery it is obviously impossible.

The renderer clips to the sea by default so the product is not embarrassing, but clipping
hides a symptom rather than fixing a cause: **the shape is still wrong.** A real plume is
stretched and bent by the current, and drifts one way. Ours fans out evenly in all
directions, which no plume has ever done.

---

## 1 · Replace `SYNTHETIC_STUB` with the real particle engine — 🔴

`backend/src/models/particle_engine.py` already has `simulate()`,
`kernel_density_contours()` and `load_release_point()`. The API is not calling them; it
calls `_synthetic_contours()` in `main.py`.

- [x] Wire `/plume/simulate` to the real engine. — done 5 Aug, see the update note above.
- [x] `plume_source` must stop saying `SYNTHETIC_STUB`, and `model_versions.particle_engine`
      must stop saying `stub-0.1`. Both are read by the renderer and both appear in stored
      exposure runs. — now `REAL_PARTICLE_ENGINE` / `custom_2d-calibrated-AQ-2016-10-28`.
- [x] Advect with **Nizar's real currents**, not synthetic drift. He has HYCOM and
      Copernicus Marine ingestion. — HYCOM historical archive, only for `AQ-2016-10-28`
      (the only event with a cached archive); everything else still gets the labelled
      `ConstantCurrentField(0,0)` placeholder, not a guess.

The moment that lands, the response header on the map endpoint flips from
`X-ReefShield-Plume-Source: stub` to `particle-engine` on its own, and the whole picture
becomes real without anyone touching the renderer.

**Watch out — the release point.** `particle_count_for_sediment_class` accepts `None`
(Component D not run) and keys on lowercase `low | medium | high | extreme`. Canonical
vocabulary is pinned by `tests/test_sediment_class_vocabulary.py`; three modules disagreed
about it until 4 Aug.

**Watch out — AQ-O04.** It sits **427 m outside the sea polygon**, in an enclosed harbour
basin — the only outlet of the five that is not in open water. A plume released there
settles in the basin. `HarbourBasinReleaseError` exists for this. Do not quietly relocate
the release point to make the simulation run.

---

## 2 · Calibrate against the mooring, not a hand-drawn mask

This is the strongest validation asset in the project, and it is measured rather than
assumed. Kalman et al. (2025), 250 m off the Kinnet Canal at 13 m depth, 5-minute sampling:

| | |
|---|---|
| turbidity peak | **2.18 g/L** |
| elevated for | **~31 h** |
| salinity anomaly | **−1.75 ‰ (19σ)** |

- [ ] Fit the transport parameters — diffusion, settling, windage — against that time
      series.
- [ ] Report the fit honestly, including where it does not match.

**The satellite validation is a NO-GO and that is a result, not a gap.** The plume
dispersed ~31 h after arrival; the only usable passes are **+104 h and +128 h**. Two
sensors, no plume. Saying *"we looked, the satellite could not see it, so we validated
against a mooring instead"* is a **stronger** slide than a vague claim of satellite
confirmation, and it survives questioning. Do not soften it.

---

## 3 · Real plume mask — closes contract swap #4

`observed_plume_PROVISIONAL.gpkg` is still provisional and it is swap #4 in
`tasks/00-contracts.md` §5.

- [ ] Publish the real mask, or **explicitly declare it stays provisional** and say so in
      the validation panel. Either is acceptable; a silent placeholder is not.
- [ ] The filename does not travel to the viewer. If provisional geometry reaches the
      screen, the UI has to label it — coordinate with Ali.

---

## 4 · Feed the renderer, do not duplicate it

`backend/src/rendering/plume_map.py` already draws contours onto real Esri WorldImagery,
clips to the sea, colours reef zones by exposure and emits animation frames. It is verified
to work **with the network cut** — I ran the container on an isolated Docker network where
it cannot resolve the tile server, and it still returned a real basemap.

You do not need to build any of that. What it needs from you is contours whose **shape**
is physics.

Two things that will make the picture read well once the engine is real:

- [ ] Contours at consistent timesteps, so the frames animate smoothly. It currently
      returns 3/6/9/12/18/24 h.
- [ ] A probability per contour that means something — the renderer shades by arrival time
      and the legend says "darker = arrives sooner".

---

## Definition of done

1. `/plume/simulate` runs the **real** particle engine; `plume_source` no longer says stub.
2. Advection uses Nizar's real currents.
3. Transport parameters fitted to the Kalman mooring, with the fit quality stated.
4. The satellite null result written up as a result, not an omission.
5. Swap #4 either closed or explicitly declared provisional in the UI.
6. `clip_to_sea=false` no longer produces a plume over the airport — because the physics
   keeps it in the water, not because it is being clipped.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Nizar** | real current fields | Yes for advection — start with the engine wiring |
| **Mahdi** | `sediment_class` for particle scaling | No — `None` is handled |
| **Karam** | event windows, rainfall series | No, already delivered |
