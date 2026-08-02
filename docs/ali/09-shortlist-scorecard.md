# 09 · Shortlist and scorecard

**All 18 assessed sites, scored against the rubric in
[`01-problem-signature.md`](01-problem-signature.md), split MENA / Rest of World.**

Scores are **[judgement]** built on **[sourced]** evidence in the regional files. Each
criterion is 0–2; maximum 12.

Legend: **C1** ephemeral drainage · **C2** intense episodic rain · **C3** reef proximity ·
**C4** confined basin · **C5** development at outlet · **C6** data-poor / unserved

---

## Part A — MENA

| Site | Country | C1 | C2 | C3 | C4 | C5 | C6 | **Total** | Tier |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|---|
| **Aqaba** *(baseline)* | Jordan | 2 | 2 | 2 | 2 | 2 | 2 | **12** | 1 |
| **Eilat** | Israel | 2 | 2 | 2 | 2 | 2 | 1 | **11** | 1 |
| **Taba / Nuweiba / Dahab** | Egypt | 2 | 2 | 2 | 2 | 2 | 1 | **11** | 1 |
| **Saudi Aqaba coast / NEOM** | Saudi Arabia | 2 | 2 | 2 | 2 | 2 | 1 | **11** | 1 |
| **Hurghada → Marsa Alam** | Egypt | 2 | 2 | 2 | 1 | 2 | 2 | **11** | 1 |
| **Muscat / Daymaniyat** | Oman | 2 | 2 | 2 | 1 | 2 | 2 | **11** | 1 |
| **Fujairah east coast** | UAE | 2 | 2 | 1 | 1 | 2 | 2 | **10** | 2 |
| **Jeddah / central Red Sea** | Saudi Arabia | 2 | 2 | 1 | 1 | 2 | 2 | **10** | 2 |
| **Port Sudan / Dungonab** | Sudan | 2 | 1 | 2 | 2 | 1 | 2 | **10** | 2 ✗ access |
| **Dhofar / Salalah** | Oman | 1 | 2 | 2 | 1 | 1 | 2 | **9** | 2 |
| **Djibouti / Eritrea / Socotra** | multiple | 2 | 1 | 2 | 1 | 0 | 2 | **8** | 2 |
| **Makran / Chabahar** | Iran | 2 | 2 | 1 | 0 | 0 | 2 | **7** | 3 |
| **Arabian Gulf (Bahrain/Qatar/AUH)** | multiple | 1 | 0 | 1 | 2 | 2 | 1 | **7** | ✗ wrong trigger |

**Six MENA sites score Tier 1.** Four of them share a single 15–25 km basin with Aqaba.

---

## Part B — Rest of World

| Site | Country | C1 | C2 | C3 | C4 | C5 | C6 | **Total** | Tier |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|---|
| **Bonaire / Curaçao** | Netherlands (Caribbean) | 2 | 2 | 2 | 1 | 2 | 2 | **11** | 1 |
| **Toliara / Ranobe Bay** | Madagascar | 1 | 2 | 2 | 2 | 1 | 2 | **10** | 2 |
| **Baja California Sur** | Mexico | 2 | 2 | 1 | 1 | 1 | 2 | **9** | 2 |
| **Guánica / Coral Bay** | USA (PR / USVI) | 1 | 2 | 2 | 2 | 2 | **0** | **9** | ✗ already served |
| **Malindi–Watamu** | Kenya | **0** | 1 | 2 | 1 | 2 | 2 | **8** | 3 |
| **West Maui** | USA (Hawaii) | 1 | 2 | 2 | 1 | 1 | **0** | **7** | ✗ already served |
| **Ningaloo** | Australia | 2 | 1 | 2 | 1 | 0 | 0 | **6** | ✗ counterexample |
| **Burdekin / GBR** | Australia | **0** | 2 | 2 | 1 | 2 | **0** | **7** | ✗ already served |

Note how the exclusions cluster on **C1** (perennial rivers) and **C6** (already served).
Those are the two criteria that do the real screening work.

---

## Recommended expansion sequence

**[judgement]** Ordered by *effort to first demo*, not by market size.

### Phase 0 — the hackathon (now)
**Aqaba.** Do not dilute. One validated backtest beats five unvalidated map pins — the
concept doc's own §25 risk table flags "dashboard becomes more important than science."

### Phase 1 — the free win (a slide, not a build)
**The Gulf of Aqaba basin: Eilat, Taba/Nuweiba, Haql/NEOM.** No new code. The demo already
covers this water. Reframe the existing map as a four-country basin and state that the
October 2016 storm hit all four. **Cost: one slide. Value: turns a city tool into a regional
platform.**

### Phase 2 — the first real port (weeks)
**Egyptian Red Sea (Hurghada → Marsa Alam).** Largest reef-tourism market in the region,
documented flood-sediment layers on the reefs, same language and institutional context,
Allen Coral Atlas coverage. Needs: new AOI, new catchments, one documented event with a
clean post-event scene.

### Phase 3 — the funded buyer
**NEOM / Red Sea Global, Saudi Arabia.** Highest budget, active construction on the same
gulf, explicit reef-protection commitments. A working Jordanian demo is directly
demonstrable. **This is where the money is.**

### Phase 4 — the second climate zone
**Muscat / Daymaniyat, Oman.** Proves the platform handles the cyclone-driven variant, with
independent published evidence of reef damage from sedimentation and freshwater. Requires
recalibrating plume detection for naturally turbid water.

### Phase 5 — the non-MENA proof
**Bonaire.** Proves the product travels outside the Arab world with the same buyer persona
(dive tourism + marine park). Check the 2025 Curaçao connectivity paper first.

---

## What actually changes per site

**[judgement]** Reusability of the current codebase, from
[`docs/pipeline_capability_report.md`](../pipeline_capability_report.md) §2:

| Component | Reusable as-is? | Notes |
|---|---|---|
| IMERG ingestion | ✅ **Yes** | Arbitrary bbox and time range already proven — tested with a `[-10, 40, -9, 41]` box |
| ERA5-Land ingestion | ✅ **Yes** | Same |
| Antecedent features | ✅ **Yes** | Event time and windows are all arguments |
| Config-driven runner | ✅ **Yes** | New site = new YAML |
| Catchment delineation | ⚙️ **Re-run + code edit** | Mahdi's DEM chain works anywhere hydrologically, but `01_make_aoi.py` hard-codes `MARINE_BBOX` and `06_catchments.py` hard-codes `country == "Jordan"`. Parameterising those two constants is the actual porting task **[verified against branch `mahdi`]** |
| Land cover / soil / urban | ⚙️ Re-run | Pulga's scripts are global-source-driven |
| Reef habitat | ⚙️ Re-run | Allen Coral Atlas is global |
| Bathymetry / coastline | ⚙️ Re-run | GMRT/GEBCO global |
| Ocean currents | ⚠️ Degrades | Copernicus 1/12° is worse outside confined basins, not better |
| Plume detection (spectral) | ⚠️ Recalibrate | Baseline "clear water" assumption breaks in naturally turbid water (Oman) |
| **Validation event** | ❌ **New each time** | Documented event + clean post-event scene. **This is the real cost of expansion.** |

**The honest scaling statement for the pitch [judgement]:**

> Moving ReefShield to a new coast is a configuration change for the data pipeline and a
> re-run for the terrain and habitat layers. What does not transfer is validation: every new
> site needs its own documented flood event and its own cloud-free post-event satellite
> scene. That is the constraint that sets our expansion rate — not the software.

---

## One-line answers for the judges

**"Is this only for Aqaba?"**
> No. Six MENA sites score identically to Aqaba on our screening rubric, four of them in the
> same 15–25 km basin. The October 2016 storm we model flooded four countries at once.

**"How big is this?"**
> More than a quarter of the world's reefs face watershed-based pollution. Reef tourism is
> ~$36 billion a year across 100+ countries. We are not addressing all of that — we screen
> for six specific conditions, and we exclude sites like Ningaloo that look similar and
> aren't.

**"Hasn't someone built this?"**
> For the Great Barrier Reef, yes — eReefs, four national agencies, and it assumes
> perennial gauged rivers. For arid coasts, no. NOAA's only post-rain water-clarity product
> covers exactly two regions on Earth, is still experimental, and models neither the land
> side nor the forecast.
