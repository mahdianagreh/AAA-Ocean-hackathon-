# Phase 2 — Five Streams Become One System

**Project:** ReefShield Aqaba
**Written:** 2 August 2026
**Window:** 2 → 13 August 2026 (11 working days)
**Read this before your own task file.**

---

## Where Phase 1 left us

Five people researched five data domains independently and every stream delivered. What
does not exist yet is a **system**. There is no database, no API, no interface, no trained
model, and the five streams have never run end to end against each other.

Phase 2 builds exactly that, and nothing else.

### What Phase 1 proved

| Stream | Result |
|---|---|
| Rainfall & reanalysis | Event-agnostic IMERG + ERA5-Land pipeline, 272 tests passing, config-driven |
| Terrain & hydrology | 5 real catchments (4,656 km²) and 5 outlets from 30 m GLO-30, validated four ways |
| Land / soil / urban / marine | WorldCover, SoilGrids, OSM (12 layers), GMRT bathymetry, 8 reef zones, 34 QA figures |
| Forecasts & currents | GFS, GEFS (30 members), ECMWF IFS, HYCOM — all pulling live |
| Imagery & plume | Full plume-extraction pipeline, and a **NO-GO verdict** on satellite validation |

### The three findings that reshape Phase 2

**1 · The AOI was wrong by ~37×.** The original download box cut off about 85% of Wadi
Yutum, which drains from 90 km inland out to 35.89 °E. Every IMERG and ERA5-Land granule on
disk was pulled against that box. This is almost certainly why the derived rainfall peak
falls *after* the documented flood arrival — the box was sampling coastal rain, not the
upstream catchment that generated the flood. **All rainfall must be re-pulled.**

**2 · Satellite validation is dead, for a real physical reason.** The Kalman et al. (2025)
mooring shows the turbidity signal lasted ~31 hours and had returned to background by
17:15 on 29 Oct. Both available satellite passes are **2.5–3.5 days later**. Two independent
sensors confirm no visible plume. This is a genuine null result, not a data-quality problem.

**3 · The replacement is better.** That same mooring — 250 m offshore the Kinnet Canal
outlet, 13 m depth — recorded salinity and turbidity every 5 minutes through the whole
event. Validating against a measured time series beats validating against a hand-drawn
mask from a fuzzy image. **The mooring is now the validation target.**

---

## What Phase 2 delivers

```
IMERG / GFS rainfall  ─┐
ERA5 soil moisture     ├──> [A] runoff classifier ──> P(runoff) + severity + SHAP
static catchment feats ─┘                                    │
                                                             v
                              [B] sediment proxy  (x transmission loss)
                                                             │
currents + wind + bathymetry ──> [C] particle engine ────────> plume probability field
                                                             │
reef zones ──────────────────────────────────────────────────┼──> [D] exposure score
                                                             v
                                     [E] LLM: explain (AR/EN) + RAG + cite
```

Served from **Supabase Cloud** through a **FastAPI** backend to a **bilingual React map**,
all in **Docker Compose**, with a fully cached offline path.

### What is actually machine-learned

Be precise about this, because a judge will press on it.

| Component | Nature | Trained? |
|---|---|---|
| **A · Runoff classifier** | Rule baseline + XGBoost + calibration + SHAP | **Yes — the only trained model** |
| **B · Sediment proxy** | Deterministic formula, one real anchor point | No |
| **C · Plume transport** | Physics; parameters fitted to the mooring | Parameters fitted, not learned |
| **D · Exposure score** | Deterministic formula | No |
| **E · LLM layer** | Explanation + retrieval over our own docs | No — and it never computes a number |

This is a **hybrid physics-informed system**, exactly as concept doc §10.3 prescribes.
Describing it that way is honest and defensible. Implying end-to-end deep learning is not.

### The label problem, and how it is solved

We have **one** event with ground truth. You cannot supervise on n = 1.

ERA5-Land ships modelled surface runoff (`sro`) and sub-surface runoff (`ssro`) hourly back
to 1950. That is not observation — it is ECMWF's land-surface scheme answering *"did this
rain generate runoff"* — but it converts n = 1 into thousands of weak labels.

| Tier | Source | Count | Use |
|---|---|---:|---|
| **Gold** | Literature-confirmed flood reaching the sea, mooring-verified | ~1 | **Final validation only. Never trained on.** |
| **Silver** | ERA5-Land `sro` exceeds that catchment's own p99 in the 24 h after rainfall | hundreds | The training workhorse |
| **Bronze** | Rainfall percentile alone | thousands | **Never a target — it is circular** |

> ### The one rule that keeps this honest
> **ERA5-Land runoff variables (`sro`, `ssro`) are LABELS ONLY. They are never features.**
>
> Feed runoff in as a feature while also using it as the label and you have built a
> tautology that scores 0.99 and means nothing. Features come from IMERG rainfall,
> ERA5 soil moisture / wind / temperature, and the static terrain, land-cover and soil
> columns.

---

## Day 0 — merge day · 2 August · everyone · BLOCKING

Nothing in Phase 2 starts until all six items are done. Half a day, together.

- [ ] **Merge `origin/mahdi` into `main`.** Real catchments and outlets have existed for a
      day while three people report themselves blocked on files that are already written.
      This is a real merge, not a fast-forward — `tasks/00-contracts.md` and the per-person
      task files will conflict. Mahdi's versions win on the hydrology sections.
- [ ] **Adopt the two-AOI contract** (below) and purge the dead bounding box from all seven
      modules that hard-code it.
- [ ] **`git rm --cached .env`** and **rotate all 12 credentials.** `.env` is tracked in
      history from commit `2f0a6d6` despite being in `.gitignore`.
- [ ] **Archive `AAA-project-bank.md`** — it describes a different, superseded concept
      (coral photo CNN, reef sound classifier) and someone will eventually build from it by
      mistake.
- [ ] **Accept the validation pivot** — satellite mask out, mooring time series in.
- [ ] **Two 10-minute unblocks:** register Copernicus Marine (Nizar) and authenticate
      Google Earth Engine (Pulga).

---

## The spatial contract — v2

Superseded on 1 Aug. If you downloaded against the old single box, **re-pull**.

```text
TERRAIN_AOI = 34.75, 29.15, 35.94, 30.30   # W,S,E,N  EPSG:4326  ~115 x 128 km
              land side: DEM, hydrology, rainfall, land cover, soil

MARINE_AOI  = 34.80, 29.25, 35.05, 29.60   # W,S,E,N  EPSG:4326  ~24 x 39 km
              sea side: currents, bathymetry, imagery, reef zones

AQABA_BBOX  = 34.75, 29.15, 35.94, 30.30   # the union — download against this or wider
```

| Purpose | CRS |
|---|---|
| Storage, exchange, GeoJSON, PostGIS | **EPSG:4326** |
| Every area, distance, slope calculation | **EPSG:32636** (UTM 36N) |

Any area in km² computed in degrees is wrong. No exceptions.

## The geometry contract — settled

| Catchment | Area | Outlet | lon, lat | Outlet confidence |
|---|---:|---|---|---|
| `AQ-C01` Wadi Yutum | 4,453.1 km² ±4% | `AQ-O01` | 34.97073, 29.54560 | **plausible** — demo on this |
| `AQ-C02` | 64.9 km² | `AQ-O02` | 34.97643, 29.47270 | low — routes through container terminal |
| `AQ-C03` | 59.9 km² | `AQ-O03` | 34.96416, 29.38167 | low — tank farm corridor |
| `AQ-C04` | 42.7 km² | `AQ-O04` | 34.96622, 29.36052 | **low — enclosed harbour, see warning** |
| `AQ-C05` | 35.6 km² | `AQ-O05` | 34.95998, 29.35737 | **good** — natural wadi, reef offshore |

4,656 km² total — 97% of everything draining Jordan's Gulf coast. `AQ-O01` carries **96% of
the discharge**.

> **AQ-O04 discharges into an enclosed harbour basin.** Sediment released there settles in
> the basin rather than dispersing into the Gulf. A particle simulation from that coordinate
> will produce a confidently wrong plume. Do not demo it without saying so.

~1,800–2,000 km² of the Wadi Yutum system is **endorheic** — it drains to internal sinks and
never reaches the Gulf. It is excluded on purpose, verified three ways. Do not add it back
from HydroBASINS `UP_AREA`.

## The event contract

**One event.** `AQ-2016-10-28`, the October 2016 Aqaba–Eilat flash flood.

| Item | Value | Basis |
|---|---|---|
| Flood arrival (Eilat) | `2016-10-28T00:00:00Z` | Reported, timezone-converted (IDT, UTC+3) |
| Offshore instrument response | `2016-10-28T06:50:00Z` | Reported, timezone-converted |
| Sediment mass | ≈24,400 t | Kalman et al. 2025 |
| Mooring salinity minimum | 38.75 ‰ (−1.75 ‰, 19σ below background) | Measured |
| Mooring turbidity peak | 2.18 g/L near seafloor | Measured |
| Elevated turbidity duration | ~31 h, 09:50 Oct 28 → ~17:15 Oct 29 local | Measured |

February 2013 is **dead**: no date (Katz et al. paywalled and not being chased), no
Sentinel-2 (pre-launch), no Landsat 8 (pre-commissioning), only SLC-off Landsat 7.
Do not spend a day on it.

---

## Sources — in and out

### In

IMERG V07 **Final** (`C2723754847-GES_DISC`) · IMERG V07 **Early** (`C2723758340-GES_DISC`) ·
IMERG **Daily Final** (`GPM_3IMERGDF`, ID to be resolved from CMR) · **ERA5-Land** hourly,
7 variables · **Copernicus GLO-30** DEM · **HydroBASINS L9** · **HydroRIVERS** · **SRTM 1"** ·
**ESA WorldCover** 10 m 2021 · **ISRIC SoilGrids** v2.0 · **OpenStreetMap** Jordan ·
**GMRT** bathymetry · **NOAA GFS / GEFS / ECMWF IFS** · **HYCOM GLBy0.08** ·
**Copernicus Marine** `GLOBAL_ANALYSISFORECAST_PHY_001_024` · **Microsoft Planetary Computer**
(Sentinel-2 L2A + Landsat C2, no credentials needed) · **Allen Coral Atlas** via Earth Engine ·
**Kalman et al. 2025** mooring record.

### Out, and why

| Source | Reason |
|---|---|
| **GEBCO** | Every programmatic route closed. Substituted by GMRT, named honestly — the file stays `gmrt_aqaba.tif`, never renamed |
| **MERIT Hydro** | Needs Univ. Tokyo registration. Replaced by HydroRIVERS, which is more independent anyway |
| **CHIRPS** | Never executed. IMERG Final + Early already satisfy the rainfall requirement. Documented as deliberately not-run, not an oversight |
| **NASA HLS** | Extra revisits cannot help an event whose plume was gone before any pass |
| **Feb 2013 / Landsat 7** | No date, no usable sensor |
| **Sentinel-2 as backtest validation** | Null result. The pipeline is retained as the *live* path |
| **Copernicus Data Space (CDSE)** | Superseded by Planetary Computer for imagery |
| **Old `DOWNLOAD_BBOX`** | Wrong by ~37× |
| **`AAA-project-bank.md` concept** | Different, superseded project |

### The research documents

`docs/ali/*` — the MENA and global analogue scan — is **research and pitch material only**.
It backs the market slide and the *"is this only for Aqaba?"* answer in Q&A. **It is not an
app surface and it is not in the RAG corpus.**

The **RAG corpus** is the technical and operational documentation only: Kalman et al. 2025
full text, `docs/data_dictionary.md`, `docs/event_dates.md`, the two ERA5 semantics docs,
`docs/pitch_limitations.md`, `docs/forcing_limitations.md`, `docs/qa_screenshots/MANIFEST.md`,
and the model card once it exists.

---

## Schedule

| Dates | Milestone |
|---|---|
| **2 Aug** | **Day 0 — merge day.** Six blocking items above. |
| 3–4 Aug | Foundations: Supabase schema live · daily IMERG sweep running · FastAPI skeleton · React shell |
| **6 Aug** | **VERTICAL SLICE.** End-to-end and ugly: one event → one prediction → one plume → one exposure score → visible on the map. It does not need to be right. It needs to *run*. |
| 7–9 Aug | Deepen: real model trained and validated · calibration against the mooring · exposure engine · scenario controls · bilingual · RAG |
| 10–11 Aug | Integration, offline cache, demo rehearsal, limitations page |
| **12 Aug** | **Freeze.** No new features. Rehearse, record a backup video, cache everything. |
| 13 Aug | Present |

**The 6 August vertical slice is the most important date on this page.** A system integrated
on Day 11 is a system that has never been tested. Build the thin ugly version early and
thicken it.

---

## Ownership

| # | Owner | Workstream | Task file |
|---|---|---|---|
| 1 | **Karam** | Integration lead + unified data pipeline | [`01-karam.md`](01-karam.md) |
| 2 | **Mahdi** | Model layer + DevOps | [`02-mahdi.md`](02-mahdi.md) |
| 3 | **Nizar** | Supabase Cloud + live forcing | [`03-nizar.md`](03-nizar.md) |
| 4 | **Pulga** | Backend, exposure engine, RAG | [`04-pulga.md`](04-pulga.md) |
| 5 | **Abd** | Marine transport + validation | [`05-abd.md`](05-abd.md) |
| 6 | **Ali** | Frontend, all of it | [`06-ali.md`](06-ali.md) |

**Karam is integration lead.** That means merges, schema arbitration, and owning the fact
that the demo runs end to end. When two people disagree about a column name, he decides the
same day.

---

## Rules that carry over from Phase 1

These are why the Phase 1 work is trustworthy. They do not lapse because we are building an
app now.

1. **Missing is never zero, and nothing is interpolated.** A gap is reported as a gap.
2. **No fabricated geometry, ever.** If an input does not exist, the step is skipped and the
   skip is recorded — as `catchment_integration_status.json` did.
3. **Provisional data is named `*_PROVISIONAL`** and swapping it is a tracked checklist item.
4. **Every claim has evidence.** Processing scripts assert; QA scripts visualise. If a step
   has no figure or no test, it is assumed rather than verified.
5. **Source vs derived is labelled.** A paper-reported number, a timezone-converted number,
   and a number we computed are three different things and are never presented as one.
6. **Provenance is not bookkeeping.** Every product ID, version, access date, licence and
   known limitation goes in `docs/data_dictionary.md`, and it drives the UI's Data Sources
   panel.
7. **Never claim exactness.** The Gulf is narrower than three grid cells of the best free
   ocean model. We output probabilistic exposure zones with stated confidence, and we say so
   before a judge finds it.

---

## Day 12 gate

```bash
grep -ri PROVISIONAL --include='*.py' --include='*.md' .
ls data/**/*PROVISIONAL* data/**/*FIXTURE* 2>/dev/null
```

Anything still matching on 12 August is either swapped or **explicitly declared a known
placeholder in the demo and the validation report**. No silent placeholders reach the stage.
