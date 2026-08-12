# ReefShield Aqaba — Data Model

**What this document answers:** for every data stream in the project — what data, *why the system cannot work without it*, the numbered steps that turn it into a database row, and where it ends up on disk or in Postgres.

**Sources:** `aqaba_aqua_ai_concept.md` §10 (components), §11 (sources), §12 (dataset), §18 (tables) · `tasks/00-contracts.md` (IDs, paths, CRS)

This document supersedes concept §18, which lists column *names* but no types, no keys, and is missing several tables the pipeline needs. Additions and changes are listed in §8.

**If you want the procedure only:** §3 gives per-stream steps (each step names what it reads and what it writes), and §7 orders every step in the sequence they actually run in, with the blockers marked.

---

## 1. The one architectural rule

Two stores, and the split is not negotiable:

| Store | Holds | Why |
|---|---|---|
| **Files** (`data/`, object storage) | Every pixel and every grid cell — rasters, weather cubes, ocean cubes, particle trajectories, model artifacts | Postgres is a terrible raster database. A 20-million-pixel land-cover tile is one file, not 20 million rows. |
| **PostgreSQL + PostGIS** | Every *thing you join on or ask a question about* — IDs, geometries small enough to draw, feature rows, model outputs, run parameters, metrics, provenance | The API serves joins, not arrays. `GET /catchments/AQ-C03` must be one query. |

**The bridge:** every heavy file has a row in `raster_assets` (or a `*_path` column) carrying its path, CRS, checksum, and the `data_sources.id` it came from. Nothing in `data/` is anonymous, and nothing in Postgres is a pixel.

Corollary that will come up: **particle positions never enter Postgres.** 5,000 particles × 48 timesteps × 300 calibration runs is 72M rows of data nobody queries individually. Trajectories go to Parquet; only the contoured probability polygons per timestep land in `plume_forecasts`.

---

## 2. Section → component → table map

| Section (owner) | Concept component | Primary tables written |
|---|---|---|
| Terrain & Hydrology (Mahdi) | B — catchment & flow | `catchments`, `outlets` |
| Rainfall & Reanalysis (Karam) | A — event detection · C — runoff | `events`, `catchment_rainfall`, `catchment_rainfall_climatology`, `event_catchment_features` |
| Land, Soil, Habitat, Bathymetry (Pulga) | C · D — sediment · G — exposure | `catchment_surface_features`, `reef_zones` |
| Imagery & Plume (Abd) | E — plume detection · validation | `satellite_scenes`, `observed_plumes` |
| Forecasts & Currents (Nizar) | A forecast mode · F — transport | `forecast_runs`, `forecast_catchment_rainfall`, `forecast_exceedance`, `simulation_runs`, `plume_forecasts` |
| Cross-cutting | D · G · H · §13 backtest | `data_sources`, `raster_assets`, `model_versions`, `runoff_predictions`, `reef_exposures`, `calibration_trials`, `backtests`, `backtest_metrics`, `alerts` |

---

## 3. Data needed, section by section

### 3.1 Terrain & Hydrology — Mahdi

**Data:** Copernicus DEM GLO-30 (30 m elevation raster, primary) · NASA SRTM 1″ (independent cross-check) · MERIT Hydro (90 m flow direction/accumulation) · HydroBASINS L9 (regional basin polygons)

**Why the system needs it.** Rainfall without terrain has no address. IMERG tells us 40 mm fell somewhere in a ~11 km cell; only the DEM tells us whether that water reaches the Gulf or dies in a closed depression 30 km inland. Two things come out of this stream and nothing else in the project can produce either:

1. **The catchment polygon** — the spatial unit *every other stream aggregates into*. Karam's rainfall, Pulga's land cover and soil, the runoff model's features: all of them are "mean/fraction inside `AQ-C03`". Change the polygon and every downstream number changes.
2. **The outlet point** — the single coordinate where the land model hands off to the ocean model. It is the particle release point in Component F and the origin for every distance-to-reef calculation. This is why the contracts doc puts a hard lock on it.

**How it is used — step by step.**

| # | Step | Reads | Writes |
|---:|---|---|---|
| 1 | Pull GLO-30 COG tiles covering `DOWNLOAD_BBOX` from the AWS mirror | — | `data/raw/cop_dem/` |
| 2 | Merge tiles → clip to AOI → reproject to EPSG:32636 | step 1 | `processed/dem/dem_utm36n.tif` + `raster_assets` |
| 3 | Condition the DEM — fill sinks or breach depressions | step 2 | `dem_filled.tif` |
| 4 | Flow direction, D8 or D-∞ | step 3 | `flowdir.tif` |
| 5 | Flow accumulation, and slope in degrees | steps 3–4 | `flowacc.tif`, `slope.tif` |
| 6 | Extract streams at an accumulation threshold; tune the threshold until the network matches wadis visible in imagery | step 5 | `vectors/streams.gpkg` |
| 7 | Place candidate pour points where streams meet the coastline; snap each to the max-accumulation cell within a small radius | steps 5–6 | **`outlets`** (`AQ-O01…`) with `snap_distance_m`, `method` |
| 8 | Delineate the watershed upstream of each outlet | steps 4, 7 | **`catchments`** (`AQ-C01…`), geom in 4326, `area_km2` computed in 32636 |
| 9 | Zonal terrain stats per catchment: mean/max slope, relief, drainage density, longest flow path, max flow accumulation, time of concentration | steps 5, 8 | columns on `catchments`, mirrored to `features/catchment_terrain.parquet` |
| 10 | Cross-check — repeat 3–8 on SRTM, compare outlet positions; overlay MERIT Hydro channels on the extracted streams. Commit to one DEM | SRTM, MERIT | `catchments.notes` (the reason), `is_provisional = false` |
| 11 | Clip HydroBASINS L9 for the context map layer | — | `vectors/hydrobasins_context.gpkg` — map only, never read by a model |

Steps 9–10 are the point of the whole stream: those per-catchment statistics become **static feature columns** joined into every training row at model-fit time. MERIT and HydroBASINS never enter the model.

**Storage.**
- Conditioned DEM, flow direction, flow accumulation, slope → `data/processed/dem/*.tif` (COG, EPSG:32636) + rows in `raster_assets`
- Catchment polygons → `catchments.geom` (PostGIS, EPSG:4326) and `data/processed/vectors/catchments.gpkg`
- Outlets → `outlets.geom` (Point, 4326)

**Watch:** GLO-30 is a *surface* model — buildings are in the elevation. Near the urban outlets it will route flow around structures that water actually goes past. The concept doc flags hand-correction; whatever is corrected must be recorded in `catchments.notes`, because the corrected DEM is no longer the published product.

---

### 3.2 Rainfall & Reanalysis — Karam

**Data:** GPM IMERG V07 Final (half-hourly, 2000→present) · IMERG Early/Late (near-real-time) · CHIRPS (daily, cross-check) · ERA5-Land (hourly: volumetric soil water L1, total precipitation, surface & sub-surface runoff, 10 m u/v wind, 2 m temperature)

**Why the system needs it.** This stream produces the **trigger variable** and the **labels**. The entire causal chain starts at "did/will it rain hard", so rainfall is not one feature among many — it is the input the system exists to react to.

Two non-obvious reasons the *long history* matters:

- **"Extreme" is only definable against history.** A fixed threshold in millimetres is somebody's guess. A catchment-specific 99th percentile is a measurement, and it needs ~25 years of half-hourly data to be stable. This is also what makes Component H's explanation defensible: "exceeds the catchment's historical 99th percentile" is a checkable claim.
- **Antecedent soil moisture is the main non-rainfall predictor, and it is nearly free.** It is the reason identical 40 mm produces a flood one week and nothing the next. ERA5-Land gives it at T−24 h and T−72 h at no extra acquisition cost.

The wind variables from ERA5-Land do double duty: antecedent state for the runoff model, and **windage forcing for the plume engine** during historical events (Nizar has no forecast wind for 2016).

**How it is used — step by step.**

| # | Step | Reads | Writes |
|---:|---|---|---|
| 1 | Authenticate `earthaccess` against NASA Earthdata | — | — |
| 2 | Query IMERG V07 Final granules, 2000→present, **with the bounding box in the request** | — | `data/raw/imerg/` |
| 3 | Open as one Xarray cube; verify units (mm/hr vs mm per step) and that timestamps are UTC | step 2 | `interim/imerg.zarr` |
| 4 | Rasterize catchments to the IMERG grid once, keep the weights; zonal mean per catchment per half-hour | step 3, `catchments` | `features/catchment_rainfall.parquet` → **`catchment_rainfall`** |
| 5 | Rolling accumulations at 1 h, 3 h, 6 h, 24 h per catchment | step 4 | in-memory / Parquet |
| 6 | Percentiles p50…p99.9 per (catchment, window) over the full record | step 5 | **`catchment_rainfall_climatology`** |
| 7 | Rank windows; keep those above p99 for 3 h or 24 h | steps 5–6 | candidate list |
| 8 | **Check:** Oct 2016 and Feb 2013 must both appear. If they don't, the AOI subset or the time-zone handling is wrong — stop and fix before continuing | step 7 | — |
| 9 | Pull CHIRPS daily for the candidate dates; set the agreement flag | — | `events.chirps_agrees` |
| 10 | Pull ERA5-Land hourly via `cdsapi` for the AOI — 7 variables | — | `data/raw/era5_land/` |
| 11 | Sample per candidate: soil moisture at T−24 h and T−72 h, prior 7-day rainfall, wind speed/direction at peak, ERA5 runoff | step 10 | **`event_catchment_features`** |
| 12 | Write the event rows with `AQ-YYYY-MM-DD` IDs, `detection_method`, `label_tier`, and paper DOIs in `source_references` | steps 7–9 | **`events`** |

CHIRPS is an agreement flag on the event row, never a value that gets averaged in.

**Storage.**
- Raw AOI subsets → `data/raw/imerg/`, `data/raw/era5_land/` as NetCDF or Zarr cubes (time × lat × lon)
- Per-catchment derived series → `data/processed/features/catchment_rainfall.parquet`, and loaded into `catchment_rainfall` (5 catchments × 26 y × half-hourly ≈ 2.3 M rows — trivially fine in Postgres, and it is what the dashboard hyetograph reads)
- Percentiles → `catchment_rainfall_climatology`
- Candidate events → `events` + one `event_catchment_features` row per (event, catchment)

**Watch — a hard size constraint.** IMERG half-hourly global files are ~30 MB each; 26 years is ~455,000 files ≈ 13 TB. The AOI is roughly 4 × 5 grid cells. **Subsetting must happen server-side** (GES DISC subsetter / OPeNDAP / `earthaccess` with a bounding box), or this stream is physically impossible. Same logic for ERA5-Land and GFS: request the box, never the globe.

**Watch — never mix runs.** IMERG Early/Late are uncalibrated. They are for the live demo path only. A training set built on Final Run with a few Early Run rows spliced in is silently corrupt.

---

### 3.3 Land Cover, Soil, Urban & Marine Habitat — Pulga

**Data:** ESA WorldCover 10 m (2021) · ISRIC SoilGrids (clay/sand/silt/SOC/bulk density/coarse fragments, 0–5 and 5–15 cm) · OpenStreetMap Jordan extract (roads, buildings, waterways, industrial polygons) · Allen Coral Atlas (5 m geomorphic + benthic habitat) · GEBCO 15″ bathymetry

**Why the system needs it.** Three distinct jobs:

1. **Land cover + soil answer "how much of the rain becomes surface flow, and what can it pick up?"** Bare ground on a steep slope is the erodible surface; vegetation intercepts; built-up area is impervious and shortens the time to peak. Without these, all five catchments look identical to the runoff model except for size and slope. They are also the entire basis of Component D — sediment availability is estimated from bare fraction × slope × erodibility, because we have no field measurements.
2. **Allen Coral Atlas is the receptor.** Risk is hazard × exposure × vulnerability. Without habitat polygons there is no exposure term and no vulnerability term, and the output degrades to "a brown blob is in the sea" — which is not a decision-support product. The reef zones are also the unit the dashboard, the alert text, and the validation metrics all speak in.
3. **GEBCO is a boundary condition.** The particle engine needs a water mask and a coastline to reflect off, or particles walk across Aqaba city. Depth additionally gates where settling matters.

**How it is used — step by step.**

| # | Step | Reads | Writes |
|---:|---|---|---|
| 1 | Download the WorldCover 2021 AOI tile, clip | — | `data/raw/esa_worldcover/` |
| 2 | Per-catchment class fractions — full histogram to `class_fractions` jsonb, bare/built-up/vegetation/water promoted to columns. **Sanity check:** bare ground should come out high for hyper-arid catchments | step 1, `catchments` | `features/landcover_by_catchment.parquet` |
| 3 | SoilGrids: 6 properties × 2 depths for the AOI → per-catchment means | — | `features/soil_by_catchment.parquet` |
| 4 | Derive `erodibility_proxy` from texture + organic carbon — relative, unitless, formula written down | step 3 | one column |
| 5 | Clip the Jordan `.osm.pbf` to the AOI; extract roads, buildings, waterways/culverts, industrial polygons | — | `vectors/osm_*.gpkg` |
| 6 | Road length km, building footprint km², estimated impervious % per catchment | step 5 | columns |
| 7 | Flag any mapped waterway that contradicts Mahdi's flow paths — **report it, don't silently override the DEM** | steps 5–6, `streams.gpkg` | a note to Mahdi |
| 8 | Load steps 2–6 as one row per catchment | — | **`catchment_surface_features`** |
| 9 | Export ACA habitat (5 m) for the Aqaba coast via Earth Engine | — | `data/raw/aca/` |
| 10 | Split into named zones `R-01`…`R-NN`; area km² in 32636; carry the ACA geomorphic and benthic class | step 9 | zone polygons |
| 11 | Set `sensitivity_weight = 1.0` and **leave `sensitivity_basis` at its placeholder string** until a marine scientist replaces it | — | two columns |
| 12 | Nearest outlet and distance per reef zone (provisional outlets are good enough here) | `outlets` | **`reef_zones`** + `vectors/reef_zones.gpkg` |
| 13 | GEBCO 15″ for the northern Gulf → clip → reproject → threshold to a binary mask | — | `bathymetry/depth_utm36n.tif`, `water_mask.tif` + 2 `raster_assets` rows |

Step 13 is the one the particle engine loads at startup; steps 2–8 are what let five catchments differ from each other in the runoff model.

**Storage.**
- Per-catchment features → `data/processed/features/{landcover,soil}_by_catchment.parquet` → `catchment_surface_features`
- Reef zones → `reef_zones` (PostGIS) + `data/processed/vectors/reef_zones.gpkg`
- OSM layers → `data/processed/vectors/osm_*.gpkg`; optionally loaded to PostGIS for map display, not needed by any model
- Depth + water mask → `data/processed/bathymetry/depth_utm36n.tif`, `water_mask.tif` + `raster_assets`

**Watch — the sensitivity weight is the project's most quotable assumption.** ACA maps reef *habitat*, not ecological sensitivity. The weights are ours. The schema therefore makes `reef_zones.sensitivity_basis` a `NOT NULL` text column defaulting to an explicit placeholder string, so the caveat travels with the number into every API response instead of living only on a slide.

**Watch — a modelling consequence of this stream.** With ~30 events × 5 catchments ≈ 150 training rows, and static features that are *constant per catchment*, an XGBoost model can trivially memorise catchment identity and look excellent in random cross-validation. Validation must be **leave-one-catchment-out**, and that should be stated in the model card. This is a data-design problem, not a tuning problem.

---

### 3.4 Satellite Imagery & Observed Plume — Abd

**Data:** Sentinel-2 L2A (B2, B3, B4, B8, B11, B12 + SCL) · NASA HLS (HLSS30 + HLSL30 v2.0) · Landsat 8/9 L2 (the only optical option for Feb 2013) · Copernicus ocean-colour method reference

**Why the system needs it.** **This is the only observation in the entire project.** Rainfall is a satellite retrieval, currents are a model, runoff is a model, the plume forecast is a model. The observed plume mask is the one thing measured rather than computed, which makes it the sole basis for:

- **Calibration** — diffusion, windage and settling have no local literature values; they are fitted by maximising agreement with this mask.
- **Validation** — IoU, Dice, centroid distance and area error in §13.4 are all "predicted versus *this*".
- **Credibility** — the difference between "we built a simulator" and "we reproduced a real event to a measured degree".

The pre-event baseline composite matters for a subtler reason: an anomaly is only meaningful against a defined normal. Gulf water has natural reflectance variation from depth, bottom type and glint, so "brighter than usual" requires a per-pixel "usual" — a median of 5–10 clear pre-event scenes.

**How it is used — step by step.** Search *then* download; the audit is free, the downloads are not.

| # | Step | Reads | Writes |
|---:|---|---|---|
| 1 | Read the two papers, fix the event dates — Day 1, depends on nobody | Ginat 2025, Katz 2015 | `docs/event_dates.md` |
| 2 | List every S2 / HLS / Landsat scene within ±10 days of each candidate event | STAC / Copernicus Browser | **`satellite_scenes`**, one row each, `decision = 'pending'` |
| 3 | Open each in the browser and score by eye: cloud % over **AOI water** (not scene-wide — scene cloud % lies when the cloud is all over the mountains), glint 0–3, plume visible yes/partial/no | step 2 | `cloud_pct_aoi_water`, `sun_glint_score`, `plume_visible` |
| 4 | Compute `usability_score`; set `decision` and `decision_reason` on every row | step 3 | `satellite_scenes` |
| 5 | **THE GATE** — is there ≥1 event with a post-event scene ≤~5 days, <~20% cloud over water, and a visible plume? Report to the team the day it is known, good or bad | step 4 | go / no-go |
| 6 | Download the selected post-event scene + 5–10 clear pre-event scenes; bands B2, B3, B4, B8, B11, B12 + SCL | step 4 | `data/raw/sentinel2/<scene_id>/` |
| 7 | Water mask from SCL + a NIR threshold; exclude land, cloud, cloud shadow | step 6 | water mask raster |
| 8 | Median composite of the pre-event scenes over water — this defines "normal" | steps 6–7 | `plume/baseline_composite.tif` + `raster_assets` |
| 9 | Compute NDSSI, NSMI, red/green ratio, and a plain multi-date reflectance anomaly on the post-event scene | steps 6–8 | index rasters |
| 10 | Compare all four side by side on the demo scene; pick **one** primary index and document why with a figure | step 9 | `docs/event_audit.md` |
| 11 | Anomaly vs baseline → strip glint, cloud and land-edge artifacts → probability raster | steps 8–10 | `plume/observed_plume_probability.tif` |
| 12 | Manual QC in QGIS; threshold to a polygon | step 11 | `vectors/observed_plume.gpkg` |
| 13 | Write the observation row: `index_used`, threshold, both raster IDs, area, centroid, reef overlap, `label_tier`, `qc_notes` | steps 11–12 | **`observed_plumes`** |

Step 5 is the only step in this document that can invalidate the project. Steps 1–5 need no downloads and no other stream's output, which is why they run on Day 1 instead of Day 5.

**Storage.**
- Band subsets → `data/raw/sentinel2/<scene_id>/`
- Baseline composite, index rasters, plume probability → `data/processed/plume/*.tif` + `raster_assets`
- **The audit itself → `satellite_scenes`.** This is the one place I deviate most from concept §18, which has no scene table. The audit is the highest-risk decision in the project; it belongs in a queryable table with a `decision` and `decision_reason`, not only in `docs/event_audit.md`.
- Final mask → `observed_plumes` (geometry + `probability_raster_id` + `label_tier` gold/silver/bronze + `quality_score`)

**Watch:** the go/no-go criterion is concrete — at least one event with a post-event scene within ~5 days, under ~20% cloud over the water, with a visually distinguishable plume. Sentinel-2 revisit is 2–5 days; a plume can disperse in 24–72 h. Timing luck is a genuine project risk, which is why several events get audited and why the answer is wanted on Day 2–3.

---

### 3.5 Weather Forecasts & Ocean Currents — Nizar

**Data:** NOAA GFS (deterministic, ~0.25°) · NOAA GEFS (ensemble) · ECMWF IFS/AIFS open data (second opinion) · Copernicus Global Ocean Physics Analysis & Forecast (u/v currents, ~1/12°) · HYCOM (backup currents)

**Why the system needs it.**

- **Forecast rainfall is what makes this a warning system.** Everything Karam supplies is retrospective. GFS is the difference between a post-mortem and a 9-hour lead time, which is the operational claim in §22.
- **GEFS supplies the confidence number.** A deterministic forecast gives "42 mm". The ensemble gives "68% of members exceed this catchment's 3 h threshold". That conversion from a value to a probability is the whole reason the dashboard can honestly display a confidence figure, and it is what a judge will press on.
- **Currents and wind are the only inputs that decide direction.** Remove them and the plume forecast collapses to a circle around the outlet — which is literally baseline #1 in §13.6. The model must beat that, and currents are how.

**How it is used — step by step.**

| # | Step | Reads | Writes |
|---:|---|---|---|
| 1 | Pull the latest GFS run from the AWS bucket using `.idx` byte-range subsetting; extract AOI rainfall + 10 m wind to 48 h lead | — | **`forecast_runs`** + **`forecast_catchment_rainfall`** (`member = 0`) |
| 2 | **Confirm the live path runs end-to-end on today's data whatever the weather** — the demo must work on a dry day | step 1 | a working pipeline |
| 3 | Pull all GEFS members over the same AOI and lead window | — | `forecast_catchment_rainfall` (`member = 1…N`) |
| 4 | Join to the stored climatology; count members exceeding p99 per window | step 3, `catchment_rainfall_climatology` | **`forecast_exceedance`** — the dashboard's confidence number |
| 5 | Pull ECMWF open data with `ecmwf-opendata` over the same window; build a GFS-vs-IFS agreement flag | — | agreement flag |
| 6 | Pull Copernicus Marine u/v for the northern Gulf, surface + upper depth levels; rechunk for time-slicing | — | `interim/currents.zarr` |
| 7 | Wrap it in an interpolator `u(lon, lat, t)`, `v(lon, lat, t)` — **the engine calls this, it never reshapes an array** | step 6 | a Python interface |
| 8 | Pull HYCOM for the same window as a direction cross-check at the outlet | — | a comparison figure |
| 9 | Particle engine: release N particles at the outlet at `release_time`; per step advect by currents + windage × wind + random diffusion, settle by settling velocity, reflect off the water mask | steps 7, 13 of §3.3, `outlets` | — |
| 10 | Insert the run row **before** computing, with `status` and full `parameters` jsonb; write trajectories to file | step 9 | **`simulation_runs`**, `outputs/<run_id>/particles.parquet` |
| 11 | Kernel-density the particle cloud per timestep → probability raster → contour at 0.10 / 0.25 / 0.50 / 0.75 | step 10 | **`plume_forecasts`** (one row per hour × level) |
| 12 | Intersect each contour with the reef zones per timestep → arrival window, max exposure probability, duration → risk score | step 11, `reef_zones` | **`reef_exposures`** incl. `formula_terms` |
| 13 | Sweep diffusion × windage × settling against Abd's observed mask; mark the winner | `observed_plumes` | **`calibration_trials`**, `is_selected = true` |
| 14 | Copy the selected parameters into the demo run and re-run | step 13 | the final `simulation_runs` row |

Steps 9–12 are built and tested against the **provisional** outlet and the **synthetic** plume mask (contracts P2 and P5). Step 13 is the one place in the project that genuinely cannot proceed without another person's real output.

**Storage.**
- Raw GRIB/NetCDF → `data/raw/gfs/`, `data/raw/gefs/`, `data/raw/currents/`; currents rechunked to Zarr for fast time-slicing
- Forecast metadata → `forecast_runs`; per-catchment values → `forecast_catchment_rainfall`; exceedance fractions → `forecast_exceedance`
- Simulation parameters and status → `simulation_runs` (full request stored verbatim as `jsonb` so any run is reproducible)
- Particle trajectories → `data/outputs/<run_id>/particles.parquet` — **files, never Postgres**
- Contoured probability polygons per timestep and probability level → `plume_forecasts`

**Watch — the project's binding accuracy limit.** Both current products are ~1/12° (~9 km) across a gulf 15–25 km wide: roughly 2–3 grid cells span the entire basin, so nearshore circulation is effectively unresolved. This is not a bug to be fixed within the hackathon; it is the reason the deliverable must be a **probabilistic exposure zone** rather than a metre-level prediction. It should be stated in the pitch before a judge finds it.

---

### 3.6 Cross-cutting — provenance and results

**`data_sources` is not bookkeeping.** §22.4 scores scientific integrity, and every number on the dashboard needs to be traceable to a product ID, version, access date, licence and citation. One row per product, filled in as each stream downloads. It also drives the "Data Sources" panel in the UI, which is cheap credibility for the cost of a table.

**`model_versions`** records which model produced which prediction, trained on which event IDs, with what hyperparameters. Without it, a `runoff_predictions` row is an orphan number that cannot be reproduced or explained.

---

## 4. Schema

PostgreSQL 16 + PostGIS 3. Storage CRS is EPSG:4326 throughout; every area/distance column is pre-computed in EPSG:32636 and stored as a number, per the contracts doc — see [Appendix A](#appendix-a--glossary) for why the two differ and what breaks if they're mixed. `is_provisional` appears on every table that can receive seed data — the Day-12 gate is then a SQL query, not a grep.

### 4.1 Provenance

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE data_sources (
    id                   text PRIMARY KEY,          -- 'imerg_v07_final', 'cop_dem_glo30'
    name                 text NOT NULL,
    provider             text NOT NULL,             -- NASA, ESA, ECMWF, NOAA, ISRIC, ACA
    product              text NOT NULL,
    version              text,
    temporal_resolution  text,                      -- '30min', 'hourly', 'static'
    spatial_resolution_m numeric,
    native_crs           text,
    access_url           text,
    access_method        text,                      -- earthaccess|cdsapi|gee|aws-s3|http|copernicusmarine
    requires_account     boolean NOT NULL DEFAULT false,
    license              text NOT NULL,
    citation             text,
    first_accessed_at    timestamptz,
    last_checked_at      timestamptz,
    known_limitation     text,                      -- the §11 caveat, verbatim
    notes                text
);

CREATE TABLE raster_assets (
    id              bigserial PRIMARY KEY,
    kind            text NOT NULL,                  -- dem|flowacc|slope|landcover|depth|water_mask
                                                    -- |baseline_composite|spectral_index|plume_probability
    source_id       text REFERENCES data_sources(id),
    path            text NOT NULL UNIQUE,
    format          text NOT NULL DEFAULT 'COG',
    crs             text NOT NULL,
    pixel_size_m    numeric,
    bbox            geometry(Polygon, 4326),
    valid_time      timestamptz,                    -- NULL for static layers
    bytes           bigint,
    checksum_sha256 text,
    is_provisional  boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX raster_assets_bbox_idx ON raster_assets USING gist (bbox);
```

### 4.2 Static geography

```sql
CREATE TABLE catchments (
    id                      text PRIMARY KEY,       -- AQ-C01 … AQ-C05
    name                    text,
    geom                    geometry(MultiPolygon, 4326) NOT NULL,
    area_km2                numeric NOT NULL,
    perimeter_km            numeric,
    mean_elev_m             numeric,
    relief_m                numeric,
    mean_slope_deg          numeric,
    max_slope_deg           numeric,
    drainage_density_km_km2 numeric,
    stream_length_km        numeric,
    longest_flowpath_km     numeric,
    max_flow_accum_cells    bigint,
    time_of_concentration_min numeric,
    dem_source_id           text REFERENCES data_sources(id),
    delineation_method      text,                   -- 'd8_whitebox' | 'hydrobasins_l9'
    notes                   text,                   -- record any manual DEM correction here
    is_provisional          boolean NOT NULL DEFAULT true,
    updated_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX catchments_geom_idx ON catchments USING gist (geom);

CREATE TABLE outlets (
    id              text PRIMARY KEY,               -- AQ-O01, matches its catchment number
    catchment_id    text NOT NULL UNIQUE REFERENCES catchments(id),
    geom            geometry(Point, 4326) NOT NULL,
    method          text,                           -- 'dem_pourpoint' | 'manual_imagery'
    snap_distance_m numeric,                        -- how far it moved from the raw pour point
    is_provisional  boolean NOT NULL DEFAULT true
);
CREATE INDEX outlets_geom_idx ON outlets USING gist (geom);

CREATE TABLE catchment_surface_features (
    catchment_id            text PRIMARY KEY REFERENCES catchments(id),
    landcover_source_id     text REFERENCES data_sources(id),
    landcover_year          int,
    bare_ground_pct         numeric,
    built_up_pct            numeric,
    vegetation_pct          numeric,
    water_pct               numeric,
    class_fractions         jsonb,                  -- full WorldCover histogram
    clay_pct_0_5            numeric,
    sand_pct_0_5            numeric,
    silt_pct_0_5            numeric,
    soc_g_per_kg_0_5        numeric,
    bulk_density_0_5        numeric,
    coarse_fragments_pct_0_5 numeric,
    clay_pct_5_15           numeric,
    sand_pct_5_15           numeric,
    silt_pct_5_15           numeric,
    erodibility_proxy       numeric,                -- derived, relative, unitless
    road_length_km          numeric,
    building_footprint_km2  numeric,
    impervious_pct_est      numeric,
    is_provisional          boolean NOT NULL DEFAULT true,
    updated_at              timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reef_zones (
    id                 text PRIMARY KEY,            -- R-01 … R-08
    name               text,
    geom               geometry(MultiPolygon, 4326) NOT NULL,
    area_km2           numeric NOT NULL,
    habitat_class      text,                        -- ACA geomorphic class
    benthic_class      text,                        -- ACA benthic class
    mean_depth_m       numeric,
    sensitivity_weight numeric NOT NULL DEFAULT 1.0,
    sensitivity_basis  text NOT NULL
        DEFAULT 'PLACEHOLDER: uniform 1.0, team assumption, not scientifically derived',
    nearest_outlet_id  text REFERENCES outlets(id),
    distance_to_outlet_m numeric,
    source_id          text REFERENCES data_sources(id),
    is_provisional     boolean NOT NULL DEFAULT true
);
CREATE INDEX reef_zones_geom_idx ON reef_zones USING gist (geom);
```

### 4.3 Rainfall, climatology, events

```sql
CREATE TABLE catchment_rainfall (
    catchment_id text NOT NULL REFERENCES catchments(id),
    ts           timestamptz NOT NULL,              -- UTC, start of the accumulation step
    source_id    text NOT NULL REFERENCES data_sources(id),
    rain_mm      numeric NOT NULL,                  -- accumulation over the native step
    PRIMARY KEY (catchment_id, ts, source_id)
);

CREATE TABLE catchment_rainfall_climatology (
    catchment_id  text NOT NULL REFERENCES catchments(id),
    window_hours  int  NOT NULL,                    -- 1, 3, 6, 24
    source_id     text NOT NULL REFERENCES data_sources(id),
    p50 numeric, p90 numeric, p95 numeric, p99 numeric, p99_9 numeric,
    max_observed_mm numeric,
    n_windows     bigint,
    period_start  date,
    period_end    date,
    PRIMARY KEY (catchment_id, window_hours, source_id)
);

CREATE TABLE events (
    id                text PRIMARY KEY,             -- AQ-2016-10-25
    start_time        timestamptz NOT NULL,
    end_time          timestamptz,
    peak_time         timestamptz,
    event_type        text NOT NULL DEFAULT 'historical',  -- historical|forecast|scenario
    detection_method  text,                         -- imerg_percentile|literature|manual
    label_tier        text CHECK (label_tier IN ('gold','silver','bronze')),
    quality_score     numeric CHECK (quality_score BETWEEN 0 AND 1),
    chirps_agrees     boolean,                      -- independent cross-check flag
    source_references jsonb,                        -- DOIs / URLs confirming the date
    is_demo_event     boolean NOT NULL DEFAULT false,
    notes             text,
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- The ML training table. One row per (event, catchment).
-- Static features are JOINED from catchments / catchment_surface_features at fit time,
-- deliberately not copied here — copying them is how a training set drifts out of sync
-- with the geography it describes.
CREATE TABLE event_catchment_features (
    event_id                text NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    catchment_id            text NOT NULL REFERENCES catchments(id),
    rain_30min_max_mm       numeric,
    rain_1h_mm              numeric,
    rain_3h_mm              numeric,
    rain_6h_mm              numeric,
    rain_24h_mm             numeric,
    rain_percentile_3h      numeric,
    rain_percentile_24h     numeric,
    antecedent_rain_7d_mm   numeric,
    soil_moisture_t24       numeric,
    soil_moisture_t72       numeric,
    era5_surface_runoff_m   numeric,
    era5_subsurface_runoff_m numeric,
    wind_speed_ms           numeric,
    wind_direction_deg      numeric,
    current_u_ms            numeric,
    current_v_ms            numeric,
    extra_features          jsonb,                  -- anything added after freeze
    -- labels
    runoff_observed         boolean,
    severity_observed       text CHECK (severity_observed IN ('none','low','medium','high','extreme')),
    label_source            text,                   -- 'satellite_plume'|'literature'|'inferred'
    PRIMARY KEY (event_id, catchment_id)
);
```

### 4.4 Imagery and observation

```sql
CREATE TABLE satellite_scenes (
    id                  text PRIMARY KEY,           -- provider granule/scene ID
    source_id           text NOT NULL REFERENCES data_sources(id),
    platform            text,                       -- S2A|S2B|L8|L9
    acquisition_time    timestamptz NOT NULL,
    event_id            text REFERENCES events(id),
    days_from_event     numeric,                    -- signed: negative = pre-event
    role                text,                       -- candidate|pre_event|post_event
    cloud_pct_scene     numeric,
    cloud_pct_aoi_water numeric,                    -- the number that actually matters
    sun_glint_score     int CHECK (sun_glint_score BETWEEN 0 AND 3),
    plume_visible       text CHECK (plume_visible IN ('yes','partial','no','unknown')),
    usability_score     numeric,
    decision            text CHECK (decision IN ('selected','baseline','rejected','pending')),
    decision_reason     text,
    footprint           geometry(Polygon, 4326),
    local_path          text,
    reviewed_by         text,
    reviewed_at         timestamptz
);

CREATE TABLE observed_plumes (
    id                    bigserial PRIMARY KEY,
    event_id              text NOT NULL REFERENCES events(id),
    scene_id              text REFERENCES satellite_scenes(id),
    acquisition_time      timestamptz NOT NULL,
    index_used            text,                     -- ndssi|nsmi|red_green_ratio|reflectance_anomaly
    threshold_value       numeric,
    baseline_raster_id    bigint REFERENCES raster_assets(id),
    probability_raster_id bigint REFERENCES raster_assets(id),
    geom                  geometry(MultiPolygon, 4326),
    area_km2              numeric,
    centroid              geometry(Point, 4326),
    reef_overlap_km2      numeric,
    label_tier            text CHECK (label_tier IN ('gold','silver','bronze')),
    quality_score         numeric,
    qc_by                 text,
    qc_notes              text,
    is_provisional        boolean NOT NULL DEFAULT false
);
CREATE INDEX observed_plumes_geom_idx ON observed_plumes USING gist (geom);
```

### 4.5 Forecast ingestion

```sql
CREATE TABLE forecast_runs (
    id             text PRIMARY KEY,                -- 'gfs_2026-07-31T00Z'
    source_id      text NOT NULL REFERENCES data_sources(id),
    model          text NOT NULL,                   -- gfs|gefs|ifs|aifs
    reference_time timestamptz NOT NULL,
    n_members      int NOT NULL DEFAULT 1,
    max_lead_hours int,
    raw_path       text,
    ingested_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (model, reference_time)
);

CREATE TABLE forecast_catchment_rainfall (
    forecast_run_id    text NOT NULL REFERENCES forecast_runs(id) ON DELETE CASCADE,
    catchment_id       text NOT NULL REFERENCES catchments(id),
    lead_hours         int  NOT NULL,
    member             int  NOT NULL DEFAULT 0,     -- 0 = deterministic / ensemble mean
    rain_mm            numeric,
    wind_speed_ms      numeric,
    wind_direction_deg numeric,
    PRIMARY KEY (forecast_run_id, catchment_id, lead_hours, member)
);

-- The dashboard's confidence number, materialised.
CREATE TABLE forecast_exceedance (
    forecast_run_id  text NOT NULL REFERENCES forecast_runs(id) ON DELETE CASCADE,
    catchment_id     text NOT NULL REFERENCES catchments(id),
    window_hours     int  NOT NULL,
    threshold_mm     numeric NOT NULL,
    threshold_source text,                          -- e.g. 'climatology p99'
    members_total    int,
    members_exceeding int,
    exceedance_prob  numeric CHECK (exceedance_prob BETWEEN 0 AND 1),
    PRIMARY KEY (forecast_run_id, catchment_id, window_hours)
);
```

### 4.6 Model outputs

```sql
CREATE TABLE model_versions (
    id                 text PRIMARY KEY,            -- 'runoff_xgb_v3'
    component          text NOT NULL,               -- C|D|E
    algorithm          text,
    trained_at         timestamptz,
    training_event_ids text[],
    cv_scheme          text,                        -- 'leave_one_catchment_out'
    hyperparams        jsonb,
    metrics            jsonb,
    artifact_path      text,
    git_commit         text
);

CREATE TABLE runoff_predictions (
    id                     bigserial PRIMARY KEY,
    event_id               text REFERENCES events(id),
    catchment_id           text NOT NULL REFERENCES catchments(id),
    model_version_id       text REFERENCES model_versions(id),
    mode                   text NOT NULL,           -- historical|forecast|scenario
    forecast_run_id        text REFERENCES forecast_runs(id),
    runoff_probability     numeric CHECK (runoff_probability BETWEEN 0 AND 1),
    severity               text CHECK (severity IN ('none','low','medium','high','extreme')),
    confidence             numeric,
    rule_baseline_index    numeric,                 -- transparent baseline, kept alongside the ML output
    sediment_class         text CHECK (sediment_class IN ('low','medium','high','extreme')),
    sediment_index         numeric,
    feature_attributions   jsonb,                   -- SHAP values → Component H "top drivers"
    created_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (event_id, catchment_id, model_version_id, mode)
);
```

### 4.7 Simulation, exposure, validation

```sql
CREATE TABLE simulation_runs (
    id                     text PRIMARY KEY,        -- sim_01JXYZ (ULID)
    event_id               text REFERENCES events(id),
    forecast_run_id        text REFERENCES forecast_runs(id),
    catchment_id           text REFERENCES catchments(id),
    outlet_id              text REFERENCES outlets(id),
    mode                   text NOT NULL,           -- historical|forecast|scenario
    engine                 text NOT NULL,           -- opendrift|custom_2d
    release_time           timestamptz NOT NULL,
    duration_hours         int,
    time_step_minutes      int,
    particle_count         int,
    sediment_class         text,
    diffusion_m2_s         numeric,
    settling_velocity_mm_s numeric,
    windage_fraction       numeric,
    current_source_id      text REFERENCES data_sources(id),
    wind_source_id         text REFERENCES data_sources(id),
    parameters             jsonb NOT NULL,          -- the request verbatim → reproducibility
    is_calibration_trial   boolean NOT NULL DEFAULT false,
    status                 text NOT NULL,           -- queued|running|completed|failed
    error_message          text,
    started_at             timestamptz,
    completed_at           timestamptz,
    runtime_seconds        numeric,
    git_commit             text,
    output_dir             text                     -- data/outputs/<run_id>/
);

-- Contoured probability polygons. NOT particles.
CREATE TABLE plume_forecasts (
    id                   bigserial PRIMARY KEY,
    run_id               text NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    forecast_hour        numeric NOT NULL,
    forecast_time        timestamptz,
    probability_level    numeric NOT NULL,          -- 0.10 | 0.25 | 0.50 | 0.75
    geom                 geometry(MultiPolygon, 4326),
    area_km2             numeric,
    centroid             geometry(Point, 4326),
    raster_id            bigint REFERENCES raster_assets(id),
    active_particle_count int,
    UNIQUE (run_id, forecast_hour, probability_level)
);
CREATE INDEX plume_forecasts_geom_idx ON plume_forecasts USING gist (geom);

CREATE TABLE reef_exposures (
    id                       bigserial PRIMARY KEY,
    run_id                   text NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    reef_zone_id             text NOT NULL REFERENCES reef_zones(id),
    max_exposure_probability numeric,
    overlap_km2_at_max       numeric,
    exposure_duration_hours  numeric,
    arrival_start            timestamptz,
    arrival_end              timestamptz,
    arrival_window_hours_low  numeric,
    arrival_window_hours_high numeric,
    risk_score               numeric CHECK (risk_score BETWEEN 0 AND 100),
    risk_level               text CHECK (risk_level IN ('minimal','low','moderate','high','critical')),
    confidence               numeric,
    formula_terms            jsonb NOT NULL,        -- each multiplicand of the §10.7 formula
    UNIQUE (run_id, reef_zone_id)
);

> **Corrected 5 Aug 2026 (Nizar).** `reef_exposures.risk_level` was specified above as
> `('low','moderate','high','severe')` — a transcription slip. `backend/src/exposure/
> engine.py`'s `RISK_BANDS`, which matches concept §14.5 exactly, produces
> `minimal/low/moderate/high/critical`. The live constraint was wrong from the day this
> table was created in Phase 2 and has been altered to match
> (`supabase/migrations/20260805080814_fix_reef_exposures_risk_level.sql`); the DDL
> above now reflects the corrected constraint.

CREATE TABLE calibration_trials (
    id                     bigserial PRIMARY KEY,
    event_id               text NOT NULL REFERENCES events(id),
    observed_plume_id      bigint NOT NULL REFERENCES observed_plumes(id),
    run_id                 text REFERENCES simulation_runs(id),
    diffusion_m2_s         numeric,
    settling_velocity_mm_s numeric,
    windage_fraction       numeric,
    iou                    numeric,
    dice                   numeric,
    centroid_distance_m    numeric,
    area_ratio             numeric,
    is_selected            boolean NOT NULL DEFAULT false
);

CREATE TABLE backtests (
    id                text PRIMARY KEY,
    event_id          text NOT NULL REFERENCES events(id),
    run_id            text REFERENCES simulation_runs(id),
    observed_plume_id bigint REFERENCES observed_plumes(id),
    baseline          text,                         -- NULL = the model; else circular_buffer|wind_only|…
    blind             boolean NOT NULL DEFAULT true,
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- Long format: new metrics need no migration.
CREATE TABLE backtest_metrics (
    id                  bigserial PRIMARY KEY,
    backtest_id         text NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    metric_name         text NOT NULL,              -- iou|dice|centroid_distance_m|direction_error_deg|…
    metric_value        numeric,
    unit                text,
    at_forecast_hour    numeric,
    at_probability_level numeric,
    UNIQUE (backtest_id, metric_name, at_forecast_hour, at_probability_level)
);

CREATE TABLE alerts (
    id                  bigserial PRIMARY KEY,
    issued_at           timestamptz NOT NULL DEFAULT now(),
    forecast_run_id     text REFERENCES forecast_runs(id),
    run_id              text REFERENCES simulation_runs(id),
    catchment_id        text REFERENCES catchments(id),
    reef_zone_ids       text[],
    severity            text,
    lead_time_hours     numeric,
    headline            text NOT NULL,
    explanation         text NOT NULL,              -- Component H narrative
    recommended_action  text,
    uncertainty_note    text NOT NULL,              -- forced: no alert ships without its caveat
    status              text NOT NULL DEFAULT 'draft'
);
```

> **Added 11 Aug 2026 (Phase 9, Mahdi/Nizar).** The storm-response recommendation
> swarm (`tasks/phase9/00-phase9-plan.md`) adds four tables —
> `response_recommendations`, `recommendation_turns`, `recommendation_verdicts`,
> `recommendation_gaps` — and one column, `alerts.recommendation_id text
> REFERENCES response_recommendations(id)`, linking an alert's existing free-text
> `recommended_action` to the full evidence-grounded, multi-agent deliberation
> record behind it. No RLS, matching this section's other tables. Full DDL:
> `supabase/migrations/20260811090000_response_recommendations.sql`.

---

## 5. File storage

| Data type | Format | Why | Path |
|---|---|---|---|
| Weather / ocean cubes | NetCDF (raw), **Zarr** (working) | Chunked, lazy, and Xarray slices a time range without reading the whole cube. Zarr specifically for currents — the engine hits it thousands of times during calibration. | `data/raw/<source>/`, `data/interim/<source>.zarr` |
| Rasters | **COG** GeoTIFF | Windowed reads; the API can serve a tile without loading the file | `data/processed/{dem,bathymetry,plume}/` |
| Vectors, small | GeoPackage + PostGIS | GPKG for the exchange copy in git-lfs-free size, PostGIS as the queryable authority | `data/processed/vectors/` |
| Feature tables | **Parquet** | Typed, compressed, columnar; the direct input to XGBoost with no parsing step | `data/processed/features/` |
| Particle trajectories | Parquet | 70M+ rows across calibration; columnar and never joined | `data/outputs/<run_id>/particles.parquet` |
| Model artifacts | joblib / JSON | — | `data/models/<model_version_id>/` |
| Per-run deliverables | GeoJSON | What the frontend fetches directly | `data/outputs/<run_id>/t{HH}.geojson` |

**Provisional naming:** `*_PROVISIONAL.*` per the contracts doc, mirrored by `is_provisional` in Postgres. The Day-12 gate becomes:

```sql
SELECT 'catchments' t, id FROM catchments WHERE is_provisional
UNION ALL SELECT 'outlets', id FROM outlets WHERE is_provisional
UNION ALL SELECT 'reef_zones', id FROM reef_zones WHERE is_provisional
UNION ALL SELECT 'surface_features', catchment_id FROM catchment_surface_features WHERE is_provisional;
```

### Expected volume

| Stream | Realistic size | Note |
|---|---:|---|
| DEM + derivatives (AOI, 30 m) | ~50 MB | |
| WorldCover 10 m AOI | ~25 MB | |
| SoilGrids, GEBCO, OSM Jordan clip, ACA | ~500 MB | OSM `.osm.pbf` dominates before clipping |
| IMERG 26 y, **AOI-subset** | ~200 MB | **13 TB if not subset at source** |
| ERA5-Land 26 y, AOI, 7 vars | ~100 MB | |
| Sentinel-2 / HLS, ~15 scenes, band subset | ~1 GB | ~12 GB if full tiles are pulled |
| Currents (AOI, Zarr) | ~200 MB | |
| GFS/GEFS runs (byte-range subset) | ~50 MB / run | |
| **Total** | **~3–5 GB** | Fits a laptop. Skipping server-side subsetting turns this into terabytes — that is the single decision that determines whether the data volume is manageable. |

Postgres, by contrast, is tiny: 5 catchments, ~8 reef zones, ~30 events, ~150 training rows, a few hundred scenes, a few thousand simulation rows. The largest table is `catchment_rainfall` at ~2.3 M rows. **Nothing here needs tuning, partitioning, or scaling work** — the schema exists for correct joins and honest provenance, not for volume. Effort spent on database performance is effort taken from the imagery gate.

---

## 6. End-to-end trace

Reading the schema as one story, for the demo event:

```
events(AQ-2016-10-25)                         ← Karam: IMERG percentile + literature date
  └─ event_catchment_features(·, AQ-C03)      ← Karam: rain + ERA5, joined to
     ├─ catchments(AQ-C03)                    ← Mahdi: DEM delineation
     └─ catchment_surface_features(AQ-C03)    ← Pulga: WorldCover + SoilGrids + OSM
        └─ runoff_predictions                 ← Component C/D: probability + sediment class + SHAP
           └─ simulation_runs(sim_01JXYZ)     ← Nizar: released at outlets(AQ-O03)
              ├─ plume_forecasts              ← contoured probability per hour × level
              │  └─ reef_exposures            ← × reef_zones(R-01…R-08) → risk score
              │     └─ alerts                 ← Component H narrative + uncertainty note
              └─ backtests
                 ├─ observed_plumes           ← Abd: Sentinel-2 mask, the only observation
                 └─ backtest_metrics          ← IoU, Dice, centroid error, vs each §13.6 baseline
```

Every arrow is a foreign key. Every leaf is traceable to a `data_sources` row with a licence and an access date.

---

## 7. Build sequence — every step in the order it runs

§3 gives each stream in isolation. This is the assembly order for the whole system. `§3.1→4` means "step 4 of section 3.1".

### Phase 0 — before anything is downloaded (half a day, everyone together)

| # | Step | Owner | Result |
|---:|---|---|---|
| S1 | Confirm the download box and the analysis box | all | `data/aoi/aqaba_aoi.geojson` |
| S2 | Confirm ID formats **and counts** — 5 catchments, 5 outlets, 8 reef zones | all | frozen join keys |
| S3 | Create the folder tree from §5, commit with `.gitkeep` | anyone | empty structure |
| S4 | `createdb reefshield` → apply §4 DDL **in order 4.1 → 4.7** (foreign keys require it) | anyone | empty schema |
| S5 | Seed `data_sources` — one row per §11 product, `known_limitation` filled in from the doc | all, ~1 h split | **the first data in the database**; everything else FKs to it |
| S6 | Provisional seeds P1–P5 from the contracts doc | Mahdi, Pulga, Nizar | rows with `is_provisional = true` |

After S6 every stream can run. Nothing below waits on anything except where marked ⛔.

### Phase 1 — static geography (Day 1–4, parallel)

| # | Step | Owner | Writes |
|---:|---|---|---|
| S7 | §3.1 → 1–11 | Mahdi | `catchments`, `outlets`, DEM rasters |
| S8 | §3.3 → 1–8 | Pulga | `catchment_surface_features` |
| S9 | §3.3 → 9–13 | Pulga | `reef_zones`, depth + water-mask rasters |

### Phase 2 — history (Day 1–4, parallel with Phase 1 via provisional catchments)

| # | Step | Owner | Writes |
|---:|---|---|---|
| S10 | §3.2 → 1–8 | Karam | `catchment_rainfall`, `catchment_rainfall_climatology` |
| S11 | §3.2 → 9–12 | Karam | `events`, `event_catchment_features` |

### Phase 3 — the observation (Day 1–6)

| # | Step | Owner | Writes |
|---:|---|---|---|
| S12 | §3.4 → 1–5 | Abd | `satellite_scenes` + **the go/no-go answer** |
| S13 | §3.4 → 6–13 | Abd | `observed_plumes`, baseline composite |

### Phase 4 — land models (Day 7)

| # | Step | Owner | Writes |
|---:|---|---|---|
| S14 | Build the training matrix: `event_catchment_features ⋈ catchments ⋈ catchment_surface_features` | modeller | `features/training.parquet` |
| S15 | Fit the rule baseline **and** XGBoost · leave-one-catchment-out CV · probability calibration · SHAP | modeller | `model_versions` + artifact |
| S16 | Predict per (event, catchment); derive the sediment class for Component D | modeller | `runoff_predictions` |

⛔ S14 needs S7, S8 and S11 — but only their *provisional* versions to start. The real blocker is that S14 must be **re-run** after every swap-in.

### Phase 5 — transport (Day 5–9)

| # | Step | Owner | Writes |
|---:|---|---|---|
| S17 | §3.5 → 1–5 | Nizar | `forecast_runs`, `forecast_catchment_rainfall`, `forecast_exceedance` |
| S18 | §3.5 → 6–8 | Nizar | `interim/currents.zarr` + interpolator |
| S19 | §3.5 → 9–12 | Nizar | `simulation_runs`, `plume_forecasts`, `reef_exposures` |
| S20 | §3.5 → 13–14 | Nizar | `calibration_trials`, final parameters |

⛔ **S20 is the one true blocker in the project** — it needs S13's real mask. S19 runs against the synthetic mask until then.

### Phase 6 — validation and product (Day 10–13)

| # | Step | Owner | Writes |
|---:|---|---|---|
| S21 | Blind backtest per concept §13.3: freeze inputs at event time, hide the post-event scene, run S16 + S19, then reveal and compare | modeller | `backtests`, `backtest_metrics` |
| S22 | Repeat S21 for each §13.6 baseline — circular buffer, wind-only, current-only, fixed-south, no-catchment-model | modeller | one `backtests` row per baseline, same metrics |
| S23 | Compose the Component H narrative for the demo event | all | `alerts` |
| S24 | FastAPI over the tables; frontend reads GeoJSON from `outputs/<run_id>/` | platform | working demo |
| S25 | **Day-12 provisional sweep** — run the SQL in §5 and check `data_dictionary.md` is complete | all | nothing left `is_provisional` unless declared |

### What a swap-in forces to re-run

The contracts doc tracks *when* provisional data gets replaced. This is *what has to be recomputed* each time, and it is the reason S14 should be one `make` target and not a memory exercise:

| Swap-in | Re-run | Cost |
|---|---|---|
| Real catchments (S7) | S8, S10, S11, S14–S16 | minutes |
| Real outlets (S7) | S9 step 12, S19, S20 | minutes |
| Real reef zones (S9) | S19 step 12 → `reef_exposures` | seconds |
| Real plume mask (S13) | S20, then S21 | ~1 hour |
| Confirmed AOI (S1) | every clip, i.e. S7–S13 | hours |

---

## 8. Changes from concept §18, and open decisions

**Added tables** (§18 has no equivalent, and the pipeline cannot run without them):

| Table | Why it is required |
|---|---|
| `outlets` | §18 folds `outlet_geometry` into `catchments`. It needs its own ID (`AQ-O{NN}` is in the ID contract), its own snap provenance, and its own swap-in state. |
| `satellite_scenes` | The imagery audit is the project's gate. It must be queryable, not only prose in a markdown file. |
| `catchment_surface_features` | Separates Pulga's stream from Mahdi's so the two can be re-run independently; §18's single `land_cover_features` blob couples them. |
| `catchment_rainfall`, `catchment_rainfall_climatology` | Percentile thresholds are a stored artifact. Without the climatology table, "99th percentile" is recomputed ad hoc and will silently differ between the model and the dashboard. |
| `event_catchment_features` | §18's `events.rainfall_statistics` blob is not trainable. The training matrix needs typed columns and a (event, catchment) key. |
| `forecast_runs`, `forecast_catchment_rainfall`, `forecast_exceedance` | §18 has no forecast ingestion at all, so forecast mode has nowhere to write. |
| `raster_assets` | Centralises the file↔DB bridge instead of scattering `*_path` strings. |
| `model_versions` | A prediction without a model version is unreproducible. |
| `calibration_trials` | Keeps a few hundred parameter-sweep runs out of the demo tables. |
| `alerts` | §17 exposes `GET /alerts` with no backing table. |
| `backtests` | §18 attaches `backtest_metrics` directly to `run_id`, which cannot express "same run, compared against baseline #3". |

**Changed:** `events` split into temporal event vs per-catchment statistics · `plume_forecasts` gains an explicit `probability_level` (a probabilistic product has one polygon *per level*, not one polygon) · `reef_exposures.formula_terms` added so a risk score can be audited term by term · `reef_zones.sensitivity_basis` is `NOT NULL` so the placeholder caveat cannot be dropped · `alerts.uncertainty_note` is `NOT NULL` for the same reason.

**Open decisions, for the team not for the schema:**

1. **Does `catchment_rainfall` live in Postgres or stay in Parquet only?** Load it if the dashboard plots hyetographs; skip it otherwise. 2.3 M rows either way — the question is whether anything queries it.
2. **Probability contour levels** — 0.10/0.25/0.50/0.75 is assumed above. Fix them Day 8, before `plume_forecasts` has rows, because changing them invalidates every stored polygon and every IoU.
3. **`severity_observed` labels for historical events.** With ~30 events and one usable plume observation, most severity labels will be inferred, not observed. `label_source` records which. This is the honest weak point in the training set and belongs in the model card.
4. **Re-delineation invalidates history.** If catchments change after `event_catchment_features` is populated, every rainfall zonal mean in it is stale. Contract swap-in #1 must trigger a full re-run of Karam's and Pulga's aggregations — worth a `make features` target so it is one command, not a memory exercise.

---

## Appendix A — Glossary

### CRS — Coordinate Reference System

The answer to "what do these two numbers mean?" A pair like `(34.96, 29.54)` is meaningless until you say which system it is in. The CRS defines the units, the origin, and the assumed shape of the Earth. `EPSG:####` is a catalogue number for one — EPSG is the registry that assigns them.

The project uses exactly two:

| CRS | What it is | Units | Aqaba looks like |
|---|---|---|---|
| **EPSG:4326** | WGS 84 — plain longitude/latitude on the globe | **degrees** | `34.96, 29.54` |
| **EPSG:32636** | WGS 84 / UTM zone 36N — a flat metric grid projected for the 30°E–36°E strip | **metres** | `689000, 3268000` |

Aqaba sits at ~35°E, which falls in UTM zone 36; north of the equator makes it 32636 and not 32736.

**Why 4326 for storage.** It is what everything else expects. The GeoJSON specification mandates WGS 84 lon/lat, MapLibre reads it directly, and `geometry(..., 4326)` is the interchange default in PostGIS. Handing a teammate a file in a projected CRS without saying so is how two layers end up 3,000 km apart.

**Why 32636 for every calculation.** Because *a degree is not a length*. At Aqaba's latitude:

- 1° of latitude ≈ 111.3 km
- 1° of longitude ≈ 111.3 × cos(29.5°) ≈ **96.9 km**

So a "square" 0.01° × 0.01° cell is really 1113 m × 969 m — a 15% aspect distortion. Three consequences that would land directly in the deliverables:

| What breaks | How badly |
|---|---|
| **Area** | A catchment area computed in degree-space and scaled as though degrees were square comes out **~15% too large**. `area_km2` is the runoff model's most important static feature, so the error propagates into every prediction. |
| **Distance** | §13.4 reports centroid error in metres. You cannot subtract two degree pairs and get metres. |
| **Slope** | The classic version of this bug: elevation in metres over cell spacing in degrees gives rise-over-run in "metres per degree" — slopes wrong by a factor of ~10⁵. The symptom is a slope raster full of absurd values, which is why §3.1 → 2 reprojects **before** anything is computed. |

Hence the rule from the contracts doc: **store in 4326, compute in 32636**, and pre-compute `area_km2` and `distance_to_outlet_m` as plain numeric columns so nobody downstream is tempted to re-derive them from the geometry.

**Where CRS appears in this schema.**

- `data_sources.native_crs` — what the provider ships. It varies: GLO-30, WorldCover, GEBCO and ERA5-Land all arrive in 4326, while Sentinel-2 L2A tiles arrive already in UTM — and for Aqaba that is zone 36N, so imagery needs no reprojection.
- `raster_assets.crs` — what the file on disk is actually in *after* processing. Needed because `dem_utm36n.tif` and `baseline_composite.tif` are in different systems, and a script that assumes otherwise fails silently rather than loudly.
- Every `geometry(..., 4326)` column — PostGIS enforces the declared SRID, so a 32636 insert is rejected outright instead of quietly landing in the Gulf of Guinea.

### Other terms used above

| Term | Meaning here |
|---|---|
| **COG** | Cloud Optimized GeoTIFF — a GeoTIFF laid out so a reader can fetch one window without downloading the whole file. |
| **Zarr** | Chunked array storage on disk. Same data as NetCDF, but a time-slice read touches only the chunks it needs — which is why the currents cube is rechunked to it before calibration hammers it. |
| **GRIB** | The weather-model file format. Ships with an `.idx` sidecar listing byte offsets per variable, so a single field can be fetched by HTTP range request instead of downloading the run. |
| **Zonal statistics** | Summarising a raster inside a polygon — "mean rainfall inside `AQ-C03`". The operation that turns every gridded product in §3.2 and §3.3 into a table column. |
| **D8 / D-∞** | Flow-direction algorithms. D8 sends all water from a cell to its single steepest neighbour; D-∞ splits it between two. Both produce the flow-accumulation raster that streams are extracted from. |
| **Flow accumulation** | Per cell, how many upstream cells drain through it. Threshold it and you have a stream network; its maximum inside a catchment is at the outlet. |
| **Pour point / snapping** | The cell a catchment drains through. "Snapping" nudges a hand-placed point onto the true maximum-accumulation cell nearby — `outlets.snap_distance_m` records how far it moved. |
| **SCL** | Sentinel-2 Scene Classification Layer — the per-pixel cloud / shadow / water band that drives the masking in §3.4 → 7. |
| **Windage** | The fraction of wind speed added to a particle's drift, on top of the current. One of the three parameters fitted in S20. |
| **IoU / Dice** | Overlap scores between predicted and observed plume masks. IoU = intersection ÷ union; Dice = 2 × intersection ÷ (sum of areas). Both are 0 for no overlap and 1 for a perfect match. |
| **SHAP** | Per-prediction feature attribution. Supplies the "top drivers" list in `runoff_predictions.feature_attributions` that Component H turns into a sentence. |
