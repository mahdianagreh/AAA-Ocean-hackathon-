# Nizar — Weather Forecasts & Ocean Currents

**Project:** ReefShield Aqaba
**Workstream:** A + C (forecast mode and transport forcing)
**Feeds:** Component A (forecast-mode event detection) → Component F (probabilistic plume transport)
**Window:** Day 5 for the forecast path, Day 8 for currents

---

## Why your stream matters

You own the two things that make this a **forecasting** platform rather than a hindcast: the live weather path that gives the system lead time, and the ocean current fields that move the plume.

You also own the project's most important honest caveat. The current products are ~9 km across a gulf ~15–25 km wide, which means nearshore circulation is effectively unresolved — and **that single fact is why the whole platform outputs probabilistic exposure zones instead of exact predictions.** You should be the person on the team who can explain that to a judge without flinching.

---

## Before you download anything

- [ ] **AOI bounding box frozen** (Mahdi commits `data/aoi/aqaba_aoi.geojson`).
Read [`00-contracts.md`](00-contracts.md) first — **you start Day 1 and wait for nobody.**

- [ ] **Copernicus Marine account** registered → needed for the primary currents. **Day 1** — don't leave this to Day 8.
- [ ] **Real outlets have landed (2 Aug)** — use `data/processed/vectors/outlets.gpkg`. **Five release points, not the two the contract said for a day.** The 30 m DEM resolves 30 discharge points on Jordan's coast where HydroBASINS saw two; the five selected each have their own mouth.

  | Outlet | Catchment | lon, lat | Upstream |
  |---|---|---|---:|
  | `AQ-O01` | `AQ-C01` Wadi Yutum | 34.97073, 29.54560 | 4,453.1 km² |
  | `AQ-O02` | `AQ-C02` | 34.97643, 29.47270 | 64.9 km² |
  | `AQ-O03` | `AQ-C03` | 34.96416, 29.38167 | 59.9 km² |
  | `AQ-O04` | `AQ-C04` | 34.96622, 29.36052 | 42.7 km² |
  | `AQ-O05` | `AQ-C05` | 34.95998, 29.35737 | 35.6 km² |

  `AQ-O01` carries 96% of the discharge — if you only wire up one release point for the demo, wire that one. The other four are within 13 km of each other on the southern coast, so their plumes will overlap and should be modelled together rather than as independent events.
- [ ] **Pull your own GEBCO copy.** It's a 10-minute download with no dependencies — don't wait for Pulga's coastline and depth field. Two people having their own is fine.
- [ ] **Event dates** are in `docs/event_dates.md` from Day 1, straight from the literature. You don't need Karam's IMERG ranking to know which windows to pull.
- [ ] **Publish P5 · synthetic plume mask on Day 1 (~30 min):** a plain ellipse offset from an outlet, saved in the exact format Abd's real mask will use → `data/processed/plume/observed_plume_PROVISIONAL.gpkg`. This is what lets you build and test the entire calibration parameter search before any satellite mask exists.

### Environment

```bash
pip install xarray netCDF4 zarr dask
pip install copernicusmarine        # Copernicus Marine toolbox
pip install ecmwf-opendata          # ECMWF open data client
pip install cfgrib herbie-data      # GRIB handling for GFS/GEFS
```

GRIB is the format you'll fight with most. `cfgrib` works but is picky about index files; `herbie` wraps the NOAA cloud buckets and saves real time.

---

## Part 1 — Weather Forecasts

### 1. NOAA GFS — deterministic forecast

**Role:** forecast rainfall and wind
**Resolution:** ~0.25°
**Registration:** none (public cloud bucket)

**Links**
- https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast
- https://registry.opendata.aws/noaa-gfs-bdp-pds/

**Tasks**
- [ ] Pull a current run from the AWS open-data bucket — no credentials needed.
- [ ] Extract AOI total precipitation and 10 m u/v wind out to **48 h lead**.
- [ ] Confirm the forecast pipeline runs **end-to-end on today's data, whatever the weather is doing.**

**Deliverable:** `backend/src/ingestion/gfs.py` + one cached live forecast for the demo

**Important framing:** the demo must work on a dry sunny day. The point isn't to show a storm — it's to show the pipeline ingesting a live forecast and producing a (correctly low) risk number. A system that only demos during rainfall isn't demoable.

---

### 2. NOAA GEFS — ensemble / uncertainty

**Role:** exceedance probability, and the dashboard's confidence figure
**Registration:** none (public cloud bucket)

**Links**
- https://www.ncei.noaa.gov/products/weather-climate-models/global-ensemble-forecast
- https://registry.opendata.aws/noaa-gefs/

**Tasks**
- [ ] Pull the ensemble members for the AOI.
- [ ] Compute **exceedance probability**: the fraction of members exceeding each catchment's 3 h rainfall threshold (thresholds come from Karam's percentile work).
- [ ] Feed this into `event_probability` in the Component A output.

**Why this is the highest-value item in your stream:** it's what turns the dashboard's confidence number from a made-up figure into a defensible one. "72% of ensemble members exceed the catchment's 99th-percentile 3-hour rainfall" is a real statement. "Confidence: moderate" with no derivation is not, and a judge will ask.

**Watch out:** GEFS is coarse for local convection. The ensemble spread tells you about synoptic-scale uncertainty; it will not capture whether a single thunderstorm cell lands on Wadi Yutum or 10 km away.

---

### 3. ECMWF IFS / AIFS Open Data — comparison forecast

**Role:** independent second opinion, two-model agreement indicator
**Registration:** none for the open subset

**Links**
- https://www.ecmwf.int/en/forecasts/datasets/open-data
- https://data.ecmwf.int/
- https://github.com/ecmwf/ecmwf-opendata

**Tasks**
- [ ] Install and configure the `ecmwf-opendata` client.
- [ ] Pull the same AOI and lead-time window as GFS.
- [ ] Build a **GFS-vs-IFS agreement flag** to surface in the dashboard.

**Deliverable:** `backend/src/ingestion/ecmwf.py` + the agreement indicator

**Watch out:** the open subset is a **rolling archive** with limited variables and short retention. It cannot serve historical backfill — don't plan any part of the backtest around it. Live and near-real-time only.

**Optional but cheap credibility:** AIFS is ECMWF's ML-based forecast model. Mentioning that the platform can ingest an AI weather model alongside a physics-based one fits the track's framing well, and it's the same client.

---

## Part 2 — Ocean Currents

### 4. Copernicus Global Ocean Physics Analysis & Forecast — primary currents

**Role:** u/v current forcing for the particle engine
**Resolution:** ~1/12° (~9 km), daily updated
**Registration:** Copernicus Marine

**Link**
- https://data.marine.copernicus.eu/product/GLOBAL_ANALYSISFORECAST_PHY_001_024/description

**Product:** `GLOBAL_ANALYSISFORECAST_PHY_001_024`

**Tasks**
- [ ] Install and authenticate `copernicusmarine`.
- [ ] Pull u/v currents for the northern Gulf: **surface plus the upper depth levels** (the plume may move as a dense underwater flow, not only at the surface — see the hyperpycnal-flow note below).
- [ ] Pull for both the historical event windows and the live forecast period.
- [ ] Deliver as an Xarray dataset the particle engine can query at any `(lon, lat, time)` **without a manual reshape step**.

**Deliverables**
- `data/raw/currents/`
- `backend/src/ingestion/ocean_currents.py`

**Acceptance:** the particle engine calls your interpolator and gets u/v back. If someone has to transpose dimensions or fix coordinate names before using it, it's not done.

---

### 5. HYCOM — backup currents

**Role:** independent current field, direction cross-check at the outlet
**Resolution:** global 1/12°
**Registration:** none (public data server)

**Links**
- https://www.hycom.org/dataserver
- https://www.hycom.org/ocean-prediction

**Tasks**
- [ ] Pull the equivalent u/v fields for the event windows.
- [ ] Compare current direction at the outlet against Copernicus.
- [ ] Document agreement or disagreement.

**Why bother:** if two independent ocean models agree the current was heading south during the event, your plume direction claim is much stronger. If they disagree, that's genuinely important to know — and it belongs in the uncertainty discussion rather than being quietly dropped.

---

## The limitation you own

> **~1/12° (~9 km) resolution across a gulf only ~15–25 km wide means roughly 2–3 grid cells span the entire basin.** Nearshore circulation — precisely where the reefs are — is effectively unresolved.

This is documented in the concept doc as a **High probability / High impact** risk (§25) and as a known limitation (§24.3). It is not something you can fix with better downloading. What you can do:

1. **Present ensemble exposure zones, not single trajectories.** Run many particles with stochastic diffusion; show a probability field.
2. **State the resolution explicitly in the UI** next to the plume layer.
3. **Show the HYCOM-vs-Copernicus comparison** as an honest measure of forcing uncertainty.
4. **Have the answer ready:** "The Gulf is narrower than 3 grid cells of the best free global ocean model, so we don't claim meter-level accuracy — we output probabilistic exposure zones and we tell the user the confidence. Higher-resolution local current measurements are Phase 2."

That answer is stronger than a vague one, and the doc's §23.4 explicitly warns against claiming exactness.

**One scientific note worth knowing:** Katz et al. 2015 found Aqaba flash floods form **hyperpycnal flows** — sediment-dense water that sinks and travels along the seabed rather than floating as a surface plume. Surface currents may therefore be the *wrong* forcing for part of the sediment mass. Pulling upper depth levels rather than surface-only is a cheap hedge, and being able to mention this shows you read the science.

---

## Definition of done

1. **Live forecast path** producing a per-catchment rainfall probability, working on today's data regardless of weather.
2. **GEFS exceedance probability** wired into the confidence number.
3. **GFS-vs-IFS agreement flag** implemented.
4. **Current fields interpolation-ready** for the particle engine — surface and upper depths, both historical windows and live.
5. **HYCOM-vs-Copernicus direction comparison** documented.
6. **A written, one-paragraph statement of the resolution limitation** that anyone on the team can read off the slide.
7. **Every product ID, variable list, and access date** in `docs/data_dictionary.md`.

**Target files**
```text
data/raw/currents/
data/raw/forecasts/gfs/
data/raw/forecasts/gefs/
data/raw/forecasts/ecmwf/
backend/src/ingestion/gfs.py
backend/src/ingestion/gefs.py
backend/src/ingestion/ecmwf.py
backend/src/ingestion/ocean_currents.py
docs/forcing_limitations.md
```

---

## Handoffs — non-blocking

| Teammate | What they get from you | Are they blocked? |
|---|---|---|
| **Particle engine** | interpolation-ready current + wind fields | It's yours — build it Day 1 against provisional outlets |
| **Calibration** | current fields for the demo window | **No** — dates are known Day 1 from the literature |
| **Frontend** | live forecast output | Day 12, and it works on any weather |

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Mahdi** | real outlet coordinates | **No** — provisional from Day 1; the swap is a config change |
| **Karam** | per-catchment 3 h rainfall thresholds | **No** — ask for a rough number early, refine later |
| **Pulga** | coastline + depth field | **No** — pull your own GEBCO, 10 minutes |
| **Abd** | observed plume mask | **Only for final calibration** — see below |

### The one real dependency, and how it's reduced

Calibration tunes diffusion, windage and settling by comparing simulated plumes against Abd's observed mask. You genuinely cannot calibrate against an observation that doesn't exist.

**So don't wait for it.** Build and test the entire parameter search against your synthetic mask (P5) — the grid search, the metric computation, the best-parameter selection, all of it. When Abd's real mask lands, you swap one file path and re-run. Roughly an hour, not days of blocked work.

**Start Day 1.** GFS, GEFS, ECMWF and both current products need nothing but the padded download box.
