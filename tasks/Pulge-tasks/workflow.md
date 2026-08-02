# Pulga — Workflow & Schedule

## Daily Cadence (Chain 1 & Chain 2)
You own two independent value chains: Land-Side Data (WorldCover, SoilGrids, OSM) and Marine Data (Allen Coral Atlas, GEBCO). Work them in parallel to avoid being blocked. 
**Rule:** You wait on nobody after Day 1.

### Day-by-Day Schedule
| Day | Land Chain | Marine Chain | Deliverable/Handoff |
|---|---|---|---|
| **1** | Env setup, download WorldCover + SoilGrids + OSM raw files | Hand-draw and publish `reef_zones_PROVISIONAL.gpkg` | Provisional reef zones live for exposure engine + dashboard |
| **2** | Clip WorldCover to AOI, verify class codes, stage SoilGrids WCS clip | Register own GEE project, start ACA export task | — |
| **3** | Process SoilGrids units, verify conversion | Download + clip GEBCO, derive water mask, verify sign convention | Coastline mask ready early |
| **4** | Pull provisional catchments; run WorldCover + soil per-catchment aggregation | Continue ACA processing in background | First land-cover/soil numbers exist |
| **5** | Run bare-ground sanity check; fix class mapping; finalize `landcover_by_catchment.parquet` | Polygonize ACA export, begin zone-merging | — |
| **6** | Finalize `soil_by_catchment.parquet`; clip/extract OSM roads + drainage | Compare ACA zones vs provisional | — |
| **7** | Compute road density; run OSM-vs-DEM conflict detection; write conflicts doc | Finalize coastline + depth field files | **Land-cover + soil delivered (hard deadline)** |
| **8** | Buffer day — fix issues flagged by runoff model builder | Finalize reef zone schema, run diff check | **Coastline + depth field delivered** |
| **9** | Populate `docs/data_dictionary.md` | Finalize `sensitivity_weight` labeling | — |
| **10** | — | Swap provisional reef zones for final | **Real reef zones delivered (hard deadline)** |
| **11–14** | Support/debug as needed; prep pitch slides | Same | Pitch prep, backup data caching |

## QA & Screenshot Protocol
Capture screenshots/plots BEFORE any aggregation for:
- **WorldCover:** Classified raster over AOI (`docs/qa_screenshots/worldcover_check.png`)
- **SoilGrids:** One variable raster over AOI (`docs/qa_screenshots/soilgrids_check.png`)
- **OSM:** Roads + drainage layers over a satellite basemap (`docs/qa_screenshots/osm_check.png`)
- **OSM vs DEM:** Drainage overlay showing conflicts (`docs/qa_screenshots/osm_dem_conflicts.png`)
- **Allen Coral Atlas:** Reef zones over Sentinel-2 basemap (`docs/qa_screenshots/reef_zones_check.png`)
- **GEBCO:** Water mask sanity check (`docs/qa_screenshots/gebco_watermask_check.png`)
- **Reef zones:** Provisional vs final side-by-side comparison (`docs/qa_screenshots/reef_zones_provisional_vs_final.png`)

## Data Dictionary Protocol
For each data source, update `docs/data_dictionary.md` immediately with:
- Product/version
- Access date & method
- Spatial resolution & Coverage
- License
- Known limitations
- Link to QA screenshot and processing script
