# Ali — Frontend

**Phase 2 · Workstream 6**
**Feeds:** the judges. Everything the team built is invisible until you draw it.
**Read [`00-phase2-plan.md`](00-phase2-plan.md) first.**

---

## Why your stream matters

Five people are producing numbers that nobody can see. The map **is** the product — the
concept doc's entire demo storyboard (§15.3) is eight scenes on one screen.

Two consequences worth internalising:

**You are on the critical path from Day 1.** You cannot start when the data is ready,
because it will not be ready until Day 8. Build against stubs immediately and swap in the
real endpoints as they land. Pulga owes you typed shapes on Day 3 for exactly this reason.

**Your second job is restraint.** Concept §25 lists *"dashboard becomes more important than
science"* as a real risk. A beautiful UI over one validated backtest wins; a spectacular UI
over five unvalidated map pins does not. Freeze the interface early and spend the back half
making it honest and fast.

---

## Stack

React · TypeScript · **MapLibre GL JS** · Deck.gl for animated particles if it earns its
place · Recharts or ECharts for time series. Runs in Mahdi's Docker Compose alongside the
API.

**Bilingual Arabic / English with full RTL.** Not a late-stage translation pass — build the
layout RTL-capable from the first component, or you will rewrite it in the last three days.

---

## 1 · The map

- [ ] Coastline (`coastline.gpkg`) and the AOI boxes
- [ ] **5 catchments** `AQ-C01`…`AQ-C05`, coloured by runoff risk
- [ ] **5 outlets** `AQ-O01`…`AQ-O05`, sized by upstream area
- [ ] **8 reef zones** `R-01`…`R-08`, coloured by exposure score
- [ ] Rainfall intensity over the catchments
- [ ] **Time-stepped plume probability field** — a probability surface, contoured. **Never a
      single trajectory line.**
- [ ] Bathymetry / depth as an optional layer
- [ ] Dive sites and the Aqaba Marine Park boundary as optional layers (both in
      `osm_aqaba.gpkg`)
- [ ] Time slider driving every time-varying layer together

> **The plume must always render as a probability field with its confidence stated.** The
> best free ocean model is ~9 km across a gulf 15–25 km wide — two to three cells span the
> whole basin. Nizar proved this concretely: our own release point sits on a cell the model
> masks as land. A single confident line on this map would be a claim the data cannot
> support, and `docs/forcing_limitations.md` says so in the exact words you should put in
> the UI.

---

## 2 · Three modes

| Mode | Shows |
|---|---|
| **Historical** | Reconstruct `AQ-2016-10-28` — rainfall, runoff, plume, exposure, then the validation panel |
| **Forecast** | Today's live GFS/GEFS/IFS → per-catchment risk. **Must work on a dry day and show a correctly low number** — a system that only demos during a storm is not demoable |
| **Scenario** | The user changes parameters and watches risk change |

### Scenario controls

- [ ] Rainfall multiplier
- [ ] Wind direction and speed
- [ ] Sediment load class
- [ ] Diffusion coefficient
- [ ] Settling velocity
- [ ] **Transmission loss** — 13–98% of a desert flood soaks into the wadi bed and never
      reaches the sea (Negev range 20–85%). Mahdi is making this an explicit model parameter.
      Putting a slider on it turns the project's largest assumption into a visible feature
      rather than a hidden one.

---

## 3 · Risk cards

One per reef zone at risk:

```text
HIGH MARINE SEDIMENT RISK

Catchment:            AQ-C01 / Wadi Yutum
Runoff probability:   81%
Sediment severity:    High
Coastal discharge:    AQ-O01
Reef zones at risk:   R-03, R-04
Estimated arrival:    8-12 hours
Forecast confidence:  Moderate

Recommended action:
Prioritize water-quality observation near R-04 and review
temporary dive-site restrictions.
```

- [ ] Show the **top drivers** from SHAP, not just the score.
- [ ] Show **confidence**, derived from GEFS ensemble exceedance — *"72% of members exceed
      this catchment's 99th-percentile 3-hour rainfall"* is a real number and it should be
      visible as one.
- [ ] Risk bands per concept §14.5 (0–20 minimal … 81–100 critical), with the note that
      operational thresholds require marine scientists.

---

## 4 · The panels that separate this from a pretty map

These are where the team's Phase 1 rigour becomes visible. Do not treat them as optional.

### Validation panel

- [ ] **Modelled vs measured**, plotted together: the mooring's salinity and turbidity time
      series against the model's predicted arrival and duration at the same point.
- [ ] State the measured numbers plainly: salinity −1.75 ‰ (19σ), turbidity peak 2.18 g/L,
      elevated ~31 hours.
- [ ] Include the **satellite null result**: two sensors, no visible plume, because the plume
      dispersed 2.5–3.5 days before either pass. Shown as a finding, not hidden as a failure.

### Provenance panel

- [ ] The 34 QA figures from `docs/qa_screenshots/`, with their captions from `MANIFEST.md`.
      Click a layer → see the figure that proves it is right.
- [ ] The **Data Sources** table from `data_sources`: product, version, resolution, access
      date, licence, known limitation. Concept §22.4 scores exactly this.

**No other team will have this.** "Here is the picture that proves our depth field's sign
convention, across 22 control points" is an unusual thing to be able to show.

### Limitations page

- [ ] In-app, from `docs/pitch_limitations.md` and `docs/forcing_limitations.md`.
- [ ] Say the uncomfortable things: soil data is a global model not local measurement; reef
      `sensitivity_weight = 1.0` is a placeholder; bathymetry cannot see the reef shelf; reef
      zone widths are a 250 m assumption; land cover is a 2021 snapshot used for a 2016 event.

### Assistant

- [ ] Chat surface over Pulga's `/ask`. Every answer renders **with its citation** — source
      file and section. An uncited answer must not render as an answer.
- [ ] Bilingual.

---

## 5 · Demo storyboard — build toward this

Concept §15.3, adjusted for what actually exists:

1. **The problem** — narrow coast, steep catchments, reef metres from shore. Kinnet Canal
   site photos if their provenance gets confirmed.
2. **A historical storm** — select `AQ-2016-10-28`.
3. **Land prediction** — rainfall over Wadi Yutum, runoff probability, activated outlet.
4. **Marine prediction** — plume probability at T+3 / +6 / +12 / +24 h.
5. **Reef exposure** — zones shifting from low to high.
6. **Validation** — modelled arrival against the *measured* mooring record.
7. **What-if** — raise rainfall 20%, or rotate the wind, and watch risk move.
8. **Recommendation** — the alert, with confidence and the honest caveat.

---

## Definition of done

1. Map with all layers, time slider, three modes.
2. Scenario controls including transmission loss.
3. Risk cards with SHAP drivers and a derived confidence figure.
4. Validation panel: modelled vs measured, plus the satellite null result.
5. Provenance panel: 34 figures + the data-sources table.
6. In-app limitations page.
7. Assistant with visible citations.
8. Bilingual AR/EN with working RTL.
9. Runs in Docker Compose; works with **wifi off** against the offline snapshot.

## What you depend on

| From | What | When | Blocked? |
|---|---|---|---|
| **Pulga** | typed endpoints, stubs acceptable | **Day 3** | Yes until then — build the shell and layout now |
| **Nizar** | stable read schema | Day 3 | No |
| **Abd** | plume layers per timestep | Day 6 | No — stub with a static polygon |
| **Mahdi** | risk fields + driver list | Day 5 | No — stub |
| **Pulga (QA)** | the 34 figures + captions | Day 4 | No — they already exist in the repo |

---

## One note on the research documents

`docs/ali/*` — your MENA and global analogue scan — is **research and pitch material, not an
app surface.** It backs the market slide and answers *"is this only for Aqaba?"* in Q&A. It
does not become a screen, and it is not in the assistant's corpus. Building it into the UI
would spend frontend days on something the pitch already covers in one slide.
