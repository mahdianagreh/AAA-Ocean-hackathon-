
# 12 · Business — Buyers, value and willingness to pay

**Part C. Who signs the cheque, what they are actually buying, and what it is worth to them.**

---

## 0 · The central commercial question

The concept doc lists users (§6) and journeys (§7). Those are **users**, not **buyers**. A
dive centre is a user; it will not fund a geospatial platform. This document separates the
two, because conflating them is the most common way a good technical pitch fails the
business question.

**[judgement]** There are exactly **four** buyer archetypes for this product, and only two
of them can fund development.

---

## 1 · Buyer A — The coastal zone authority *(the anchor customer)*

### Who, concretely

**ASEZA** — the Aqaba Special Economic Zone Authority. It is the **autonomous manager,
regulator and developer** of the Aqaba Special Economic Zone, and it established the Aqaba
Marine Park in 1997, which became the national **Aqaba Marine Reserve** by royal directive
in **June 2020**. It manages the reserve through its **Environment Commission**, including a
Beaches Administration Directorate, under Marine Park Bylaw No. 22 (2001)
([UNDP/ASEZA](https://www.undp.org/jordan/press-releases/aseza-and-undp-sign-agreement-support-aqaba-marine-reserve-management-and-science-park))
**[sourced]**.

Regional equivalents: Egypt's EEAA and the Red Sea Governorate, Saudi Arabia's National
Center for Wildlife and the NEOM/Red Sea Global environment teams, Oman's Environment
Authority, Bonaire's STINAPA.

### What they are actually buying

Not "a plume model." **[judgement]** They are buying three things, in this order:

1. **Defensible allocation of a scarce survey team.** They have a handful of staff and 27 km
   of coast. Being told *which* reef zone to sample tomorrow morning, with a stated
   confidence, is the concrete product.
2. **An evidentiary record.** A timestamped, reproducible archive of every event, what was
   predicted, and what was observed — for reporting to government, UNESCO, and donors.
3. **Political cover.** When a plume damages a reef, "we had no way of knowing" is a weak
   position. "Our system flagged it, we sampled within 12 hours, here is the data" is a
   strong one.

### Willingness to pay

**[sourced]** ASEZA's stated funding strategy for the reserve is a **diverse portfolio:
direct government subvention, entrance fees, and grants from national and international
sources**. That is the shape of the deal: **the first contract is almost certainly
grant-funded, not budget-funded.**

**[assumption]** $40k–120k/yr once operational. But **year one should be priced at zero** and
funded by a donor programme, with ASEZA contributing staff time and data access rather than
cash — see [`14-business-funding-and-policy.md`](14-business-funding-and-policy.md).

### The buying trigger

**[judgement]** Institutions like this buy after an incident, not before one. The commercial
strategy should assume the next significant flood event is the sales event — which means the
system must be *already running and already right* when it happens. That is an argument for
getting a live deployment up cheaply and early, not for a polished sales process.

---

## 2 · Buyer B — The mega-development environment team *(the money)*

### Who, concretely

**NEOM**, **Red Sea Global**, and **Jeddah Central** — three giga-projects inside a **$1.3
trillion** Saudi economic expansion programme **[sourced]**. NEOM sits **directly on the Gulf
of Aqaba**, roughly 100 km from Aqaba.

### Why they are a fundamentally different buyer

**[judgement]**

- They have **environmental compliance obligations with real budget attached**, not a
  conservation aspiration with a small grant.
- They are **building now**, which means construction runoff is an active, attributable risk
  they are already being asked about publicly. Researchers explicitly note that
  *understanding reef health status is paramount to developing baselines and management
  strategies to minimise human impact* given this development **[sourced]**.
- **Attribution is their core need.** When a plume appears near a Red Sea Global reef, the
  question "was that us, or was that a wadi?" is worth a great deal of money. ReefShield
  answers it, because it models the natural baseline pathway.

> **This is the single strongest commercial insight in the scan [judgement]:** ReefShield's
> catchment attribution is not just an environmental tool, it is a **liability-defence
> tool**. A developer that can show a sediment event came from a 4,000 km² natural
> catchment during a 1-in-10-year storm — rather than from its own earthworks — has bought
> something valuable. That framing should be tested with a Saudi contact before the pitch,
> and it should **not** be led with in an environmental-track hackathon, where it will read
> as cynical. Keep it for the business Q&A.

### Willingness to pay

**[assumption]** $150k–400k/yr. Comfortably a rounding error against a multi-billion
programme, and consistent with environmental monitoring line items on large coastal
infrastructure.

---

## 3 · Buyer C — Donor and multilateral programmes *(the year-one funder)*

Not a customer in the commercial sense — the entity that **pays for the first deployments**
so buyers A and B can see it working. Full detail in
[`14-business-funding-and-policy.md`](14-business-funding-and-policy.md).

### The named channel — this is not a cold introduction **[sourced]**

| Entity | Role | Named contact in the public document |
|---|---|---|
| **UNDP Jordan** | Convening agent, GFCR Gulf of Aqaba programme (**USD 10 M** target) | **Randa Aboul-Hosn**, Resident Representative |
| **UNDP** (HQ) | Nature, Climate & Energy | Pradeep Kurukulasuriya, Director |
| **IUCN Regional Office for West Asia** | Co-implementer; implementing agency for GEF 10905 | **Hany El Shaer**, Regional Director |
| **CORDAP** | Co-implementer, coral R&D accelerator | Carlos M. Duarte, Executive Director |
| **UNDP Jordan** | Executing agency, **GEF project 10905** at the AMR (USD 663k grant + USD 5.5 M co-financing) | — |

**[judgement]** Every organisation above is already working on the Aqaba Marine Reserve,
under **two separate funded instruments** — the GFCR Gulf of Aqaba programme and GEF 10905 —
with **UNDP Jordan in both**. And the GFCR programme document names *"water quality /
land-ocean interface projects"* as a funded outcome and increased sediment flows as a key
threat.

A student team in Jordan requesting a meeting with UNDP Jordan about a tool that serves a
funded outcome of their own programme is a realistic ask, not a cold pitch. **This is the
single most actionable item in the entire research set.**

---

## 4 · Buyer D — Tourism operators *(users, not buyers — mostly)*

Aqaba has **20–30+ named dive sites** along **>25 km of fringing reef** **[sourced]**.
Individual dive centres are small businesses; none will fund a platform.

**[judgement]** Two viable routes, both secondary:

- **Association or chamber licensing** — one aggregate contract covering all operators.
  **[assumption]** $10k–30k/yr.
- **Free tier as a distribution and political asset.** Give operators the alert feed at no
  cost. When ASEZA is deciding whether to renew, thirty dive operators who depend on the
  daily alert are the strongest possible argument. **This is worth more than the licence
  revenue.**

---

## 5 · Value quantification — the four arguments, ranked by strength

**[judgement]** In the order they should be deployed:

### 5.1 Survey efficiency — the strongest, because it is measurable

A monitoring team covering 27 km of coast without prediction samples on a schedule or after
visible damage. With a 12-hour-ahead exposure map, the same team samples the right zone at
the right time.

**The claim:** the same budget produces more decision-relevant observations. This is
**measurable inside the pilot** — count useful samples per staff-day before and after. It is
the metric to instrument from day one.

### 5.2 Avoided asset loss

From [`11-business-market-sizing.md`](11-business-market-sizing.md) §5, Aqaba's reef is worth
roughly **$0.6–3.8 million/yr** in direct-use terms **[derived from sourced ranges]**. A
system in the tens of thousands protects an asset in the low millions — a ratio that holds up
without inflating anything.

### 5.3 Attribution and liability defence

See §2. Highest willingness to pay, lowest suitability for an environmental pitch.

### 5.4 Compliance and reporting

The Aqaba Marine Reserve has a **management plan for 2022–2026** and is on Jordan's **UNESCO
tentative list** **[sourced]**. Both generate reporting obligations that an automatic event
record satisfies cheaply.

---

## 6 · What each buyer needs before they can say yes

**[judgement]** This is effectively the product roadmap, expressed commercially.

| Buyer | Blocking requirement | Currently exists? |
|---|---|---|
| Coastal authority | One validated historical backtest with honest metrics | ❌ blocked on Abd's imagery gate |
| Coastal authority | Reef zones matching *their* official zonation, not ours | ⚠️ provisional zones exist; ACA export pending |
| Mega-development | Catchment attribution — natural vs construction source | ⚠️ catchments exist on branch `mahdi`, unmerged |
| Mega-development | Audit trail: every run stores parameters and inputs | ✅ manifest/summary JSON already written per run |
| Donor programme | A named institutional partner and a work plan | ✅ ASEZA–UNDP relationship already exists |
| Dive operators | A phone-readable alert, not a GIS dashboard | ❌ no frontend exists at all |

**The pattern [judgement]:** three of the six blockers are the same three gaps identified in
[`16-technical-build-state.md`](16-technical-build-state.md) — the imagery gate, the unmerged
catchments, and the absent frontend. The commercial and technical critical paths are the same
path.
