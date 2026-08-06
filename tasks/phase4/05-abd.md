# Abd — Phase 4

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

## 1 · Replace `SYNTHETIC_STUB` with the real particle engine — 🔴 same ask as Phase 3, still open

- [ ] Wire `/plume/simulate` to the real engine. This is route-level plumbing in
      `main.py`, not new modeling — the engine and its tests already exist.
- [ ] `plume_source` must stop reading `SYNTHETIC_STUB`, and `model_versions.particle_engine`
      must stop reading `stub-0.1`. Both are read by the renderer and both get written into
      every stored exposure run — right now every run this project has that lists a real
      `runoff_model` version still lists a fake `particle_engine` one next to it.
- [ ] Advect with Nizar's real currents once he confirms they're ready for you (his file
      has him re-checking Supabase and the current-field handoff this phase) — synthetic
      drift was the reason a stub render put a plume over Aqaba's airport last time this
      was checked.

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

## 2 · Real Sensor Proof Overlay (feature 10) — 🟡 confirm which fields, Pulga builds the route

The mooring data itself is real and already file-cited — your derivation work here from
Phase 3 stands. Pulga is adding a thin read-through endpoint over
`data/processed/marine/mooring_target_AQ-2016-10-28.json` this phase (his file, item 2).
What he needs from you is scope, not new data:

- [ ] Confirm which fields the overlay UI actually needs on screen — turbidity peak
      (2.18 g/L), salinity anomaly (−1.75‰, 19σ), the elevated-duration window (~31h) are
      the headline three from Phase 3's validation work. Say if there's a fourth.
- [ ] If your transport-parameter fit against the mooring (Phase 3 item 2 — diffusion,
      settling, windage fitted to the time series) is done, report the fit quality
      honestly, including where it doesn't match — that number belongs next to the overlay,
      not just in a report nobody reads during the demo. If it isn't done yet, say that
      plainly rather than let the overlay ship with an implied "the model matches the
      sensor" that hasn't actually been checked.

---

## 3 · Swap #4 — still open from Phase 3, worth one line here

`observed_plume_PROVISIONAL.gpkg` — if this closed already, confirm it in writing so it
drops off future lists. If it's still provisional, that's fine, but the UI has to keep
labelling it as such; don't let it go stale-and-silent into Phase 4's demo.

---

## Definition of done

1. `/plume/simulate` runs the real particle engine — confirmed live, not just in code,
   the way I confirmed it's *not* running live during this audit.
2. `plume_source` and `model_versions.particle_engine` both read real values in a live
   response.
3. Mooring overlay fields confirmed to Pulga; fit quality against the mooring stated
   honestly, whichever way it goes.
4. Swap #4's status stated explicitly — closed, or still provisional and labelled.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Nizar** | real current fields for advection | Yes for full realism — start wiring the route now, advect with synthetic drift if his fields aren't ready yet, upgrade after |
| **Pulga** | the mooring endpoint itself | No — he's building it in parallel; you just need to confirm field scope |
