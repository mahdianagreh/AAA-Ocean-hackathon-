# Phase 7 — Feature → Surface Matrix

All 44 features this repo tracks, the page each one must live on, who owns that
screen, and what is **actually true today** — 8 Aug 2026, after the rebrand landed.

Feature IDs match [`../phase6/00-master-test-matrix.md`](../phase6/00-master-test-matrix.md)
exactly. Do not renumber them; Phase 6 evidence is filed under these IDs.

## State vocabulary

| State | Means |
|---|---|
| **Done** | All six gates in [`00-phase7-plan.md`](00-phase7-plan.md#the-definition-of-done-per-feature) met, screenshot filed |
| **Shell** | A page exists and renders, but the feature is thin, partly wired, or unstyled |
| **Backend-only** | API verified in Phase 6; nothing renders it yet |
| **Not started** | No surface |
| **Absent** | No backend exists — must be named on `/limitations`, not mocked |

Nothing here says "in progress". A row is one of the five, and the owner changes it
only after checking the running app.

---

## Core (5)

| ID | Feature | Route(s) | Owner | State today | The one thing that makes it Done |
|---|---|---|---|---|---|
| core-A | Runoff classifier | `/dashboard` risk cards | Mahdi | **Shell** | Cards read live `/runoff/predict`, showing `is_stub`, `model_version` and real drivers — not the fixture |
| core-B | Sediment proxy (anchor) | `/reef-zones/:id`, `/dashboard` | Mahdi | **Backend-only** | `relative_sediment_intensity` and its `_source` visible in the formula inspector, anchored to 24,400 t |
| core-C | Plume / particle engine | `/dashboard` plume layer, `/dashboard/replay` | Abd | **Shell** | Probability field rendered (never a trajectory line), `plume_source` shown verbatim, zero-current caveat on screen |
| core-D | Exposure engine | `/reef-zones`, `/alerts` | Pulga | **Done (list)** | All 25 `formula_terms` inspectable per zone from the UI |
| core-E | Explanation + Retrieval | `/assistant` | Pulga | **Shell** | Live `POST /ask`; an uncited answer never renders as an answer |

---

## Phase 4 dashboard features (30)

| ID | Feature | Route(s) | Owner | State today | The one thing that makes it Done |
|---|---|---|---|---|---|
| p4-01 | Storm Replay Mode | `/dashboard/replay/:eventId` | Abd | **Shell** | Rainfall → runoff → sediment → plume → exposure plays in sequence from real frames |
| p4-02 | Live Forecast Mode | `/dashboard` (Forecast) | Nizar | **Not started** | A calm day reads as low risk, from `/forecast/latest` — see the architecture gap in `03-nizar.md` |
| p4-03 | 8-Hour Countdown | `/dashboard` | Nizar | **Not started** | Live countdown composed from `arrival_window_hours` + `issued_at`, never a static number |
| p4-04 | Top Weather Drivers | `/dashboard` risk card | Mahdi + Pulga | **FAIL (Phase 6)** | Real driver names reach `/explain` **and** render as a grammatical sentence |
| p4-05 | Confidence Meter | `/dashboard` | Karam | **Shell** | Phrased exactly as "X% of ensemble members exceed this catchment's Nth-percentile rainfall" |
| p4-06 | Bilingual Assistant | `/assistant` | Pulga | **Shell** | Answers in the language asked, full RTL, citations always |
| p4-07 | What-If Scenario Presets | `/dashboard` drawer | Pulga | **Backend-only** | The drawer actually sends `rainfall_multiplier` + `transmission_loss_override` |
| p4-08 | Rain Intensity Ranking | `/events` | Karam | **Shell** | Ranked on `rank`/`max_daily_mm` — **never** `max_anomaly_ratio` (stale column) |
| p4-09 | "AI Never Saw This Storm" | `/dashboard` model panel | Mahdi | **Not started** | `temporal_holdout_AP` from `/models`, framed as a temporal holdout |
| p4-10 | Real Sensor Proof Overlay | `/dashboard/validation` | Abd | **Shell** | Live mooring endpoint, per-field provenance and uncertainty rendered |
| p4-11 | Simple Guess vs Smart Guess | `/dashboard` model panel | Mahdi | **Not started** | `baseline_mean_AP` vs `mean_AP` from `/models`, both labelled |
| p4-12 | Click-to-See-Why | `/reef-zones/:id` | Pulga | **Not started** | Click any score → every input that produced it |
| p4-13 | Honest Limits Page | `/limitations` | Ali | **Shell** | Every documented limitation rendered, Arabic-pending marked honestly |
| p4-14 | 3D Journey | journey overlay | Abd | **Shell** | Six phases play; terrain assets present or the absence stated |
| p4-15 | Judge-Controlled Slider | `/dashboard` drawer | Pulga | **Backend-only** | Slider moves a real API parameter and the response changes on screen |
| p4-16 | Rainfall Accumulation Chart | `/dashboard` | Karam | **Shell** | Small multiples, one shared scale, real rolling columns |
| p4-17 | The Gap Chart | `/limitations` | Mahdi | **Not started** | The 21×/78× event-frequency gap, drawn honestly |
| p4-18 | Toughest Coral Fact | `/` landing | Ali | **Not started** | One sourced fact about Gulf of Aqaba thermal resilience |
| p4-19 | One-Line Mission Statement | `/` landing | Ali | **Done** | Present in the hero, both languages |
| p4-A | Named Reef Zone Priority List | `/reef-zones` | Pulga | **Done** | Sorted by live exposure, placeholder weight flagged per row |
| p4-B | Dive Site Safety Status | `/reef-zones/:id`, map | Karam | **Backend-only** | 46 real POIs; the 30–54 km inland ones carry their "not a real safety association" caveat |
| p4-C | Transmission Loss Reality Check | `/dashboard` drawer | Mahdi | **Backend-only** | The Negev-proxy provenance stated next to the slider |
| p4-D | Culvert & Drainage Correction Map | `/dashboard` layer | Mahdi | **Not started** | 27 real culverts; `AQ-O02`/`AQ-O03` candidate-correction verdicts visible |
| p4-E | Enclosed Harbor Warning | `/dashboard`, `/alerts` | Pulga | **Shell** | `AQ-O04`'s critical caveat impossible to miss wherever that outlet appears |
| p4-F | Multi-Source Weather Agreement | `/dashboard` | Nizar | **Not started** | HYCOM vs Copernicus agreement, `null` rendered as "cache aged out", not 0 |
| p4-G | Historical Event Search | `/events` | Karam | **Shell** | 675 events, filterable, each linking to its replay |
| p4-H | Offline Emergency Mode | cross-cutting | Ali + Mahdi | **Shell** | A person runs it with wifi physically off and signs the check |
| p4-I | Coastal Zone Risk Comparison | `/reef-zones` | Pulga | **Backend-only** | Calls all 5 outlets and assembles client-side — `/alerts` alone cannot produce this |
| p4-J | Post-Storm Damage Estimate | `/reports` | Mahdi | **Not started** | A **class**, never a tonnage, for any non-anchor event |
| p4-K | Seasonal Risk Calendar | `/events` | Karam | **Not started** | Month-by-month, framed as **rainfall intensity**, not exposure |

---

## Phase 5 AI features (9)

| ID | Feature | Route(s) | Owner | State today | The one thing that makes it Done |
|---|---|---|---|---|---|
| b1 | Automated Plume Segmentation | — | Mahdi | **Absent** | Named on `/limitations` as not built |
| b2 | Learned Transmission-Loss Model | — | Mahdi | **Absent** | Named on `/limitations`; live value is the borrowed Negev proxy |
| b3 | Cross-Site Transfer Learning | — | Mahdi | **Absent** | Named on `/limitations` |
| b4 | Automated Site-Scoring Agent | `/sites/score` | Pulga | **Shell** | Six criteria, `null` → "insufficient data", one-site caveat always |
| b5 | Post-Event Forensic Report | `/reports` | Pulga | **Shell** | `ai_drafted` vs `human_reviewed` badge unmissable; no-list-endpoint stated |
| b6 | Live Anomaly Detection | `/dashboard` banner | Nizar | **Not started** | `anomaly_caveat` rendered **verbatim**; never conflated with the Confidence Meter |
| b7 | Adaptive Sampling Recommender | `/reef-zones/:id` | Pulga | **Backend-only** | Honesty copy: infrastructure, not a working feature; the 5 rows were synthetic |
| b8 | Coral Health Vision Model | `/reef-zones/:id` | Pulga | **Shell** | Proposed weight visually inseparable from live weight — the phase's hard safeguard |
| b9 | Culvert/Drainage-Conflict Detector | — | Mahdi | **Absent** | Named on `/limitations`; the 27 culverts remain a manual result |

---

## Tally at the start of Phase 7

| State | Count |
|---|---|
| Done | 3 — `core-D` (list), `p4-19`, `p4-A` |
| Shell | 16 |
| Backend-only | 6 |
| Not started | 14 |
| Absent (no backend) | 4 — `b1`, `b2`, `b3`, `b9` |
| FAIL carried from Phase 6 | 1 — `p4-04` |

**44 rows.** Update your own rows only, and only after looking at the running app.
A row that changes state without a screenshot under `tasks/phase7/evidence/` is a
claim, and Phase 6 exists because this team stopped accepting those.

---

## Environmental failures to leave alone

These fail today for reasons that are not feature work. Do not "fix" them by
weakening the test.

| What | Why | Owner |
|---|---|---|
| `journey3d.spec.ts` × 3 | `public/terrain/` and `public/basemap-raster/` are gitignored and absent; regenerate with `scripts/tile_terrain_rgb.py` and `scripts/fetch_basemap_raster.py` | Abd |
| `offline-arabic.spec.ts` "no external requests" | Three real backend calls fire on a plain pan/zoom; pre-existing since Phase 4, unowned until now | Ali |
| journey 60fps sample | Passes in isolation, fails under full-suite load — machine contention, not a regression | Abd |
