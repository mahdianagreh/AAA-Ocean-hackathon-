# Running the stack

```bash
cp .env.example .env      # fill in the Supabase keys
docker compose up --build
```

That brings up two services. `curl localhost:8000/health` should answer.

| Service | Port | What it is |
|---|---|---|
| `api` | 8000 | FastAPI. Geometry, model serving, health |
| `worker` | — | Long jobs: pipeline runs, simulations. Exposes nothing; it picks work up |
| `frontend` | 5173 | Behind a profile until Ali's shell exists |

```bash
docker compose --profile frontend up    # once frontend/ exists
docker compose logs -f worker
docker compose exec api sh
```

## There is no database container

The stack talks to **Supabase Cloud**. This is a decision, not an omission:
**the demo needs a live connection.** The concept doc's risk register rates
"data downloads fail during demo" as medium probability / high impact, and
conference wifi is exactly that scenario. If it bites, the fix is a
cached-fixture fallback in `api` rather than reinstating Postgres.

## Two images, one Dockerfile

`api` carries serving dependencies only — small, and the layer that gets
rebuilt constantly. `worker` adds the geospatial stack. Requirements are
copied before source so a code change doesn't invalidate the dependency layer.

**Python 3.12 in the container, not the host's 3.14.** The geospatial wheels
are mature there, and the container not needing to match the build machine is
most of the point of containerising.

## Pinning

Both requirement files are pinned exactly, and resolved by pip rather than
written by hand — two build failures came from invented version numbers
(`pandas==2.3.4` does not exist) and from a version with no cp312 wheel
(`rasterio==1.4.3`, which fell back to a source build and demanded
`gdal-config`). To re-resolve:

```bash
docker run --rm python:3.12-slim sh -c \
  "pip install -q --only-binary=:all: geopandas rasterio shapely pyproj && pip freeze"
```

`--only-binary=:all:` is also in the worker image build, so a source build
fails at resolve time instead of surfacing as a missing system library.

## Hardening

Both containers run as a non-root user. `api` mounts `data/` **read-only** —
it reads geometry and model artifacts and must never be what writes to
`data/`. Only `worker` gets write access.

## Verified

```
api      Up (healthy)          non-root, data/ read-only, write refused
worker   Up                    geopandas 1.1.4, rasterio 1.5.0, pyproj 3.7.2
                               reads catchments.gpkg: 5 rows, 4,656 km²
                               EPSG:4326 -> 32636 transform works
POST /api/v1/runoff/predict -> 503, naming the missing matrix
```
