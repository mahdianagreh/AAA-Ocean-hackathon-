# Data dictionary — Workstream A+B (land cover, soil, urban, marine habitat)

**Owner:** Pulga · **Project:** ReefShield Aqaba · **Last verified:** 2026-08-01

**Spatial contract:** download box `34.80, 29.25, 35.15, 29.70` (W, S, E, N, EPSG:4326).
Storage CRS **EPSG:4326**, all area/distance maths in **EPSG:32636** (UTM 36N).
Constants live in [scripts/pulga_config.py](../scripts/pulga_config.py) — nothing hardcodes a bbox.

**Reproduce from zero:** [README_pulga.md](README_pulga.md).
**All 42 QA figures with captions:** [qa_screenshots/MANIFEST.md](qa_screenshots/MANIFEST.md).
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

Figures drawn in EPSG:4326 pass `pulga_config.geographic_aspect()` to `set_aspect()`.
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

**Measured composition** (padded AOI, 14280×13800 px @ 10 m):

| class | % of AOI | % of land |
|---|---:|---:|
| bare / sparse vegetation | 93.63 | **97.82** |
| permanent water | 4.28 | (sea) |
| built-up | 0.70 | 0.73 |
| grassland | 0.65 | 0.68 |
| cropland | 0.52 | 0.55 |
| tree cover | 0.12 | 0.13 |
| shrubland | 0.09 | 0.10 |
| herbaceous wetland | 0.00 | 0.00 |

Land is 18,863 km², 95.7% of the terrain extent. Note how different this is from the
v1 figures: the old box was largely sea, so water was 23.89% of it and bare ground
72.53%. The terrain box reaches 90 km inland, so it is overwhelmingly desert. Both
sets of numbers are correct for their own extent — which is exactly why an extent has
to be quoted alongside any fraction.

**Sanity check: PASSED.** Bare/sparse ground is 97.82% of the land surface, above the
concept doc's ~74% baseline and far above the 50% assert threshold. The check is an
`assert`, so a wrong class mapping halts the pipeline rather than quietly poisoning
the runoff model. Class codes are **not sequential** (10, 20, …, 95, 100) and are
declared once in `pulga_config.py`.

**Independent corroboration, recomputed for v2.** Comparing water fraction between
WorldCover and the bathymetry water mask only means something over a *common* extent.
Measured inside `MARINE_AOI`:

| product | resolution | water |
|---|---|---:|
| ESA WorldCover class 80 | 10 m | 42.91% |
| Bathymetry water mask (elev < 0) | 50 m | 41.29% |

**Agreement: 1.62 pp** between two products that share no lineage — one an optical
land-cover classifier, the other a bathymetric grid. That is good evidence both clips
are correctly georeferenced. The v1 version of this check compared 23.89% against
23.3% over the old box; it is superseded, not deleted, because the old box no longer
defines either product's extent.

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
| **Coverage** | Padded box, 526×481 cells |
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
| [osm_04_culverts_all_numbered.png](qa_screenshots/osm_04_culverts_all_numbered.png) | all 46 culverts, numbered to match the handoff table |
| [osm_05_culvert_top5_insets.png](qa_screenshots/osm_05_culvert_top5_insets.png) | each top culvert sits under a visible road embankment |
| [osm_06_dive_poi_and_marine_park.png](qa_screenshots/osm_06_dive_poi_and_marine_park.png) | dive sites and the Marine Park boundary |
| [urban_01_road_density_choropleth.png](qa_screenshots/urban_01_road_density_choropleth.png) | road density per catchment |
| [urban_02_builtup_fraction_choropleth.png](qa_screenshots/urban_02_builtup_fraction_choropleth.png) | built-up fraction per catchment |

**Layers extracted (12)**

| layer | features | purpose |
|---|---:|---|
| roads | 8 289 | impervious surface, runoff |
| buildings | 12 570 | independent built-up estimate |
| waterways | 206 | drainage network |
| drainage_features | 200 | **outlet correction** — 46 culverts |
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
and that is what surfaced the **46 culverts**, the **Aqaba Marine Park**, and the
**OSM coastline**. `drainage_features` composition: 89 stream, 57 drain, 41 canal,
9 river, 4 ditch; 27 `tunnel=culvert`; 102 `intermittent=yes`; 42 named, including
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

## 4. Reef zones (real — Allen Coral Atlas v2.0, swap-in #3 CLOSED 2026-08-03)

| Field | Value |
|---|---|
| **Product/version** | `ACA/reef_habitat/v2_0` — Allen Coral Atlas v2.0, `benthic` + `geomorphic` bands, via Google Earth Engine |
| **Access date** | 2026-08-03 (Earth Engine batch export to Drive, task `WJKEYOKSLGKFF2VSEIK5RWCD` / full-box predecessor) |
| **Access method** | `export_aca.py submit` → Drive → `export_aca.py build`. Exported at native **5 m**, CRS EPSG:32636, over the download superset box |
| **Coverage** | Export covers the full padded box; **only reef within 100 m of the Jordanian zone chain is used**. 6.09 km² of the 7.32 km² exported lies in Egyptian, Saudi and Israeli water and is deliberately discarded |
| **License** | CC BY 4.0 — Allen Coral Atlas (Arizona State University / Planet / Vulcan) |
| **Reproduce** | `../.venv/bin/python export_aca.py build` (needs the GeoTIFF in `data/raw/aca/` and `process_bathymetry.py` + `extract_osm.sh` already run) |
| **Output** | `data/processed/vectors/reef_zones.gpkg`, plus `aca_fragments_BEFORE_MERGE.gpkg` (raw polygonized ACA) and `aca_pieces_ASSIGNED.gpkg` (audit trail of which piece went to which zone) |
| **Superseded** | `reef_zones_PROVISIONAL.gpkg` is retained for the before/after comparison only. **Do not read it as current geometry** — `qa_marine.py` now prefers the final file automatically |

**Swap-in #3 result — verified 2026-08-03**

| check | result |
|---|---|
| zone IDs | **8/8 survived**, none renumbered, none dropped (contract §2) |
| worst centroid drift | **982 m** against a 5 km assert bound |
| piece assignment | cut at zone boundaries, guarded by an area-conservation assert |
| `sensitivity_weight` | **still 1.0**, still `PLACEHOLDER_PENDING_MARINE_SCIENTIST` |

**Area correction — the headline of this swap.** The provisional strips claimed 5.69 km²;
the Atlas outline gives **1.24 km²**, roughly **4.6× smaller**. The strips assumed a uniform
250 m width along the whole coastline, and that assumption was the error. Any exposure
figure computed against the provisional areas is wrong rather than merely imprecise, and the
per-zone *ranking* changed too, not only the totals.

**The 250 m width caveat is now obsolete.** The outline is ACA's own 5 m polygons, so an
absolute km² is defensible. Expressing exposure as a fraction of a named zone is still
preferable, but for a different reason: ACA maps optically shallow reef only, so deeper
habitat inside a zone is unrepresented and an absolute "km² affected" understates the real
habitat at risk.

**Depth is now the weakest field, not the geometry.** The bathymetry is 50 m while the reef
strip is 20–50 m wide, so 39–100% of the cells under a zone read as land. `depth_land_cell_pct`
records that share and must be checked before any depth reaches a formula or a screen.
`R-02` is **NaN** — it contains no water cell at all — and must be handled explicitly, never
coerced to 0. R-03's −179.7 m rests on 2 cells over a 0.01 km² zone and should not be quoted.

**Habitat classes** are read off the live Earth Engine asset's own property tables and
re-verified on every build, not transcribed. Dominant class is computed **by area, not by
piece count**: polygonizing a raster yields one large patch plus a scatter of single-pixel
specks, and counting pieces let 25 rock specks outvote the coral patch that is the zone.

**QA figures**

| figure | claim it makes checkable |
|---|---|
| [reef_01_provisional_over_satellite.png](qa_screenshots/reef_01_provisional_over_satellite.png) | every zone is seaward of the visible shoreline. **Filename retains "provisional" for link stability — the figure now shows ACA geometry, and its caption states which file it was drawn from** |
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
| `habitat_class` | str | **Real ACA benthic class, as a readable name** (`Coral/Algae`, `Rock`, …). Dominant class **by area**, not by piece count |
| `habitat_class_code` | int | The raw ACA integer beside the name, so provenance back to the raster survives |
| `habitat_class_mix` | str | Full benthic composition as area percentages, e.g. `Coral/Algae:89%;Rock:11%` |
| `geomorphic_class`, `geomorphic_class_code` | str, int | ACA geomorphic band, same treatment |
| `sensitivity_weight` | float | **Still 1.0 placeholder for every zone** — ACA maps habitat, not sensitivity |
| `sensitivity_weight_status` | str | `PLACEHOLDER_PENDING_MARINE_SCIENTIST` — in the schema itself, not only the docs |
| `provisional` | bool | `False` |
| `geom_basis` | str | How the geometry was derived |
| `area_km2` | float | From UTM 36N, never degrees |
| `depth_median_m`, `depth_min_m` | float | Over **water cells only**; `NaN` where no water cell exists — see caveat |
| `depth_land_cell_pct` | float | Share of bathymetry cells under the zone that read as land. Carries the 50 m / 5 m resolution mismatch with the number instead of hiding it |
| `marine_park_overlap_pct` | float | **Real measured data**, recomputed for the ACA geometry |

**Zones** (north → south, total **1.24 km²**). Note this is *below* the published
~5–13 km² range for Jordan's reef, and the provisional figure of 5.69 km² sat inside
it — but the provisional number was the area of hand-drawn 250 m-wide boxes, not of
reef. 1.24 km² is what ACA actually maps as benthic habitat within 100 m of the
Jordanian chain. The published range covers a wider definition of reef area and
includes the deeper habitat ACA does not map (limitation 1).

| id | stretch | area km² | median depth m | land cells | dominant habitat | in Marine Park |
|---|---|---:|---:|---:|---|---:|
| R-01 | North Aqaba / Ayla & Public Beach | 0.46 | −7.4 | 39% | Coral/Algae 89% | 0% |
| R-02 | Port frontage / First Bay & Power Station | 0.04 | *n/a* | 100% | Coral/Algae 100% | 0% |
| R-03 | Tourist Camp / north Marine Park boundary | 0.01 | −179.7 | 0% | Coral/Algae 100% | 0% |
| R-04 | Marine Science Station / Cedar Pride | 0.15 | −44.0 | 19% | Coral/Algae 99% | **96.9%** |
| R-05 | Japanese Garden / Gorgonian | 0.07 | −17.4 | 0% | Coral/Algae 99% | **100%** |
| R-06 | Black Rock / Blue Coral | 0.19 | −6.4 | 52% | Coral/Algae 91% | **100%** |
| R-07 | Tala Bay / Seven Sisters | 0.13 | −14.9 | 75% | Rock 86% | **92.4%** |
| R-08 | Royal Diving Club / Yamanieh to Saudi border | 0.20 | −13.9 | 51% | Rock 66% | 10.3% |

**Independent validation, and it got stronger.** The Aqaba Marine Park boundary (from
OSM, `protect_class=4`, 3.45 km², spanning 29.397–29.460 N) was **never used as an
input to zone placement or to the ACA merge**. Against the hand-drawn boxes R-04–R-07
landed 67–85% inside it; against real ACA habitat they land **92–100%**. Independent
corroboration improving when the geometry is replaced by measured data is the
strongest evidence in this section. R-01–R-03 falling outside remains consistent with
city and port frontage.

**The dominant-habitat result also corroborates the placement.** Coral/Algae dominates
R-01–R-06 (the Marine Park stretch) and Rock dominates R-07–R-08. Nothing in the merge
knows where the park is.

**Two independent exports agree, and the wider one is the more complete.** The same ACA
asset was exported twice on 3 Aug — once over the download superset box (task
`HL3VYSAJRVN6TLKEAXR3CEH2`) and once over the marine AOI only
(`WJKEYOKSLGKFF2VSEIK5RWCD`), submitted in parallel because the wide one was slow and
the deadline was real. Compared over the 39,038,220 pixels they share:

| | |
|---|---|
| identical | 39,036,538 px — **99.9957%** |
| differing | 1,682 px (0.042 km², **3.4%** of the 1.24 km² used) |
| direction | **always** reef in the wide export and `Unmapped` in the narrow one; never the reverse |
| location | every differing pixel lies within 380 m of the *narrow* export's own boundary (median 140 m), on its south and west edges |

That one-directional, boundary-hugging pattern is a clip artefact in the narrower
request: Earth Engine loads fewer source tiles for a smaller region, so pixels near the
clip edge that need a neighbouring tile return `Unmapped`. Two independently submitted
exports matching to 4 decimal places across 39 M pixels is strong evidence the export
path is sound; the 3.4% shortfall is why `find_export()` **selects the widest available
GeoTIFF and prints which one it used and which it ignored**, rather than taking the
first of a sorted glob. Had the narrow file been chosen silently, every zone area would
have been up to 3.4% low with nothing to indicate it.

**What is trustworthy in this geometry, and what is not.** Both the outline *and* the
width are now measured: the geometry is ACA's own 5 m benthic polygons, so the flat
250 m width assumption that made the provisional `area_km2` order-of-magnitude only
is **gone**. What remains judgement is which zone a piece of reef belongs to:

- **Fragments are cut at zone boundaries, not assigned whole.** ACA polygonizes
  Aqaba's continuous fringing reef into a few very long shapes that run through
  several zones. Assigning each to the zone it overlapped *most* gave R-05 (Japanese
  Garden, a well-known reef) **475 m²** while 0.068 km² of reef sat inside its box,
  credited to R-04 and R-06 — which were in turn credited with reef outside theirs.
  No error and no missing data, just a wrong area per zone, which is exactly what the
  exposure engine consumes. An area-conservation assert now guards this.
- **Reef within 100 m of a zone but inside none is snapped to the nearest zone.** The
  boxes were hand-drawn outlines of dive sites and the reef strip runs past them:
  0.71 km² sits within 100 m of a box against 0.52 km² inside one. The eight zones are
  a contiguous chain 24–50 m apart (R-07/R-08 touch), so 15 pieces totalling 0.011 km²
  are near two zones and take the nearer — reported by the build, and asserted to
  occur only between *adjacent* zones. The tolerance is 100 m against >5 km to the
  nearest foreign reef, so it cannot reach across a border.
- **Dominant habitat is by area, not by piece count.** Polygonizing a raster yields one
  large patch plus a scatter of single-pixel specks; counting pieces let 25 rock specks
  outvote the coral patch that *is* the zone. R-08 reads `Rock:59 / Coral-Algae:47` by
  count — a meaningless near-tie — versus `Rock:66% / Coral-Algae:34%` by area.
- **Depth is now the weakest field, not the geometry.** The bathymetry is 50 m and the
  reef strip is 20–50 m wide, so 39–100% of the cells under a zone read as land.
  Depths are medians over water cells only; R-02 has no water cell at all and is
  reported `NaN`, never 0 and never the +10 m the raw cells would give. R-03's −179.7 m
  comes from just 2 cells over a 0.01 km² zone and should not be quoted. Use
  `depth_land_cell_pct` before trusting any depth here.
- **Class labels are read off the live Earth Engine asset**, not from documentation,
  and `export_aca.py verify-classes` re-checks them on every build. Guessing is a real
  trap: geomorphic `22` is *Reef Slope*, and the plausible guess (*Back Reef Slope*,
  which is `24`) would have mislabelled five of the eight zones with no error.

**Known limitations**

1. **Allen Coral Atlas maps shallow reef only**, so deeper habitat is unrepresented and
   the exposure model is silent about it. This is the main reason 1.24 km² sits below
   the published ~5–13 km² range.
2. **`sensitivity_weight` reflects team assumptions, not Atlas data and not
   scientific measurement**; assigning real weights is a Phase 2 item requiring
   marine-scientist input, and this must be said out loud on the slide because
   presenting invented weights as data is what loses credibility under questioning.
3. `marine_park_overlap_pct` is deliberately stored as a **raw measured percentage
   and not converted into a sensitivity weight**, because that conversion is the
   marine scientist's judgement call and inventing it from protection status would
   repeat the exact error limitation 2 warns about.
4. **R-01 and R-02 cover developed beach and port frontage** where reef presence was
   expected to be doubtful. ACA maps habitat in both, so per contract §2 no zone was
   dropped and all eight IDs survive. R-02 is now the smallest zone at 0.04 km² and
   R-03 at 0.01 km²; both are thin enough that per-zone exposure for them should be
   quoted with the area beside it.
5. R-08 is no longer the outlier it was — at 0.20 km² against a 0.14 km² median it is
   **1.4×** the median rather than 2.4×, so the case for splitting it has weakened.
   Splitting would still change the zone count and break the ID contract, so it stays
   a recommendation, not a unilateral change.
6. **`sensitivity_weight` did not become derivable when real habitat arrived.** It is
   still 1.0 everywhere. `habitat_class` and `marine_park_overlap_pct` are exactly the
   measured inputs a marine scientist needs in order to set it — handing them over is
   useful, converting them into a weight ourselves is the error limitation 2 names.

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
- Depth range −907.1 m to +1542.3 m; 23.3% of the bathymetry raster's own extent
  below sea level. Within `MARINE_AOI` specifically it is 41.29%, which is the figure
  to compare against WorldCover's 42.91% — see the cross-check in §1. The two extents
  differ, so the two percentages are not interchangeable.
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
| 5 | Culvert distances measured in **EPSG:3857** | every distance overstated by 14.8% | [osm_04](qa_screenshots/osm_04_culverts_all_numbered.png) now matches the report |

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
| Geographic extent used | **`TERRAIN_AOI` = 34.75–35.94 °E, 29.15–30.30 °N.** Was documented as 34.80–35.15 / 29.25–29.70 — that box was **retired on 2 Aug 2026** for cutting off ~85% of Wadi Yutum. Any file fetched before then covers the wrong area; see `scripts/check_aoi_coverage.py` |
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

## 1b. NASA GPM IMERG V07 — Daily Final (stage-1 screening)

The half-hourly product above is the one used for storm *intensity*. This daily one is
what made a 27.7-year search affordable: half-hourly IMERG for the whole record is
~455,000 Harmony requests, which is weeks of wall time. Daily is ~10,000, and it is only
ever used to **decide which days deserve half-hourly detail** — never to measure
intensity.

| Field | Value |
|---|---|
| Source organization | NASA / JAXA (GPM mission), distributed by NASA GES DISC |
| Dataset name | GPM IMERG Final Precipitation L3 **1 day** 0.1° |
| Product / version | `GPM_3IMERGDF`, version **07** |
| Collection concept ID | `C2723754864-GES_DISC` |
| Run type | **final** — gauge-adjusted, calibrated |
| Suitable for training | Yes, for daily totals only — `screening_only: true` in the registry |
| Access method | NASA Harmony spatial + variable subsetting (`harmony-py`), auth via `earthaccess` |
| Access date | 2026-08-02 (sweep manifest `generated_utc` 2026-08-02T18:08:36Z) |
| Registration required | Same as the half-hourly product — Earthdata account + *NASA GESDISC DATA ARCHIVE* approval |
| Licence / terms status | Accepted (EULA approved 2026-08-01) |
| Temporal resolution | 1 day (`granule_minutes: 1440`) |
| Period swept | **1998 → 2026**, 10,321 days expected |
| Spatial resolution | 0.1° (~11 km) |
| Geographic extent used | `TERRAIN_AOI` = 34.75–35.94 °E, 29.15–30.30 °N |
| Raw path | `data/raw/imerg/daily_final/` |
| Processed path | `data/processed/features/catchment_rainfall_daily.parquet`, `catchment_rainfall_climatology.parquet` |
| Manifest | `data/processed/events/daily_sweep_manifest.json` |
| Reproduce | `./scripts/run_daily_sweep.sh` → `python scripts/aggregate_daily_to_catchments.py` → `python scripts/build_event_catalogue.py` |
| Citation | https://gpm.nasa.gov/data/imerg |

**Completeness: 10,135 of 10,321 days = 98.2%.**

The 186 missing days are **contiguous — 2025-10-01 to 2026-04-04** — and every one of
them is after the last day the Final Run had been produced at the access date. This is
the product's ~3.5-month gauge-adjustment latency, not a gap in the sweep, which is why
the event catalogue records `search_scope_end_utc = 2025-09-30` rather than today's date.
Per the data rules the days are **reported and never interpolated**; the full list is in
the manifest.

| Variable | Internal name | Units | Notes |
|---|---|---|---|
| `precipitation` | `precipitation` | **mm/day** | **No `Grid/` prefix** — unlike the half-hourly product |
| derived | `precipitation_depth_mm` | mm | `rate × interval_hours / rate_period_hours`, i.e. × 1 for a daily granule |

**The units trap.** Daily is **mm/day** and half-hourly is **mm/hr**, and the daily
variable has **no `Grid/` prefix**. Applying the half-hourly convention to daily data
understates depth by **48×** and raises no error — the numbers just come out small and
plausible. Both the variable name and the rate period come from `IMERG_PRODUCTS` in
`backend/src/ingestion/imerg.py`; neither is ever written as a literal.

**Limitations.**

1. **A daily total cannot rank a flash flood.** Aqaba's damaging events are short,
   intense bursts; two storms with the same daily total can differ severalfold in peak
   3-hour intensity. That is the entire reason stage 2 exists, and it is measurable —
   re-ranking the catalogue by peak 3-hour intensity moved the demo event from 14th to
   **8th**. Stage 1 output is a *candidate list*, never a severity ranking.
2. The generous top-N (≥100) is the mitigation for exactly that under-ranking.
3. ~11 km cells smooth localized convective storms — inherited from the product, same as
   the half-hourly run.

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

### The cross-event table, and the target definition

`scripts/extract_event_antecedents.py` rolls the per-event files into one table at
`data/processed/features/event_antecedents.parquet`, one row per (event × catchment),
with the two ERA5 runoff targets prefixed `label_`.

| | |
|---|---|
| Rows / events | **395 rows, 79 events** (as of 2026-08-03) |
| Events skipped | 21 — their ERA5 month has not downloaded yet; the sweep is at 74 of 84 months |
| Label columns | `label_surface_runoff_mm`, `label_subsurface_runoff_mm` |
| Label window | 24 h from the event hour |
| Distribution | published in `event_antecedents.summary.json` under `label_distribution` |

**Do not binarise the label at `> 0`.** The candidates are already the top ~1% of days by
rainfall, so nearly every one produces *some* ERA5 runoff: **98% of rows are positive at a
zero threshold.** A model predicting "runoff" always would score ~98% and have learned
nothing — the same tautology the label rule exists to prevent, reached from the other
direction, and it would present as a good result rather than as a bug.

The **magnitude** is what discriminates. It spans four orders of magnitude, and within a
single catchment the maximum is ~19× the median:

| percentile | mm | binary balance if used as threshold |
|---|---:|---:|
| p10 | 0.00014 | — |
| p50 | 0.00584 | **50% positive** |
| p75 | 0.01624 | 25% positive |
| p90 | 0.03897 | 10% positive |
| p99 | 0.13343 | — |

So the usable formulations are regression on the value (log scale) or a binary split at a
candidate-set percentile. Whichever is chosen, **the threshold is a modelling decision and
belongs in the model card**, not buried in a script.

**Leakage warning.** Per-catchment median runoff orders monotonically with catchment area
— AQ-C01 0.0104 mm (4,453 km²) descending to AQ-C05 0.0047 mm. Combined with static
features that are constant per catchment, random CV will memorise catchment identity and
report a meaningless score. This is the concrete reason **leave-one-catchment-out *and* a
temporal holdout are both mandatory**, not merely advisable.

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
Engine login needed. Search box: `ANALYSIS_BBOX` (`scripts/pulga_config.py`).

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
- **Phase 5, B6 — `forecast_anomalies` added (2026-08-07).** A new derived table, not an
  external product — no new source row needed, but noted here for the same reason
  `forecast_exceedance` is: every number on the dashboard traces to a file. Scores each
  GEFS run's ensemble-mean 24h rainfall against `catchment_rainfall_climatology`'s real
  percentiles (`p50`/`p99`/`p99_9`) — a **percentile-relative score, not a z-score**,
  because the climatology artifact only has percentiles, not a mean/std or the daily
  series. See `backend/src/processing/anomaly_detection.py` for the formula and
  `supabase/migrations/20260807120000_forecast_anomalies.sql` for the schema. Exposed via
  `GET /api/v1/forecast/latest`'s `anomalies` + `anomaly_caveat` fields. Explicit
  limitation, stated here and in every API response: this is a statistical outlier signal
  against ~27 years of climatology, never validated against a real flood event's lead
  time — not a working early-warning system.


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

---

# AMENDMENT — 2 August 2026 · AOI v2 re-pull and the Phase-2 backend

Appended rather than merged into the sections above, so the record shows what was
corrected and when. A project that visibly catches and fixes its own AOI bug is
more credible than one that never mentions it had one.

## Why every land-side source was re-pulled

The original download box was `34.80, 29.25, 35.15, 29.70`. It covered **~11.5% of
the terrain area the project actually needs**. Wadi Yutum drains from about 90 km
inland, out to 35.94 E and 30.30 N, so the old box cut off most of `AQ-C01` — the
catchment that is 4,453 of the basin's 4,656 km².

This was a **coverage** failure, not a data-quality one. Every download succeeded.
Nothing raised. The numbers were simply taken over the wrong ground, which is the
exact failure mode this project's standing law #1 exists to catch.

Measured evidence, saved before anything was re-fetched:
[aoi_coverage_report_20260802.txt](aoi_coverage_report_20260802.txt) — 19 files
short at the start, 7 at the end, with each remaining one explained in the
report's own interpretation section.

## What changed, per source

| Source | v1 | v2 | Access date |
|---|---|---|---|
| ESA WorldCover | 1 tile (`N27E033`), 4200×5400 px | **2 tiles mosaicked** (`N27E033` + `N30E033`), 14280×13800 px | 2026-08-02 |
| ISRIC SoilGrids | 188×155 cells | **481×526 cells** | 2026-08-02 |
| OpenStreetMap | clipped to old box; 3,845 roads / 200 drainage / 27 culverts | **clipped to `terrain_aoi.geojson`; 8,289 roads / 1,402 drainage / 46 culverts** | 2026-08-02 |
| Bathymetry / coastline / reef zones | — | **NOT re-pulled** — `MARINE_AOI` is unchanged between contract v1 and v2 | 2026-08-01 |

Required WorldCover tiles are now **derived from the AOI** in
`process_worldcover.required_tiles()` rather than hardcoded. A hardcoded list is
how v1's northern edge went missing in the first place, and a future AOI change
would have repeated it silently.

**New failure mode introduced by v2, and checked:** two ESA tiles can carry
different processing dates. Measured discontinuity in bare-ground fraction across
the 30°N seam is **0.01 percentage points** — ordinary terrain variation, not a
version mismatch. No blending was applied.
→ [worldcover_06_v2_mosaic_seam_check.png](qa_screenshots/worldcover_06_v2_mosaic_seam_check.png)

## Re-verified against the real 5-catchment set

The three feature tables now sit at the contract paths, built from
`catchments.gpkg`, and the local test fixture has been deleted.

Catchment areas cross-checked against the geometry contract — **all five within
0.1%**, total 4,656.1 km² against the contract's 4,656 km²:

| id | contract km² | computed km² | diff |
|---|---:|---:|---:|
| AQ-C01 | 4,453.1 | 4,453.1 | 0.00% |
| AQ-C02 | 64.9 | 64.9 | 0.07% |
| AQ-C03 | 59.9 | 59.9 | 0.01% |
| AQ-C04 | 42.7 | 42.7 | 0.07% |
| AQ-C05 | 35.6 | 35.6 | 0.10% |

**Bare-ground sanity check on the number that matters.** `AQ-C01` is
**98.64% bare/sparse ground over 4,453 km²** — 95.6% of the basin. This is a far
stronger test than v1's, which measured a fraction of one small-box catchment.
→ [worldcover_07_aq_c01_bareground_v2.png](qa_screenshots/worldcover_07_aq_c01_bareground_v2.png)

Land composition over the full terrain AOI (18,863 km² of land, 95.7% of the box):
bare/sparse 97.82%, grassland 0.68%, cropland 0.55%, built-up 0.73%, tree 0.13%.

## Phase-2 backend — what the API asserts about its own numbers

| Artifact | Evidence |
|---|---|
| Exposure `formula_terms` stored on every run | [phase2_01_formula_terms_table.png](qa_screenshots/phase2_01_formula_terms_table.png) |
| `/explain` alters no number, EN and AR | [phase2_02_explain_number_fidelity.png](qa_screenshots/phase2_02_explain_number_fidelity.png) |
| `/ask` citation coverage, incl. refusals | [phase2_03_ask_citation_coverage.png](qa_screenshots/phase2_03_ask_citation_coverage.png) |
| 19 caveats verified to reach a payload | [phase2_04_caveat_coverage_matrix.png](qa_screenshots/phase2_04_caveat_coverage_matrix.png) |
| Endpoint status, stubs labelled | [phase2_05_endpoint_status.png](qa_screenshots/phase2_05_endpoint_status.png) |

**Every area and distance in the exposure engine is computed in EPSG:32636**, and
`_assert_measure_crs` refuses any other frame. `measure_crs` is recorded in every
`formula_terms` row so the guarantee is auditable from stored data, not just from
reading the code.

**Risk bands** (0–20 minimal … 80–100 critical) are a reasonable default, **not
validated policy**. Operational thresholds require marine-scientist input, and the
band caveat travels on every exposure and alert response.

`risk_score = product × 100`, and the ×100 is recorded as `score_scale` in
`formula_terms`. No exponent or curve is applied: every factor is already
dimensionless on [0,1], so the product is on [0,1] and ×100 maps it onto the band
table with no further reshaping. Any curve invented here would change the ranking
between zones while looking like a presentation detail.

## Scenario engine parameters (`rainfall_multiplier`, `transmission_loss_override`) — Phase 5, A3.4

The what-if backend contract, documented fully now that both fields are echoed
consistently on every response that applies them.

| Field | Type | Bounds | Applies to | Echoed in |
|---|---|---|---|---|
| `rainfall_multiplier` | float | `[0.5, 2.0]`, default `1.0` | `RunoffRequest`, `ExposureRequest` | `RunoffPrediction.rainfall_multiplier` (structured); `ExposureResult.formula_terms["relative_sediment_intensity_source"]` (string suffix, only when ≠1.0) |
| `transmission_loss_override` | float\|None | `[0.20, 0.85]`, default `None` | `RunoffRequest`, `ExposureRequest` | `RunoffPrediction.transmission_loss` (structured); `ExposureResult.formula_terms["transmission_loss"]` (structured — **fixed in Phase 5**, previously dropped silently) |

**The Phase 5 fix:** `exposure_calculate` was applying `transmission_loss_override`
to the real feature row (it reached `predict_one()` correctly) but never surfaced
the value anywhere in the response — the only way to know what transmission loss
was actually used was to call `/runoff/predict` separately and hope the two agreed.
`main.py::exposure_calculate` now reads `real.get("transmission_loss")` (or
`pred.transmission_loss` on the no-training-row fallback path) into
`formula_terms["transmission_loss"]`, mirroring exactly what `runoff_predict`
already did. No schema migration was needed — `formula_terms` is stored as an
unstructured JSON blob precisely so a new term never needs one
(`exposure/store.py`'s own documented rationale).

Only the four raw rainfall-**depth** columns are scaled by `rainfall_multiplier`
(`RAINFALL_MM_COLUMNS` in `main.py`: `precipitation_mm_day`, `precip_prior_1d_mm`,
`precip_prior_3d_mm`, `precip_prior_7d_mm`) — never the percentile-rank features,
since "150% of the 90th percentile" is not a meaningful operation. Both fields are
part of the exposure TTL-cache key (`da.TTLCache.key(...)`), so two different
scenario requests for the same event/outlet never collide on a stale cached result.

## `candidate_sites`, `generated_reports`, `sampling_feedback`, `reef_zone_photos` — Phase 5 new artifacts

Four new SQLite-backed tables, added for Phase 5's B4/B5/B7/B8 features. Each
follows `exposure/store.py`'s existing pattern exactly: its own SQLite file under
`data/outputs/`, an env-var override for tests, a `_conn()` contextmanager that
runs `CREATE TABLE IF NOT EXISTS` on every connect, and schema-fluid JSON-blob
columns for anything that will grow new terms over time — the same reasoning
`exposure_runs`/`exposure_results` already use for `formula_terms`.

| Table | File | ID prefix | Purpose |
|---|---|---|---|
| `candidate_sites` | `data/outputs/candidate_sites.sqlite` | `site_{ULID}` | B4 — every auto-scored coastline, browsable |
| `generated_reports` | `data/outputs/generated_reports.sqlite` | `report_{ULID}` | B5 — draft/reviewed forensic reports, `status` never self-upgrades |
| `sampling_feedback` | `data/outputs/sampling_feedback.sqlite` | `feedback_{ULID}` | B7 — logged sampling outcomes vs. predictions |
| `reef_zone_photos` | `data/outputs/reef_zone_photos.sqlite` | `photo_{ULID}` | B8 — uploaded photo classifications; image bytes live under `data/raw/reef_photos/`, git-ignored |

**None of these four new prefixes reuse or resemble the five frozen ID schemes**
in `tasks/00-contracts.md` §2 (`AQ-C`, `AQ-O`, `R-`, `AQ-YYYY-MM-DD`, `sim_{ULID}`)
— a candidate site, a report, a feedback row, and a photo are never Aqaba
catchment/outlet/reef-zone/event/simulation entities, so none of them squat an
`AQ-*` ID. `tests/test_site_id_contract.py` is the matching static guard for
`site_{ULID}`, mirroring `tests/test_run_id_contract.py`'s existing enforcement of
`sim_{ULID}` — the same "new frozen convention gets a scanning guard" pattern this
project already uses for the spatial contract.

The shared ULID generator moved to `backend/src/lib/ulid.py` in the same pass
(extracted from `exposure/store.py::_new_ulid`, which now imports it) so these four
new tables and the original `exposure_runs` table all mint IDs identically instead
of four copies of the same ~15 lines.

**`reef_zone_photos.sqlite` also carries two more tables:**

- **`sensitivity_weight_approvals`** (`approval_id`, `reef_zone_id`, `approved_at`,
  `reviewer`, `reasoning`, `proposed_value`, `approved_value`) — a permanent log of
  every time a human has moved `sensitivity_weight` off the
  `PLACEHOLDER_PENDING_MARINE_SCIENTIST` default (`tasks/00-contracts.md` §5, swap-in
  #5).
- **`sensitivity_weight_overrides`** (`reef_zone_id`, `value`, `updated_at`) — the
  live override itself, one row per zone, latest wins.

`POST /api/v1/reef-zones/{id}/sensitivity-weight/approve` is the **only** code path
anywhere that writes to either table, and the only code path anywhere that calls
`data_access.clear_all_caches()` for this field — B8's photo-upload endpoint computes
a `proposed_sensitivity_weight` from accumulated classifications into a wholly
separate response field, and never touches either table or the cache at all
(Standing Law rule 13: propose, never auto-overwrite).

**The override is a read-time overlay, never a `reef_zones.gpkg` rewrite** —
`data_access.py::reef_zones()` applies `all_overrides()` on top of the base geometry
on every call. Found while wiring `approve` against the real deployed container, not
assumed: `./data` is mounted **read-only** there (same class of bug this project
already hit once for `exposure_runs.sqlite`), so a direct `.gpkg` write would have
worked on a developer's machine and failed in production. Confirmed via SHA-256 hash
that the base file is byte-for-byte unchanged before and after an approval.

**The override is also genuinely live in the exposure formula, not just on
`/reef-zones`'s display.** `exposure_calculate` used to pass
`engine.HABITAT_SENSITIVITY_PLACEHOLDER` (the constant) into
`engine.summarise_zone()` unconditionally — an approval changed what `/reef-zones`
showed but never once entered a real `risk_score`. Fixed: the same real per-zone
value (override included) that `/reef-zones` displays now feeds the formula
directly, verified end to end against the running container — approving a zone's
weight moves its `risk_score` by exactly that factor on the next
`/exposure/calculate` call.

**B7's `adjusted_priority` is additive, not a formula change.**
`ExposureResult.risk_score` is unchanged — the exact same product
`exposure/engine.py::calculate_exposure()` has always computed.
`adjusted_priority` is a second, separate field that equals `risk_score` exactly
(`adjusted_priority_status: "NO_FEEDBACK_YET"`) until
`sampling_feedback.MIN_FEEDBACK_FOR_ADJUSTMENT` (5) real logged outcomes exist for
that zone, at which point it becomes `risk_score × historical_accuracy` — bounded
to `[0, risk_score]`, so feedback can only ever dampen the score, never inflate it
past what the model itself computed.

## Bugs caught in Phase 2 (continuing the Phase-1 count)

| # | Bug | Silent failure it would have caused |
|---|---|---|
| 6 | `/explain` rendered `0.0725 × 100` as `7.249999999999999%` | An IEEE754 artefact on screen, unfixable by rounding because rounding is forbidden — solved with an exact decimal shift |
| 7 | Number-fidelity check used substring matching | `72` → `72.4` passed undetected; a number could be *extended* without failing the audit |
| 8 | `/ask` answered an out-of-corpus question with a real citation | "airspeed **velocity**" matched a chunk about ocean current velocity — cited, but not responsive |
| 9 | `/alerts` read the newest run, not the requested scenario | A cached exposure response writes no new run, so alerts could describe a different outlet than the user asked about |
| 10 | Catchment-area caveat cited the wrong file | The ±4% figure lives in this dictionary, not `00-contracts.md §2` — a caveat pointing at a file that lacks the claim |

Bugs 6–9 were found **by writing the test or building the artifact**, not by
reading the code — the same pattern as Phase 1's bugs 4 and 5.
