# Master Task Summary — Generic ReefShield Rainfall & Land-Reanalysis Pipeline

Completed 2026-08-01. All 10 phases executed sequentially.

**Final verdict: PARTIAL GO** — the core pipeline is fully GO; catchment
integration is blocked on a teammate dependency that was never fabricated.

---

## 1. Test counts

| Stage | Tests |
|---|---|
| Baseline | **151** |
| Final | **272** |
| Added | **+121** |

All 272 pass in ~1.5 s. Every suite is offline: socket guards assert no network
access during processing tests, and `cdsapi.Client.retrieve` is never called.

| Suite | Tests |
|---|---|
| `test_era5_land_ingestion.py` | 91 |
| `test_imerg_ingestion.py` | 66 |
| `test_event_pipeline_config.py` | 38 |
| `test_catchment_rainfall.py` | 31 |
| `test_antecedent_features.py` | 25 |
| `test_event_mining.py` | 21 |

## 2. Modules and functions added

**`backend/src/ingestion/era5_land.py`** — `normalize_era5_land_fluxes`,
`infer_temporal_semantics`, `fetch_era5_land_window`,
`validate_era5_land_window`, `_chunk_bounds`, `ERA5LandTemporalSemanticsError`,
`FLUX_HOURLY_M_NAMES`, `DEFAULT_MAX_EXPECTED_TIMESTAMPS`.

**`backend/src/ingestion/imerg.py`** — `IMERG_PRODUCTS` registry,
`get_imerg_product`, `fetch_imerg_window`, `process_imerg_window`,
`wettest_windows`, `expected_granule_count`, `expected_granule_timestamps`,
`granule_timestamp_from_name`, `existing_granules`,
`missing_granule_timestamps`, `IMERGProductError`. `download_imerg_subset` now
takes `collection_id` / `variable`.

**`backend/src/processing/antecedent_features.py`** *(new)* —
`extract_antecedent_features`, `antecedent_features_to_dataframe`,
`WIND_DIRECTION_CONVENTION`, `AntecedentFeatureError`.

**`backend/src/processing/event_mining.py`** *(new)* —
`rank_rainfall_candidates`, `separate_by_run_type`, `EventMiningError`.

**`backend/src/config/event_pipeline.py`** *(new)* — `EventPipelineConfig`,
`Spatial`, `ImergConfig`, `Era5LandConfig`, `AntecedentConfig`,
`OutputsConfig`, `ValidationConfig`, `load_event_pipeline_config`, `ConfigError`.

## 3. Scripts and configs created

`scripts/fetch_era5_land_window.py`, `scripts/extract_antecedent_features.py`,
`scripts/run_event_pipeline.py`, `scripts/run_imerg_early_demo.py`,
`scripts/build_rainfall_candidates.py`,
`scripts/validate_era5_land_deaccumulation.py`.

`configs/event_pipeline.example.yaml`, `configs/october_2016_demo.yaml`,
`configs/imerg_early_live_demo.yaml`.

## 4. IMERG Final capabilities proven

- Registry entry verified through CMR **and** Harmony capabilities:
  `GPM_3IMERGHH` v07, `C2723754847-GES_DISC`, bbox + variable subsetting true.
- 156-granule Oct 2016 window, **100 % complete**, reprocessed offline.
- Arbitrary window and bbox: granule-count maths tested for 2016 and 2020
  windows and a `[-10, 40, -9, 41]` box.
- Safety limit aborts before submission; chunking, resume and idempotency proven.
- Wettest windows (identical to the hand-built Task 16 run):

| Window | Max | UTC span |
|---|---|---|
| 1 h | 6.7600 mm | 2016-10-28T02:00Z → 03:00Z |
| 3 h | 11.7150 mm | 2016-10-28T02:30Z → 05:30Z |
| 6 h | 12.9900 mm | 2016-10-28T00:00Z → 06:00Z |
| 24 h | 20.5450 mm | 2016-10-27T05:30Z → 2016-10-28T05:30Z |

## 5. IMERG Early capabilities — **GO**

- Collection resolved from CMR (not guessed): `GPM_3IMERGHHE` v07,
  `C2723758340-GES_DISC`; Harmony capabilities verified.
- Latest availability resolved from metadata, not wall clock.
- Measured **2026-08-01T14:06Z**: latest granule 08:00 UTC → **6.12 h latency**.
- Retrieved 5 of 6 requested granules; **07:00 UTC granule genuinely missing**
  (83.33 % window completeness). Gap reported, longest contiguous 3-granule run
  processed, nothing interpolated.
- Output: `data/processed/live/imerg_early_latest.nc` (52.3 KB) with
  `run_type=early`, `preliminary=true`, `suitable_for_training=false`.
  No Final Run file touched.

## 6. ERA5-Land capabilities proven

Seven variables, arbitrary windows, daily chunking that keeps CDS's
`year × month × day × time` product exact, resume, and structural validation
(timestamp count, uniqueness, hourly spacing, variables present, spatial subset,
common grid).

## 7. ERA5 temporal semantics — verified, not assumed

| Evidence class | Finding |
|---|---|
| **File metadata** | `tp`/`sro`/`ssro` → `GRIB_stepType='accum'`, `GRIB_dataType='fc'`; `swvl1` → `stepType='instant'`, `dataType='an'` |
| **Official docs** | ECMWF: accumulations run 00 UTC → forecast step; "For the CDS time of 00 UTC, the accumulations are over the 24 hours ending at 00 UTC i.e. during the previous day" |
| **Observation** | Recorded but **explicitly excluded as evidence** — a dry window makes an accumulated field look flat |
| **Assumptions** | interval-end labelling; unresolvable first interval → NaN; caller-supplied negative tolerance |
| **Unresolved** | sub-hourly requests, `expver`/`number` semantics, other delivery formats |

`mode="auto"` reads metadata only and raises `ERA5LandTemporalSemanticsError`
rather than guessing. Documented in `docs/era5_land_temporal_semantics.md`.

## 8. Antecedent features

19 gridded features for any event timestamp: soil-moisture lags, 24/72/168 h
precipitation and runoff totals, event-time wind (speed + meteorological
direction), temperature, trailing state means, per-feature valid fractions and a
quality flag. Windows and offsets are all arguments.

Example run (`AQ-2016-10-28`, 20 cells): `precipitation_prior_24h_mm`
0.0561–0.7930 mm; flags `{NO_DATA: 3 (sea), PARTIAL_WINDOW: 17}` — honest,
because a 48 h ERA5 window cannot fill a 168 h lookback.

## 9. Config-driven pipeline — working

`--dry-run` prints a credential-free plan with pre-download estimates (156
granules, ~4 Harmony jobs, 49 timestamps, ~3 CDS requests).
`--offline-process-only` reprocessed the whole event from local files with
**0 downloads, 156 reused**.

A test asserts the string `AQ-2016-10-28` appears **nowhere** in the config
source — the event lives only in YAML.

## 10. Candidate mining

`data/processed/events/rainfall_candidates.parquet` — 1 row, 20 columns,
full contract schema.

| event_id | peak_time_utc | rain_3h_mm | rain_24h_mm | percentile | anomaly | run_type | quality |
|---|---|---|---|---|---|---|---|
| GPM_3IMERGHH | 2016-10-28T05:00:00Z | 11.715 | 20.545 | 100.0 | 3.27 | final | 1.0 |

**`is_exhaustive = false`** on every row, with scope
`2016-10-25T00:00:00Z .. 2016-10-28T05:30:00Z`.

## 11. Catchment integration — SKIPPED_MISSING_DEPENDENCY

Neither `catchments.gpkg` nor `catchments_PROVISIONAL.gpkg` exists;
`data/processed/vectors/` was never created. Owner: task P1
(`tasks/00-contracts.md`). **0 GeoPackages exist in the project** — the 5 found
by `find` are `pyogrio` test fixtures inside `.venv`. Status recorded in
`data/processed/events/catchment_integration_status.json`. Non-blocking.

## 12. Example outputs

| Path | Size |
|---|---|
| `data/processed/events/AQ-2016-10-28/AQ-2016-10-28_imerg.nc` | 126.3 KB |
| `data/processed/events/AQ-2016-10-28/AQ-2016-10-28_era5_land.nc` | 166.1 KB |
| `data/processed/events/AQ-2016-10-28/AQ-2016-10-28_antecedent_features.parquet` | 21.6 KB |
| `data/processed/events/AQ-2016-10-28/AQ-2016-10-28_summary.json` | — |
| `data/outputs/AQ-2016-10-28/AQ-2016-10-28_manifest.json` | — |
| `data/processed/events/rainfall_candidates.parquet` | 12.5 KB |
| `data/processed/live/imerg_early_latest.nc` | 52.3 KB |
| `data/raw/era5_land/example_window/…nc` | 33.4 KB |

## 13. Data completeness and quality findings

- IMERG Oct 2016: **100 %** (156/156), 0 missing cells.
- IMERG Early live: **83.33 %** — one granule genuinely absent.
- ERA5-Land: 17 land cells, **3 permanent sea-mask cells**, mask identical
  across all seven variables, never interpolated.
- Antecedent: 17 `PARTIAL_WINDOW` (168 h window vs 48 h data), 3 `NO_DATA` (sea).
- GRIB quantisation: 11 of 1632 increments negative at exactly 2⁻²⁷/2⁻²⁶.

## 14. Documentation

`docs/pipeline_capability_report.md` (baseline + capabilities + limits),
`docs/data_dictionary.md` (IMERG Final, IMERG Early, ERA5-Land, derived
features, candidates, CHIRPS-not-executed), `docs/era5_land_temporal_semantics.md`,
`docs/era5_land_accumulation_semantics.md`, `docs/data_access_setup.md`
(refreshed), `README.md` (new), `notebooks/01_event_mining.ipynb` (18 cells,
executes offline — verified with nbconvert).

## 15. Validation results

- **272 tests pass.**
- **180 NetCDF files** reopened; **3 project Parquet** files; **990 JSON** files
  parse. **Zero problems.**
- No duplicate timestamps, correct spacing, UTC internal times, correct units,
  no Final/Early mixing, no index merging, no missing-as-zero, no interpolation.
- Secret scan: **no credential values** anywhere. All keyword hits are variable
  names, sanitiser denylists, test assertions or docs. No signed URLs stored.

## 16. Files modified / created

**Modified:** `backend/src/ingestion/era5_land.py`,
`backend/src/ingestion/imerg.py`,
`backend/src/processing/antecedent_features.py`,
`backend/src/processing/event_mining.py`, `tests/test_era5_land_ingestion.py`,
`tests/test_imerg_ingestion.py`, `.gitignore` (added `data/outputs/`),
`docs/data_access_setup.md`.

**Created:** 5 backend modules/packages, 6 scripts, 3 configs, 3 test files,
1 notebook, 4 docs, `README.md`.

## 17. Downloaded vs reused

**Downloaded this task:** 6 ERA5-Land hours (example window, 33.4 KB) + 5 IMERG
Early granules (~250 KB). **Reused:** all 156 IMERG Oct 2016 granules, 3 ERA5
deaccumulation files, 6 smoke granules. **No global HDF5 downloaded** — the
single 7,924,327-byte file predates this task and is untouched.

## 18-19. Nothing committed, no credentials exposed

`git status` shows only untracked source/doc directories; **0 tracked data
files**. `.env` (1512 B), `.env.example` (40 B), `tasks/00-contracts.md`
(11027 B) and `~/.cdsapirc` (mode 600, 85 B) all unchanged; `~/.netrc` does not
exist. `data/outputs/` was added to `.gitignore` **before** any output landed.

## 20. Remaining blockers and limitations

1. **Catchment polygons (P1)** — the only hard blocker.
2. **Candidate mining is non-exhaustive** — demo windows only.
3. **Oct 2016 ordering anomaly** — derived rainfall peak falls *after* the
   documented flood arrival; likely because generating catchments lie outside
   this box. Unresolved until (1).
4. **ERA5/IMERG grid misalignment** — combine only by area-weighted overlap.
5. **IMERG ~11 km cells** smooth the convective storms that drive these floods.
6. **Early Run is preliminary** and can have gaps.
7. **Two credentials remain exposed in the session transcript** and should be
   rotated: the Earthdata password and the CDS token.

## 21. Final verdict — PARTIAL GO

Every GO criterion is met: arbitrary time range ✓, arbitrary bbox ✓, IMERG
Final ✓, ERA5-Land retrieval + antecedent extraction ✓, config-driven execution
✓, rolling rainfall ✓, candidate schema ✓, tests pass ✓, documentation ✓.
IMERG Early is additionally **GO**.

**PARTIAL** solely because catchment integration is blocked on a file that does
not exist and was correctly not fabricated. The core pipeline is production-ready
and event-agnostic.
