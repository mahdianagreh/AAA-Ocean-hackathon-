# Pulga Implementation Plan — Full Detail
## Workstream A+B: Land Cover, Soil, Urban & Marine Habitat
### ReefShield Aqaba

**Owner:** You
**Feeds:** Component C (runoff features), Component D (sediment-load proxy), Component G (reef exposure)
**Blocking status:** You are blocked by nobody after Day 1. Everyone downstream of you can be unblocked by Day 1 if you execute the provisional-data steps correctly.

---

## 0. Mental Model Before You Start

You own two independent value chains that happen to share you as the person building them:

**Chain 1 (Land):** WorldCover + SoilGrids + OSM → per-catchment feature table → feeds the runoff/sediment model
**Chain 2 (Sea):** Allen Coral Atlas + GEBCO → reef zones + coastline/depth → feeds the exposure engine and the particle transport model

These chains do **not** depend on each other. You can work them in parallel, or hand one off in your head to "morning tasks" and the other to "afternoon tasks." Structure your week around that independence — don't let a delay in one chain stall the other.

The single most important structural fact in the updated brief: **you no longer wait on anyone.** The padded box replaces the frozen AOI, `catchments_PROVISIONAL.gpkg` replaces waiting for Mahdi's real polygons, and a 1-hour hand-drawn `reef_zones_PROVISIONAL.gpkg` replaces waiting for a clean Coral Atlas export. Every one of your 5 sources is startable on Day 1 with zero external dependency. Treat "provisional first, real later" as the operating principle for your entire week, not just a Day 1 trick.

---

## 1. Environment Setup (Day 1, ~30 min)

```bash
# Core geospatial stack
pip install geopandas rasterio rioxarray shapely pyproj fiona

# Earth Engine
pip install earthengine-api

# HTTP for SoilGrids REST + GEBCO downloads
pip install requests

# OSM extraction — pick ONE approach, pyrosm is faster to script against
pip install pyrosm          # pure-Python, good for scripted clipping/filtering
# OR
pip install osmium          # lower-level, more control, steeper API
# OR use CLI tools instead of Python:
#   osmium-tool (apt install osmium-tool / brew install osmium-tool)
#   ogr2ogr (comes with GDAL)

# Plotting/QA
pip install matplotlib contextily  # contextily = satellite basemap tiles for quick QA plots

# Optional but recommended for visual QA across all layers at once
# Install QGIS separately (not via pip) — https://qgis.org/download
```

**Authenticate Earth Engine (your own project, not shared):**
```bash
earthengine authenticate
# Follow browser OAuth flow, then in Python:
```
```python
import ee
ee.Authenticate()  # one-time
ee.Initialize(project='YOUR-OWN-GEE-PROJECT-ID')
```

**Set up your working directory structure immediately** (mirrors the target file layout so nothing gets lost):

```bash
mkdir -p data/raw/osm data/raw/bathymetry data/raw/worldcover data/raw/soilgrids data/raw/aoi
mkdir -p data/processed/features data/processed/vectors data/processed/bathymetry
mkdir -p docs notebooks scripts
```

---

## 2. Day 1 Critical Path — Do These in This Exact Order

### Step 2.1 — Get the padded box and lock your AOI constant

From `00-contracts.md`: `34.80, 29.25, 35.15, 29.70` (lon_min, lat_min, lon_max, lat_max — confirm ordering against the contract file itself before trusting this, contract files sometimes use minx/miny/maxx/maxy or a GeoJSON polygon instead of a flat tuple).

```python
# config.py — single source of truth, import this everywhere, never hardcode the box again
AOI_BBOX = (34.80, 29.25, 35.15, 29.70)  # lon_min, lat_min, lon_max, lat_max
AOI_CRS_STORAGE = "EPSG:4326"
AOI_CRS_PROJECTED = "EPSG:32636"  # UTM 36N — use for ALL area/distance calculations
```

Save `data/raw/aoi/aqaba_padded_box.geojson` as a proper GeoJSON polygon from this bbox so every downstream clip operation references a file, not a hand-typed tuple:

```python
import geopandas as gpd
from shapely.geometry import box

minx, miny, maxx, maxy = AOI_BBOX
aoi_geom = box(minx, miny, maxx, maxy)
gpd.GeoDataFrame({'geometry': [aoi_geom]}, crs=AOI_CRS_STORAGE).to_file(
    "data/raw/aoi/aqaba_padded_box.geojson", driver="GeoJSON"
)
```

### Step 2.2 — Publish provisional reef zones (~1 hour, do this before lunch on Day 1)

This is your highest-leverage task of the entire week. It unblocks the exposure engine and the dashboard team immediately, and — critically — **the IDs you choose here must survive unchanged into the final Allen Coral Atlas version.**

**How to actually draw the 6–8 boxes:**
1. Open Copernicus Browser (https://browser.dataspace.copernicus.eu) or Google Earth, navigate to Aqaba's coastline
2. Visually identify where reef is known to exist along the coast (northern Aqaba coastline, the Marine Science Station area, the Marine Park/Reserve stretch south of the city, the Royal Diving Club area — cross-reference against the UNDP Aqaba Marine Reserve Management Plan reference from the concept doc if you have it)
3. In QGIS (fastest for hand-drawing) or directly in GeoPandas/Shapely with rough coordinate boxes, draw 6–8 rectangular or simple polygons hugging the coast at reef-plausible locations
4. Name them `R-01` through `R-08` sequentially along the coast (e.g., north to south) so the naming has a logical order a teammate can infer without a legend

```python
import geopandas as gpd
from shapely.geometry import Polygon

# Placeholder structure — replace coordinates with your actual hand-drawn boxes
provisional_zones = [
    {"reef_zone_id": "R-01", "geometry": Polygon([...]), "habitat_class": "unknown", "sensitivity_weight": 1.0},
    {"reef_zone_id": "R-02", "geometry": Polygon([...]), "habitat_class": "unknown", "sensitivity_weight": 1.0},
    # ... through R-08
]

gdf = gpd.GeoDataFrame(provisional_zones, crs=AOI_CRS_STORAGE)

# Compute area correctly — reproject to UTM 36N first, never compute area in degrees
gdf_utm = gdf.to_crs(AOI_CRS_PROJECTED)
gdf["area_km2"] = gdf_utm.geometry.area / 1e6

gdf.to_file("data/processed/vectors/reef_zones_PROVISIONAL.gpkg", driver="GPKG")
```

**Non-negotiable rule:** every field that will exist in the final `reef_zones.gpkg` must exist in the provisional file too, with the same names and types (`reef_zone_id`, `geometry`, `habitat_class`, `sensitivity_weight`, `area_km2`). If the exposure engine gets built against a schema that changes later, that's a second bug to fix on top of the real-data swap.

**Immediately message/commit this file and tell the team it's live.** This is the one task where speed matters more than polish — a rough box today is worth more than a perfect polygon in three days, because everyone downstream starts building against it the moment it lands.

### Step 2.3 — Get `catchments_PROVISIONAL.gpkg` from Mahdi

You don't build this yourself — confirm Mahdi has published it Day 1 and pull it. If it's late, don't block: proceed with Steps 3–7 below (which only need the AOI box), and slot in catchment aggregation the moment it lands.

### Step 2.4 — Register your own Earth Engine project

Don't wait for a shared project — the brief is explicit this was a pointless blocker before. Go to https://code.earthengine.google.com, sign up under your own account, create a project, and initialize against your own project ID in all your EE scripts. Takes 10 minutes.

### Step 2.5 — Kick off all 5 raw downloads in parallel

The moment 2.1 and 2.4 are done, start every download below simultaneously — none of them need the catchment polygons, only the AOI box.

---

## 3. Chain 1 — Land-Side Data (detailed, source by source)

### 3.1 ESA WorldCover 10m

**Purpose:** bare ground / built-up / vegetation / water fractions → these directly *are* your sediment-load proxy signal.

**Download:**
```python
import requests

# WorldCover is tiled globally; identify the tile(s) covering your AOI
# Access via: https://esa-worldcover.org/en/data-access (S3 bucket listing available)
# Simplest path: use the STAC API or direct S3 tile download for the tile(s) intersecting AOI_BBOX

# Example using the AWS Open Data S3 bucket (check current path structure at time of download,
# ESA has occasionally restructured the bucket):
# s3://esa-worldcover/v200/2021/map/ESA_WorldCover_10m_2021_v200_<tile_id>_Map.tif
```

Practical approach: use the WorldCover Viewer (https://worldcover2021.esa.int/viewer) to visually identify which tile(s) intersect your padded box first — Aqaba likely falls within one tile given the box is small, but confirm before writing download code, since a missed tile edge silently truncates your western or eastern catchments.

**Processing:**
```python
import rasterio
from rasterio.mask import mask
import geopandas as gpd
import numpy as np

# 1. Clip WorldCover raster to AOI
aoi = gpd.read_file("data/raw/aoi/aqaba_padded_box.geojson")
with rasterio.open("data/raw/worldcover/ESA_WorldCover_10m_2021_v200_<tile>_Map.tif") as src:
    clipped, transform = mask(src, aoi.geometry, crop=True)
    meta = src.meta.copy()
    meta.update({"height": clipped.shape[1], "width": clipped.shape[2], "transform": transform})

with rasterio.open("data/interim/worldcover_aqaba_clip.tif", "w", **meta) as dst:
    dst.write(clipped)

# 2. WORLDCOVER CLASS CODES — THESE ARE NOT SEQUENTIAL, hardcode this map explicitly:
WORLDCOVER_CLASSES = {
    10: "tree_cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare_sparse_vegetation",
    70: "snow_ice",
    80: "permanent_water_bodies",
    90: "herbaceous_wetland",
    95: "mangroves",
    100: "moss_lichen",
}
```

**Per-catchment aggregation** (run once `catchments_PROVISIONAL.gpkg` is available):
```python
import rasterstats

catchments = gpd.read_file("data/processed/vectors/catchments_PROVISIONAL.gpkg")

# zonal_stats with categorical=True gives pixel counts per class per catchment
stats = rasterstats.zonal_stats(
    catchments,
    "data/interim/worldcover_aqaba_clip.tif",
    categorical=True,
    geojson_out=False
)

rows = []
for cid, stat in zip(catchments["catchment_id"], stats):
    total = sum(stat.values())
    row = {"catchment_id": cid}
    for code, name in WORLDCOVER_CLASSES.items():
        row[f"frac_{name}"] = stat.get(code, 0) / total if total > 0 else np.nan
    rows.append(row)

landcover_df = pd.DataFrame(rows)
landcover_df.to_parquet("data/processed/features/landcover_by_catchment.parquet")
```

**Mandatory sanity check before you consider this done:**
```python
print(landcover_df["frac_bare_sparse_vegetation"].describe())
# Expect median well above 0.5 for hyper-arid catchments (~0.74 per the concept doc's example).
# If you see ~0.20, your class code mapping is wrong — re-check WORLDCOVER_CLASSES against
# the official ESA legend before doing anything else. Do not proceed to soil aggregation
# until this passes, because Mahdi's runoff model will silently train on bad features.
```

**Visual QA (do this, don't skip it):**
```python
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(10, 10))
catchments.plot(ax=ax, facecolor="none", edgecolor="red")
# overlay the clipped raster
show(clipped, ax=ax, transform=transform)
plt.savefig("docs/qa_screenshots/worldcover_classification_check.png", dpi=150)
```
Look at this image before moving on. Bare ground should visually dominate. If it doesn't look right, trust your eyes over the numbers.

**Known limitation to write into `docs/data_dictionary.md` now, not later:** 2021 baseline only, no time series — cannot capture land-use change between 2013 and 2016 flood events. State it, don't hide it.

---

### 3.2 ISRIC SoilGrids

**Purpose:** infiltration/erodibility proxy — relative ranking across catchments, not measured local truth.

**Variables:** clay, sand, silt, organic carbon (soc), bulk density (bdod), coarse fragments (cfvo) — at 0-5cm and 5-15cm depths.

**Download via REST API** (fine for your small AOI):
```python
import requests

SOILGRIDS_BASE = "https://rest.isric.org/soilgrids/v2.0/properties/query"
variables = ["clay", "sand", "silt", "soc", "bdod", "cfvo"]
depths = ["0-5cm", "5-15cm"]

def fetch_soilgrids_point(lon, lat, variables, depths):
    params = {
        "lon": lon, "lat": lat,
        "property": variables,
        "depth": depths,
        "value": "mean",
    }
    r = requests.get(SOILGRIDS_BASE, params=params)
    r.raise_for_status()
    return r.json()

# For an AOI (not a point), SoilGrids REST is point-based — you'll need to either:
#   (a) sample a grid of points across each catchment and average, or
#   (b) use the WCS/file-server route for a proper raster clip (better for area aggregation)
# Recommendation: use the file server for a real raster, REST API only for spot-checks.
```

**Better approach — WCS raster clip (recommended over point-sampling for area aggregation):**
```python
# ISRIC provides WCS endpoints per variable, e.g.:
# https://maps.isric.org/mapserv?map=/map/clay.map
# Use owslib or a direct WCS GetCoverage request clipped to AOI_BBOX, per variable/depth combo.
# This gives you an actual raster you can zonal_stats against catchments, same pattern as WorldCover.
```

**Units gotcha — do this conversion explicitly and write a test for it:**
```python
# SoilGrids stores values as scaled integers. Documented conversion factors (verify against
# current ISRIC docs before trusting these, they are the kind of thing that changes silently):
SOILGRIDS_CONVERSION = {
    "clay": 0.1,   # g/kg -> % ... CHECK actual factor in docs, do not assume
    "sand": 0.1,
    "silt": 0.1,
    "soc": 0.1,    # dg/kg -> ...
    "bdod": 0.01,  # cg/cm3 -> kg/dm3
    "cfvo": 0.1,
}
# Write a unit test: known ISRIC example point should convert to a plausible soil fraction
# (clay % should land between 0-100, not 0-1000 or 0-10). If it doesn't, the factor is wrong.
```

**Per-catchment aggregation and output:**
```python
soil_df.to_parquet("data/processed/features/soil_by_catchment.parquet")
```

**Framing discipline — put this sentence directly in your slide/doc, not just your head:**
> "SoilGrids is a global model-derived product, not surveyed local soil. We use it strictly as a relative erodibility ranking across our catchments. Local sampling is a Phase 2 item."

---

### 3.3 OpenStreetMap — Jordan Extract

**Purpose:** roads/impervious surfaces (runoff features) + mapped drainage (outlet correction — this is your highest-value cross-check).

**Download:**
```bash
wget https://download.geofabrik.de/asia/jordan-latest.osm.pbf -O data/raw/osm/jordan-latest.osm.pbf
```

**Clip to AOI using osmium CLI (fast, recommended over pure-Python for a country-sized file):**
```bash
osmium extract -b 34.80,29.25,35.15,29.70 \
    data/raw/osm/jordan-latest.osm.pbf \
    -o data/interim/osm_aqaba_clip.osm.pbf
```

**Extract layers via ogr2ogr (converts OSM PBF to GeoPackage layers):**
```bash
ogr2ogr -f GPKG data/processed/vectors/osm_aqaba.gpkg data/interim/osm_aqaba_clip.osm.pbf \
    lines -where "highway IS NOT NULL" -nln roads

ogr2ogr -f GPKG -update data/processed/vectors/osm_aqaba.gpkg data/interim/osm_aqaba_clip.osm.pbf \
    multipolygons -where "building IS NOT NULL" -nln buildings

ogr2ogr -f GPKG -update data/processed/vectors/osm_aqaba.gpkg data/interim/osm_aqaba_clip.osm.pbf \
    lines -where "waterway IS NOT NULL" -nln waterways

ogr2ogr -f GPKG -update data/processed/vectors/osm_aqaba.gpkg data/interim/osm_aqaba_clip.osm.pbf \
    multipolygons -where "landuse='industrial' OR industrial IS NOT NULL" -nln industrial

ogr2ogr -f GPKG -update data/processed/vectors/osm_aqaba.gpkg data/interim/osm_aqaba_clip.osm.pbf \
    multipolygons -where "landuse='port' OR industrial='port'" -nln port
```

**Also explicitly search for drainage/culvert tags — these are the ones that matter most and are easy to miss with a broad `waterway` filter:**
```bash
# tunnel=culvert, waterway=drain, waterway=ditch, man_made=storm_drain (tagging is inconsistent
# in OSM, so check for all of these variants, not just one)
ogr2ogr -f GPKG -update data/processed/vectors/osm_aqaba.gpkg data/interim/osm_aqaba_clip.osm.pbf \
    lines -where "waterway IN ('drain','ditch','stream') OR tunnel='culvert'" -nln drainage_features
```

**Per-catchment road density + built-up fraction:**
```python
roads = gpd.read_file("data/processed/vectors/osm_aqaba.gpkg", layer="roads").to_crs(AOI_CRS_PROJECTED)
catchments_utm = catchments.to_crs(AOI_CRS_PROJECTED)

road_density = []
for _, cat in catchments_utm.iterrows():
    clipped_roads = roads.clip(cat.geometry)
    length_km = clipped_roads.geometry.length.sum() / 1000
    area_km2 = cat.geometry.area / 1e6
    road_density.append({
        "catchment_id": cat["catchment_id"],
        "road_density_km_per_km2": length_km / area_km2 if area_km2 > 0 else np.nan
    })

road_density_df = pd.DataFrame(road_density)
```

**The cross-check that matters most — DEM flow paths vs. OSM drainage:**
```python
dem_flowpaths = gpd.read_file("<path Mahdi provides>/flow_paths.gpkg")
osm_drainage = gpd.read_file("data/processed/vectors/osm_aqaba.gpkg", layer="drainage_features")

# Buffer DEM flow paths slightly and check which OSM drainage features fall OUTSIDE that buffer
# — those are candidate corrections to the outlet position
dem_buffered = dem_flowpaths.to_crs(AOI_CRS_PROJECTED).buffer(50)  # 50m tolerance, tune this
osm_utm = osm_drainage.to_crs(AOI_CRS_PROJECTED)

conflicts = osm_utm[~osm_utm.intersects(dem_buffered.unary_union)]
conflicts.to_file("data/processed/vectors/osm_dem_drainage_conflicts.gpkg", driver="GPKG")
```

**Deliverable to Mahdi:** don't just hand him the GPKG — write a short markdown note (`docs/osm_dem_conflicts.md`) listing each conflict with a lat/lon and a one-line description ("OSM shows a culvert under the coastal highway near 29.53,34.97 that isn't in the DEM-derived flow network — possible outlet correction"). A raw geometry file forces him to go hunting; a short annotated list gets acted on same-day.

**Epistemic discipline, written into the same doc:** "Absence of a mapped drainage feature in OSM is not evidence the channel doesn't exist — OSM completeness in this area is unverified. Only positive matches (a feature IS mapped) are used as corrections."

---

## 4. Chain 2 — Marine Data (detailed, source by source)

### 4.1 Allen Coral Atlas — Real Export (do this in parallel with land-side work, target Day 8-9 so you have buffer before the Day 10 deadline)

**Earth Engine export script:**
```python
import ee
ee.Initialize(project='YOUR-OWN-GEE-PROJECT-ID')

aoi_ee = ee.Geometry.Rectangle(list(AOI_BBOX))

aca_benthic = ee.ImageCollection("ACA/reef_habitat/v2_0").select("benthic").mosaic().clip(aoi_ee)
aca_geomorphic = ee.ImageCollection("ACA/reef_habitat/v2_0").select("geomorphic").mosaic().clip(aoi_ee)

# Export as vectors via reduceToVectors, or export raster and vectorize locally in QGIS/GeoPandas
task = ee.batch.Export.image.toDrive(
    image=aca_benthic.addBands(aca_geomorphic),
    description="aca_aqaba_habitat",
    folder="reefshield_exports",
    region=aoi_ee,
    scale=5,
    crs="EPSG:32636",
    maxPixels=1e9
)
task.start()
# Monitor at https://code.earthengine.google.com/tasks
```

**Convert exported raster to named zones locally:**
```python
# 1. Load exported raster
# 2. Polygonize contiguous reef habitat areas (rasterio.features.shapes or GDAL polygonize)
# 3. Manually group/merge polygonized fragments into 6-8 operationally meaningful zones
#    (don't keep every tiny polygon fragment as its own "zone" — that fails the "few enough
#    to read on a map" requirement)
# 4. CRITICAL: assign the SAME R-01...R-08 IDs to the SAME approximate coastal stretches
#    as your provisional file. Compare side-by-side against reef_zones_PROVISIONAL.gpkg
#    before finalizing — this is the step most likely to silently break everything downstream
#    if rushed.
```

**Schema — must match provisional exactly:**
```python
final_zones = gpd.GeoDataFrame({
    "reef_zone_id": ["R-01", "R-02", ...],   # same IDs, same order/meaning as provisional
    "geometry": [...],
    "habitat_class": [...],                    # NOW populated with real ACA classes
    "sensitivity_weight": [1.0, 1.0, ...],     # STILL placeholder unless a marine scientist
                                                 # has given you real values — do not invent these
    "area_km2": [...],                          # recomputed from projected CRS
}, crs=AOI_CRS_STORAGE)

final_zones.to_file("data/processed/vectors/reef_zones.gpkg", driver="GPKG")
```

**Before you replace the provisional file, run a diff check:**
```python
prov = gpd.read_file("data/processed/vectors/reef_zones_PROVISIONAL.gpkg")
final = gpd.read_file("data/processed/vectors/reef_zones.gpkg")

assert set(prov["reef_zone_id"]) == set(final["reef_zone_id"]), \
    "Zone ID mismatch between provisional and final — this WILL break every stored exposure result"

# Also visually compare centroids to make sure R-03 in the final file is still roughly
# where R-03 was in the provisional file, not swapped with R-05
```

**Two limitations to write into the slide deck and `docs/data_dictionary.md`, verbatim:**
1. "Allen Coral Atlas maps shallow reef only — deeper habitat is not represented in our exposure model."
2. "`sensitivity_weight` reflects team assumptions, not Atlas data or scientific measurement — assigning real weights is a Phase 2 item requiring marine-scientist input."

---

### 4.2 GEBCO Bathymetry

**Download:**
```python
import requests

# GEBCO download API accepts a bounding box and returns a GeoTIFF
url = "https://www.gebco.net/data_and_products/gebco_web_services/web_map_service/mapserv"
# Or use the direct grid download tool at https://download.gebco.net/downloads
# with your AOI_BBOX entered manually if the API route is unreliable during the hackathon
```

Practical note: GEBCO's download portal sometimes works better through the manual web form than a scripted API call — don't burn more than 20 minutes trying to script this before falling back to the manual download, since it's a one-time download, not a repeated pipeline step.

**Processing:**
```python
import rasterio
from rasterio.mask import mask

with rasterio.open("data/raw/bathymetry/gebco_aqaba.tif") as src:
    clipped, transform = mask(src, aoi.geometry, crop=True)
    meta = src.meta.copy()
    meta.update({"height": clipped.shape[1], "width": clipped.shape[2],
                 "transform": transform, "crs": src.crs})

# Reproject to UTM 36N for the particle engine
import rasterio.warp
# ... reproject_match or calculate_default_transform + reproject into
# data/processed/bathymetry/depth_utm36n.tif

# Derive water mask / coastline: depth < 0 = water (check GEBCO's sign convention —
# some products use negative-below-sea-level, others positive-depth; verify before
# building the mask or you'll get an inverted coastline)
water_mask = clipped < 0  # VERIFY SIGN CONVENTION FIRST
```

**Coastline extraction:**
```python
from rasterio.features import shapes
import geopandas as gpd

shapes_gen = shapes(water_mask.astype('uint8'), transform=transform)
coastline_polys = [shape(geom) for geom, val in shapes_gen if val == 1]
coastline_gdf = gpd.GeoDataFrame({'geometry': coastline_polys}, crs=src.crs)
coastline_gdf.to_file("data/processed/vectors/coastline.gpkg", driver="GPKG")
```

**Sign-convention sanity check (do not skip):**
```python
# Plot the mask and visually confirm land is land and water is water
fig, ax = plt.subplots(figsize=(10,10))
ax.imshow(water_mask, cmap='Blues')
plt.savefig("docs/qa_screenshots/gebco_watermask_check.png", dpi=150)
# If Aqaba city appears blue and the Gulf appears white, your mask is inverted — flip it
# before handing anything to Nizar. An inverted mask means his particle engine thinks
# land is sea.
```

**Resolution limitation — state explicitly:** "15 arc-seconds ≈ 450m at this latitude. Sufficient for basin-scale geometry and a shore-boundary constraint. Not sufficient for reef-scale depth changes, small channels, or harbor structures — the plume model should not be read as resolving anything at that scale."

---

## 5. QA & Screenshot Protocol (apply at every stage, not just at the end)

For each of the 5 sources, capture a screenshot/plot at the moment of load, before any aggregation:

| Source | What to screenshot | Tool | Save to |
|---|---|---|---|
| WorldCover | Classified raster over AOI, catchments overlaid | `rasterio`/`matplotlib` or QGIS | `docs/qa_screenshots/worldcover_check.png` |
| SoilGrids | One variable (e.g., clay%) as a raster or point map over AOI | `matplotlib` | `docs/qa_screenshots/soilgrids_check.png` |
| OSM | Roads + drainage layers over a satellite basemap | QGIS + Google Satellite plugin | `docs/qa_screenshots/osm_check.png` |
| OSM vs DEM | Drainage overlay showing conflicts | QGIS (two layers, different colors) | `docs/qa_screenshots/osm_dem_conflicts.png` |
| Allen Coral Atlas | Reef zones over Sentinel-2 basemap | Earth Engine Code Editor or QGIS | `docs/qa_screenshots/reef_zones_check.png` |
| GEBCO | Water mask sanity check | `matplotlib` | `docs/qa_screenshots/gebco_watermask_check.png` |
| Reef zones (provisional vs final) | Side-by-side centroid comparison | QGIS | `docs/qa_screenshots/reef_zones_provisional_vs_final.png` |

Recommended tool for cross-layer checks specifically: **QGIS**, installed Day 1 alongside your Python environment, with a satellite basemap plugin (Google Satellite or Bing) added immediately. You'll use it repeatedly across all 7 checks above — install it once, don't improvise a new plotting approach for each source.

---

## 6. Day-by-Day Schedule

| Day | Land Chain | Marine Chain | Deliverable/Handoff |
|---|---|---|---|
| **1** | Env setup, download WorldCover + SoilGrids + OSM raw files (all need only the padded box) | Hand-draw and publish `reef_zones_PROVISIONAL.gpkg` (R-01–R-08, weight=1.0) | Provisional reef zones live for exposure engine + dashboard |
| **2** | Clip WorldCover to AOI, verify class codes, stage SoilGrids WCS clip | Register own GEE project, start ACA export task (can run in background for days) | — |
| **3** | Process SoilGrids units, verify conversion factors with unit test | Download + clip GEBCO, derive water mask, verify sign convention | Coastline mask ready early (Nizar's Day 8 deadline has huge buffer) |
| **4** | Pull `catchments_PROVISIONAL.gpkg` from Mahdi if not already in hand; run WorldCover + soil per-catchment aggregation the moment catchments exist | Continue ACA processing in background | First land-cover/soil numbers exist for early sanity-checking |
| **5** | Run bare-ground sanity check; fix class mapping if needed; finalize `landcover_by_catchment.parquet` | Polygonize ACA export, begin zone-merging into 6–8 operational zones | — |
| **6** | Finalize `soil_by_catchment.parquet`; clip/extract OSM roads + drainage layers | Compare ACA-derived zone boundaries against provisional, start ID alignment | — |
| **7** | Compute road density per catchment; run OSM-vs-DEM conflict detection; write `docs/osm_dem_conflicts.md` | Finalize coastline + depth field files | **Land-cover + soil delivered to runoff model builder (hard deadline)** |
| **8** | Buffer day — fix anything flagged by the runoff model builder using your features | Finalize reef zone schema, run provisional-vs-final ID diff check | **Coastline + depth field confirmed ready for Nizar** |
| **9** | Populate `docs/data_dictionary.md` fully for all land sources | Finalize `sensitivity_weight` labeling, run visual centroid comparison | — |
| **10** | — | Swap `reef_zones_PROVISIONAL.gpkg` → `reef_zones.gpkg`, notify exposure engine builder | **Real reef zones delivered (hard deadline)** |
| **11–14** | Support/debug as needed; prepare your slide(s) for the pitch deck using your QA screenshots | Same | Pitch prep, backup data caching |

---

## 7. Documentation — `docs/data_dictionary.md` Entry Template

Use this exact structure for each of your 5 sources, filled in as you go (not retroactively — you will not remember access dates and version numbers a week later):

```markdown
### <Source Name>
- **Product/version:** e.g., ESA WorldCover v200, 2021
- **Access date:** YYYY-MM-DD
- **Access method:** e.g., direct S3 download / Earth Engine export / REST API
- **Spatial resolution:** e.g., 10m
- **Coverage:** AOI padded box, 34.80,29.25,35.15,29.70
- **License:** e.g., CC BY 4.0
- **Known limitations:** (paste directly from Sections 3-4 above)
- **QA screenshot:** link to docs/qa_screenshots/<file>.png
- **Processing script:** link to scripts/<script>.py
```

---

## 8. Definition of Done — Full Checklist

- [ ] `data/raw/aoi/aqaba_padded_box.geojson` created and used as the single AOI reference everywhere
- [ ] `reef_zones_PROVISIONAL.gpkg` published Day 1, IDs `R-01`–`R-08`, `sensitivity_weight=1.0`
- [ ] WorldCover clipped, class-mapped, per-catchment fractions computed, bare-ground sanity check passed and screenshotted
- [ ] SoilGrids variables pulled, unit conversion verified with a test, per-catchment means computed
- [ ] OSM extracted (roads, buildings, waterways, drainage, industrial/port), per-catchment road density computed
- [ ] OSM-vs-DEM drainage conflict list written and handed to Mahdi as an annotated doc, not a raw file dump
- [ ] Allen Coral Atlas exported via own GEE project, polygonized, merged into 6–8 zones
- [ ] Final reef zone IDs verified identical (same count, same meaning) to provisional via automated diff check
- [ ] `sensitivity_weight` explicitly labeled as placeholder in both provisional and final files
- [ ] GEBCO downloaded, clipped, reprojected to UTM 36N, water mask sign-convention verified visually
- [ ] Coastline + depth field delivered to Nizar (with major schedule buffer, not at the last moment)
- [ ] `docs/data_dictionary.md` fully populated for all 5 sources with QA screenshot links
- [ ] All 8 target files exist at the correct paths:
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

## 9. Risk Register Specific to Your Workstream

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| WorldCover class codes mis-mapped, bare-ground fraction wrong | Medium | High (feeds runoff model directly) | Mandatory sanity check against ~74% baseline before proceeding |
| SoilGrids unit conversion wrong (10x error) | Medium | High (silent, doesn't crash) | Unit test against a known ISRIC example point |
| GEBCO water mask inverted | Low-Medium | High (breaks Nizar's particle engine) | Mandatory visual sign-convention check before handoff |
| Provisional and final reef zone IDs don't match | Medium if rushed on Day 10 | Critical (silently corrupts every stored result) | Automated `assert` diff check before replacing the file |
| OSM drainage completeness gives false confidence | Medium | Medium | Explicit "absence isn't evidence" framing in the conflict doc |
| ACA export takes longer than expected via Earth Engine | Medium | Medium (only threatens Day 10 if started late) | Start the export task Day 2, let it run in background for a week of buffer |
| `sensitivity_weight` gets treated as real data by teammates under time pressure | Medium | High (credibility risk with judges) | Label it in the file schema itself, not just documentation, and say it out loud on the slide |

---

*This plan assumes the updated `pulga.md` contract (padded box, provisional catchments/reef zones, own GEE project). Cross-check `00-contracts.md` for the authoritative AOI bbox coordinate ordering before running Step 2.1 — bounding box coordinate order conventions vary between tools and it's worth 30 seconds to confirm.*
