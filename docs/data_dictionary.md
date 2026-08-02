# Data dictionary

Provenance ledger for ReefShield Aqaba. **One row per external product**: what it is, where it came from, when, under what licence, and what it is used for.

> **Why this exists.** Concept doc §22.4 requires every number on the dashboard to trace back to a registered source. A judge asking "where did 4,453 km² come from?" should get a file path, not a recollection.

**Format for new rows.** Product ID and version, access date, spatial and temporal extent actually retrieved, licence, and the script that fetches it. If you pulled it by hand, say so — that flags a reproducibility gap.

---

## Terrain & hydrology — Mahdi

### Copernicus DEM GLO-30

| | |
|---|---|
| Product | `Copernicus_DSM_COG_10_{N29,N30}_00_{E034,E035}_00_DEM` |
| Version | GLO-30, COG distribution |
| Source | AWS Open Data mirror, `s3://copernicus-dem-30m/` (public, no credentials) |
| Accessed | 1 Aug 2026 (re-fetched 2 Aug after a nodata fix) |
| Extent | 4 × 1° tiles, clipped to 34.75–35.94 °E, 29.15–30.30 °N |
| Resolution | 1 arc-second (~30 m); reprojected to EPSG:32636 at 30 m |
| Licence | Free for any use with attribution to ESA / Copernicus |
| Script | `scripts/03_dem_fetch.py` |
| Output | `data/raw/dem/cop_glo30_aqaba.tif`, `data/processed/dem/dem_utm36n.tif` |
| **Role** | **Production DEM.** Catchment delineation, outlets, all terrain features |

**Known limitation:** surface model — buildings, container stacks and road embankments are in the elevation values. Caused 3 of 5 outlets to route through port infrastructure (`reports/outlets/`).

**Gotcha:** nodata must be set explicitly. GLO-30 encodes sea as exactly `0.0`, so leaving nodata unset makes reprojection fill indistinguishable from the Gulf and welds the raster frame onto the coastline — 1,080 km² of "sea" against a true 623 km². Also: `PREDICTOR=3` is rejected by the WhiteboxTools GeoTIFF reader.

### NASA SRTM 1 arc-second

| | |
|---|---|
| Product | `N29E034`, `N29E035`, `N30E034`, `N30E035` (`.hgt`) |
| Version | SRTM GL1, skadi distribution |
| Source | `https://s3.amazonaws.com/elevation-tiles-prod/skadi/` |
| Accessed | 2 Aug 2026 |
| Resolution | 1 arc-second; warped onto the exact GLO-30 grid |
| Licence | Public domain (NASA) |
| Script | `scripts/09_srtm_crosscheck.py` |
| **Role** | **Cross-check only.** Not a pipeline dependency |

**Finding:** yields 136,927 depressions against GLO-30's 20,352 over the same area — too noisy for depression-based analysis here. Confirms outlet *positions* to within 600 m; disagrees on catchment area. See `reports/srtm/`.

### HydroBASINS v1.c level 12

| | |
|---|---|
| Product | `hybas_eu_lev12_v1c` |
| Version | v1.c |
| Source | `https://data.hydrosheds.org/file/hydrobasins/standard/` |
| Accessed | 1 Aug 2026 |
| Licence | Free for non-commercial and commercial use with attribution (HydroSHEDS) |
| Script | `scripts/00_fetch_reference_data.py` |
| **Role** | Provisional catchment seed (superseded); independent exorheic-area check |

**Region gotcha:** HydroSHEDS files the Middle East under **`eu`**, not `as`. The Asia file returns zero basins for Aqaba.

Level 09 (`hybas_eu_lev09_v1c`) was also pulled for exploration and the `ENDO` flag audit. Not fetched by script.

### HydroRIVERS v1.0

| | |
|---|---|
| Product | `HydroRIVERS_v10_eu` |
| Version | v1.0 |
| Source | `https://data.hydrosheds.org/file/HydroRIVERS/` |
| Accessed | 2 Aug 2026 |
| Resolution | ~500 m; reaches ≥ ~10 km² upstream |
| Licence | As HydroSHEDS |
| Script | `scripts/00_fetch_reference_data.py` |
| **Role** | Independent stream-network validation (M3) |

**Independence note:** HydroSHEDS derives from **SRTM (2000)**; our DEM from **TanDEM-X (2011–2015)**. Different missions — a genuinely independent check, not a product compared to itself.

### Natural Earth 10m admin 0 countries

| | |
|---|---|
| Product | `ne_10m_admin_0_countries` |
| Source | `https://naciscdn.org/naturalearth/10m/cultural/` |
| Accessed | 1 Aug 2026 |
| Licence | Public domain |
| Script | `scripts/00_fetch_reference_data.py` |
| **Role** | Assign discharge points to Jordan vs Israel / Egypt / Saudi Arabia |

**Limitation:** ~1 km coastline generalisation, so a point on the real shore can sit up to ~1 km from the polygon. Matching uses a 3 km tolerance.

### Esri World Imagery

| | |
|---|---|
| Source | `server.arcgisonline.com/.../World_Imagery/MapServer/tile/{z}/{y}/{x}` |
| Accessed | 2 Aug 2026, zoom 16 |
| Licence | Esri terms — **verification and internal review only, not redistribution** |
| Script | `scripts/07_outlet_imagery_check.py` |
| **Role** | Visual verification of outlet positions |

### MERIT Hydro — not acquired, requirement met elsewhere

The task file names MERIT Hydro, but the *requirement* was an independent published channel network to validate our extracted streams against. **HydroRIVERS served that** — 140 m median offset, 84% of trunk cells within 500 m (`reports/streams/`).

Not acquired because it needs University of Tokyo registration or an authenticated Earth Engine project. Recorded here for completeness rather than as an outstanding gap.

**Would it add anything?** At 90 m it could pin channel position more finely than a ~500 m product. But it is partly SRTM-derived, so as a *cross-check* it is weaker than HydroRIVERS turned out to be — HydroSHEDS is SRTM, our DEM is TanDEM-X, which made that pairing genuinely independent. Optional refinement, not a dependency.

---

## Derived products — Mahdi

| File | Contents | Script |
|---|---|---|
| `data/aoi/terrain_aoi.geojson` | Land extent, derived from the catchments | `02` |
| `data/aoi/marine_aoi.geojson` | Sea extent, hand-set, **unconfirmed** | `01` |
| `data/aoi/aqaba_aoi.geojson` | Union of both — the download superset | `02` |
| `data/processed/dem/dem_utm36n.tif` | Production DEM, EPSG:32636, 30 m | `03` |
| `data/processed/vectors/catchments.gpkg` | 5 catchments, `catchment_id` + `outlet_id` | `06` |
| `data/processed/vectors/outlets.gpkg` | 5 outlets + `position_confidence` | `06` |
| `data/processed/features/catchment_terrain.parquet` | 17 terrain columns | `06` |
| `data/interim/hydro/outlet_candidates.csv` | All 72 coastal discharge points | `05` |

### `catchment_terrain.parquet` columns

| Column | Units | Notes |
|---|---|---|
| `catchment_id` | — | `AQ-C01`…`AQ-C05`, join key |
| `outlet_id` | — | `AQ-O01`…`AQ-O05` |
| `area_km2` | km² | **±4%** — see the endorheic caveat below |
| `elev_min_m` / `elev_max_m` / `elev_mean_m` | m | Land cells only, sea excluded |
| `relief_m` | m | max − min |
| `slope_mean_deg` / `slope_max_deg` | ° | From the 30 m grid |
| `stream_len_km` | km | Stream cells × 30 m |
| `drainage_density_km_km2` | km/km² | Channel length per unit area |
| `outlet_accum_cells` | cells | Flow accumulation at the mouth |
| `accum_mean_cells` / `accum_p95_cells` | cells | Shape descriptors — elongated basins concentrate flow late and read low |
| `dist_to_coast_max_km` / `dist_to_coast_mean_km` | km | Grid distance to the outlet; travel-time proxy |
| `elongation_ratio` | — | `2√(A/π) / L_max`. Near 1 = compact, low = elongated |

**Pulga** joins land cover and soil onto this table on `catchment_id`.

---

## Caveats that must travel with the numbers

**Wadi Yutum contributing area: 4,453 km² ±4%** (range 4,349–4,690). Three approaches agree — explicit endorheic masking 4,349, `fill=False` proxy 4,453, HydroBASINS exorheic 4,690. Roughly 1,800–2,000 km² of the topographic basin drains to internal sinks and never reaches the Gulf; it is excluded on purpose. Do not restore it from HydroBASINS `UP_AREA`, which includes it. See `reports/endorheic/`.

**Outlet positions:** only `AQ-O01` and `AQ-O05` verify against imagery — 96.4% of discharge. `AQ-O02`/`O03`/`O04` route through the container terminal, tank farms and a harbour basin, and carry `position_confidence = "low"`. `AQ-O04` discharges into an enclosed harbour and must not be demoed without saying so. See `reports/outlets/`.

**Marine AOI is unconfirmed.** Nobody has checked the seaward reach against a 24 h drift at northern-Gulf current speeds.

---

## Not yet filled in

Karam, Pulga, Abd and Nizar — add your products above using the same format. Rainfall, reanalysis, forecasts, land cover, soil, OSM, reef habitat, bathymetry, currents and satellite imagery are all still missing from this ledger.
