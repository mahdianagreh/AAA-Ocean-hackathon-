# PULGA — LEGENDARY PHASE 2 PLAN
## Backend · Exposure Engine · RAG — ReefShield Aqaba
### Workstream 4 of 6 · Window: 2 → 13 August 2026

---

## 0. STANDING LAW — carried over from Phase 1, non-negotiable in Phase 2

These seven rules (from `00-phase2-plan.md`) are why your Phase 1 work was trusted enough to
be the thing every other stream builds on. They do not relax now that there's an API and a
UI in front of your numbers — if anything they matter more, because a wrong number in a
parquet file is a bug; a wrong number on a judge's screen is the whole pitch.

1. **Missing is never zero, and nothing is interpolated.** A gap is reported as a gap.
2. **No fabricated geometry, ever.** If an input doesn't exist, the step is skipped and the skip is recorded.
3. **Provisional data is named `*_PROVISIONAL`**, and swapping it is a tracked checklist item.
4. **Every claim has evidence.** Processing scripts assert; QA scripts visualise. No figure, no test → assumed, not verified.
5. **Source vs derived is labelled.** A paper number, a converted number, and a computed number are three different things.
6. **Provenance is not bookkeeping.** Every product ID, version, access date, licence, and limitation goes in `docs/data_dictionary.md` and drives the UI's Data Sources panel.
7. **Never claim exactness.** Probabilistic, stated confidence, said before a judge finds it.

**Your Phase 1 addition to this law, now formalized as a standing rule for Phase 2:** *if two
independently-produced artifacts disagree, that disagreement is the signal, not noise.* This
is literally how you caught the EPSG:3857 culvert-distance bug. Build cross-checks into the
backend and exposure engine on purpose, not as an afterthought — see §6.4.

---

## 1. URGENT — THE AOI CHANGE (do this before anything else, this week)

Your teammate's message, restated as an executable checklist. **Nothing in §2–§7 below is
trustworthy until this section is closed**, because every downstream feature table, every
exposure score, and every RAG-cited claim about "catchment X's bare-ground fraction" ships
from data pulled against the wrong box otherwise.

### 1.1 Why this happened, stated plainly (put this in the model card / data dictionary too)

The original download box was wrong by roughly **37×** — it cut off ~85% of Wadi Yutum,
which drains from 90 km inland. Your Phase 1 WorldCover, SoilGrids, and OSM extracts were
all pulled against that old, too-small box. **This is not a data-quality problem, it's a
coverage problem** — the numbers you computed for the catchments that *were* inside the old
box are probably fine; the numbers for anything touching the new, larger upstream area are
either missing or wrong, and you cannot tell which from the file alone. That's exactly why
step 1.2 exists.

### 1.2 Step one — find out exactly what's short (do not skip, do not guess)

```bash
python scripts/check_aoi_coverage.py
```

Run this **first**, before re-downloading anything. Read its output literally — it should
tell you, per file, whether it fully covers `TERRAIN_AOI` / `MARINE_AOI`, partially covers
it, or misses it entirely. Treat this output as a to-do list, not a formality:

```bash
python scripts/check_aoi_coverage.py > docs/aoi_coverage_report_$(date +%Y%m%d).txt
```

Save that timestamped output into the repo. It's your evidence that the re-pull was
triggered by a measured gap, not a hunch — and it's the first artifact anyone (Karam, a
judge, future-you) can check against the swap-completion claim.

### 1.3 The new spatial contract (v2) — memorize these two boxes, import them, never retype them

```text
TERRAIN_AOI = 34.75, 29.15, 35.94, 30.30   # W,S,E,N — EPSG:4326 — ~115 x 128 km
              land side: your WorldCover, SoilGrids, OSM all belong here

MARINE_AOI  = 34.80, 29.25, 35.05, 29.60   # W,S,E,N — EPSG:4326 — ~24 x 39 km
              sea side: your GEBCO/GMRT bathymetry, coastline, reef zones belong here

AQABA_BBOX  = 34.75, 29.15, 35.94, 30.30   # the union — download against this or wider
```

```python
# config.py — DELETE the old (34.80, 29.25, 35.15, 29.70) constant entirely.
# Do not leave it commented out — Karam's Day-0 test asserts no module contains a
# literal bounding box, and a commented-out one is exactly the kind of thing someone
# copy-pastes back in on Day 9 under pressure.

TERRAIN_AOI = (34.75, 29.15, 35.94, 30.30)  # lon_min, lat_min, lon_max, lat_max
MARINE_AOI  = (34.80, 29.25, 35.05, 29.60)
AOI_CRS_STORAGE   = "EPSG:4326"
AOI_CRS_PROJECTED = "EPSG:32636"  # UTM 36N — every area/distance calc, no exceptions
```

Import `TERRAIN_AOI` for WorldCover, SoilGrids, and OSM. Import `MARINE_AOI` for bathymetry,
coastline, and reef zones — those didn't change, since the marine box is untouched between
v1 and v2. **Do not accidentally re-pull your marine data — it's still correct.** Only the
land-side terrain box moved.

### 1.4 WorldCover — the second-tile problem, solved explicitly

ESA WorldCover ships as 3°×3° tiles named by their lower-left corner. Your original tile
(`N27E033`, covering roughly 27°N–30°N) is why your data "stops at 30°N" — that's not a bug,
that's the tile boundary. `TERRAIN_AOI` now reaches **30.30°N**, which is past that tile's
northern edge, so you need the adjacent tile to the north.

```python
# Confirm the exact second tile ID before downloading — don't assume it's N30E033,
# verify it against the actual WorldCover tile grid for your longitude band:
# https://worldcover2021.esa.int/viewer  — zoom to TERRAIN_AOI's north edge, read the
# tile ID directly off the grid overlay if the viewer exposes one, or cross-check
# against the WorldCover tiling scheme document before you download.

WORLDCOVER_TILES_NEEDED = [
    "ESA_WorldCover_10m_2021_v200_N27E033_Map.tif",  # already have this
    "ESA_WorldCover_10m_2021_v200_N30E033_Map.tif",  # CONFIRM this ID, then download
]
```

**Mosaic the two tiles before clipping, don't clip-then-merge:**

```python
import rasterio
from rasterio.merge import merge

srcs = [rasterio.open(f"data/raw/worldcover/{f}") for f in WORLDCOVER_TILES_NEEDED]
mosaic, out_transform = merge(srcs)
meta = srcs[0].meta.copy()
meta.update({
    "height": mosaic.shape[1],
    "width": mosaic.shape[2],
    "transform": out_transform,
})
with rasterio.open("data/interim/worldcover_mosaic_v2.tif", "w", **meta) as dst:
    dst.write(mosaic)
for s in srcs:
    s.close()

# THEN clip the mosaic to TERRAIN_AOI, same pattern as Phase 1
```

**Mandatory seam check** — the exact kind of visual QA that caught your Phase 1 bugs:

```python
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(12, 12))
show(mosaic, ax=ax, transform=out_transform)
ax.axhline(y=30.0, color='red', linestyle='--', linewidth=1)  # mark the old tile seam
ax.set_title("WorldCover mosaic — red line = tile seam at 30°N, check for discontinuity")
plt.savefig("docs/qa_screenshots/worldcover_v2_mosaic_seam_check.png", dpi=150)
```

Look at this image before trusting anything downstream. A visible brightness jump or
classification discontinuity exactly at the 30°N line means the two tiles used different
processing versions or dates — flag it in the data dictionary if so, don't silently average
across it.

### 1.5 SoilGrids and OSM — re-pull against `TERRAIN_AOI`

Same processing pipeline as Phase 1 (§3.2/§3.3 of your original plan), just re-pointed:

```python
# SoilGrids — same WCS clip approach, new box
soilgrids_clip = fetch_soilgrids_wcs(bbox=TERRAIN_AOI, variables=SOILGRIDS_VARS, depths=DEPTHS)
```

```bash
# OSM — re-clip from the same jordan-latest.osm.pbf, no need to re-download the country
# extract itself, just re-run the extraction against the new box:
osmium extract -b 34.75,29.15,35.94,30.30 \
    data/raw/osm/jordan-latest.osm.pbf \
    -o data/interim/osm_terrain_v2_clip.osm.pbf
```

**Re-run every per-catchment aggregation** once Karam/Mahdi's merged `catchments.gpkg`
(5 real catchments, 4,656 km² total, per `00-phase2-plan.md`'s geometry contract) is in
hand — see §2 below, this is the same blocker as your feature-table close-out.

**Re-run the bare-ground sanity check against the new, much larger Wadi Yutum catchment
specifically** — this is actually a more meaningful test now than it was in Phase 1, because
`AQ-C01` is 4,453 km² and spans a lot more terrain diversity than your old small-box
catchments did:

```python
print(landcover_v2_df.loc[landcover_v2_df["catchment_id"] == "AQ-C01", "frac_bare_sparse_vegetation"])
# Sanity check against the concept doc's ~74% baseline, same as before — but now
# AQ-C01 alone represents 4,453 km² of the 4,656 km² total, so this single number
# carries almost the whole project's runoff-feature credibility. Get a screenshot.
```

### 1.6 Earth Engine — the 10-minute unblock, do it today, not "when you have 10 minutes"

This is explicitly listed as a Day-0 blocking item in `00-phase2-plan.md` §Day-0. It's not
optional housekeeping — it's one of six things the *entire team* is blocked on until done.

```bash
earthengine authenticate
```
or
```python
import ee
ee.Authenticate()
```

Then register your own project (per your Phase 1 legendary-prompt work, this should already
exist as `reefshield-aqaba` if you completed that step — confirm, don't re-create):

```python
ee.Initialize(project='reefshield-aqaba')
print(ee.Image("USGS/SRTMGL1_003").getInfo()['id'])  # sanity check, should print cleanly
```

The moment this works, kick off the **real** ACA export at full 5m resolution over the
(unchanged) `MARINE_AOI` — see §2.2.

### 1.7 Definition of done for the AOI fix

- [ ] `check_aoi_coverage.py` run, output saved and timestamped in `docs/`
- [ ] `TERRAIN_AOI` / `MARINE_AOI` constants added to `config.py`, old box deleted (not commented out)
- [ ] Second WorldCover tile identified, downloaded, mosaicked, seam-checked with a saved screenshot
- [ ] SoilGrids re-pulled against `TERRAIN_AOI`
- [ ] OSM re-clipped against `TERRAIN_AOI` from the existing `.osm.pbf`
- [ ] All three per-catchment aggregations re-run against the real 5-catchment set (blocked on §2.1 below)
- [ ] Bare-ground sanity check re-verified specifically for `AQ-C01`, screenshotted
- [ ] Earth Engine authenticated, project verified working
- [ ] `docs/data_dictionary.md` updated to note the re-pull, the reason, and the date — don't just silently overwrite the old entries, add a line documenting the correction, since a project that visibly catches and fixes its own AOI bug is more credible than one that never mentions it had one

---

## 2. CLOSE PHASE 1 BLOCKERS — Day 1

Both of your Phase 1 blockers are now unblocked per `04-pulga.md`. Close them fast — Ali is
blocked on you by **Day 3**, and Nizar wants real reef zones by **Day 2**.

### 2.1 The three feature tables — real catchments, not the fixture

```bash
# Confirm catchments.gpkg has actually merged (Karam owns Day 0 — verify, don't assume)
python -c "import geopandas as gpd; c = gpd.read_file('data/processed/vectors/catchments.gpkg'); print(c['catchment_id'].tolist())"
# Expect: AQ-C01 through AQ-C05
```

```bash
python scripts/aggregate_catchments.py --input data/processed/vectors/catchments.gpkg
```

Then, **delete the fixture** — don't leave it lying around as a stale reference someone
imports by accident:

```bash
rm data/interim/catchments_FIXTURE_local_test_only.gpkg
```

Output at the contract paths, no longer quarantined:
```text
data/processed/features/landcover_by_catchment.parquet
data/processed/features/soil_by_catchment.parquet
data/processed/features/urban_by_catchment.parquet
```

**Cross-check against the geometry contract** before calling this done — this is exactly the
"two artifacts disagree, that's the signal" discipline from §0:

```python
import pandas as pd
expected_areas = {
    "AQ-C01": 4453.1, "AQ-C02": 64.9, "AQ-C03": 59.9, "AQ-C04": 42.7, "AQ-C05": 35.6,
}
your_landcover_df = pd.read_parquet("data/processed/features/landcover_by_catchment.parquet")
catchments = gpd.read_file("data/processed/vectors/catchments.gpkg").to_crs(AOI_CRS_PROJECTED)
catchments["area_km2"] = catchments.geometry.area / 1e6

for cid, expected in expected_areas.items():
    actual = catchments.loc[catchments["catchment_id"] == cid, "area_km2"].values[0]
    pct_diff = abs(actual - expected) / expected * 100
    assert pct_diff < 5, f"{cid}: expected {expected} km², got {actual:.1f} km² ({pct_diff:.1f}% off)"
print("All catchment areas match the geometry contract within 5%.")
```

If this assertion fails for `AQ-C01` specifically, stop — that's a 96%-of-discharge
catchment, and every downstream feature, model input, and exposure score inherits whatever
error is hiding there.

### 2.2 Earth Engine auth + the real ACA export

Already unblocked per §1.6. Now run the actual export:

```bash
python scripts/export_aca.py submit
# poll:
python scripts/export_aca.py status
# once complete:
python scripts/export_aca.py build
```

**`verify_against_provisional()` is not optional ceremony — read what it actually asserts
and don't override it under time pressure:**

```python
def verify_against_provisional(provisional_gdf, final_gdf, max_centroid_shift_km=5.0):
    prov_ids = set(provisional_gdf["reef_zone_id"])
    final_ids = set(final_gdf["reef_zone_id"])

    assert final_ids <= prov_ids, (
        f"New zone IDs appeared that weren't in the provisional set: {final_ids - prov_ids}. "
        f"Per contract §2, if ACA yields fewer zones, extras are DROPPED and remaining "
        f"IDs keep their names. New IDs are not allowed — check your merge/naming logic."
    )

    for zid in final_ids:
        prov_centroid = provisional_gdf.loc[provisional_gdf["reef_zone_id"] == zid, "geometry"].centroid.iloc[0]
        final_centroid = final_gdf.loc[final_gdf["reef_zone_id"] == zid, "geometry"].centroid.iloc[0]
        # reproject to UTM 36N before measuring distance — see §0's cross-check rule
        shift_km = prov_centroid.to_crs(AOI_CRS_PROJECTED).distance(
            final_centroid.to_crs(AOI_CRS_PROJECTED)
        ) / 1000
        assert shift_km < max_centroid_shift_km, (
            f"{zid} centroid moved {shift_km:.1f} km — exceeds the 5 km sanity bound. "
            f"This could mean R-03 and R-05 got swapped, not just refined."
        )
    print(f"Verified: {len(final_ids)}/{len(prov_ids)} provisional zones confirmed, "
          f"no unexpected new IDs, all centroids within {max_centroid_shift_km} km.")
```

**The specific watch-out from your task file:** `R-01` and `R-02` sit over developed beach
and port frontage where reef presence is doubtful. If the real ACA export yields fewer real
zones — **the extras are dropped, remaining IDs keep their names, nothing gets renumbered.**
Every stored exposure result across the whole system joins on these IDs; a renumber
silently corrupts everything computed so far, with no error message.

**`sensitivity_weight` stays exactly as it was — do not "improve" it under Phase 2
pressure:**

```python
final_zones["sensitivity_weight"] = 1.0
final_zones["sensitivity_weight_status"] = "PLACEHOLDER_PENDING_MARINE_SCIENTIST"
```

ACA maps habitat, not sensitivity. This is the single most-repeated warning across your
entire Phase 1 and Phase 2 documentation for a reason — it's the easiest number to
accidentally start treating as real once it's sitting in a production database with a
confident-looking schema around it.

---

## 3. FASTAPI BACKEND

### 3.1 Endpoint surface (concept §17, verbatim from your task file)

```text
GET  /api/v1/health
GET  /api/v1/data-sources
GET  /api/v1/catchments               GET /api/v1/catchments/{id}
GET  /api/v1/reef-zones
GET  /api/v1/events                   GET /api/v1/events/{id}
POST /api/v1/runoff/predict
POST /api/v1/plume/simulate
POST /api/v1/exposure/calculate
POST /api/v1/backtests/run            GET /api/v1/backtests/{run_id}
GET  /api/v1/alerts
POST /api/v1/explain
POST /api/v1/ask
```

### 3.2 Pydantic contracts — write these before you write a single route handler

Ali is blocked without shapes on **Day 3**. Treat the schema as the actual deliverable and
the implementation as secondary — a stub that returns the right shape with fake numbers
unblocks him; a real implementation with the wrong shape does not.

```python
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime

class Caveat(BaseModel):
    """Every response that carries a limitation ships it as structured data,
    not as a comment in a doc nobody reads at 2am before a demo."""
    field: str                 # which field this caveat applies to
    message: str                # human-readable, bilingual-ready
    severity: Literal["info", "warning", "critical"]

class ReefZoneOut(BaseModel):
    reef_zone_id: str           # "R-01".."R-08"
    habitat_class: str | None
    area_km2: float
    sensitivity_weight: float
    sensitivity_weight_status: Literal["PLACEHOLDER_PENDING_MARINE_SCIENTIST", "SCIENTIST_ASSIGNED"]
    geometry: dict               # GeoJSON
    caveats: list[Caveat] = []   # e.g. "zone width is a 250m assumption, not depth-derived"

class ExposureResult(BaseModel):
    reef_zone_id: str
    risk_score: float = Field(ge=0, le=100)
    risk_level: Literal["minimal", "low", "moderate", "high", "critical"]
    arrival_window_hours: tuple[float, float] | None
    max_exposure_probability: float
    confidence: Literal["low", "moderate", "high"]
    formula_terms: dict          # every input value, see §4.3 — non-negotiable
    caveats: list[Caveat] = []

class OutletOut(BaseModel):
    outlet_id: str               # "AQ-O01".."AQ-O05"
    lon: float
    lat: float
    position_confidence: Literal["low", "plausible", "good"]
    caveat: str | None           # e.g. AQ-O04's full harbour-basin warning, verbatim
```

Get these fixed **early** and communicate any change to Ali the same day you make it — "he
is not chasing a moving shape" is the literal instruction from your task file, and a schema
that drifts mid-sprint is worse for him than a schema that's honestly incomplete but stable.

### 3.3 Connection discipline

```python
# backend/src/db/session.py — Nizar owns this. Import it. Never open your own.
from backend.src.db.session import get_session

# WRONG — do not do this anywhere in your code:
# conn = psycopg2.connect(...)

# RIGHT:
async def get_reef_zones(session = Depends(get_session)):
    ...
```

Two independently-opened connections means two retry policies and two transaction
assumptions quietly diverging under load — exactly the kind of thing that looks fine in dev
and breaks during the live demo on conference wifi.

### 3.4 Caching

```python
from functools import lru_cache
# or, better for async FastAPI, a proper cache layer (e.g. cachetools.TTLCache or Redis
# if Mahdi's Docker Compose already includes it — check before adding a new dependency)

# A plume simulation must not re-run because someone dragged the time slider.
# Cache on (event_id, scenario_params_hash), not on wall-clock TTL alone —
# the same scenario requested twice should hit cache even minutes apart.
```

### 3.5 Caveats travel as data — the rule that matters most in this whole section

```python
def build_exposure_caveats(outlet_id: str, reef_zone: ReefZoneOut) -> list[Caveat]:
    caveats = []
    if outlet_id == "AQ-O04":
        caveats.append(Caveat(
            field="outlet_id",
            message="AQ-O04 discharges into an enclosed harbour basin; sediment released "
                    "here settles in the basin rather than dispersing into the Gulf. "
                    "Simulation results from this outlet should not be presented as "
                    "representative Gulf exposure.",
            severity="critical",
        ))
    if reef_zone.sensitivity_weight_status == "PLACEHOLDER_PENDING_MARINE_SCIENTIST":
        caveats.append(Caveat(
            field="sensitivity_weight",
            message="This zone's sensitivity weight is a team placeholder (1.0), not a "
                    "scientific assessment. Real weights require marine-scientist input.",
            severity="warning",
        ))
    # ±4% catchment area uncertainty, reef zone width 250m assumption, etc. — same pattern
    return caveats
```

Don't write these facts only into `docs/pitch_limitations.md`. If they only live in
documentation, they will not be on the screen when a judge is looking at a specific number
and asking "how sure are you about this." The whole point of shipping caveats *in the
payload* is that Ali's UI can render them right next to the number they qualify, automatically,
without anyone remembering to check a separate doc.

### 3.6 Priority order — the 6 August vertical slice

Per `00-phase2-plan.md`, the vertical slice is the single most important date on the whole
project's calendar. Your specific priority for it:

```text
Priority 1 (must exist by Aug 6): health · catchments · reef-zones · events · one STUBBED exposure response
Priority 2 (real, by Aug 8):       runoff/predict wired to Mahdi's real model
Priority 3 (real, by Aug 8):       plume/simulate wired to Abd's real particle engine
Priority 4 (real, by Aug 9):       exposure/calculate with real formula_terms
Priority 5 (Aug 9-10):             explain, ask, backtests, alerts
```

Ali needs *shapes* to draw against far more than he needs *correctness* this early. A
stubbed `/api/v1/exposure/calculate` that returns a plausible, correctly-typed
`ExposureResult` with made-up numbers on Day 3 is more valuable to the team right now than a
real one on Day 9 — **as long as it is unmistakably labeled as stub data internally**, so
nobody accidentally wires it into the RAG corpus or the pitch deck by mistake.

---

## 4. COMPONENT D — EXPOSURE ENGINE

### 4.1 The formula

```text
Exposure = plume_probability
         x relative_sediment_intensity
         x exposure_duration_weight
         x habitat_sensitivity_weight        (= 1.0, placeholder)
         x confidence_adjustment
```

```python
def calculate_exposure(
    plume_probability: float,       # from Abd's contoured field, 0-1
    relative_sediment_intensity: float,   # from Mahdi's sediment class, normalized
    exposure_duration_weight: float,      # derived from time-stepped contours
    habitat_sensitivity_weight: float,    # 1.0, always, until a marine scientist says otherwise
    confidence_adjustment: float,         # derived from GEFS ensemble spread (Nizar) etc.
) -> tuple[float, dict]:
    raw_score = (
        plume_probability
        * relative_sediment_intensity
        * exposure_duration_weight
        * habitat_sensitivity_weight
        * confidence_adjustment
    )
    risk_score = min(100.0, raw_score * 100)  # scale to 0-100, confirm this scaling is
                                                # documented, not arbitrary — write down why
                                                # *this* scaling and not another in the model card
    formula_terms = {
        "plume_probability": plume_probability,
        "relative_sediment_intensity": relative_sediment_intensity,
        "exposure_duration_weight": exposure_duration_weight,
        "habitat_sensitivity_weight": habitat_sensitivity_weight,
        "confidence_adjustment": confidence_adjustment,
        "raw_score": raw_score,
        "risk_score": risk_score,
    }
    return risk_score, formula_terms
```

### 4.2 Intersect plume contours with reef zones

```python
def intersect_plume_with_zones(
    plume_contours: gpd.GeoDataFrame,   # Abd's time-stepped probability contours
    reef_zones: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    # BOTH inputs reprojected to EPSG:32636 before ANY intersection or area calc —
    # this is the exact class of bug that overstated your culvert distances by 14.8%
    # when measured in EPSG:3857. Do not repeat it here at a higher-stakes layer.
    plume_utm = plume_contours.to_crs(AOI_CRS_PROJECTED)
    zones_utm = reef_zones.to_crs(AOI_CRS_PROJECTED)

    intersected = gpd.overlay(zones_utm, plume_utm, how="intersection")
    intersected["intersection_area_km2"] = intersected.geometry.area / 1e6
    intersected["zone_fraction_affected"] = (
        intersected["intersection_area_km2"] / intersected["area_km2"]
    )
    return intersected
```

### 4.3 `formula_terms` storage — the non-negotiable audit trail

```python
class ExposureRun(BaseModel):
    run_id: str
    event_id: str
    reef_zone_id: str
    timestamp: datetime
    formula_terms: dict          # EVERY input, not just the output
    model_versions: dict         # which runoff model version, which sediment proxy version,
                                   # which particle-engine calibration run — see Mahdi's
                                   # model_versions table, join to it here
```

"A score you cannot reconstruct six hours later is a number nobody can defend" — this is
the literal standard from your task file. Store `formula_terms` on every single run, not
just the final headline demo run. When a judge asks "why is R-04 at 81%," the answer must be
a database lookup, not a re-derivation from memory.

### 4.4 Risk bands

```python
RISK_BANDS = [
    (0, 20, "minimal"),
    (21, 40, "low"),
    (41, 60, "moderate"),
    (61, 80, "high"),
    (81, 100, "critical"),
]

def risk_level(score: float) -> str:
    for lo, hi, label in RISK_BANDS:
        if lo <= score <= hi:
            return label
    raise ValueError(f"score {score} out of bounds")
```

Attach the standing note everywhere this is displayed: **operational thresholds require
marine-scientist input.** These bands are a reasonable default, not a validated policy.

### 4.5 The reef-zone-width assumption — say it, don't bury it

Reef zone widths are a **250m assumption**, deliberately not derived from depth contours,
because the bathymetry's true resolution (~450m, whether GMRT or the substituted product)
cannot resolve the Gulf's drop-off. This means `area_km2` is order-of-magnitude, not precise
— and any exposure figure expressed as an absolute area inherits that imprecision silently.

```python
# Prefer this framing in every API response and every UI card:
"zone_fraction_affected": 0.42   # 42% of R-04's named area

# Over this framing, which implies false precision:
"area_affected_km2": 0.87        # sounds exact, isn't
```

### 4.6 Cross-check discipline for the exposure engine specifically

Apply the "two artifacts disagree = signal" rule here directly. Before trusting any exposure
score for the demo event, generate two independent sanity checks and compare:

1. **A synthetic circular-buffer baseline** around the discharging outlet (same baseline Abd
   uses for his backtest per `05-abd.md` §3) — does your exposure engine's output roughly
   track a simple "closer zones get hit harder, sooner" pattern, or does something look
   structurally wrong?
2. **A manual spot-check** of one zone's `formula_terms` computed by hand against the
   API-returned value, for at least one full run before the Aug 6 slice.

---

## 5. COMPONENT E — EXPLANATION AND RAG

### 5.1 `/explain` — the rule that is not negotiable

```python
async def explain(request: ExplainRequest) -> ExplainResponse:
    """
    Takes Mahdi's SHAP output + current model state.
    Returns the concept §10.8 paragraph, bilingual.

    THE LLM PHRASES NUMBERS IT IS HANDED. It never computes one, never rounds one,
    never invents one. This is the literal rule from the task file, restated as code
    comment because it WILL be tempting to let the model "helpfully" round 71.8% to
    "about 72%" or restate a probability slightly differently across two calls —
    don't allow that kind of drift either. Pass numbers through as given.
    """
    context = {
        "catchment_id": request.catchment_id,
        "shap_top_drivers": request.shap_drivers,          # from Mahdi, verbatim
        "plume_probability_to_zone": request.plume_probability,  # from Abd, verbatim
        "arrival_window_hours": request.arrival_window,     # from exposure engine, verbatim
        "confidence": request.confidence,                    # from Nizar's GEFS exceedance, verbatim
    }
    prompt = build_explain_prompt(context, language=request.language)  # EN or AR
    llm_response = await call_llm(prompt, temperature=0.0)  # temperature 0 — no creative
                                                              # variance in a paragraph
                                                              # that phrases audit-critical numbers
    return ExplainResponse(text=llm_response, source_numbers=context)
```

Example target output (from your task file, keep this as the literal calibration example
you test against):

> *"Wadi Yutum is classified as high risk because forecast 3-hour rainfall exceeds the
> catchment's historical 99th percentile, the upstream terrain is steep, and antecedent soil
> conditions support rapid runoff. The plume ensemble indicates a 72% probability of reaching
> Reef Zone R-04 within 8–12 hours. Confidence is moderate because nearshore currents are
> represented by a coarse global model."*

**Test this explicitly, don't just eyeball it:** write a unit test that feeds a known
`formula_terms` dict through `/explain` and asserts every number in the returned text
matches the input dict exactly (string match on the number, not just "a number appears
somewhere"). If the LLM ever changes "72%" to "approximately three-quarters" or similar,
that test should fail loudly.

### 5.2 RAG corpus — exactly these files, nothing else

```python
RAG_CORPUS_FILES = [
    "data/raw/literature/kalman_et_al_2025_fulltext_ATC1.pdf",
    "docs/data_dictionary.md",
    "docs/event_dates.md",
    "docs/era5_land_temporal_semantics.md",
    "docs/era5_land_accumulation_semantics.md",
    "docs/pitch_limitations.md",
    "docs/forcing_limitations.md",
    "docs/osm_dem_conflicts.md",
    "docs/qa_screenshots/MANIFEST.md",
    "docs/model_card.md",
    "tasks/00-contracts.md",
]

# EXPLICITLY EXCLUDED — do not ingest, even accidentally via a glob pattern:
# docs/ali/*  — the MENA/global analogue scan. Research and pitch material ONLY.
# It backs the market slide and the "is this only for Aqaba?" Q&A answer.
# It is NOT an app surface. If your ingestion script uses a wildcard like
# `docs/**/*.md`, it WILL pick this up by accident — write an explicit exclude,
# don't rely on remembering not to point at it.
```

```python
import glob

def get_corpus_files() -> list[str]:
    # WRONG — silently ingests docs/ali/* too:
    # return glob.glob("docs/**/*.md", recursive=True)

    # RIGHT — explicit allowlist, matches the RAG_CORPUS_FILES constant exactly:
    return RAG_CORPUS_FILES
```

### 5.3 `/ask` — citations are not optional decoration

```python
class AskResponse(BaseModel):
    answer: str
    citations: list[dict]   # [{"source_file": str, "section": str, "excerpt": str}]
    language: Literal["en", "ar"]

async def ask(request: AskRequest) -> AskResponse:
    retrieved_chunks = await retrieve(request.question, corpus=RAG_CORPUS_FILES, k=5)
    if not retrieved_chunks:
        return AskResponse(
            answer="I don't have documented information to answer that." if request.language == "en"
                   else "لا تتوفر لدي معلومات موثقة للإجابة على هذا السؤال.",
            citations=[],
            language=request.language,
        )
    answer, citations = await generate_cited_answer(request.question, retrieved_chunks, request.language)
    assert citations, "An uncited answer is not shippable — this assertion should never fire in production"
    return AskResponse(answer=answer, citations=citations, language=request.language)
```

**"An uncited answer is not shippable"** is your task file's literal words — make it an
actual assertion in the code path, not just a design intention that erodes under deadline
pressure on Day 11.

### 5.4 Bilingual discipline

```python
def build_explain_prompt(context: dict, language: Literal["en", "ar"]) -> str:
    template = EXPLAIN_TEMPLATE_EN if language == "en" else EXPLAIN_TEMPLATE_AR
    return template.format(**context)

# Test both languages against the SAME formula_terms input and assert the NUMBERS
# (not the prose) are identical between the English and Arabic responses — the
# language changes, the underlying facts must not.
```

### 5.5 Why this whole component earns its place — keep this framing for the pitch

Questions like *"how confident are we in the catchment area?"* or *"why is the reef
sensitivity 1.0?"* have real, documented, honest answers already sitting in this repo. The
`/ask` endpoint is the difference between a team that *wrote down* its limitations and a
team that can *defend them live, in real time, in front of a judge, in either language.*
That's a genuinely rare capability at a hackathon — protect it, test it thoroughly, and make
sure it never returns an answer it can't back with a citation.

---

## 6. QA AND SCREENSHOT DISCIPLINE — carried forward, expanded for Phase 2

Phase 1 taught this project that visual verification catches what code review misses. Phase
2 has more surface area for silent bugs (a live API, cached values, cross-service joins), not
less — so the discipline expands, it doesn't relax.

### 6.1 What needs a screenshot/artifact in Phase 2, specifically

| What | Artifact | Why |
|---|---|---|
| WorldCover v2 mosaic seam | Plot with 30°N line marked | Two-tile merge is a new failure mode |
| Re-run bare-ground check for AQ-C01 | Annotated plot vs. baseline | AQ-C01 now carries 96% of project credibility |
| `verify_against_provisional()` result | Centroid comparison map | Same discipline as Phase 1's reef zone check |
| Every exposure engine test run | `formula_terms` dumped to a readable table, not just JSON in a log | Auditability |
| `/explain` number-fidelity test | Side-by-side input dict vs. output text, numbers highlighted | Catches LLM drift |
| `/ask` citation coverage | A table of test questions → whether a citation was returned | Catches silent uncited answers |
| API response caveat coverage | A table: which endpoints, which caveats fire under which conditions | Confirms caveats actually travel, not just exist in code |

### 6.2 Data dictionary discipline continues exactly as before

Every re-pulled source (WorldCover v2, SoilGrids v2, OSM v2) gets its own entry or a clearly
dated amendment to its existing entry — never a silent overwrite. Include: product/version,
access date, access method, the specific reason for the re-pull, and a link to the QA
screenshot proving the fix worked.

### 6.3 The Day 12 gate applies to your outputs too

```bash
grep -ri PROVISIONAL --include='*.py' --include='*.md' .
ls data/**/*PROVISIONAL* data/**/*FIXTURE* 2>/dev/null
```

If `reef_zones_PROVISIONAL.gpkg` or the deleted fixture's name still appears anywhere in
your code, docs, or the RAG corpus by 12 August, it's either genuinely swapped or explicitly
declared a known placeholder in the demo script. No silent placeholders reach the stage —
this applies to your `sensitivity_weight` placeholder specifically, which by design is
*supposed* to still say `PLACEHOLDER_PENDING_MARINE_SCIENTIST` at the end. That's fine — a
labeled placeholder is honest. An *unlabeled* one is the failure mode this gate exists to
catch.

---

## 7. FULL SCHEDULE — Pulga's row, cross-referenced against the whole team

| Day | Pulga | Cross-team dependency |
|---|---|---|
| **Day 0 (2 Aug)** | AOI fix: run `check_aoi_coverage.py`, re-pull WorldCover (2 tiles), SoilGrids, OSM. EE auth. | Karam merges catchments; everyone purges old bbox |
| **Day 1** | Close Phase 1 blockers: real feature tables (§2.1), real ACA export kicked off (§2.2) | — |
| **Day 2** | ACA export likely still running (background). Start FastAPI skeleton + Pydantic contracts (§3.2) | **Nizar needs real reef zones by today** — if ACA isn't done, hand off provisional + your verified schema so his loader isn't blocked |
| **Day 3** | Deliver typed endpoints (stubs acceptable) to Ali | **Ali is blocked without shapes today — hard deadline** |
| **Day 4** | Wire `/runoff/predict` against Mahdi's stub | Mahdi delivers predict function stub |
| **Day 5** | Exposure engine (§4) built against synthetic contours | — |
| **Day 6 — VERTICAL SLICE DAY** | Priority-1 endpoints live and demo-able end to end, even if ugly | **The most important date on the whole project.** Deliver the exposure consumer interface to Abd today |
| **Day 7** | Wire real `/plume/simulate` against Abd's real particle engine output | Abd delivers real time-stepped probability contours |
| **Day 8** | Real exposure scores with real `formula_terms`; real ACA reef zones fully swapped in if not already | Mahdi's real (non-stub) model lands |
| **Day 9** | `/explain` + `/ask` built and tested for number-fidelity and citation coverage (§5) | — |
| **Day 10** | Integration support; help Karam run the full demo daily; contribute to offline cache seeding | Nizar seeds frozen "today" snapshot |
| **Day 11** | Bug fixes surfaced by daily demo runs; finalize `docs/data_dictionary.md` | — |
| **Day 12 — FREEZE** | Run the Day-12 gate grep (§6.3) yourself before anyone else has to ask | No new features, anywhere, by anyone |
| **Day 13** | Present | — |

---

## 8. HANDOFF MATRIX — both directions, fully cross-referenced

### 8.1 What Pulga delivers

| To | What | Deadline | Consequence if late |
|---|---|---|---|
| **Ali** | Typed endpoints, stubs acceptable | **Day 3** | He is fully blocked — cannot build anything against a moving/absent shape |
| **Nizar** | Real reef zones (or provisional + stable schema) | **Day 2** | His loader for `reef_zones` stalls |
| **Karam** | Land/soil/urban feature tables | **Day 1** | His feature matrix for Mahdi is incomplete |
| **Abd** | Exposure consumer interface for his probability fields | **Day 6** | His plume output has nowhere to feed into |

### 8.2 What Pulga depends on

| From | What | Blocked? | Mitigation if late |
|---|---|---|---|
| **Nizar** | Schema + connection layer | Yes, partly | Build endpoints against fixtures until Day 2 |
| **Mahdi** | Predict function + SHAP output | No | Stub it, swap when real lands (Day 4 stub, Day 8 real) |
| **Abd** | Plume probability fields | No | Exposure engine tests against synthetic contours from Day 5 |
| **Karam** | Merged `catchments.gpkg` | No (merges Day 0) | — |

---

## 9. DEFINITION OF DONE — the complete list

1. `check_aoi_coverage.py` run, gap report saved
2. WorldCover v2 mosaic (2 tiles) built, seam-checked, screenshotted
3. SoilGrids and OSM re-pulled against `TERRAIN_AOI`
4. All three feature tables regenerated against real catchments, fixture deleted, areas cross-checked against the geometry contract
5. Earth Engine authenticated and verified working
6. Real ACA reef zones exported, `verify_against_provisional()` passed, `sensitivity_weight` still correctly labeled as placeholder
7. FastAPI serving every §17 endpoint, typed with Pydantic, cached, caveats travelling as structured data
8. Exposure engine producing scores with `formula_terms` stored on every run, all area/distance math in EPSG:32636
9. `/explain` tested for exact number-fidelity (no LLM rounding/rephrasing of source numbers)
10. `/ask` tested for 100% citation coverage on a defined test-question set; `docs/ali/*` confirmed excluded from the corpus
11. `docs/data_dictionary.md` fully updated — both the AOI re-pull and the ACA export documented with versions and dates
12. Day-12 gate grep run clean (or every remaining match explicitly declared)

---

## 10. RISK REGISTER — specific to this phase of your work

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Second WorldCover tile has different processing date/version than the first | Medium | Medium | Seam-check screenshot (§1.4), document if found rather than silently blending |
| AQ-C01 re-aggregated feature values fail the geometry-contract cross-check | Medium | Critical | Assertion in §2.1 stops the pipeline before bad data propagates to Mahdi's model |
| ACA export produces fewer zones and someone renumbers instead of dropping | Low but catastrophic | Critical | `verify_against_provisional()` hard-asserts no new IDs appear |
| `sensitivity_weight` gets "temporarily" set to something non-1.0 under demo-polish pressure | Medium as Day 12 approaches | High (credibility) | Schema-level `sensitivity_weight_status` field makes it visible in every API response, not just docs |
| `/explain` LLM subtly rephrases a number (e.g. rounds 71.8% to "about 72%") | Medium | High (breaks auditability claim) | Automated number-fidelity test, not just manual review |
| `/ask` returns a confident but uncited answer under a tricky question | Medium | High (the exact thing a skeptical judge will try) | Hard assertion that citations is non-empty before returning |
| Caveats exist in code but never actually reach a response because of a missed code path | Medium | High | §6.1's caveat-coverage table — literally enumerate which endpoints fire which caveats and verify each |
| Exposure engine area/distance math accidentally done in EPSG:4326 or :3857 somewhere new | Medium (you've hit this exact bug before) | High | §4.2's explicit reprojection-first pattern, applied at every new intersection you write |
| Two independently-computed exposure numbers for the same zone/time silently diverge and nobody notices | Low if §4.6 is followed | High | Build the cross-check comparison as a standing habit, not a one-time Phase 1 exercise |

---

## GUIDING PRINCIPLE FOR THIS ENTIRE PHASE

> The backend is where every number a judge will see gets assembled. An exposure score that
> is wrong will look completely normal — it won't crash, it won't throw an error, it will
> just render on Ali's beautiful map looking exactly as confident as a correct one. The only
> defense against that is the same one that already caught five bugs in Phase 1: build the
> artifact, look at it, make it disagree with something else if you can, and never let a
> number reach the screen without a `formula_terms` trail that can reconstruct it six hours
> later in front of a judge who's asking why.

Proceed.
