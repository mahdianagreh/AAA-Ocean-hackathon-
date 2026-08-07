# Abd — Satellite/Plume, Particle Engine, Mooring Calibration

**Phase 5 · Workstream 5**
**Feeds:** Mahdi (B1 mask library)
Read [`00-phase5-plan.md`](00-phase5-plan.md) first.

---

## Why this phase matters

Both of your Part A items are genuinely done — the real particle engine is wired and
live, and the calibration grid search ran with a recorded winner. What's left is one
honest runtime caveat that's already self-reported by the API, and it's worth closing
because it's the same fix Nizar's Part A item (A4.2) also needs.

---

## 0 · Close your Phase 2 items — Day 0/1

- [x] **A5.1 — `/plume/simulate` wired to the real particle engine.** Confirmed
      live: `POST /api/v1/plume/simulate` returns `"is_stub": false`,
      `"model_version": "custom_2d-calibrated-AQ-2016-10-28"`, 24 real contours.
      **One real, currently-live caveat, not a fabricated concern:** the response's
      own `caveats` field says the engine is running on
      `PLACEHOLDER: ConstantCurrentField(0, 0)` and `ConstantWindField(0, 0)` because
      `hycom_aoi_AQ-2016-10-28.nc` is absent from the container. The engine is real;
      the forcing feeding it right now is not. This is the exact same missing
      `.nc` cache Nizar's A4.2 needs re-fetched for the HYCOM-vs-Copernicus
      comparison — coordinate with him so this is one re-fetch effort, not two.
      - [ ] Confirm with Nizar whether re-fetching the currents cache for A4.2 also
            resolves this, or whether the plume engine needs its own separate
            historical wind source (his file notes "no historical marine wind
            source exists in this repo" — GFS/GEFS/ECMWF here are forecast-only).
            If a real historical wind source genuinely doesn't exist, say so in
            `docs/forcing_limitations.md` rather than leaving the constant-zero
            placeholder unexplained anywhere outside the API's own caveat string.
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

## 1 · Your role in B1 — Automated Plume Segmentation Model (primary: Mahdi, [`02-mahdi.md`](02-mahdi.md))

Mahdi's model needs a labelled mask library to train on. That library is your domain.

- [ ] Confirm exactly how many real, human-reviewed plume masks currently exist in
      `data/processed/plume/masks/` (per the fixed schema Mahdi is defining this
      phase) — this number directly determines whether B1 ships as a genuinely
      trained model or as plumbing waiting on more masks. Report the real count, not
      an estimate.
- [ ] If the count is small (likely, given one demo event is fully worked), flag
      this explicitly to Mahdi and Ali so B1's dashboard doesn't imply a
      well-trained segmenter when the training set is a handful of masks.

---

## Definition of done

1. A5.1's forcing-placeholder caveat is either resolved (real currents/wind cache
   fetched) or explicitly and permanently documented in `docs/forcing_limitations.md`
   as a known, named limitation — not left as an API-only caveat string nobody reads.
2. If real forcing lands, the calibration grid search is re-run and the new winner
   (if different) replaces the current tie-break-flagged one.
3. B1's real mask count is reported to Mahdi and Ali before either builds dashboard
   copy implying a specific level of training maturity.

---

## Handoffs

| Teammate | What they get | When |
|---|---|---|
| **Mahdi** | Real plume-mask count and schema confirmation for B1 | Day 2 |
| **Nizar** | Confirmation of whether one currents/wind re-fetch effort serves both A4.2 and A5.1 | Day 1 |

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Nizar** | Re-fetched `.nc` current cache files, if the joint re-fetch is feasible this phase | No — the engine already runs correctly on placeholder forcing and says so; this is an accuracy improvement, not a blocker to demoing |
