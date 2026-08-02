# ReefShield — research, business and technical scan

**Where else does this problem happen · who pays for solving it · what is actually built**

**Author:** Ali · **Date:** 2026-08-02 · **20 documents, ~36,400 words, 51 sources**

> ### Scope — read this before wiring anything to these files
>
> This folder is **pitch and market material**. It is **not an app surface** and it is **not in the
> RAG corpus**. It backs the market slide and answers *"is this only for Aqaba?"* in Q&A.
> Building it into the UI would spend frontend days on something one slide already covers.
> See [`00-phase2-plan.md`](../../../tasks/phase2/00-phase2-plan.md) §Sources and
> [`06-ali.md`](../../../tasks/phase2/06-ali.md) §One note on the research documents.
>
> Frontend build documentation lives in [`../frontend/`](../frontend/) — a different thing entirely.

> ### 👉 New here? Read [`00-summary.md`](00-summary.md) first
>
> It explains the whole research set **in plain English, on one page** — what the problem is, who
> would pay for it, what we've actually built, and what is currently going wrong. You can read it
> top to bottom without needing any of the others.
>
> Every other document opens with a **"The short version"** box, so you can skim any of them in
> about thirty seconds before deciding whether to read the detail.

---

## Why this exists

The concept doc, [`reefshield_aqaba_concept.md`](../../../reefshield_aqaba_concept.md) §5.2,
forbids claiming novelty without doing the search:

> The team should **not** claim global uniqueness unless a formal patent and literature
> search is completed.

This set is that search, extended to cover the two questions a judge asks immediately
afterwards: *who would pay for it*, and *what have you actually built*. Four parts:

| Part | Question | Docs |
|---|---|---|
| **Framing** | What makes a site have this problem? | 01 |
| **A — MENA** | Where else, in our region? | 02–04 |
| **B — Rest of World** | Where else, globally? | 05–07 |
| **C — Business** | Who buys, who funds, what does it cost? | 11–15 |
| **D — Technical** | What exists, what scales, what breaks? | 16–18 |
| **Cross-cutting** | Prior art, rankings, sources | 08–10 |

---

## The six findings that matter

### 1 · It is a category, not a one-off — and MENA is the densest cluster on Earth

Six MENA sites score as high as Aqaba on the screening rubric, and **four share one basin
14–26 km wide**. One storm hits Jordan, Israel, Egypt and Saudi Arabia in 48 hours. Globally,
**more than a quarter of the world's reefs face watershed-based pollution**
([WRI](https://www.wri.org/data/reefs-risk-watershed-based-pollution)).

### 2 · Aridity alone is not the problem — and this sharpens the pitch

**Ningaloo Reef is arid, reef-lined, and has excellent water quality *because* it has almost
no runoff.** The rubric in [`01-signature.md`](01-signature.md) deliberately
excludes it. Being able to say "no, not that one, and here's why" is what makes the screening
credible.

### 3 · There is a $10 million UNDP programme with our problem written into it

**This is the single most actionable finding in the set.** The GFCR *Gulf of Aqaba and
Northern Red Sea Resilient Reefs Programme* — UNDP convening, **USD 10 million** target,
running to 2030 — lists the **Aqaba Marine Reserve as a priority site**, names *"changed
rainfall patterns / intensity that could increase flows of freshwater, sediments and
pollution onto coral reefs"* as a **key threat**, and funds *"water quality / land-ocean
interface projects"* as a **protection outcome**. Separately, **GEF project 10905**
(USD 663k + USD 5.5M co-financing, IUCN/UNDP) is already in implementation at the same
reserve.

ReefShield is not adjacent to that programme. It is a missing component of it. Full detail:
[`14-funding.md`](14-funding.md).

### 4 · The prior art validates the concept and leaves the arid coast empty

**eReefs** does this operationally for the Great Barrier Reef — four national agencies,
~AU$26M cumulative — and assumes perennial gauged rivers. **NOAA's** only ocean-colour
water-clarity product covers **Hawaii and Puerto Rico** and is **experimental**. No
operational forecast-mode land-to-sea sediment system exists on any arid coast.
[`08-prior-art.md`](08-prior-art.md).

### 5 · Three of five workstreams are complete; the product layer does not exist

**5,570 lines** of production backend covering **6 of 8** planned ingestion sources but only
**1 of 8** planned subsystem directories. No API, no database, no frontend, no dependency
manifest, and the test suite has still never been run on this machine.
[`16-build-state.md`](16-build-state.md).

### 6 · The imagery gate has resolved — and it failed

**[sourced]** The project's own audit ([`docs/event_audit.md`](../../event_audit.md) §3) returns
**NO-GO for image-based validation**: the October 2016 plume dispersed **2.5–3.5 days before any
accessible satellite pass**, confirmed by Sentinel-2 and Landsat 8 independently. A **physical
null**, not a data-quality problem. The documented pivot is to validate against the Kalman et al.
**in-situ mooring record** instead — a quantitative target rather than a visual one.
[`18-risks.md`](18-risks.md) §1.5.

---

## Document index

### Start here

| # | File | Contents |
|---|---|---|
| 00 | [`00-summary.md`](00-summary.md) | **The whole set in plain English.** What the problem is · is it only Aqaba · has someone built it already · who pays · is it a real business · what's built · **what's going wrong now** · what not to cite |

### Framing

| # | File | Contents |
|---|---|---|
| 01 | [`01-signature.md`](01-signature.md) | The six-criterion rubric, scoring bands, the Ningaloo counterexample test |

### Part A — MENA

| # | File | Contents |
|---|---|---|
| 02 | [`02-aqaba.md`](02-aqaba.md) | Eilat, Sinai, Saudi/NEOM — Tier 1, same basin, transboundary machinery |
| 03 | [`03-red-sea.md`](03-red-sea.md) | Egyptian Red Sea, Jeddah, Sudan, Djibouti/Eritrea/Socotra |
| 04 | [`04-arabia.md`](04-arabia.md) | Oman, UAE, Iran — the cyclone-driven variant |

### Part B — Rest of World

| # | File | Contents |
|---|---|---|
| 05 | [`05-indian-ocean.md`](05-indian-ocean.md) | Madagascar, Kenya — semi-arid, land-use-driven |
| 06 | [`06-americas.md`](06-americas.md) | Bonaire/Curaçao, Baja California, Puerto Rico/USVI |
| 07 | [`07-asia-pacific.md`](07-asia-pacific.md) | West Maui, and the Australian counterexamples |

### Cross-cutting

| # | File | Contents |
|---|---|---|
| 08 | [`08-prior-art.md`](08-prior-art.md) | eReefs, NOAA CRW, Allen Coral Atlas, WaveFoRCE, R2R — and the gap |
| 09 | [`09-scorecard.md`](09-scorecard.md) | 21 scored sites, expansion sequence, judge one-liners |
| 10 | [`10-sources.md`](10-sources.md) | 51 sources with access level and what each supports |

### Part C — Business

| # | File | Contents |
|---|---|---|
| 11 | [`11-market.md`](11-market.md) | TAM/SAM/SOM with shown arithmetic; the reef-valuation trap; Aqaba value-at-risk |
| 12 | [`12-buyers.md`](12-buyers.md) | Four buyer archetypes, named contacts, value quantification |
| 13 | [`13-economics.md`](13-economics.md) | Revenue streams, cost structure, per-deployment unit economics |
| 14 | [`14-funding.md`](14-funding.md) | **The GFCR programme, GEF 10905, PERSGA, policy hooks, parametric insurance** |
| 15 | [`15-gtm.md`](15-gtm.md) | Five-move GTM sequence, partnerships, commercial risk register |

### Part D — Technical

| # | File | Contents |
|---|---|---|
| 16 | [`16-build-state.md`](16-build-state.md) | Measured build audit vs the concept doc's own plan; critical path; ranked actions |
| 17 | [`17-scaling.md`](17-scaling.md) | Data volumes, compute profile, cost to run, porting cost |
| 18 | [`18-risks.md`](18-risks.md) | Six undocumented risks + re-scored concept doc §25 risks |

---

## How to read the evidence markers

Follows the project's source-vs-derived discipline ([`docs/event_dates.md`](../../event_dates.md) §3):

| Marker | Meaning |
|---|---|
| **[sourced]** | Stated in a cited document. Follow the link. |
| **[derived]** | Computed from sourced facts, with the reasoning shown. |
| **[judgement]** | My assessment. Arguable. Labelled so it is never mistaken for data. |
| **[assumption]** | A business number with no public comparable. Arithmetic shown so it can be replaced. |
| **[unverified]** | Encountered but not confirmed. **Do not cite.** |

---

## Corrections this research forces on the project's own docs

Findings that contradict or sharpen existing repo content. Each is a small fix that prevents
a wrong number reaching a slide.

| # | Repo doc | Issue |
|---|---|---|
| 1 | [`tasks/nizar.md`](../../../tasks/nizar.md) | States the gulf is "~15–25 km wide". Authoritative figure is **14–26 km, ~180 km long, average depth 800 m** |
| 2 | [`docs/event_dates.md`](../../event_dates.md) | The 82%/18 h figure is **water volume (109 million m³) across both the Eilat *and* Wadi Yutum catchments** — not rainfall depth over the Aqaba box |
| 3 | [`docs/pitch_limitations.md`](../../pitch_limitations.md) | **Transmission loss is missing** — 20–85% of a Negev flood can infiltrate the wadi bed and never reach the sea |
| 4 | [`docs/pipeline_capability_report.md`](../../pipeline_capability_report.md) §4.7 | The "Oct 2016 ordering anomaly" is **explained**: Kalman et al. name Wadi Yutum (= `AQ-C01`, 4,453 km²) as a generating catchment, and the download box is ~1,700 km² |
| 5 | Concept doc §19 | The published repo structure describes **8 directories that do not exist**. Do not show §9.1's architecture diagram as though it is the system |

---

## What I could not verify

1. **"~28,000 km of arid coastline worldwide."** Not in Kalman et al. (2025); Katz et al.
   (2015) is paywalled. **Do not cite.**
2. **The $6.91 bn GCF ocean figure** from the hackathon briefing — not independently confirmed.
3. **Aqaba Marine Reserve visitor numbers and management budget.** Area (2.45 km²), coastline
   (7 km) and dive sites (19) recovered; budget and visitors remain unread — the AMR
   management plan PDF blocks automated fetching.
4. **Current status of the GFCR full proposal.** Concept note signed late 2022 targeting a
   Jun 2023 proposal. Live or lapsed is unknown, and it determines whether §3 above is a
   channel or a history lesson.

---

## Corrections log — verification pass, 2026-08-02

The first draft was written from search summaries; every load-bearing claim was then checked
against primary sources. **Six were wrong**, logged here rather than silently fixed.

| # | As first written | What the source says | Fixed in |
|---|---|---|---|
| 1 | NOAA turbidity covers "Puerto Rico and West Maui" | *"Chlorophyll-a and Kd(490) … (**Hawaii and Puerto Rico**)"*, **experimental v1.0** | 06, 07, 08, README |
| 2 | Cyclone Gonu "50 deaths, $3.9 bn" | Sources vary: ~49–50 deaths, ~US$4–4.2 bn | 04, 10 |
| 3 | Gonu coral damage cited to *Twenty-year changes in coral near Muscat* | Actually *Oman's coral reefs: a unique ecosystem…* — **wrong paper** | 04, 10 |
| 4 | "Mahdi's DEM chain is location-agnostic" | It hard-codes `country == "Jordan"` and `MARINE_BBOX` | 03, 09, 17 |
| 5 | Eilat "12/12"; Puerto Rico "8/12" | Contradicted their own tables (11 and 9) | 02, 06 |
| 6 | Culebra road-erosion figures filed under "Guánica" | The 330–760× study is from **Isla de Culebra** | 06 |

**Verified unchanged:** Kalman sediment tonnages (24,000 t / 21,000 t), 27 mm/yr Eilat
rainfall, the 66 h / 18 h / 82% / 50 h / 3 h timings, transmission loss (13.2% / 98% /
20–85%), the authors' generalisability sentence, WRI's >25%, eReefs' "world's largest" and
four-agency partnership, NOAA's 95% thermal coverage, Ningaloo's low-runoff statements, and
every figure in the GFCR concept note.

---

## What this licenses the team to claim

**Safe [derived]:**

> ReefShield addresses a problem class that recurs along arid reef coasts worldwide, and no
> operational forecast-mode system for it exists on any of them. The nearest working
> analogue, Australia's eReefs, took four national agencies and assumes perennial gauged
> rivers. Meanwhile a $10 million UNDP programme for Gulf of Aqaba reefs already names
> increased sediment flows as a key threat and land-ocean interface work as a funded outcome.

**Unsafe — do not say:**

> Nobody has ever modelled sediment plumes / coral risk / flood forecasting.

False, and a judge will know. The novelty is the **integration on a data-poor arid coast**,
not the invention of any component.
