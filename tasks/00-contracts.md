# Day 1 Contracts — How Nobody Waits for Anybody

**Project:** ReefShield Aqaba
**Read this before your own task file.**

---

## The problem this solves

The obvious way to run this project is sequential: Mahdi delineates catchments → Karam averages rainfall inside them → the model trains. Abd waits for event dates. Nizar waits for outlets.

With 14 days and five people, that's a chain where one slow link idles four people. Worse, the riskiest task in the project (Abd's imagery gate) sits at the *end* of a dependency chain, so we'd discover the project's biggest problem late.

## The fix

**Freeze the contract, not the data.**

On Day 1 we agree every ID scheme, file path, and table column. Then we generate **provisional versions of every shared input** — crude but structurally correct. Everyone builds their full pipeline against the provisional data immediately. When real data lands, it drops into the same schema and the pipeline re-runs unchanged.

The cost of a rerun is minutes. The cost of waiting is days.

> **One rule that makes this safe:** every provisional file is named `*_PROVISIONAL.*` and every swap-in is a checklist item in §5. Placeholder data reaching the final demo is the one real risk of this approach — §5 exists to prevent it.

---

## 1. Spatial contract

### Download box (generous, padded)

Download everything to a **padded box**, wider than the study area. Clipping to the exact analysis box happens at analysis time, not download time.

```text
DOWNLOAD_BBOX = 34.80, 29.25, 35.15, 29.70   # W, S, E, N — EPSG:4326
```

Because it's a superset, **nobody has to wait for the final AOI to start downloading.** If the analysis box shifts, your downloads are still valid.

### Analysis box (exact)

Committed Day 1 as `data/aoi/aqaba_aoi.geojson`. Starting proposal, to confirm visually — *not verified*:

```text
ANALYSIS_BBOX = 34.90, 29.35, 35.05, 29.60   # W, S, E, N — EPSG:4326
```

Must extend far enough seaward to hold a 24-hour plume, or particles run off the edge of the map.

### CRS

| Purpose | CRS |
|---|---|
| Storage, exchange, GeoJSON | **EPSG:4326** |
| Area, distance, slope, all maths | **EPSG:32636** (UTM 36N) |

Any area in km² computed in degrees is wrong. No exceptions.

---

## 2. ID contract — agreed now, never changed

These strings are the join keys for every table in the project. Renaming one later breaks every stored result that referenced it.

| Entity | Format | Examples | Owner |
|---|---|---|---|
| Catchment | `AQ-C{NN}` | `AQ-C01` … `AQ-C05` | Mahdi |
| Coastal outlet | `AQ-O{NN}` — matches its catchment number | `AQ-O01` ↔ `AQ-C01` | Mahdi |
| Reef zone | `R-{NN}` | `R-01` … `R-08` | Pulga |
| Event | `AQ-{YYYY}-{MM}-{DD}` | `AQ-2016-10-25` | Karam |
| Simulation run | `sim_{ULID}` | `sim_01JXYZ` | Nizar |

**Count is fixed on Day 1 too.** Five catchments, five outlets, and a number of reef zones agreed up front. If the real delineation produces four catchments, `AQ-C05` is dropped — the other four keep their names.

---

## 3. File path contract

Everyone writes to these paths. Downstream code reads these paths. No one asks where anything is.

```text
data/
├── aoi/
│   └── aqaba_aoi.geojson
├── raw/<source>/<product>/
├── processed/
│   ├── dem/dem_utm36n.tif
│   ├── vectors/
│   │   ├── catchments.gpkg          # id, name, geometry, area_km2
│   │   ├── outlets.gpkg             # id, catchment_id, geometry
│   │   ├── reef_zones.gpkg          # id, habitat_class, area_km2, sensitivity_weight
│   │   ├── coastline.gpkg
│   │   └── observed_plume.gpkg
│   ├── features/
│   │   ├── catchment_terrain.parquet     # Mahdi
│   │   ├── landcover_by_catchment.parquet # Pulga
│   │   └── soil_by_catchment.parquet      # Pulga
│   ├── events/
│   │   └── rainfall_candidates.parquet    # Karam
│   ├── bathymetry/depth_utm36n.tif
│   └── plume/
│       ├── baseline_composite.tif
│       └── observed_plume_probability.tif
└── outputs/<run_id>/
```

Anything provisional gets `_PROVISIONAL` before the extension: `catchments_PROVISIONAL.gpkg`.

---

## 4. Provisional seed data — built in the first few hours

This is what removes the blocking. Each item is crude, fast, and structurally identical to the real thing.

### P1 · Provisional catchments — *Mahdi, ~1 hour*

Download **HydroBASINS level 9** (precomputed, no DEM processing needed) or MERIT Hydro basins, clip to the AOI, pick the 5 that drain to the Gulf, assign `AQ-C01`…`AQ-C05`.

→ `data/processed/vectors/catchments_PROVISIONAL.gpkg`

Coarse and wrong in detail. Structurally perfect. **Karam and Pulga build their entire aggregation pipeline on this and never wait.**

### P2 · Provisional outlets — *Mahdi, ~1 hour*

Open satellite imagery, find where each wadi visibly meets the sea, click a point. No DEM required.

→ `data/processed/vectors/outlets_PROVISIONAL.gpkg`

**Nizar's particle engine is built against these.** Swapping in real coordinates later is a config change, not a rebuild.

### P3 · Event dates — *anyone, ~1 hour, Day 1*

The two candidate events are already named in the concept doc: **October 2016** and **February 2013**. Exact dates come from two papers, not from IMERG:

- Ginat et al. 2025 — https://nhess.copernicus.org/articles/25/3201/2025/index.html
- Katz et al. 2015 — https://www.sciencedirect.com/science/article/pii/S0012821X15001119

→ `docs/event_dates.md`

**This deletes the Karam → Abd dependency entirely.** Abd reads the papers himself and starts his audit on Day 1 instead of Day 5. That matters more than any other item here, because his audit is the project's gate.

### P4 · Provisional reef zones — *Pulga, ~1 hour*

Hand-draw 6–8 boxes along the Aqaba coast where reefs are known to be. Name them `R-01`…`R-08`. Set every `sensitivity_weight` to `1.0`.

→ `data/processed/vectors/reef_zones_PROVISIONAL.gpkg`

The exposure engine and the dashboard can be built end-to-end against these while the real Coral Atlas export is prepared.

### P5 · Provisional plume mask — *Nizar, ~30 min*

A synthetic ellipse offset from an outlet, saved in the same format Abd's real mask will use.

→ `data/processed/plume/observed_plume_PROVISIONAL.gpkg`

Lets Nizar build and test the whole calibration parameter search before any real satellite mask exists. When Abd's mask lands, the search runs against real data with no code change.

### P6 · Everyone pulls their own small statics — *Day 1*

Stop routing small downloads through other people:

- **GEBCO bathymetry** — 10-minute download, no dependencies. Nizar pulls his own copy rather than waiting for Pulga.
- **Coastline** — derive from GEBCO or use Natural Earth. Two people having their own is fine.
- **Google Earth Engine** — **each person registers their own free project.** There is no reason for a shared one, and it was a pointless blocker.

---

## 5. Swap-in checkpoints — the part that must not be forgotten

Provisional data in the final demo would be a serious failure. Every swap is a tracked item.

| # | Provisional | Replaced by | Owner of swap | Re-run cost | Done |
|---:|---|---|---|---|:--:|
| 1 | `catchments_PROVISIONAL.gpkg` | 30 m DEM delineation | Mahdi publishes; Karam + Pulga re-run | minutes | ☐ |
| 2 | `outlets_PROVISIONAL.gpkg` | DEM outlets, checked vs imagery + OSM | Mahdi publishes; Nizar re-runs | minutes | ☐ |
| 3 | `reef_zones_PROVISIONAL.gpkg` | Allen Coral Atlas export | Pulga | minutes | ☐ |
| 4 | `observed_plume_PROVISIONAL.gpkg` | Real Sentinel-2 derived mask | Abd publishes; Nizar re-calibrates | ~1 hour | ☐ |
| 5 | `sensitivity_weight = 1.0` | Marine-scientist input, **or stays 1.0 and is labeled an assumption on the slide** | Pulga | none | ☐ |
| 6 | Provisional AOI | Confirmed analysis box | Everyone re-clips | minutes | ☐ |

**Day 12 gate:** grep the repo for `PROVISIONAL`. Anything still matching is either swapped or explicitly declared a known placeholder in the validation report. No silent placeholders.

---

## 6. What genuinely cannot be decoupled

Two things, and only two. Everything else above is now parallel.

### Calibration needs a real observation

Nizar tunes diffusion, windage, and settling by comparing simulated plumes against Abd's observed mask. You cannot calibrate against an observation that doesn't exist.

**Reduced to:** Nizar builds and tests the full parameter search against the synthetic mask (P5). When Abd's real mask lands, it's a file swap and a re-run — roughly an hour, not days of blocked work.

### Final validation metrics need both sides

IoU, Dice, centroid distance and area error need a real prediction *and* a real observation. This is the last substantive task in the project by definition.

**Reduced to:** the metric code itself is written and unit-tested early against synthetic masks. On the day both real inputs exist, it's one command.

---

## 7. What this changes about the schedule

Before:

```text
Day 1  everyone waits for AOI
Day 2  Mahdi DEM
Day 3  Karam waits for catchments → event dates
Day 4  Mahdi outlets → Nizar unblocked
Day 5  Abd finally starts the audit   ← the project's biggest risk, discovered late
```

After:

```text
Day 1  contracts + provisional seeds (half a day, everyone)
Day 1  ALL FIVE STREAMS RUNNING IN PARALLEL
       Mahdi   real DEM chain
       Karam   IMERG on provisional catchments
       Pulga   land/soil on provisional catchments, reef zones
       Abd     imagery audit — starts Day 1, not Day 5  ← risk found early
       Nizar   forecasts + currents + engine on provisional outlets
Day 4–6 swap-ins as real data replaces provisional
Day 9   calibration against Abd's real mask
```

**The single biggest win:** Abd's gate — the one thing that can invalidate the whole concept — is answered on Day 2 or 3 instead of Day 5. If the answer is bad, there are eleven days to change the demo event instead of nine.

---

## 8. Day 1 checklist

Half a day, together, then everyone is independent.

- [ ] Confirm download box and analysis box · commit `data/aoi/aqaba_aoi.geojson`
- [ ] Confirm ID formats and counts (§2)
- [ ] Create the folder structure (§3), commit with `.gitkeep` files
- [ ] Agree `docs/data_dictionary.md` row format
- [ ] **Mahdi:** P1 provisional catchments, P2 provisional outlets
- [ ] **Pulga:** P4 provisional reef zones
- [ ] **Anyone:** P3 event dates from the two papers → `docs/event_dates.md`
- [ ] **Nizar:** P5 synthetic plume mask
- [ ] Everyone registers their own accounts: NASA Earthdata · Copernicus CDS · Copernicus Data Space · Copernicus Marine · own GEE project
- [ ] Everyone confirms they can start their stream **today** without needing anything from anyone

Last item is the test. If anyone answers no, the contract has a gap — fix it before the day ends.
