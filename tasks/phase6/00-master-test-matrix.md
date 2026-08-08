# Phase 6 — Master Test Matrix

Filled in only by the person who personally ran the check. `PASS` / `FAIL` /
`BLOCKED-NOT-BUILT` — no other values. Every non-empty verdict must link a real
evidence file under `tasks/phase6/evidence/<feature-id>/`. See
[`00-phase6-plan.md`](00-phase6-plan.md) for the rules; this file contains no fix
instructions, only rows.

## Core (5 rows)

| ID | Feature | Owner | Tester | Verdict | Evidence | Notes |
|---|---|---|---|---|---|---|
| core-A | Runoff classifier | Mahdi | Mahdi | — | — | |
| core-B | Sediment proxy (anchor) | Mahdi | Mahdi | — | — | |
| core-C | Plume / particle engine | Abd | Abd | **PASS** | `evidence/core-c/plume_simulate.json` | Live-checked today against a freshly built `reefshield-api-1` container (`docker compose up --build`, not the dev server) — not re-quoting the 6 Aug check. `is_stub: false`, real HYCOM currents (`GLBu0.08/expt_91.2` historical archive, cached `.nc`), 24 real contours, `AQ-2016-10-28`/`AQ-O02`. |
| core-D | Exposure engine | Pulga | Pulga | **PASS** | `evidence/core-d/exposure_calculate.json`, `evidence/core-d/pytest_run_raw.txt`, `evidence/core-d/full_suite_raw.txt` | See 04-pulga.md |
| core-E | Explanation + Retrieval (RAG) | Pulga | Pulga | **PASS** | `evidence/core-e/explain_and_ask.json`, `evidence/core-e/pytest.txt` | See 04-pulga.md |

## Phase 4 (30 rows)

| ID | Feature | Primary | Also needs | Tester(s) | Verdict | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| p4-01 | Storm Replay Mode | Abd | Ali | Abd, Ali | **PASS (backend)** | `evidence/p4-01/plume_map_frames.json` | The replay's own frame list (`/plume/map/frames`) reports `plume_source: particle-engine` across all 6 real timesteps for `AQ-2016-10-28`/`AQ-O02`; one rendered frame's response headers independently confirm it (`x-reefshield-plume-source: particle-engine`, real baked imagery, no generated imagery). Checked against the freshly built container, today. Frontend half is Ali's. |
| p4-02 | Live Forecast Mode | Nizar | Ali | Nizar, Ali | — | — | |
| p4-03 | 8-Hour Countdown | Ali | — | Ali | — | — | |
| p4-04 | Top Weather Drivers Explainer | Mahdi | Pulga, Ali | Mahdi, Pulga, Ali | **FAIL (Pulga's piece)** | `evidence/p4-04/runoff_predict_real_drivers.json`, `evidence/p4-04/explain_with_unrenamed_key_field_500.json`, `evidence/p4-04/explain_with_real_driver_names.json` | Real drivers exist (Mahdi's half real); never threaded into `/explain`, and driver names don't match `DRIVER_PHRASE`'s vocabulary even if threaded manually. See 04-pulga.md |
| p4-05 | Confidence Meter | Karam | Nizar | Karam, Nizar | **PASS (Karam's threshold half)** | `evidence/p4-05/exposure_calculate_confidence.json` | Tested live against a freshly built container. `confidence_adjustment: 0.8`, `confidence_adjustment_reason` cites real, named values: "0/30 GEFS members exceed the 2.35 mm/24h threshold (catchment_rainfall_climatology p99, window_hours=24, imerg_v07_final) -> agreement 1.00, x0.8 for coarse global current model + GMRT-substituted bathymetry" — not a placeholder constant. Components (`confidence_members_exceeding/_total/_threshold_value_mm`) present on `formula_terms`. Nizar's ensemble-agreement-formula sign-off is a separate, still-open question (flagged in tasks/phase4/01-karam.md) — not re-litigated here. |
| p4-06 | Bilingual Assistant | (done) | — | Ali | — | — | |
| p4-07 | What-If Scenario Presets | Pulga | Ali | Pulga (backend), Ali (frontend) | **PASS (backend)** | `evidence/p4-07/rainfall_multiplier_and_transmission_loss.json` | Backend contract only — frontend half is Ali's |
| p4-08 | Rain Intensity Ranking | Karam | Ali | Karam, Ali | **PASS (backend)** | `evidence/p4-08/events_ranking_check.txt` | `GET /api/v1/events` live-checked: 675/675 events carry a real `rank`, 675 unique values, sorted ascending, rank 1 has the true max `max_daily_mm` (21.55mm) — not all-equal, not alphabetical. Demo event `AQ-2016-10-28` ranks 13th. `scripts/rank_events_by_intensity.py`'s own output (`events_by_intensity.parquet`) was NOT used as evidence — it's a known-stale artifact built against an old 100-event catalogue (documented in tasks/phase4/01-karam.md), so the live API ranking is the honest thing to test instead. Frontend half is Ali's. |
| p4-09 | "AI Never Saw This Storm" | Mahdi | — | Mahdi | — | — | |
| p4-10 | Real Sensor Proof Overlay | Abd | Pulga, Ali | Abd, Pulga (backend), Ali | **PASS (backend + file-level)** | `evidence/p4-10/mooring_endpoint.json` (Pulga, API), `evidence/p4-10/mooring_target_file_level.json`, `evidence/p4-10/pdf_cross_check.txt` (Abd, file-level) | Backend read-through: Pulga's piece. File-level (Abd), independent of the API: `mooring_target_AQ-2016-10-28.json` and its cited Kalman et al. 2025 PDF are both real; 4 of 5 reported magnitude fields directly text-confirmed inside the actual PDF (e.g. "2.18 g l⁻¹", "38.75 ‰", verbatim). **One finding, not fixed:** `sediment_mass_total_t: 24400` could not be found anywhere in the cited PDF's extracted text (plain or `-layout` mode), despite `docs/event_dates.md` attributing this exact figure to "mooring time series, Kalman et al. (2025)". Plausibly a table/figure value `pdftotext` can't extract, but not confirmed either way — flagged for a Phase 7 follow-up, not re-derived here. |
| p4-11 | Simple Guess vs Smart Guess | Ali | — | Ali | — | — | |
| p4-12 | Click-to-See-Why | Ali | — | Ali | — | — | |
| p4-13 | Honest Limits Page | (done) | — | Ali | — | — | |
| p4-14 | 3D Journey | Ali | Abd | Ali, Abd | **PASS (plume portion, Abd's piece)** | `evidence/p4-14/journey3d-transport.png`, `evidence/p4-14/journey3d-accumulation.png`, `evidence/p4-14/fixture_real_data_fields.json`, `evidence/p4-14/verdict_notes.txt`, `evidence/p4-14/playwright_run.txt` | Plume-cloud portion driven by real particle-engine output where present — the committed fixture's `is_stub`/`model_version`/`plume_source` fields match today's fresh core-C check field-for-field, and the on-screen caption carries the real current-masking caveat verbatim. The true volumetric per-particle 3D cloud is correctly `BLOCKED-NOT-BUILT` (no route serves raw particle positions, re-confirmed today) and the UI states this rather than faking it. Fresh Playwright run: 6/6 passed. Ali's terrain/buildings/camera piece is untested by this pass. |
| p4-15 | Judge-Controlled Slider | Pulga | Ali | Pulga (backend), Ali (frontend) | **PASS (backend)** | `evidence/p4-15/rainfall_multiplier_and_transmission_loss.json` | Same backend contract as p4-07 |
| p4-16 | Rainfall Accumulation Chart | Ali | Karam | Ali, Karam | **PASS (data half)** | `evidence/p4-16/rainfall_daily_fixture_check.txt` | `frontend/public/fixtures/event.json`'s `rainfall_daily` block traced to source: `scripts/frontend_event_series.py` reads `data/processed/features/catchment_rainfall_daily.parquet` directly (fixture's own `source`/`provenance` fields say the same). Real, differentiated per-catchment daily series for the Oct 2016 window confirmed (e.g. AQ-C01 1.88/9.58/6.44/0.0 mm across four consecutive days) — not a static stub. This is a real-data fixture, not a live endpoint, which is this project's documented, intentional architecture (◐/● indicator) — not the same thing as fabricated. Frontend-renders-it half is Ali's. |
| p4-17 | The Gap Chart | Ali | — | Ali | — | — | |
| p4-18 | Toughest Coral Fact | Ali | — | Ali | — | — | |
| p4-19 | One-Line Mission Statement | (done) | — | Ali | — | — | |
| p4-A | Named Reef Zone Priority List | Ali | Pulga | Ali (frontend), Pulga (backend data) | **PASS (backend)** | `evidence/p4-A/alerts_sorted.json` | `/alerts` sort + real data only |
| p4-B | Dive Site Safety Status | Karam | Pulga, Ali | Karam, Pulga, Ali | **PASS (Pulga's piece)** | `evidence/p4-B/dive_sites.json` | 46 real POIs, real nearest-zone join, honest distance caveats on implausible ones. See 04-pulga.md |
| p4-C | Transmission Loss Reality Check | Mahdi | Pulga, Ali | Mahdi, Pulga (backend), Ali | **PASS (backend)** | `evidence/p4-C/transmission_loss_echo.json` | `transmission_loss_override` echo only |
| p4-D | Culvert & Drainage Correction Map | Mahdi | Ali | Mahdi, Ali | — | — | |
| p4-E | Enclosed Harbor Warning Flag | (done) | Ali (verify) | Ali | — | — | |
| p4-F | Multi-Source Weather Agreement | Nizar | Ali | Nizar, Ali | **FAIL** | `evidence/p4-F/currents_agreement.txt` | `GET /api/v1/currents/agreement` returns a bare HTTP 500 on a freshly built container — never reaches the documented 65.8° disagreement figure. Root cause (full traceback in evidence): `main.py`'s `currents_agreement()` checks `hycom_path.exists()` and 503s cleanly if absent, but has no matching check for `copernicus_path` before calling `compare_hycom_vs_copernicus()` — only the HYCOM cache exists on disk (Copernicus Marine credentials were never configured), so the missing file reaches `xr.open_dataset()` unchecked and crashes. Not fixed, per this phase's rule 1. Tested by Karam (row's "also needs" partner), not Nizar himself — Nizar should confirm/add his own run since this is nominally his row. |
| p4-G | Historical Event Search | Karam | Ali | Karam, Ali | **PASS (backend)** | `evidence/p4-G/search_both_cases.txt` | `GET /api/v1/events/AQ-2016-10-28` returns 200 with full real data (rank 13, real ranking fields, literature label). `GET /api/v1/events/AQ-9999-01-01` returns a clean 404 (`"unknown event AQ-9999-01-01"`) — an honest empty result, not a fabricated hit. No dedicated search UI/endpoint exists yet; tested the lookup mechanism a search feature would call. Frontend half is Ali's. |
| p4-H | Offline Emergency Mode | Mahdi | Ali | Mahdi, Ali | — | — | |
| p4-I | Coastal Zone Risk Comparison | Ali | Pulga | Ali (frontend), Pulga (backend data) | **PASS (backend)** | `evidence/p4-I/exposure_multi_zone.json` | Finding: only 2 of 5 outlets ever reach a zone, and each reaches exactly one — a comparison view needs the frontend to call all 5 outlets, `/alerts` alone won't produce a multi-zone table. See 04-pulga.md |
| p4-J | Post-Storm Damage Estimate | Mahdi | Ali | Mahdi, Ali | — | — | |
| p4-K | Seasonal Risk Calendar | Karam | Ali | Karam, Ali | **PASS (data half)** | `evidence/p4-K/seasonal_calendar_data_trace.txt` | `data/processed/features/seasonal_risk_calendar.parquet` inspected directly: 12 real months, real event counts (6 to 121) and real per-month max/mean `max_daily_mm`, each `worst_event_id` a real event. Built from `events.parquet` (all 675 events, per-month groupby), not `catchment_rainfall_climatology.parquet` as this row's own task description assumed — that file is a 5-row percentile summary with no month dimension at all, so it couldn't have been the source; noting the discrepancy rather than silently testing against the wrong assumption. Winter-wet pattern visible and physically sensible (Dec-Mar highest counts, Jun-Aug near zero) — not hand-picked labels. Frontend half is Ali's. |

## Phase 5 (9 rows)

| ID | Feature | Owner | Tester | Verdict | Evidence | Notes |
|---|---|---|---|---|---|---|
| b1 | Automated Plume Segmentation Model | Mahdi | Mahdi | — | — | |
| b2 | Learned Transmission-Loss Model | Mahdi | Mahdi | — | — | |
| b3 | Cross-Site Transfer Learning | Mahdi | Mahdi | — | — | |
| b4 | Automated Site-Scoring Agent | Pulga | Pulga | **PASS** | `evidence/core-d/pytest_run_raw.txt` (covers `test_sites_score.py`), `evidence/b4/sites_score.json`, `evidence/b4/sites_score_far_away.json` | See 04-pulga.md |
| b5 | Post-Event Forensic Report Generator | Pulga | Pulga | **PASS** | `evidence/b5/reports_generate.json`, `evidence/b5/reports_review.json` | See 04-pulga.md |
| b6 | Live Anomaly Detection on Forecast Streams | Nizar | Nizar | — | — | |
| b7 | Adaptive Sampling Recommender | Pulga | Pulga | **PASS (infrastructure)** | `evidence/b7/calc_before_feedback.json`, `evidence/b7/calc_after_feedback.json` | Explicitly infra-only per its own spec — not a demoable capability yet, see notes in 04-pulga.md |
| b8 | Coral Health Vision Model | Pulga | Pulga | **PASS** | `evidence/b8/photos_get.json`, `evidence/b8/exposure_before_approval.json`, `evidence/b8/approve_response.json`, `evidence/b8/exposure_after_approval.json` | Sensitivity-weight gate re-confirmed live end to end; see 04-pulga.md |
| b9 | Automated Culvert/Drainage-Conflict Detector | Mahdi | Mahdi | — | — | |

## Tally

Filled in once every row has a verdict — do not pre-fill this before the rows below
it are real.

| State | Count |
|---|---|
| PASS (fully, both halves) | 0 |
| PASS (backend/data half only, or one owner's piece only — the other half/piece still open) | 13 — `p4-01` (Ali's frontend half open), `p4-05` (Nizar's ensemble-formula sign-off open), `p4-07`, `p4-08` (Ali's frontend half open), `p4-10` (Ali's frontend half open), `p4-14` (Ali's terrain/buildings/camera piece open), `p4-15`, `p4-16` (Ali's frontend half open), `p4-A`, `p4-C`, `p4-G` (Ali's frontend half open), `p4-I`, `p4-K` (Ali's frontend half open) |
| PASS (no separate frontend half) | 8 — `core-C`, `core-D`, `core-E`, `b4`, `b5`, `b7` (infrastructure), `b8`, `p4-B` (Pulga's piece) |
| FAIL | 2 — `p4-04` (Pulga's piece: real driver data exists, never wired into `/explain`, and the driver-name vocabulary doesn't match even if it were), `p4-F` (bare HTTP 500, missing-file check absent for the Copernicus Marine path) |
| BLOCKED-NOT-BUILT | 0 |
| Untested (blank) | 21 — every row not listed above |

44 rows total. 23 carry a recorded verdict so far — 14 from Pulga's pass, 3 from Abd's
pass (`core-C`, `p4-01`, `p4-14` newly recorded; `p4-10` enriched with an independent
file-level check alongside Pulga's existing API-level one, not double counted), and 6
from Karam's pass this session (`p4-05`, `p4-08`, `p4-16`, `p4-G`, `p4-K` — all PASS on
the backend/data half tested; `p4-F` — FAIL, a real bug found and left unfixed per this
phase's own rule). Every other row, the Mahdi/Ali sides of `p4-04`, and Ali's remaining
halves of `p4-01`/`p4-05`/`p4-08`/`p4-10`/`p4-14`/`p4-16`/`p4-G`/`p4-K`, are genuinely
untested as of this pass — do not read a blank row as a pass, a fail, or as "the
earlier phase's ✅ still holds." It means exactly one thing: nobody has personally run
the check yet.
