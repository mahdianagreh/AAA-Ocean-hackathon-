# Pulga — Backend, Exposure Engine, RAG, and Four New AI Features

**Phase 5 · Workstream 4**
Read [`00-phase5-plan.md`](00-phase5-plan.md) first.

---

## Why this phase matters

Three of my four Part A items are already closed with live evidence — the mooring
endpoint, the real ACA export, the dated data-dictionary amendment all shipped this
project session and are confirmed live against the running container. The one real
gap left is that the backend half of the what-if scenario engine is real, but the
frontend still bypasses it — flagged below as a known, named gap. My Part B load is
four owned features, one of which (B8) carries this phase's single most important
safety rule.

---

## 0 · Close your Phase 2 items — Day 0/1

- [x] **A3.1 — real ACA export served by `/api/v1/reef-zones`.** Confirmed live: 8
      real zones, heterogeneous area/depth/habitat values, a version marker
      distinguishing real vs. provisional. No action needed.
- [x] **A3.2 — dated `docs/data_dictionary.md` amendment for the ACA swap.**
      Confirmed: §4, "swap-in #3 CLOSED 2026-08-03," with a before/after table. No
      action needed.
- [x] **A3.3 — mooring read-through endpoint.** Confirmed live:
      `GET /api/v1/events/AQ-2016-10-28/mooring` returns the full real payload
      (citation, DOI, position, markers, magnitude fields). No action needed.
- [ ] **A3.4 — `rainfall_multiplier` field + `ScenarioDrawer` repointed.** The
      backend half is real: `RunoffRequest`/`ExposureRequest` both carry
      `rainfall_multiplier`, wired into `predict_one()` against the real feature row.
      **The frontend half is not done, and it's not a backend gap** —
      `frontend/src/api/risk.ts::riskFromSeries()` computes a separate, explicitly
      commented "deliberately does NOT alter [real model] numbers" local index, and
      `ScenarioDrawer.tsx` never calls the real endpoint at all. Document the backend
      contract clearly (field names, bounds, what gets echoed back) so wiring the
      drawer to it is a small, well-specified frontend change whenever it's picked up.

---

## 1 · B4 — Automated Site-Scoring Agent

**Model & data**

- [ ] LLM-driven agent ingesting satellite/climate/OSM data for a candidate
      coastline, scoring it against the existing six-criterion rubric
      (`docs/Ali/research/01-signature.md` C1–C6).
- [ ] Every score grounded in a specific retrieved fact, cited — the LLM never
      assigns a number without evidence behind it. Same rule as the existing
      `/explain` endpoint (Component E): **the LLM phrases numbers, it never
      computes them** (Standing Law rule 12). Concretely: the agent retrieves a
      real rainfall percentile, a real OSM building-density figure, a real reef-cover
      estimate for the candidate box, and writes prose around those retrieved
      numbers — it does not run its own hidden calculation and present that instead.
- [ ] Source the rainfall/climate criteria directly from the already-published
      `catchment_rainfall_climatology.parquet` and `docs/data_dictionary.md` — no new
      ingestion pipeline needed, this data already exists and is documented.

**Backend & storage**

- [ ] `POST /api/v1/sites/score` — takes a bounding box, returns a structured score
      with per-criterion evidence citations.
      ```python
      class SiteScoreRequest(BaseModel):
          bbox: tuple[float, float, float, float]  # W, S, E, N — EPSG:4326, same
                                                     # convention as TERRAIN_AOI/MARINE_AOI
          site_name: str | None = None

      class CriterionScore(BaseModel):
          criterion: Literal["C1", "C2", "C3", "C4", "C5", "C6"]
          score: float
          evidence: list[Citation]  # reuses the existing /ask citation shape —
                                     # do not invent a second citation format
      ```
- [ ] New `candidate_sites` table — every auto-scored site stored and browsable.
      **New artifact, confirmed clear of `tasks/00-contracts.md`'s frozen ID schemes**
      (`AQ-C`/`AQ-O`/`R-`/`AQ-YYYY-MM-DD`/`sim_{ULID}` are all Aqaba-specific; a
      candidate site is a different site entirely and gets its own identifier space,
      not a squatted `AQ-*` ID).
- [ ] All area/distance work inside the scoring criteria (e.g. reef proximity,
      catchment area estimates for the candidate box) is EPSG:32636, never degrees
      (Standing Law rule 8) — this rubric will be run on boxes far from UTM 36N's
      home zone eventually; get the reprojection right from the first call, not after
      someone quotes a wrong area.

**Dashboard sub-features (for Ali to build)**

- A "Score a new coastline" input box: paste coordinates, get back a
  live-generated six-criterion score rendered exactly like the existing scorecard
  table.
- A map layer showing auto-scored candidates color-coded by tier, letting you
  visually scan for new Tier-1 sites instead of researching one region at a time.
- Auto-populates a new row in the research-scan scorecard visualization.

**Limitation to state on the same screen this ships on:** this rubric was built and
tuned against exactly one site — Aqaba. A score for anywhere else is the rubric's
first real test, not a validated instrument. Say this next to the score, not just in
this file.

---

## 2 · B5 — Post-Event Forensic Report Generator

**Model & data**

- [ ] Reuses the existing `/explain` and `/ask` infrastructure — assembles a report
      by retrieving real `formula_terms`, real model outputs, real RAG-corpus
      citations.
- [ ] **Never computes a new number itself** — every figure in the report is
      retrieved, not generated (Standing Law rule 12, same as B4).

**Backend & storage**

- [ ] `POST /api/v1/reports/generate` — takes an `event_id`, returns a draft report
      with every claim traceable to a source.
- [ ] Every generated report stored with `status: "ai_drafted" | "human_reviewed"` —
      **never auto-published without this flag being flipped by a person.** This is
      the same shape of safeguard as B8's `sensitivity_weight` rule below — a
      generated artifact that looks finished must carry a visible flag saying it
      isn't reviewed yet, not silently read as authoritative.

**Dashboard sub-features (for Ali to build)**

- "Generate Report" button on any completed event.
- A visible, un-hideable draft-status badge on every AI-generated report.
- Direct integration with the Bilingual Assistant — same citation engine powering
  `/ask` now also sources the report's claims.

**Limitation to state:** the report is only as complete as the event's own data —
for any event other than the anchor storm (`AQ-2016-10-28`), most `formula_terms`
inputs are thinner or absent, and the report must say so per section, not present a
uniformly confident narrative regardless of which event it's about.

---

## 3 · B7 — Adaptive Sampling Recommender

**Model & data**

- [ ] Starts as a simple heuristic/bandit approach, not deep RL.
- [ ] Logs whether a recommended zone was actually sampled and whether the outcome
      matched the prediction.

**Backend & storage**

- [ ] New `sampling_feedback` table.
- [ ] The exposure engine's zone-priority ranking incorporates this history alongside
      the existing formula once enough feedback exists — **"once enough feedback
      exists" is a real gate, not a formality**: with zero real sampling history,
      the ranking must fall back to the existing formula unchanged, never blend in
      a feedback signal computed from nothing.

**Dashboard sub-features (for Ali to build)**

- Upgrades the existing Named Reef Zone Priority List with "last sampled" and
  "prediction vs. outcome" history.
- An accuracy-over-time trend chart, showing the recommender's own track record
  improving.

**Honesty note — keep this in the actual UI copy, not just internal docs, exactly as
the user's own spec for this feature demands:** this feature cannot be meaningfully
demoed with zero deployment history. Build the plumbing now; frame it in the pitch as
infrastructure for a capability that activates after real-world use, not a working
feature today. If the UI copy says anything stronger than that before real sampling
history exists, it's overclaiming.

---

## 4 · B8 — Coral Health Vision Model

**Model & data**

- [ ] CNN classifying diver-uploaded reef photos into health states
      (healthy/stressed/bleached), tied to a specific named reef zone. Start from a
      small, pretrained image classifier fine-tuned on whatever real reef photos are
      available — a first-pass model built once, not a dependency on a separate
      person's ML pipeline.

**Backend & storage**

- [ ] `POST /api/v1/reef-zones/{id}/photos` — accepts an image, returns a
      classification with confidence.
- [ ] Every classified photo stored with its result, building a per-zone health
      trend.

**The one non-negotiable design requirement in this entire phase, stated here in
writing:** this is the only Phase 5 feature that can turn
`sensitivity_weight = 1.0` / `PLACEHOLDER_PENDING_MARINE_SCIENTIST`
(`tasks/00-contracts.md` §5, swap-in #5, still open) into real, evidence-grounded
data. Accumulated photo classifications per zone should **propose** a
`sensitivity_weight` update — flagged explicitly for marine-scientist review — and
must **never silently overwrite the placeholder**. Automating the evidence-gathering
is good; automating the final judgement call is exactly the failure mode Standing Law
rule 13 exists to prevent. Concretely: a `proposed_sensitivity_weight` field, computed
from photo evidence, lives *next to* the live `sensitivity_weight` field the exposure
engine actually reads — the engine never reads the proposed field, only a human
sign-off action copies a proposed value into the live one, and that action is logged.

**Dashboard sub-features (for Ali to build)**

- Photo upload widget per named reef zone.
- Immediate classification result shown on upload, feeding a per-zone health trend
  line.
- A "photos contributed" counter — cheap engagement mechanic that also grows the
  training set.
- A clearly separate, clearly labelled "proposed sensitivity weight update — pending
  scientist review" panel, distinct from the live, in-use placeholder value.

**Limitation to state:** a CNN trained on however many diver photos accumulate in
five days is not a validated coral-health instrument — its proposals are exactly
that, proposals, and the review step exists because the model's own confidence is not
sufficient grounds to change a number the whole exposure engine multiplies through.

---

## Definition of done

1. A3.4 — the backend contract (`rainfall_multiplier`, `transmission_loss_override`)
   is fully documented (field names, bounds, echoed-back values).
2. B4 — `POST /api/v1/sites/score` live, every criterion citing real retrieved
   evidence, `candidate_sites` table populated by at least one real scored box.
3. B5 — `POST /api/v1/reports/generate` live, every generated report carries
   `status: "ai_drafted"` until a human flips it, no fabricated figures.
4. B7 — `sampling_feedback` table exists; ranking formula falls back cleanly with
   zero history; UI copy matches the honesty note above exactly.
5. B8 — photo endpoint live; `proposed_sensitivity_weight` is a separate field from
   the live `sensitivity_weight`; no code path writes the live field automatically.
