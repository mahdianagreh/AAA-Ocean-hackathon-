# Phase 6 — Karam's testing assignment

Read [`00-phase6-plan.md`](00-phase6-plan.md) first. This file contains **no fix, build,
wire, or repoint instructions** — only what to run and where to record the result. If
something fails, write `FAIL` with evidence and move on; do not fix it in this pass.

Rows below are yours because you own the underlying pipeline or contributed the
"also needs" half. Record every verdict directly in
[`00-master-test-matrix.md`](00-master-test-matrix.md) and save evidence under
`tasks/phase6/evidence/<id>/`.

| ID | Feature | What to run | Evidence to save |
|---|---|---|---|
| p4-05 | Confidence Meter | Hit the live confidence endpoint/field for the anchor event; confirm the number is real (traceable to a named source) and not a placeholder constant. Cross-check with Nizar on the "also needs" half. | Curl/response body |
| p4-08 | Rain Intensity Ranking | Run `python scripts/rank_events_by_intensity.py` (or hit its API surface if wired) against the real IMERG-derived event catalogue; confirm ranking is non-trivial (not all-equal, not alphabetical). | Script/API output |
| p4-16 | Rainfall Accumulation Chart | Confirm the chart's backing endpoint/data file returns real per-catchment accumulation series, not a static stub. Ali confirms the frontend renders it. | Data file / endpoint response |
| p4-G | Historical Event Search | Query the events catalogue for a known real event (`AQ-2016-10-28`) and a known-absent one; confirm the search returns real matches and an honest empty result, not a fabricated hit. | Query output, both cases |
| p4-K | Seasonal Risk Calendar | Confirm the calendar is built from `catchment_rainfall_climatology.parquet`'s real monthly/seasonal aggregates, not hand-picked labels. | Data trace |
| p4-F | Multi-Source Weather Agreement | Hit `GET /api/v1/currents/agreement`; confirm it reproduces the documented 65.8° disagreement for the demo event's mooring peak-response time (per Nizar's 7 Aug note in `tasks/phase4/00-phase4-plan.md`). | Curl output |

## Definition of done for this file

Every row above has a `PASS`/`FAIL`/`BLOCKED-NOT-BUILT` verdict in the master matrix,
each with a linked evidence file, recorded by you running the real check — not
transcribed from `tasks/phase4/01-karam.md`'s prior claims.
