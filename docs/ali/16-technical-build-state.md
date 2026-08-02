# 16 · Technical — Honest build-state audit

**Part D. What exists, what does not, measured against the project's own plan.**

**Audited:** 2026-08-02, against `main` at `1819b3e` plus unmerged branch `mahdi`.
All figures measured from the repository, not reported.

---

## 1 · Headline

**[derived]** The project has **4,435 lines of production backend code across 5 modules**,
covering **2 of the 8 planned ingestion sources** and **0 of the 8 planned subsystem
directories**. Two of five workstreams are essentially complete and of high quality; two have
no code at all; the entire product layer (API, database, frontend) does not exist.

**This is not a criticism — it is day 4 of 15.** But the gap between the concept doc's
architecture and the repository is large enough that it must be stated plainly in any pitch
that shows the §9.1 architecture diagram.

---

## 2 · Concept doc §19 repository structure vs reality

Measured with `test -e`:

| Planned path | Status |
|---|---|
| `backend/src/ingestion/imerg.py` | ✅ **1,163 lines** |
| `backend/src/ingestion/era5_land.py` | ✅ **1,273 lines** |
| `backend/src/ingestion/sentinel2.py` | ❌ missing |
| `backend/src/ingestion/ocean_currents.py` | ❌ missing |
| `backend/src/ingestion/reef_habitat.py` | ❌ missing |
| `backend/src/ingestion/gfs.py` / `gefs.py` / `ecmwf.py` | ❌ missing (all three) |
| `backend/src/api/` | ❌ missing |
| `backend/src/db/` | ❌ missing |
| `backend/src/schemas/` | ❌ missing |
| `backend/src/hydrology/` | ❌ missing *(exists as `scripts/0*.py` on branch `mahdi`)* |
| `backend/src/models/` | ❌ missing |
| `backend/src/simulation/` | ❌ missing |
| `backend/src/validation/` | ❌ missing |
| `backend/src/services/` | ❌ missing |
| `backend/src/main.py` | ❌ missing |
| `backend/pyproject.toml` | ❌ missing |
| `frontend/` | ❌ missing |
| `docker-compose.yml` | ❌ missing |

**What does exist beyond the plan** — and is good:

| Path | Lines | Note |
|---|---:|---|
| `backend/src/processing/catchment_rainfall.py` | 838 | Area-weighted aggregation, not in the original §19 layout |
| `backend/src/processing/antecedent_features.py` | 432 | 19 gridded pre-event features |
| `backend/src/processing/event_mining.py` | 284 | Candidate ranking with scope honesty |
| `backend/src/config/event_pipeline.py` | 445 | Typed YAML config — the reason the pipeline is event-agnostic |
| `scripts/` | ~5,900 | 35 scripts incl. Pulga's full land/marine chain |
| `tests/` | ~3,600 | 247 `def test_` functions across 7 files |

---

## 3 · Workstream completion

**[judgement]** Against the concept doc §21 workstreams:

| Workstream | Owner | State | Evidence |
|---|---|---|---|
| **A — Rainfall & reanalysis** | Karam | ✅ **Complete** | 2,436 lines ingestion + processing; event-agnostic; config-driven; 141 tests |
| **A/B — Land, soil, habitat, bathymetry** | Pulga | ✅ **Complete** | Full script chain, 34 QA figures, provenance ledger, honest limitations page |
| **A — Terrain & hydrology** | Mahdi | ⚠️ **Complete but unmerged** | Branch `mahdi`: real `catchments.gpkg` (5 catchments), `outlets.gpkg`, `catchment_terrain.parquet` |
| **B — Remote sensing / plume** | Abd | ❌ **Not started** | No `plume_segmentation.py`, no `docs/event_audit.md`, no Sentinel-2 data |
| **A/C — Forecasts & currents** | Nizar | ❌ **Not started** | No `gfs.py`, `gefs.py`, `ecmwf.py`, `ocean_currents.py`, no particle engine |
| **D — Product & platform** | — | ❌ **Not started** | No API, no DB, no frontend, no container |
| **E — Research & pitch** | — | ⚠️ **Partial** | Concept doc and limitations pages are strong; this research set adds the market side |

**[judgement]** The two complete workstreams are the *hardest to fake* and the *least
visible in a demo*. The two missing ones are the *most visible*. That is a presentation
problem as much as an engineering one.

---

## 4 · The critical path, in dependency order

**[derived]** From the concept doc's own component chain (§10) and the current state:

```text
   [DONE]      rainfall + antecedent features        (Karam)
   [DONE]      land cover, soil, reef zones, depth   (Pulga)
   [UNMERGED]  catchments + outlets                  (Mahdi)  ← merge unblocks 2 streams
        │
        ▼
   [MISSING]   observed plume mask                   (Abd)    ← GATES ALL VALIDATION
        │
        ▼
   [MISSING]   particle transport engine             (Nizar)  ← needs outlets + currents
        │
        ▼
   [MISSING]   reef exposure scoring                          ← needs plume + reef zones
        │
        ▼
   [MISSING]   API + dashboard                                ← needs everything above
```

**Three observations [judgement]:**

1. **Merging `mahdi` is the single highest-value action available**, and it costs one
   command. It unblocks catchment-level rainfall (Karam's aggregation code is written and
   tested but has never run on real polygons) and per-catchment land/soil features (Pulga's
   outputs are quarantined to `_FIXTURE` files).
2. **Abd's imagery audit gates the entire validation story** and, per
   [`12-business-buyers-and-value.md`](12-business-buyers-and-value.md) §6, gates every buyer
   too. It is the project's own stated gate (concept doc Final Recommendation) and it is
   unanswered on day 4 despite the contract moving it to day 2.
3. **The exposure engine — the thing the platform exists to produce — has no code at all.**
   It is a comparatively small piece (overlap × duration × intensity × sensitivity), but it
   sits downstream of two missing subsystems.

---

## 5 · Quality assessment of what exists

**[judgement]** This is genuinely above typical hackathon standard, and the reasons are
specific:

**Strong:**
- **Refuses to guess.** `infer_temporal_semantics()` proves ERA5's accumulation convention
  from `GRIB_stepType` metadata and **raises rather than assume**. Value behaviour is
  explicitly rejected as evidence.
- **Missing is never zero.** Enforced throughout — rolling accumulations use
  `min_periods = full window` with NaN propagation; catchment aggregation divides only by the
  area that had data and reports `valid_area_fraction`.
- **Final/Early separation is structural**, not procedural — separate collections, separate
  directories, and `imerg_run_type` on every output.
- **Grid misalignment is documented in the module docstring** with the actual coordinate
  values, and area-weighted overlap is enforced instead of index pairing.
- **Provisional data is flagged in the data itself** — `sensitivity_weight_status` literally
  reads `PLACEHOLDER_PENDING_MARINE_SCIENTIST`.
- **Scope honesty as a schema field** — `is_exhaustive` on every candidate row.

**Weak:**
- **No dependency manifest.** No `pyproject.toml`, no `requirements.txt`. Reproducing the
  environment means reading `pip install` lines out of five different task markdown files.
  For a project whose pitch includes "reproducibility from a clean environment" (concept doc
  §22.1), this is the most incongruous gap.
- **Two parallel config systems** — `src/config.py` (credentials) and
  `backend/src/config/event_pipeline.py` (pipeline). Plus `scripts/config.py`. Workable, but
  a new contributor will not know which to use.
- **`sys.path` manipulation** in every script (`sys.path.insert(0, ...)`) instead of an
  installable package. Fragile and will break under any deployment scenario.
- **Test count cannot be verified.** 247 `def test_` functions are present;
  [`docs/MASTER_TASK_SUMMARY.md`](../MASTER_TASK_SUMMARY.md) reports 272 passing. The
  difference is consistent with parametrisation, but **the suite cannot currently be run** —
  there is no venv and `xarray`, `geopandas`, `rasterio`, `earthaccess`, `cdsapi`, `harmony`
  and `netCDF4` are all absent from the system Python. **Nobody has run these tests on this
  machine.**

---

## 6 · What the pitch can honestly claim about the build

**[judgement]**

**Safe:**
> Two of the five data workstreams are complete and tested — 4,400 lines of production code
> with 247 tests, all offline, covering satellite rainfall and land reanalysis end to end.
> The pipeline is configuration-driven: a different YAML runs a different event, a different
> box, a different date range, with no code change.

**Unsafe:**
> Showing the concept doc §9.1 architecture diagram as though it describes the system. Two
> thirds of those boxes do not exist. **Show what runs, and mark the rest as roadmap on the
> slide itself.** A judge who asks "can you show me the plume simulation?" during Q&A is
> the scenario to avoid.

---

## 7 · Recommended engineering actions, ranked

**[judgement]** By value per hour:

| # | Action | Effort | Unblocks |
|---|---|---|---|
| 1 | **Merge branch `mahdi`** | minutes | Catchment rainfall + per-catchment land/soil features |
| 2 | **Reconcile the AOI** after merge — the download box (~1,700 km²) is smaller than AQ-C01 (4,453 km²) | hours | Any valid catchment-level rainfall claim |
| 3 | **Run Abd's imagery audit** | 1 day | The entire validation story and every buyer conversation |
| 4 | **Add `pyproject.toml` / `requirements.txt`** and create a venv; run the test suite | 1 hour | Reproducibility claim; verifies the 272 figure |
| 5 | **Build the exposure engine** (overlap × duration × intensity × sensitivity) | 1 day | The output the platform exists to produce |
| 6 | **Minimal read-only API + static map** | 2 days | Anything demo-able |
| 7 | Particle engine against provisional outlets | 2–3 days | Forecast mode |

**[judgement]** Items 1–4 total roughly two days and convert the project from "two excellent
pipelines" to "a validated end-to-end claim." They are worth more than any new feature.
