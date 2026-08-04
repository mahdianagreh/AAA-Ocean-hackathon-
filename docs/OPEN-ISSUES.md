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

**Frontend workaround, in place now:** [`scripts/frontend_basemap.py`](../scripts/frontend_basemap.py)
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

### 3 · Mahdi — SHAP drivers as objects with stable keys ✅ CLOSED 2026-08-03 — by the frontend

Day-1 ask #5. `runoff_model.py:219-226` returns `{feature, shap, value}` where `feature` is a raw
parquet column name. The frontend needs `{key, contribution, value}` where `key` is a stable i18n
key — a pre-rendered English label cannot become Arabic at render time, and DoD item 8 is
bilingual with working RTL.

**It was the rename this item guessed it might be, so the frontend did it** rather than ask
Mahdi to change a shape that is fine on its own side. `riskFromPredictions` maps
`feature → key`, `shap → contribution`, and wraps `value` in a `Value` with its provenance.

The half that was *not* free: raw column names are only usable as i18n keys **if the keys
exist**. They did not, so the first render of real model output put `driver.season_cos` on
screen in both languages. All 20 model features now have EN and AR labels — not just the 9 that
happened to reach the top-4 SHAP ranking on these rows, because any of the 20 can surface on
another event. `season_cos` reads *"Season (annual cycle, offset)"* / *"الموسم (الدورة السنوية،
بإزاحة)"*.

**Standing requirement on Mahdi:** a new feature in a retrained model needs a translation pair
added here, or it renders as its own key. There is no automatic fallback that could be honest —
a raw parquet column name is not a label in either language.

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

#### Updated 2026-08-03 — the suite has now actually been run, and here is how

The worker image cannot run it either: **no `pytest`, `xarray`, `httpx`, `earthaccess` or
`cdsapi`**, and the worker mounts only `./data`, `./backend/src` and `./scripts` — so `tests/`,
`configs/` and `docs/` are not even reachable inside the container. Nine of the thirteen initial
failures were that, not code: `ConfigError: Config file not found: /app/configs/…`.

With the deps installed and the three directories mounted, the real result is:

```bash
docker compose run --rm --no-deps --entrypoint "" \
  -v "$PWD/tests:/app/tests:ro" -v "$PWD/configs:/app/configs:ro" -v "$PWD/docs:/app/docs:ro" \
  -e PYTHONPATH=/app/backend/src worker \
  sh -c "pip install -q pytest xarray httpx earthaccess cdsapi >/dev/null 2>&1; \
         python -m pytest /app/tests -q -p no:cacheprovider"

# 4 failed, 421 passed, 49 skipped
```

**So the honest figure is 421 passing, not 433.** The 433 was `grep -c 'def test_'`, and it counts
49 skips and 4 failures as passes. This item predicted that exact mistake and I still had the grep
number in a doc; it is now corrected to the measured one.

The four failures are real and are **item 24**. Also note **49 skipped** — a quarter as many again
as the frontend's entire suite, and nobody has looked at why.

### 10 · Mahdi — the worker cannot write to `frontend/`

`docker-compose.yml` mounts `./data`, `./backend/src` and `./scripts` into the worker, so there is
no `/app/frontend` in the container. The basemap derivation therefore needs an ad-hoc mount:

```bash
docker compose run --rm --entrypoint "" \
  -v "$PWD/frontend/public/basemap:/out" \
  worker python /app/scripts/frontend_basemap.py --out /out
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

### 15 · Mahdi — `data/models/` does not exist, so two endpoints 503 ✅ CLOSED 2026-08-03

**Mahdi registered a real artefact.** `git pull` brought `data/models/model_versions.jsonl` with:

```
runoff_weighted_gbm_2194b48_20260803T214757Z
leave-one-catchment-out   mean AP 0.7474   baseline 0.2004
is_synthetic: false   ·   2,362 training events   ·   20 features
```

So the frontend no longer renders a 503 state on the risk cards. `scripts/frontend_predictions.py`
runs that artefact over the demo window — 5 catchments × 5 days, 25 predictions, zero failures —
and commits the output to `frontend/public/fixtures/predictions.json`. The cards now show the
model's own probabilities and SHAP attributions, tagged with the version id.

What was blocking it turned out to be the wrong table, not a missing one. The 503 body named
`event_catchment_features.parquet`, which is genuinely short two required columns — but
`training_set_full.parquet` carries **all 20** model features and covers the demo window. That is
what the derivation reads.

The stand-in index survives in exactly one place: **what-if mode.** The predictions are model
output at fixed inputs, and the browser cannot re-run a GBM against a moved transmission-loss
slider, so moving a control falls back to the labelled index with `runoff_probability` null. Every
card states which of the two it is showing, and a test asserts it can never be neither or both.

Still owed by this item, and now item 4's problem alone: the model reports a single `confidence`
float rather than its components, so the meter shows it against 1.0 and says so. Composing
"22 of 30 members" from one number would be inventing an ensemble.

### 16 · Pulga — the API has no tests ✅ CLOSED 2026-08-03 — Pulga wrote them

`tests/test_api_contracts.py` exists (commit `75b75f2`), uses `TestClient`, and covers stub
flagging, the exposure formula terms, unreached zones and stored alert runs. Exactly what
[`07-data-contracts.md`](Ali/frontend/07-data-contracts.md) §5 asked for.

**It is red, and that is item 24 — four of its own assertions fail.** Which is the test suite
doing its job: it caught a real contract defect that nobody had seen, because nobody had run it.

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

### 22 · Karam — two parallel GeoJSON exports ✅ CLOSED 2026-08-03

**Resolved by deleting mine.** `scripts/export_web_layers.py` is gone;
`scripts/frontend_basemap.py` is the single derivation.

You had the constraint right and I had written mine before yours existed — it was
scaffolding to unblock the map, and that need has passed. Yours also turned out to be
the better artefact rather than merely the necessary one: `places.geojson` already
carries the dive sites with `name_ar` / `name_en`, and `protected.geojson` the Marine
Park the same way, so it satisfies the bilingual DoD that mine quietly did not. Two
derivations of the same boundaries is exactly the drift I warned Ali about, and keeping
the one that must be committed anyway is the only version that removes it.

Three layers existed only in mine and are **not** in `frontend/public/basemap/`. None is
needed for the slice, so they are a note rather than a blocker — add them if a screen
calls for them:

| layer | source | note |
|---|---|---|
| `observed_plume_PROVISIONAL` | `observed_plume.gpkg` | swap #4, must be labelled provisional in the UI |
| `drainage_features` | `osm_aqaba.gpkg:drainage_features` | 200 features, of which only 27 are culverts — do not label it "culverts" |
| `port` | `osm_aqaba.gpkg:port` | R-02 context |

### 23 · Anyone — `scripts/config.py` was deleted with no replacement 🟠

The spatial constants moved to `backend/src/config/spatial.py`, but the path
constants (`DATA`, `PROCESSED`, `VECTORS`, `FEATURES`) went nowhere, so every script
now resolves its own. `export_web_layers.py` does it inline; my two derivation
scripts now do the same.

That is three copies of `ROOT / "data" / "processed" / "vectors"`. Worth one small
module before it becomes ten.

---

### 24 · Pulga — **`/api/v1/runoff/predict` 500s on the model's own honest answer.** 🔴

Found by running Pulga's own `test_api_contracts.py` for the first time (item 16). Four of its
assertions fail, and they are one bug:

```
pydantic_core.ValidationError: 1 validation error for RunoffPrediction
sediment_class
  Input should be 'low', 'moderate', 'high' or 'extreme'
  [type=literal_error, input_value=None, input_type=NoneType]
```

[`api/main.py:388`](../backend/src/api/main.py#L388) reads:

```python
sediment_class=real.get("sediment_class", "moderate"),
```

**`dict.get(k, default)` only substitutes when the key is *absent*.** `runoff_model.predict_one`
includes the key with an explicit `None`, so `.get` returns `None`, and `RunoffPrediction`
declares the field as a required `Literal` with no `None` member. The response cannot serialise.

This is the "missing is not zero" rule, in the backend, breaking a request. And the intended
fallback is the worse half of the bug: **defaulting an unanchored sediment class to `"moderate"`
would fabricate a claim.** The model returns `None` precisely because it cannot support a class —
its own `sediment_basis` says so:

> `UNANCHORED - index is comparable between requests, but no absolute class exists. Anchor the
> proxy at training time on AQ-2016-10-28 / AQ-C01 (~24,400 t).`

**How much this matters: all 25 of 25** predictions in the demo window carry
`sediment_class = null`. So the endpoint would 500 on **100%** of the demo, not on an edge case.

**Done looks like:** `sediment_class: Literal[...] | None` on the response model, and the `.get`
default dropped rather than changed — a null here is the answer, not a gap to fill.

**Why the frontend is not blocked:** `frontend/src/api/predictions.ts` types it
`string | null` and renders null as a declared gap, and the predictions are derived offline from
the artefact directly rather than through the API. That decision was made for item 21 (the API
does not start) and DoD item 9 (no network, no API) — it happens to route around this too. Which
is luck, not design: had the API been reachable, every prediction in the demo would have 500'd.

---

## How to close an item

Edit this file in the same commit that fixes the thing, move the item to the log below, and say
what changed. An open-issues list nobody prunes stops being read.

### Closed

**15 · `data/models/` is empty — closed by Mahdi registering a real artefact.**
`runoff_weighted_gbm_2194b48_20260803T214757Z`, LOCO mean AP **0.7474** against a
0.2004 baseline, `is_synthetic: false`. 25 predictions derived over the demo window
and committed. The risk cards show model output tagged with the version id; the
stand-in index survives only in what-if mode, labelled. This was the single largest
honesty gap in the interface — the cards previously rendered every probability as a
declared gap, which was correct but was not a product.

**3 · SHAP drivers as stable keys — closed by the frontend, not by Mahdi.**
The rename was the trivial half. The real work was the 20 EN/AR label pairs the keys
needed to exist against; without them the first render of real model output showed
`driver.season_cos` on screen in both languages.

**17 (partly) · reef geometry — closed by contract swap-in #3.** `reef_zones.gpkg`
now carries real Allen Coral Atlas habitat (`ACA/reef_habitat/v2_0`) with
`habitat_class` and `geomorphic_class` populated. Total reef area drops from
5.685 km² to **1.235 km²** — 4.6x smaller — because the provisional 250 m strip was
far more generous than the mapped habitat. The frontend was rebuilt on the new file;
anything still drawing the provisional one overstates the reef by that factor.

**Still open in 17:** `sensitivity_weight` remains 1.0 on all eight zones with status
`PLACEHOLDER_PENDING_MARINE_SCIENTIST`. The geometry and the weighting are two
separate claims and the UI copy now says so separately.
