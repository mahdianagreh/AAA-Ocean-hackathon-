# AQABA AQUA AI Pipeline Capability Report

What the rainfall and land-reanalysis pipeline can do, what it has been proven
to do, and what remains. Written against the generic (event-agnostic) pipeline.

---

## 1. Baseline (before the generalisation work)

Captured at the start of the master task.

| Item | Value |
|---|---|
| Branch | `main` |
| Tests passing | **151** |
| Data files on disk | 174 |
| Modified tracked files | none |
| Untracked paths | `.env.example`, `.gitignore`, `backend/`, `docs/`, `scripts/`, `src/`, `tests/` |
| Catchment GeoPackages | **absent** — `data/processed/vectors/` does not exist |

### Modules present at baseline

| Module | Size | Role |
|---|---|---|
| `backend/src/ingestion/imerg.py` | 29,252 B | IMERG search, Harmony subset download, reader, rolling accumulations |
| `backend/src/ingestion/era5_land.py` | 28,708 B | ERA5-Land request builder, download, reader, deaccumulation |
| `backend/src/processing/catchment_rainfall.py` | 31,066 B | Area-weighted catchment aggregation |

### Data present at baseline

| Path | Contents |
|---|---|
| `data/raw/imerg/events/AQ-2016-10-28/` | 156 Harmony NetCDF granules (Oct 2016 event window) |
| `data/raw/imerg/event_smoke_3h/` | 6 granules |
| `data/raw/imerg/harmony_smoke_test/` | 1 granule |
| `data/raw/imerg/smoke_test/` | 1 global HDF5 (the only global file, from an early diagnostic) |
| `data/raw/era5_land/smoke_test/` | 1 single-variable hour |
| `data/raw/era5_land/multivariable_smoke/` | 1 seven-variable 6-hour file |
| `data/raw/era5_land/deaccumulation_validation/` | 3 files (2016-10-26, -27, -28T00) |
| `data/processed/events/` | IMERG event NetCDF + summary, ERA5 hourly NetCDF + summary, 3-hour smoke NetCDF |

### Safety verification

| Check | Result |
|---|---|
| `data/raw/` ignored | ✓ |
| `data/processed/` ignored | ✓ |
| `data/outputs/` ignored | ✗ at baseline → **rule added** before any output was written |
| `.env` ignored | ✓ |
| `.venv/` ignored | ✓ |
| Tracked `.nc` / `.nc4` / `.HDF5` / `.parquet` files | **0** |
| `~/.cdsapirc` inside repository | **No** — lives in `$HOME`, and `.gitignore` also lists `.cdsapirc` |
| Credentials printed or inspected | None |

Files deliberately **not** modified anywhere in this work: `.env`,
`.env.example`, `~/.cdsapirc`, `~/.netrc` (which does not exist), and every
existing raw smoke-test file.

---

*Sections 2 onward are appended as each phase completes.*

## 2. What the pipeline can retrieve

| Capability | Status | Evidence |
|---|---|---|
| Arbitrary UTC time range | **Yes** | `fetch_imerg_window` / `fetch_era5_land_window` take any hour-aligned UTC bounds; tests cover 2016 and 2020 windows |
| Arbitrary bounding box | **Yes** | box is a config value; tested with `[-10, 40, -9, 41]` as well as Aqaba |
| IMERG Final Run | **Yes** | 156-granule Oct 2016 window, 100 % complete |
| IMERG Early Run | **Yes** | live retrieval 2026-08-01, 6.1 h latency |
| ERA5-Land hourly | **Yes** | 7 variables, multi-day windows, daily chunking |
| Rolling accumulations | **Yes** | any set of whole 0.5 h multiples; 1/3/6/24 h proven |
| Antecedent features | **Yes** | 19 gridded features for any event timestamp |
| Config-driven execution | **Yes** | `--dry-run` and `--offline-process-only` both proven |
| Candidate mining | **Yes** (non-exhaustive) | schema proven; `is_exhaustive=false` |
| Catchment aggregation | **Blocked** | needs `catchments_PROVISIONAL.gpkg` (task P1) |

### Supported temporal ranges

IMERG Final 2000-06 → ~3.5 months ago; IMERG Early → ~6 h ago (measured);
ERA5-Land 1950 → ~5 days ago. Guards: `max_granules` (default 500) and
`max_expected_timestamps` (default 2000) abort **before** submission.

### Supported geographic configuration

Any valid box. `spatial` uses plain west/south/east/north and is converted to
each API's order automatically — Harmony `(W, S, E, N)`, CDS `[N, W, S, E]`.
Order mistakes are a classic silent failure; the config owns the conversion.

### Supported variables

IMERG: `Grid/precipitation` only (deliberate — variable subsetting keeps
transfers ~175× smaller). ERA5-Land: all seven registry variables.

### Final vs Early distinction

Separate collection IDs, separate output directories, and every processed file
carries `imerg_run_type`, `preliminary`, `calibrated_final_product` and
`suitable_for_training`. A single config yields exactly one run type, so mixing
is structurally unrepresentable. Candidate mining penalises Early quality
scores and can split tables by run type.

### Output formats

NetCDF4 (gridded), Parquet (tabular features and candidates), JSON (summaries
and manifests).

## 3. Example commands

```bash
# plan only — no downloads, no writes
python scripts/run_event_pipeline.py --config configs/october_2016_demo.yaml --dry-run

# reuse local raw files, process and export
python scripts/run_event_pipeline.py --config configs/october_2016_demo.yaml --offline-process-only

# arbitrary ERA5-Land window over an arbitrary box
python scripts/fetch_era5_land_window.py \
  --start 2016-10-27T00:00:00Z --end 2016-10-27T05:00:00Z \
  --north 29.70 --west 34.80 --south 29.25 --east 35.15 \
  --variables soil_moisture,total_precipitation \
  --output-dir data/raw/era5_land/example_window

# antecedent features for any event time
python scripts/extract_antecedent_features.py \
  --input data/processed/events/era5_land_hourly_20161026_20161027.nc \
  --event-time 2016-10-28T00:00:00Z --event-id AQ-2016-10-28 --allow-partial

# near-real-time Early Run proof
python scripts/run_imerg_early_demo.py

# candidate table
python scripts/build_rainfall_candidates.py
```

## 4. Known scientific limitations

1. **ERA5/IMERG grid misalignment.** Both 0.1°, both 5×4 here, but cell centres
   are offset by half a cell. Index pairing is wrong and is never performed.
2. **IMERG resolution.** ~11 km cells smooth localized convective storms — the
   exact mechanism behind Aqaba flash floods.
3. **ERA5-Land sea mask.** 3 of 20 cells permanently NaN; never interpolated.
4. **Non-exhaustive candidate scope.** `is_exhaustive=false` on every row.
5. **GRIB quantisation.** Negative increments at −7.45e−9/−1.49e−8 m require a
   1e-7 m tolerance, not the 1e-10 m float64 default.
6. **Early Run gaps.** A granule may simply not exist yet (07:00 UTC on
   2026-08-01). Reported, never interpolated.
7. **Oct 2016 ordering anomaly.** The derived rainfall peak falls *after* the
   documented flood arrival — most likely because the generating catchments lie
   outside this box. Unresolved until real catchments exist.

## 5. Catchment integration status

**SKIPPED_MISSING_DEPENDENCY.** Neither `catchments.gpkg` nor
`catchments_PROVISIONAL.gpkg` exists; `data/processed/vectors/` was never
created. Task P1 (`tasks/00-contracts.md`, Mahdi, ~1 h, HydroBASINS level 9)
owns it. The aggregation pipeline is fully built and tested against synthetic
geometry (31 tests) and runs unchanged once the file lands. **No polygon was
fabricated** — 0 GeoPackages exist in the project.

## 6. What remains for operational deployment

- Real catchment polygons (P1) → catchment-level rainfall and features.
- Full historical sweep to make candidate mining exhaustive.
- Scheduling/orchestration for recurring Early Run ingestion.
- Late Run (`GPM_3IMERGHHL`, `C2723754845-GES_DISC`) if a middle-latency
  product is wanted; resolved from CMR but deliberately not added.
- Provenance beyond config content (dataset checksums, run IDs).
