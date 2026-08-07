# Abd — Satellite/Plume, Particle Engine, Mooring Calibration

**Phase 5 · Workstream 5**
Read [`00-phase5-plan.md`](00-phase5-plan.md) first.

---

## Why this phase matters

Both of your Part A items are genuinely done — the real particle engine is wired and
live, and the calibration grid search ran with a recorded winner. What's left is one
honest runtime caveat that's already self-reported by the API.

---

## 0 · Close your Phase 2 items — Day 0/1

- [x] **A5.1 — `/plume/simulate` wired to the real particle engine.** Confirmed
      live: `POST /api/v1/plume/simulate` returns `"is_stub": false`,
      `"model_version": "custom_2d-calibrated-AQ-2016-10-28"`, 24 real contours.
      **One real, currently-live caveat, not a fabricated concern:** the response's
      own `caveats` field says the engine is running on
      `PLACEHOLDER: ConstantCurrentField(0, 0)` and `ConstantWindField(0, 0)` because
      `hycom_aoi_AQ-2016-10-28.nc` is absent from the container. The engine is real;
      the forcing feeding it right now is not.
      - [x] **Currents — closed by Nizar, 2026-08-07.** The `.nc` files were never
            actually missing on this machine; live-checked `POST /api/v1/plume/simulate`
            and it already reports real HYCOM forcing
            (`currents: HYCOM GLBu0.08/expt_91.2 historical archive`), not
            `ConstantCurrentField(0, 0)`. Nothing to re-fetch.
      - [x] **Wind — permanently documented, 2026-08-07.** No historical marine wind
            source exists anywhere in this repo: GFS/GEFS/ECMWF are forecast-only, and
            ERA5-Land (which does ingest `u10`/`v10`) is land-only, so it wouldn't cover
            marine cells even if cached. Written up permanently in
            `docs/forcing_limitations.md`'s new "Wind forcing" section — `ConstantWindField(0, 0)`
            stays as a documented placeholder, not a silent zero.
- [x] **A5.2 — calibration grid search with a recorded winning trial.** Confirmed:
      72 real trials in `plume_calibration_trials.json`, exactly one
      `is_selected: true` (`diffusion_m2_s: 5.0, windage_fraction: 0.0,
      settling_velocity_mm_s: 0.1, transport_regime: "hypopycnal"`). The artifact
      itself already flags the winning `windage_fraction` as a "tie-break artifact,
      not a calibrated value" given zero wind forcing — this self-caveat is honest
      and correct; once real wind forcing exists (see above), **re-run the
      calibration** rather than assuming the current winner still holds under real
      forcing.

---

## Definition of done

1. A5.1's forcing-placeholder caveat is either resolved (real currents/wind cache
   fetched) or explicitly and permanently documented in `docs/forcing_limitations.md`
   as a known, named limitation — not left as an API-only caveat string nobody reads.
2. If real forcing lands, the calibration grid search is re-run and the new winner
   (if different) replaces the current tie-break-flagged one.
