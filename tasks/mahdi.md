# Mahdi — Terrain & Hydrology

**Project:** ReefShield Aqaba
**Workstream:** A (Geospatial and Hydrology)
**Feeds:** Component B (catchment and flow modeling) → Component C (runoff model features)
**Window:** Day 2 for the DEM, Day 4 for locked outlets

---

## Why your stream matters

You produce the geometry everyone else's work sits on. The catchment polygons decide which rainfall cells Karam averages, and the **coastal outlet coordinates are the plume release point** for Nizar's current forcing and Abd's satellite validation.

> **Hard deadline: outlets locked by Day 4.** If an outlet moves after that, Nizar's transport runs and Abd's plume comparison both re-run from scratch.

---

## Before you download anything

- [ ] **AOI bounding box frozen** and committed as `data/aoi/aqaba_aoi.geojson`. Starting proposal to confirm on a map — *not verified*: roughly `34.90–35.05 °E, 29.35–29.60 °N`, extended seaward far enough to contain a 24 h plume. Every teammate clips to this exact box.
- [ ] **Priority catchments picked:** 3–5, the Wadi Yutum system plus neighbours that drain to the Gulf.
- [ ] **CRS convention:** EPSG:4326 for storage and exchange, **EPSG:32636** (UTM 36N) for all area, slope, and distance maths.
- [ ] **NASA Earthdata account** registered (needed for SRTM).
- [ ] **Google Earth Engine project** created — you own this for the team; it's the access route for MERIT Hydro, WorldCover, ACA, Sentinel-2, HLS.
- [ ] **Ledger row template** ready in `docs/data_dictionary.md`: product ID, version, extent, access date, license, citation.

### Environment

```bash
# geospatial stack
pip install rasterio rioxarray geopandas shapely pyproj
# hydrology — pick one, whiteboxtools is the least painful to install
pip install whitebox richdem
```

`richdem` can be awkward to build on macOS. If it fights you, `whitebox` (WhiteboxTools) ships prebuilt binaries and covers everything you need: fill, flow direction, accumulation, watershed, stream extraction.

---

## 1. Copernicus DEM GLO-30 — your primary DEM

**Role:** wadi delineation, flow direction, flow accumulation, slope
**Resolution:** ~30 m
**Registration:** none needed via the AWS mirror

**Links**
- https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM
- https://registry.opendata.aws/copernicus-dem/

**Tasks**
- [ ] Identify the 1° tiles covering the AOI — Aqaba sits at ~29.5 °N, 35 °E, so expect the `N29_00_E034_00` / `N29_00_E035_00` neighbourhood.
- [ ] Pull the COGs from the AWS mirror (`s3://copernicus-dem-30m/`, public, no credentials).
- [ ] Merge tiles → clip to AOI → reproject to EPSG:32636.
- [ ] Record tile IDs and access date in the ledger.

**Deliverables**
- `data/raw/dem/cop_glo30_aqaba.tif`
- `data/processed/dem/dem_utm36n.tif`

**Watch out — this one will bite you.** GLO-30 is a **surface** model, not a terrain model. Buildings, walls, and embankments are baked into the elevation values. In urban Aqaba, that means flow will route *around* structures that water actually passes through or under. Your coastal outlets are exactly where the city is densest, so plan on hand-inspecting and correcting the last few hundred metres of each channel.

---

## 2. NASA SRTM 1 arc-second — DEM cross-check

**Role:** independent DEM to validate outlet positions
**Resolution:** ~30 m
**Registration:** NASA Earthdata

**Links**
- https://data.nasa.gov/dataset/nasa-shuttle-radar-topography-mission-global-1-arc-second-netcdf-v003-57aa4
- https://search.earthdata.nasa.gov/

**Tasks**
- [ ] Download the same AOI extent.
- [ ] Run the **full delineation chain on both DEMs independently**.
- [ ] Compare outlet coordinates catchment by catchment.
- [ ] Commit to one DEM and write down why, in `docs/data_dictionary.md`.

**Acceptance:** the two DEMs agree on each priority catchment's coastal outlet to within ~200 m. Where they disagree, you explain the cause (usually urban surface artifacts, or a flat coastal plain where flow direction is genuinely ambiguous).

**Why bother:** a judge asking "how do you know your wadi outlets are right?" is a likely question. Two independent DEMs agreeing is a real answer. One DEM is not.

**Watch out:** older acquisition (2000), and it has known voids and artifacts. It's also a surface model.

---

## 3. MERIT Hydro — flow-direction cross-check

**Role:** validate the main wadi channels against your DEM-derived streams
**Resolution:** ~3 arc-seconds (~90 m)
**Registration:** Earth Engine

**Link**
- https://developers.google.com/earth-engine/datasets/catalog/MERIT_Hydro_v1_0_1

**Tasks**
- [ ] Export flow direction and upstream drainage area for the AOI via Earth Engine.
- [ ] Overlay on your 30 m stream network.
- [ ] Confirm the main channels agree in position and direction.

**Deliverable:** `data/raw/hydro/merit_hydro_aqaba.tif`

**Watch out:** ~90 m is far too coarse to delineate small Aqaba wadis. The concept doc is explicit about this. Use it as a sanity check on the trunk channels only — **never** as the delineation source.

---

## 4. HydroSHEDS / HydroBASINS — regional context

**Role:** basin polygons for the context map layer
**Registration:** none

**Links**
- https://www.hydrosheds.org/products
- https://www.hydrosheds.org/products/hydrobasins
- https://www.hydrosheds.org/hydrosheds-core-downloads

**Tasks**
- [ ] Download Asia HydroBASINS, level 7–9.
- [ ] Clip to the northern Gulf.

**Deliverable:** `data/raw/hydro/hydrobasins_aqaba.gpkg`

**Watch out:** presentation and context layer only. Too coarse for the model itself. Useful on the "here is the regional setting" slide, nowhere else.

---

## Your processing chain

```text
Raw DEM tiles
  → merge + clip to AOI
  → reproject to EPSG:32636
  → fill sinks / breach depressions
  → flow direction (D8 or D-infinity)
  → flow accumulation
  → stream extraction (threshold on accumulation)
  → watershed delineation from pour points
  → snap outlets to the coastline
  → per-catchment feature table
```

Two decisions worth thinking about rather than defaulting:

**Fill vs breach.** Sink filling creates flat artificial surfaces; breaching cuts a channel through the blockage. In a hyper-arid basin full of DEM noise, breaching usually preserves the real channel network better. Try both on one catchment and look at the streams before committing.

**Stream threshold.** The flow-accumulation cutoff that defines "a channel" is a judgement call, and it directly controls how many catchments you get and where their boundaries fall. Pick it by looking at whether the extracted streams match the visible wadis on satellite imagery — not by taking a default.

---

## Definition of done

1. **One committed DEM**, with the reason for choosing it written down.
2. **3–5 catchment polygons** with snapped coastal outlets, as GeoPackage → seeds the `catchments` table.
3. **Per-catchment feature table** with: area (km²), mean slope, max slope, drainage density, flow-accumulation statistics, distance to coast. Pulga joins land-cover and soil columns onto this — agree the join key with them early (`catchment_id`, format `AQ-C01`, `AQ-C02`, …).
4. **Outlet coordinates published to the team by Day 4**, as lon/lat in EPSG:4326.
5. **Every source in `docs/data_dictionary.md`** with product ID, version, and access date.

**Target files**
```text
data/aoi/aqaba_aoi.geojson
data/raw/dem/cop_glo30_aqaba.tif
data/raw/dem/srtm_aqaba.tif
data/raw/hydro/merit_hydro_aqaba.tif
data/raw/hydro/hydrobasins_aqaba.gpkg
data/processed/dem/dem_utm36n.tif
data/processed/vectors/catchments.gpkg
data/processed/vectors/outlets.gpkg
data/processed/features/catchment_terrain.parquet
```

---

## Who depends on you

| Teammate | Needs from you | By when |
|---|---|---|
| **Karam** | catchment polygons — to average IMERG rainfall per catchment | Day 3 |
| **Pulga** | catchment polygons + `catchment_id` scheme — to attach land-cover and soil fractions | Day 4 |
| **Nizar** | outlet lon/lat — the particle release point | Day 4 |
| **Abd** | outlet lon/lat — to compare the observed plume against the predicted source | Day 5 |

## What you depend on

Nothing. **Your stream blocks nobody and is blocked by nobody** — which is why it should be finished early rather than late. Start Day 2 and don't wait for anyone.
