# ReefShield Aqaba — working notes

Wadi-to-reef sediment forecasting for the Gulf of Aqaba. Hackathon build:
**The Core Hacks — Blue Horizons**, 30 Jul – 13 Aug 2026, track *AI for Ocean
Science*. Repo: `github.com/mahdianagreh/AAA-Ocean-hackathon-`, shared `main`.

The chain the platform predicts:

```
rainfall forecast → wadi runoff → sediment source & coastal outlet
→ probabilistic marine plume → coral/seagrass exposure → alerts
```

Read `tasks/phase3/00-phase3-plan.md` first, then your own task file in
`tasks/phase3/`. `tasks/phase2/` is the previous phase, kept for context.
`aqaba_aqua_ai_concept.md` is the full concept.

**Phase 3 in one line:** the pieces work individually; make the chain true end to
end and no term in the exposure formula a stub. One task gates five — the sediment
proxy is unanchored and returns `0.0`, and exposure is a product, so every reef zone
reads `minimal` until it is anchored.

---

## The spatial contract — read before touching any download

**Two extents, not one.** Defined once in `backend/src/config/spatial.py`.
**Never write a bounding-box literal anywhere else** —
`tests/test_spatial_contract.py` fails the build if you do.

```python
from config.spatial import TERRAIN_AOI, MARINE_AOI, CRS_MEASURE

TERRAIN_AOI = 34.75, 29.15, 35.94, 30.30   # land: DEM, hydrology, rainfall,
                                           #       land cover, soil
MARINE_AOI  = 34.80, 29.25, 35.05, 29.60   # sea: currents, bathymetry,
                                           #      imagery, reef zones
```

Ask the box for the ordering the API wants — never reorder by hand:
`.wsen` (Harmony, shapely, rasterio) · `.cds_area` (CDS wants N,W,S,E) ·
`.nwse`.

> **A retired box, `(34.80, 29.25, 35.15, 29.70)`, is still in old raw files.**
> It cut off ~85 % of Wadi Yutum. Nothing errored — the downloads just covered
> the wrong area. Run `python scripts/check_aoi_coverage.py` before trusting any
> per-catchment aggregate computed from pre-3-Aug data.

**CRS:** EPSG:4326 for storage/exchange/PostGIS. **EPSG:32636 (UTM 36N) for
every area, distance and slope.** An area in km² computed from degrees is wrong.

## The ID contract

Join keys. **Never renamed** — renaming one breaks every stored result.

| Entity | Format | Owner |
|---|---|---|
| Catchment | `AQ-C01`…`AQ-C05` | Mahdi |
| Outlet | `AQ-O01`…`AQ-O05` | Mahdi |
| Reef zone | `R-01`…`R-08` | Pulga |
| Event | `AQ-YYYY-MM-DD` | Karam |
| Simulation run | `sim_{ULID}` | Nizar |

Geometry is settled: 5 catchments, 4,656 km², `AQ-C01` = Wadi Yutum at
**4,453 km² ±4%**, reaching ~90 km inland. `AQ-O01` carries **96 % of
discharge**. ~2,000 km² of the system is **endorheic** — drains to internal
sinks, never reaches the Gulf — and is excluded on purpose; do not add it back
from HydroBASINS `UP_AREA`.

> **`AQ-O04` discharges into an enclosed harbour basin.** A plume released
> there settles in the basin. Do not demo it without saying so.

## Event timing

`docs/event_dates.md` is the **single source of truth**. Rule 1: *never
hard-code an event date in a script* — parse it from that file's machine-
readable YAML block. A test greps for violations, ignoring comments.

Demo event `AQ-2016-10-28` (Oct 2016 Aqaba–Eilat flood, ~24,400 t sediment). It is
the **best-instrumented** documented flood, **not the biggest** — Kalman et al.
(2025) records February 2006 at ~10 kg/m² seafloor deposition against Oct 2016's
6 kg/m². Do not call it the largest.

February 2013 is **no longer dead**, corrected 5 Aug 2026. Still **no exact day**,
so satellite matching remains impossible — and it predates usable Sentinel-2 and
Landsat 8 anyway — but its **mass is confirmed at 21,000 t** (Katz et al. 2015b,
quoted in the open-access Kalman 2025), which is 86 % of the demo event. Usable for
**sediment-mass validation**, not for imagery. Two IMERG candidates are narrowed in
`docs/event_dates.md`.

**Thirteen sea-reaching floods exist since 1994** and we hold one date. The other
twelve are in two paywalled papers — `docs/karam_handoff.md` Request 0. Any harness
must report honestly against a partial list rather than score against n=1 and call
it validation.

Always convert local time with `ZoneInfo("Asia/Jerusalem")`, never a fixed
offset — Oct 2016 falls inside IDT (UTC+3), not IST.

---

## Non-negotiable data rules

These are why the Phase 1 work is trustworthy. They do not lapse.

1. **Missing is never zero, and nothing is interpolated.** A gap is reported.
2. **No fabricated geometry.** If an input is absent, skip the step and record
   the skip — see `catchment_integration_status.json`.
3. **Provisional data is named `*_PROVISIONAL`**; every swap is tracked in
   `tasks/00-contracts.md` §5. Day-12 gate: `grep -ri PROVISIONAL`.
4. **Every claim has evidence.** Processing scripts *assert*; QA scripts
   *visualise*. No figure and no test means assumed, not verified.
5. **Source vs derived is labelled.** A paper-reported number, a
   timezone-converted number and a computed number are three different things.
6. **Provenance in `docs/data_dictionary.md`** — product ID, version, access
   date, licence, known limitation. It drives the UI's Data Sources panel.
7. **Never claim exactness.** The Gulf is narrower than three cells of the best
   free ocean model. Output probabilistic exposure zones with stated confidence.

## The label rule

**ERA5-Land `sro`/`ssro` are LABELS. They are never features.** A target that
is also an input produces a model that scores ~0.99 and predicts nothing.
`scripts/build_feature_matrix.py` raises if a runoff column reaches the feature
set; the antecedent output prefixes them `label_`.

**The rule was not enough, and this is the most important correction in this file**
(Mahdi, 4 Aug; `reports/model/label_problem.md`). Excluding the runoff columns does
not remove the leak, because the label is **near-deterministic in ERA5's own
rainfall** — `corr(sro, ERA5 rain) = +0.985` while `corr(ERA5, IMERG) = +0.573`. So
*any* ERA5-sourced feature (`swvl1`, `u10`, `v10`, `t2m`) leaks the same atmosphere
the target came from. Measured by source product, LOCO AP:

| features | AP |
|---|---|
| IMERG + neutral only, **no ERA5 at all** | **0.662** ← the defensible number |
| shipped CD− set (20 cols) | 0.744 |
| **one column** of ERA5's own rainfall | 0.978 |

**Quote 0.662, not 0.741**, for "predicts runoff from independent inputs".

Two consequences that must not be lost:

1. **The label is not "reached the sea".** It is ERA5-Land runoff *generation*. Ours
   fires on 3.21 % of calendar days against the literature's 0.156 % — **21× too
   generous**, and that 21× is a floor: it assumes every unsampled day is a
   non-event. On days we actually sampled it is **78×**.
2. **The label is blind where ERA5 is blind.** ERA5 is essentially dry on 35 % of
   IMERG-wet days, and on 20 % of the heaviest IMERG days in the record. Of 276
   catchment-days where IMERG saw >1 mm and ERA5 saw nothing, `target` is positive on
   **one**. October 2016 is among the misses — 0.77 mm and p92.6 in ERA5 against
   9.58 mm and p99.5 in IMERG. A **detection** failure, not a scaling one, so no
   threshold tuning fixes it.

---

## Gotchas that have already cost real time

Each of these produced **plausible, wrong output with no error**. That is the
failure mode this project keeps hitting.

| Trap | What happens |
|---|---|
| **Harmony auto-pauses large jobs** | It previews a couple of granules, sets status `previewing`, then pauses. `wait_for_processing` returns happily and you download **1 file of 365 and report success**. Always pass `skip_preview=True` and check the final job state. |
| **IMERG daily vs half-hourly units** | Daily is **mm/day**, half-hourly is **mm/hr**, and the daily variable is `precipitation` with **no `Grid/` prefix**. Applying the half-hourly rule understates depth 48×. Both terms come from `IMERG_PRODUCTS`; never a literal. |
| **Resume matches on FILENAME** | A granule fetched over the wrong extent has the same name as the right one, so resume skips it and the dataset silently mixes two extents. Move the old directory aside before re-fetching. |
| **CDS rejects concurrent jobs** | It does not queue the surplus. 10 workers → 20 consecutive 400s. Use **2**. Killing a sweep **orphans** its accepted jobs, which hold the quota; `scripts/run_era5_sweep.sh` waits for capacity. |
| **CDS refuses whole-year requests** | `403 cost limits exceeded`. Monthly is the largest granularity for 7 variables. |
| **ERA5 GRIB quantisation** | Real CDS data carries negative increments ~1e-8 m. The module default tolerance of `1e-10` is too tight — pass `negative_tolerance_m=1.0e-7`. See `docs/era5_land_accumulation_semantics.md` §7. |
| **ERA5 accumulations reset daily at 00 UTC** | The 00 UTC value is the **previous** day's 24-h total. Never sum raw `tp`/`sro`/`ssro`. |
| **ERA5/IMERG grids are not index-aligned** | Both 0.1°, centres offset half a cell. Combine only by area-weighted overlap. |
| **ERA5-Land is land-only** | Sea cells are permanently NaN. They contribute to neither numerator nor denominator — never averaged in as zero. |
| **`config` import root** | `scripts/config.py` was deleted (OPEN-ISSUES #23) and `backend/src/config/` is a package, so `from config.spatial import X` needs `backend/src` on `sys.path` — `tests/conftest.py` does it once. Adding `scripts/` to the path makes any flat `config.py` shadow the package and breaks five test files at collection. |
| **Tests can pass while the product is dead** | The suite was 482-green while `docker compose up` started nothing: tests imported `backend.src.api.main`, the container runs `--app-dir /app/backend/src`, and `from ..exposure import` resolves under the first and not the second. `tests/test_api_startup.py` now imports the app the way the container does. A green suite is not evidence the stack runs. |
| **Storms cross midnight** | One storm is two days in a daily record. Merge consecutive wet days *before* ranking, or the same storm lands in both train and test. Literature IDs win the naming. |
| **Supabase direct host is IPv6-only** | `db.<ref>.supabase.co` has an AAAA record only. Use the **pooler** (IPv4), username `postgres.<project_ref>`. |
| **`pytest \| tail` masks failures** | The pipeline's exit status is `tail`'s. Never gate a push on `pytest ... \| tail && git push`. |

---

## Commands

```bash
source .venv/bin/activate
pytest -q                                   # 453 pass, 47 skip (git-ignored raw data
                                            #   absent: IMERG granules, baked basemap,
                                            #   SoilGrids — each skip names its script)

python scripts/check_aoi_coverage.py        # which files are short of their AOI

# stage 1 — daily screening over the whole record
./scripts/run_daily_sweep.sh
python scripts/aggregate_daily_to_catchments.py
python scripts/build_event_catalogue.py     # -> events.parquet

# stage 2 — half-hourly intensity for the selected storms
python scripts/sweep_imerg_halfhourly.py --dry-run
python scripts/sweep_imerg_halfhourly.py --literature      # documented events only
python scripts/rank_events_by_intensity.py

# ERA5-Land — antecedent state and labels
./scripts/run_era5_sweep.sh                 # capacity-gated supervisor
python scripts/extract_event_antecedents.py

python scripts/build_feature_matrix.py      # the table the model trains on
python scripts/analyse_ordering_anomaly.py
```

Long downloads: always `nohup ... &`, always resumable, and check a **process
is alive** rather than trusting a log line — a stalled process looks healthy.

**No root-level dependency manifest, and that's deliberate, not an oversight (Phase 5,
A1.4).** Three real ones exist per-service — `backend/requirements-api.txt`,
`backend/requirements-worker.txt`, `frontend/package.json` — because the API and worker
images are intentionally different sizes (`backend/Dockerfile`'s own comment: the api
image stays small and rebuilds fast; the worker carries the heavier geospatial/simulation
stack). A single root `pyproject.toml`/`requirements.txt` merging both would either bloat
the api image back up or require the same two-file split duplicated one level up. For
local dev (not a container), install both: `pip install -r backend/requirements-api.txt
-r backend/requirements-worker.txt`.

## Layout

```
backend/src/config/spatial.py        THE spatial contract
backend/src/ingestion/              imerg, era5_land, gfs, gefs, ecmwf, ocean_currents
backend/src/processing/             catchment_rainfall, antecedent_features, event_mining
backend/src/models/                 plume_segmentation, runoff model
scripts/                            61 CLI entry points; 00-10_* are Mahdi's hydrology chain
tasks/00-contracts.md               Phase 1 contract (IDs, paths, CRS)
tasks/phase3/                       CURRENT — Phase 3 plan + per-person task files
tasks/phase2/                       previous phase, kept for context
backend/src/rendering/              plume drawn on real satellite imagery, never generated
docs/plume_imagery_decision.md      what we generate and what we never generate
docs/event_dates.md                 event timing, machine-readable
docs/data_dictionary.md             provenance ledger
docs/ali/                           market/prior-art research — NOT an app surface, NOT in RAG
data/processed/{vectors,features,events}/   committed contract paths
data/raw/                           git-ignored, reproducible
```

`data/processed/` is committed **except** rasters and per-event outputs — see
`.gitignore`. Never commit `.env`.

## Ownership

| Owner | Workstream |
|---|---|
| **Karam** | Integration lead + rainfall/reanalysis pipeline |
| **Mahdi** | Terrain, hydrology, the runoff model, Docker |
| **Nizar** | Supabase (Postgres + PostGIS), forecasts, currents |
| **Pulga** | Backend (FastAPI), exposure engine, RAG |
| **Abd** | Satellite/plume, particle engine, mooring calibration |
| **Ali** | Frontend (React + MapLibre), bilingual AR/EN |

Nizar's schema is already specified in `data-model.md` — **transcribe it, do not
redesign it**.

## What is machine-learned, and what is not

Only the **runoff classifier** is trained. The sediment proxy and exposure score
are formulas; plume transport is physics with parameters fitted to the mooring;
the LLM layer explains and retrieves and **never computes a number**. Describe
it as *hybrid physics-informed* — implying end-to-end deep learning loses the
Q&A.

Validation must be **leave-one-catchment-out** *and* a temporal holdout (train
≤2014). Static features are constant per catchment, so random CV memorises
catchment identity and reports a meaningless score.

## Validation reality

**Satellite validation of the demo event is a NO-GO** — measured, not assumed.
The plume dispersed ~31 h after arrival; the only usable passes are +104 h and
+128 h. Two sensors, no plume.

The replacement is stronger: the **Kalman et al. (2025) mooring**, 250 m
offshore the Kinnet Canal at 13 m depth, sampling every 5 minutes. Salinity
−1.75 ‰ (19σ), turbidity peak 2.18 g/L, elevated ~31 h. Calibrate against that
time series, not a hand-drawn mask.
