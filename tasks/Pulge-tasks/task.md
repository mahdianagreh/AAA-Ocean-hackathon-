# Pulga — Tasks Tracker

**Last updated:** 2026-08-02 · Phase 2 (backend · exposure engine · RAG)

- Reproduce from zero: [docs/README_pulga.md](../../docs/README_pulga.md)
- Provenance & limitations: [docs/data_dictionary.md](../../docs/data_dictionary.md)
- Model card (exposure engine, explain, RAG): [docs/model_card.md](../../docs/model_card.md)
- QA figures, captioned: [docs/qa_screenshots/MANIFEST.md](../../docs/qa_screenshots/MANIFEST.md)
- Judge-facing honesty page: [docs/pitch_limitations.md](../../docs/pitch_limitations.md)
- AOI correction evidence: [docs/aoi_coverage_report_20260802.txt](../../docs/aoi_coverage_report_20260802.txt)

> **Everything green except Earth Engine**, which needs an interactive browser and is
> excluded by instruction. Whole-repo suite: **370 passed, 0 failed, 45 skipped.**

---

## §9 Definition of Done — 10 of 12

| # | Item | Status |
|---|---|---|
| 1 | `check_aoi_coverage.py` run, gap report saved | **done** — run before re-fetching; 19→7 short, each remainder explained |
| 2 | WorldCover v2 mosaic (2 tiles), seam-checked, screenshotted | **done** — 0.01 pp seam |
| 3 | SoilGrids + OSM re-pulled against `TERRAIN_AOI` | **done** |
| 4 | 3 feature tables on real catchments, fixture deleted, areas cross-checked | **done** — all 5 within 0.1% |
| 5 | Earth Engine authenticated | **BLOCKED — excluded by instruction** |
| 6 | Real ACA export + `verify_against_provisional()` | **BLOCKED on 5** — script ready, asserts written |
| 7 | FastAPI serving every §17 endpoint, typed, cached, caveats as data | **done** — 15 endpoints, 19 routes |
| 8 | Exposure engine, `formula_terms` stored, EPSG:32636 | **done** — 21 terms per result |
| 9 | `/explain` exact number-fidelity | **done** — 27 checks, EN + AR |
| 10 | `/ask` 100% citation coverage, `docs/ali` excluded | **done** — 16 checks, 13/13 corpus files |
| 11 | `data_dictionary.md` updated with the re-pull | **done** — dated amendment, v1 kept as history |
| 12 | Day-12 gate grep | **done early** — every match declared |

## §1 AOI fix — 8 of 9 (only EE outstanding)

| Item | Result |
|---|---|
| Coverage report saved + annotated | 19 files short → 7, each remaining one explained as correct-by-construction |
| `TERRAIN_AOI` / `MARINE_AOI` in config, old box deleted | done — and the literal is *not* repeated in any comment; `test_spatial_contract.py` enforces it |
| Second WorldCover tile identified, mosaicked, seam-checked | `N27E033` + `N30E033`, **derived from the AOI**, not hardcoded. 14280×13800 px |
| SoilGrids re-pulled | 188×155 → **526×481** |
| OSM re-clipped | roads 3,845→**8,289**, drainage 200→**1,402**, culverts 27→**46** |
| Per-catchment aggregations re-run | all three, on the real 5-catchment set |
| AQ-C01 bare-ground re-verified + screenshotted | **98.64%** over 4,453 km² (95.6% of basin) |
| Earth Engine | **blocked** |
| Data dictionary notes the re-pull, reason, date | done, with a v1→v2 comparison table |

**Marine data deliberately NOT re-pulled.** `MARINE_AOI` is unchanged between contract
v1 and v2. The coverage tool flags reef zones and coastline as "short", but coverage is
the wrong test for a derived coastal feature — a reef fringe cannot fill an extent that
is mostly open sea. Verified by *containment* instead, which passes.

## §2 Phase-1 blockers

- **Feature tables:** closed. `landcover` (17 cols), `soil` (**73 cols** — mean/σ/min/max/median/count), `urban` (10 cols) at the contract paths.
- **ACA export:** blocked on EE.

## §3 FastAPI — all 15 endpoints live

Priority 1 for the 6 Aug slice is live **now**, ahead of schedule. Priorities 2–3
(runoff, plume) are stubs with final shapes, flagged `is_stub: true` **and** a
`critical` caveat. Priorities 4–5 (exposure, explain, ask, backtests, alerts) are real.

Caveats are scoped: outlet- and run-level caveats attach once at run level, zone-level
ones per result. No duplication in the payload — the same critical warning repeated N
times trains a reader to skim past it.

## §4 Exposure engine

`formula_terms` on every result (21 keys, incl. `measure_crs` and `score_scale`),
persisted to SQLite behind a two-function interface so swapping to the shared session
layer touches nothing else. EPSG:32636 enforced by `_assert_measure_crs`, which
rejects both 4326 and 3857.

Both §4.6 cross-checks implemented and passing:
- **circular-buffer baseline** — 33.75 → 17.5 → 5.0 with distance, arrivals 3 → 6 → 12 h
- **hand-computed spot check** — agrees with the engine to < 1e-12

Verified across all five outlets: 4 produce scores; **AQ-O01 produces none, correctly** —
it sits at the gulf head, 2,995 m from the nearest zone, and the response says so in an
`info` caveat rather than returning a bare empty list.

## §5 Explain + RAG

- `/explain` is a deterministic template, not an LLM — so it *cannot* round a number.
  EN and AR asserted to carry identical numbers for the same input.
- `/ask` composes answers by **quotation**, so an uncited answer is structurally
  impossible. 13/13 corpus files indexed, 255 chunks. `docs/ali/*` excluded by an
  allowlist **and** an independent guard.
- Arabic questions retrieve via a query-term bridge, since the corpus is English —
  stated in `docs/rag_limitations.md`, not hidden.

## §6 QA

42 captioned, timestamped, manifested figures. Manifest reports foreign and missing
files rather than silently covering only part of the directory.

---

## Fixed this phase, beyond the plan

| What | Why it mattered |
|---|---|
| **`config` module-name collision** | `scripts/config.py` and `backend/src/config/` both claimed the bare name. Under pytest whichever imported first won, so `test_soilgrids_units.py` failed *purely on alphabetical ordering*. Renamed to `pulga_config`; added a root `conftest.py` documenting the hazard. |
| **Abd's `run_plume_extraction.py` could not import** | It used `ANALYSIS_BBOX`, removed by the AOI v2 migration. Substituted `MARINE_BBOX` (contract §1 assigns imagery to the marine extent) and flagged the substitution in-file rather than rewriting silently. |
| **5 teammate test files could not collect** | Missing `scipy`, `earthaccess`, `cdsapi`. Installed; those suites now run. |
| **`tmp_db` was not a real fixture** | Used as a pytest param but only defined in the `__main__` path, so 2 storage tests errored. Now a proper fixture pointing at a temp DB, so tests cannot pollute the real audit trail. |
| **Water-fraction cross-check was misleading after v2** | The old 23.89% vs 23.3% comparison was computed on a box that was mostly sea. Recomputed over a common extent (`MARINE_AOI`): **42.91% vs 41.29%, agreeing to 1.62 pp.** |
| **Stale count baked into a filename** | `osm_04_culverts_all_27_numbered.png` showed 46 culverts. Made count-agnostic; added an explicit `prune_missing()` so sanctioned renames don't leave a permanent warning. |
| **Fixture generator removed** | `make_catchments_fixture.py` deleted and the synthetic fallback tier dropped from resolution. With real catchments committed, silently falling back to invented geometry would produce plausible-looking feature tables from polygons that are not watersheds. |

## Target files

| file | status |
|---|---|
| `landcover_by_catchment.parquet` | **done**, real catchments |
| `soil_by_catchment.parquet` | **done**, 73 cols |
| `urban_by_catchment.parquet` | **done**, 10 cols |
| `osm_aqaba.gpkg` | **done**, 12 layers, TERRAIN_AOI |
| `worldcover_terrain_v2_clip.tif` | **done**, 2-tile mosaic |
| `coastline.gpkg`, `depth_utm36n.tif` | **done** (not re-pulled — marine box unchanged) |
| `reef_zones.gpkg` | **`_PROVISIONAL` only** — blocked on EE |
| `exposure_runs.sqlite` | **done** — audit trail |

## The one thing still needing a human

**Earth Engine auth** (~10 min, browser). Verified blocked: no credentials at
`~/.config/earthengine/`, `ee.Authenticate()` requires interactive OAuth. Unblocks
Definition-of-Done items 5 and 6. `export_aca.py submit / status / build` is written
and its ID-continuity asserts are in place.
