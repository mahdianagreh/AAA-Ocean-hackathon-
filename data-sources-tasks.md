# ReefShield Aqaba — Data Source Assignments

**Source:** `aqaba_aqua_ai_concept.md` (Section 11 + Section 31)
**Team:** Mahdi · Karam · Pulga · Abd · Nizar

Every data source named in the concept doc, assigned to one owner.

**Read first:** [`tasks/00-contracts.md`](tasks/00-contracts.md) — the Day-1 contract that lets all five streams run in parallel with no one blocked.

**Individual task files** — each is self-contained, open only your own:

- [`tasks/mahdi.md`](tasks/mahdi.md) — Terrain & Hydrology
- [`tasks/karam.md`](tasks/karam.md) — Rainfall & Land Reanalysis
- [`tasks/pulga.md`](tasks/pulga.md) — Land Cover, Soil, Urban & Marine Habitat
- [`tasks/abd.md`](tasks/abd.md) — Satellite Imagery & Plume Detection
- [`tasks/nizar.md`](tasks/nizar.md) — Weather Forecasts & Ocean Currents

---

## Shared — do this first (Day 1, together)

Nobody downloads anything until these are locked, because every download must use the same footprint.

- [ ] **Freeze the Aqaba AOI bounding box** → commit as `data/aoi/aqaba_aoi.geojson`
- [ ] **Pick the 3–5 priority catchments** (Wadi Yutum system + neighbours draining to the Gulf)
- [ ] **CRS convention:** EPSG:4326 for storage, EPSG:32636 (UTM 36N) for area/distance maths
- [ ] **Folder convention:** `data/raw/<source>/<product>/`
- [ ] **Start the ledger** `docs/data_dictionary.md` — one row per download: product ID, version, extent, access date, license, citation
- [ ] **Confirm event dates** for Oct 2016 (primary) and Feb 2013 (backup) from the literature — Karam and Abd are both blocked without these
- [ ] **Create the shared Google Earth Engine project** — access route for MERIT, WorldCover, ACA, Sentinel-2, HLS, ERA5-Land
- [ ] **Decide the plume engine:** OpenDrift (https://opendrift.github.io/) vs a custom 2D NumPy/Xarray particle model. Pick one by Day 8, don't build both.

**Accounts to register on Day 1** (approvals can take hours): NASA Earthdata · Copernicus Climate Data Store · Copernicus Data Space · Copernicus Marine · Google Earth Engine

**Literature to pull the event dates from:**
- Katz et al. 2015 — https://www.sciencedirect.com/science/article/pii/S0012821X15001119
- Ginat et al. 2025 (NHESS) — https://nhess.copernicus.org/articles/25/3201/2025/index.html
- Al-Rousan et al. 2016 — https://pubmed.ncbi.nlm.nih.gov/27237037/
- Aqaba flash-flood LULC 2023 — https://www.sciencedirect.com/science/article/pii/S1110982322001193
- UNDP Aqaba Marine Reserve Plan 2022–2026 — https://www.undp.org/jordan/publications/aqaba-marine-reserve-management-plan-2022-2026

---

# Mahdi — Terrain & Hydrology

Feeds Component B (catchment/flow modeling). **Target: Day 2.**

### 1. Copernicus DEM GLO-30 — *preferred DEM*
- **Role:** wadi delineation, flow direction, flow accumulation, slope
- **Registration:** none via the AWS mirror
- **Links:**
  - https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
  - https://registry.opendata.aws/copernicus-dem/
- **Tasks:** pull COG tiles for the AOI → merge → clip → reproject to EPSG:32636
- **Watch out:** it's a *surface* model — buildings sit in the elevation and will route urban flow wrongly until hand-corrected near the outlets

### 2. NASA SRTM 1 arc-second — *DEM cross-check*
- **Role:** independent DEM to validate outlet positions
- **Registration:** NASA Earthdata
- **Links:**
  - https://data.nasa.gov/dataset/nasa-shuttle-radar-topography-mission-global-1-arc-second-netcdf-v003-57aa4
  - https://search.earthdata.nasa.gov/
- **Tasks:** delineate catchments on both DEMs, compare outlets, commit to one DEM and document why

### 3. MERIT Hydro — *flow-direction cross-check*
- **Role:** validate the main wadi channels against your DEM-derived streams
- **Registration:** Earth Engine
- **Link:** https://developers.google.com/earth-engine/datasets/catalog/MERIT_Hydro_v1_0_1
- **Watch out:** ~90 m — cross-check only, never delineate small wadis from it

### 4. HydroSHEDS / HydroBASINS — *regional context*
- **Role:** basin polygons for the context map layer
- **Registration:** none
- **Links:**
  - https://www.hydrosheds.org/products
  - https://www.hydrosheds.org/products/hydrobasins
  - https://www.hydrosheds.org/hydrosheds-core-downloads
- **Watch out:** too coarse for the model — presentation layer only

**Mahdi's deliverables:** committed DEM · 3–5 catchment polygons with snapped coastal outlets · per-catchment area, slope, drainage density, flow-accumulation stats

> **Lock the outlet coordinates by Day 4.** They are the plume release point for Nizar's forcing and Abd's validation. If they move late, everything downstream re-runs.

---

# Karam — Rainfall & Land Reanalysis

Feeds Component A (event detection) and Component C (runoff model). **Target: Day 3–4.**

### 1. NASA GPM IMERG V07 — Final Run
- **Role:** historical rainfall, event mining, training labels
- **Registration:** NASA Earthdata (use `earthaccess`)
- **Links:**
  - https://gpm.nasa.gov/data/imerg
  - https://gpm.nasa.gov/data/directory
  - https://disc.gsfc.nasa.gov/
  - https://search.earthdata.nasa.gov/
- **Tasks:** pull half-hourly 2000→present, subset at the source · build rolling 1h/3h/6h/24h accumulations per catchment · rank extreme windows by percentile
- **Check:** Oct 2016 and Feb 2013 must both appear in the top windows. If not, your AOI subset or time-zone handling is wrong.
- **Watch out:** ~0.1° (~11 km) — one cell may cover an entire small catchment and smooths localized convective cells

### 2. NASA GPM IMERG — Early / Late Run
- **Role:** near-real-time monitoring for the live demo path
- **Registration:** NASA Earthdata
- **Links:** same as above
- **Watch out:** preliminary and uncalibrated — never mix Early-Run values into a training set built from Final Run

### 3. CHIRPS — *optional cross-check*
- **Role:** independent daily rainfall confirmation for the candidate events
- **Registration:** none
- **Link:** https://www.chc.ucsb.edu/data/chirps
- **Value:** cheap credibility — if IMERG and CHIRPS agree a day was extreme, event confidence rises

### 4. ERA5-Land
- **Role:** soil moisture, surface/subsurface runoff proxy, wind, antecedent conditions
- **Registration:** Copernicus CDS (`cdsapi`)
- **Links:**
  - https://www.ecmwf.int/en/era5-land
  - https://cds.climate.copernicus.eu/
  - https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY
- **Variables:** volumetric soil water L1, total precipitation, surface runoff, sub-surface runoff, 10 m u/v wind, 2 m temperature
- **Tasks:** extract antecedent soil moisture at T−24h and T−72h, plus 7-day prior rainfall, for every candidate event
- **Watch out:** ~9 km, and its precipitation will *not* match IMERG. Use ERA5-Land for soil/wind state, IMERG for rainfall magnitude — don't average them.

**Karam's deliverables:** ranked candidate-event table including Oct 2016 and Feb 2013 · antecedent features joined to every event

---

# Pulga — Land Cover, Soil, Urban & Marine Habitat

Feeds Component C (runoff features), Component D (sediment proxy), Component G (reef exposure). **Target: Day 4, reef zones by Day 10.**

### 1. ESA WorldCover 10 m
- **Role:** bare ground, built-up, vegetation, water → runoff and erosion features
- **Registration:** none
- **Links:**
  - https://esa-worldcover.org/en/data-access
  - https://worldcover2021.esa.int/download
- **Tasks:** download AOI tile (2021) · compute per-catchment class fractions
- **Check:** bare-ground fraction should be high for hyper-arid catchments — the doc's example record assumes ~74%
- **Watch out:** 2020/2021 baseline only, no time series

### 2. ISRIC SoilGrids
- **Role:** infiltration and erodibility proxies
- **Registration:** none
- **Links:**
  - https://docs.isric.org/globaldata/soilgrids/index.html
  - https://rest.isric.org/soilgrids/v2.0/docs
  - https://files.isric.org/soilgrids/latest/data/
- **Variables:** clay, sand, silt, organic carbon, bulk density, coarse fragments (0–5 cm and 5–15 cm)
- **Tasks:** aggregate to per-catchment means
- **Watch out:** globally model-derived, not surveyed — use as a *relative* erodibility proxy, never quote as measured local soil

### 3. OpenStreetMap — Jordan extract
- **Role:** roads, built-up/impervious surfaces, mapped drainage channels, industrial and port features
- **Registration:** none
- **Links:**
  - https://download.geofabrik.de/asia/jordan.html
  - https://www.openstreetmap.org/export/
- **Tasks:** clip the `.osm.pbf` to AOI · extract roads, buildings, waterways/culverts, industrial polygons · flag any mapped drainage that contradicts Mahdi's DEM flow paths
- **Watch out:** completeness in Aqaba is unknown — an unmapped channel is not an absent channel

### 4. Allen Coral Atlas
- **Role:** shallow coral geomorphic + benthic habitat → the reef exposure calculation
- **Registration:** Earth Engine or Atlas access
- **Links:**
  - https://allencoralatlas.org/
  - https://developers.google.com/earth-engine/datasets/catalog/ACA_reef_habitat_v2_0
- **Tasks:** export habitat layers (5 m) for the Aqaba coast · split into named zones `R-01`, `R-02`, … with areas in km² · add a `sensitivity_weight` column **explicitly labeled a placeholder pending marine-scientist input**
- **Watch out:** ACA maps shallow reef *habitat*, not ecological sensitivity. The weights are the team's assumption — say so on the slide.

### 5. GEBCO bathymetry
- **Role:** depth constraints and coastline barrier for the plume transport model
- **Registration:** none
- **Links:**
  - https://www.gebco.net/data-products/gridded-bathymetry-data
  - https://download.gebco.net/downloads
- **Tasks:** download the 15 arc-second grid for the northern Gulf · derive a water mask and a depth field the particle engine can read
- **Watch out:** ~450 m at this latitude — fine for basin geometry, useless for reef-scale depth change or harbour structures

**Pulga's deliverables:** per-catchment land-cover + soil feature tables · OSM vector layers · named reef zones with areas · depth field and coastline mask

---

# Abd — Satellite Imagery & Plume Detection

Feeds Component E (plume detection) and all validation/backtesting. **Target: imagery audit Day 5, plume mask Day 6.**

> **This is the project's gating risk.** The concept doc's Final Recommendation makes the whole idea conditional on finding one usable post-event scene. Abd's Day-5 audit *is* that gate — report the answer to the team the day it's known, good or bad.

### 1. Sentinel-2 L2A — *primary imagery*
- **Role:** observed plume extraction, pre-event baseline composite, validation ground truth
- **Registration:** Copernicus Data Space (+ Earth Engine as the fast path)
- **Links:**
  - https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel2.html
  - https://browser.dataspace.copernicus.eu/
  - https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED
- **Tasks:** **search before you download** — visually inspect every scene within ±10 days of each candidate event in the Copernicus Browser · score each on cloud % over AOI water, sun glint, plume visibility, days since event · then pull the chosen post-event scene + 5–10 clear pre-event scenes
- **Bands:** B2, B3, B4, B8, B11, B12 + SCL
- **The gate:** at least one event needs a post-event scene within ~5 days, under ~20% cloud over the water, with a visually distinguishable plume. If none passes, escalate the same day.
- **Watch out:** revisit is ~5 days (2–3 with both satellites) but a plume can disperse in 24–72 h — timing luck is a real risk, which is why several events get audited

### 2. NASA HLS (Harmonized Landsat Sentinel-2)
- **Role:** extra revisits to fill Sentinel-2 gaps
- **Registration:** NASA Earthdata or Earth Engine
- **Links:**
  - https://hls.gsfc.nasa.gov/
  - https://hls.gsfc.nasa.gov/data-access-and-tools/
  - https://developers.google.com/earth-engine/datasets/catalog/NASA_HLS_HLSS30_v002
- **Tasks:** query HLSS30 + HLSL30 v2.0 over the same event windows · fill any date where S2 was cloudy but Landsat wasn't
- **Value:** roughly doubles the chance of catching the plume
- **Watch out:** 30 m — plume edges are coarser than Sentinel-2's 10 m

### 3. Landsat 8/9 Level-2 — *backup scenes*
- **Role:** the only optical option for the Feb 2013 event (Sentinel-2A launched 2015)
- **Registration:** NASA Earthdata
- **Link:** https://search.earthdata.nasa.gov/
- **Tasks:** verdict on whether Feb 2013 is validatable at all — flag early, since it may fail as a backup despite being well documented

### 4. Copernicus Marine ocean-colour guidance — *method reference*
- **Role:** how to derive turbidity / suspended matter from Sentinel-2 HR products
- **Registration:** none
- **Link:** https://help.marine.copernicus.eu/en/articles/5194057-introduction-to-ocean-colour-sentinel-2-high-resolution-products
- **Tasks:** implement and compare NDSSI, NSMI, red/green band ratios, and a plain multi-date reflectance anomaly on the demo scene · pick one primary index and document why with a side-by-side figure
- **Pipeline order:** pre-event baseline composite → water mask → spectral features → post-event anomaly → strip glint/cloud/land-edge artifacts → probability raster → manual QC
- **Watch out:** do not start with a U-Net. The labeled set is too small; spectral anomaly + manual QC is what can actually be validated and explained in two weeks.

**Abd's deliverables:** `docs/event_audit.md` scoring every event × scene with a go/no-go · cloud-free pre-event composite · manually QC'd observed plume mask as both raster probability and vector polygon

---

# Nizar — Weather Forecasts & Ocean Currents

Feeds Component A (forecast mode) and Component F (plume transport). **Target: forecasts Day 5, currents Day 8.**

### 1. NOAA GFS — *deterministic forecast*
- **Role:** forecast rainfall and wind
- **Registration:** none (public cloud bucket)
- **Links:**
  - https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast
  - https://registry.opendata.aws/noaa-gfs-bdp-pds/
- **Tasks:** pull a current run from the AWS open-data bucket · extract AOI rainfall + 10 m wind to 48 h lead · confirm the forecast pipeline runs end-to-end on today's data whatever the weather
- **Watch out:** ~0.25° standard grid

### 2. NOAA GEFS — *ensemble / uncertainty*
- **Role:** exceedance probability and the dashboard's confidence number
- **Registration:** none (public cloud bucket)
- **Links:**
  - https://www.ncei.noaa.gov/products/weather-climate-models/global-ensemble-forecast
  - https://registry.opendata.aws/noaa-gefs/
- **Tasks:** pull ensemble members for the AOI · compute the fraction of members exceeding each catchment's 3 h rainfall threshold
- **Why it matters:** this is what turns the confidence figure from a guess into something defensible to a judge
- **Watch out:** coarse for local convection

### 3. ECMWF IFS / AIFS Open Data — *comparison forecast*
- **Role:** second opinion, two-model agreement indicator
- **Registration:** none for the open subset
- **Links:**
  - https://www.ecmwf.int/en/forecasts/datasets/open-data
  - https://data.ecmwf.int/
  - https://github.com/ecmwf/ecmwf-opendata
- **Tasks:** install the `ecmwf-opendata` client · pull the same AOI/lead window as GFS · build a GFS-vs-IFS agreement flag
- **Watch out:** rolling archive, limited variables, short retention — it will not serve historical backfill

### 4. Copernicus Global Ocean Physics Analysis & Forecast — *primary currents*
- **Role:** u/v current forcing for the particle engine
- **Registration:** Copernicus Marine (`copernicusmarine`)
- **Link:** https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/description
- **Tasks:** pull u/v for the northern Gulf — surface plus upper depth levels · deliver as an Xarray dataset the engine can interpolate at any (lon, lat, time) with no manual reshape

### 5. HYCOM — *backup currents*
- **Role:** independent current field, direction comparison at the outlet
- **Registration:** none (public data server)
- **Links:**
  - https://www.hycom.org/dataserver
  - https://www.hycom.org/ocean-prediction

> **Watch out — the project's single biggest accuracy limit.** Both current products are ~1/12° (~9 km) across a gulf only ~15–25 km wide, so roughly 2–3 grid cells span the whole basin and nearshore circulation is effectively unresolved. This is exactly why the output must be a probabilistic exposure zone, not a meter-level prediction. Nizar should be the one who can explain this to a judge.

**Nizar's deliverables:** live forecast path producing a rainfall probability per catchment · interpolation-ready current fields for the plume engine

---

## Critical path

1. **Day 1 — everyone:** AOI box, catchment shortlist, accounts. Nothing starts until the box is frozen.
2. **Day 3 — Karam:** event dates from the literature, then the IMERG candidate table. Abd can't start the audit without dates.
3. **Day 4 — Mahdi:** outlet coordinates locked. Nizar and Abd both depend on them.
4. **Day 5 — Abd:** the imagery gate. Highest-risk item in the plan — the project either proceeds or changes its demo event.
5. **Day 8 — Nizar:** currents interpolation-ready, or the plume engine stalls.
6. **Day 4 / Day 10 — Pulga:** catchment features by Day 4 (blocks the runoff model), reef zones by Day 10 (blocks the exposure engine).
