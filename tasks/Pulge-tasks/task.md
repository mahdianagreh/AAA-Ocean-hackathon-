# Pulga — Tasks Tracker

**Last updated:** 2026-08-01 (phase 2: scale + visual verification)

- Reproduce from zero: [docs/README_pulga.md](../../docs/README_pulga.md)
- Provenance & limitations: [docs/data_dictionary.md](../../docs/data_dictionary.md)
- **All 34 QA figures, captioned:** [docs/qa_screenshots/MANIFEST.md](../../docs/qa_screenshots/MANIFEST.md)
- Judge-facing honesty page: [docs/pitch_limitations.md](../../docs/pitch_limitations.md)

Legend: `[x]` done, with linked visual evidence · `[~]` done but blocked on someone
else for the final input · `[ ]` needs a human

> **Phase-2 rule:** an item is not complete without a linked figure. 34 figures,
> 34 manifested, 0 unmanifested.

---

## Environment Setup

- [x] Core geospatial stack in `.venv/` — `fiona` skipped (pyogrio), `osmium` skipped
      (GDAL's OSM driver reads `.osm.pbf` directly)
- [x] `contextily` added this phase → Esri WorldImagery basemaps for satellite QA
- [x] Earth Engine API installed (1.7.37)
- [ ] **Authenticate Earth Engine — NEEDS YOU.** `ee.Authenticate()` requires a browser
      OAuth flow plus a GEE project under your own account (contract §4 P6). Cannot be
      done from a script. Verified blocked: no credentials at `~/.config/earthengine/`,
      `ee.Initialize()` raises. ~10 min at https://code.earthengine.google.com
- [x] Directory structure per contract §3

## Day 1 Critical Path

- [x] AOI boxes — padded + contract analysis box, `assert analysis ⊆ download`
- [x] `reef_zones_PROVISIONAL.gpkg` — R-01–R-08, 5.69 km², anchored to the real water
      mask → [reef_01](../../docs/qa_screenshots/reef_01_provisional_over_satellite.png),
      [reef_02](../../docs/qa_screenshots/reef_02_per_zone_insets.png)
- [~] Mahdi's `catchments_PROVISIONAL.gpkg` — still not published. Not blocking:
      pipeline verified against a quarantined fixture
- [ ] Register own Earth Engine project — see above
- [x] All raw downloads complete

## Chain 1 — Land

| Task | Status | Evidence |
|---|---|---|
| WorldCover raw tile covers AOI | done | [worldcover_01](../../docs/qa_screenshots/worldcover_01_raw_tile_before_clip.png) |
| WorldCover clipped to AOI | done | [worldcover_02](../../docs/qa_screenshots/worldcover_02_clipped_to_aoi.png) |
| Zonal boundaries over raster | done | [worldcover_03](../../docs/qa_screenshots/worldcover_03_catchment_boundaries_overlay.png) |
| Class fractions per catchment | done | [worldcover_04](../../docs/qa_screenshots/worldcover_04_class_fractions_by_catchment.png) |
| **Bare-ground sanity check: 95.3% of land** | **PASSED** | [worldcover_05](../../docs/qa_screenshots/worldcover_05_bareground_sanity_annotated.png) — 74% and 50% thresholds annotated on the image |
| SoilGrids 6 variables individually | done | [soilgrids_01–06](../../docs/qa_screenshots/soilgrids_01_clay_both_depths.png) |
| Texture closure physically sensible | done | [soilgrids_07](../../docs/qa_screenshots/soilgrids_07_texture_triangle_by_catchment.png) — ternary plot |
| Unit conversion before/after | done | [soilgrids_08](../../docs/qa_screenshots/soilgrids_08_unit_conversion_before_after.png) |
| **Within-catchment variance (new)** | done | [soilgrids_09](../../docs/qa_screenshots/soilgrids_09_within_catchment_variance.png) — mean/σ/min/max, 73 columns |
| SoilGrids unit tests | **21/21 pass** | texture median exactly 100.00 |
| OSM roads on satellite | done | [osm_01](../../docs/qa_screenshots/osm_01_roads_over_satellite.png) |
| OSM buildings on satellite | done | [osm_02](../../docs/qa_screenshots/osm_02_buildings_over_satellite.png) |
| OSM drainage on satellite | done | [osm_03](../../docs/qa_screenshots/osm_03_waterways_drainage_over_satellite.png) |
| **All 27 culverts numbered** | done | [osm_04](../../docs/qa_screenshots/osm_04_culverts_all_27_numbered.png) |
| **Top-5 culvert insets** | done | [osm_05](../../docs/qa_screenshots/osm_05_culvert_top5_insets.png) — road embankments visible |
| **Dive POIs + Marine Park (new)** | done | [osm_06](../../docs/qa_screenshots/osm_06_dive_poi_and_marine_park.png) |
| Road density choropleth | done | [urban_01](../../docs/qa_screenshots/urban_01_road_density_choropleth.png) |
| Built-up fraction choropleth | done | [urban_02](../../docs/qa_screenshots/urban_02_builtup_fraction_choropleth.png) |
| Per-catchment feature tables | **blocked on Mahdi** | pipeline verified on fixture, outputs quarantined |
| OSM-vs-DEM conflict doc §1–3 | done, final | [osm_dem_conflicts.md](../../docs/osm_dem_conflicts.md) |
| OSM-vs-DEM conflict doc §4 | **blocked on Mahdi's `flow_paths.gpkg`** | auto-runs when the file appears |

**OSM expanded 6 → 12 layers this phase:** + dive_tourism_poi (75), tourism_areas
(208), protected_areas (2), osm_coastline (11), infrastructure_lines (251),
water_bodies (49).

## Chain 2 — Marine

| Task | Status | Evidence |
|---|---|---|
| Provisional reef zones on satellite | done | [reef_01](../../docs/qa_screenshots/reef_01_provisional_over_satellite.png) |
| Per-zone detail insets | done | [reef_02](../../docs/qa_screenshots/reef_02_per_zone_insets.png) |
| **R-04/R-05 overlap bug: 1.46 ha → 0 m²** | **FIXED, proven** | [reef_03](../../docs/qa_screenshots/reef_03_overlap_bug_before_after.png) |
| **Marine Park independent validation** | done | [reef_04](../../docs/qa_screenshots/reef_04_marine_park_validation.png) — R-04–R-07 are 67–85% inside a park never used as an input |
| `sensitivity_weight` labelled placeholder | done | in the file schema (`sensitivity_weight_status`), not just docs |
| Depth field + isobaths | done | [depth_01](../../docs/qa_screenshots/depth_01_full_field_and_isobaths.png) |
| **Sign convention: 22/22 control points** | **PASSED** | [depth_02](../../docs/qa_screenshots/depth_02_sign_convention_22_control_points.png) — expanded from 5 |
| **Nodata bug: 1917 NaN → 0** | **FIXED, proven** | [depth_03](../../docs/qa_screenshots/depth_03_nodata_bug_before_after.png) |
| Across-shore profiles per zone | done | [depth_04](../../docs/qa_screenshots/depth_04_crossshore_profiles_per_zone.png) — why width is an assumption |
| Coastline single sea body | done | [coastline_01](../../docs/qa_screenshots/coastline_01_single_sea_body.png) |
| **GMRT substitution justified vs OSM** | done | [coastline_02](../../docs/qa_screenshots/coastline_02_osm_vs_gmrt_agreement.png) — median 62 m, p90 337 m |
| Allen Coral Atlas export | **BLOCKED on EE auth** | `export_aca.py` written, fails cleanly, ID-continuity asserts included. No figure faked. |
| Provisional-vs-final ID diff | **runs at swap** | `verify_against_provisional()` asserts no new IDs, no centroid drift > 5 km |

## Cross-cutting

- [x] **Master composite map** →
      [overview_01](../../docs/qa_screenshots/overview_01_master_all_layers.png) — pitch-deck ready
- [x] **Data lineage diagram** →
      [overview_02](../../docs/qa_screenshots/overview_02_data_lineage_diagram.png) — GMRT substitution
      drawn in so nobody "corrects" it back to a broken GEBCO call
- [x] `data_dictionary.md` — every limitation as a full sentence, every figure linked
- [x] `README_pulga.md` — from-zero walkthrough, dependency graph, gotchas table
- [x] `pitch_limitations.md` — judge-ready, not internal-notes language
- [x] Full clean rebuild verified: all derived outputs deleted and regenerated,
      identical results, 34/34 figures manifested

## Target files

| file | status |
|---|---|
| `data/raw/osm/jordan-latest.osm.pbf` | done, 30 MB |
| `data/raw/bathymetry/gebco_aqaba.tif` | **ships as `gmrt_aqaba.tif`** — GEBCO unobtainable, substitution documented and quantified |
| `data/processed/vectors/osm_aqaba.gpkg` | done, **12 layers** |
| `data/processed/vectors/coastline.gpkg` | done, 1 sea body 397.3 km² |
| `data/processed/bathymetry/depth_utm36n.tif` | done, 50 m UTM 36N |
| `data/processed/vectors/reef_zones.gpkg` | **`_PROVISIONAL` only** — blocked on EE auth |
| `data/processed/features/landcover_by_catchment.parquet` | blocked on Mahdi |
| `data/processed/features/soil_by_catchment.parquet` | blocked on Mahdi |

Beyond the brief: `urban_by_catchment.parquet` (10 cols), `aca_fragments_BEFORE_MERGE.gpkg`
(on ACA build), `pitch_limitations.md`, 34 QA figures.

## Bugs caught (5 — each with evidence)

| # | bug | silent failure it would have caused | evidence |
|---|---|---|---|
| 1 | Reef zones R-03–R-05 on dry land | exposure scores for land | reef_01 + depth assert |
| 2 | Mixed NaN / −32768 nodata | NaN particle positions, no exception | depth_03 |
| 3 | Undeclared 0-nodata in SoilGrids | coastal soil means dragged to zero | soilgrids_08 + 21 tests |
| 4 | 1.46 ha R-04/R-05 overlap | reef area double-counted | reef_03 |
| 5 | **Culvert distances in EPSG:3857** | every distance 14.8% too large | osm_04 now matches the report |

Bugs 4 and 5 were found **by building the figure**, not by reading code — which is the
argument for the phase-2 rule.

## The two things that still need a human

1. **Earth Engine auth** (~10 min, browser) → unblocks the real ACA export.
2. **Mahdi publishes `catchments_PROVISIONAL.gpkg`** → three feature tables land with
   one command, plus `flow_paths.gpkg` completes the conflict doc §4.
