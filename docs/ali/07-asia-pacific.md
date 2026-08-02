# 07 · Rest of World — Asia-Pacific, and the counterexamples

**Part B. West Maui, plus the two Australian cases that do *not* fit — and why that is
useful.**

> **The short version.** None of these three is a market. All three are **arguments.**
>
> **West Maui (7/12)** shows the mature end-state — watershed plans, agency partnership,
> before/after monitoring — and shows the gap **even in a well-funded site**: the monitoring is
> retrospective. *Nobody there forecasts the next plume either.*
>
> **Ningaloo (≈6/12) is the site that disciplines the whole thesis.** Its reef sits close to shore
> **because** there is no runoff. Aridity is not the hazard; aridity *plus* four other conditions
> is. Being able to name a famous arid reef coast that fails the rubric is what makes the rubric
> credible.
>
> **Burdekin / GBR** is the **existence proof and the price tag**: governments will fund exactly
> this capability at national scale, and the version they funded assumes data richness no arid
> coast has.
>
> **The most important number in this doc is a risk, not a market:** transmission loss of
> **13.2% → 98%** (20–85% in the Negev). Most of a desert flood can soak into the wadi bed and
> never reach the sea, **and the pipeline does not model this.**

---

## Site 18 · West Maui, Hawaii — Score 7/12

**Fits the mechanism, but is the most heavily managed site in the scan.**

| Criterion | Score | Evidence |
|---|---|---|
| C1 ephemeral | 1 | Leeward, semi-arid; seasonal streams |
| C2 intense episodic | 2 | Storm-driven sediment delivery |
| C3 reef proximity | 2 | Reefs directly offshore of the stream mouths **[sourced]** |
| C4 confined basin | 1 | Open coast, but nearshore retention |
| C5 development | 1 | Former plantation agriculture, dirt roads, resort development **[sourced]** |
| C6 data-poor | **0** | Funded R2R programme + NOAA experimental ocean-colour product covering Hawaii |

### What already exists there

- The **West Maui Ridge to Reef (R2R)** initiative covers ~24,000 acres from Kāʻanapali to
  Honolua and from the summit of Puʻu Kukui to the outer reef **[sourced]**.
- The **US Coral Reef Task Force designated West Maui a priority Pacific partnership in
  2011**, starting with Wahikuli and Honokōwai and expanding to Kahana, Honokahua and
  Honolua **[sourced]**.
- Formal **watershed management plans** exist with explicit goals to *measurably reduce
  erosion and sediment loads generated on dirt roads, fields and waterways and carried to
  the coral reefs* **[sourced]**.
- **NOAA runs a near-real-time VIIRS ocean-colour product** (chlorophyll-*a* and Kd(490), 750 m) covering **Hawaii**, at experimental status **[sourced, verified verbatim]**.
- Baseline coral demographic and benthic-cover assessments are established at the stream
  mouths to **evaluate the efficacy of implemented management practices** **[sourced]**.

**[judgement]** West Maui is not a customer. It is the **template for what a mature version
of this problem's management looks like**, and it is worth studying for two reasons:

1. It shows the endpoint — watershed plans, agency partnership, before/after monitoring —
   that ReefShield's Phase 3/4 (concept doc §26) is aiming at.
2. It shows the **gap even in a well-funded site**: the monitoring is retrospective
   ("did our management work?"), not predictive ("what happens in the next 12 hours?").
   Nobody there is forecasting the next plume either.

---

## Counterexample 1 · Ningaloo Reef, Western Australia — Score ~6/12, and it fails on the
right criteria

**This is the site that disciplines the whole thesis.**

Ningaloo is arid. It has ephemeral rivers that **flow only after rare heavy rainfall**
**[sourced]**. It has a fringing reef exceptionally close to the mainland. It is subject to
**tropical cyclones roughly every 2–3 years, with winds over 100 km/h and high
precipitation** **[sourced]**.

And yet:

> **Ningaloo Reef's arid climate results in low run-off and very high water quality for
> coral reef building. Extremely low average annual rainfall and lack of run-off have
> contributed to Ningaloo Reef's proximity to the mainland.** **[sourced]**

**The reef is close to shore *because* there is no runoff.** Terrestrial input is the thing
that normally prevents fringing reefs from forming right against a coastline; its absence is
why Ningaloo exists in that configuration.

### What this teaches — three things, all useful in the pitch

**[judgement]**

1. **Aridity is not the hazard.** The hazard is aridity *plus* a catchment steep and large
   enough to concentrate flow, *plus* development that amplifies and contaminates runoff,
   *plus* a confined basin, *plus* rain intensity high enough to overcome transmission
   losses in the wadi bed. Aqaba has all five; Ningaloo has essentially one.
2. **Transmission loss is the hidden variable.** Kalman et al. cite transmission-loss rates
   ranging from **13.2% in Australian desert streams to 98% in Saudi Arabia**, with
   **20–85% at Nahal Zin in Israel's Negev** **[sourced]**. In other words, most of a desert
   flood can simply soak into the wadi bed and never reach the sea. **This is a real
   scientific risk to the project's core assumption and it is not currently modelled** —
   see the recommendation below.
3. **It gives the team a clean answer to "does this work everywhere?"** — "No. Here are the
   five conditions, and here is a famous arid reef coast that fails them. That is why we
   screen sites instead of claiming the whole desert."

> ### Recommendation to the team
> Transmission loss should appear in [`docs/pitch_limitations.md`](../pitch_limitations.md)
> as a named limitation. The pipeline currently derives rainfall over the catchment and
> treats it as a runoff driver; between 13% and 98% of that water may never arrive at the
> coast depending on the site. For Aqaba specifically, the Negev range (20–85%) is the best
> available proxy and it is very wide. **[judgement]**

---

## Counterexample 2 · The Burdekin and the Great Barrier Reef — a different problem, already
solved

The GBR's dry-tropics catchments (notably the Burdekin) deliver enormous sediment loads to
reef waters, and flood plumes carrying **fine sediment, nutrients and pesticides** are a
documented major threat **[sourced]**.

**But it fails the signature on C1 and C6:**

- Perennial and large seasonal rivers, gauged catchments, decades of monitoring.
- **eReefs** already provides operational near-real-time hydrodynamic, sediment and water
  quality modelling — see [`08-prior-art.md`](08-prior-art.md).

**[judgement]** The GBR's role in this scan is as the **existence proof and the price tag**:
it demonstrates that governments will fund exactly this capability at national scale, and
it demonstrates that the version they funded assumes data richness that no arid coast has.

---

## Elsewhere in Australia — Pilbara / Dampier

Arid, cyclone-exposed, with coral communities and heavy industrial/port development. Little
searchable published work linking wadi-equivalent flood sediment to reef condition
**[judgement]**; the dominant sediment issue is **dredging** for iron-ore ports, which is a
scheduled industrial activity rather than a weather event. Same adjacency as the Arabian
Gulf: a dredge-plume product, not this product.

---

## Net read for Asia-Pacific

**[judgement]**

| Site | Verdict |
|---|---|
| **West Maui** | Not a market — already funded and monitored. Study it as the model of a mature end-state, and note that even there nobody forecasts. |
| **Ningaloo** | Not a market, and *say so in the pitch*. It is the counterexample that makes the screening rubric credible. |
| **Burdekin / GBR** | Not a market. Existence proof that this capability gets funded at national scale, plus the source of the transmission-loss caveat. |
| **Pilbara** | Adjacent (dredging), not this product. |
