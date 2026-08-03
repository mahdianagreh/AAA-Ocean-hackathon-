# Vertical slice — dry run, 3 August 2026

Karam, integration lead. The slice is due **6 August, three days out**. This is a
*measured* status, not an estimate: I built the image and hit the endpoints. Every
verdict below has a command behind it.

**Headline: the slice is closer than I expected. The backend containerises and serves
real data today.** Four endpoints are missing and two of them are mine to unblock in
minutes.

---

## 1 · What actually works, verified

```bash
docker compose build api          # succeeds, ~2.5 min cold
docker run -d -p 8099:8000 -v "$PWD/data:/app/data:ro" reefshield-api:latest
curl localhost:8099/health        # 200 in ~1 second
```

| check | result |
|---|---|
| `docker compose build api` | **passes** |
| container reaches healthy | **~1 s** |
| `GET /health` | **200** |
| `GET /api/v1/catchments` | **200, real data** — 5 catchments, Wadi Yutum 4453.08 km² |
| `GET /api/v1/outlets` | **200, real data** — 5 outlets, 2 verified against imagery |
| `data_volume_mounted` | **true** with `-v`, false without, and it says so |

Two things in here are better than they had to be, and both are worth keeping:

**The caveats travel as data.** `/api/v1/catchments` returns `position_confidence` and
`caveat` per row, including the AQ-O04 harbour-basin warning. That is the contract
requirement actually met, not documented.

**Absent data degrades honestly.** There is an embedded contract-value fallback, disk is
preferred when mounted, and the `source` field states which was used —
`"embedded contract values — data volume not mounted"` versus
`"data/processed/vectors/outlets.geojson"`. `data/` is git-ignored, so without this
pattern a teammate's fresh clone would have served silent placeholder geometry. It does
not.

**`/api/v1/models` returns 503 with instructions**, not a stack trace: *"no trained model
registered … Ledger: data/models/model_versions.jsonl (absent or empty)"*. A blocked
dependency reporting itself clearly is the correct behaviour.

---

## 2 · What is missing

| endpoint | status | owner | effort |
|---|---|---|---|
| `GET /api/v1/reef-zones` | **404** | Pulga | minutes — data is final as of today |
| `GET /api/v1/events` | **404** | Pulga | minutes — `events.parquet` is final |
| `GET /api/v1/data-sources` | **404** | Pulga | small — reads `docs/data_dictionary.md` |
| `GET /api/v1/alerts` | **404** | Pulga | needs the exposure engine |
| `POST /api/v1/plume/simulate` | absent | Pulga + Abd | blocked on swap #4 |
| `POST /api/v1/exposure/calculate` | absent | Pulga | **stub it for the slice** |
| `POST /api/v1/backtests/run` | absent | Pulga | after the slice |
| `POST /api/v1/explain`, `/ask` | absent | Pulga | after the slice |
| trained model | `503` | Mahdi | see his handoff |
| frontend | no `frontend/` dir | Ali | **nothing pushed** |

### The two I can hand over immediately

`reef-zones` and `events` need no new data work — both files are final and committed:

```
data/processed/vectors/reef_zones.gpkg              8 zones, real ACA habitat
data/processed/events/events.parquet                100 storms, is_exhaustive
```

Pulga can serve both by copying the `catchments` handler pattern. These are the two the
slice most needs, because a map with reef zones and a storm list *is* the demo's
first screen.

### One inconsistency Ali will hit

Health lives at **`/health`**, not `/api/v1/health`, while everything else is under
`/api/v1/`. The task file lists `GET /api/v1/health`. Pick one and tell Ali before he
hardcodes the wrong one — I'd add `/api/v1/health` as an alias and keep `/health` for the
Docker healthcheck, which already depends on it.

---

## 3 · Docker: further along than the task list suggests

Mahdi's DoD item 6 is not the risk I flagged this morning. `backend/Dockerfile` and
`docker-compose.yml` exist (commit `4a411ed`), with:

- two targets from one base — slim `api`, `worker` with the geospatial stack
- requirements copied before code, so a code edit does not rebuild dependencies
- non-root user, healthcheck via curl, `proj-data` installed for the UTM 36N transforms
- **the frontend behind a Compose profile**, so `docker compose up` works for everyone
  *before* Ali's directory exists — a genuinely thoughtful call

**Two open questions on item 6, which specifies wifi off:**

1. **`data/` is a bind mount, not baked into the image.** Fine on our machines, fatal on
   a judge's laptop or a fresh clone, because `data/` is git-ignored. Decide before the
   12th: bake the demo subset into the image, or ship a documented volume.
2. **The MapLibre basemap is the classic offline failure.** Ali's map goes grey with wifi
   off unless tiles are bundled. Nobody owns this yet. It needs an owner today.

### One local snag, not a code problem

`docker compose up api` failed with `Bind for 0.0.0.0:8000 failed: port is already
allocated` — something else on my machine holds 8000. Not a repo defect; I tested on 8099.
Worth knowing so nobody debugs the Dockerfile over it.

---

## 4 · A gap that would have bitten later

**`fastapi` and `uvicorn` are not in `.venv`.** The API only runs in Docker on this
machine — `from api.main import app` fails with `ModuleNotFoundError` outside the
container.

That is survivable but it means the API is not covered by `pytest`, so all 429 tests pass
without ever importing the app. A broken route would not be caught by the suite. Either
add the API deps to the dev environment and write endpoint tests, or accept the gap
knowingly. I would add them — endpoint tests are cheap and the slice depends on shapes
being right.

---

## 5 · Verdict

**Can the slice run on 6 August? Yes, if two people move.**

The path is: Pulga adds `reef-zones` + `events` + a stubbed `exposure/calculate`, and Ali
creates `frontend/` and draws against those shapes. Both are small. The backend, the
container and the real data underneath are done.

**What would sink it:** Ali has pushed nothing at all. Backend endpoints without a
frontend is not a vertical slice. That is the single highest-risk item on the board right
now — above the trained model, above the exposure engine — because it is the one with no
partial credit and no substitute.

**Priorities, in order:**

1. **Ali starts `frontend/` today.** Shapes over correctness — stub payloads are fine.
2. **Pulga: `reef-zones`, `events`, stubbed `exposure`.** Data is ready and final.
3. **Resolve `/health` vs `/api/v1/health`** before Ali hardcodes it.
4. **Assign the offline basemap** to someone by name.
5. **Mahdi: rule baseline** — see `HANDOFF_mahdi_2026-08-03.md`, especially the target
   definition.

## Reproduce this audit

```bash
docker compose build api
docker run -d --name rs-api-test -p 8099:8000 -v "$PWD/data:/app/data:ro" reefshield-api:latest
for p in /health /api/v1/health /api/v1/data-sources /api/v1/catchments \
         /api/v1/reef-zones /api/v1/events /api/v1/alerts /api/v1/models; do
  printf '%s  GET %s\n' "$(curl -s -o /dev/null -w '%{http_code}' localhost:8099$p)" "$p"
done
docker rm -f rs-api-test
```
