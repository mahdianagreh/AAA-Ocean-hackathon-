# Mahdi — Terrain & Hydrology

**Project:** ReefShield Aqaba
**Workstream:** A (Geospatial and Hydrology)
**Feeds:** Component B (catchment and flow modeling) → Component C (runoff model features)
**Window:** Day 2 for the DEM, Day 4 for locked outlets

---

## Why your stream matters

You produce the geometry everyone else's work sits on. The catchment polygons decide which rainfall cells Karam averages, and the **coastal outlet coordinates are the plume release point** for Nizar's current forcing and Abd's satellite validation.

> ## Status — M1 complete, 2 Aug 2026
>
> Real catchments and outlets are published. `scripts/03_dem_fetch.py` → `05_flow_and_streams.py` → `06_catchments.py` reproduce everything from scratch.
>
> | ID | Area | Relief | Mean slope | Drainage density | Outlet lon, lat |
> |---|---:|---:|---:|---:|---|
> | AQ-C01 Wadi Yutum | 4,453.1 km² | 1,841 m | 10.8° | 0.81 | 34.97073, 29.54560 |
> | AQ-C02 | 64.9 km² | 1,321 m | 16.6° | 0.71 | 34.97643, 29.47270 |
> | AQ-C03 | 59.9 km² | 1,418 m | 16.7° | 0.74 | 34.96416, 29.38167 |
> | AQ-C04 | 42.7 km² | 996 m | 8.3° | 1.01 | 34.96622, 29.36052 |
> | AQ-C05 | 35.6 km² | 1,015 m | 6.8° | 1.29 | 34.95998, 29.35737 |
>
> 4,656 km² — 97% of the drainage reaching Jordan's Gulf coast. Delineated area matches upstream flow accumulation at every pour point to **0.0%**.
>
> **Three bugs the data caught**, each of which produced plausible-looking wrong output:
>
> 1. **Area inflated 34%.** `breach_depressions_least_cost(fill=True)` forces genuine endorheic basins to spill coastward, annexing 1,767 km² to Wadi Yutum. 6,282 km² with fill, 4,453 km² without; HydroBASINS independently says 4,690 km² exorheic. Runoff scales with area, so this would have reached the sediment class and plume magnitude.
> 2. **Sea mask welded to the raster frame.** Reprojection fill shared the value 0 with sea level, so "largest polygon below sea level" returned the Gulf *plus* the frame — 1,080 km² against a true 623 km². Fixed by setting nodata and flood-filling from a seed in open water.
> 3. **HydroSHEDS files the Middle East under `eu`, not `as`.** The Asia file returns zero basins for Aqaba.
>
> ### Validation — all four checks done
>
> | Check | Result | Report |
> |---|---|---|
> | Internal consistency | Delineated area = flow accumulation, **0.0%** at every pour point | — |
> | Outlets vs imagery | **2 of 5** verify; the other 3 route through port infrastructure | `reports/outlets/` |
> | Stream network (M3) | **140 m** median offset vs HydroRIVERS, 84% within 500 m | `reports/streams/` |
> | Second DEM (M2) | Every mouth within **600 m** on SRTM; areas diverge | `reports/srtm/` |
> | Endorheic masking | 4,349 km² by explicit method, **2.3%** from the published figure | `reports/endorheic/` |
>
> **The contributing area is 4,453 km² ±4%** (range 4,349–4,690). Three independent approaches agree: explicit endorheic masking 4,349, the `fill=False` proxy 4,453, HydroBASINS exorheic 4,690.
>
> An earlier statement of ±1.7× was too pessimistic — it treated SRTM as an equal witness. SRTM finds **136,927 depressions to GLO-30's 20,352**, so its noise manufactures spurious sinks and it is unfit for depression-based analysis here. That is a measured claim, not a preference.
>
> ### Still open
>
> - **MERIT Hydro** — M3 was completed with HydroRIVERS instead. MERIT needs University of Tokyo registration or an authenticated Earth Engine project. Lower priority than it looks: HydroRIVERS is SRTM-derived while our DEM is TanDEM-X, so it was a genuinely independent check, and MERIT is partly SRTM too.
> - **Three low-confidence outlets** — AQ-O02/O03/O04 route through the container terminal, tank farms and a harbour basin. Only local stormwater outfall data from ASEZA fixes this; it is Phase 2 in the concept doc.
> - **Pulga's OSM culverts** — not yet cross-checked against the routed channels.

**Nobody waited for you.** Read [`00-contracts.md`](00-contracts.md) first. The Day-1 job was to publish *provisional* versions of both so everyone else could start immediately, then replace them with the real thing. Both swaps are now done.

### Your two Day-1 provisional deliverables (~2 hours total)

**P1 · Provisional catchments** — download HydroBASINS level 9 (precomputed, no DEM processing), clip to AOI, pick the 5 draining to the Gulf, assign `AQ-C01`…`AQ-C05`.
→ `data/processed/vectors/catchments_PROVISIONAL.gpkg`

**P2 · Provisional outlets** — open satellite imagery, click where each wadi visibly meets the sea. No DEM needed.
→ `data/processed/vectors/outlets_PROVISIONAL.gpkg`

Both are coarse and wrong in detail, and structurally identical to your real output. Karam, Pulga and Nizar build their full pipelines against them and re-run in minutes when your real geometry lands.

> **Outlets still matter.** Getting them right is your main technical contribution — the provisional ones just mean nobody sits idle while you do it properly.

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

## Handoffs — non-blocking

Nobody is idle waiting for you, because the provisional versions went out on Day 1. These are **upgrades**, not unblocks.

| Teammate | Provisional they're using | Your real version replaces it | Their re-run cost |
|---|---|---|---|
| **Karam** | `catchments_PROVISIONAL.gpkg` | 30 m DEM delineation | minutes |
| **Pulga** | `catchments_PROVISIONAL.gpkg` | same | minutes |
| **Nizar** | `outlets_PROVISIONAL.gpkg` | DEM outlets checked vs imagery + OSM | minutes |
| **Abd** | not blocked — he needs event dates, not outlets | outlets used as a source cross-check | none |

Announce each swap in the team channel and tick it off in [`00-contracts.md`](00-contracts.md) §5. An unannounced swap means someone keeps quoting stale numbers.

## What you depend on

**Nothing at all.** Your stream is fully independent start to finish. One optional input worth having: Pulga's OSM layer flags mapped culverts and storm drains, which helps you correct the last stretch of each channel. Useful, not required — if it's late, hand-check against satellite imagery instead.
