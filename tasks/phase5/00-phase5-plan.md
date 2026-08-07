# Phase 5 — Closing Phase 2, Then Real AI Across Every Layer

**Project:** ReefShield Aqaba
**Written:** 7 August 2026
**Window:** 7 Aug (today) → 12 Aug (freeze) → 13 Aug (present)
**Read this before your own task file.**

---

## Where Phase 2 left us

Every item below was checked against the real filesystem and the running API on
7 Aug — none of this is transcribed from a task description. Full evidence is in each
person's own file (§0 of each). Nothing here is included on the strength of a comment
saying it's done.

| # | Item | Owner | Status |
|---|---|---|---|
| A1.1 | Rainfall re-pulled over corrected `TERRAIN_AOI`; Oct-2016 ordering anomaly resolved in writing | Karam | ✅ Done |
| A1.2 | `event_catchment_features.parquet` complete | Karam | ✅ Done, one undocumented all-null column group |
| A1.3 | Daily IMERG sweep 2000→2026 / `catchment_rainfall_climatology.parquet` | Karam | 🟡 Partial — real, but a 5-row summary, not the daily series |
| A1.4 | Dependency manifest exists | Karam | 🟡 Partial — exists per-service, not at repo root |
| A1.5 | Repo-ownership/continuity conversation happened | Karam | ⬜ Unverifiable from the filesystem |
| A2.1 | `docs/model_card.md` complete, in the RAG corpus | Mahdi | ✅ Done |
| A2.2 | Standalone temporal-holdout metric recorded | Mahdi | ✅ Done |
| A2.3 | `.env` credentials rotated | Mahdi | 🔴 **Not done — real exposure** |
| A2.4 | Culvert cross-check / `position_confidence` / `AQ-O04` caveat live | Mahdi | ✅ Done |
| A2.5 | `docker compose up` genuinely works with wifi off | Mahdi, Ali | 🟡 Test written, execution unconfirmed |
| A3.1 | Real ACA export served by `/api/v1/reef-zones` | Pulga | ✅ Done |
| A3.2 | Dated `docs/data_dictionary.md` amendment for the ACA swap | Pulga | ✅ Done |
| A3.3 | Mooring read-through endpoint | Pulga | ✅ Done |
| A3.4 | `rainfall_multiplier` field + `ScenarioDrawer` repointed | Pulga, Ali | 🟡 Backend real; frontend still bypasses it |
| A4.1 | GEFS exceedance vs. real per-catchment p99 | Nizar | ✅ Done |
| A4.2 | Copernicus Marine vs. HYCOM comparison | Nizar | 🟡 Documented with real numbers; not re-runnable in this container today |
| A4.3 | Frozen "today" offline snapshot seeded | Nizar | ✅ Done |
| A5.1 | `/plume/simulate` wired to the real particle engine | Abd | ✅ Done, running on placeholder zero-current/zero-wind forcing |
| A5.2 | Calibration grid search with a recorded winning trial | Abd | ✅ Done, with a self-flagged tie-break caveat |
| A6.1 | Live vs. stubbed endpoint map | Ali | ✅ Mapped |
| A6.2 | Wifi-off Playwright test executed | Ali | 🟡 Written, execution unconfirmed |
| A6.3 | Validation Panel wired to mooring | Ali | 🟡 Measured side real; modelled side intentionally `null` |

**One real, unresolved risk sits above everything else on this list:** `.env` with
team credentials was committed to git history on 1 Aug (`2f0a6d6`) and later removed
from the tip without a history rewrite. The credentials in that commit are still
retrievable by anyone with clone access, regardless of `.gitignore` being correct
today. This is not a documentation gap — it is a live exposure, and it is Mahdi's
first Phase 5 task, ahead of anything new.

---

## What Phase 5 delivers

Nine new AI features, each specified as one unit across its model/data component, its
backend and storage, and its dashboard sub-features — no feature ships as a model
nobody can see or a UI panel with nothing real behind it.

| # | Feature | One line |
|---|---|---|
| B1 | Automated Plume Segmentation Model | Learns to draw the plume mask itself, with every auto-mask flagged for human review until proven |
| B2 | Learned Transmission-Loss Model | Replaces the borrowed Negev 20–85% range with a per-catchment learned estimate, always labelled which one is in use |
| B3 | Cross-Site Transfer Learning | Fine-tunes Aqaba's validated model onto a new site's thin data, with an honest maturity badge |
| B4 | Automated Site-Scoring Agent | Scores a new candidate coastline against the six-criterion rubric, every score cited to a retrieved fact |
| B5 | Post-Event Forensic Report Generator | Assembles a draft report from real `formula_terms`/RAG citations — retrieves, never computes, never auto-publishes |
| B6 | Live Anomaly Detection on Forecast Streams | Flags an unusual forecast pattern as an early, distinct signal — never conflated with the formal confidence meter |
| B7 | Adaptive Sampling Recommender | Infrastructure for a capability that activates after real deployment history — built now, honestly framed as not demoable yet |
| B8 | Coral Health Vision Model | Classifies diver photos into health states, and is the one path that can turn `sensitivity_weight` from a placeholder into evidence — proposed, never auto-applied |
| B9 | Automated Culvert/Drainage-Conflict Detector | Formalizes the manual OSM-vs-DEM check that already found 27 real culverts into a repeatable detector |

The **Multi-Language Voice Assistant is deliberately out of scope** — it already
exists and needs no Phase 5 work.

---

## Schedule

Five build days, not twelve. Say the constraint out loud rather than discover it at
freeze: **Part B is nine new AI features, several of them real model-training efforts
(a segmentation network, an LLM scoring agent, a CV classifier), landing on top of
Part A cleanup, in five days.** The realistic outcome for most of B1–B9 is real
plumbing plus a first working pass, not a fully validated model — and B6/B7 are
explicitly infrastructure for a capability that activates later, not full demo
features, per their own specs below. That is not a reason to cut anything from this
plan; it is the reason every per-person file's Definition of Done distinguishes
"wired and honestly labelled" from "validated."

| Day | Date | Milestone |
|---|---|---|
| 0 | 7 Aug | This plan lands. Everyone reads §"Where Phase 2 left us" and their own file. Mahdi starts credential rotation immediately — nothing else on this list is more urgent. |
| 1–2 | 8–9 Aug | Part A closure items with real, specific gaps (A1.3/A1.4 Karam, A2.3/A2.5 Mahdi, A3.4/A6.1 Pulga+Ali, A4.2 Nizar). Part B schema/table decisions locked (`candidate_sites`, `calibration_trials` extension, `sampling_feedback`, `forecast_anomalies`) — commit these before writing model code against them. |
| 2–4 | 9–11 Aug | Part B model/backend work in parallel. Dashboard sub-features build against whichever backend contract lands first, same "provisional schema, real code" discipline as Day 1 of the original project. |
| 5 | 11 Aug | Ali repoints `ScenarioDrawer` (A3.4), wires the mooring comparison (A6.3), and builds the B1–B9 dashboard slices against the committed API contracts already in each owner's file. |
| Freeze | 12 Aug | Every ✅-able item is ✅. Every feature that can't be fully validated in time is explicitly labelled "plumbing, first-pass model" — never silently presented as finished. |
| Present | 13 Aug | Demo. |

---

## Ownership

| Priority | Person | Workstream |
|---|---|---|
| **1** | Karam | Close A1 (rainfall/climatology/manifest) |
| **1** | Mahdi | Close A2 (**credential rotation first**); own B1, B2, B3, B9 end to end |
| **1** | Pulga | Close A3; own B4, B5, B7, B8 end to end |
| **2** | Nizar | Close A4; own B6 end to end |
| **2** | Abd | Close A5 |
| **2** | Ali | Close A6; build the dashboard for every B1–B9 feature against each owner's already-committed API contract |

Ali appears against every feature below — not because he's behind, but because every
feature in this phase, same as every phase before it, ends in a screen, and he's the
only frontend. See [`06-ali.md`](06-ali.md).

---

## Rules that carry over

**1–7, unchanged since Phase 1 — these do not lapse:**

1. Missing is never zero, and nothing is interpolated.
2. No fabricated geometry, ever.
3. Provisional data is named `*_PROVISIONAL`, and every swap is a tracked checklist item.
4. Every claim has evidence. No figure, no test → assumed, not verified.
5. Source vs. derived is labelled.
6. Provenance is not bookkeeping — every product, version, date, licence, limitation goes in `docs/data_dictionary.md`.
7. Never claim exactness — probabilistic, stated confidence, said before a judge finds it.

**8–13, new this phase — every Part B feature is built against these from day one:**

8. Every area/distance calculation is in EPSG:32636, never degrees, never EPSG:3857.
9. Caveats travel as data, not documentation — every response carrying a limitation ships it in the payload.
10. Every new AI output needs a `formula_terms`-equivalent audit trail — every input that produced a number, stored, reconstructable six hours later in front of a judge.
11. `docs/ali/*` (the market/research scan) stays out of the RAG corpus and out of the app surface, exactly as in Phase 2.
12. The LLM phrases numbers, it never computes them — applies to the forensic report generator (B5) and the site-scoring agent (B4) by name.
13. No model silently overwrites a labelled placeholder. `sensitivity_weight` and any future placeholder like it can be *proposed* toward, never *auto-replaced*. A human sign-off step is mandatory wherever this applies — B8 by name.

---

## Day-of-freeze gate

```bash
# No provisional data reaching the demo
grep -ri PROVISIONAL -r data/ docs/ | grep -v '_PROVISIONAL\.'

# No new table/ID collides with the existing contract
grep -rn "candidate_sites\|sampling_feedback\|forecast_anomalies\|calibration_trials" tasks/00-contracts.md
# (expect zero matches — these are new, not contract renames)

# Every B-feature has a stated limitation, not a silent one
grep -L "Limitation" tasks/phase5/0[1-6]-*.md   # any file with no hits under a B-section is a gap

# B8 safeguard: sensitivity_weight is proposed, never auto-overwritten
grep -n "propos" tasks/phase5/02-mahdi.md tasks/phase5/04-pulga.md
```

Done for this phase means: every ✅-able Part A row confirmed still true after
everyone's changes land, every 🟡/🔴 row either closed or explicitly deferred with a
reason on record, and every Part B feature either fully wired or honestly labelled as
plumbing-plus-first-pass — never silently presented as more finished than it is.
