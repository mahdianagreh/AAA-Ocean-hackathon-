# 08 · Prior art and competitive landscape

**What already exists, what it does, and precisely where the gap is.**

This is the section that answers the concept doc's §5.2 warning and the §28.4 judge
question *"is this just a satellite dashboard?"*

---

## The short version

| System | Does it forecast? | Land→sea chain? | Reef exposure? | Arid coast? | Coverage |
|---|---|---|---|---|---|
| **eReefs** (AU) | ✅ near-real-time | ✅ full | ✅ | ❌ wet tropics | GBR only |
| **NOAA Coral Reef Watch** | ✅ thermal only | ❌ | ❌ | n/a | 95% of reefs (thermal) |
| **NOAA CRW ocean colour** | ⚠️ nowcast, **experimental** | ❌ | ❌ | ❌ | **Hawaii + Puerto Rico only** |
| **Allen Coral Atlas** | ❌ static | ❌ | ❌ habitat only | ✅ global | Global shallow reef |
| **WaveFoRCE** | ✅ | ❌ wave flooding | ❌ | n/a | In development |
| **Ridge-to-Reef programmes** | ❌ retrospective | ✅ planning-scale | ⚠️ | ⚠️ some | Site-specific |
| **ReefShield** | ✅ | ✅ | ✅ | ✅ | Arid reef coasts |

---

## 1 · eReefs — the closest thing to a competitor, and the best validation available

**What it is.** A partnership between the **Australian Institute of Marine Science, the
Bureau of Meteorology, CSIRO and the Queensland Government** — described as the **world's
largest reef forecasting and modelling program**
([eReefs, *Journal of Operational Oceanography*](https://www.tandfonline.com/doi/full/10.1080/1755876X.2019.1650589))
**[sourced]**.

**What it does.** Operational provision of **near-real-time hydrodynamic, water quality and
optical conditions** over the reef, plus prognostic scenarios to support catchment
management policy **[sourced]**. It includes hydrodynamic, sediment, wave and
biogeochemistry models, simulating **transport and fate of waterborne material and its
impact on reef water quality** **[sourced]**. It runs routinely in near-real-time for
emergent events including **floods, dredge plumes, phytoplankton blooms, cyclones, vessel
groundings and bleaching** **[sourced]**, and models water quality in 3D using NASA and ESA
Sentinel-3 data **[sourced]**.

### Why this is good news for the pitch, not bad news

**[judgement]** Three arguments, in order of usefulness:

1. **It proves the concept works and gets funded.** If a judge asks "would anyone actually
   pay for this?", the answer is: Australia already does, at national scale, through four
   agencies. ReefShield is not speculative capability — it is an existing capability class,
   absent from an entire climate zone.
2. **It does not transfer.** eReefs assumes perennial gauged rivers, wet-tropics hydrology,
   dense in-situ instrumentation and a decade of national investment. The Gulf of Aqaba has
   **27 mm/yr of rain, no perennial rivers, no local gauges, and an ocean model too coarse
   to resolve the basin**. Porting eReefs to Aqaba is not a configuration change; the
   hydrological model has nothing to ingest.
3. **It sets the honest ceiling.** ReefShield in two weeks is not eReefs. Saying "eReefs is
   what this looks like at maturity, and we are demonstrating the open-data path to it for
   coasts that will never get a four-agency programme" is a stronger and more credible
   claim than pretending no prior art exists.

**Recommended framing for the deck [judgement]:**

> "Australia built eReefs for the Great Barrier Reef with four national agencies. It works.
> It also assumes rivers that flow year-round and catchments with gauges. Aqaba has 27 mm
> of rain a year and neither. We are showing that the same decision-support layer can be
> built for a data-poor arid coast out of open satellite data alone."

---

## 2 · NOAA Coral Reef Watch — global thermal, almost no water quality

**What it covers.** The daily global 5 km product suite — SST/CoralTemp, SST Anomaly,
Bleaching HotSpot, Degree Heating Week, Bleaching Alert Area — allows **"direct monitoring
of 95% of global coral reefs and significantly reducing data gaps caused by cloud cover"**
([NOAA CRW 5 km suite](https://coralreefwatch.noaa.gov/product/5km/index.php))
**[sourced, verified against the product page]**.

**What it does not cover.** The core products are thermal stress and bleaching risk. There
is no global water-quality or land-based-pollution product.

**The critical detail — stated precisely.** The CRW product catalogue lists exactly one
ocean-colour offering:

> **"Chlorophyll-*a* and Kd(490) monitoring at 750 m from VIIRS satellite (Hawaii and
> Puerto Rico)"** — listed at **experimental status, v1.0**
> ([NOAA CRW Product Overview](https://coralreefwatch.noaa.gov/satellite/product_overview.php))
> **[sourced, verified verbatim]**

Two precision notes so nobody overstates this:

- It is **chlorophyll-*a* and Kd(490)** — Kd(490) is the diffuse attenuation coefficient, a
  **water-clarity proxy**. Calling it "turbidity" is a fair gloss but not the product's own
  label.
- The product page says **Hawaii and Puerto Rico**, not "West Maui and Puerto Rico". The
  West Maui framing appears in secondary descriptions of why the product was developed
  (post-rain-event monitoring for reef managers); the product's own stated coverage is the
  broader Hawaii region.

**[judgement]** With that precision in place, it is still the single strongest
market-validation fact in this document:

- A US federal agency independently identified **post-rainfall water clarity on reefs** as a
  management need worth building a dedicated near-real-time product for.
- It built that product for **two regions on Earth**, and it is still **experimental**.
- It is a **nowcast from ocean colour** — it observes conditions that already exist. It does
  not forecast, does not model the land side, does not attribute to a catchment, and does
  not produce reef-zone exposure scores.

So: the need is federally validated; the coverage is two regions; it is experimental; and
even there the product is observational, not predictive. That is the gap, stated in someone
else's budget.

---

## 3 · Allen Coral Atlas — habitat, not risk

Global shallow-reef geomorphic and benthic habitat mapping at 5 m in the Earth Engine
product (concept doc §11.11) **[sourced]**. It is an **input** to ReefShield — Pulga's
Component G depends on it — not a competitor. It maps **habitat, not sensitivity**, as
[`docs/pitch_limitations.md`](../../pitch_limitations.md) §5 already states honestly.

---

## 4 · WaveFoRCE — adjacent hazard, same coasts

An international team associated with **GEO Blue Planet** is developing a **wave-driven
flood-forecasting early-warning system for coral reef-lined coasts (WaveFoRCE)**
([USGS](https://www.usgs.gov/publications/wave-driven-flood-forecasting-reef-lined-coasts-early-warning-system-waveforce))
**[sourced]**. The motivation is that tools built for sandy shorelines do not predict
wave-driven flooding on reef-lined coasts, and existing reef-coast flood models have been
implemented in only a small number of places because they are costly and compute-heavy
**[sourced]**.

**[judgement]** This is the **inverse** of ReefShield — sea-to-land hazard rather than
land-to-sea. It is not a competitor, and it is arguably a future integration partner: the
same coastal communities, the same reef geometry, the same open-data philosophy. Worth
naming in the pitch as evidence that reef-coast early-warning systems are an active,
funded research direction.

---

## 5 · Ridge-to-Reef programmes — management, not forecasting

The **West Maui R2R** initiative, the **Guánica Bay** partnership, and the broader **US Coral
Reef Task Force** watershed priorities all target land-based sediment reaching reefs
**[sourced]**. They produce watershed management plans, fund erosion controls, and run
before/after coral monitoring to **evaluate the efficacy of implemented management
practices** **[sourced]**.

**[judgement]** These operate on a *planning* timescale — years — and are *retrospective* in
their monitoring. None of them answers "a storm is forecast for tonight; which reef zone
should we sample tomorrow morning?" That question is unowned everywhere I looked.

---

## 6 · Where the gap actually is

**[derived]** Composing the above:

| Capability | Who has it | Where |
|---|---|---|
| Global reef thermal forecasting | NOAA CRW | Everywhere |
| Global reef habitat mapping | Allen Coral Atlas | Everywhere |
| Operational land→sea sediment forecasting | eReefs | GBR only |
| Post-rain water-clarity nowcast (experimental) | NOAA CRW | Hawaii + Puerto Rico only |
| Wave-driven reef-coast flood EWS | WaveFoRCE | In development |
| Watershed sediment management | R2R programmes | Site-specific, retrospective |
| **Land→sea sediment forecasting on an arid coast** | **nobody** | **—** |

### The defensible novelty statement

Replacing the placeholder in [`aqaba_aqua_ai_concept.md`](../../../aqaba_aqua_ai_concept.md)
§5.2, this is what the search supports:

> **Every component of ReefShield exists somewhere.** Flood forecasting, plume transport
> modelling, satellite turbidity detection and reef habitat mapping are all established
> fields with mature products.
>
> **The integration does not exist for an arid coast.** The only operational system that
> chains rainfall → catchment → plume → reef exposure is eReefs, built for the Great
> Barrier Reef by four national agencies, and it assumes perennial gauged rivers. The only
> post-rain reef water-clarity products are experimental NOAA nowcasts for two regions, and they model
> neither the land side nor the forecast.
>
> **ReefShield's contribution is that chain, on a hyper-arid coast, from open data only,
> with no local instrumentation required.**

---

## 7 · Risks this creates for the pitch

**[judgement]**

1. **A judge who knows eReefs may ask "why not just use eReefs?"** Answer prepared above.
   Do not be caught unaware of it — that is the failure mode.
2. **The Curaçao surface-connectivity paper (Ocean Science, 2025)** models land-derived
   substance transport at the sea surface **[sourced]**. Somebody should read it before the
   team claims the marine-transport half is unaddressed anywhere.
3. **Wadi Watir flash-flood forecasting with WRF already exists** on the Egyptian side
   **[sourced]**. The atmospheric/land half is not novel in this region either. The novelty
   is continuing past the shoreline — which is exactly how the concept doc §28.4 already
   frames it. Good; keep that framing.
