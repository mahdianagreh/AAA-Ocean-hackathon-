# Phase 4 — the feature list, against what actually runs

Source: the demo feature audit run live against the stack on 6 Aug 2026 (containers
rebuilt, every claim checked against the filesystem or a running endpoint, not recalled).
Full findings: the audit report in this conversation's history. This plan turns that
audit's verdicts into six people's task lists.

Read your own file next: [`01-karam.md`](01-karam.md) · [`02-mahdi.md`](02-mahdi.md) ·
[`03-nizar.md`](03-nizar.md) · [`04-pulga.md`](04-pulga.md) · [`05-abd.md`](05-abd.md) ·
[`06-ali.md`](06-ali.md)

---

## The one fact that shapes this whole phase

**Every exposure score the live system can currently produce for the documented demo
event tops out at 9.05 / 100 — "minimal" band.** Confirmed live on 6 Aug, both before and
after the sediment-anchor merge landed. Sediment is real and non-zero now
(`relative_sediment_intensity: 0.084`, `sediment_index` provenance string present in every
`formula_terms`), which is genuine progress — three weeks ago this number was exactly
0.0 everywhere. But the headline score still can't leave "minimal," because
`plume_probability` is still `SYNTHETIC_STUB`, `confidence_adjustment` is a placeholder,
and exposure is a product of five terms each ≤1.

That single fact is why so many rows below say 🟡 rather than 🔴 or ✅: the *data* behind
a feature is often real, and the thing actually missing is one specific piece of wiring —
usually the plume engine, sometimes a threshold, sometimes an API parameter that doesn't
exist yet. Nothing in this list is blocked on new data collection. Everything blocked is
blocked on a named file, a named person, or a named number.

## Status legend (carried from the audit)

| | |
|---|---|
| ✅ Doable now | Real data, real endpoint, live-verified. Remaining work is UI/composition only. |
| 🟡 Partial | Some real piece exists; a specific, named gap keeps it from being honestly demoable. |
| 🔴 Not yet / risky as worded | Either nothing is wired, or the feature as named overclaims what one data point supports. |

## Ownership map

Assigned by matching each gap to whoever already owns the file, model or pipeline it
sits in — not evenly split by headcount. Ali appears on almost every row because nearly
every feature has a screen; that is the frontend's job, not a sign Ali is behind.

| # | Feature | Status | Primary | Also needs |
|---|---|---|---|---|
| 1 | Storm Replay Mode | 🟡 | Abd | Ali |
| 2 | Live Forecast Mode | 🟡 | Nizar | Ali |
| 3 | 8-Hour Countdown | ✅ | Ali | — |
| 4 | Top Weather Drivers Explainer | 🟡 | Mahdi | Pulga, Ali |
| 5 | Confidence Meter | 🟡 | Karam | Nizar |
| 6 | Bilingual Assistant | ✅ | — (done) | — |
| 7 | What-If Scenario Presets | 🔴 | Pulga | Ali |
| 8 | Rain Intensity Ranking | ✅ | Karam | Ali |
| 9 | "AI Never Saw This Storm" | 🟡 | Mahdi | — |
| 10 | Real Sensor Proof Overlay | 🔴 | Abd | Pulga, Ali |
| 11 | Simple Guess vs Smart Guess | ✅ | Ali | — |
| 12 | Click-to-See-Why | ✅ | Ali | — |
| 13 | Honest Limits Page | ✅ | — (done) | — |
| 14 | 3D Journey | 🟡 | Ali | Abd (plume portion, deferred) |
| 15 | Judge-Controlled Slider | 🔴 | Pulga | Ali |
| 16 | Rainfall Accumulation Chart | ✅ | Ali | Karam |
| 17 | The Gap Chart | ✅ | Ali | — |
| 18 | Toughest Coral Fact | ✅ | Ali | — |
| 19 | One-Line Mission Statement | ✅ | — (done) | — |
| A | Named Reef Zone Priority List | ✅ | Ali | Pulga |
| B | Dive Site Safety Status | ✅ | Karam | Pulga, Ali |
| C | Transmission Loss Reality Check | 🟡 | Mahdi | Pulga, Ali |
| D | Culvert & Drainage Correction Map | ✅ | Mahdi | Ali |
| E | Enclosed Harbor Warning Flag | ✅ | — (done) | Ali (verify) |
| F | Multi-Source Weather Agreement | 🟡 | Nizar | — |
| G | Historical Event Search | ✅ | Karam | Ali |
| H | Offline Emergency Mode | 🟡 | Mahdi | Ali |
| I | Coastal Zone Risk Comparison | ✅ | Ali | Pulga |
| J | Post-Storm Damage Estimate | 🔴 | Mahdi | Ali |
| K | Seasonal Risk Calendar | ✅ | Karam | Ali |

Six rows are already done end to end (6, 13, 19, E — mostly, plus static content 17/18)
and need no further work; they're in each relevant person's file as "verify, don't rebuild."

## The dependency chain that gates the most rows

```
Abd wires the real particle engine into /plume/simulate
        │
        ├── unblocks Storm Replay (1) fully
        ├── unblocks the 3D Journey's plume-cloud portion (14)
        └── raises every exposure score off the plume-stub ceiling,
            which is what makes 2, 4, 5 look muted today
```

This is the same single point of leverage the Phase 3 audit found before sediment
anchoring landed — it just moved from "sediment is 0.0" to "plume is a synthetic buffer."
**One piece of wiring, most visible improvement.** `particle_engine.py` and its 23 tests
already exist; this is route-wiring in `main.py`, not new modeling — see
[`05-abd.md`](05-abd.md) item 1.

## Two things to say out loud before building anything

1. **Nothing on this list needs new data.** Every 🔴 and 🟡 traces to a specific missing
   endpoint, an unwired route, or a UI not yet pointed at a real API — never to "we don't
   have that dataset." Say this to whoever is judging scope; it changes what "not ready"
   means.
2. **Item J (Post-Storm Damage Estimate) is written wrong and should be renamed before
   anyone builds it.** The sediment model is anchored to **one** real point — 24,400 t,
   AQ-2016-10-28, AQ-C01. A precise tonnage for a *different* storm is an extrapolation
   along an unverified curve, stated as such in the anchor file itself
   (`data/models/sediment_anchor.json`: *"ONE measurement fixes the SCALE, never the
   SHAPE... any mass for a different event is an extrapolation along an unverified
   curve"*). The honest version of this feature reports a class — Low/Medium/High/Extreme
   — never a number of tonnes. Mahdi and Ali both have this framed correctly in their
   files; don't let a slide walk it back to a fake-precise figure.

## Definition of done for Phase 4

1. Every ✅ row confirmed still true after everyone's changes land (nothing regresses).
2. Every 🟡 row's named gap closed, or explicitly deferred with a reason on record.
3. Every 🔴 row either built for real or the feature name corrected to match what the
   data actually supports (see item J above).
4. Re-run the audit's live checks after all six files are done. If a row that was 🟡
   is now claimed ✅, prove it the same way the audit did — a live curl or a running
   test, not a read of the code.
