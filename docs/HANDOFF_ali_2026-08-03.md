# Handoff to Ali — 3 August 2026

Karam. Straight to it: **you are the critical path.** Three days to the 6 August vertical
slice, ten to the deadline, and `frontend/` does not exist yet.

That is not a criticism — your task file said you were blocked on Pulga's endpoints until
Day 3. But a backend with no frontend is not a vertical slice, and yours is the one item
on the board with **no partial credit and no substitute**. Everyone else can ship
something rough. A missing UI is a missing demo.

So: I have removed the two things that were actually blocking you. Read §1 and §2, then
start the shell today.

---

## 1 · Your map layers are ready — I converted them for you

**MapLibre cannot read a GeoPackage**, and every vector layer in the repo was `.gpkg`
except one. That was a real blocker and it was mine to fix. Now:

```bash
../.venv/bin/python scripts/export_web_layers.py     # ~5 seconds
```

writes to `data/processed/web/`, all in **EPSG:4326**, all loadable straight into a
MapLibre `geojson` source:

| file | features | size | what it is |
|---|---:|---:|---|
| `catchments.geojson` | 5 | 620 KB | `AQ-C01`…`AQ-C05` |
| `reef_zones.geojson` | 8 | 234 KB | `R-01`…`R-08`, **real ACA habitat as of today** |
| `shoreline.geojson` | 1 | 70 KB | coastline |
| `water.geojson` | 1 | 71 KB | sea polygon |
| `marine_park.geojson` | 2 | 8 KB | Aqaba Marine Park boundary |
| `dive_sites.geojson` | 75 | 39 KB | dive/tourism POIs |
| `drainage_features.geojson` | 200 | 149 KB | wadi drainage lines |
| `port.geojson` | 1 | 4 KB | port area |
| `observed_plume_PROVISIONAL.geojson` | 110 | 144 KB | **provisional** — see §5 |

**1.3 MB total.** No simplification applied to any of it — a simplified boundary is a
different claim about where a catchment is, so the default is untouched geometry. There is
a `--simplify` flag, but only for roads and buildings (`--include-heavy`), and it records
the tolerance in `manifest.json` so nobody mistakes altered geometry for source geometry.

The directory is **git-ignored**. Regenerate it, do not commit it — two copies of every
boundary is how they drift apart.

> **`drainage_features` is not "culverts".** It has 200 features; only **27** are tagged
> culverts. If you put "culverts" on a legend next to 200 dots, that number is wrong and
> someone will ask about it.

---

## 2 · Two endpoints work right now, with real data

I ran the API in Docker and hit it. These two are live and return real values today:

```
GET /api/v1/catchments     200
GET /api/v1/outlets        200
```

Real response, `catchments[0]` — build your types off this, not off a guess:

```json
{
  "catchment_id": "AQ-C01",
  "name": "Wadi Yutum",
  "area_km2": 4453.08,
  "outlet_id": "AQ-O01",
  "lon": 34.97073,
  "lat": 29.5456,
  "position_confidence": "plausible",
  "caveat": "Engineered Wadi Yutum flood channel; mouth verified at the shoreline. Area carries ±4% from separating endorheic basins from DEM artifacts."
}
```

`outlets[0]` additionally carries `culvert_verdict`, `unmodelled_coastal_culverts`,
`nearest_culvert_m` and `upstream_km2`.

**`position_confidence` and `caveat` are in every row on purpose.** They are not
documentation that happens to be in the payload — they are the design. Put them on screen:
a badge on the marker, the caveat in the popup. `AQ-O02` is `"low"` confidence because its
channel crosses reclaimed land; if the UI renders all five outlets identically, the map
makes a claim the data does not support. Sizing outlets by `upstream_km2` is in your task
file and works today.

### Still 404 — these are Pulga's, not yours

`reef-zones` · `events` · `data-sources` · `alerts`. The first two are minutes of work for
him because the underlying files are final. **In the meantime load
`reef_zones.geojson` from §1 directly** — do not wait on the endpoint to start the map.

### One thing to settle before you hardcode it

Health is at **`/health`**, not `/api/v1/health`, while everything else is under
`/api/v1/`. Your task file implies the prefixed one. Ask Pulga to add the alias rather
than guessing — and do not build a health indicator against the unprefixed path only.

---

## 3 · The offline basemap — this one is yours and nobody has it

Mahdi's DoD item 6 and your item 9 both require the demo to work with **wifi off**. The
classic failure is exactly your layer: **MapLibre's basemap tiles come from the network,
so the map goes grey.** Everything else can be baked into the image; tiles are the piece
that gets forgotten until the day.

Nobody owns this yet. I am assigning it to you because it is inside your stack, but tell
me today if you want it moved.

Cheapest options, roughly in order:

1. **No raster basemap at all.** You already have `shoreline`, `water`, `port` and
   `drainage_features` as vectors. A clean cartographic style over the sea polygon may
   honestly look *better* than a satellite tile, and it is bulletproof offline.
2. **A small bundled raster** for the ~25 × 40 km AOI at a couple of zoom levels, shipped
   in the image.
3. **A local tile server** in Compose — most faithful, most work.

I would take option 1 and spend the time saved on the panels in §4. Do not leave this to
the 12th.

---

## 4 · The panels are what separate this from a pretty map

Your task file is right that these matter more than polish, and three of them are **already
sitting in the repo** — you are not blocked on anyone:

- **Provenance panel** — `docs/qa_screenshots/` has **37 figures** (your task file says 34;
  it is 37 now) with captions in `MANIFEST.md` and machine-readable captions in
  `manifest.json`. Every caption is burned into the image itself, so a figure stays
  self-explanatory if someone screenshots it out of context. Read `manifest.json` and
  render the gallery from it — do not retype captions.
- **Limitations page** — `docs/data_dictionary.md` has a "Known limitations" block per
  dataset, and `docs/forcing_limitations.md` has the plume wording. Quote them; do not
  paraphrase. Paraphrasing a limitation is how it stops being true.
- **Validation panel** — the honest story is stronger than a pass/fail badge. See §5.

---

## 5 · Three things you must not render as more certain than they are

**The plume is a probability field, never a line.** The best free ocean model is ~9 km
across a gulf 15–25 km wide — two to three cells span the whole basin, and our own release
point sits on a cell the model masks as land. A single confident trajectory would be a
claim the data cannot support. Contoured probability with the confidence stated, always.

**`observed_plume_PROVISIONAL.geojson` is in the filename for a reason.** It is Abd's
placeholder, swap #4, not a satellite observation. If it reaches the screen it must be
labelled provisional in the UI too — the filename does not travel to the viewer.

**The satellite validation is a null result, and say so.** The plume dispersed ~31 h after
arrival and the only usable passes are +104 h and +128 h. Two sensors, no plume. That is
not a gap to hide: the replacement is stronger — the Kalman et al. (2025) mooring 250 m off
the Kinnet Canal at 13 m depth, sampling every 5 minutes, which recorded salinity −1.75 ‰
(19σ) and a turbidity peak of 2.18 g/L elevated for ~31 h. "We looked, the satellite could
not see it, so we validated against a mooring instead" is a *better* slide than a vague
claim of satellite confirmation, and it survives questioning.

**`sensitivity_weight` is 1.0 for every reef zone** and labelled
`PLACEHOLDER_PENDING_MARINE_SCIENTIST` in the data itself. If exposure scores appear
weighted by habitat sensitivity, they are not. Show the placeholder as a placeholder.

---

## 6 · What changed today that touches your UI

Reef zones became **real Allen Coral Atlas habitat**. Total area fell **5.69 → 1.24 km²**
because the old figure was the area of hand-drawn boxes. All eight IDs survived and none
were renumbered, so nothing in your code breaks — but:

- Zones are now **narrow, irregular fringing strips**, not tidy rectangles. At low zoom
  R-03 (0.01 km²) and R-02 (0.04 km²) will be nearly invisible. Give small zones a minimum
  hit area and consider a zoom threshold that switches to centroid markers, or they become
  unclickable.
- `habitat_class` is now a readable name — `"Coral/Algae"`, `"Rock"` — and
  `habitat_class_mix` gives the composition as percentages, e.g.
  `"Coral/Algae:89%;Rock:11%"`. Good popup content.
- `depth_median_m` can be **`NaN`** (R-02 has no water cell in the 50 m bathymetry under a
  5 m reef strip). Render that as "not measurable at this resolution", never as `0` and
  never as an empty string. `depth_land_cell_pct` says how much of the zone the bathymetry
  reads as land.

---

## 7 · Do this today

1. **Create `frontend/`** with a Dockerfile. It is already wired into
   `docker-compose.yml` behind a `frontend` profile, so `docker compose --profile frontend
   up` will pick it up the moment the directory exists. Mahdi left that door open for you.
2. **Map shell + the §1 GeoJSON layers.** Catchments, reef zones, shoreline, outlets. No
   API needed for any of it.
3. **RTL from the first component.** Your own task file is emphatic and it is right — a
   late translation pass means rewriting layout in the final three days. Logical CSS
   properties (`margin-inline-start`, not `margin-left`), `dir` on the root, and check one
   real screen in Arabic today rather than all of them on the 12th.
4. **Wire `/api/v1/catchments` and `/outlets`** — real data, and it proves the container
   networking works.
5. **Decide the basemap** per §3.

Stub everything else with a fixed payload. For the slice, **shapes beat correctness** —
a screen that draws the right regions with placeholder numbers is a passing slice; a
perfect number with no screen is not.

Anything ambiguous at the seams is mine. Ask rather than guess, especially about response
shapes — that is faster than either of us reverse-engineering the other.

---

## 8 · One note on `docs/ali/`

Your MENA and global analogue research is **pitch and research material, not an app
surface**. It is not in the RAG corpus and should not become a screen. Use it for the
narrative and the slides.
