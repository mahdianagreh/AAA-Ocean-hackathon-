# Nizar — Phase 3

> **Closed out, 7 Aug.** All 6 items below are done; checkboxes here were never ticked at
> the time because the follow-up verification happened inside Phase 4 instead. Current,
> re-verified state as of 7 Aug (`tasks/phase4/03-nizar.md` items 1 & 4 for the full
> trail):
> - Cached forecast snapshot: live, `GET /api/v1/forecast/latest`, real GFS+GEFS data.
> - `model_versions`: 4 rows, all real trained artifacts (not just the first one).
> - `reef_exposures`/`simulation_runs`: populated with real particle-engine runs
>   (`plume_source: REAL_PARTICLE_ENGINE`), not synthetic stubs.
> - Currents to Abd: `get_historical_interpolator()` in `ocean_currents.py`, cached
>   historical `.nc` files on disk, verified working with sockets blocked.
> - DB-vs-files integration check: `scripts/verify_db_matches_files.py` — all green
>   except one known, already-documented file-side staleness (5 feature rows for an
>   event removed from the catalogue), not a loader bug.
> - Nothing in the demo path reaches the network — confirmed, by design
>   (`main.py`/`exposure/store.py`'s own docstrings), not just observed.

Read [`00-phase3-plan.md`](00-phase3-plan.md) first.

Your schema is done and it holds. Verified against the live database on 4 Aug via the
pooler: **25 tables, 15 populated, PostGIS present**, and after a reload it matches the
source files exactly — 100 events, 500 feature rows, 8 reef zones, zero orphans.

Two things you should know happened to it while you were away, both mine:

- **The reef zones were stale.** The loader had `reef_zones_PROVISIONAL.gpkg` hardcoded, so
  after swap #3 closed the database kept serving hand-drawn boxes — `habitat_class`
  `unknown`, `is_provisional` true, 5.69 km² against the real 1.235 km². Nothing errored;
  the API would simply have answered with superseded geometry. It now prefers
  `reef_zones.gpkg` and prints which file it read. You and I both fixed this
  independently — I kept your `resolve_reef_zones()` structure and only corrected
  `ACA_SOURCE_ID` to `allen_coral_atlas`, which is the id actually registered in
  `data_sources`. The longer spelling would have failed the foreign key.
- **16 duplicate events removed.** They were storm-days I merged away in the catalogue, and
  they dragged 80 duplicate feature rows. Anyone training off the DB would have had the same
  storm in train *and* test. Backed up to `data/interim/supabase_stale_events_backup.json`
  before deleting.

One correction, in case it cost you time: **the direct host `db.<ref>.supabase.co` is
unreachable from Karam's machine.** It publishes an AAAA record only and that Mac has no
global IPv6. The pooler on **6543** with username `postgres.<project_ref>` works fine. Not a
database problem.

---

## 1 · The cached forecast snapshot — 🟠 this is the one that shapes the demo

"Live mode" must not mean a network call. DoD item 9 is **works with wifi off**, and a live
view that fetches GFS on stage can die on conference wifi at the worst possible moment.

- [ ] Produce a **cached forecast snapshot** — the most recent GFS/GEFS/ECMWF run, frozen to
      disk, with its issue time recorded.
- [ ] The UI shows *"latest cached run, issued <time>"*. Same screen, same story, cannot
      fail.
- [ ] `forecast_runs` already has 3 rows and `forecast_catchment_rainfall` has 2,570 — so
      most of this exists. What is missing is a frozen, documented snapshot the demo points
      at rather than a live pull.

**Watch out — this is the difference between a demo that works on a judge's laptop and one
that works on yours.** Everything else in the stack is already offline-safe: the plume
renderer bakes its own satellite basemap, Ali committed his map layers, the RAG is
extractive and needs no key. Forecast ingestion is the last thing reaching for the network.

---

## 2 · Persist the model and exposure outputs

Three tables are empty and they are the ones the demo reads from:

| table | rows | waiting on |
|---|---:|---|
| `model_versions` | 0 | Mahdi's artefact is registered on disk — load it |
| `reef_exposures` | 0 | Pulga's runs |
| `runoff_predictions` | 0 | the model path |
| `simulation_runs` | 0 | Abd's plume |
| `alerts` | 0 | downstream of exposure |

- [ ] Load `model_versions` from `data/models/model_versions.jsonl`. There is a real artefact
      there now: `runoff_weighted_gbm_2194b48_20260803T214757Z`, trained on 11,810 rows.
- [ ] Persist exposure runs with **`formula_terms` and `model_versions` together**. A stored
      score that cannot be reconstructed six hours later is a number nobody can defend, and
      that reconstructability is a large part of what makes this project credible.

**Note:** Pulga's exposure store currently writes local SQLite via
`REEFSHIELD_EXPOSURE_DB=/app/var/exposure_runs.sqlite`, deliberately — `./data` is mounted
read-only and the API must not write there. Postgres persistence is the durable path, not a
replacement for that.

---

## 3 · Currents to Abd — he is blocked on this for advection

Abd's particle engine exists but the API still serves synthetic `sqrt(t)` circles. Rendered
on real imagery they cover Aqaba's city centre, the airport and a golf course, which is
visibly impossible. He needs real current fields to advect with.

- [ ] Hand him the current fields for the Oct 2016 window in whatever form is least work for
      him — he needs `u`, `v` at depth over time.
- [ ] Your own finding matters here and should reach the UI: **our release point sits on a
      cell the model masks as land.** That is exactly why the plume must render as a
      probability field with confidence stated and never as a line. It is written up in
      `docs/forcing_limitations.md` — make sure Ali quotes it rather than paraphrasing.

You already fixed the tz-aware timestamp handling in `CurrentFieldInterpolator` and closed
half the calibration forcing gap. Finish that thread.

---

## 4 · One integration check only you can do

- [ ] **Confirm the DB and the files agree** after everyone's reloads, the way I did on
      4 Aug: events, feature rows and reef zones should match the parquet/gpkg exactly, with
      zero orphaned foreign keys. If they diverge, the API and the model are reading two
      different truths and nothing will say so.

---

## Definition of done

1. A **cached forecast snapshot** the demo points at, with its issue time shown.
2. `model_versions` populated from the real artefact.
3. Exposure runs persisted with `formula_terms` + `model_versions`.
4. Real current fields delivered to Abd.
5. DB verified to match the files, zero orphans.
6. Nothing in the demo path reaches the network.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Mahdi** | the registered artefact | No — it is on disk already |
| **Pulga** | exposure runs to persist | Partly — the schema is ready |
| **Karam** | the climatology for exceedance | No, delivered |
