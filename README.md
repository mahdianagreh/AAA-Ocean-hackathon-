# ReefShield Aqaba — Rainfall & Land-Reanalysis Pipeline

Event-agnostic retrieval and processing of NASA GPM IMERG precipitation and
Copernicus ERA5-Land reanalysis for wadi-to-reef sediment forecasting.

The pipeline is **configuration-driven**: an event is described by a YAML file,
not by code. October 2016 is one example configuration and regression case, not
a requirement baked into any function.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install earthaccess harmony-py cdsapi xarray netCDF4 h5py numpy pandas \
            geopandas shapely pyproj pyarrow pydantic pyyaml pytest

cp .env.example .env && chmod 600 .env      # NASA Earthdata credentials
# CDS credentials go in ~/.cdsapirc (outside the repo) — see docs/data_access_setup.md

pytest -v
python scripts/run_event_pipeline.py --config configs/october_2016_demo.yaml --dry-run
```

## Running an event

```bash
# plan only, no downloads
python scripts/run_event_pipeline.py --config configs/my_event.yaml --dry-run

# process from local raw files, no network
python scripts/run_event_pipeline.py --config configs/my_event.yaml --offline-process-only

# full run: fetch what is missing, then process
python scripts/run_event_pipeline.py --config configs/my_event.yaml
```

Start from `configs/event_pipeline.example.yaml` — every option is annotated.
Changing only the YAML runs a different event, box and time range.

## Layout

```
backend/src/ingestion/imerg.py            IMERG products, retrieval, rolling accumulations
backend/src/ingestion/era5_land.py        ERA5-Land requests, reader, temporal normalisation
backend/src/processing/antecedent_features.py  pre-event predictors
backend/src/processing/catchment_rainfall.py   area-weighted catchment aggregation
backend/src/processing/event_mining.py    rainfall candidate ranking
backend/src/config/event_pipeline.py      typed YAML configuration
configs/                                  event configurations
scripts/                                  CLI entry points
notebooks/01_event_mining.ipynb           offline exploration
docs/                                     capability report, data dictionary, semantics
```

Data lives under `data/` and is **git-ignored** — raw, processed and outputs.

## Products

| Product | Collection | Run type | Training-safe | Latency |
|---|---|---|---|---|
| GPM IMERG V07 Final | `C2723754847-GES_DISC` | `final` | Yes | ~3.5 months |
| GPM IMERG V07 Early | `C2723758340-GES_DISC` | `early` | **No** | ~6 h (measured) |
| ERA5-Land Hourly | `reanalysis-era5-land` | reanalysis | Yes | ~5 days |

Final and Early are separate collections written to separate directories, and
every output records `imerg_run_type`. They are never mixed.

## Things that will bite you

- **ERA5-Land and IMERG grids are not index-aligned.** Both 0.1°, both 5×4 over
  Aqaba, cell centres offset by half a cell. Combine only by area-weighted
  overlap — never by array index.
- **ERA5-Land accumulations reset daily at 00 UTC**, and the 00 UTC value is the
  *previous* day's 24-hour total. Never sum raw `tp`/`sro`/`ssro`.
- **ERA5-Land is land-only.** Sea cells are permanently NaN and are never filled.
- **Missing is never zero** anywhere in this pipeline, and nothing is interpolated.
- **Two one-time approvals** are required: the NASA GES DISC application and the
  ERA5-Land licence. Both block downloads while unaccepted.

## Documentation

| Document | Contents |
|---|---|
| `docs/pipeline_capability_report.md` | what the pipeline can do, limits, commands |
| `docs/data_dictionary.md` | every source, variable, unit and transformation |
| `docs/data_access_setup.md` | accounts, credentials, registration |
| `docs/era5_land_temporal_semantics.md` | evidence for the ERA5 temporal convention |
| `docs/era5_land_accumulation_semantics.md` | deaccumulation rules and worked example |
| `docs/event_dates.md` | event timing contract, source vs derived |

## Status

Catchment-level aggregation is built and tested but **blocked** on
`data/processed/vectors/catchments_PROVISIONAL.gpkg` (task P1). No polygons have
been fabricated.
