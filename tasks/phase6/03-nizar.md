# Phase 6 — Nizar's testing assignment

> **Note from Karam, 8 Aug — p4-F already has a recorded FAIL, left unfixed on
> purpose (this phase's own rule).** Ran it live against a freshly built
> container: `GET /api/v1/currents/agreement` returns a bare HTTP 500, never
> reaches the 65.8° figure. Full traceback in
> `evidence/p4-F/currents_agreement.txt`. For whoever picks this up in Phase 7
> — not doing it now, just naming it precisely: `main.py`'s
> `currents_agreement()` (around line 787) checks `hycom_path.exists()` and
> returns a clean 503 if it's missing, but has no matching check for
> `copernicus_path` before calling `oc.compare_hycom_vs_copernicus()` — only
> the HYCOM cache exists on disk, Copernicus Marine credentials were never
> configured. The fix is presumably either (a) fetch/cache the Copernicus
> Marine side too, once credentials exist, or (b) add the same
> exists-or-503 guard for `copernicus_path` that already exists for
> `hycom_path`, so the endpoint degrades honestly instead of crashing — that's
> a real design choice, not mine to make. Your independent re-run below should
> still happen for real, not be skipped because a FAIL is already on record —
> the point of two testers on this row is that it doesn't depend on who ran it.

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

---

## Closed, 2026-08-08 — all three rows personally re-run against a fresh container

- **`p4-02` — PASS (backend), with a real finding.** `/forecast/latest` correctly
  never makes a live network call (confirmed architecture, not a defect). But the
  snapshot it serves (`issued_at: 2026-08-03`) is stale against Postgres's newest
  GFS pull (`gfs_2026-08-07T06Z`) — nobody re-ran `build_forecast_snapshot.py` since.
  Named, not fixed, per this phase's rule. Evidence: `evidence/p4-02/`.
- **`p4-F` — FAIL, confirmed independently, with the "who ran it" question actually
  answered.** My machine initially returned HTTP 200 (the Copernicus `.nc` cache
  happens to already be present here from A4.2 work) — the opposite of Karam's 500.
  Moved that file aside on the same running container and reproduced his exact
  crash, then restored it. This is the real finding: the row's correctness is
  presently contingent on which teammate's git-ignored local cache is populated,
  not on the code being correct — kept as FAIL. Evidence: `evidence/p4-F-nizar/`.
- **`b6` — PASS.** Fed the real Oct 2016 event's IMERG rain value at `AQ-C01`
  through the live detector against real climatology — fires distinctly. Fed a
  real current (non-event) forecast value through the same climatology — stays
  silent. Confirmed `/forecast/latest`'s anomaly fields and `/exposure/calculate`'s
  confidence fields (`p4-05`) share zero field names — conflation is structurally
  impossible. Evidence: `evidence/b6/`.
- **Bonus: `p4-05`'s previously-open half closed too.** Re-derived the confidence
  formula by hand from a fresh run (`agreement = |0-0.5|*2 = 1.0`,
  `confidence_adjustment = 1.0*0.8 = 0.8`) — matches the live response exactly.
  Row moves from partial to fully `PASS`. Evidence: `evidence/p4-05-nizar/`.

## Bonus, 2026-08-08 — browser-automated a chunk of Ali's frontend-half backlog

Not my assigned rows, but I have Chrome automation tooling and the matrix had 13 rows
sitting on "backend PASS, frontend half open." Real findings, not shallow re-clicks:

- **`p4-14` (3D Journey)**: ran the repo's own `frontend/tests/journey3d.spec.ts` against
  a freshly built frontend+API. 3 of 5 real-terrain assertions **FAIL** — terrain
  mesh/imagery draping, rain/runoff pixel rendering (0 pixels), and the reef-reveal paint
  property never changing. Real, reproducible frontend defect. Evidence:
  `evidence/p4-14-nizar/`.
- **`p4-07`/`p4-15` (What-If sliders)**: dragged the real Rainfall slider live in the
  browser, confirmed via network tracking that zero calls reach the API — matches the
  drawer's own honest on-screen label ("stand-in index, not model output"). Confirms
  `tasks/phase4/00-phase4-plan.md`'s A3.4 gap is still open. Evidence:
  `evidence/p4-07-nizar/`.
- **Architecture note for whoever tests the remaining frontend rows**: `VITE_DATA_SOURCE`
  defaults to `fixtures` and `docker-compose.yml` never overrides it, so
  catchments/outlets/reefZones/health never go live via the standard `--profile frontend
  up` path. `exposure`/`plume-frames`/`alerts` (`frontend/src/api/live.ts`) are NOT gated
  by that flag and always attempt a real call regardless — the two need to be checked
  separately per panel, not assumed from the masthead's fixtures/live badge.
- **Stopped here deliberately.** The remaining ~9 blank Ali-only rows (8-Hour Countdown,
  Click-to-See-Why, etc.) aren't covered by the existing Playwright suite and I don't have
  Ali's context on exactly where each lives in the component tree — pushing further risked
  producing exactly the shallow "I think I checked it" verdict this phase exists to
  eliminate. Left genuinely blank for Ali rather than guessed at.
