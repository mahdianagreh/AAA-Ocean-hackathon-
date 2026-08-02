# 01 · The problem signature

**What has to be true at a site before ReefShield is the right tool for it**

---

## Why a rubric rather than a list

"Desert coast with a reef" is too loose. It sweeps in Ningaloo, which is arid, reef-lined,
and has *excellent* water quality **because** it gets almost no runoff
([Australian Heritage Database](https://www.dcceew.gov.au/sites/default/files/documents/ningaloo.pdf))
**[sourced]**. A screening rule that flags Ningaloo as a customer is a broken rule, and a
judge who knows Ningaloo will use it to take the pitch apart.

So the signature has to be specific enough to *exclude* things. Six criteria, each scored
0–2, plus two modifiers.

---

## The six criteria

### C1 · Ephemeral, not perennial, drainage

The catchment is dry most of the time and discharges only during brief flood events —
hours to days. This is what makes the problem a *forecasting* problem rather than a
*management* problem: there is nothing to measure until suddenly there is.

In the northern Gulf of Aqaba, mean rainfall at Eilat is **27 mm/yr**, there are no
perennial rivers, and ephemeral rivers discharge water and sediment into the sea **only
during brief flooding events** ([Kalman et al. 2025,
NHESS](https://nhess.copernicus.org/articles/25/3201/2025/)) **[sourced]**.

| Score | Condition |
|---|---|
| 2 | Fully ephemeral; wadi/arroyo/rooi systems, no baseflow |
| 1 | Strongly seasonal river with long dry season |
| 0 | Perennial river with year-round discharge |

> **Why it matters for the model:** a perennial-river site can be monitored with in-situ
> gauges and modelled with continuous hydrology. An ephemeral site cannot — which is
> exactly why a satellite-and-reanalysis-driven approach earns its keep.

### C2 · Rare but high-intensity rainfall

The site gets convective or cyclonic rainfall that concentrates a year's water into hours.
Aqaba's October 2016 event delivered **≈82% of total rainfall in a concentrated 18-hour
spell** within a ≈66-hour event ([`docs/event_dates.md`](../event_dates.md), from Kalman et
al. 2025) **[sourced]**.

| Score | Condition |
|---|---|
| 2 | Documented flash-flood regime; convective or tropical-cyclone driven |
| 1 | Occasional intense rainfall, poorly documented |
| 0 | Rainfall spread evenly; no flash-flood regime |

### C3 · Reef or seagrass within a few kilometres of the outlet

The plume has to be able to reach the habitat before it disperses. Aqaba's reefs sit close
to shore and close to urban activity, roads, drainage outlets and ports
([concept doc §3.3](../../reefshield_aqaba_concept.md)) **[sourced]**.

| Score | Condition |
|---|---|
| 2 | Fringing reef within ~2 km of a wadi mouth |
| 1 | Reef 2–10 km away, or offshore banks |
| 0 | Reef far offshore or absent |

### C4 · Narrow shelf or restricted-flushing basin

A narrow, semi-enclosed basin keeps the plume in contact with habitat instead of diluting
it into open ocean. The Gulf of Aqaba is **~180 km long and 14–26 km wide, average depth
800 m** ([GFCR concept note](https://mptf.undp.org/sites/default/files/documents/2022-12/gulf_of_aqaba_and_n_red_sea_reefs_programme_redacted.pdf))
**[sourced]** — which is also why global 1/12° (~9 km) ocean models cannot resolve it, and
why the platform must output probabilistic exposure zones rather than trajectories.

| Score | Condition |
|---|---|
| 2 | Semi-enclosed gulf, bay, or lagoon; steep narrow shelf |
| 1 | Open coast with a shelf that retains material |
| 0 | Fully exposed open ocean, rapid dispersal |

### C5 · Development at the outlet

Urbanisation, ports, roads and industry both **increase** runoff (impervious surfaces) and
**add** contaminants (metals, oils, wastewater). Aqaba's reefs sit next to a working port
and a growing city **[sourced, concept doc §3.3]**.

| Score | Condition |
|---|---|
| 2 | City, port or industrial zone at the outlet |
| 1 | Roads, agriculture or scattered settlement |
| 0 | Undeveloped catchment |

### C6 · Data-poor and unmonitored

This is the criterion that decides whether ReefShield is *needed* or merely *possible*. If
a site already has gauged catchments, local current meters and an operational model, the
value proposition collapses — see the Burdekin/GBR discussion in
[`07-row-asia-pacific.md`](07-row-asia-pacific.md).

Kalman et al. explicitly note that **data limitations often prevent comprehensive analysis**
of these events elsewhere ([NHESS](https://nhess.copernicus.org/articles/25/3201/2025/))
**[sourced]**.

| Score | Condition |
|---|---|
| 2 | No gauges, no local ocean model, no operational monitoring |
| 1 | Some monitoring, no integration or forecasting |
| 0 | Operational system already running |

---

## Two modifiers

Not scored, but they change the sales story.

**M1 · Economic exposure.** Dive tourism, fisheries or a designated MPA at risk. Globally,
coral reef tourism generates roughly **US$36 billion a year across more than 100 countries
and territories**, from about **70 million visitor trips**
([Spalding et al. 2017](https://www.sciencedirect.com/science/article/pii/S0308597X17300635))
**[sourced]**. In Egypt, coastal tourism contributes **over 3.5% of GDP**
([MEEA](https://meea.sites.luc.edu/volume14/PDFS/MEEA%202011%20Coral%20reefs%20and%20tourism%20in%20Egypts%20Red%20Sea%2016%20mai%202011_3.pdf))
**[sourced]**.

**M2 · Transboundary basin.** If one storm hits several jurisdictions at once, no single
national agency can own the answer — which makes a shared platform the natural fit and
opens regional/multilateral funding. The Gulf of Aqaba is the strongest example anywhere
**[judgement]**.

---

## Scoring bands

Maximum 12.

| Total | Band | Meaning |
|---|---|---|
| 11–12 | **Tier 1 — near-identical** | Deploy with a config change and local habitat data |
| 8–10 | **Tier 2 — strong** | Same architecture; one component needs rework |
| 5–7 | **Tier 3 — partial** | Real problem, different mechanism; substantial adaptation |
| ≤4 | **Not a fit** | Either no problem, or already solved |

Full scored table in [`09-shortlist-scorecard.md`](09-shortlist-scorecard.md).

---

## The counterexample test

Before adding any site, check it against **Ningaloo**:

> Arid? Yes. Reef-lined? Yes. Fringing reef close to shore? Yes.
> **Runoff? Almost none — and that is why the water quality is excellent.**

Ningaloo scores 2 on C1 and C3 but near-zero on C2 (rare cyclones, but the arid climate
means low total runoff), C5 (undeveloped) and C6-value (it is inside a World Heritage
property with existing management). **Total ≈ 6, and the problem it has is cyclone
mechanical damage, not sediment exposure.**

If a candidate site looks like Ningaloo, the honest answer is "not our problem to solve."
Saying that out loud in the pitch is worth more than one extra pin on the map
**[judgement]**.

---

## Applying the rubric to Aqaba (the baseline)

| Criterion | Score | Evidence |
|---|---|---|
| C1 ephemeral drainage | 2 | 27 mm/yr, no perennial rivers **[sourced]** |
| C2 intense episodic rainfall | 2 | 82% of rain in 18 h, Oct 2016 **[sourced]** |
| C3 reef proximity | 2 | Fringing reef close to shore and to outlets **[sourced]** |
| C4 confined basin | 2 | Gulf 14–26 km wide **[sourced]** |
| C5 development at outlet | 2 | Port, city, industry at the coast **[sourced]** |
| C6 data-poor | 2 | No local gauges; global ocean models too coarse **[sourced]** |
| **Total** | **12/12** | |
| M1 economic exposure | Yes | Dive tourism, Aqaba Marine Reserve |
| M2 transboundary | Yes | Four countries, one 14–26 km basin |

Aqaba is a maximum-score site. **[derived]** That is a genuinely good thing to be able to
say — the pilot was chosen well, and every other site in this scan is measured against it.
