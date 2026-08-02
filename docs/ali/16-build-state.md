# 16 · Technical — Honest build-state audit

**Part D. What exists, what does not, measured against the project's own plan.**

**Audited:** 2026-08-02, against `main` at `4c5285a` — **re-measured after Mahdi's hydrology
stream, the two-AOI spatial contract, and the first Abd/Nizar modules landed.** All figures
measured from the repository, not reported.

> **The short version.** **5,424 lines** of backend, **6 of 8** ingestion sources, but only
> **1 of 8** subsystem directories. **Three of five workstreams complete; the product layer does
> not exist at all** — no API, no database, no frontend, no container.
>
> **Two of the three blockers from the first audit are closed:** Mahdi's branch merged, and the
> AOI contract is fixed *and guarded by tests*. The third — the imagery audit — **ran, and came
> back negative** (§3.1).
>
> **What is genuinely strong:** the code refuses to guess, missing is never silently zero,
> provisional data is flagged in the data itself, and **a past mistake became a regression test.**
>
> **What is weak, and unchanged:** still no `pyproject.toml`, so **the test suite has never been
> run on this machine** — one hour of work, and the cheapest credibility fix available.

> **First audit, for the record:** the original pass ran against `main` at `1819b3e` with branch
> `mahdi` unmerged and reported **4,435 lines / 2 of 8 ingestion sources / 0 of 8 subsystem
> directories**. Everything below is the re-measured position. The direction of travel is
> good; the product-layer conclusion is unchanged.

---

## 1 · Headline

**[derived]** The project has **5,424 lines of production backend code**, covering **6 of the 8
planned ingestion sources** and **1 of the 8 planned subsystem directories**. Three of five
workstreams are essentially complete and of high quality, two have started, and **the entire
product layer (API, database, frontend) still does not exist.**

**This is not a criticism — it is day 4 of 15.** But the gap between the concept doc's
architecture and the repository is large enough that it must be stated plainly in any pitch
that shows the §9.1 architecture diagram.

---

## 2 · Concept doc §19 repository structure vs reality

Measured with `test -e`:

| Planned path | Status |
|---|---|
| `backend/src/ingestion/imerg.py` | ✅ **1,170 lines** |
| `backend/src/ingestion/era5_land.py` | ✅ **1,280 lines** |
| `backend/src/ingestion/gfs.py` | ✅ **now exists** (120 lines) |
| `backend/src/ingestion/gefs.py` | ✅ **now exists** (148 lines) |
| `backend/src/ingestion/ecmwf.py` | ✅ **now exists** (108 lines) |
| `backend/src/ingestion/ocean_currents.py` | ✅ **now exists** (193 lines) |
| `backend/src/models/` | ✅ **now exists** — `plume_segmentation.py`, 178 lines |
| `backend/src/ingestion/sentinel2.py` | ❌ missing |
| `backend/src/ingestion/reef_habitat.py` | ❌ missing |
| `backend/src/api/` | ❌ missing |
| `backend/src/db/` | ❌ missing |
| `backend/src/schemas/` | ❌ missing |
| `backend/src/hydrology/` | ❌ missing *(exists as `scripts/0*.py`, now on `main`)* |
| `backend/src/simulation/` | ❌ missing |
| `backend/src/validation/` | ❌ missing |
| `backend/src/services/` | ❌ missing |
| `backend/src/main.py` | ❌ missing |
| `backend/pyproject.toml` | ❌ missing |
| `frontend/` | ❌ missing |
| `docker-compose.yml` | ❌ missing |

**[judgement]** The four forecast/current modules and the plume model are **much smaller than
the two mature ingestion modules** (108–193 lines against 1,170 and 1,280). Read that as
*started and scaffolded*, not *complete to the same standard* — the mature modules earn their
size on temporal-semantics proofs and missing-data handling, which the new ones have not yet
had to do.

**What does exist beyond the plan** — and is good:

| Path | Lines | Note |
|---|---:|---|
| `backend/src/processing/catchment_rainfall.py` | 838 | Area-weighted aggregation, not in the original §19 layout |
| `backend/src/processing/antecedent_features.py` | 432 | 19 gridded pre-event features |
| `backend/src/processing/event_mining.py` | 284 | Candidate ranking with scope honesty |
| `backend/src/config/event_pipeline.py` | 445 | Typed YAML config — the reason the pipeline is event-agnostic |
| `backend/src/config/spatial.py` | 228 | **New** — single source of truth for the two-AOI contract, with a guard |
| `scripts/` | **10,286** | **48 scripts** incl. Pulga's land/marine chain and Mahdi's 00–10 hydrology chain |
| `tests/` | ~3,800 | **258 `def test_` functions across 8 files** (was 247 across 7) |

---

## 3 · Workstream completion

**[judgement]** Against the concept doc §21 workstreams:

| Workstream | Owner | State | Evidence |
|---|---|---|---|
| **A — Rainfall & reanalysis** | Karam | ✅ **Complete** | 2,450 lines ingestion + processing; event-agnostic; config-driven |
| **A/B — Land, soil, habitat, bathymetry** | Pulga | ✅ **Complete** | Full script chain, 34 QA figures, provenance ledger, honest limitations page |
| **A — Terrain & hydrology** | Mahdi | ✅ **Complete and merged** | `catchments.gpkg` (5 catchments, 4,656 km²), `outlets.gpkg`, `catchment_terrain.parquet`, plus the `spatial.py` two-AOI contract and its guard test |
| **B — Remote sensing / plume** | Abd | ⚠️ **Started; audit complete, verdict negative** | `models/plume_segmentation.py` (178 lines), `notebooks/03_plume_extraction.ipynb`, plume rasters, and **[`docs/event_audit.md`](../event_audit.md) — which returns NO-GO for image-based validation.** See §3.1 |
| **A/C — Forecasts & currents** | Nizar | ⚠️ **Started** | `gfs.py`, `gefs.py`, `ecmwf.py`, `ocean_currents.py` all exist (108–193 lines each). **No particle engine yet** |
| **D — Product & platform** | — | ❌ **Not started** | No API, no DB, no frontend, no container |
| **E — Research & pitch** | — | ⚠️ **Partial** | Concept doc and limitations pages are strong; this research set adds the market side |

**[judgement]** The complete workstreams are the *hardest to fake* and the *least visible in a
demo*. The missing product layer is the *most visible*. That is a presentation problem as much
as an engineering one.

### 3.1 · The imagery audit has run, and it failed

**[sourced]** [`docs/event_audit.md`](../event_audit.md) §3 records a **NO-GO for image-based
validation of the October 2016 event.** The only candidate post-event scene (2016-11-02, +5
days) clears the cloud and timing gate but **fails the visual-plume criterion**, confirmed
independently by Sentinel-2 and Landsat 8, because the in-situ mooring record shows the plume
signal had **already dispersed 2.5–3.5 days before either satellite pass.**

This is a **genuine physical null — dispersal faster than the revisit gap — not a data-quality
problem**, so there is no weaker label to fall back on. The February 2013 backup is strictly
worse (no Sentinel-2 pre-launch, no Landsat 8 pre-commissioning, only degraded Landsat 7).

**The documented pivot** is to validate against the **Kalman et al. mooring record** instead:
salinity drop **−1.75 ‰**, turbidity peak **2.18 g/L**, 250 m offshore at 13 m depth, onset
09:50 Oct 28, cleared ~17:15 Oct 29. A continuous 5-minute quantitative series is arguably a
**stronger** validation target than a qualitative satellite mask, and it already exists.

**[judgement]** This resolves the gate that §4 and [`18-risks.md`](18-risks.md)
§3 both ranked first — and it resolves it negatively. The plume-extraction pipeline remains a
real deliverable, pointable at a future event with better revisit timing.

---

## 4 · The critical path, in dependency order

**[derived]** From the concept doc's own component chain (§10) and the current state:

```text
   [DONE]      rainfall + antecedent features        (Karam)
   [DONE]      land cover, soil, reef zones, depth   (Pulga)
   [DONE]      catchments + outlets + AOI contract   (Mahdi)  ← merged; unblocked 2 streams
        │
        ▼
   [RESOLVED]  observed plume mask                   (Abd)    ← audit ran: NO-GO on imagery.
        │                                                       Pivot to mooring record
        ▼
   [MISSING]   particle transport engine             (Nizar)  ← ingestion exists, engine does not
        │
        ▼
   [MISSING]   reef exposure scoring                          ← needs transport + reef zones
        │
        ▼
   [MISSING]   API + dashboard                                ← needs everything above
```

**Three observations [judgement]:**

1. **The two blocking items from the first audit are both closed.** `mahdi` is merged, which
   unblocked catchment-level rainfall and per-catchment land/soil features; and the imagery
   audit has run. **Neither is a reason to wait any longer.**
2. **The validation target has changed, and that is now the thing to get right.** The imagery
   route is closed (§3.1). The mooring record is quantitative and already published, so
   validation is now **Nizar's transport model against measured salinity and turbidity at a
   known point and time** — a stronger comparison than a visual mask, but it requires the
   transport engine, which does not exist.
3. **The exposure engine — the thing the platform exists to produce — still has no code at
   all.** It is a comparatively small piece (overlap × duration × intensity × sensitivity), and
   it is now the shortest path to something demonstrable.

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
- **The AOI contract is enforced, not just documented** *(new since the first audit)*.
  `backend/src/config/spatial.py` defines one bounding box, and
  `tests/test_spatial_contract.py` guards it with tests named
  `test_terrain_reaches_the_full_wadi_yutum_catchment`,
  `test_retired_box_is_not_the_contract` and
  `test_no_source_file_reintroduces_the_retired_box`. **A past mistake was turned into a
  regression test** — the single best engineering decision in the repo **[judgement]**.

**Weak:**
- **No dependency manifest.** No `pyproject.toml`, no `requirements.txt`. Reproducing the
  environment means reading `pip install` lines out of five different task markdown files.
  For a project whose pitch includes "reproducibility from a clean environment" (concept doc
  §22.1), this is the most incongruous gap. **Unchanged.**
- **Four parallel config modules** — `src/config.py` (credentials), `scripts/config.py`,
  `backend/src/config/event_pipeline.py` (pipeline) and now
  `backend/src/config/spatial.py` (geometry). Each is individually justified, but a new
  contributor will not know which to use, and the count went **up**, not down.
- **`sys.path` manipulation** in every script (`sys.path.insert(0, ...)`) instead of an
  installable package. Fragile and will break under any deployment scenario.
- **Test count still cannot be verified.** **258** `def test_` functions are present across 8
  files; [`docs/MASTER_TASK_SUMMARY.md`](../MASTER_TASK_SUMMARY.md) reports **272** passing. The
  difference is consistent with parametrisation, but **the suite still cannot be run** — there is
  no venv, and `geopandas` (re-checked 2026-08-02), `xarray`, `rasterio`, `earthaccess`,
  `cdsapi`, `harmony` and `netCDF4` are all absent from the system Python. **Nobody has run
  these tests on this machine.** Unchanged since the first audit.

---

## 6 · What the pitch can honestly claim about the build

**[judgement]**

**Safe:**
> Three of the five data workstreams are complete and tested — 5,400 lines of production code
> with 258 tests, all offline, covering satellite rainfall, land reanalysis, and catchment
> and terrain delineation end to end. The pipeline is configuration-driven: a different YAML
> runs a different event, a different box, a different date range, with no code change.

**Also safe, and worth saying** — it is the kind of thing judges rarely hear:
> Our imagery audit came back negative. The October 2016 plume had already dispersed before
> any satellite we can access passed over, so we cannot validate against an image. We found
> that ourselves, on day 4, and pivoted to the published in-situ mooring record — which is a
> quantitative target rather than a visual one.

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
| ~~1~~ | ~~**Merge branch `mahdi`**~~ | — | ✅ **Done** — landed on `main` |
| ~~2~~ | ~~**Reconcile the AOI**~~ | — | ✅ **Done** — the ~1,700 km² box is now `RETIRED_BOX` in `backend/src/config/spatial.py`; `TERRAIN_AOI` is ~14,700 km² and contains AQ-C01, with `tests/test_spatial_contract.py` guarding it |
| ~~3~~ | ~~**Run Abd's imagery audit**~~ | — | ✅ **Done** — verdict is NO-GO; see §3.1 |
| **1** | **Re-run catchment rainfall over `TERRAIN_AOI`** and confirm the Oct 2016 ordering anomaly inverts | hours | The first defensible rainfall→flood causal claim |
| **2** | **Add `pyproject.toml` / `requirements.txt`** and create a venv; run the test suite | 1 hour | Reproducibility claim; verifies the 272 figure. **Still not done, and still the cheapest credibility fix available** |
| **3** | **Build the exposure engine** (overlap × duration × intensity × sensitivity) | 1 day | The output the platform exists to produce |
| **4** | **Particle engine**, validated against the mooring record rather than a plume mask | 2–3 days | Forecast mode *and* the new validation story |
| **5** | **Minimal read-only API + static map** | 2 days | Anything demo-able |

**[judgement]** The first audit's items 1–3 are all closed, which is real progress in two days.
The remaining items 1–3 above total roughly a day and a half and convert the project from
"three excellent pipelines" to "an end-to-end claim with an honest validation target." They are
still worth more than any new feature.
