# Handoff to Pulga — 3 August 2026

Karam here. Both of your Phase 1 blockers are closed and your provenance section is
written. This is what changed while you were away, what you need to re-run, and what is
left that only you can do.

**Nothing in this file is a credential.** See §5 — for Earth Engine you do not need one
from me, because the account is already yours.

---

## 1 · The short version

| Your DoD item | State |
|---|---|
| 1 · Three feature tables at contract paths, fixture deleted | **done** |
| 2 · Real `reef_zones.gpkg` from ACA, IDs verified | **done** |
| 3 · FastAPI serving every §17 endpoint | **5 of 14** |
| 4 · Exposure engine with `formula_terms` | not started |
| 5 · `/explain` bilingual, grounded | not started |
| 6 · `/ask` RAG with citations | not started |
| 7 · Data dictionary: ACA product version + access date | **done** |

So the data under you is real now. **The remaining risk is all in the backend**, not in the
inputs. Items 3–6 are yours and nobody else can start them.

---

## 2 · Read this before you run the exposure engine

### Reef zone areas changed by 4.6×

`reef_zones.gpkg` is now Allen Coral Atlas v2.0 benthic habitat at native 5 m, not
hand-drawn 250 m boxes.

```
total reef area   5.69 km²  ->  1.24 km²
```

The old number was the area of the boxes. The new one is the area ACA maps as habitat.
**Any exposure figure you have already computed is wrong, not merely imprecise**, and the
per-zone ranking changed too, not just the totals.

| zone | was km² | now km² | dominant habitat | in Marine Park |
|---|---:|---:|---|---:|
| R-01 | 0.85 | 0.46 | Coral/Algae 89% | 0% |
| R-02 | 0.81 | 0.04 | Coral/Algae 100% | 0% |
| R-03 | 0.62 | 0.01 | Coral/Algae 100% | 0% |
| R-04 | 0.42 | 0.15 | Coral/Algae 99% | 96.9% |
| R-05 | 0.39 | 0.07 | Coral/Algae 99% | 100% |
| R-06 | 0.54 | 0.19 | Coral/Algae 91% | 100% |
| R-07 | 0.61 | 0.13 | Rock 86% | 92.4% |
| R-08 | 1.44 | 0.20 | Rock 66% | 10.3% |

All 8 IDs survived. Nothing was renumbered, nothing dropped. Max centroid drift 982 m.

### One caveat in your task file is now obsolete

Your task file warns that reef zone widths are a 250 m assumption and that `area_km2` is
therefore order-of-magnitude only, so exposure should be expressed as a *fraction of a
named zone* rather than an absolute area.

**The width assumption is gone** — the outline is ACA's own 5 m polygons. Absolute km²
is now defensible. Expressing exposure as a fraction of a zone is still the better
choice for a different reason: ACA maps shallow reef only, so deeper habitat in a zone is
unrepresented and an absolute "km² affected" silently understates the real habitat at
risk.

### Your schema did not break

The new file is a **superset** of the provisional one. Every column you built against is
still there with the same name and type, so existing code keeps working. New columns:

```
habitat_class            now a readable name ("Coral/Algae", "Rock"), was "unknown"
habitat_class_code       the raw ACA integer, so provenance to the raster survives
habitat_class_mix        full composition by area, e.g. "Coral/Algae:89%;Rock:11%"
geomorphic_class         + geomorphic_class_code
depth_land_cell_pct      NEW — read this before trusting any depth, see below
```

### Depth is now the weakest field, not the geometry

The bathymetry is 50 m; the reef strip is 20–50 m wide. So 39–100% of the bathymetry
cells under a zone read as **land**.

- Depths are medians over **water cells only**.
- **`R-02` is `NaN`** — it has no water cell at all. Not 0, and not the +10 m the raw
  cells would give you. Handle `NaN` explicitly; do not coerce it.
- **Do not quote R-03's −179.7 m.** It rests on 2 cells over a 0.01 km² zone.
- Check `depth_land_cell_pct` before using any depth in a formula or on screen.

### `sensitivity_weight` is still 1.0

Unchanged, and still `PLACEHOLDER_PENDING_MARINE_SCIENTIST` in the schema itself. Real
habitat arriving is **not** a licence to derive a weight from it. `habitat_class` and
`marine_park_overlap_pct` are exactly the measured inputs a marine scientist needs in
order to set it — hand those over, do not convert them yourself. Swap #5 is still open.

---

## 3 · Two audit files you may find useful

Alongside `reef_zones.gpkg`:

```
aca_fragments_BEFORE_MERGE.gpkg   raw polygonized ACA, before any assignment decision
aca_pieces_ASSIGNED.gpkg          every piece, which zone it went to, and whether it
                                  got there by overlap or by snap
```

If someone asks in the Q&A why a zone is the size it is, the second file is the answer.

---

## 4 · What I changed in your scripts, and why

I edited `scripts/export_aca.py` and `scripts/qa_marine.py`. Your design notes are intact
— where I disagreed I said so in a comment rather than deleting your reasoning. Four
defects, each of which produced a **plausible wrong number with no error**:

1. **Fragments were assigned whole to the zone they overlapped most.** ACA polygonizes
   Aqaba's continuous fringing reef into a few very long strips that run through several
   zones. Each went entirely to one winner. R-05 (Japanese Garden, a well-known reef) came
   out at **475 m²** while 0.068 km² of reef sat inside its box, credited to R-04 and
   R-06 — which were in turn credited with reef outside theirs. Pieces are now cut at
   zone boundaries, guarded by an area-conservation assert.

2. **`habitat_class` held the raw integer** (`ACA_benthic_13`) in a text column that
   reaches the map popup, Postgres and your RAG answers. Class tables are now read off
   the live Earth Engine asset and re-verified on every build. Worth knowing: geomorphic
   `22` is *Reef Slope*, and the plausible guess — *Back Reef Slope*, which is `24` —
   would have mislabelled five of the eight zones with nothing to indicate it.

3. **Dominant class was counted by piece, not by area.** Polygonizing a raster gives one
   big patch plus a scatter of single-pixel specks, so 25 rock specks outvoted the coral
   patch that *is* the zone. R-08 read `Rock:59 / Coral:47` by count — a meaningless
   near-tie — versus `Rock:66% / Coral:34%` by area.

4. **Geometry-dependent attributes were inherited from the provisional file.** So
   `marine_park_overlap_pct` described a hand-drawn box rather than reef, and
   `depth_min_m`/`depth_median_m` were dropped entirely, which broke `qa_marine`'s
   per-zone insets. Both are recomputed now.

Also: reef within 100 m of a zone but inside none is snapped to the nearest zone,
recovering 0.71 km² the boxes had clipped off. The zones turn out to be a **contiguous
chain 24–50 m apart** (R-07/R-08 touch), so 15 pieces totalling 0.011 km² are near two
zones and take the nearer — asserted to happen only between *adjacent* zones.

`qa_marine.py` now prefers `reef_zones.gpkg` when it exists and states in each figure's
caption which file it was drawn from. All 34 QA figures are regenerated.

New tests: `tests/test_aca_zone_merge.py`, 12 of them. Suite is at **421 passing**.

---

## 5 · Earth Engine and GCP — you do not need a credential from me

The Earth Engine account already in use is **yours**: `pulgateam9xai@gmail.com`, project
**`reefshield-aqaba-504406`**. Contract §4 P6 is explicit that each person registers their
own project and there is deliberately no shared one. So on your machine:

```bash
.venv/bin/python -c "import ee; ee.Authenticate()"     # browser, sign in as pulgateam9xai
export EARTHENGINE_PROJECT=reefshield-aqaba-504406     # or pass --project
```

Then `export_aca.py submit / status / build` all work. Two things that cost time here, so
you do not repeat them:

- **The OOB flow is dead.** Google blocked `urn:ietf:wg:oauth:2.0:oob` in 2022, so if a
  guide tells you to paste a code into the terminal, it will fail with *Access blocked:
  Authorization Error*. Use the localhost flow, which is what `ee.Authenticate()` does by
  default now.
- **A duplicate project `reefshield-aqaba-504318` exists — ignore it.** Use `…-504406`.

The exports are already done and their GeoTIFFs are on disk, so you do not need to re-run
any of this unless you want a different region. `data/raw/` is git-ignored, so if you want
the rasters locally, re-export rather than expecting them in a pull.

### On the other credentials

I am not putting secrets in this file or anywhere in the repo, and neither should you —
`docs/data_access_setup.md` says never paste a password, key or token into chat, a
screenshot, a commit message or a log line, and git history cannot be un-published by
deleting a file later. The names you may need are in `.env`, which is git-ignored:

```
EARTHDATA_USERNAME / EARTHDATA_PASSWORD        NASA, for IMERG
CDSAPI_URL / CDSAPI_KEY                        Copernicus, for ERA5-Land
SUPABASE_DB_URL / DATABASE_URL                 Nizar's Postgres
EARTHENGINE_PROJECT                            yours, value above — not a secret
```

Ask for any actual value out of band, not here and not in the repo. **Separately: the
Earthdata password, the CDS token and the Supabase superuser password have each been
exposed in a chat transcript and rotation is still outstanding.** That is on my list, not
yours, but do not treat those three as safe.

---

## 6 · What I would do first, in order

1. **Re-run the exposure engine** against the new `reef_zones.gpkg`. Nothing else you do
   is meaningful until the areas are right.
2. **The 6 August vertical slice needs shapes, not correctness.** Your task file's own
   priority: `health` · `catchments` · `reef-zones` · `events` · one *stubbed* exposure
   response. Ali needs a fixed payload shape far more than he needs real numbers. Nine
   endpoints are still missing, and `reef-zones` and `events` are both trivial now
   because the files behind them are real and final.
3. **Pin the Pydantic models early.** They are the contract between you and Ali. He
   cannot build against a moving shape.
4. **Make the caveats travel as data.** `sensitivity_weight` is a placeholder, `AQ-O04`
   discharges into an enclosed harbour basin, catchment area carries ±4%, and now
   `depth_median_m` can be `NaN` and ACA maps shallow reef only. Those belong in the
   payload, not in a doc nobody opens during a demo.
5. Exposure engine, then `/explain`, then `/ask`.

Measure every area and distance in **EPSG:32636**, never in degrees. Draw in 3857 if you
like, but measure in 32636 — this already cost 14.8% on culvert distances once.

---

## 7 · What is still moving underneath you

- **ERA5-Land sweep: 24 of 84 months.** Labels exist for 7 events so far. This limits what
  Mahdi can train on, not what you can serve.
- **`sensitivity_weight`** stays 1.0 until a marine scientist rules, or it ships labelled
  as an assumption on the slide. Contract §5 swap #5.
- **Abd's real plume mask** is swap #4 and still open, so the exposure engine's plume
  input is provisional. Build against the shape, not the values.
- **Supabase**: the direct host `db.<ref>.supabase.co` publishes an AAAA record only and
  this machine has no global IPv6, so it is unreachable from here. Nizar needs to supply
  a **pooler** connection string (IPv4, username `postgres.<project_ref>`).

Ping me on anything at the seams — that is my job this phase.
