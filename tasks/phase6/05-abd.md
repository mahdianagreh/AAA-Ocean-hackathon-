# Phase 6 — Abd's testing assignment

Read [`00-phase6-plan.md`](00-phase6-plan.md) first. This file contains **no fix, build,
wire, or repoint instructions** — only what to run and where to record the result. If
something fails, write `FAIL` with evidence and move on; do not fix it in this pass.

Record every verdict directly in [`00-master-test-matrix.md`](00-master-test-matrix.md)
and save evidence under `tasks/phase6/evidence/<id>/`.

| ID | Feature | What to run | Evidence to save |
|---|---|---|---|
| core-C | Plume / particle engine | `POST /plume/simulate` for the anchor event; confirm `is_stub: false` and real HYCOM-derived currents drive the output (per the 6 Aug correction already on record in `tasks/phase4/00-phase4-plan.md`). Re-confirming this, live, today, not re-quoting the 6 Aug check. | Curl output |
| p4-01 | Storm Replay Mode | Replay the anchor event end to end through `/plume/simulate`; confirm the replay is driven by the real particle engine (same as core-C), not the placeholder zero-current/zero-wind forcing noted as a caveat in `tasks/phase5/00-phase5-plan.md` A5.1. If forcing is still placeholder, that is a `FAIL` for "real," not a blocker — record it exactly as observed. | Curl output |
| p4-10 | Real Sensor Proof Overlay (sensor side) | Confirm the mooring time-series data (Kalman et al. 2025, salinity/turbidity) that this overlay is supposed to show is real and retrievable, independent of Pulga's `/mooring` endpoint test — verify at the data-file level (`data/processed/...` mooring parquet/csv), not just via the API. | File-level check output |
| p4-14 | 3D Journey (plume portion) | Confirm the plume-cloud portion of the 3D Journey (previously deferred per `tasks/phase4/00-phase4-plan.md` row 14) is driven by real particle-engine output where present, and explicitly `BLOCKED-NOT-BUILT` (not silently faked) where it is still deferred. | Screenshot / data trace |

## Definition of done for this file

Every row above has a `PASS`/`FAIL`/`BLOCKED-NOT-BUILT` verdict in the master matrix,
each with a linked evidence file, recorded by you running the real check — not
transcribed from `tasks/phase4/05-abd.md` or `tasks/phase5/05-abd.md`'s prior claims.
