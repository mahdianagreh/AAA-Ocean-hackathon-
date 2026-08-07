# Phase 6 — Nizar's testing assignment

Read [`00-phase6-plan.md`](00-phase6-plan.md) first. This file contains **no fix, build,
wire, or repoint instructions** — only what to run and where to record the result. If
something fails, write `FAIL` with evidence and move on; do not fix it in this pass.

Record every verdict directly in [`00-master-test-matrix.md`](00-master-test-matrix.md)
and save evidence under `tasks/phase6/evidence/<id>/`.

| ID | Feature | What to run | Evidence to save |
|---|---|---|---|
| p4-02 | Live Forecast Mode | Hit the live forecast endpoint against a real current forecast pull (GFS/GEFS); confirm it is not silently serving the frozen A4.3 offline snapshot when it should be live. Ali confirms the frontend switches correctly between modes. | Curl output, timestamp check |
| p4-F | Multi-Source Weather Agreement | Independently re-run `GET /api/v1/currents/agreement` (same check as Karam's p4-F row) and confirm it reproduces the documented 65.8° disagreement for the mooring peak-response time. Two independent runs on this row is deliberate — currents-vs-marine-model agreement is exactly the kind of number that should not depend on who ran it. | Curl output |
| b6 | Live Anomaly Detection on Forecast Streams | Feed a real anomalous forecast pattern through the detector; confirm it fires as a distinct, separately labelled signal and is never conflated with or overwrites the formal confidence meter's number (p4-05). Also confirm it stays silent on a normal forecast (no false-positive-by-default). | Detector output, both cases |

## Definition of done for this file

Every row above has a `PASS`/`FAIL`/`BLOCKED-NOT-BUILT` verdict in the master matrix,
each with a linked evidence file, recorded by you running the real check — not
transcribed from `tasks/phase4/03-nizar.md` or `tasks/phase5/03-nizar.md`'s prior claims.
