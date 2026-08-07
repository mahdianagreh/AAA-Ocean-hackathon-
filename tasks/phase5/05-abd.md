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

---

## Status update, 7 Aug 2026, from Abd — both DoD items re-confirmed live, after Phase 5's first merge landed

Re-checked from scratch rather than trusted from the checklist above, specifically
because a large batch of teammate Phase 5 work (14 commits — Karam's A1 closure,
Nizar's A4.2/B6, Pulga's A3.4/B4/B5/B7/B8) had just merged into `main` and touched
`backend/src/api/main.py` substantially (+467 lines). Live-checked `POST
/api/v1/plume/simulate` for `AQ-2016-10-28`/`AQ-O02` against the running container
after that merge:

```
is_stub: false
model_version: custom_2d-calibrated-AQ-2016-10-28
provenance: "currents: HYCOM GLBu0.08/expt_91.2 historical archive, cached
  data/raw/currents/hycom_aoi_AQ-2016-10-28.nc"
caveats: wind = ConstantWindField(0, 0), "no historical marine wind source exists
  in this repo (GFS/GEFS/ECMWF here are forecast-only, not a 2016 archive)"
```

Matches this file's own claims exactly — DoD item 1 still holds. `data/models/plume_calibration.json`
also re-checked: `current_source: "HYCOM GLBu0.08/expt_91.2 historical archive"` confirms
the 72-trial calibration already ran against real currents, not a placeholder — the
`forcing_is_placeholder` flag on that artifact is scoped to wind only, matching DoD
item 2's actual trigger ("once real wind forcing exists"), which cannot fire: wind is a
permanent limitation (`docs/forcing_limitations.md`), not a pending fetch. Full backend
suite re-run after the merge: 543 passed, 49 skipped, 1 xfailed.

**Checked `00-phase5-plan.md`'s ownership table before looking for more to do, rather
than assuming there was none:** Abd's only Phase 5 assignment is "Close A5" — no Part B
feature, unlike every other teammate (Mahdi: B1/B2/B3/B9, Pulga: B4/B5/B7/B8, Nizar:
B6). Grepped every other teammate's Phase 5 file for "Abd" — zero hits, so nothing
downstream depends on this workstream either. **Deliberately did not pick up B1
(Automated Plume Segmentation Model) or continue the 3D Journey**, even though both sit
close to this workstream's domain — `tasks/phase5/02-mahdi.md` §1 and §5 assign both to
Mahdi explicitly "end to end," and the commit that made that change
(`8d6feea`, "make the 3D Journey task Mahdi's alone, no cross-team wiring") states the
reason plainly: no cross-team wiring this phase. Building on either without being asked
would contradict that decision, not help it.

One thing worth handing off rather than leaving implicit: `tasks/phase5/02-mahdi.md`
§5's first checklist items (§3.1 — fetch the DEM, merge it with `depth_utm36n.tif`
bathymetry through the coastline seam) already have a working, tested implementation
from the Phase 4 terrain upgrade (`tasks/phase4/05-abd.md` §1a's "Upgrade #3") —
`scripts/03_dem_fetch.py` (pre-existing), `scripts/merge_terrain_bathymetry.py` and
`scripts/tile_terrain_rgb.py` (new, committed, pushed). The DEM/merged-surface raster
outputs themselves are git-ignored (regenerable, not committed, same convention as
every other baked raster in this repo), so Mahdi still needs to run these scripts on
his own machine — but he does not need to write them from scratch.
