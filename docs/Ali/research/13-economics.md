# 13 · Business — Model, pricing and unit economics

**Part C. How the thing makes money, what it costs to run, and what a deployment actually
takes.**

> **The short version.** **All the input data is free.** That single fact shapes everything: no
> cost of goods, structurally high margin — **but no data moat either.** The moat is the
> integration, the validation record, and institutional embedding.
>
> **The numbers:** ≈**+$45k** contribution in year one per site, ≈**+$73k/site/yr** at steady
> state. **Six sites ≈ $440k/yr** — sustains a team of 3–4. Infrastructure is **~2–7%** of a
> mid-range licence, so **cost is not the constraint.**
>
> **The constraint is expert labour.** Manual plume QC is *the method, not a shortcut*, so
> validation cost does **not** fall with scale. **Treat every QC'd mask as a capital asset** — at
> ~50–100 labelled masks, segmentation becomes trainable and the economics change.
>
> **One legal decision:** Allen Coral Atlas is **CC BY 4.0** (fine), but **OpenStreetMap is
> share-alike (ODbL)**. Recommended: publish the OSM-derived tables under ODbL and record it.
> A formal licence review is needed before the first paid contract.

---

## 1 · The structural fact that determines everything

**The platform's input data is free.** IMERG, ERA5-Land, GFS, GEFS, ECMWF open data,
Sentinel-2, HLS, Copernicus DEM, SRTM, WorldCover, SoilGrids, OSM, GEBCO/GMRT, Allen Coral
Atlas and Copernicus Marine are all open or free-on-registration
([concept doc §11](../../../aqaba_aqua_ai_concept.md)) **[sourced]**.

**[judgement]** Three consequences that shape the whole business:

1. **No cost of goods scaling with customers.** Marginal cost of an additional user of an
   existing deployment is ≈ compute only. Gross margin is structurally very high.
2. **No data moat.** Anyone can get the same inputs. The moat is the *integration, the
   validation record, and the institutional embedding* — not the data.
3. **The scarce input is human, not computational.** Every new site needs a documented event
   and a validated backtest, which is expert labour. **The business scales like a
   consultancy with a software core, not like SaaS.** Model it that way or the numbers will
   be wrong.

---

## 2 · Revenue model — four streams, ranked

### 2.1 Deployment + annual licence *(primary)*

The core commercial motion.

| Component | Price **[assumption]** | Notes |
|---|---|---|
| One-off deployment / site onboarding | **$25k – 80k** | AOI, catchment delineation, habitat zones, one validated backtest. This is where the real labour sits. |
| Annual platform licence | **$40k – 120k** (authority) · **$150k – 400k** (mega-development) | Hosting, data refresh, model updates, support |
| Additional catchment/reef zone | **$3k – 8k** each | Expansion within an existing site |

**Why a deployment fee matters [judgement]:** the honest finding from
[`09-scorecard.md`](09-scorecard.md) is that geography is cheap to change
but **validation is not**. Pricing onboarding separately makes that visible rather than
burying expert labour inside a subscription and eroding margin.

### 2.2 Event-response and forensic analysis *(highest margin)*

After a significant event: reconstruction, attribution, and a defensible report.

**[assumption]** $8k–25k per event. **[judgement]** This is the stream most likely to
generate the first real revenue, because it is *reactive* — it sells after an incident, when
budget appears, and it does not require the customer to believe in forecasting first.

### 2.3 Data and API access *(later)*

Programmatic access for research institutions and, eventually, insurance or port operators.
**[assumption]** $5k–20k/yr. Low priority until the validation record is credible.

### 2.4 Grant-funded deployments *(the actual year-one revenue)*

See [`14-funding.md`](14-funding.md). For sites like
Toliara this is the *only* viable model, and for Aqaba it is the likely first-year one.

---

## 3 · Cost structure

### 3.1 Infrastructure — genuinely small

**[assumption, derived from the repo's measured data volumes]** Real figures from the
project: committed processed data is **17 MB** (was 7.6 MB before two 4 MB plume rasters landed
on 2 Aug); the 156-granule October 2016 IMERG event occupies a few hundred MB raw and produces a
**126 KB** processed NetCDF; an ERA5-Land event file is **166 KB**; the antecedent feature
Parquet is **21.6 KB** ([`docs/MASTER_TASK_SUMMARY.md`](../../MASTER_TASK_SUMMARY.md) §12)
**[sourced]**. Full current breakdown in
[`17-scaling.md`](17-scaling.md) §1.

| Item | Monthly **[assumption]** |
|---|---|
| Compute (scheduled ingestion + on-demand simulation) | $80 – 300 |
| Storage (raw archive + processed outputs, per site) | $20 – 60 |
| Database (PostGIS) | $30 – 100 |
| Frontend hosting / CDN | $10 – 40 |
| **Per-site infrastructure total** | **~$140 – 500/month** = **$1.7k – 6k/yr** |

**[derived]** Against the **mid-range $80k** authority licence, **infrastructure is roughly
2–7% of revenue** — the figure to quote, with the basis stated. Across the full $40k–120k
licence range it spans **~1.4% to 15%**, the 15% being the worst case of high infrastructure
against the lowest licence. Either way the cost base is not the constraint. Sensitivity table in
[`17-scaling.md`](17-scaling.md) §3.

The particle simulation is the only compute-intensive component, and it is bounded: the
concept doc's own API example specifies **5,000 particles over 24 hours at 30-minute steps**
(§17.2) **[sourced]** — a trivially small numerical problem by modern standards.

### 3.2 People — the actual cost

**[judgement]** This is where the money goes.

| Role | Why needed |
|---|---|
| Geospatial/hydrology engineer | New site delineation, DEM chain, validation |
| Remote sensing analyst | The plume mask. **Manual QC is the method, not a shortcut** (concept doc §10.5) — this is irreducible expert labour |
| Backend engineer | API, scheduling, deployment |
| Frontend engineer | Dashboard; currently 0% built |
| Domain/partnership lead | Institutional relationships, grant applications |

**The remote-sensing role is the structural cost problem [judgement].** The concept doc is
explicit that the observed plume mask requires manual review. That means **every validation
event carries human cost that does not fall with scale**. Automating plume QC — carefully,
after enough labelled masks exist — is the single highest-leverage margin improvement
available, and it is exactly what §10.5 defers to Phase 2.

---

## 4 · Unit economics of one deployment

**[assumption]** Illustrative, mid-range, one authority-class site.

**Year 1**

| Line | Amount |
|---|---:|
| Deployment fee | +$50,000 |
| Annual licence (part year) | +$30,000 |
| **Revenue** | **+$80,000** |
| Onboarding labour (~25 person-days incl. validation) | −$25,000 |
| Infrastructure | −$4,000 |
| Support / account management | −$6,000 |
| **Year 1 contribution** | **≈ +$45,000** |

**Year 2 onward**

| Line | Amount |
|---|---:|
| Annual licence | +$80,000 |
| Occasional event analysis | +$12,000 |
| Infrastructure | −$4,000 |
| Support + model maintenance | −$15,000 |
| **Steady-state contribution** | **≈ +$73,000/site/yr** |

**[derived]** With **6 sites live**, steady-state contribution is roughly **$440k/yr** —
enough to sustain a team of 3–4 plus infrastructure, not enough to be venture-backable.
**That is the correct read of this business.** Presenting it as anything else invites a
finance judge to take it apart.

---

## 5 · What breaks these economics

**[judgement]** Ranked by likelihood:

| Risk | Effect | Mitigation |
|---|---|---|
| **Validation labour doesn't fall with scale** | Onboarding cost stays at 25 days/site forever; margin never improves | Build the labelled plume-mask library from day one so segmentation can be automated later. Every manually QC'd mask is an asset, not just a deliverable. |
| **Public procurement cycles** | 12–24 months from interest to contract; cash-flow death | Lead with grant-funded deployments and event-response work, which bypass procurement |
| **Customer concentration** | One Saudi contract could be >60% of revenue | Accept it early; diversify by Year 3 |
| **Free alternative appears** | A national agency or NOAA generalises its product | Genuinely possible. Defence is institutional embedding and the local validation record, not technology |
| **No validated backtest** | There is no product to sell at all | This is the *actual* top risk, and it is Abd's imagery gate — see [`18-risks.md`](18-risks.md) |

---

## 6 · Data licensing — can this legally be sold?

**[judgement]** Mostly yes, with **one dataset that needs a decision**. This section is
general information, not legal advice; **a formal licence review is required before the
first paid contract.**

| Dataset | Licence | Commercial use |
|---|---|---|
| **Allen Coral Atlas** | **CC BY 4.0** **[sourced]** — maps, bathymetry and map statistics © 2018–2023 Allen Coral Atlas Partnership and Arizona State University | ✅ **Permitted with attribution.** Good news: the reef habitat layer is the most product-critical third-party dataset and it is cleanly licensed. |
| NASA (IMERG, HLS, SRTM) | NASA Earth science data policy — full and open | ✅ Attribution expected |
| Copernicus (ERA5-Land, Sentinel-2, Marine, DEM) | Copernicus free, full and open | ✅ Attribution required |
| ESA WorldCover | CC BY 4.0 | ✅ |
| ISRIC SoilGrids | CC BY 4.0 | ✅ |
| NOAA (GFS, GEFS) | US Government public domain | ✅ |
| GEBCO / GMRT | Open, attribution | ✅ |
| **OpenStreetMap** | **ODbL — share-alike** | ⚠️ **The one to think about** |

### The OSM problem

**[judgement]** The Open Database Licence is **share-alike**: a "derived database" built from
OSM must itself be offered under ODbL. Pulga's chain uses OSM for road density, built-up
fraction, and — most valuably — the **27 mapped culverts that correct outlet positions**
([`docs/osm_dem_conflicts.md`](../../osm_dem_conflicts.md)) **[sourced]**.

If catchment feature tables containing OSM-derived columns are delivered to a paying
customer, the share-alike obligation plausibly attaches to that table. Three options:

1. **Accept it.** Publish the derived feature tables under ODbL. Costs little — the
   commercial value is in the forecasting service and the validated model, not in a table of
   road densities. **Probably the right answer [judgement]**.
2. **Segregate.** Keep OSM-derived columns in a separate, openly-licensed table so the core
   product is unencumbered. More engineering, cleaner position.
3. **Replace.** Use a differently-licensed roads/impervious source. Loses the culvert data,
   which is the single most useful thing OSM contributes.

**Recommendation:** option 1, decided explicitly and recorded in the data dictionary —
which already tracks licence per source ([`docs/data_dictionary.md`](../../data_dictionary.md))
**[sourced]**. That ledger is the right place for this decision, and it is already built.

### Attribution as a product feature

**[judgement]** Every one of these licences requires attribution. A visible "data sources"
panel in the dashboard discharges the obligation *and* doubles as a credibility asset —
showing a judge or a customer that every layer is traceable to a named, licensed source is
exactly the scientific-integrity claim in concept doc §22.4.

---

## 7 · What to say about business model in the pitch

**[judgement]** The hackathon is an environmental track. The concept doc §27.5 already gives
the right instruction: *lead with environmental and national value, not an aggressive
commercial model.* Two or three sentences, no more:

> The platform runs entirely on free open data, so the cost of operating it for a coastline
> is a few thousand dollars a year against a reef worth low single-digit millions annually.
> The realistic first customers are coastal zone authorities and the environment teams of
> Red Sea mega-developments, and the realistic first funding is a donor programme — ASEZA
> already partners with UNDP on exactly this reserve. We are not claiming a billion-dollar
> market; we are claiming a dozen serviceable coastlines and a very low cost to serve them.

**[judgement]** That last sentence is the one that will earn credibility. Deliberately
undersizing a market in front of judges who have heard ten inflated TAMs is a
differentiator.
