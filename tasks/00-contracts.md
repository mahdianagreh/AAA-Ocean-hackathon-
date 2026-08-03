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

> **Corrected 1 Aug 2026.** The first version of this contract proposed a single
> 14 × 28 km box. That was wrong by roughly 37×. Wadi Yutum drains from **90 km
> inland, out to 35.89 °E** — the old box cut off about 85% of it, which would have
> made headwater rainfall invisible to the model. If you downloaded against the old
> numbers, re-pull. The boxes below are unchanged since that correction.

**The project needs two extents, not one.** They are written by
`scripts/01_make_aoi.py` and `scripts/02_provisional_catchments.py`.

### Terrain AOI — land side

`data/aoi/terrain_aoi.geojson` · **derived from the catchments, not guessed**

```text
TERRAIN_BBOX = 34.75, 29.15, 35.94, 30.30   # W, S, E, N — EPSG:4326
                                            # ~115 km × 128 km
```

Must cover the **full contributing catchments**. Anything clipped tighter loses
upstream drainage area. Used for: DEM, hydrology, rainfall, land cover, soil.

### Marine AOI — sea side

`data/aoi/marine_aoi.geojson` · hand-set, **unconfirmed**

```text
MARINE_BBOX = 34.80, 29.25, 35.05, 29.60    # W, S, E, N — EPSG:4326
                                            # ~24 km × 39 km
```

Must reach far enough seaward to hold a 24-hour plume, or particles run off the
edge of the map. Used for: currents, bathymetry, satellite imagery, reef zones.

### Download box — the union

`data/aoi/aqaba_aoi.geojson` · **download against this or wider**

```text
AQABA_BBOX = 34.75, 29.15, 35.94, 30.30     # W, S, E, N — EPSG:4326
```

Because it's a superset of both, **nobody waits for a final AOI to start
downloading.** Clip to the relevant extent at analysis time, not download time.

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
| Coastal outlet | `AQ-O{NN}` | `AQ-O01` … `AQ-O05` | Mahdi |
| Reef zone | `R-{NN}` | `R-01` … `R-08` | Pulga |
| Event | `AQ-{YYYY}-{MM}-{DD}` | `AQ-2016-10-25` | Karam |
| Simulation run | `sim_{ULID}` | `sim_01JXYZ` | Nizar |

> **Settled 2 Aug 2026 by the 30 m delineation — outlets ARE 1:1 with catchments.**
>
> This flipped twice, so here is the history in one place. The original contract
> assumed one outlet per catchment. HydroBASINS then suggested **two** outlets for
> the whole Jordanian coast, and this section said so for a day. The Copernicus
> GLO-30 run resolves **30 discharge points** on that coast — HydroBASINS was
> lumping the small coastal wadis into a single strip basin. The five selected
> catchments each have their own mouth.
>
> | Catchment | Outlet | Area | lon, lat |
> |---|---|---:|---|
> | `AQ-C01` — Wadi Yutum | `AQ-O01` | 4,453.1 km² | 34.97073, 29.54560 |
> | `AQ-C02` | `AQ-O02` | 64.9 km² | 34.97643, 29.47270 |
> | `AQ-C03` | `AQ-O03` | 59.9 km² | 34.96416, 29.38167 |
> | `AQ-C04` | `AQ-O04` | 42.7 km² | 34.96622, 29.36052 |
> | `AQ-C05` | `AQ-O05` | 35.6 km² | 34.95998, 29.35737 |
>
> 4,656 km² total — 97% of everything draining Jordan's Gulf coast.
>
> **Keep joining on `outlet_id` anyway.** It happens to equal the catchment number
> today; hard-coding that assumption is how the previous two versions of this
> section broke.
>
> **Nizar:** five release points. `AQ-O01` carries 96% of the discharge.

> **Wadi Yutum is 4,453 km², not 6,458 km².** The larger figure appeared here on
> 1 Aug and was wrong. It counted **1,767 km² of endorheic basins** — closed
> depressions that drain to internal sinks and never reach the Gulf. HydroBASINS
> flags them `ENDO>0`; the DEM only included them because depression-breaching ran
> with `fill=True`, which forces closed basins to spill toward the coast. With that
> off, the DEM gives 4,453 km² against HydroBASINS' independent exorheic figure of
> 4,690 km² — agreement within 5%, where before they differed by 34%.
>
> **Karam:** rainfall falling on those 1,767 km² does not reach the sea. Averaging
> it into the catchment would inflate every runoff prediction.
>
> **Confirmed 2 Aug by explicit masking.** `fill=False` was only a proxy for
> "preserve closed basins", so the basins were identified directly instead — fill,
> measure depression depth, keep those over 1 km² and 10 m, walk the D8 network
> upstream, mask. That gives **4,349 km²**, within 2.3% of the published figure.
> Three independent approaches now agree:
>
> | | Wadi Yutum |
> |---|---:|
> | Explicit endorheic masking | 4,349 km² |
> | `fill=False` proxy | 4,453 km² ← published |
> | HydroBASINS exorheic | 4,690 km² |
>
> **Use 4,453 km² ±4%.** Depth is what separates a playa from an artifact: the main
> basin is 101.7 km² and 27.6 m deep and captures 1,562 km² on its own, while a
> 1.8 km² depression only 3.8 m deep was trapping 459 km² — a road embankment
> across a wadi, not a basin. Full working in `reports/endorheic/`.

**Count is fixed.** Five catchments, five outlets, and an agreed number of reef zones. Delineated area matches upstream flow accumulation at every pour point to 0.0%.

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
| 1 | `catchments_PROVISIONAL.gpkg` | **Done 2 Aug** → `catchments.gpkg` | Karam + Pulga re-run | minutes | ☑ |
| 2 | `outlets_PROVISIONAL.gpkg` | **Done 2 Aug** → `outlets.gpkg` | Nizar re-runs | minutes | ☑ |
| 3 | `reef_zones_PROVISIONAL.gpkg` | **Done 3 Aug** → `reef_zones.gpkg` (Allen Coral Atlas v2.0) | Pulga re-runs exposure | minutes | ☑ |
| 4 | `observed_plume_PROVISIONAL.gpkg` | Real Sentinel-2 derived mask | Abd publishes; Nizar re-calibrates | ~1 hour | ☐ |
| 5 | `sensitivity_weight = 1.0` | Marine-scientist input, **or stays 1.0 and is labeled an assumption on the slide** | Pulga | none | ☐ |
| 6 | Provisional AOI | Confirmed analysis box | Everyone re-clips | minutes | ☐ |

### Swaps 1 and 2 have landed — action for Karam, Pulga, Nizar

Real geometry is in the repo. Re-point and re-run; the schema is unchanged.

```text
data/processed/vectors/catchments.gpkg          5 catchments, catchment_id + outlet_id
data/processed/vectors/outlets.gpkg             5 outlets, lon/lat
data/processed/features/catchment_terrain.parquet   area, relief, slope, drainage density
data/interim/hydro/outlet_candidates.csv        all 72 discharge points, for reference
```

**What actually changed, not just the file name:**

- **Areas moved a lot.** The provisional set totalled 6,833 km²; the real one is 4,656 km². Any per-catchment rainfall total computed against the old polygons is wrong, not merely imprecise.
- **`AQ-C01` is a different place.** It was a 1,767 km² endorheic basin. It is now Wadi Yutum at 4,453 km². Same ID, different geometry — this is the one that bites silently.
- **Five outlets, not two.** Nizar releases from five points.
- **The southern coast split.** One 376 km² lumped polygon became four separate wadis with separate mouths.

### Swap 3 has landed — action for Pulga

`data/processed/vectors/reef_zones.gpkg` — real Allen Coral Atlas v2.0 benthic
habitat, all 8 IDs intact, no renumbering. Schema is a **superset** of the
provisional one, so existing code keeps working. Re-run the exposure engine.

**What actually changed, not just the file name:**

- **Total reef area fell from 5.69 km² to 1.24 km².** The provisional number was the
  area of hand-drawn 250 m-wide boxes; this is the area ACA maps as benthic habitat.
  Any absolute exposure figure computed against the old polygons is wrong, not merely
  imprecise. Relative rankings between zones changed too.
- **`habitat_class` is now a real readable class** (`Coral/Algae`, `Rock`, …) instead of
  `unknown`, with `habitat_class_mix` giving the full composition by area. Coral/Algae
  dominates R-01–R-06; Rock dominates R-07–R-08.
- **`marine_park_overlap_pct` was recomputed** and rose sharply — R-04/R-05/R-06 go from
  71/67/85% to 97/100/100%. The old values described the boxes, not the reef.
- **Depths are less usable, not more.** The bathymetry is 50 m and the reef strip is
  20–50 m wide, so 39–100% of cells under a zone read as land. Depths are now medians
  over water cells only and **R-02 is `NaN`**. Check the new `depth_land_cell_pct`
  before using any depth. Do not quote R-03's −179.7 m — it rests on 2 cells.
- **`sensitivity_weight` is still 1.0** everywhere (swap 5 is unaffected). ACA maps
  habitat, not sensitivity.
- New audit files alongside it: `aca_fragments_BEFORE_MERGE.gpkg` (raw ACA polygons) and
  `aca_pieces_ASSIGNED.gpkg` (which piece went to which zone, and whether by overlap or
  by snap).

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
- [x] **Nizar:** P5 synthetic plume mask
- [ ] Everyone registers their own accounts: NASA Earthdata · Copernicus CDS · Copernicus Data Space · Copernicus Marine · own GEE project
- [ ] Everyone confirms they can start their stream **today** without needing anything from anyone

Last item is the test. If anyone answers no, the contract has a gap — fix it before the day ends.
