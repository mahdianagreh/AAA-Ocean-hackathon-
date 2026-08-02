# 17 · Technical — Scaling, data volumes and cost to run

**Part D. What it costs to operate, what breaks at scale, and what porting to a new coast
actually involves.**

---

## 1 · Measured data volumes

**[sourced]** All figures measured from the repository or reported in
[`docs/MASTER_TASK_SUMMARY.md`](../MASTER_TASK_SUMMARY.md) §12.

| Artefact | Size |
|---|---|
| Committed processed data (whole repo) | **7.6 MB** |
| `osm_aqaba.gpkg` | 5.0 MB |
| `depth_utm36n.tif` | 2.4 MB |
| `coastline.gpkg` | 148 KB |
| `reef_zones_PROVISIONAL.gpkg` | 120 KB |
| Processed IMERG event NetCDF (156 granules → one file) | **126.3 KB** |
| Processed ERA5-Land event NetCDF | **166.1 KB** |
| Antecedent features Parquet (20 cells) | **21.6 KB** |
| Rainfall candidates Parquet | 12.5 KB |
| IMERG Early live output | 52.3 KB |

**[derived]** The critical number: **one full event, fully processed, is ~350 KB.** A decade
of events at ~10 events/year is under 40 MB. **This is a small-data problem wearing
big-data clothing**, and that is entirely because of one design decision.

### The decision that makes this cheap

**[sourced]** Harmony spatial + variable subsetting returns only `Grid/precipitation` inside
the bounding box — **~44 KB per granule versus ~7.6 MB for a full-globe HDF5 granule**
(`backend/src/ingestion/imerg.py` module docstring). That is a **~175× reduction**, stated in
the capability report as the reason variable subsetting is deliberate.

**[derived]** Without it: 26 years of half-hourly global IMERG ≈ **455,000 files ≈ 13 TB**
([`data-model.md`](https://github.com/mahdianagreh/AAA-Ocean-hackathon-/blob/mahdi/data-model.md),
branch `mahdi`). With it, the same period over the Aqaba box is a few GB. **Server-side
subsetting is not an optimisation here — it is the difference between possible and
impossible.**

---

## 2 · Compute profile

**[judgement]** Component by component:

| Component | Profile | Constraint |
|---|---|---|
| IMERG retrieval | Network-bound; Harmony job latency dominates | 156 granules ≈ 4 Harmony jobs at `chunk_granules=48` |
| ERA5-Land retrieval | **Queue-bound** — CDS requests queue, sometimes for hours | The real bottleneck for a live system |
| Rolling accumulations | Trivial — numpy over a 5×4×156 array | None |
| Catchment aggregation | Vector overlay, seconds | None |
| Antecedent features | Trivial | None |
| **Particle simulation** | The only real compute | Concept doc §17.2 specifies **5,000 particles, 24 h, 30-min steps** = 240,000 particle-steps. Seconds on one core. |
| Plume detection (Sentinel-2) | Heaviest — 10 m imagery over the AOI | Per-event, not continuous |

**[derived]** **None of this needs a GPU or a cluster.** The concept doc's own parameters
describe a numerical problem that runs comfortably on a laptop. The infrastructure argument
is about *scheduling and reliability*, not horsepower.

---

## 3 · Cost to run

**[assumption]** Modelled from the volumes above, at commodity cloud rates.

| Item | Per site, per month |
|---|---|
| Scheduled ingestion (a few CPU-hours/day) | $60 – 200 |
| On-demand simulation | $20 – 80 |
| Object storage (raw archive + processed) | $20 – 60 |
| PostGIS instance | $30 – 100 |
| Frontend / CDN | $10 – 40 |
| **Total** | **~$140 – 480/month** → **$1.7k – 5.8k/yr** |

**[derived]** Against the $40k–120k licence assumed in
[`13-business-model-and-unit-economics.md`](13-business-model-and-unit-economics.md),
infrastructure is **2–8% of revenue**. The cost base is not the constraint; **expert labour
is** — see §6.

**Cost anchor at maturity [sourced]:** eReefs, the mature comparable, has drawn roughly
**AU$11 M** (Australian Government + private sector, as of 2015), **AU$3 M** (Queensland
Government), **AU$9.6 M** via the Reef Trust Partnership, and **AU$2.3 M** for
"Operationalising eReefs" — on the order of **AU$25–26 M cumulative**. That is what the
full-fidelity, 3D, biogeochemical version of this capability costs for one reef system.
Useful for framing: ReefShield is not proposing to build that; it is proposing the open-data
decision-support layer for coasts that will never receive it.

---

## 4 · What breaks at scale

**[judgement]** Ranked by how soon it bites.

| # | Breaks | When | Fix |
|---|---|---|---|
| 1 | **CDS queue latency** — ERA5-Land requests queue unpredictably | At the first live forecast deployment | Pre-fetch on a schedule; never put CDS in a request path |
| 2 | **Harmony job limits** — `max_granules=500` guard aborts large windows | On any multi-year historical sweep (needed to make candidate mining exhaustive) | Chunk across jobs; the code already supports `chunk_granules` |
| 3 | **`sys.path` hacks** — every script does `sys.path.insert(0, ...)` | On first containerised deployment | Make `backend/src` an installable package. Small change, unavoidable eventually. |
| 4 | **No dependency manifest** | Already broken — the suite cannot be run without reconstructing the environment from markdown | `pyproject.toml`. One hour. |
| 5 | **Ocean model resolution** — Copernicus 1/12° (~9 km) across a **14–26 km** gulf | Already known and documented | Unfixable with free data. Output probabilistic zones, state it, and cross-check against HYCOM. |
| 6 | **Manual plume QC** | At ~5 sites, when it becomes the dominant cost | Build the labelled mask library now so segmentation can be automated later |
| 7 | **Per-site config sprawl** | At ~10 sites | The YAML config system already anticipates this well |

---

## 5 · Porting to a new coast — the honest cost

**[judgement]** Corrected after inspecting branch `mahdi`.

| Step | Reusable? | Real effort |
|---|---|---|
| IMERG ingestion | ✅ **Verbatim** | 0 — arbitrary bbox proven, tested with a `[-10, 40, -9, 41]` box **[sourced]** |
| ERA5-Land ingestion | ✅ **Verbatim** | 0 |
| Antecedent features | ✅ **Verbatim** | 0 — windows and event time are arguments |
| Config / runner | ✅ **Verbatim** | New YAML |
| DEM fetch + flow routing | ⚙️ Re-run | Hours of compute |
| **Catchment delineation** | ⚠️ **Code edit** | `06_catchments.py` hard-codes `country == "Jordan"` and `JORDAN_MAX_DIST_M`; `01_make_aoi.py` hard-codes `MARINE_BBOX`. **Parameterise these two before the second site.** |
| Land cover / soil / OSM | ⚙️ Re-run | Global sources; scripted |
| Reef habitat | ⚙️ Re-run | Allen Coral Atlas is global |
| Bathymetry / coastline | ⚙️ Re-run | GMRT/GEBCO global |
| Ocean currents | ⚠️ Degrades | Copernicus 1/12° is *worse* on an open coast than in a confined gulf |
| Plume detection | ⚠️ **Recalibrate** | The "clear water = normal" baseline fails where water is naturally turbid (Oman) **[sourced]** |
| **Validation event** | ❌ **New every time** | Documented event + cloud-free post-event scene + manual QC. **This is the real cost.** |

**[derived]** Estimated first-time porting effort to a new coast: **~15–25 person-days**,
of which **60–70% is validation**, not engineering. That is the number behind the deployment
fee in [`13-business-model-and-unit-economics.md`](13-business-model-and-unit-economics.md)
§2.1.

---

## 6 · The one structural cost problem

**[judgement]** The concept doc §10.5 is explicit that manual QC of the observed plume mask
is **the method, not a shortcut**, and warns against starting with a U-Net because the
labelled set will be tiny.

That is correct science and a real business problem: **it means every validation event
carries human cost that does not fall with scale.**

**The resolution is to treat every manually QC'd mask as a capital asset, not a
deliverable.** Store them, version them, and keep them in a consistent schema from the first
one. At roughly 50–100 labelled masks, segmentation becomes trainable and the marginal cost
of a new site's validation drops sharply. That transition is the single highest-leverage
margin improvement available to the product, and nothing in the current codebase is set up to
accumulate toward it.

**Recommendation:** create `data/processed/plume/masks/` with a fixed schema and a manifest
row per mask, **before** the first mask is produced. Cheap now, expensive to retrofit.
