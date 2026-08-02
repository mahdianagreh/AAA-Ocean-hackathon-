# Abd — Marine Transport & Validation

**Phase 2 · Workstream 5**
**Feeds:** Component F (plume transport) → the exposure engine, the backtest, the demo
**Read [`00-phase2-plan.md`](00-phase2-plan.md) first.**

---

## Why your stream matters

You just did the hardest thing on this project: you ran the gate, and you reported a
**NO-GO** instead of dressing up an artifact as a detection. Three independent lines of
evidence — two sensors, the in-situ record, and a spectral anomaly that only surfaced a
coastline-hugging artifact — and you said so plainly.

That result is worth more than a weak positive would have been, and it changes what you
build next. **You now own the marine half of the model**, and the validation target you
yourself found.

The mooring record from Kalman et al. (2025) — 250 m offshore the Kinnet Canal outlet, 13 m
depth, sampling every 5 minutes through the entire flood — is a quantitative, continuous,
satellite-independent measurement of exactly what this project claims to predict. It is a
better calibration target than a hand-drawn mask would ever have been.

---

## 1 · Component F · The particle engine

```text
particle position at t+1
  = current-driven advection
  + windage x wind
  + stochastic horizontal diffusion
  + settling / deposition
  + reflection off the coastline
```

- [ ] Custom lightweight 2D NumPy/Xarray engine. Concept §25 lists *"team overbuilds full
      physics"* as medium probability / high impact — the MVP is explicitly limited to 2D
      probabilistic particles. Do not import OpenDrift and spend three days configuring it.
- [ ] Forcing from Nizar's interpolator: `u(lon, lat, t)`, `v(lon, lat, t)`. You call it and
      get u/v back. If you find yourself transposing dimensions or renaming coordinates,
      that is his bug, not yours — tell him.
- [ ] Boundary from Pulga's `coastline.gpkg` and `depth_utm36n.tif`. Particles stop at the
      shore.
- [ ] Release points: **`AQ-O01`** (34.97073, 29.54560 — Wadi Yutum, **96% of discharge**,
      the event the project is built around) and **`AQ-O05`** (34.95998, 29.35737 — clean
      natural wadi, reef directly offshore). These are the two defensible outlets.

> **Do not release at `AQ-O04`.** It sits inside an enclosed harbour basin. Sediment there
> settles in the basin rather than dispersing into the Gulf, so a simulation from that
> coordinate produces a confidently wrong plume. If it must appear at all, it appears with
> the caveat attached.

- [ ] Release magnitude scaled by Mahdi's sediment class for the event.
- [ ] Output: **kernel-density probability field per timestep**, contoured at 0.10 / 0.25 /
      0.50 / 0.75. **Never a single trajectory line.** Trajectories go to Storage as Parquet;
      only the contours go in the database.

---

## 2 · Calibration against the mooring

This replaces calibrating against a satellite mask. It is the core of your workstream.

### The target

| Quantity | Measured value |
|---|---|
| Turbidity onset | 09:50 local, 28 Oct 2016 |
| Turbidity cleared | ~17:15 local, 29 Oct 2016 |
| Elevated duration | **~31 hours** |
| Peak suspended sediment | **2.18 g/L** near the seafloor |
| Salinity minimum | **38.75 ‰** — 1.75 ‰ below the 9-month background mean of 40.53 ‰, 19σ |
| Location | 250 m offshore the Kinnet Canal outlet, 13 m depth |

- [ ] Grid-search **diffusion coefficient × windage × settling velocity**.
- [ ] Objective: match arrival time, duration and peak timing at that point. Write the
      objective function down — a fit whose criterion is unstated is a fit nobody can check.
- [ ] Record every trial in `calibration_trials` with `is_selected` on the winner. Concept
      §22.4 scores scientific integrity on exactly this: every model run stores its
      parameters.

### The detail that works in your favour

The mooring sits at **13 m depth, near the seafloor**. Katz et al. (2015) found these floods
form **hyperpycnal flows** — sediment-dense water that sinks and travels along the bed rather
than floating as a surface plume, and that carries most of the sediment mass. So the mooring
is measuring the **dominant pathway**, not a surface film. You are calibrating the branch
that actually matters.

- [ ] Implement hypopycnal (surface) and hyperpycnal (bottom) transport as a toggle, and be
      able to say which one the calibration selected. Kalman et al. report the plume
      alternated between the two during the event.

### The exact mooring coordinate is not published

The paper gives only *"~250 m offshore the Kinnet Canal outlet, 13 m depth."*

- [ ] Derive a position, **record how you derived it**, and treat it as an assumption with a
      stated uncertainty radius. Do not present a derived coordinate as a reported one — the
      project's source-vs-derived discipline (`docs/event_dates.md` §3) applies here too.

---

## 3 · Backtest metrics

- [ ] Metric module written and unit-tested against synthetic inputs early, so that on the day
      both real sides exist it is one command.
- [ ] Report against the mooring: **arrival-time error**, **duration error**, **peak-timing
      error**.
- [ ] Report spatial metrics (IoU, Dice, centroid distance) **only if** a real observed mask
      ever exists. For `AQ-2016-10-28` it does not — say so rather than computing them
      against your own coastal artifact.
- [ ] Beat at least one baseline from concept §13.6: a circular buffer around the outlet,
      wind-only movement, current-only movement, or a fixed southward assumption. If the
      model cannot beat a circle, that is the finding and it gets reported.

---

## 4 · The satellite pipeline keeps its place

Your extraction pipeline is built, documented, credential-free via Planetary Computer, and
correct. It is not wasted.

- [ ] Keep it as the **live / operational path** — the thing that runs when a real flood is
      caught with better revisit luck.
- [ ] Do **not** hand `observed_plume.gpkg` (110 polygons, ~2.0 km²) to the exposure engine
      or the backtest as ground truth. Per your own §1c it is the coastal artifact, not a
      validated plume.
- [ ] Write the null result up as a demo slide. *"We tested it, it failed, here is the
      physical reason, so we validated against something better"* is a stronger story than
      most teams will bring, and it is true.

**The methodology finding is worth stating too:** naive per-pixel differencing of Sentinel-2
L2A reflectance over open water produces a coastline-hugging artifact that survives a
same-season baseline and an 80 m coastal buffer. Sen2Cor's atmospheric correction is
land-optimised, and sun-angle and residual aerosol differences swamp subtle water-leaving
radiance at basin scale. That is a real, generalisable lesson.

---

## Definition of done

1. 2D particle engine running against Nizar's interpolator and Pulga's coastline, releasing
   at AQ-O01 and AQ-O05.
2. Probability fields per timestep, contoured; trajectories to Storage, contours to Postgres.
3. Calibration grid search complete, objective function documented, `calibration_trials`
   populated with a selected winner.
4. Hypopycnal / hyperpycnal toggle implemented, with a stated verdict on which fits.
5. Mooring coordinate derivation documented as an assumption with an uncertainty radius.
6. Backtest metrics: arrival, duration, peak — against at least one baseline.
7. The NO-GO written up as a slide, and `observed_plume.gpkg` clearly flagged as
   not-ground-truth wherever it appears.

## Handoffs

| Teammate | What they get | When |
|---|---|---|
| **Pulga** | time-stepped probability contours for the exposure engine | Day 6 |
| **Ali** | plume layers per timestep for the map and time slider | Day 6 |
| **Karam** | backtest numbers for the validation panel | Day 9 |

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Nizar** | current interpolator | **Partly** — build against HYCOM, which already works |
| **Pulga** | coastline + depth field | **No** — both already exist |
| **Mahdi** | sediment class per event | **No** — parameterise it, swap the number later |
| **Karam** | event window | **No** — it is in `docs/event_dates.md` |
