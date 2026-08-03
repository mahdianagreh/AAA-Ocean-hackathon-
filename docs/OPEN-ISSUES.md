# Open issues — things blocked on, or waiting for, someone

**Owner of this file:** Ali · **Opened:** 2026-08-03 · **Raised from:** the frontend build

Every item below is something **the frontend cannot resolve on its own**. Each names the
person who owns it, what "done" looks like, and the evidence — so nobody has to take a claim
on trust or go looking for the file it came from.

Workstream owners, from [`tasks/phase2/00-phase2-plan.md`](../tasks/phase2/00-phase2-plan.md) §Team:

| # | Who | Owns | Task file |
|---|---|---|---|
| 1 | **Karam** | Integration lead + unified data pipeline | [`01-karam.md`](../tasks/phase2/01-karam.md) |
| 2 | **Mahdi** | Model layer + DevOps | [`02-mahdi.md`](../tasks/phase2/02-mahdi.md) |
| 3 | **Nizar** | Supabase Cloud + live forcing | [`03-nizar.md`](../tasks/phase2/03-nizar.md) |
| 4 | **Pulga** | Backend, exposure engine, RAG | [`04-pulga.md`](../tasks/phase2/04-pulga.md) |
| 5 | **Abd** | Marine transport + validation | [`05-abd.md`](../tasks/phase2/05-abd.md) |
| 6 | **Ali** | Frontend | [`06-ali.md`](../tasks/phase2/06-ali.md) |

**Severity key.** 🔴 blocks a storyboard scene · 🟠 forces a workaround we would rather not
keep · 🟡 should be decided before it becomes expensive.

---

## 🔴 Blocks a scene

### 1 · Pulga — `/api/v1/catchments` has no geometry, and `/api/v1/reef-zones` does not exist

**This is Day-1 ask #8**, and it is not in
[`07-data-contracts.md`](Ali/frontend/07-data-contracts.md) §1 because I only found it after the
API landed.

`GET /api/v1/catchments` is tagged `geometry` and documented as feeding the map layer, but it
returns attributes plus a single `lon`/`lat` point per catchment
([`backend/src/api/main.py:159-168`](../backend/src/api/main.py#L159-L168)) — and it never reads
disk, it returns a hardcoded module constant. There is no polygon, no GeoJSON, no bbox.
`/api/v1/reef-zones` is in the planned endpoint list and is unwritten.

Reef zones are the *subject* of the product: the exposure colouring, the legend and the
five-band hazard ramp all key off them.

**Done looks like:** both endpoints return a GeoJSON `FeatureCollection`, or a `geometry` field
per row, in EPSG:4326.

**Note on the api image:** it deliberately has no geospatial stack
([`backend/requirements-api.txt`](../backend/requirements-api.txt); the reason is stated at
`main.py:69-71`), so it cannot read a GeoPackage. Either the worker exports GeoJSON to
`data/processed/vectors/` the way `outlets.geojson` already is, or the api image gains
`pyogrio`. The first is cheaper and matches what already works.

**Frontend workaround, in place now:** [`scripts/13_frontend_basemap.py`](../scripts/13_frontend_basemap.py)
derives all of it from the `.gpkg` files into committed GeoJSON. That is needed anyway for the
wifi-off requirement, so it is not wasted — but it means the map is showing geometry the API
does not know about, and those two must not drift.

### 2 · Abd — plume contours as GeoJSON, not a GeoTIFF

Day-1 ask #1. `observed_plume_probability.tif` is **4.2 MB** for one timestep, and Scene 4 needs
four timesteps with scenario reruns on top — tens of MB per interaction.

`particle_engine.kernel_density_contours` already exists; the ask is that
`POST /api/v1/plume/simulate` serves the contours rather than the raster, and that
`density_caveat` and `forcing_caveat` travel **in the payload** rather than in a footer someone
can forget to render.

**Done looks like:** the `PlumeTimestep` shape in
[`07-data-contracts.md`](Ali/frontend/07-data-contracts.md) §4 — `levels[]` with
`relative_density` and a `MultiPolygon`, both caveats required not optional.

**The naming matters.** The field is `relative_density`, never `probability`. The engine
peak-normalises before contouring, so a `0.50` band means *half the peak density of this cloud*,
not a 50% chance of impact. Its own docstring says so. Mislabelling it is the first thing a judge
would press on.

### 3 · Mahdi — SHAP drivers as objects with stable keys

Day-1 ask #5. `runoff_model.py:219-226` returns `{feature, shap, value}` where `feature` is a raw
parquet column name. The frontend needs `{key, contribution, value}` where `key` is a stable i18n
key — a pre-rendered English label cannot become Arabic at render time, and DoD item 8 is
bilingual with working RTL.

The raw column names are usable as i18n keys by convention, so this may be a rename plus a
`Value` wrapper rather than real work.

### 4 · Nizar / Mahdi — confidence as its components, not a sentence

Day-1 ask #6. Needed: `{members_exceeding, members_total, threshold_label, threshold_value}`, so
the UI composes *"22 of 30 members exceed…"* in the active language.

What exists is `confidence_terms` (`runoff_model.py:61-107`) — same spirit, different shape, and
**untranslatable as-is**, because `catchment_ap` can be an English string like
`"0.412 (mean - AQ-C06 not in LOCO folds)"`.

---

## 🟠 Forces a workaround

### 5 · Pulga — the health endpoint path

The API serves **`GET /health`** (`main.py:134`). Every planning doc says
`GET /api/v1/health`. One of the two is wrong; changing `main.py` is a one-line fix and changing
the docs is not. The frontend currently targets `/health`.

### 6 · Pulga — no `Value` wrapper, so numbers arrive without units or provenance

[`07-data-contracts.md`](Ali/frontend/07-data-contracts.md) §2 makes this structural, not
stylistic: *"A `Value` without `provenance` fails type-check, so an unlabelled number cannot reach
the screen."* It exists because carry-over rule 5 says a reported number, a converted number and
a computed number are three different things.

The API returns bare floats — `runoff_probability: 0.7213`, `area_km2: 4453.08`.

**The pattern already exists in this repo.** `data/processed/marine/mooring_target_AQ-2016-10-28.json`
provenance-tags every single field. It just has not reached the API.

### 7 · Pulga / Mahdi — `position_confidence` has two different vocabularies

For the same five physical outlets:

- `/api/v1/catchments` emits `plausible` · `low` · `good` (`main.py:97`, `main.py:120`)
- `/api/v1/outlets` reading from disk emits `high` · `low`

The frontend union currently has to cover all four. Pick one vocabulary.

### 8 · Pulga — `/api/v1/outlets` returns a variable key set

`main.py:191` filters with `{k: r[k] for k in keys if k in r}`, so `culvert_verdict`,
`unmodelled_coastal_culverts`, `nearest_culvert_m` and `upstream_km2` appear only when
`outlets.geojson` is readable and vanish on the embedded fallback — with no flag in the payload
except a prose `source` string. Every one of them is optional in TypeScript as a result.

### 9 · Team — the backend test suite cannot run outside Docker

**10 of 14 test files fail to import** locally: `geopandas`, `rasterio`, `shapely` and `xarray`
are absent, so `pytest tests/` stops at collection.

The often-quoted **"368 tests"** figure comes from grepping `def test_`, not from a run. I
repeated it in a plan myself before checking, which is exactly how it spreads.

This is the reproducibility gap [`16-build-state.md`](Ali/research/16-build-state.md) already
records. There is no root dependency manifest — only `backend/requirements-api.txt` and
`requirements-worker.txt`, neither of which covers the test suite.

**Done looks like:** a `requirements-dev.txt` (or the worker image running pytest in CI) and a
number in the docs that came from an actual run.

### 10 · Mahdi — the worker cannot write to `frontend/`

`docker-compose.yml` mounts `./data`, `./backend/src` and `./scripts` into the worker, so there is
no `/app/frontend` in the container. The basemap derivation therefore needs an ad-hoc mount:

```bash
docker compose run --rm --entrypoint "" \
  -v "$PWD/frontend/public/basemap:/out" \
  worker python /app/scripts/13_frontend_basemap.py --out /out
```

That works and needs no compose change, so this is a nicety rather than a blocker. Three
optional compose improvements if you want them: `VITE_DATA_SOURCE` passed through as the
fixtures/http switch, a `frontend` healthcheck, and `VITE_POLL` for macOS bind mounts.

---

## 🟡 Decide before it gets expensive

### 11 · Pulga — figure delivery, and who generates thumbnails

Day-1 ask #3, still undecided. 27 MB of QA PNGs, 11 of them over 1 MB, `overview_01` alone
5.4 MB. API static mount or frontend bundle? The offline pack has to carry them either way.

Two facts the provenance panel already depends on: `manifest.json` lists **34** figures while
**36** PNGs exist, and driving the panel off the manifest silently omits two — which is a
decision, not an accident. And `overview_01_master_all_layers.png` is **excluded entirely**,
because its own burned-in caption says *"CATCHMENTS ARE A LOCAL TEST FIXTURE… 5 latitude bands,
not a watershed delineation."* Best-looking figure, wrong catchments.

### 12 · Pulga / Nizar — pre-downsampled hyetograph

Day-1 ask #2. `catchment_rainfall` is ~2.3 M rows and the browser must never see the raw series.
`catchment_rainfall_daily.parquet` is 50,675 rows, which is fine; the half-hourly product is not.
The ask is a series already at display resolution.

### 13 · Pulga — `/ask` citations as a structured array, never prose

Day-1 ask #4. *"An uncited answer must not render as an answer"* has to be structurally
impossible rather than a convention — hence the discriminated union in
[`07-data-contracts.md`](Ali/frontend/07-data-contracts.md) §4, where `citations` is a non-empty
tuple on the `answered` branch.

The corpus is technical and operational docs only. **`docs/Ali/research/*` is not in it.**

### 14 · Everyone — units never baked into value strings

Day-1 ask #7. RTL reorders `2.18 g/L` into `g/L 2.18` if it arrives as one string. Send
`{value, unit}`; the UI owns formatting because the UI knows the language.

### 15 · Mahdi — `data/models/` does not exist, so two endpoints 503

`GET /api/v1/models` and `POST /api/v1/runoff/predict` return 503 today, because
`artifacts.py:27-28` looks for `data/models/model_versions.jsonl` and the directory is absent.

The 503 body names `data/processed/features/event_catchment_features.parquet` as the blocker.
That file **does** exist (500 × 35) but is missing two of five columns `schema.REQUIRED` wants —
it has `timestamp_utc` instead of `event_time_utc`, and **no `runoff_label` at all** — so
training would raise `SchemaError` at `schema.py:83`. `feature_matrix_status.json` agrees:
`"complete": false`, with `landcover`, `soil` and `urban` under `sources_missing`.

**The frontend does not need this to be fixed** — it renders the 503 as a first-class state
saying the harness is built and validated but no artefact is registered, which is honest. Flagged
so nobody assumes the dashboard is broken when it says that.

### 16 · Pulga — the API has no tests

No `TestClient`, no `api.main` import anywhere under `tests/`. `main.py` has no regression net, and
[`07-data-contracts.md`](Ali/frontend/07-data-contracts.md) §5's contract tests — *"a fixture that
stops matching the live response fails CI rather than surfacing as a blank panel during
rehearsal"* — have nothing to run against on the backend side.

### 17 · Pulga — a marine scientist is needed for reef sensitivity

Every one of the 8 reef zones still carries `sensitivity_weight = 1.0` and
`sensitivity_weight_status = 'PLACEHOLDER_PENDING_MARINE_SCIENTIST'` (verified in
`reef_zones_PROVISIONAL.gpkg` today). Exposure therefore varies **only** through the hazard term.

The frontend legend is written so it does not imply zones differ in sensitivity, which is the
honest rendering — but this is swap-in #3 on
[`tasks/00-contracts.md`](../tasks/00-contracts.md) and it is still `☐`.

### 18 · Ali — Arabic scientific copy needs a human reviewer

[`06-bilingual-rtl.md`](Ali/frontend/06-bilingual-rtl.md) §6 calls this *"the item with no
technical fallback"*, and it is the only risk in the whole frontend plan without an engineering
mitigation. Machine-translating scientific caveats is precisely what concept §22.4 scores against.

**Current state:** UI chrome is translated and reviewed. Every string that carries a *caveat* will
be listed separately for review before Phase 5, so the review list stays short and specific.

### 19 · Team — the satellite overlay needs a licensing answer

Phase 2 wants a single pre-rendered satellite image via MapLibre `ImageSource` (~300–600 KB,
offline by construction). `scripts/qa_common.py` already has an Esri WorldImagery fetcher.

**The question:** does the Esri Basemap TOU permit committing a rendered extract into this repo?
If not, a Sentinel-2 scene is CC-BY and does. Attribution is required either way.

---

## 🔴 Not a frontend issue, but nobody has closed it

### 20 · Karam / whoever owns the repo — the committed credentials are still recoverable

[`18-risks.md`](Ali/research/18-risks.md) §R6 recorded this on 2 Aug as *partly addressed*.
**Re-checked today, and the state has not changed:** `git show 1819b3e:.env` still resolves, so
the Earthdata, CDS, Copernicus Marine and CDSE credentials remain readable by anyone who can
clone the repository.

`.env` being deleted from the tip does not remove it from history. **Rotating the four
credentials is the only step that closes this**, and it has not been done.

Raised here because it outlives any one workstream, and because a customer's security review
finds it in the history — where *"we removed the file"* is not an answer.

---

---

## Found while merging `main` into `frontend` — 2026-08-03

### 21 · Pulga / Karam — **the API does not start.** 🔴

`docker compose up` brings the api container up unhealthy, and the worker will not
start behind it because of `depends_on: service_healthy`:

```
File "/app/backend/src/api/main.py", line 51, in <module>
    from ..exposure import engine, store
ImportError: attempted relative import beyond top-level package
```

`backend/src/exposure/` exists, so the package is not missing — the **relative**
import is wrong. The container runs uvicorn with `--app-dir /app/backend/src`, which
makes `api` the top-level package, so `from ..exposure` reaches above it. The same
applies to the `..rag` imports on the following lines.

Absolute imports (`from exposure import engine, store`) would resolve, since
`/app/backend/src` is on the path. Not fixed here because it is backend code and one
of you owns it — but **nothing in the compose stack starts right now**, so this
outranks everything else on this list.

Workaround while it stands: `docker compose run --rm --no-deps worker …`.

### 22 · Karam — two parallel GeoJSON exports 🟠

`scripts/export_web_layers.py` (yours) writes nine layers to `data/processed/web/`
and gitignores them. `scripts/13_frontend_basemap.py` (mine) writes twelve to
`frontend/public/basemap/` and commits them.

Mine cannot be gitignored the same way, and that is the constraint rather than a
preference: the compose build context is `./frontend`, so nothing under `data/` is
reachable at image-build time, and DoD item 9 needs the layers present in the image
rather than regenerable. Yours is the better default for everything else.

They should be reconciled so one script feeds both — probably yours, with an output
path flag. Until then two derivations of the same boundaries can drift, which is
exactly what your handoff note warns about.

### 23 · Anyone — `scripts/config.py` was deleted with no replacement 🟠

The spatial constants moved to `backend/src/config/spatial.py`, but the path
constants (`DATA`, `PROCESSED`, `VECTORS`, `FEATURES`) went nowhere, so every script
now resolves its own. `export_web_layers.py` does it inline; my two derivation
scripts now do the same.

That is three copies of `ROOT / "data" / "processed" / "vectors"`. Worth one small
module before it becomes ten.

---

## How to close an item

Edit this file in the same commit that fixes the thing, move the item to the log below, and say
what changed. An open-issues list nobody prunes stops being read.

### Closed

**17 (partly) · reef geometry — closed by contract swap-in #3.** `reef_zones.gpkg`
now carries real Allen Coral Atlas habitat (`ACA/reef_habitat/v2_0`) with
`habitat_class` and `geomorphic_class` populated. Total reef area drops from
5.685 km² to **1.235 km²** — 4.6x smaller — because the provisional 250 m strip was
far more generous than the mapped habitat. The frontend was rebuilt on the new file;
anything still drawing the provisional one overstates the reef by that factor.

**Still open in 17:** `sensitivity_weight` remains 1.0 on all eight zones with status
`PLACEHOLDER_PENDING_MARINE_SCIENTIST`. The geometry and the weighting are two
separate claims and the UI copy now says so separately.
