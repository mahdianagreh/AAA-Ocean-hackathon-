# Karam — Integration Lead & Unified Data Pipeline

**Phase 2 · Workstream 1**
**Feeds:** everyone. Your feature matrix is what Mahdi trains on and what the API serves.
**Read [`00-phase2-plan.md`](00-phase2-plan.md) first.**

---

## Why your stream matters

You have two jobs and they pull in opposite directions.

**As pipeline owner** you build the single table the whole system rests on. Right now
rainfall, terrain, land cover and soil live in five separate parquet files produced by four
people against three different bounding boxes. One row per (event × catchment), joined and
correct, is the deliverable — and nothing downstream can start without it.

**As integration lead** your job is the seams. Six streams converge on one app in eleven
days. When two people disagree about a column name, you decide the same day. When someone's
output does not match the contract, you catch it before it reaches the demo. Your real
deliverable is *the demo runs end to end*, and that is not the same thing as everyone
finishing their own piece.

Protect the second job. It is the one that fails silently.

---

## 1 · Contract v2 enforcement — Day 0

The old bounding box is wired into seven places. Until they are all fixed, people are
downloading the wrong data and will not notice.

- [ ] Create one authoritative spatial module — `TERRAIN_AOI`, `MARINE_AOI`, `AQABA_BBOX`,
      both CRS constants. Everything imports from it.
- [ ] Purge the hard-coded `(34.80, 29.25, 35.15, 29.70)` from:
      `backend/src/ingestion/imerg.py` · `era5_land.py` · `gfs.py` · `gefs.py` ·
      `ecmwf.py` · `ocean_currents.py` · `scripts/config.py`
- [ ] Update `configs/october_2016_demo.yaml` and `configs/event_pipeline.example.yaml`
      to the terrain AOI.
- [ ] Write `data/aoi/terrain_aoi.geojson` and `data/aoi/marine_aoi.geojson`; keep
      `aqaba_aoi.geojson` as the union.
- [ ] Add a test that asserts no module contains a literal bounding box.

**Watch out:** a wrong box does not raise an error. It returns data — just the wrong data,
for a smaller area, silently. This is exactly the class of bug that produced the ordering
anomaly in `docs/event_dates.md`.

---

## 2 · Two-stage event mining

The point of this is to turn one labelled event into a training set. Twenty-six years of
IMERG contains every storm that has hit these catchments since 2000.

### Why two stages

Half-hourly IMERG for 26 years is **~455,000 granules**. Even at ~44 KB each after
subsetting, that is 455,000 separate Harmony requests — weeks of wall time. We have eleven
days.

IMERG publishes the same product **daily**: one file per day, ~9,500 files for 26 years.
So: skim cheaply at daily resolution to find the wet days, then pull 30-minute detail only
where it matters.

```
Stage 1   daily,      2000-06 -> 2026      ~9,500 files      hours
Stage 2   half-hourly, top ~50 events x 4 days  ~6,000 files  hours
          -----------------------------------------------------------
          ~15,500 files instead of 455,000       ~3% of the work
```

### Stage 1 — daily screen

- [ ] Resolve the daily Final collection ID **from CMR, not by guessing** — the project's
      norm, and it is how the Early Run ID was established. Add it to the `IMERG_PRODUCTS`
      registry alongside `final` and `early`.
- [ ] Pull daily Final over `TERRAIN_AOI`, 2000-06 → present, with the existing chunking and
      resume logic.
- [ ] Aggregate per catchment, **area-weighted against the real polygons** — never per
      bounding box, never by array index.
- [ ] Rank days per catchment against that catchment's own daily climatology.
- [ ] Keep the **top 100** days, not the top 20. Cheap insurance against the caveat below.
- [ ] **Force-include** every date named in `docs/event_dates.md` regardless of rank.

**Watch out — the honest caveat.** Screening on daily totals can under-rank a short violent
burst that lands on a day with a modest total. That matters because intensity, not daily
depth, is what floods a wadi. The generous top-N and the forced literature dates are the
mitigation. **Write this in the model card** — a stated methodology limit is fine; an
unstated one is a hole.

### Stage 2 — half-hourly detail

- [ ] For the retained events only, pull half-hourly Final over a ±2-day window.
- [ ] Rolling 1 / 3 / 6 / 24 h accumulations per catchment, `skipna=False`, full
      `min_periods`.
- [ ] Per-catchment percentiles p50 … p99.9 per window →
      `data/processed/features/catchment_rainfall_climatology.parquet`.

> **Nizar needs the climatology as early as you can give it.** His GEFS exceedance
> probability is currently running against a placeholder 15 mm threshold. A rough real
> number this week beats a precise one on Day 9.

---

## 3 · The event catalogue

- [ ] Rank windows above p99 for 3 h or 24 h → `data/processed/events/events.parquet`.
- [ ] Set `is_exhaustive = true` with the real scope recorded — this has been `false` on
      every row so far and the catalogue is the reason to change it.
- [ ] Event IDs follow `AQ-YYYY-MM-DD` per contract §2.
- [ ] Record `detection_method`, `label_tier`, and paper DOIs in `source_references`.

**Acceptance:** `AQ-2016-10-28` appears in the top 3 for `AQ-C01`. If it does not, stop and
find out why before building anything on top — that is the sanity check that catches an AOI
or timezone error, and it is more important than any deadline.

**The ordering anomaly.** `docs/event_dates.md` records that the derived rainfall peak
(02:30Z) falls *after* the documented flood arrival (00:00Z) — the opposite of the paper's
sequence. The stated hypothesis is that the generating catchments lie outside the old box.
Recomputing over the real catchments either resolves this or it does not. **Either way,
record the answer in `docs/event_dates.md`.** A resolved anomaly is a good slide; an
unexamined one is a liability.

---

## 4 · Antecedent features

- [ ] ERA5-Land hourly over `TERRAIN_AOI` for every retained event window.
- [ ] Run the existing extractor: soil moisture at T−24 h and T−72 h, 24/72/168 h
      precipitation and runoff totals, event-time wind and temperature, valid fractions and
      quality flags.
- [ ] Where a window cannot be fully covered, the flag says `PARTIAL_WINDOW` and the value
      is honest. Never zero-fill.

**Watch out:** ERA5-Land is land-only and its sea cells are permanently NaN. They stay NaN.
ERA5-Land precipitation will not match IMERG and that is not an error to fix — IMERG for
rainfall magnitude, ERA5-Land for soil and wind state, never averaged.

---

## 5 · Labels

Three tiers, each declared in the data, not just in a doc.

| Tier | Rule | Use |
|---|---|---|
| **Gold** | Literature-confirmed flood reaching the sea, mooring-verified | Held out. **Never trained on.** |
| **Silver** | ERA5-Land `sro` exceeds that catchment's own p99 within 24 h of the rainfall window | Training target |
| **Bronze** | Rainfall percentile only | **Never a target** |

- [ ] Add `label_tier` and `label_basis` columns. `label_basis` is a sentence, not a code.
- [ ] Assert that `sro` and `ssro` appear **nowhere** in the feature column list.

> ### The rule that keeps this honest
> **ERA5-Land runoff is a label, never a feature.** Use it as both and you build a
> tautology that scores beautifully and predicts nothing. Make the assertion a test so
> nobody re-adds the column in a hurry on Day 9.

---

## 6 · The feature matrix — your main deliverable

One row per (event × catchment):

```text
data/processed/features/event_catchment_features.parquet
```

| Group | Columns | From |
|---|---|---|
| Keys | `event_id`, `catchment_id`, `event_time_utc` | you |
| Rainfall | `rain_1h_mm`, `rain_3h_mm`, `rain_6h_mm`, `rain_24h_mm`, `rain_3h_percentile`, `anomaly_score` | you |
| Antecedent | soil moisture T−24/−72 h, prior 24/72 h/7 d precipitation, event-time wind speed and direction, temperature | you |
| Terrain | area, relief, mean/max slope, drainage density, longest flow path | Mahdi |
| Land & soil | bare fraction, built-up fraction, clay/sand/silt/SOC/bulk density, coarse fragments | Pulga |
| Urban | road density, building fraction, mapped drainage density, industrial fraction | Pulga |
| Label | `label_tier`, `label_basis`, `runoff_label` | you |
| Quality | `valid_data_fraction`, `quality_flag` | you |

- [ ] Assert every join is on `catchment_id` in `AQ-C{NN}` form and that no row is dropped
      silently by a join.
- [ ] Assert land-cover fractions sum to 1.0 and catchment-mean soil texture still sums to
      100% after spatial averaging — Pulga already has these checks; keep them at the join.

**Hand this to Mahdi the moment it exists, even if only Stage 1 events are in it.** A model
trained on 40 events on Day 5 that gets retrained on 100 events on Day 8 is far better than
a model that starts on Day 8.

---

## 7 · Integration lead

Not a title. A workload.

- [ ] Own Day 0. Do the merge yourself if it is not done by midday.
- [ ] Own the schema. When Nizar's column and Pulga's column disagree, you pick, you write
      it down, and you tell everyone the same day.
- [ ] Own the **6 August vertical slice**. End to end, ugly, wrong numbers allowed. One
      event → one prediction → one plume → one exposure score → visible on the map.
- [ ] Run the full demo yourself daily from 7 August. You will be the first to know when it
      breaks, which is the entire point.
- [ ] Own the offline cache decision with Mahdi — every input for Oct 2016 and one cached
      "today" forecast, baked in. The demo must never call an external API live.

> **The 6 August slice is the most important thing you own.** A system integrated on Day 11
> has never been tested. Five people finishing their own piece perfectly and discovering on
> Day 12 that the pieces do not fit is the standard way hackathon projects die.

---

## Definition of done

1. One spatial module; zero hard-coded boxes; a test that enforces it.
2. Daily IMERG swept 2000 → 2026 over the five real catchments; climatology published.
3. Half-hourly detail for the retained events; rolling accumulations per catchment.
4. `events.parquet` with `is_exhaustive = true`, and Oct 2016 in the top 3 for AQ-C01.
5. `event_catchment_features.parquet` — the joined matrix, delivered to Mahdi.
6. The ordering anomaly resolved or explained, in writing, in `docs/event_dates.md`.
7. `docs/data_dictionary.md` updated: daily IMERG product ID, version, access date, licence.
8. The vertical slice ran on 6 August, and the full demo runs daily after it.

## Handoffs

| Teammate | What they get | When they need it |
|---|---|---|
| **Mahdi** | `event_catchment_features.parquet` | As early as possible; partial is fine |
| **Nizar** | `catchment_rainfall_climatology.parquet` | Early — his exceedance is on a placeholder |
| **Pulga** | Feature schema for the API | Day 2 |
| **Abd** | Event windows and the rainfall series for the demo event | Day 3 |
| **Ali** | The demo event's rainfall time series for the hyetograph | Day 5 |

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Mahdi** | `catchments.gpkg`, `catchment_terrain.parquet` | **No — merged on Day 0** |
| **Pulga** | land / soil / urban per catchment | **No — his pipeline runs the moment catchments land** |
| Nobody else | — | — |
