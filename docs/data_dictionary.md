# Data dictionary — Workstream A+B (land cover, soil, urban, marine habitat)

**Owner:** Pulga · **Project:** ReefShield Aqaba · **Last verified:** 2026-08-01

**Spatial contract:** download box `34.80, 29.25, 35.15, 29.70` (W, S, E, N, EPSG:4326).
Storage CRS **EPSG:4326**, all area/distance maths in **EPSG:32636** (UTM 36N).
Constants live in [scripts/config.py](../scripts/config.py) — nothing hardcodes a bbox.

**Reproduce from zero:** [README_pulga.md](README_pulga.md).
**All 34 QA figures with captions:** [qa_screenshots/MANIFEST.md](qa_screenshots/MANIFEST.md).
**Judge-facing limitations:** [pitch_limitations.md](pitch_limitations.md).

> **Standing rule for this workstream.** Every dataset, transformation, join and
> sanity check has a saved, captioned, timestamped figure. If it cannot be shown, it
> is assumed rather than verified — and assumptions produced all five bugs listed at
> the bottom of this file.

---

## CRS of every artefact

| Artefact | CRS | Pixel size |
|---|---|---|
| WorldCover tile + AOI clip | EPSG:4326 | 8.33e-05° (~10 m) |
| Bathymetry, raw (`gmrt_aqaba.tif`) | EPSG:4326 | 5.50e-04° (~53 m) |
| SoilGrids ×12 | EPSG:4326 | 2.26e-03° (~250 m) |
| **`depth_utm36n.tif`** | **EPSG:32636** | **50 m** |
| All vectors — reef zones, coastline, `osm_aqaba.gpkg`, AOI boxes | EPSG:4326 | — |
| All `*.parquet` feature tables | non-spatial | — |

Per contract §1: **EPSG:4326 for storage, EPSG:32636 for all maths.** The depth field
is the single reprojected raster, because the particle engine integrates distances on
it. SoilGrids is natively Homolosine; `OUTPUTCRS=EPSG:4326` is requested in the WCS
call so it arrives already reprojected.

**Measurement CRS is not cosmetic.** Every length, area and distance is computed in
UTM 36N. Figures with satellite basemaps are *drawn* in EPSG:3857 because that is the
tile CRS — but measuring there inflates ground distance by 1/cos(lat) = **1.148** at
this latitude, which is exactly how culvert #1 was briefly reported as 45 m from the
coast when the true distance is 39 m. Draw in 3857; measure in 32636.

Figures drawn in EPSG:4326 pass `config.geographic_aspect()` to `set_aspect()`.
`imshow` defaults to `aspect='equal'`, which would draw 1° longitude the same length
as 1° latitude — at 29.4 °N that is ~97 km against ~111 km, making the figure **14.9%
too wide**. A distorted picture is a real defect when the picture is the evidence.

**Zonal statistics** run with catchments and raster in the same geographic CRS
(4326 against 4326), so no reprojection artefacts enter the aggregation. Caveat:
4326 cells are not equal-area, so a catchment mean is very slightly weighted toward
its northern cells. Across a 0.45°-tall AOI that is far below SoilGrids' own model
uncertainty and is not worth correcting.

---

## 1. ESA WorldCover 10 m

| Field | Value |
|---|---|
| **Product/version** | ESA WorldCover v200, 2021 epoch |
| **Access date** | 2026-08-01 |
| **Access method** | Direct S3 (AWS Open Data), tile `N27E033` |
| **Source URL** | `https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N27E033_Map.tif` |
| **Spatial resolution** | 10 m |
| **Coverage** | One 3°×3° tile fully contains the padded box (asserted in code, not assumed) |
| **License** | CC BY 4.0 — attribution: © ESA WorldCover project 2021 |
| **Reproduce** | `cd scripts && ../.venv/bin/python process_worldcover.py` |
| **Outputs** | `data/interim/worldcover_aqaba_clip.tif`, `data/processed/features/landcover_by_catchment.parquet` |

**QA figures — all five steps**

| figure | claim it makes checkable |
|---|---|
| [worldcover_01_raw_tile_before_clip.png](qa_screenshots/worldcover_01_raw_tile_before_clip.png) | one tile covers the whole AOI |
| [worldcover_02_clipped_to_aoi.png](qa_screenshots/worldcover_02_clipped_to_aoi.png) | the clip is correctly placed and bare ground dominates |
| [worldcover_03_catchment_boundaries_overlay.png](qa_screenshots/worldcover_03_catchment_boundaries_overlay.png) | the exact polygons zonal_stats aggregates within |
| [worldcover_04_class_fractions_by_catchment.png](qa_screenshots/worldcover_04_class_fractions_by_catchment.png) | fractions close to 100% per catchment |
| [worldcover_05_bareground_sanity_annotated.png](qa_screenshots/worldcover_05_bareground_sanity_annotated.png) | every catchment clears the 50% assert and brackets the ~74% baseline |

**Measured composition** (padded AOI, 4200×5400 px @ 10 m):

| class | % of AOI | % of land |
|---|---:|---:|
| bare / sparse vegetation | 72.53 | **95.30** |
| built-up | 3.15 | 4.14 |
| permanent water | 23.89 | (sea) |
| tree cover | 0.25 | 0.33 |
| grassland | 0.07 | 0.09 |
| cropland | 0.06 | 0.08 |
| shrubland | 0.04 | 0.06 |
| herbaceous wetland | 0.00 | 0.00 |

**Sanity check: PASSED.** Bare/sparse ground is 95.3% of the land surface. The check
is an `assert`, so a wrong class mapping halts the pipeline rather than quietly
poisoning the runoff model. Class codes are **not sequential** (10, 20, …, 95, 100)
and are declared once in `config.py`.

**Independent corroboration.** WorldCover puts water at 23.89% of the AOI; the
bathymetry water mask independently gives 23.3%. Two unrelated products agreeing to
within 0.6 pp is good evidence both clips are correctly georeferenced.

**Known limitations**

1. The product is a **2021 epoch only and carries no time series**, so it cannot
   capture land-use change between the February 2013 and October 2016 flood events;
   both events are modelled against 2021 land cover, which is a real source of error
   we accept rather than hide for a two-week MVP.
2. At 10 m the product **cannot resolve individual streets**, and its `built_up`
   class bundles roads, yards and parking together with roofs, which is precisely why
   OSM building footprints are carried as a second independent impervious estimate.
3. The full 11-class fraction table is retained in the parquet output even though
   only bare-ground and built-up were requested, because **re-running the aggregation
   later to recover a dropped column is more expensive than storing it now**.

---

## 2. ISRIC SoilGrids v2.0

| Field | Value |
|---|---|
| **Product/version** | SoilGrids v2.0 |
| **Access date** | 2026-08-01 |
| **Access method** | WCS 2.0.1 `GetCoverage` per variable/depth, `https://maps.isric.org/mapserv?map=/map/<var>.map` |
| **Spatial resolution** | 250 m |
| **Coverage** | Padded box, 155×188 cells |
| **License** | CC BY 4.0 |
| **Reproduce** | `../.venv/bin/python download_soilgrids.py` then `.venv/bin/python tests/test_soilgrids_units.py` |
| **Outputs** | `data/raw/soilgrids/*.tif` (12 rasters), `data/processed/features/soil_by_catchment.parquet` (73 columns) |

**QA figures — one per variable plus three verification figures**

| figure | claim it makes checkable |
|---|---|
| [soilgrids_01_clay_both_depths.png](qa_screenshots/soilgrids_01_clay_both_depths.png) | clay plausible at both depths, nodata matches the gulf |
| [soilgrids_02_sand_both_depths.png](qa_screenshots/soilgrids_02_sand_both_depths.png) | sand, inverse pattern to clay as expected |
| [soilgrids_03_silt_both_depths.png](qa_screenshots/soilgrids_03_silt_both_depths.png) | silt |
| [soilgrids_04_soc_both_depths.png](qa_screenshots/soilgrids_04_soc_both_depths.png) | organic carbon low, as desert soil must be |
| [soilgrids_05_bdod_both_depths.png](qa_screenshots/soilgrids_05_bdod_both_depths.png) | bulk density in the real-soil band |
| [soilgrids_06_cfvo_both_depths.png](qa_screenshots/soilgrids_06_cfvo_both_depths.png) | coarse fragments |
| [soilgrids_07_texture_triangle_by_catchment.png](qa_screenshots/soilgrids_07_texture_triangle_by_catchment.png) | the 100.00% sum is physically sensible, not arithmetic luck |
| [soilgrids_08_unit_conversion_before_after.png](qa_screenshots/soilgrids_08_unit_conversion_before_after.png) | the ÷10 divisor, and the 100% ceiling not being breached |
| [soilgrids_09_within_catchment_variance.png](qa_screenshots/soilgrids_09_within_catchment_variance.png) | spread per catchment, not just a point estimate |

**Variables:** clay, sand, silt, soc, bdod, cfvo at 0–5 cm and 5–15 cm (12 rasters).

**Unit conversions** (values ship as scaled integers; divide by these):

| variable | divisor | converted unit | observed range |
|---|---:|---|---|
| clay | 10 | % | 17.6 – 55.8 |
| sand | 10 | % | 10.6 – 51.4 |
| silt | 10 | % | 25.1 – 50.3 |
| soc | 10 | g/kg | 3.1 – 60.5 |
| bdod | 100 | kg/dm³ | 1.09 – 1.46 |
| cfvo | 10 | vol% | 13.3 – 39.7 |

**How the divisors were verified rather than assumed.** Clay + sand + silt is a
closed composition and must sum to 100%. It does, to a median of **exactly 100.00**
at both depths — and a 10× divisor error would land the sum at 1000 or 10, so this
single identity pins the texture divisor. Bulk density landing in 1.09–1.46 kg/dm³ is
textbook real soil, and organic carbon median 12.1 g/kg is appropriately low for
desert. 21/21 tests in
[tests/test_soilgrids_units.py](../tests/test_soilgrids_units.py) pass.

**Statistics retained per catchment:** mean, std, min, max, median, count — for all
6 variables at both depths, giving 73 columns. Added beyond the requested mean
because a catchment whose clay spans 18–56% behaves differently from one uniformly
at 35%, and the mean alone hides that.

**Known limitations**

1. SoilGrids is a **globally model-derived product, not surveyed soil**, so it must
   be used strictly as a *relative* erodibility ranking across our catchments and no
   value may ever be quoted as a measured local soil property.
2. The honest answer if a judge asks how we know Aqaba's soil texture is: *"We don't.
   We use a global model as a relative ranking across catchments, and local sampling
   is a Phase 2 item."*
3. The 250 m cells are **coarser than the smaller catchments**, so aggregation uses
   `all_touched=True`; without it a small catchment can contain no cell centre and
   return null rather than a value.
4. The WCS GeoTIFFs arrive with **no nodata tag declared**, yet 25.5% of cells are
   exactly `0`, matching the AOI's sea fraction — these are nodata, not soil with
   zero clay, and are masked to NaN in `soilgrids_units.load_converted()`. Left
   unmasked they would drag every coastal catchment mean toward zero.

---

## 3. OpenStreetMap — Jordan extract

| Field | Value |
|---|---|
| **Product/version** | Geofabrik `jordan-latest.osm.pbf`, 30 MB |
| **Access date** | 2026-08-01 |
| **Access method** | `https://download.geofabrik.de/asia/jordan-latest.osm.pbf`, clipped with `ogr2ogr -clipsrc` |
| **Spatial resolution** | Vector (no intrinsic resolution) |
| **Coverage** | Padded box |
| **License** | ODbL 1.0 — © OpenStreetMap contributors |
| **Reproduce** | `./scripts/extract_osm.sh` then `../.venv/bin/python osm_drainage_report.py` |
| **Outputs** | `data/raw/osm/jordan-latest.osm.pbf`, `data/processed/vectors/osm_aqaba.gpkg` (12 layers) |

**QA figures**

| figure | claim it makes checkable |
|---|---|
| [osm_01_roads_over_satellite.png](qa_screenshots/osm_01_roads_over_satellite.png) | roads align with visible carriageways — georeferencing is right |
| [osm_02_buildings_over_satellite.png](qa_screenshots/osm_02_buildings_over_satellite.png) | footprints match built-up areas in imagery |
| [osm_03_waterways_drainage_over_satellite.png](qa_screenshots/osm_03_waterways_drainage_over_satellite.png) | drainage follows real wadi floors |
| [osm_04_culverts_all_27_numbered.png](qa_screenshots/osm_04_culverts_all_27_numbered.png) | all 27 culverts, numbered to match the handoff table |
| [osm_05_culvert_top5_insets.png](qa_screenshots/osm_05_culvert_top5_insets.png) | each top culvert sits under a visible road embankment |
| [osm_06_dive_poi_and_marine_park.png](qa_screenshots/osm_06_dive_poi_and_marine_park.png) | dive sites and the Marine Park boundary |
| [urban_01_road_density_choropleth.png](qa_screenshots/urban_01_road_density_choropleth.png) | road density per catchment |
| [urban_02_builtup_fraction_choropleth.png](qa_screenshots/urban_02_builtup_fraction_choropleth.png) | built-up fraction per catchment |

**Layers extracted (12)**

| layer | features | purpose |
|---|---:|---|
| roads | 3 845 | impervious surface, runoff |
| buildings | 10 099 | independent built-up estimate |
| waterways | 206 | drainage network |
| drainage_features | 200 | **outlet correction** — 27 culverts |
| industrial | 32 | sediment/contaminant source proxy |
| port | 1 | port frontage |
| dive_tourism_poi | 75 | who the alert product serves |
| tourism_areas | 208 | coastal tourism footprint |
| protected_areas | 2 | **Aqaba Marine Park**, independent reef reference |
| osm_coastline | 11 | **independent check on the derived shoreline** |
| infrastructure_lines | 251 | rail, embankments, breakwaters — flow-blocking |
| water_bodies | 49 | reservoirs, standing water |

**Custom osmconf was required.** GDAL's default OSM config does not expose `tunnel`,
`industrial`, `natural` or `protect_class` as columns — they sit inside the
`other_tags` HSTORE where SQL cannot filter them cleanly.
[scripts/osmconf_reefshield.ini](../scripts/osmconf_reefshield.ini) promotes them,
and that is what surfaced the **27 culverts**, the **Aqaba Marine Park**, and the
**OSM coastline**. `drainage_features` composition: 89 stream, 57 drain, 41 canal,
9 river, 4 ditch; 27 `tunnel=culvert`; 102 `intermittent=yes`; 9 named, including
**وادي اليتيم (Wadi Al-Yutum)**, the major wadi draining to Aqaba.

**Known limitations**

1. **Absence of a mapped feature is not evidence of absence.** OSM drainage
   completeness in Aqaba is unverified and probably patchy, so only *positive*
   matches — a feature that IS mapped — may be used as outlet corrections, and OSM
   may never be used to rule a channel out.
2. Tagging for arid drainage is **inconsistent across contributors**: `wadi` is
   deprecated upstream but still present in Jordanian data, so the filter
   deliberately catches every variant rather than one canonical tag.
3. The extract is a **single snapshot with no version history**, so if a contributor
   adds or removes a culvert tomorrow our conflict list silently goes stale; the
   access date above is the only provenance anchor.

---

## 4. Reef zones (provisional — Allen Coral Atlas pending)

| Field | Value |
|---|---|
| **Product/version** | **PROVISIONAL**, derived. Allen Coral Atlas v2.0 export is swap-in #3. |
| **Access date** | 2026-08-01 (provisional build) |
| **Access method** | Derived from the water mask + published dive-site positions |
| **Coverage** | Jordanian coast, 29.356–29.530 N |
| **License** | n/a (own derivation). ACA is CC BY 4.0 when swapped in. |
| **Reproduce** | `../.venv/bin/python make_reef_zones_provisional.py` (needs `process_bathymetry.py` first) |
| **Output** | `data/processed/vectors/reef_zones_PROVISIONAL.gpkg` |

**QA figures**

| figure | claim it makes checkable |
|---|---|
| [reef_01_provisional_over_satellite.png](qa_screenshots/reef_01_provisional_over_satellite.png) | every zone is seaward of the visible shoreline |
| [reef_02_per_zone_insets.png](qa_screenshots/reef_02_per_zone_insets.png) | each zone individually, with area/park/depth |
| [reef_03_overlap_bug_before_after.png](qa_screenshots/reef_03_overlap_bug_before_after.png) | **bug fixed** — 1.46 ha double-count removed |
| [reef_04_marine_park_validation.png](qa_screenshots/reef_04_marine_park_validation.png) | **independent validation** against the Marine Park |
| [depth_04_crossshore_profiles_per_zone.png](qa_screenshots/depth_04_crossshore_profiles_per_zone.png) | why width is an assumption, not a derived contour |

**Schema** — every field that will exist in the final `reef_zones.gpkg` exists here
already, with the same names and types, so the exposure engine is built once:

| column | type | notes |
|---|---|---|
| `reef_zone_id` | str | `R-01`…`R-08`, contract §2. **Never renumber.** |
| `id` | str | Duplicate of `reef_zone_id` — contract §3 names the column `id`, the implementation plan uses `reef_zone_id`. Both carried so either join key works. |
| `zone_name` | str | Human-readable coastal stretch |
| `habitat_class` | str | `unknown` until ACA lands |
| `sensitivity_weight` | float | **1.0 placeholder for every zone** |
| `sensitivity_weight_status` | str | `PLACEHOLDER_PENDING_MARINE_SCIENTIST` — in the schema itself, not only the docs |
| `provisional` | bool | `True` |
| `geom_basis` | str | How the geometry was derived |
| `area_km2` | float | From UTM 36N, never degrees |
| `depth_median_m`, `depth_min_m` | float | Context only — see caveat |
| `marine_park_overlap_pct` | float | **Real measured data**, added this pass |

**Zones** (north → south, total 5.69 km², consistent with published estimates of
Jordan's reef area of ~5–13 km²):

| id | stretch | area km² | median depth m | in Marine Park |
|---|---|---:|---:|---:|
| R-01 | North Aqaba / Ayla & Public Beach | 0.85 | −44.8 | 0% |
| R-02 | Port frontage / First Bay & Power Station | 0.81 | −312.2 | 0% |
| R-03 | Tourist Camp / north Marine Park boundary | 0.62 | −220.6 | 0% |
| R-04 | Marine Science Station / Cedar Pride | 0.42 | −103.7 | **71.3%** |
| R-05 | Japanese Garden / Gorgonian | 0.39 | −36.6 | **66.6%** |
| R-06 | Black Rock / Blue Coral | 0.54 | −21.6 | **84.5%** |
| R-07 | Tala Bay / Seven Sisters | 0.61 | −19.9 | **79.1%** |
| R-08 | Royal Diving Club / Yamanieh to Saudi border | 1.44 | −29.4 | 7.8% |

**Independent validation.** The Aqaba Marine Park boundary (from OSM,
`protect_class=4`, 3.45 km², spanning 29.397–29.460 N) was **never used as an input
to zone placement**, yet R-04–R-07 land 67–85% inside it. That is genuine
corroboration that the dive-site latitudes are right. R-01–R-03 falling outside is
consistent with them being city and port frontage.

**What is trustworthy in this geometry, and what is not.** A first attempt placed
these as boxes on a hand-fitted straight-line shoreline. Checked against the
bathymetry it was ~600 m too far east at R-03–R-05 (those boxes sat on dry land at
+7 to +18 m elevation) and too far west at R-07–R-08 (in 250–400 m of open water).
- **Along-shore position is data-derived** from the water mask, reliable to ~50 m,
  and an `assert` now requires every zone's median depth to be below sea level.
- **Seaward width is a flat 250 m assumption**, deliberately *not* derived from depth
  contours: the Gulf of Aqaba drop-off is far steeper than the bathymetry's ~450 m
  true resolution can resolve, so those contours would dress an artefact up as a
  measurement. `area_km2` is therefore order-of-magnitude only.
- The implausibly deep medians at R-02/R-03 are that same artefact, not evidence of
  300 m-deep reef.

**Known limitations**

1. **Allen Coral Atlas maps shallow reef only**, so once swapped in, deeper habitat
   remains unrepresented and the exposure model is silent about it.
2. **`sensitivity_weight` reflects team assumptions, not Atlas data and not
   scientific measurement**; assigning real weights is a Phase 2 item requiring
   marine-scientist input, and this must be said out loud on the slide because
   presenting invented weights as data is what loses credibility under questioning.
3. `marine_park_overlap_pct` is deliberately stored as a **raw measured percentage
   and not converted into a sensitivity weight**, because that conversion is the
   marine scientist's judgement call and inventing it from protection status would
   repeat the exact error limitation 2 warns about.
4. **R-01 and R-02 cover developed beach and port frontage** where reef presence is
   doubtful; per contract §2, if ACA yields fewer real zones the extras are dropped
   and the remaining IDs keep their names, never renumbered.
5. R-08 is **2.4× the median zone area** and straddles the park boundary, making it
   the obvious candidate for a split once real habitat data exists — but splitting it
   now would change the zone count and break the ID contract, so it is flagged as a
   recommendation rather than done unilaterally.

---

## 5. Bathymetry — depth field and coastline

| Field | Value |
|---|---|
| **Product/version** | **GMRT (Global Multi-Resolution Topography), gmrt.org** — GEBCO stand-in |
| **Access date** | 2026-08-01 |
| **Access method** | `https://www.gmrt.org/services/GridServer`, `resolution=max`, `layer=topo` |
| **Spatial resolution** | ~53 m grid spacing; **true information content ~450 m** |
| **Coverage** | Padded box, 639×943 source → 699×1013 @ 50 m in UTM 36N |
| **License** | Open — GMRT / GEBCO attribution |
| **Reproduce** | `../.venv/bin/python process_bathymetry.py` |
| **Outputs** | `data/raw/bathymetry/gmrt_aqaba.tif`, `data/processed/bathymetry/depth_utm36n.tif`, `data/processed/vectors/coastline.gpkg` |

**QA figures**

| figure | claim it makes checkable |
|---|---|
| [depth_01_full_field_and_isobaths.png](qa_screenshots/depth_01_full_field_and_isobaths.png) | the field handed to Nizar, and the steep shelf |
| [depth_02_sign_convention_22_control_points.png](qa_screenshots/depth_02_sign_convention_22_control_points.png) | 22/22 control points pass, each labelled |
| [depth_03_nodata_bug_before_after.png](qa_screenshots/depth_03_nodata_bug_before_after.png) | **bug fixed** — 1917 NaN → 0, one sentinel |
| [coastline_01_single_sea_body.png](qa_screenshots/coastline_01_single_sea_body.png) | one sea body, no false interior lakes |
| [coastline_02_osm_vs_gmrt_agreement.png](qa_screenshots/coastline_02_osm_vs_gmrt_agreement.png) | **substitution justified** — 62 m median vs OSM |

**Provenance deviation — flagged deliberately, not buried.** The contract asks for
GEBCO 15 arc-second. Every programmatic GEBCO route is currently closed:
`wcs.gebco.net` returns empty capabilities, `download.gebco.net` rejects POST (405),
and BODC GeoTIFF tile paths 404. GEBCO's portal is an interactive web form and cannot
be scripted. We therefore ship GMRT, a synthesis whose deep-water source in this
region **is** GEBCO.

Two independent corroborations:
- GMRT and NOAA NCEI's independent global DEM mosaic agree on the AOI minimum to
  within 0.2 m (−907.08 vs −907.27 m).
- The derived coastline agrees with **OSM's `natural=coastline`** — a completely
  separate lineage, traced from imagery — to a **median of 62 m**, about one 50 m
  pixel, rising to 337 m at p90 in the port and marina where breakwaters are below
  the source resolution.

`resolve_source()` prefers a canonical `data/raw/bathymetry/gebco_aqaba.tif` if
anyone drops one in from the web form; **nothing else in the pipeline changes.** The
file is named `gmrt_aqaba.tif` rather than `gebco_aqaba.tif` on purpose — naming a
GMRT file "gebco" is exactly the silent provenance error the contract exists to
prevent.

**Verified properties**

- **Sign convention: negative = below sea level, positive = land**, asserted against
  **22 empirically sampled control points** spread across the whole basin (11 water,
  11 land). Expanded from 5, which were clustered near the city and could have passed
  while the mask was wrong elsewhere. The expansion immediately caught two points
  wrongly assumed to be mid-gulf that are in fact Wadi Araba land at +533 m and
  +241 m.
- Depth range −907.1 m to +1542.3 m; 23.3% of the AOI below sea level (WorldCover
  independently: 23.89%).
- The water mask polygonises to **one** 397.3 km² sea body — no spurious interior
  lakes in dry wadi floors, which would punch false holes in the particle barrier.
- **Single nodata representation.** GMRT ships 1 917 cells (~0.3%) as bare NaN with
  no nodata tag; these are gap-filled before warping and the output carries only the
  declared `−32768` sentinel.

**Known limitations**

1. **15 arc-seconds is ≈450 m at this latitude**, which is sufficient for basin-scale
   geometry and as a "particles stop at the shore" barrier but **not** sufficient for
   reef-scale depth changes, small channels or harbour structures, so the plume model
   must not be read as resolving anything at that scale.
2. The **~53 m grid spacing is not 53 m of resolution**: away from multibeam tracks
   GMRT is interpolated from the coarser source grid, so quoting 53 m as the
   resolution would overstate the data by roughly an order of magnitude.
3. The **coastline is derived from the 0 m contour of that same coarse grid**, which
   is why it is only accurate to ~62 m in the median and several hundred metres
   around engineered structures — quantified against OSM rather than asserted.
4. A **NaN depth does not raise an exception**; it silently turns any interpolated
   particle position into a non-number, which is why the nodata consolidation is
   enforced by an `assert` rather than left to convention.

---

## Feature tables — schema

`data/processed/features/*.parquet`, all joined on `catchment_id` (`AQ-C{NN}`,
contract §2). Produced by [aggregate_catchments.py](../scripts/aggregate_catchments.py).

| table | columns |
|---|---|
| `landcover_by_catchment` | `catchment_id`, `landcover_px_total`, `frac_<class>` × 11, `frac_bare_or_sparse` |
| `soil_by_catchment` | `catchment_id`, `<var>_<depth>_{mean,std,min,max,median,count}` × 12 = **73 columns** |
| `urban_by_catchment` | `catchment_id`, `area_km2`, `road_density_km_per_km2`, `road_length_km`, `osm_building_frac`, `osm_building_count`, `mapped_drainage_km_per_km2`, `industrial_frac`, `infra_line_km_per_km2`, `tourism_poi_count` |

**Built-in assertions:** land-cover fractions must sum to 1.0 per catchment, and
catchment-mean texture must still sum to 100% after spatial averaging.

**`osm_building_frac` vs `frac_built_up` are independent estimates and will
disagree** — OSM maps roofs, WorldCover's `built_up` includes roads, yards and
parking. The disagreement is informative, not a bug.

> **Current status: blocked on Mahdi's catchment polygons** (contract §4 P1). The
> pipeline is written, runs clean, and its assertions pass against a labelled local
> fixture, with outputs quarantined to `data/interim/*_FIXTURE.parquet`. The contract
> feature paths are **not** written in fixture mode. Re-run when Mahdi publishes —
> that is the only remaining step.

---

## Bugs caught by this QA discipline

Five so far. Each has a figure or a test, because a fix without evidence is a claim.

| # | bug | how it would have failed silently | evidence |
|---|---|---|---|
| 1 | Reef zones R-03–R-05 placed on **dry land** | exposure scores computed for land | [reef_01](qa_screenshots/reef_01_provisional_over_satellite.png), depth assert |
| 2 | **Mixed NaN / −32768** nodata in depth field | NaN particle positions, no exception | [depth_03](qa_screenshots/depth_03_nodata_bug_before_after.png) |
| 3 | **Undeclared 0-nodata** in SoilGrids over sea | coastal catchment means dragged to zero | [soilgrids_08](qa_screenshots/soilgrids_08_unit_conversion_before_after.png), 21 tests |
| 4 | **1.46 ha overlap** between R-04 and R-05 | reef area double-counted, inflated headline | [reef_03](qa_screenshots/reef_03_overlap_bug_before_after.png) |
| 5 | Culvert distances measured in **EPSG:3857** | every distance overstated by 14.8% | [osm_04](qa_screenshots/osm_04_culverts_all_27_numbered.png) now matches the report |

Bugs 4 and 5 were both found *by building the figure*, not by reading the code.
# ReefShield Data Dictionary

One row per source variable, from provider to processed output. Every entry
reflects what was actually retrieved and verified in this workstream.

Access dates in this document: **2026-08-01** (IMERG Early; ERA5-Land example
windows) and **2026-07-31 / 2026-08-01** (IMERG Final Oct 2016 window).

---

## 1. NASA GPM IMERG V07 — Final Run

| Field | Value |
|---|---|
| Source organization | NASA / JAXA (GPM mission), distributed by NASA GES DISC |
| Dataset name | GPM IMERG Final Precipitation L3 Half Hourly 0.1° |
| Product / version | `GPM_3IMERGHH`, version **07** (files V07B) |
| Collection concept ID | `C2723754847-GES_DISC` |
| Run type | **final** — gauge-adjusted, calibrated |
| Suitable for training | **Yes** |
| Access method | NASA Harmony spatial + variable subsetting (`harmony-py`), auth via `earthaccess` |
| Registration required | Yes — NASA Earthdata account **plus** one-time approval of *NASA GESDISC DATA ARCHIVE* |
| Licence / terms status | Accepted (EULA approved 2026-08-01; blocked downloads until then) |
| Native format | HDF5 (global) |
| Processed format | NetCDF4 subset (~44 KB per granule vs ~7.6 MB global) |
| Temporal resolution | 30 minutes |
| Time availability | 2000-06 → present (Final lags ~3.5 months) |
| Spatial resolution | 0.1° (~11 km) |
| Geographic extent used | 34.80–35.15 °E, 29.25–29.70 °N (5 lat × 4 lon cells) |
| Raw path | `data/raw/imerg/events/<event_id>/` |
| Processed path | `data/processed/events/<event_id>/<event_id>_imerg.nc` |
| Citation | https://gpm.nasa.gov/data/imerg |

| Variable | Internal name | Units | Missing-data semantics | Transformation |
|---|---|---|---|---|
| `Grid/precipitation` | `precipitation` | mm/hr | `_FillValue = -9999.9` → NaN; never zero | transpose `(time, lon, lat)` → `(time, lat, lon)` |
| derived | `precipitation_depth_mm` | mm | NaN propagates | `rate × 0.5 h` |
| derived | `rain_1h_mm`, `rain_3h_mm`, `rain_6h_mm`, `rain_24h_mm` | mm | NaN if any interval missing (`skipna=False`) | trailing rolling sums, `min_periods` = full window |
| `Grid/lat`, `Grid/lon` | `lat`, `lon` | degrees | — | ascending |
| `Grid/time` | `time` | UTC | — | cftime `DatetimeJulian`, epoch 1980-01-06 |
| `Grid/lat_bnds`, `lon_bnds`, `time_bnds` | same | — | — | carried through, used for cell footprints |

**Limitations.** ~11 km cells smooth the localized convective storms that cause
Aqaba flash floods — a documented product limitation, not a pipeline defect.
The delivered array is `(time, lon, lat)`; index-order errors are silent.
Harmony does **not** concatenate — one file per granule.

---

## 2. NASA GPM IMERG V07 — Early Run

| Field | Value |
|---|---|
| Source organization | NASA / JAXA, GES DISC |
| Dataset name | GPM IMERG Early Precipitation L3 Half Hourly 0.1° |
| Product / version | `GPM_3IMERGHHE`, version **07** (files V07C) |
| Collection concept ID | `C2723758340-GES_DISC` (resolved from CMR, Harmony-verified) |
| Run type | **early** — preliminary, uncalibrated |
| Suitable for training | **No** — `preliminary=true`, `calibrated_final_product=false` |
| Observed latency | **6.1 h** measured 2026-08-01 (latest granule 08:00 UTC at 14:06 UTC) |
| Access method | Same Harmony path as Final; separate collection ID |
| Registration required | Same Earthdata account and GES DISC approval |
| Licence / terms status | Accepted |
| Native / processed format | HDF5 → NetCDF4 subset |
| Temporal / spatial resolution | 30 minutes / 0.1° |
| Time availability | ~4–6 h behind real time |
| Raw path | `data/raw/imerg/early_live/` |
| Processed path | `data/processed/live/imerg_early_latest.nc` |
| Citation | https://gpm.nasa.gov/data/imerg |

Variables identical to Final Run. Every output carries `imerg_run_type="early"`,
and Early results are written to `live/` so they can never overwrite Final Run
files.

**Limitations.** Preliminary values are revised in Late and Final runs.
**Granules can be missing**: on 2026-08-01 the 07:00 UTC granule was absent
(83.33 % window completeness). Gaps are reported and the longest contiguous run
is processed; nothing is interpolated.

---

## 3. ERA5-Land Hourly

| Field | Value |
|---|---|
| Source organization | ECMWF / Copernicus Climate Change Service (C3S) |
| Dataset name | ERA5-Land hourly data from 1950 to present |
| Product / version | `reanalysis-era5-land` (ERA5-Land) |
| Run type | reanalysis (not applicable to Final/Early distinction) |
| Access method | Copernicus CDS API (`cdsapi` ≥ 0.7.7), credentials in `~/.cdsapirc` |
| Registration required | Yes — CDS account **plus** one-time ERA5-Land licence acceptance |
| Licence / terms status | Accepted 2026-08-01 (403 "required licences not accepted" until then) |
| Native format | GRIB, converted server-side to NetCDF (cfgrib 0.9.15.1 / ecCodes 2.48.0) |
| Processed format | NetCDF4 |
| Temporal resolution | 1 hour |
| Time availability | 1950 → present (~5-day lag) |
| Spatial resolution | 0.1° (~9 km native) |
| Geographic extent used | CDS area `[29.70, 34.80, 29.25, 35.15]` → 5 lat × 4 lon |
| Raw path | `data/raw/era5_land/events/<event_id>/` |
| Processed path | `data/processed/events/<event_id>/<event_id>_era5_land.nc` |
| Citation | https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land |

| CDS variable | Short name | Internal name | Units | `GRIB_stepType` | Missing-data semantics | Transformation |
|---|---|---|---|---|---|---|
| `volumetric_soil_water_layer_1` | `swvl1` | `swvl1` | m³ m⁻³ | `instant` | permanent sea mask → NaN | negatives in `[-1e-12, 0)` → 0; **never deaccumulated** |
| `total_precipitation` | `tp` | `total_precipitation_hourly_m` / `_mm` | m / mm | `accum` | NaN preserved | reset-aware deaccumulation, then × 1000 |
| `surface_runoff` | `sro` | `surface_runoff_hourly_m` / `_mm` | m / mm | `accum` | NaN preserved | same |
| `sub_surface_runoff` | `ssro` | `subsurface_runoff_hourly_m` / `_mm` | m / mm | `accum` | NaN preserved | same |
| `10m_u_component_of_wind` | `u10` | `u10` | m s⁻¹ | `instant` | NaN preserved | none — negatives are physical |
| `10m_v_component_of_wind` | `v10` | `v10` | m s⁻¹ | `instant` | NaN preserved | none |
| `2m_temperature` | `t2m` | `t2m` | K | `instant` | NaN preserved | none — **not** converted to °C |

**Limitations.**
- **Land-only.** 3 of 20 cells over the Gulf of Aqaba are permanently NaN, and
  the mask is identical across all seven variables.
- **Accumulations reset daily at 00 UTC**, and the 00 UTC value is the previous
  day's 24-hour total. See `docs/era5_land_temporal_semantics.md`.
- **GRIB quantisation** produces negative increments of exactly −7.45e−9 and
  −1.49e−8 m; the module default tolerance of 1e-10 m is too tight for real
  data (use 1e-7 m).
- **CDS expands `year × month × day × time` as a product** — cross-midnight
  partial windows over-request. The pipeline chunks daily to prevent this.
- Latitude is delivered **descending**; normalised to ascending on read.

---

## 4. Derived antecedent features

Produced by `backend/src/processing/antecedent_features.py`; written to
`<event_id>_antecedent_features.parquet`.

| Feature | Units | Definition |
|---|---|---|
| `soil_moisture_t_minus_24h`, `_72h` | m³ m⁻³ | `swvl1` sampled at the exact lag |
| `precipitation_prior_24h_mm`, `_72h_mm`, `_7d_mm` | mm | sum over `(event − N h, event]` |
| `surface_runoff_prior_*`, `subsurface_runoff_prior_*` | mm | same windows |
| `u10_event_time`, `v10_event_time` | m s⁻¹ | value at the event hour |
| `wind_speed_event_time` | m s⁻¹ | `sqrt(u10² + v10²)` |
| `wind_direction_event_time` | degrees | **meteorological**: bearing the wind blows **from**; `(270 − deg(atan2(v, u))) mod 360` |
| `temperature_2m_event_time` | K | value at the event hour |
| `mean_wind_speed_prior_state_window`, `mean_temperature_...` | m s⁻¹, K | mean over the trailing state window |
| `<feature>_valid_fraction` | 1 | share of the window with usable data |
| `valid_data_fraction` | 1 | minimum across all features |
| `quality_flag` | — | `GOOD` / `MISSING_DATA` / `PARTIAL_WINDOW` / `NO_DATA` |

Missing hours are excluded from sums and reduce the valid fraction — never
treated as zero.

---

## 5. Rainfall candidates

`data/processed/events/rainfall_candidates.parquet`. Columns per the Phase 7
contract, including `candidate_generation_scope`, `search_scope_start_utc`,
`search_scope_end_utc` and **`is_exhaustive`**.

> **`is_exhaustive = false`** for everything produced so far. The table covers
> only the configured demonstration windows and is **not** a complete
> historical event catalogue.

---

## 6. CHIRPS — not executed

| Field | Value |
|---|---|
| Source organization | UCSB Climate Hazards Center / USGS |
| Dataset name | CHIRPS (Climate Hazards InfraRed Precipitation with Station data) |
| Status | **Out of scope for this workstream — not retrieved, not evaluated** |
| Reason | IMERG Final + Early already satisfy the rainfall requirement; CHIRPS was never part of the executed plan |
| Registration | None required (open access) |
| Note | Listed only so its absence is explicit rather than an oversight. No CHIRPS data exists anywhere in this repository. |

---

## 7. Cross-product warning

**ERA5-Land and IMERG grids are not index-aligned.** Both are 0.1° and both are
5 × 4 over this box, which makes index pairing look plausible — it is wrong:

```
IMERG lat: 29.25 29.35 29.45 29.55 29.65   (ascending)
ERA5  lat: 29.30 29.40 29.50 29.60 29.70   (after normalisation)
IMERG lon: 34.85 34.95 35.05 35.15
ERA5  lon: 34.80 34.90 35.00 35.10
```

Cell centres are offset by half a cell. Any spatial combination must use
area-weighted overlap or catchment aggregation. No index-based merge exists
anywhere in this codebase.

---

## 8. Sentinel-2 / Landsat — plume validation imagery (Abd)

Full audit and methodology: [event_audit.md](event_audit.md). Access method
verified 2026-08-02: Microsoft Planetary Computer STAC
(`planetarycomputer.microsoft.com/api/stac/v1`), anonymous SAS-token signing
via the `planetary-computer` package — no Copernicus Data Space / Earth
Engine login needed. Search box: `ANALYSIS_BBOX` (`scripts/config.py`).

| Product/version | Access date | Scene ID(s) | Role |
|---|---|---|---|
| Sentinel-2 L2A | 2026-08-02 | `S2A_MSIL2A_20161102T082112_R121_T36RXT_20210213T163836` | Post-event candidate, AQ-2016-10-28. Cloud 3.6% (scene), 0.07% (AOI water). **No plume visible** — see event_audit.md §1a. |
| Sentinel-2 L2A | 2026-08-02 | `S2A_MSIL2A_20161023T082012_*_T36RXT/T36RYT` | Pre-event, in-window — 82–85% cloud, unusable |
| Sentinel-2 L2A ×8 | 2026-08-02 | `20161013T082002`, `20161003T081752`, `20160923T082002`, `20160913T081602`, `20160903T082012`, `20160824T081602`, `20160814T082012`, `20160725T082012` (all `T36RXT`) | Baseline composite (median), <1.1% cloud each |
| Landsat 8 C2 L2 | 2026-08-02 | `LC08_L2SP_174039_20161101_02_T1` | Independent post-event corroboration, +4 days, 0.47% cloud (tile 174040 was 32.8%, unused) |
| Landsat 7 C2 L2 ×4 | 2026-08-02 | `LE07_L2SP_174039_20130202_02_T1`, `LE07_L2SP_174040_20130202_02_T1`, `LE07_L2SP_174039_20130218_02_T1`, `LE07_L2SP_174040_20130218_02_T1` | Feb 2013 backup event candidates — SLC-off gaps, exact event date still unresolved (event_audit.md §2) |

**Outputs:** `data/processed/plume/baseline_composite.tif`,
`data/processed/plume/observed_plume_probability.tif`,
`data/processed/vectors/observed_plume.gpkg`.

**⚠️ The probability raster and vector polygons are a documented artifact,
not a validated plume detection** — differencing Sentinel-2 L2A reflectance
over open water across dates produces a coastline-hugging anomaly from
atmospheric-correction/sun-angle noise, confirmed by testing a same-season
baseline and a much larger coastal buffer without it going away (full
reasoning: event_audit.md §1a). Two independent sensors' true-color imagery
and the Kalman et al. (2025) in-situ mooring timing all agree the real plume
had already dispersed before either satellite pass. **Do not consume these
two files as ground truth without reading that section first.**

**Reproduce:** `cd scripts && ../.venv/bin/python run_plume_extraction.py`
(pipeline code: `backend/src/models/plume_segmentation.py`).

---

## 8. Nizar — Weather Forecasts & Ocean Currents

**Owner:** Nizar · **Feeds:** Component A (forecast mode), Component F (plume transport)
**Last verified:** 2026-08-02 · **Judge-facing limitation:** [forcing_limitations.md](forcing_limitations.md)

Spatial contract as above (§ intro). All sources below pulled live and cached under
`data/raw/forecasts/` and `data/raw/currents/`; ingestion code in
`backend/src/ingestion/{gfs,gefs,ecmwf,ocean_currents}.py`.

| Product | Provider | Version | Extent | Access Date | License | Citation / Notes |
|---|---|---|---|---|---|---|
| GEBCO Bathymetry (GeoTIFF) | GEBCO / gebco.net | GEBCO 2026 Global | padded download box | 2026-08-02 | GEBCO Grid Terms of Use (free, cite GEBCO) | **Superseded, 2026-08-03 — do not chase this further.** Requested via the web subsetter on Day 1 (email delivery), but the file never landed and this is now moot: Pulga's team independently substituted GMRT project-wide ("every programmatic GEBCO route closed" — `tasks/phase2/00-phase2-plan.md`). The depth field the particle engine actually uses is `gmrt_bathymetry` (see §5 "Bathymetry — depth field and coastline" above), already loaded into `raster_assets`. |
| NOAA GFS (pgrb2.0p25) | NOAA NCEP / AWS Open Data (`noaa-gfs-bdp-pds`) | 2026-08-02 00Z cycle | padded box, F00–F48 (3h steps) | 2026-08-02 | US Government work, public domain | Pulled via Herbie (GRIB .idx byte-range subset, no full-file download). Variables: APCP surface (→ `tp`), UGRD/VGRD 10 m (→ `u10`/`v10`). → `backend/src/ingestion/gfs.py`, cached at `data/raw/forecasts/gfs/latest_gfs_aoi_forecast.nc`. |
| NOAA GEFS (atmos.5, pgrb2a) | NOAA NCEP / AWS Open Data (`noaa-gefs-pds`) | 2026-08-02 00Z cycle | padded box, F03–F48 (3h steps), 30 members | 2026-08-02 | US Government work, public domain | Pulled via Herbie, one GRIB subset per member per lead hour (480 total, full production run confirmed). Computes AOI-level ensemble exceedance probability against a placeholder 3h rain threshold (15mm) — swap for Karam's real per-catchment percentile once `rainfall_candidates.parquet` lands. Result: 0.00 exceedance across all 16 lead hours (correct — dry day, all 30 members agree). → `backend/src/ingestion/gefs.py`, cached at `data/raw/forecasts/gefs/latest_gefs_exceedance.nc`. |
| ECMWF IFS Open Data | ECMWF Open Data portal (rolling archive) | latest available run, 2026-08-02 | Global 0.25°, clipped locally to AOI, steps 0–48h (3h) | 2026-08-02 | CC BY 4.0 (attribute ECMWF) | Pulled via `ecmwf-opendata` client (`type=fc, stream=oper`). Variables: tp, 10u, 10v. Rolling archive only — never use for historical backfill. Feeds GFS-vs-IFS agreement flag (100% agreement on this dry day — both models correctly show no rain over the AOI). → `backend/src/ingestion/ecmwf.py`, cached at `data/raw/forecasts/ecmwf/latest_ifs_aoi_forecast.nc`. |
| HYCOM GLBy0.08 (FMRC best) | US Navy / hycom.org public THREDDS OPeNDAP | `GLBy0.08/latest` | padded box, depth 0–50m, ±24h around access time | 2026-08-02 | Approved for public release, unlimited distribution | Lazy-opened via OPeNDAP (no full 2TB download). Variables: water_u/water_v → `u`/`v`. Confirmed the resolution limitation directly: the provisional outlet cell (34.96, 29.54) is masked/nan in this grid; nearest resolved open water is ~6km further into the gulf mouth. → `backend/src/ingestion/ocean_currents.py`, cached at `data/raw/currents/hycom_aoi_recent.nc`. |
| Copernicus Marine (GLOBAL_ANALYSISFORECAST_PHY_001_024) | Copernicus Marine Service | `cmems_mod_glo_phy_anfc_0.083deg_PT1H-m` | MARINE_AOI, depth: single level ~0.49m (this product tier is surface/near-surface hourly-mean — live/rolling window only, no historical reach) | 2026-08-03 | Copernicus Marine license (free w/ registration) | **Pulled successfully — account registered and activated 2026-08-03.** Same output schema as HYCOM (interpolator is source-agnostic). At the provisional outlet (34.96, 29.54): masked/nan — same as HYCOM, two independent models agree this exact cell is unresolved. Live only — use the reanalysis row below for the demo event. → `backend/src/ingestion/ocean_currents.py`. |
| HYCOM GLBu0.08 expt_91.2 (historical) | US Navy / hycom.org public THREDDS OPeNDAP | `GLBu0.08/expt_91.2/uv3z` | MARINE_AOI, depth 0–50m (real levels: 0,2,4,...50m), 2016-04-18 to 2018-11-20 coverage | 2026-08-03 | Approved for public release, unlimited distribution | Operational-analysis archive — NOT the same product as the "latest" FMRC endpoint above, which has zero 2016 data. Pulled for the demo event window (26–31 Oct 2016). → `backend/src/ingestion/ocean_currents.py::fetch_hycom_historical`, cached at `data/raw/currents/hycom_aoi_AQ-2016-10-28.nc`. |
| Copernicus Marine GLORYS12V1 reanalysis | Copernicus Marine Service (Mercator Ocean) | `cmems_mod_glo_phy_my_0.083deg_P1D-m` | MARINE_AOI, depth 0–50m (18 real levels, 0.49–47.4m), multiyear reanalysis covering 2016 | 2026-08-03 | Copernicus Marine license (free w/ registration) | The correct product for both the historical date AND real sub-surface depth levels — the "anfc" live tier above has neither. Pulled for the demo event window (26–31 Oct 2016). → `backend/src/ingestion/ocean_currents.py::fetch_copernicus_marine_historical`, cached at `data/raw/currents/copernicus_marine_aoi_AQ-2016-10-28.nc`. |

**Note on the root `.env`:** commit `2f0a6d6` added a real `.env` at the repo root
containing live NASA Earthdata credentials in plaintext, despite its own header saying
"GIT-IGNORED. DO NOT SHARE." That file predates this workstream and was not introduced
here — flagging it so it doesn't get missed: **rotate the Earthdata password**, and
make sure no `.gitignore` gap lets it happen again (`.env` and `.env.*` must always be
excluded before any commit touches this repo).

### Phase 2 update — 2026-08-03

- **Copernicus Marine activated.** Registered account, real u/v pulled for MARINE_AOI.
  `compare_hycom_vs_copernicus()` added to `ocean_currents.py`. At the gulf mouth
  (34.90, 29.40), **today's** conditions: under 5° direction disagreement between HYCOM
  and Copernicus Marine (drifts hour to hour with live currents — see
  `docs/qa_screenshots/currents_01_hycom_vs_copernicus.png` top row for the exact
  snapshot). Both models mask the exact provisional outlet cell (34.96, 29.54) as
  unresolved/land — corroborating evidence for the resolution limitation, not a
  single-source artifact.
- **Historical pull added — the actual demo event window.** The live products above only
  cover a rolling recent window; neither reaches back to 2016. Added
  `fetch_hycom_historical()` (HYCOM `GLBu0.08/expt_91.2`) and
  `fetch_copernicus_marine_historical()` (Copernicus Marine GLORYS12V1 reanalysis,
  `cmems_mod_glo_phy_my_0.083deg_P1D-m`) — see the two new rows above. **Finding:** the two
  models' resolved (non-masked) footprints in the narrow gulf barely overlap at all — a
  0.01°-resolution scan of the full MARINE_AOI found zero shared points; the nearest point
  both resolve is (34.85, 29.30), 6km from the outlet. There, at the mooring's
  peak-response time (2016-10-28 06:50 UTC), HYCOM and Copernicus Marine disagree by
  **65.8°** on current direction — see `docs/qa_screenshots/currents_01_hycom_vs_copernicus.png`
  bottom row and `docs/forcing_limitations.md` for the full writeup. This is materially
  worse than the live agreement and is the uncertainty figure that actually applies to
  the backtest, not the "today" number.
- **Interpolator bug fixed.** `CurrentFieldInterpolator` requested `depth=0.0` by default,
  but GLORYS12V1's shallowest coordinate is 0.494m — linearly interpolating below a
  dataset's minimum silently returns `nan` rather than raising. Fixed by clipping the
  requested depth into the dataset's own `[depth.min(), depth.max()]` range before
  interpolating. This was masking real data as a false "unresolved" cell for any product
  whose shallowest level isn't exactly 0m — worth checking if any other depth-aware
  interpolation in the project has the same assumption.
- **GEFS exceedance repointed** from the Phase 1 placeholder (flat 15mm/3h) to Karam's
  real per-catchment p99 climatology (`catchment_rainfall_climatology`, window_hours=24,
  source `imerg_v07_final`). Karam's delivered climatology is daily-resolution only (no
  1h/3h/6h windows were computed), so the exceedance window is 24h, not 3h as originally
  scoped — documented here rather than silently assumed. Ensemble precipitation is now
  sampled at each of the 5 catchment centroids (not one AOI-wide mean), since TERRAIN_AOI
  is large enough (~115×128km) for GFS/GEFS grid cells to meaningfully differ by catchment.
  Real per-catchment exceedance now writes to `forecast_runs` / `forecast_catchment_rainfall`
  / `forecast_exceedance` in Postgres — see `backend/src/db/loaders/forecast_pipeline.py`.
- **Old bounding box purged.** `gfs.py`/`gefs.py`/`ecmwf.py`/`ocean_currents.py` now import
  `TERRAIN_AOI`/`MARINE_AOI` from the shared `config.spatial` module instead of a hardcoded
  bbox — done as part of the team's Day-0 merge, not by this workstream, but confirmed
  working post-merge.


---

# Terrain & Hydrology — Mahdi

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
