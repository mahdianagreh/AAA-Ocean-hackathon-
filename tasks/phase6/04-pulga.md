# Phase 6 — Pulga's testing results

Read [`00-phase6-plan.md`](00-phase6-plan.md) first. Everything below is a **test
result**, recorded after running the check against the real, running
`reefshield-api-1` container (not against source code, not transcribed from
`tasks/phase4/04-pulga.md` or `tasks/phase5/04-pulga.md`'s prior claims) on 7 Aug 2026.
Nothing in this file is a fix — where a real gap was found (see §"Findings worth
flagging" at the end), it is written down, not patched.

All evidence files are under `tasks/phase6/evidence/<id>/`. Container was
`docker ps`-confirmed healthy throughout; restarted once mid-session solely to clear
the in-process `lru_cache` after test cleanup, per the plan's own rule 3.

---

## core-D — Exposure engine

**Verdict: PASS**

- `pytest -q` — full suite: **545 passed, 47 skipped, 1 xfailed** (`evidence/core-d/full_suite_raw.txt`). The 47 skips are all git-ignored raw data absent (IMERG granules, baked basemap, SoilGrids), each skip naming its own script — matches the documented baseline in the root `CLAUDE.md`.
- The five exposure/scenario-specific test files (54 tests) green in isolation: `evidence/core-d/pytest_run_raw.txt`.
- Live `POST /exposure/calculate` for the anchor event (`AQ-2016-10-28`, `AQ-O02`): real `formula_terms` with 24 real keys, `measure_crs: "EPSG:32636"` (rule 8 compliance, confirmed live not just by test), `transmission_loss: 0.525` present and non-null (the A3.4 echo fix, confirmed live). `run_id` is a real `sim_{ULID}`. Full response: `evidence/core-d/exposure_calculate.json`.
- `adjusted_priority == risk_score` exactly with `NO_FEEDBACK_YET` on a fresh run — the B7 fallback default, confirmed live against the real persistent store, not just the test DB.

## core-E — Explanation + Retrieval (RAG)

**Verdict: PASS**

- `pytest -q tests/test_ask_citations.py tests/test_explain_ask_adversarial.py` — **15 passed, 1 xfailed** (`evidence/core-e/pytest.txt`).
- Live `POST /explain`: passed real driver values (`rainfall_3h_mm=41.2`, etc.) and got back a template-phrased paragraph whose `source_numbers` echo the inputs verbatim, `generator: "deterministic_template"`, and an explicit caveat that numbers are "never recomputed or rounded by the phrasing layer" — confirms rule 12 (LLM phrases, never computes) live, not just in the module docstring.
- Live `POST /ask` (two real questions, harbour exclusion and `AQ-O04`): both returned real citations with `source_file`/`section`/`excerpt`/`score`, `corpus_files_searched: 12`. No `docs/ali/*` citation appeared in either response (rule 11 spot-check).
- Full combined evidence: `evidence/core-e/explain_and_ask.json`.

## b4 — Automated Site-Scoring Agent

**Verdict: PASS**

- `pytest -q` (included in the core-D run above) covers `test_sites_score.py` and `test_site_id_contract.py` — all green.
- Live `POST /sites/score` for a real Aqaba box: `site_id` starts `site_`, C1/C3/C5 genuinely scored with real citations, C6 correctly `insufficient_data` (no dataset can prove absence of other monitoring — by design, everywhere). `evidence/b4/sites_score.json`.
- Live scoring of a mid-Atlantic box with zero real coverage: C1/C2/C4/C5 correctly report `insufficient_data`/`score: null`, never a guessed number. `evidence/b4/sites_score_far_away.json`.
- The "validated on exactly one site" caveat is present in both responses.

## b5 — Post-Event Forensic Report Generator

**Verdict: PASS**

- Live `POST /reports/generate` for the anchor event: every claim's `source` is a real, traceable pointer — `exposure_run:sim_...#R-08`, `docs/data_dictionary.md §4`, the full Kalman et al. (2025) citation, `docs/event_dates.md#Canonical event ID`. Report starts `status: "ai_drafted"`.
- Live `PATCH /reports/{id}/review`: flips status to `"human_reviewed"` — confirmed this is the only path that can do so (grepped `generated_reports.py`; no other write site sets that string).
- Full evidence: `evidence/b5/reports_generate.json`, `evidence/b5/reports_review.json`.

## b7 — Adaptive Sampling Recommender

**Verdict: PASS (infrastructure — not a demoable capability yet, by its own spec)**

- Live, on the real persistent store (not the test DB): a fresh calculation for `R-08` showed `adjusted_priority == risk_score` exactly, `NO_FEEDBACK_YET` (`evidence/b7/calc_before_feedback.json`).
- Posted 5 real feedback rows against that run (3 `confirmed`, 2 `not_confirmed` — 60% accuracy) via `POST /reef-zones/R-08/feedback`, all `HTTP 200`.
- Re-calculated: `risk_score=1.8304`, `adjusted_priority=1.0982`, `status=FEEDBACK_APPLIED`. `1.8304 × 0.6 = 1.0982` exactly — the blending is real, live, and bounded (never inflates past `risk_score`). `evidence/b7/calc_after_feedback.json`.
- The 5 feedback rows used to produce this were synthetic (mine, for this test) — real deployment history still doesn't exist, which is exactly why this row is "infrastructure," not "demoable," per its own spec in `tasks/phase5/00-phase5-plan.md`. Recording that honestly rather than upgrading the verdict.
- Test rows deleted from the live store after verification; see §"Cleanup" below.

## b8 — Coral Health Vision Model + the sensitivity-weight gate

**Verdict: PASS**

This is the safety-critical row — the one place a model output is allowed to move a
number that changes `risk_score`. Tested the full chain live, not just via `pytest`:

1. Uploaded 3 real (test-generated, pale/low-texture) JPEGs to `R-08` via `POST /reef-zones/R-08/photos`. All classified `"bleached"`, `confidence: 0.55`, `model_basis: "heuristic_rule_v1"` — consistent with the documented heuristic (pale + low edge density → bleached).
2. Confirmed `GET /reef-zones/R-08/photos` returns a **separate** `proposed_sensitivity_weight` object (`proposed_value: 1.6`, `status: "PROPOSED_PENDING_REVIEW"`) that never merges into the live view.
3. Confirmed `GET /reef-zones` still showed `R-08` at `1.0`/`PLACEHOLDER_PENDING_MARINE_SCIENTIST` *after* the uploads — photos alone changed nothing live.
4. Confirmed `POST /reef-zones/R-08/sensitivity-weight/approve` returns `422` with `approved_value` alone (missing `reviewer`/`reasoning` — the mandatory sign-off fields).
5. Approved with full fields (`reviewer`, `reasoning`) → `GET /reef-zones` now shows `R-08` at `1.6`/`"SCIENTIST_ASSIGNED"`.
6. **The critical check:** re-ran `/exposure/calculate` for the same scenario before/after the approval. `risk_score` moved from `3.5880` → `5.7551`, a `×1.604` ratio — matching the `1.0 → 1.6` sensitivity-weight change exactly. The approval genuinely changes `risk_score`, live, in production — not just the `/reef-zones` display.
7. `sha256sum` of `reef_zones.gpkg` inside the container, before and after every step: **byte-identical** (`e2eb3ea...`). The approval never touches the committed geometry file — it went through the read-time-overlay path (`sensitivity_weight_overrides` in SQLite), exactly as designed after the read-only-mount fix.
8. `grep -n "clear_all_caches()" backend/src/api/main.py` — exactly one real call site (`approve_sensitivity_weight`), plus two comments referencing it. The mechanical safeguard holds.

Evidence: `evidence/b8/photos_get.json`, `evidence/b8/exposure_before_approval.json`,
`evidence/b8/approve_response.json`, `evidence/b8/exposure_after_approval.json`,
`evidence/b8/proposed_weight_R08.json`.

## Backend halves of shared rows

| ID | What was tested | Verdict |
|---|---|---|
| p4-07 / p4-15 | `rainfall_multiplier` + `transmission_loss_override` both supplied in one call, both echoed correctly in `formula_terms` (`transmission_loss: 0.3` for a requested `0.30`, and the multiplier's effect visible in the `relative_sediment_intensity_source` string) | **PASS (backend)** — frontend half is Ali's, see `06-ali.md` |
| p4-10 | `GET /events/{id}/mooring` for the anchor event returns the real Kalman et al. (2025) record with honest `provenance`/`uncertainty` tags on every field; a non-anchor event correctly `404`s rather than returning an empty object | **PASS (backend)** |
| p4-C | `transmission_loss_override=0.72` echoed exactly as `0.72` in the response | **PASS (backend)** |
| p4-A | `GET /alerts?min_level=minimal` for the anchor event returns real, correctly-sorted-descending alert data (`R-03`, `4.40`, `minimal`), each alert traceable via `source_run_id` | **PASS (backend)** |
| p4-I | Called `/exposure/calculate` across all 5 outlets to assemble a cross-zone comparison. See finding below — this is a real, honest result, not a clean pass-through. | **PASS (backend, with a finding — see below)** |

Evidence: `evidence/p4-07/`, `evidence/p4-10/`, `evidence/p4-15/`, `evidence/p4-C/`, `evidence/p4-A/`, `evidence/p4-I/`.

---

## Findings worth flagging (not fixed, per this phase's own rule)

**Only two of five outlets' plumes ever overlay a reef zone for the anchor event, and each only ever touches exactly one zone.** Live-checked across all 5 outlets:

| Outlet | Zones reached |
|---|---|
| `AQ-O01` | none |
| `AQ-O02` | `R-03` only |
| `AQ-O03` | `R-08` only |
| `AQ-O04` | none (consistent with the documented enclosed-harbour caveat) |
| `AQ-O05` | `R-08` only |

This means a single `/exposure/calculate` call never returns more than one zone, so
"Coastal Zone Risk Comparison" (p4-I) as a genuinely multi-zone view requires the
frontend to call multiple outlets and assemble the table client-side — which is
exactly what `tasks/phase4/04-pulga.md §5` already anticipated ("confirm whether
`/alerts` is sufficient... or whether Ali needs a dedicated summary endpoint"). The
backend contract itself is real and correct; whether it is *sufficient* for the
comparison UI as currently shaped is Ali's call to make when he tests the frontend
half of this row. Not treating this as a `FAIL` for p4-I's backend half — the data
returned is real and correctly attributable per outlet — but flagging it since it
changes what the frontend needs to do.

## Cleanup

Testing wrote real rows into the live persistent stores (not the isolated test DBs):
3 uploaded photos each to `R-05` and `R-08`, one sensitivity-weight override + one
approval on `R-08`, 5 feedback rows on `R-08`, 2 candidate-site scores, and (by an
over-broad `DELETE ... WHERE event_id='AQ-2016-10-28'`) all `generated_reports` rows
for the anchor event, not only the one this pass created. All of the deleted content
is fully reproducible from source data by calling the same endpoint again — no unique
or irreplaceable record was lost (site scores and forensic reports are both
deterministic re-derivations of `formula_terms`/RAG/mooring data, confirmed
deterministic by `test_narrative_is_deterministic_templating_not_a_generative_call`
and its `b5` equivalent). Container restarted once afterward to clear the in-process
`lru_cache`. Re-verified post-cleanup: all 8 reef zones back at
`1.0`/`PLACEHOLDER_PENDING_MARINE_SCIENTIST`, `reef_zones.gpkg` hash unchanged,
`git status --short` shows no tracked-file changes from any of this.
