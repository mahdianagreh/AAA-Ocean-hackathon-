# Phase 7 — Nizar

**Owns:** forecasts, ocean currents, anomaly detection, Supabase.
**Pages:** Forecast mode on `/dashboard` · the countdown · the anomaly banner ·
the currents-agreement surface.
**Rows:** `p4-02`, `p4-03`, `p4-F` (with Karam), `b6`.

Read [`00-phase7-plan.md`](00-phase7-plan.md) and
[`00-design-system.md`](00-design-system.md) first.

You have the fewest rows and the hardest one. `p4-02` is not a screen that was never
drawn — it is a **hole in the architecture**, and it has been open since Phase 4.

---

## The brand, in the two lines you will actually use

Never write a colour — `python3 scripts/qa_frontend_tokens.py` fails on a hex literal
in `frontend/src/`.

```
grounds   bg-canvas  bg-surface  bg-surface-2   borders  border-hairline
ink       text-ink   text-ink-2  text-ink-3     accent   text-accent
hazard    BAND_CLASS from src/api/types.ts
```

Deep Navy `#0A1F4D` · Ocean Blue `#0D3D7A` · Marine Teal `#007A99` · Aqua `#00B7C3`
· Foam White `#E6F7FA`. Montserrat; every number through `<ValueWithUnit>` in IBM
Plex Mono. Radii 8/12/16/20. Cards are `<Card>`.

**Your pattern:** you own the two most "alive" elements on the dashboard — a live
countdown and an anomaly banner. Both are exactly where a product starts lying if
nobody is careful. Aqua `#00B7C3` and the pulsing dot are already established for
"live"; reuse the chip in the masthead rather than inventing a second treatment.

---

## Your rows

### `p4-02` Live Forecast Mode — read this before you plan anything

✅ **Phase 6, 8 Aug: PASS on the backend half**, with a real **staleness** finding —
the architecture is cache-only, which is a finding about freshness, not a code defect.
Ali's frontend half is still open, and the gap below is still open.

**The gap, stated exactly** (`tasks/phase4/03-nizar.md` lines 88–98):

> `ExposureRequest` has no rainfall field (`schemas.py:319-326`), so a forecast
> lead-hour has **zero path** into an exposure score. Exposure always sources from
> `da.training_row(...)` or a hardcoded 30.0 mm/3h fallback.

And the frontend side: there are **zero references** to `/forecast/latest` anywhere in
`frontend/src/`, and `Mode` includes `'forecast'` whose i18n string is literally
*"no live forcing wired yet"*.

So this row is a decision before it is a build. Pick one, **write down which and why**:

- **(a)** Add a rainfall/forecast input to `ExposureRequest` so a lead-hour can drive
  a real score. Real work, real value, touches Pulga's engine — agree it with him.
- **(b)** Ship Forecast mode as **rainfall-and-exceedance only** — show what
  `/forecast/latest` genuinely has (per-catchment rain, wind, GEFS exceedance) and
  state plainly that it does not yet produce a reef exposure score.
- **(c)** Remove the mode until it is real.

**(b) is the honest default** if time is short. What is not acceptable is a Forecast
tab that renders an exposure score sourced from a training row while looking live.

- [ ] Decision recorded here, with the date.
- [ ] `GET /api/v1/forecast/latest` wired. It is a **cached snapshot** (GFS/GEFS run
      `2026-08-03T00Z`), never live — say so with `issued_at` on screen.
- [ ] Many `rain_mm` values are `null` in the snapshot. Gaps, not zeros.
- [ ] **A calm day must read as low risk.** The plan asks for this explicitly; a
      forecast view that always looks dangerous is worthless.

### `p4-03` 8-Hour Countdown — `/dashboard`

- [ ] Composed **client-side** from `arrival_window_hours` and the forecast's
      `issued_at`. No new endpoint.
- [ ] A live ticking countdown, not a static number. The foundation deck shows
      `07:40:41` — that is a **hand-typed placeholder**, do not copy the value.
- [ ] Tabular figures (`num`) so digits do not jitter. `dir="ltr"` on the clock in
      Arabic.
- [ ] When there is no arrival window, render the absence — never `00:00:00`, which
      reads as "it has arrived".
- [ ] `ZoneInfo("Asia/Jerusalem")` for any local-time display. October 2016 is inside
      IDT (UTC+3), not IST. Never a fixed offset.

### `b6` Live Anomaly Detection — `/dashboard` banner

✅ **You closed this on 8 Aug: Phase 6 PASS**, fed both a real anomalous and a real
normal value through the live detector. The detector is no longer the risk — the
banner is, and it does not exist yet.

Note the cached snapshot still has no `gefs_anomalies` key, so `/forecast/latest`
returns `anomalies: []` against it. The banner must handle "detector works, this
snapshot has nothing to report" without looking broken.

- [ ] Banner fires on `is_anomalous`, in its own colour — **distinct from the hazard
      ramp**, because this is not a risk level.
- [ ] Rolling sparkline with anomalous points marked by `anomaly_score`.
- [ ] **Render `anomaly_caveat` verbatim. Do not paraphrase it.**
- [ ] 🔴 **Never conflate this with the Confidence Meter** (`p4-05`, Karam's). Different
      inputs, different claim. Two "confidence-ish" numbers next to each other with no
      distinction is how a judge concludes the team does not understand its own model.
- [ ] It is **percentile-relative, not a z-score**. Label it that way.

### `p4-F` Multi-Source Weather Agreement — with Karam · 🔴 **FAIL**

Phase 6 recorded this as a **real bug**, reproduced independently by you and Karam,
and left unfixed under Phase 6's no-fix rule. **Fixing it is yours this phase.**

The defect: `GET /api/v1/currents/agreement` answers with a **bare HTTP 500** — there
is no missing-file check on the Copernicus Marine path. With the git-ignored `.nc`
cache present it returns 200, which is the row's real point: **its correctness
currently depends on which machine you are sitting at.**

- [ ] Fix the backend to answer a *missing cache* with a structured, honest response
      — 503 with a body naming what is absent, in the style the model endpoints
      already use — never a bare 500.
- [ ] Only then build the surface.
- [ ] Reproduces the documented 65.82° HYCOM-vs-Copernicus disagreement for the demo
      event. Show the disagreement, not a reassuring green tick.
- [ ] `agreement = 1 − diff/180`, continuous. `null` when the cache aged out — render
      "not available", never 0.
- [ ] The foundation deck shows three aqua dots and "GFS, GEFS and HYCOM in
      agreement". **That is placeholder art.** The real answer for this event is that
      two current models disagree by 65.82°, and saying so is more impressive than
      three green dots.

---

## Two facts about your data layer that must not reach the UI wrongly

1. **Supabase is a batch mirror, not the live path.** The demo reads local files and
   `exposure_runs.sqlite`. Anything you wire to Postgres shows
   whenever-someone-last-ran-the-loader numbers. `runoff_predictions` is empty and
   nothing writes to it.
2. **The Gulf is narrower than three cells of the best free ocean model.** Every
   current-derived number on screen inherits that. Probabilistic language, always.

---

## Done means

- [ ] The `p4-02` decision is written down here, dated, and the UI matches it
- [ ] The countdown ticks from real values and renders its own absence
- [ ] The `b6` banner exists and handles an empty-but-working detector honestly
- [ ] The anomaly banner is visually and verbally distinct from the Confidence Meter
- [ ] Currents agreement shows real disagreement or an honest "not available"
- [ ] Screenshots under `tasks/phase7/evidence/forecast/` and `.../anomaly/`, EN + AR,
      light + dark
- [ ] `npm run qa` green, `qa_frontend_tokens.py` exit 0
