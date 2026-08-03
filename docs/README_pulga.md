# Workstream A+B — reproduce everything from zero

**Owner:** Pulga · land cover, soil, urban, marine habitat, bathymetry

- Provenance, licences, limitations: [data_dictionary.md](data_dictionary.md)
- All 42 QA figures with captions: [qa_screenshots/MANIFEST.md](qa_screenshots/MANIFEST.md)
- Judge-facing honesty page: [pitch_limitations.md](pitch_limitations.md)
- Handoff to the terrain lead: [osm_dem_conflicts.md](osm_dem_conflicts.md)
- Visual provenance map: [overview_02_data_lineage_diagram.png](qa_screenshots/overview_02_data_lineage_diagram.png)

> **Standing rule.** Processing scripts **assert**; QA scripts **visualise**. Each
> figure has exactly one owner so two scripts cannot drift into two different
> pictures of the same claim. If a step has no figure, it is not verified.

---

## 0. If you had to reproduce this from an empty repo

Assume you have nothing but a clone: no `.venv/`, no `data/`, no figures. This is the
complete path to every deliverable. Total wall time is roughly 20 minutes, most of it
the 30 MB OSM download.

### 0.1 System prerequisites

```bash
python3 --version          # 3.14 here; 3.11+ is fine
ogr2ogr --version          # GDAL CLI, used for the OSM extract
```

GDAL comes from Homebrew (`brew install gdal`) or your package manager. **You do not
need `osmium`** — GDAL's OSM driver reads `.osm.pbf` directly and `-clipsrc` does the
AOI clip in the same pass.

### 0.2 Environment

The system Python here is Homebrew's and is externally managed, so a venv is
mandatory — a bare `pip install` will refuse.

```bash
cd <repo root>
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install shapely pyproj geopandas rasterio rioxarray \
    pyarrow rasterstats requests matplotlib contextily earthengine-api
```

Notes on deliberate choices:
- **`fiona` is intentionally absent.** geopandas 1.1 uses `pyogrio` by default and
  reads/writes GeoPackage fine.
- **`contextily`** supplies Esri WorldImagery basemaps for the satellite QA figures.
  Without network access those figures still render, just without imagery.

### 0.3 Directory skeleton

```bash
mkdir -p data/aoi data/raw/{osm,bathymetry,worldcover,soilgrids,aoi,aca} \
         data/interim data/processed/{features,vectors,bathymetry,dem,events,plume} \
         data/outputs docs/qa_screenshots notebooks scripts tests
```

### 0.4 Raw downloads

Three of the four are scripted. Run from the repo root:

```bash
# OSM — Jordan extract, 30 MB
curl -sL --fail -o data/raw/osm/jordan-latest.osm.pbf \
  https://download.geofabrik.de/asia/jordan-latest.osm.pbf

# ESA WorldCover — one 3x3 degree tile covers the whole AOI
curl -sL --fail -o data/raw/worldcover/ESA_WorldCover_10m_2021_v200_N27E033_Map.tif \
  https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N27E033_Map.tif

# Bathymetry — see the GEBCO section below before "fixing" this URL
curl -sL --fail -o data/raw/bathymetry/gmrt_aqaba.tif \
  "https://www.gmrt.org/services/GridServer?minlongitude=34.80&maxlongitude=35.15&minlatitude=29.25&maxlatitude=29.70&format=geotiff&resolution=max&layer=topo"

# SoilGrids — 12 rasters via WCS
cd scripts && ../.venv/bin/python download_soilgrids.py && cd ..
```

### 0.5 STOP — read this before you "fix" the bathymetry URL

**GEBCO is unobtainable programmatically. This is not an oversight and the GMRT URL
above is not a bug.** Verified failures, all re-testable:

| route | result |
|---|---|
| `wcs.gebco.net/2024/service?request=GetCapabilities` | empty response |
| `download.gebco.net` POST | HTTP 405, method not allowed |
| `bodc.ac.uk/.../gebco_2024/geotiff/<tile>.tif` | HTTP 404 |
| `wms.gebco.net` with `format=image/tiff` | returns a **rendered RGB image**, not elevation values — unusable as a depth field |

GEBCO's portal is an interactive web form. We therefore ship **GMRT**, a synthesis
whose deep-water source in this region is GEBCO, cross-validated two ways (NOAA NCEI
agrees on the basin minimum to 0.2 m; the derived coastline agrees with OSM's
independent coastline to a 62 m median).

**If you obtain the canonical grid by hand**, save it as
`data/raw/bathymetry/gebco_aqaba.tif`. `process_bathymetry.resolve_source()` prefers
it automatically and **nothing else changes**. Do not rename the GMRT file to
`gebco_*` — mislabelling provenance is the exact failure the contract exists to
prevent.

### 0.6 Build, in dependency order

Scripts import `pulga_config.py` as a sibling module, so run them from `scripts/`.

```bash
cd scripts

# 1. Spatial contract — first, everything clips against these
../.venv/bin/python make_aoi.py

# 2. Bathymetry — MUST precede reef zones, which anchor to its water mask
../.venv/bin/python process_bathymetry.py

# 3. Land sources
../.venv/bin/python process_worldcover.py
./extract_osm.sh                      # self-locates; run from anywhere

# 4. Marine deliverable (needs 2 and 3: water mask + Marine Park boundary)
../.venv/bin/python make_reef_zones_provisional.py

# 5. Verify SoilGrids unit conversion — 21 checks (from the repo root)
cd .. && .venv/bin/python tests/test_soilgrids_units.py && cd scripts

# 6. Per-catchment features. See §2 on the catchments blocker.
../.venv/bin/python make_catchments_fixture.py     # only while Mahdi's are pending
../.venv/bin/python aggregate_catchments.py

# 7. All 42 QA figures + the manifest
../.venv/bin/python qa_land.py
../.venv/bin/python qa_marine.py
../.venv/bin/python qa_overview.py
../.venv/bin/python qa_common.py                   # regenerates MANIFEST.md

# 8. Handoff document for the terrain lead
../.venv/bin/python osm_drainage_report.py
```

### 0.7 Confirm you got what we got

| check | expected |
|---|---|
| WorldCover bare/sparse ground | **97.82%** of land, 93.63% of AOI |
| SoilGrids unit tests | **21/21 pass**, texture median exactly 100.00 |
| OSM layers | **12**, incl. 46 culverts and 6 protected areas |
| Depth field | min **−907.1 m**, max **+1542.3 m**, 23.3% below sea level |
| Sign-convention controls | **22/22 pass** |
| Coastline | **1** water polygon, **397.3 km²** |
| Reef zones | **8**, total **5.69 km²**, all median depth < 0 |
| Coastline vs OSM | median **62 m**, p90 337 m |
| QA figures | **34** in `docs/qa_screenshots/manifest.json` |

Any mismatch means something upstream changed — check the data dictionary's access
dates before assuming the code is wrong. OSM in particular is a live database.

---

## 1. Dependency graph

```
make_aoi ──> process_worldcover ─┐
         ├─> download_soilgrids ─┤
         ├─> extract_osm ────────┼──> aggregate_catchments ──> runoff model (Mahdi)
         │        │              │            ▲
         │        │ Marine Park  │            │ catchments (Mahdi, PENDING)
         │        ▼              │
process_bathymetry ─────────────┘
   ├──> depth_utm36n.tif + coastline.gpkg ──> particle engine (Nizar)
   └──> make_reef_zones_provisional ────────> exposure engine + dashboard
                  ▲
        export_aca.py (BLOCKED: Earth Engine browser auth)
```

Rendered version: [overview_02_data_lineage_diagram.png](qa_screenshots/overview_02_data_lineage_diagram.png).

---

## 2. What is blocked, and on whom

| Item | Blocked on | Status |
|---|---|---|
| `landcover_by_catchment.parquet` | Mahdi — `catchments_PROVISIONAL.gpkg` (contract §4 P1) | Pipeline verified against a labelled fixture; outputs quarantined to `data/interim/*_FIXTURE.parquet` |
| `soil_by_catchment.parquet` | same | same, 73 columns |
| `urban_by_catchment.parquet` | same | same, 10 columns |
| `osm_dem_conflicts.md` §4 | Mahdi — `flow_paths.gpkg` | §1–3 complete and final; §4 auto-runs when the file appears |
| `reef_zones.gpkg` (real) | **You** — Earth Engine browser auth | `export_aca.py` ready; provisional carries the final schema |

Nothing else waits on anyone.

**Fixture safety.** `aggregate_catchments.py` resolves catchments in the order
real → provisional → fixture. In fixture mode it writes to `data/interim/` with a
`_FIXTURE` suffix and **refuses to write the contract feature paths**, so fixture
numbers cannot reach the runoff model or the demo by accident. Every figure derived
from the fixture carries a warning burned into the image. Delete
`data/interim/catchments_FIXTURE_local_test_only.gpkg` once real catchments land.

We deliberately did **not** publish our own `catchments_PROVISIONAL.gpkg`: contract §4
P1 assigns that to Mahdi, and two different `AQ-C{NN}` geometries in circulation is
precisely what the ID contract exists to prevent.

### Unblocking Earth Engine (~10 minutes, needs a browser)

```bash
.venv/bin/python -c "import ee; ee.Authenticate()"   # opens a browser
export GEE_PROJECT=your-own-project-id               # register at code.earthengine.google.com
cd scripts
../.venv/bin/python export_aca.py submit    # full padded box, native 5 m, both bands
../.venv/bin/python export_aca.py status    # poll until COMPLETED
# download the GeoTIFF from Drive/reefshield_exports/ into data/raw/aca/
../.venv/bin/python export_aca.py build     # polygonize -> merge -> assert IDs
../.venv/bin/python qa_marine.py            # regenerate reef figures
```

Contract §4 P6 is explicit that each person registers **their own** free project;
there is deliberately no shared one.

---

## 3. Swap-ins still owed (contract §5)

| # | Provisional | Replaced by | Re-run cost |
|---|---|---|---|
| 3 | `reef_zones_PROVISIONAL.gpkg` | Allen Coral Atlas export | minutes |
| 5 | `sensitivity_weight = 1.0` | Marine-scientist input, **or stays 1.0 and is labelled an assumption on the slide** | none |
| — | `gmrt_aqaba.tif` | Canonical GEBCO grid from the web form | one download, no code change |
| — | `catchments_FIXTURE_local_test_only.gpkg` | Mahdi's real polygons | one command |

**Day 12 gate:**

```bash
grep -ri PROVISIONAL --include='*.py' --include='*.md' .
ls data/**/*PROVISIONAL* data/**/*FIXTURE* 2>/dev/null
```

Anything still matching is either swapped or explicitly declared a known placeholder
in the validation report.

---

## 4. Reef zone IDs are a contract

`R-01`…`R-08` must mean the same stretch of coast before and after the ACA swap. If
`R-03` shifts, every stored exposure result silently becomes wrong — and unlike a
crash, nothing tells you.

`export_aca.py` enforces this in `verify_against_provisional()`: it asserts no new IDs
appear, and that no centroid moves more than 5 km. It also assigns ACA fragments to
the **existing** R-NN extents rather than re-deriving zones from scratch, so ACA
supplies habitat, not numbering.

Per contract §2, if ACA yields fewer real zones the extras are **dropped and the
remaining IDs keep their names**. Never renumber.

**Known candidate for future refinement:** R-08 is 2.4× the median zone area and
straddles the Marine Park boundary, so it is the obvious split candidate once real
habitat data exists. Splitting it now would change the zone count and break the ID
contract, so it is recorded here as a recommendation rather than done unilaterally —
that call needs the whole team, not one workstream.

---

## 5. Gotchas that cost us time

Recorded so nobody pays for them twice.

| Gotcha | Symptom | Fix |
|---|---|---|
| `-skipfailures` and `-gt` are mutually exclusive in GDAL | `ogr2ogr` prints usage and writes nothing, exit 0 | use one or the other |
| `-clipsrc` cuts lines into multi-parts | non-conformant GeoPackage write | add `-nlt PROMOTE_TO_MULTI` |
| GDAL's default osmconf hides `tunnel`, `industrial`, `natural`, `protect_class` in `other_tags` | SQL filters silently return 0 rows | use [osmconf_reefshield.ini](../scripts/osmconf_reefshield.ini) |
| pandas stores missing strings as float `NaN`, which is **truthy** | markdown tables print literal `nan` | `pd.isna()`, never `value or default` |
| EPSG:3857 inflates distance by 1/cos(lat) | culvert distances 14.8% too large | measure in UTM 36N, draw in 3857 |
| `imshow` defaults to `aspect='equal'` | degree-extent figures 14.9% too wide | `pulga_config.geographic_aspect()` |
| SoilGrids WCS returns XML errors with HTTP 200 | a "successful" download that is not a raster | check the TIFF magic bytes |
| GMRT ships bare `NaN` with no nodata tag | NaN propagates through interpolation without raising | gap-fill, then one declared sentinel |
