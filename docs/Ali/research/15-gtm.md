# 15 · Business — Go-to-market and commercial risk register

**Part C. The sequence of moves, and everything that can kill it.**

> **The short version.** **This does not sell into a market — it inserts into a funded programme
> that already exists.** The go-to-market is not lead generation; it is **getting into one room at
> UNDP Jordan with a working demo and an honest backtest.**
>
> **Five moves:** finish the validation (now) → **ABOFA, 9–13 Sept 2026** → a grant-funded pilot
> (3–12 mo) → a commercial Saudi second site (12–24 mo) → regional via GFCR or PERSGA (24–36 mo).
>
> **ABOFA is a procurement room, not a demo slot.** Success there is **one named follow-up
> meeting**, not a prize.
>
> **Of ten commercial risks, two are real:** no validated backtest, and **the team simply stopping
> on 14 August.** The second is the most probable reason this never becomes a business, and it is
> the only one that costs nothing to fix — one conversation before the hackathon ends.

---

## 1 · The go-to-market thesis in one paragraph

**[judgement]** ReefShield does not sell into a market; it inserts into a **funded programme
that already exists**. The GFCR Gulf of Aqaba and Northern Red Sea Resilient Reefs Programme
targets a **USD 10 million** grant with the **Aqaba Marine Reserve as a priority site**, names
**increased sediment flows from changing rainfall intensity** as a key threat, and funds
**"water quality / land-ocean interface projects"** as an explicit protection outcome
**[sourced, §2.1 of [`14-funding.md`](14-funding.md)]**.
The go-to-market is therefore not lead generation — it is **getting into one room at UNDP
Jordan with a working demo and a validated backtest.**

---

## 2 · The sequence

### Move 1 — Finish the validation (now → 13 August)

**Nothing else matters until there is one honest backtest.** Not a better dashboard, not more
sites. Every buyer in [`12-buyers.md`](12-buyers.md)
§6 has "one validated historical backtest" as a blocking requirement.

> **Update 2026-08-02 — the contingency below has fired.** The imagery audit has run and
> returned **NO-GO**: [`docs/event_audit.md`](../../event_audit.md) §3 shows the October 2016 plume
> dispersed 2.5–3.5 days before any accessible satellite pass, confirmed by Sentinel-2 and
> Landsat 8. **A physical null, not a data-quality problem.**
>
> **So Move 1 is now specific:** validate the transport model against the Kalman et al. **in-situ
> mooring record** — salinity **−1.75 ‰**, turbidity peak **2.18 g/L**, 250 m offshore at 13 m
> depth, onset 09:50 Oct 28, cleared ~17:15 Oct 29. **[judgement]** This is a *quantitative*
> target rather than a visual one, so it is a better backtest than originally planned — but it
> depends on the particle engine, which does not exist yet. That dependency is now the single
> most schedule-critical item in the project.

**[judgement]** The original contingency still reads correctly, and is worth keeping on the
record: if the imagery gate failed, the honest move was to reposition around *forecast capability
and exposure mapping* and say so plainly. **That is survivable, and it is what happened.**
Claiming validation you do not have is not.

### Move 2 — The ABOFA room (9–13 September)

**[sourced]** ABOFA and the Regional Ocean Summit are held in Aqaba, hosted with the Aqaba
Development Corporation. The organisations named in the GFCR document — UNDP Jordan, IUCN
ROWA, ASEZA — are the plausible attendee list.

**Deliverables for that week [judgement]:**

| Artefact | Purpose |
|---|---|
| Working demo, offline-capable | The concept doc §25 already flags "data downloads fail during demo" as a risk. Cache everything. |
| **One-page institutional brief** | Problem, what it does, what it costs, what it needs from ASEZA. Something a director hands to a colleague. Not a pitch deck. |
| Validation report with honest metrics | IoU, centroid error, and the limitations. The limitations are the credibility. |
| A named ask | "A 30-minute meeting to discuss whether this fits Outcome 1 of the GFCR programme." Specific, small, answerable. |

**Success metric for ABOFA is one named follow-up meeting.** Not a prize.

### Move 3 — The pilot (3–12 months)

One deployment, one full flood season, instrumented for the survey-efficiency metric in
[`12-buyers.md`](12-buyers.md) §5.1. Funded by GFCR or
GEF 10905, not sold.

**[judgement]** Design the pilot so the *evaluation* is credible: baseline the current
sampling regime before the system goes live, or there is nothing to compare against. This is
the most commonly skipped step and it is what makes or breaks the case for renewal.

### Move 4 — The commercial second site (12–24 months)

Saudi giga-project. **Saudi Arabia is not a GFCR recipient** **[sourced]**, so this is
straight commercial procurement and it is where actual revenue starts.

### Move 5 — Regional (24–36 months)

GFCR Growth phase, PERSGA, or the **Gulf of Aqaba Coordination Mechanism among Jordan, Egypt
and Saudi Arabia** named in the GFCR document **[sourced]**.

---

## 3 · Partnership strategy

**[judgement]** Three categories, in descending order of importance:

**Channel partners — how you reach buyers.** UNDP Jordan (convening agent, both instruments),
IUCN ROWA (co-implementer and GEF 10905 implementing agency), PERSGA (regional monitoring
coordination). None of these buy; all of them decide who gets in the room.

**Scientific credibility partners.** The **Marine Science Station in Aqaba** and the
**InterUniversity Institute in Eilat** already run joint surveys **[sourced]**; **CORDAP**
is a named GFCR co-implementer. An endorsement from a marine scientist is what converts
`sensitivity_weight = 1.0` from a placeholder into a defensible parameter — the exact gap
[`docs/pitch_limitations.md`](../../pitch_limitations.md) §5 flags.

**Delivery partners.** For sites outside Jordan, a local geospatial or environmental
consultancy does the site onboarding. This is how a small team serves twelve coastlines
without twelve offices.

---

## 4 · Commercial risk register

Scored **[judgement]**. Probability × impact, highest first.

| # | Risk | P | I | Mitigation |
|---|---|---|---|---|
| 1 | **No validated backtest** — ⬛ **the imagery half of this has already happened.** The audit ran and found no detectable plume in any accessible scene | **Certain** (imagery) → **Med** (overall) | **Critical** | **Route changed, not lost.** Validate against the in-situ mooring record instead — see Move 1. Residual risk is now *"the transport engine isn't built in time to test against it"*, which is an engineering-schedule risk rather than a data-availability one. |
| 2 | **The GFCR programme is dormant or already allocated** | Med | High | Concept note signed late 2022 with a Jun 2023 proposal target — **status unverified**. Check first; GEF 10905 is the fallback channel, and it is confirmed in implementation. |
| 3 | **Procurement timelines** — 12–24 months from interest to contract | **High** | High | Lead with grant-funded deployment and event-response work, which bypass tender. Do not model revenue on a normal sales cycle. |
| 4 | **Team dissolves after the hackathon** | **High** | High | The most likely failure mode for any student project, and it is rarely written down. Decide before 13 August who owns the repo, the relationships and the follow-up. |
| 5 | **Key-person dependency** | High | Med | Five workstreams, one owner each. The repo's contract-first design already mitigates this better than most — keep it. |
| 6 | **Customer concentration** — one Saudi contract dominates revenue | Med | Med | Accept early; diversify by year 3 |
| 7 | **A free alternative appears** — NOAA or a national agency generalises | Low–Med | High | Genuinely possible. Defence is institutional embedding and the local validation record, not technology. |
| 8 | **Validation labour never falls with scale** | Med | Med | Build the labelled plume-mask library from day one so segmentation can be automated later |
| 9 | **Placeholder data reaches a real customer** | Low | **Critical** | The `_PROVISIONAL` naming convention and the day-12 grep gate in [`tasks/00-contracts.md`](../../../tasks/00-contracts.md) §5 already handle this. **Keep that discipline after the hackathon** — it becomes more important with a paying customer, not less. |
| 10 | **Over-claiming in the pitch** | Med | High | The `[sourced]/[derived]/[judgement]` discipline across this doc set exists for this. One inflated number discredits the honest ones. |

**[judgement]** Risks 1 and 4 are the real ones. Everything else is manageable. Risk 4 — the
team simply stopping on 14 August — is the single most probable reason this never becomes a
business, and it is the only one that costs nothing to mitigate: one conversation before the
hackathon ends.

---

## 5 · What "success" should mean at each horizon

**[judgement]** Defined so nobody moves the goalposts later.

| Horizon | Success is | Success is *not* |
|---|---|---|
| **13 Aug 2026** | One validated backtest with honest metrics; a demo that runs offline | Five map layers and no validation |
| **13 Sep 2026** | One named follow-up meeting from ABOFA | Winning a prize |
| **12 months** | One live deployment through a full flood season, with a before/after sampling-efficiency measurement | A signed MoU with no deployment |
| **24 months** | First commercial contract; second site live | More pilots |
| **36 months** | 6+ sites; the team is self-sustaining on contracts | A large grant with no customers |

---

## 6 · The three sentences of business case for the pitch

**[judgement]** The concept doc §27.5 instructs: lead with environmental and national value,
not an aggressive commercial model. Keep it to this:

> There is already a ten-million-dollar UNDP programme for Gulf of Aqaba reefs whose priority
> site is the Aqaba Marine Reserve, and it names increased sediment flows from changing
> rainfall as a key threat and land-ocean interface projects as a funded outcome. We built the
> tool for that outcome. It runs on free open data, so operating it for a coastline costs a
> few thousand dollars a year against a reef worth low single-digit millions annually — and
> the same platform serves eleven other coastlines from Sinai to Oman without changing the
> science.
