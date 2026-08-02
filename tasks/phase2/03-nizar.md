# Nizar — Supabase Cloud & Live Forcing

**Phase 2 · Workstream 3**
**Feeds:** everyone. Every read and every write in the system goes through what you build.
**Read [`00-phase2-plan.md`](00-phase2-plan.md) first.**

---

## Why your stream matters

Right now the project's state lives in loose parquet files, GeoPackages and NetCDFs across
four people's machines. Nothing joins. Nothing is queryable. The API has nothing to serve.

You turn that into one system of record. It is the least glamorous workstream and the one
everything else waits on, so it is **front-loaded on purpose**: get the schema and loaders
up in the first three days and you free yourself for the rest of the sprint. That slack is
deliberate — you are the reinforcement for whoever slips.

You also keep your forecast and current ingestion, which is already working. The difference
is that it now writes into the database instead of into a cache file nobody else can read.

---

## 1 · Do not design a schema — it is already written

`data-model.md` on the `mahdi` branch contains the complete PostgreSQL 16 + PostGIS schema:
tables, types, primary keys, foreign keys, spatial indexes, and an `is_provisional` flag on
every table that can receive seed data. It also documents *why* each table exists.

**Transcribe it. Do not redesign it.** If you find something genuinely wrong, raise it with
Karam and change it once, in that file, for everyone.

### The one architectural rule

| Store | Holds | Why |
|---|---|---|
| **Supabase Storage** | Every pixel and grid cell — rasters, NetCDF cubes, particle trajectories, model artifacts, QA figures | Postgres is a terrible raster database. A 20-million-pixel tile is one file, not 20 million rows. |
| **Postgres + PostGIS** | Everything you join on or ask questions about — IDs, small geometries, feature rows, model outputs, run parameters, metrics, provenance | The API serves joins, not arrays. `GET /catchments/AQ-C03` must be one query. |

**The bridge:** every heavy file gets a row in `raster_assets` carrying its path, CRS, pixel
size, checksum and the `data_sources.id` it came from. Nothing in storage is anonymous and
nothing in Postgres is a pixel.

**Corollary that will come up:** particle positions never enter Postgres. 5,000 particles ×
48 timesteps × hundreds of calibration runs is tens of millions of rows nobody queries
individually. Trajectories go to Storage as Parquet; only the contoured probability polygons
per timestep land in `plume_forecasts`.

---

## 2 · Supabase Cloud setup

- [ ] Create the project. Enable **PostGIS**.
- [ ] Migrations, in order: provenance (`data_sources`, `raster_assets`) → static geography
      (`catchments`, `outlets`, `reef_zones`, `catchment_surface_features`) → rainfall and
      events → forecasts and simulations → results and metrics.
- [ ] Storage buckets: `rasters/` · `netcdf/` · `trajectories/` · `figures/`.
- [ ] Keep every migration in the repo as SQL. A schema that only exists in a web console is
      a schema nobody else can reproduce.

**Watch out — secrets.** The service-role key is not the anon key. The service key goes in
the backend environment only and never near the frontend bundle. `.env` was already
committed once in this project (`2f0a6d6`); do not be the second time.

---

## 3 · Loaders

- [ ] `catchments.gpkg` + `outlets.gpkg` + `catchment_terrain.parquet` → `catchments`,
      `outlets` (Mahdi)
- [ ] `reef_zones_PROVISIONAL.gpkg`, then the real ACA export → `reef_zones` (Pulga)
- [ ] `landcover_by_catchment` + `soil_by_catchment` + `urban_by_catchment` →
      `catchment_surface_features` (Pulga)
- [ ] `catchment_rainfall.parquet`, `catchment_rainfall_climatology.parquet`,
      `events.parquet`, `event_catchment_features.parquet` (Karam)
- [ ] `depth_utm36n.tif`, `coastline.gpkg`, baseline composite, plume rasters, the 34 QA
      figures → Storage + `raster_assets` rows

**Every loader must be idempotent.** These will be re-run many times as upstream files
change, and a loader that duplicates rows on second run will cost someone an afternoon on
Day 9.

- [ ] `is_provisional` set truthfully on every row. The Day-12 gate then becomes a SQL query
      rather than a `grep`.

---

## 4 · One connection layer

- [ ] `backend/src/db/` — a single client and session factory that Pulga's API, Mahdi's model
      serving and the worker all import.
- [ ] Nobody opens their own connection. Two clients means two sets of retry behaviour, two
      transaction assumptions, and two different answers to the same question.

---

## 5 · Live forcing — carried over and finished

Your Phase 1 ingestion works. Point it at the database and close the two gaps.

### Repoint the GEFS exceedance

- [ ] It currently runs against a **placeholder 15 mm** 3-hour threshold. Replace it with
      Karam's real per-catchment p99 from `catchment_rainfall_climatology.parquet`, joined on
      `catchment_id`, and write results to `forecast_exceedance`.

This is the highest-value item in your stream. *"72% of ensemble members exceed this
catchment's 99th-percentile 3-hour rainfall"* is a real statement. *"Confidence: moderate"*
with no derivation is not, and a judge will ask which one you have.

### Copernicus Marine

- [ ] Register (free, ~10 minutes). The fetch and cache functions are already written and
      share HYCOM's output schema, so the interpolator is source-agnostic.
- [ ] Pull u/v for the marine AOI, surface plus upper depth levels.
- [ ] Publish the **HYCOM vs Copernicus Marine direction comparison** at the outlet. If two
      independent ocean models agree the current was heading south during the event, the
      plume direction claim is much stronger. If they disagree, that belongs in the
      uncertainty discussion rather than being quietly dropped.

**Watch out — you already proved this empirically and it matters:** the provisional outlet
cell is **masked as land** in HYCOM's grid, and the nearest resolved open water is ~6 km
further into the gulf mouth. That is not a bug to fix — it is the concrete evidence behind
`docs/forcing_limitations.md`. Keep it, and make sure it reaches the UI next to the current
layer.

### Offline demo snapshot

- [ ] Cache one complete "today" forecast — GFS, GEFS, IFS, currents — and seed it into the
      database as the frozen live-mode demo.
- [ ] The demo must **never** call an external API during the presentation. Coordinate the
      dump with Mahdi's offline compose path.

**Framing that matters:** the live path has to work on a dry sunny day and produce a
correctly *low* risk number. A system that only demos during a storm is not demoable.

---

## Definition of done

1. Supabase Cloud project live, PostGIS on, every migration in the repo as SQL.
2. Every table from `data-model.md` §4 created, with spatial indexes.
3. Storage buckets populated; `raster_assets` rows with path, CRS and checksum for every file.
4. Idempotent loaders for all five people's outputs.
5. One connection layer everyone imports.
6. GEFS exceedance running against Karam's real per-catchment p99.
7. Copernicus Marine pulled; HYCOM comparison documented with a figure.
8. A frozen "today" snapshot seeded for the offline demo.
9. `docs/data_dictionary.md` updated with the Copernicus Marine product ID, version and
   access date.

## Handoffs

| Teammate | What they get | When |
|---|---|---|
| **Pulga** | schema + connection layer | **Day 2 — he cannot start the API without it** |
| **Mahdi** | `model_versions` table + Storage for artifacts | Day 3 |
| **Abd** | currents interpolator + Storage for trajectories | Day 4 |
| **Ali** | stable read schema | Day 3 |
| **Everyone** | the offline snapshot | Day 10 |

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Karam** | climatology, for the exceedance threshold | **No** — ship with the placeholder, swap when it lands |
| **Mahdi** | `data-model.md` | **No** — it is written and merges on Day 0 |
