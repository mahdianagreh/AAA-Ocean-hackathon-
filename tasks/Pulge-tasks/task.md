# Pulga — Tasks Tracker

**Last updated:** 2026-08-02 · Phase 2 · Backend, Exposure Engine, RAG

- Reproduce from zero: [docs/README_pulga.md](../../docs/README_pulga.md)
- Provenance + the v2 amendment: [docs/data_dictionary.md](../../docs/data_dictionary.md)
- **42 QA figures, captioned:** [docs/qa_screenshots/MANIFEST.md](../../docs/qa_screenshots/MANIFEST.md)
- Judge-facing: [docs/pitch_limitations.md](../../docs/pitch_limitations.md) · [docs/rag_limitations.md](../../docs/rag_limitations.md)
- AOI evidence: [docs/aoi_coverage_report_20260802.txt](../../docs/aoi_coverage_report_20260802.txt)

**Test suite: 174 checks, 0 failures.**

```
tests/test_soilgrids_units.py     21 pass    unit conversion, texture closes to 100.00
tests/test_exposure_engine.py     33 pass    formula, CRS guard, formula_terms, cross-checks
tests/test_explain_fidelity.py    27 pass    no number altered, EN + AR
tests/test_ask_citations.py       15 pass    100% citation coverage, docs/ali excluded
tests/test_api_contracts.py       78 pass    15 routes, 19 caveats verified to reach payloads
```

---

## §1 · THE AOI FIX — closed

| Item | Status | Evidence |
|---|---|---|
| `check_aoi_coverage.py` run, output saved + timestamped | done | [aoi_coverage_report_20260802.txt](../../docs/aoi_coverage_report_20260802.txt) — **19 files short → 7**, each remainder explained |
| `TERRAIN_AOI` / `MARINE_AOI` in config, old box deleted | done | Team's `backend/src/config/spatial.py` owns it; `make_aoi.py` reduced to a **verifier** rather than a second writer |
| Second WorldCover tile identified, downloaded, mosaicked | done | **N27E033 + N30E033**, tiles *derived* from the AOI not hardcoded |
| Seam-checked with a saved screenshot | done | [worldcover_06_v2_mosaic_seam_check.png](../../docs/qa_screenshots/worldcover_06_v2_mosaic_seam_check.png) — **0.01 pp** discontinuity, no blending applied |
| SoilGrids re-pulled against `TERRAIN_AOI` | done | 188×155 → **481×526** cells |
| OSM re-clipped against `TERRAIN_AOI` | done | roads 3,845 → **8,289**; drainage 200 → **1,402** |
| All three aggregations re-run on the real 5-catchment set | done | at the contract paths, fixture deleted |
| `AQ-C01` bare-ground re-verified + screenshotted | done | **98.64%** over 4,453 km² → [worldcover_07](../../docs/qa_screenshots/worldcover_07_aq_c01_bareground_v2.png) |
| Earth Engine authenticated | **BLOCKED — needs you** | No credentials at `~/.config/earthengine/`; `ee.Authenticate()` requires browser OAuth |
| `data_dictionary.md` updated with the re-pull, reason, date | done | Appended as a dated **amendment**, not a silent overwrite |

**Marine data deliberately NOT re-pulled.** `MARINE_AOI` is unchanged between
contract v1 and v2. The coverage tool flags `reef_zones` and `coastline` as "short",
but that is the wrong test for a derived coastal feature: reef zones are
**contained** in the marine box and occupy 8.3% of it, which is correct for a
fringing reef. Verified rather than assumed, and recorded in the report.

## §2 · Phase-1 blockers

| Item | Status |
|---|---|
| Three feature tables at contract paths, fixture deleted | **done** |
| Catchment areas cross-checked vs geometry contract | **done — all 5 within 0.1%**, total 4,656.1 vs 4,656 km² |
| Earth Engine auth + real ACA export | **BLOCKED on browser OAuth.** `export_aca.py` ready; `verify_against_provisional()` asserts no new IDs and no centroid drift > 5 km |
| `sensitivity_weight` still 1.0 and still labelled | **done** — enforced by test, and the caveat travels on 3 endpoints |

## §3 · FastAPI backend

All **15 concept §17 routes** registered and returning declared shapes.
→ [phase2_05_endpoint_status.png](../../docs/qa_screenshots/phase2_05_endpoint_status.png)

- [x] Pydantic models for every request/response — [schemas.py](../../backend/src/api/schemas.py) is the deliverable
- [x] Caveats travel as **structured data**, 19 verified → [phase2_04](../../docs/qa_screenshots/phase2_04_caveat_coverage_matrix.png)
- [x] Caching keyed on the scenario hash, not wall clock — verified by test
- [x] No database connection opened. Reads go through `data_access`; runs persist via `exposure/store.py` behind two functions so the shared session layer swaps in cleanly
- [x] Stubs shaped correctly and flagged `is_stub` + a **critical** caveat

**Priority-1 for the 6 Aug slice is live now:** health · catchments · reef-zones ·
events · exposure (real engine, not a stub).

## §4 · Component D — exposure engine

- [x] Formula exactly as specified; `risk_score = product × 100`, with `score_scale` recorded
- [x] Contour × zone intersection **in EPSG:32636**, enforced by `_assert_measure_crs` which rejects both 4326 and 3857
- [x] `formula_terms` stored on **every** run → [phase2_01](../../docs/qa_screenshots/phase2_01_formula_terms_table.png)
- [x] Risk bands per §14.5, with the "needs marine scientists" caveat attached wherever displayed
- [x] `zone_fraction_affected` preferred over absolute km²
- [x] **Cross-check 1** (circular-buffer baseline): scores 33.75 → 17.5 → 5.0 with distance; arrivals 3 h → 6 h → 12 h
- [x] **Cross-check 2** (hand-computed): 21.2439280620 by hand == engine, to 1e-12

A zone the plume never reaches returns **no result plus an explanatory caveat**,
never a zero-risk hit — and the caveat names the nearest zone and the plume's
actual reach.

## §5 · Component E — explanation and RAG

- [x] `/explain` bilingual, matching the calibration paragraph almost verbatim
- [x] **The LLM phrases nothing it computes** — the shipped generator is a deterministic template, so the rule holds by construction. Self-checks fidelity in the response path, not only in tests
- [x] RAG corpus is an **explicit allowlist**; `docs/ali/*` excluded twice over
- [x] `/ask` returns citations or an honest refusal; assertion in the request path
- [x] Bilingual, with the English-corpus limitation stated → [rag_limitations.md](../../docs/rag_limitations.md)

## §6 · QA discipline

42 Pulga figures, all captioned, timestamped and manifested. The manifest now also
accounts for 2 figures belonging to another workstream rather than pretending to
cover the whole directory.

## Day-12 gate (run early)

| Artifact | Status |
|---|---|
| `catchments_PROVISIONAL.gpkg` | superseded by `catchments.gpkg` |
| `outlets_PROVISIONAL.gpkg` | superseded by `outlets.gpkg` |
| `reef_zones_PROVISIONAL.gpkg` | **still the live artifact** — ACA blocked on EE auth; `/health` reports `degraded` and says why |
| `*FIXTURE*` anywhere under `data/` | **none** |
| `sensitivity_weight` = 1.0 | still a **labelled** placeholder, which is the correct end state |

## Bugs caught in Phase 2 — 5 more, running total 10

| # | Bug | Would have caused |
|---|---|---|
| 6 | `0.0725 × 100` rendered as `7.249999999999999%` | IEEE754 artefact on screen, unfixable by rounding since rounding is banned — fixed with an exact decimal shift |
| 7 | Fidelity check used substring matching | `72` → `72.4` passed undetected — a number could be *extended* without failing the audit |
| 8 | `/ask` answered out-of-corpus with a real citation | "airspeed **velocity**" matched ocean-current velocity: cited but not responsive — fixed with a term-coverage gate |
| 9 | `/alerts` read the newest run, not the requested scenario | A cached exposure response writes no run, so alerts could describe a different outlet than asked about |
| 10 | Catchment-area caveat cited the wrong file | ±4% lives in the data dictionary, not `00-contracts.md §2` |

Bugs 6–9 were found **by writing the test or building the artifact**.

## The one thing that still needs a human

**Earth Engine authentication** (~10 min, browser). Confirmed blocked: no
credentials on disk, and `ee.Authenticate()` needs an interactive OAuth flow.

```bash
.venv/bin/python -c "import ee; ee.Authenticate()"
export GEE_PROJECT=<your-project-id>
cd scripts && ../.venv/bin/python export_aca.py submit
```

Everything downstream of it is built and asserted against the provisional schema,
so the swap is a data change, not a rebuild.
