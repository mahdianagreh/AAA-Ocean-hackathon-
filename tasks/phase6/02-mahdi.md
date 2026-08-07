# Phase 6 — Mahdi's testing assignment

Read [`00-phase6-plan.md`](00-phase6-plan.md) first. This file contains **no fix, build,
wire, or repoint instructions** — only what to run and where to record the result. If
something fails, write `FAIL` with evidence and move on; do not fix it in this pass.

Record every verdict directly in [`00-master-test-matrix.md`](00-master-test-matrix.md)
and save evidence under `tasks/phase6/evidence/<id>/`.

| ID | Feature | What to run | Evidence to save |
|---|---|---|---|
| core-A | Runoff classifier | Load the trained model, run it against the temporal holdout set (train ≤2014), confirm the recorded AP (0.662, IMERG+neutral only, no ERA5) is reproducible from the current `model_versions.jsonl` entry, not just quoted in docs. | Reproduction script output |
| core-B | Sediment proxy (anchor) | Confirm `relative_sediment_intensity` for the anchor event is non-zero and traces to `data/models/sediment_anchor.json`'s real 24,400 t anchor, via a live `/exposure/calculate` call's `formula_terms`. | Curl output |
| b1 | Automated Plume Segmentation Model | Run the segmentation model against a real plume input; confirm output masks are flagged for human review (per its own spec — auto-masks are never presented as final) rather than silently trusted. | Model output + flag field |
| b2 | Learned Transmission-Loss Model | Confirm the learned per-catchment estimate is labelled which model produced it (vs. the borrowed Negev 20-85% range), live, in an actual `/exposure/calculate` or `/runoff/predict` response. | Curl output showing the label |
| b3 | Cross-Site Transfer Learning | Confirm the maturity badge appears and is honest (does not claim Aqaba-level validation for a new site with thin data). | API/response evidence |
| b9 | Automated Culvert/Drainage-Conflict Detector | Run the detector against the real OSM/DEM inputs; confirm it reproduces at least the 27 real culverts already found manually (per Phase 4 row D), not a smaller or fabricated count. | Detector output |
| p4-04 | Top Weather Drivers Explainer | Confirm the explainer names real weather-driver features (not placeholder text) for a real event, cross-checked against Pulga's explanation endpoint. | Curl/response |
| p4-09 | "AI Never Saw This Storm" | Confirm the flagged out-of-distribution storms are real (traced to the label-blind-spot analysis in the root `CLAUDE.md`'s label rule section — ERA5 misses on IMERG-heavy days), not arbitrarily chosen. | Data trace |
| p4-C | Transmission Loss Reality Check | Confirm the "reality check" framing (borrowed Negev range vs. any learned value) is presented honestly, live. Pulga covers the backend echo half separately (`p4-C` backend note already `PASS` in the matrix). | Screenshot or response |
| p4-D | Culvert & Drainage Correction Map | Re-verify the map still shows the same real culvert count/positions as originally verified in Phase 4 — a regression check, not a rebuild. | Map data / screenshot |
| p4-H | Offline Emergency Mode | Confirm the frozen "today" offline snapshot (A4.3) actually serves the app with wifi off; this is a re-run of the same wifi-off test named in `tasks/phase5/00-phase5-plan.md`'s A2.5/A6.2 rows, not a new test. | Test run log |
| p4-J | Post-Storm Damage Estimate | Confirm the feature reports a class (Low/Medium/High/Extreme), never a tonnage number for a non-anchor event — per the explicit correction in `tasks/phase4/00-phase4-plan.md` item 2. A tonnage number anywhere here is an automatic `FAIL`. | Response body |

## Definition of done for this file

Every row above has a `PASS`/`FAIL`/`BLOCKED-NOT-BUILT` verdict in the master matrix,
each with a linked evidence file, recorded by you running the real check — not
transcribed from `tasks/phase4/02-mahdi.md` or `tasks/phase5/02-mahdi.md`'s prior claims.
