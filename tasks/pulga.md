# Pulga — Land Cover, Soil, Urban & Marine Habitat

**Project:** ReefShield Aqaba
**Workstream:** A + B (surface characterisation and habitat mapping)
**Feeds:** Component C (runoff features), Component D (sediment-load proxy), Component G (reef exposure)
**Window:** Day 4 for catchment features, Day 10 for reef zones

---

## Why your stream matters

You supply both ends of the chain. On land, your land-cover and soil layers are what let the model distinguish "this catchment will shed sediment" from "this one won't" — they *are* the sediment-load proxy. In the sea, your reef zones are the thing the entire platform exists to protect: **without named reef polygons there is no exposure score, and no product.**

---

## Before you download anything

Read [`00-contracts.md`](00-contracts.md) first — **you start Day 1 and wait for nobody.**

- [ ] **Download using the padded box** from the contract (`34.80, 29.25, 35.15, 29.70`). It's a superset of the analysis area, so your downloads stay valid even if the AOI shifts.
- [ ] **Use `catchments_PROVISIONAL.gpkg`** — Mahdi publishes it Day 1 from HydroBASINS. Build your full aggregation pipeline against it; re-running on his real polygons later takes minutes.
- [ ] **Register your own free Google Earth Engine project.** There is no shared one — that was a pointless blocker.
- [ ] **Publish P4 · provisional reef zones on Day 1 (~1 hour):** hand-draw 6–8 boxes along the coast where reefs are known, name them `R-01`…`R-08`, set every `sensitivity_weight` to `1.0`. → `data/processed/vectors/reef_zones_PROVISIONAL.gpkg`. This unblocks the exposure engine and the whole dashboard while you prepare the real Coral Atlas export.
- [ ] **CRS convention:** EPSG:4326 for storage, EPSG:32636 (UTM 36N) for all area calculations. Reef zone areas in km² must come from the projected CRS, not degrees.

### Environment

```bash
pip install geopandas rasterio rioxarray earthengine-api requests
pip install osmium  # or use osmium-tool / ogr2ogr for the .osm.pbf clip
```

---

## 1. ESA WorldCover 10 m

**Role:** bare ground, built-up, vegetation, water → runoff and erosion features
**Resolution:** 10 m
**Registration:** none

**Links**
- https://esa-worldcover.org/en/data-access
- https://worldcover2021.esa.int/download

**Tasks**
- [ ] Download the AOI tile (2021 product).
- [ ] Compute per-catchment class fractions: bare/sparse vegetation, built-up, herbaceous, water.
- [ ] Join to Mahdi's catchment table on `catchment_id`.

**Deliverable:** `data/processed/features/landcover_by_catchment.parquet`

**Sanity check:** bare-ground fraction should come out **high** for hyper-arid catchments — the concept doc's example event record (§12.3) assumes ~74%. If you're getting 20%, check your class remapping; WorldCover class codes are not sequential integers.

**Watch out:** 2020/2021 baseline products only — there's no time series, so you cannot capture land-use change between the 2013 and 2016 events. For a two-week MVP that's acceptable; note it as a limitation rather than pretending it isn't there.

---

## 2. ISRIC SoilGrids

**Role:** infiltration and erodibility proxies
**Registration:** none

**Links**
- https://docs.isric.org/globaldata/soilgrids/index.html
- https://rest.isric.org/soilgrids/v2.0/docs
- https://files.isric.org/soilgrids/latest/data/

**Variables to pull** (0–5 cm and 5–15 cm depths)
- clay fraction
- sand fraction
- silt fraction
- organic carbon
- bulk density
- coarse fragments

**Tasks**
- [ ] Pull the variables above for the AOI — the REST API is fine for small extents, the file server for bulk.
- [ ] Aggregate to per-catchment means.
- [ ] Join to the catchment feature table.

**Deliverable:** `data/processed/features/soil_by_catchment.parquet`

**Watch out:** SoilGrids is **globally model-derived, not surveyed**. Use it as a *relative* erodibility proxy across catchments — never quote a value as measured local soil property. If a judge asks how you know Aqaba's soil texture, the honest answer is "we don't; we use a global model as a relative ranking, and local sampling is Phase 2."

**Units gotcha:** SoilGrids stores values scaled as integers (e.g. clay in g/kg, not %). Check the documented conversion factors before you compute anything, or your fractions will be off by 10×.

---

## 3. OpenStreetMap — Jordan extract

**Role:** roads, impervious surfaces, mapped drainage, industrial and port features
**Registration:** none

**Links**
- https://download.geofabrik.de/asia/jordan.html
- https://www.openstreetmap.org/export/

**Tasks**
- [ ] Download `jordan-latest.osm.pbf` and clip to AOI.
- [ ] Extract layers: roads, buildings/built-up, waterways + culverts + drains, industrial and port polygons.
- [ ] Compute per-catchment road density and built-up fraction as runoff features.
- [ ] **Cross-check against Mahdi's DEM-derived flow paths** and flag anywhere mapped drainage contradicts the modelled route.

**Deliverables**
- `data/raw/osm/jordan-latest.osm.pbf`
- `data/processed/vectors/osm_aqaba.gpkg`

**Watch out:** OSM completeness in Aqaba is unknown and probably patchy for drainage infrastructure. **An unmapped channel is not an absent channel** — absence of a feature in OSM is not evidence, so never use it to rule something out. It's only useful as positive evidence when a feature *is* mapped.

**Where this earns its keep:** Mahdi's DEM will route flow around buildings that water actually flows through, past, or under. Where OSM shows a culvert or storm drain that the DEM doesn't know about, that's a real correction to the outlet position — and outlet position is the single most consequential number in the project.

---

## 4. Allen Coral Atlas

**Role:** shallow coral geomorphic and benthic habitat → the reef exposure calculation
**Resolution:** 5 m (Earth Engine product)
**Registration:** Earth Engine or Atlas access

**Links**
- https://allencoralatlas.org/
- https://developers.google.com/earth-engine/datasets/catalog/ACA_reef_habitat_v2_0

**Tasks**
- [ ] Export benthic and geomorphic habitat layers for the Aqaba coast via Earth Engine.
- [ ] Split the coast into named zones: `R-01`, `R-02`, … matching the concept doc's convention.
- [ ] Compute each zone's area in km² (projected CRS).
- [ ] Add a `habitat_class` column and a `sensitivity_weight` column.
- [ ] **Label `sensitivity_weight` explicitly as a placeholder pending marine-scientist input.**

**Deliverable:** `data/processed/vectors/reef_zones.gpkg` → seeds the `reef_zones` table

**Acceptance:** zones are stable, uniquely named, and each has an area. The exposure engine joins on these IDs across every simulation run — if the zones get renumbered mid-project, every stored result becomes meaningless.

**Watch out — two separate limitations, both worth stating out loud:**
1. ACA maps **shallow** reef only. Deeper habitat isn't in the product, so your exposure map is silent about it.
2. ACA maps **habitat, not sensitivity**. The `sensitivity_weight` values are the team's assumption, not Atlas data. The concept doc (§24.6) is explicit that local scientific expertise is needed to assign these. Put that on the slide — inventing weights and presenting them as data is the kind of thing that loses credibility fast under questioning.

**How many zones?** Enough to be operationally meaningful, few enough to read on a map. The doc's examples use `R-03`, `R-04` in an alert with a handful of zones total. Aim for something a dive-centre operator could actually act on.

---

## 5. GEBCO bathymetry

**Role:** depth constraints and coastline barrier for the plume transport model
**Resolution:** 15 arc-second grid
**Registration:** none

**Links**
- https://www.gebco.net/data-products/gridded-bathymetry-data
- https://download.gebco.net/downloads

**Tasks**
- [ ] Download the 15 arc-second grid for the northern Gulf.
- [ ] Derive a water mask / coastline the particle engine can use as a boundary.
- [ ] Produce a depth field on the same grid the engine will interpolate on.

**Deliverables**
- `data/raw/bathymetry/gebco_aqaba.tif`
- `data/processed/bathymetry/depth_utm36n.tif`
- `data/processed/vectors/coastline.gpkg`

**Watch out:** 15 arc-seconds is ~450 m at this latitude. That's fine for overall basin geometry and as a "particles stop at the shore" barrier. It will **not** resolve reef-scale depth changes, small channels, or harbour structures — so don't let the plume model imply behaviour it can't see. The concept doc (§24.4) names this limitation directly.

---

## Definition of done

1. **Per-catchment land-cover fractions** joined on `catchment_id`.
2. **Per-catchment soil properties** joined on `catchment_id`, with unit conversions verified.
3. **OSM vector layers** clipped to AOI, plus a written list of any DEM-vs-OSM drainage conflicts handed to Mahdi.
4. **Named reef zones** with `habitat_class`, area in km², and clearly-labeled placeholder `sensitivity_weight`.
5. **Depth field and coastline mask** ready for Nizar's particle engine.
6. **Every source in `docs/data_dictionary.md`** with product version and access date.

**Target files**
```text
data/raw/osm/jordan-latest.osm.pbf
data/raw/bathymetry/gebco_aqaba.tif
data/processed/features/landcover_by_catchment.parquet
data/processed/features/soil_by_catchment.parquet
data/processed/vectors/osm_aqaba.gpkg
data/processed/vectors/reef_zones.gpkg
data/processed/vectors/coastline.gpkg
data/processed/bathymetry/depth_utm36n.tif
```

---

## Handoffs — non-blocking

| Teammate | What they get from you | Are they blocked? |
|---|---|---|
| **Exposure engine** | real Coral Atlas reef zones | **No** — your `reef_zones_PROVISIONAL.gpkg` went out Day 1 with the same IDs |
| **Nizar** | coastline + depth field | **No** — he pulls his own GEBCO copy, it's a 10-minute download |
| **Runoff model** | land-cover + soil columns | Only at training time, Day 7 |
| **Mahdi** | OSM culvert/drain conflicts | **No** — helpful for his outlet correction, not required |

Keep the reef zone **IDs and count identical** between provisional and real. If `R-01` means a different stretch of coast after the swap, every stored exposure result silently becomes wrong — and unlike a crash, nothing tells you.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Mahdi** | real catchment polygons | **No** — provisional from Day 1, re-run costs minutes |
| **Contract** | the padded download box, `catchment_id` scheme | Available Day 1 |

**Start Day 1.** All five of your sources need nothing but the padded box.
