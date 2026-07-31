# Karam — Rainfall & Land Reanalysis

**Project:** ReefShield Aqaba
**Workstream:** A + C (event mining and forcing data)
**Feeds:** Component A (rainfall event detection) → Component C (runoff risk model)
**Window:** Day 3 for IMERG history, Day 4 for ERA5-Land features

---

## Why your stream matters

You decide **which historical event the whole demo is built on**. Abd cannot start the satellite imagery audit until you hand over candidate event dates, and the runoff model has no training labels until your event table exists.

> **Day 3 is your hard deadline for candidate event dates.** Abd's Day-5 imagery gate — the project's single biggest risk — sits directly downstream of your output.

---

## Before you download anything

- [ ] **AOI bounding box frozen** (Mahdi commits it as `data/aoi/aqaba_aoi.geojson`). Clip everything to this exact box.
- [ ] **Catchment polygons from Mahdi** — you need these to compute per-catchment rainfall rather than per-pixel.
- [ ] **NASA Earthdata account** registered → needed for IMERG.
- [ ] **Copernicus Climate Data Store account** registered → needed for ERA5-Land. **Do this on Day 1** — approval is not always instant and ERA5-Land requests also queue.
- [ ] **Event dates pulled from the literature** (see below) before you start scanning rainfall.

### Environment

```bash
pip install earthaccess xarray netCDF4 zarr cdsapi dask rioxarray
```

`earthaccess` handles NASA Earthdata auth for you — much less painful than raw `.netrc` wrangling.

### Literature — get the event dates first

The doc's primary candidate is **October 2016** and its backup is **February 2013**. Exact dates and times come from:

- Ginat et al. 2025, *Anatomy of a Flash Flood in a Hyperarid Environment* (NHESS) — https://nhess.copernicus.org/articles/25/3201/2025/index.html
- Katz et al. 2015, *Desert flash floods form hyperpycnal flows in the coral-rich Gulf of Aqaba* — https://www.sciencedirect.com/science/article/pii/S0012821X15001119

Pull out: exact date/time of both events, and the sediment tonnages (≈24,000 t for Oct 2016, ≈21,000 t for Feb 2013) — those numbers are the pitch's evidence that this problem is real.

---

## 1. NASA GPM IMERG V07 — Final Run

**Role:** historical rainfall, event mining, training labels
**Resolution:** ~0.1° (~11 km), half-hourly, 2000 → present
**Registration:** NASA Earthdata

**Links**
- https://gpm.nasa.gov/data/imerg
- https://gpm.nasa.gov/data/directory
- https://disc.gsfc.nasa.gov/
- https://search.earthdata.nasa.gov/

**Tasks**
- [ ] Set up `earthaccess` auth and confirm you can list granules.
- [ ] Pull half-hourly Final Run for the AOI, 2000 → present. **Subset spatially at the source** — do not download global grids, you will drown.
- [ ] Compute rolling **1 h / 3 h / 6 h / 24 h** accumulations per catchment.
- [ ] Compute per-catchment percentile thresholds and a seasonal-climatology anomaly score.
- [ ] Rank every extreme rainfall window and export the candidate-event table.

**Deliverables**
- `data/raw/imerg/` (Zarr or NetCDF)
- `data/processed/events/rainfall_candidates.parquet`
- `backend/src/ingestion/imerg.py`

**Sanity check that actually matters:** October 2016 and February 2013 must **both** appear in your top-ranked rainfall windows. If they don't, something is wrong before you go further — the usual culprits are AOI subsetting off by a grid cell, or UTC vs local time handling shifting the event across a day boundary. Do not proceed until they show up.

**Watch out:** ~11 km cells mean a single grid cell may cover an entire small catchment, and localized convective cells — exactly the kind that cause Aqaba flash floods — get smoothed out. This is a documented limitation, not a bug in your pipeline. Say it plainly on the slide.

---

## 2. NASA GPM IMERG — Early / Late Run

**Role:** near-real-time monitoring for the live demo path
**Registration:** NASA Earthdata

**Links:** same portals as above.

**Tasks**
- [ ] Add an `early` mode to `imerg.py` alongside `final`.
- [ ] Wire one Early-Run fetch so the live-forecast path works.
- [ ] Measure the actual latency in hours and surface it in the dashboard's data-quality indicator.

**Watch out:** Early and Late runs are **preliminary and uncalibrated**. Never mix Early-Run values into a training set built from Final Run — the distributions differ and you'd be training on one product and inferring on another.

---

## 3. CHIRPS — optional cross-check

**Role:** independent daily rainfall confirmation
**Registration:** none

**Link**
- https://www.chc.ucsb.edu/data/chirps

**Tasks**
- [ ] Pull daily CHIRPS for the AOI over your candidate event dates.
- [ ] Compare daily totals against IMERG for the same days.
- [ ] Put the comparison table in `notebooks/01_event_mining.ipynb`.

**Why do it:** cheap credibility. Two independent satellite rainfall products agreeing that a given day was extreme is a much stronger claim than one product's word. Costs you an hour, strengthens the validation story.

---

## 4. ERA5-Land

**Role:** soil moisture, surface/subsurface runoff proxy, wind, antecedent conditions
**Resolution:** ~9 km, hourly, 1950 → near present
**Registration:** Copernicus CDS

**Links**
- https://www.ecmwf.int/en/era5-land
- https://cds.climate.copernicus.eu/
- https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_HOURLY

**Variables to pull**
- volumetric soil water layer 1 (surface soil moisture)
- total precipitation
- surface runoff
- sub-surface runoff
- 10 m u and v wind components
- 2 m temperature

**Tasks**
- [ ] Configure `cdsapi` credentials.
- [ ] Pull the hourly variables above for the AOI across all candidate event windows.
- [ ] Extract **antecedent conditions** for every candidate event: soil moisture at T−24 h and T−72 h, plus 7-day prior rainfall.
- [ ] Join those columns into the event table.

**Deliverables**
- `data/raw/era5_land/`
- antecedent feature columns in `data/processed/events/rainfall_candidates.parquet`
- `backend/src/ingestion/era5_land.py`

**Watch out — a trap worth naming.** ERA5-Land precipitation will **not** match IMERG, sometimes not even closely. They are different products built different ways. Use **ERA5-Land for soil moisture and wind state, IMERG for rainfall magnitude.** Do not average them, and do not treat the disagreement as an error to be fixed.

**Why antecedent moisture matters scientifically:** dry soil in a hyper-arid catchment can produce *more* runoff, not less, because crusted dry surfaces have low infiltration during intense rainfall. This is counterintuitive and worth being able to explain — it's one of the nonlinear relationships that justifies using a model rather than a simple threshold.

---

## Definition of done

1. **IMERG history ingested** and stored efficiently (Zarr recommended over thousands of loose NetCDFs).
2. **Ranked candidate-event table** that includes Oct 2016 and Feb 2013, with per-catchment rainfall accumulations and percentiles.
3. **CHIRPS cross-check** documented for the candidate events.
4. **ERA5-Land antecedent features** joined to every candidate event.
5. **Ingestion modules** committed: `imerg.py` (final + early modes), `era5_land.py`.
6. **Every product ID, variable list, and access date** in `docs/data_dictionary.md`.

**Target files**
```text
data/raw/imerg/
data/raw/era5_land/
data/processed/events/rainfall_candidates.parquet
backend/src/ingestion/imerg.py
backend/src/ingestion/era5_land.py
notebooks/01_event_mining.ipynb
```

**Event record schema** — the concept doc (§12.3) defines the target shape. Your columns should include: `event_id`, `start_time_utc`, `catchment_id`, `rain_1h_mm`, `rain_3h_mm`, `rain_24h_mm`, `soil_moisture`, `surface_runoff_proxy`, `historical_percentile`, `quality_score`.

---

## Who depends on you

| Teammate | Needs from you | By when |
|---|---|---|
| **Abd** | candidate event dates — cannot start the imagery audit without them | **Day 3** |
| **Nizar** | event windows — to pull matching current fields for those dates | Day 8 |
| **Whoever builds the runoff model** | the full event feature table with labels | Day 7 |

## What you depend on

| From | What | By when |
|---|---|---|
| **Mahdi** | catchment polygons — to aggregate rainfall per catchment instead of per pixel | Day 3 |
| **Everyone** | the frozen AOI box | Day 1 |

You can start downloading IMERG over the raw bounding box on Day 1 and aggregate to catchments as soon as Mahdi's polygons land — don't sit idle waiting for them.
