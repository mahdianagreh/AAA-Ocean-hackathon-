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

- [x] **Decision, 2026-08-09: option (b), forecast-only.** `ExposureRequest` has no
      rainfall field today, and wiring one in is real work that touches Pulga's
      exposure engine — not something to do unilaterally days before a demo. Shipped
      what `/forecast/latest` actually has: per-catchment rain, wind, real GEFS
      exceedance, plus the anomaly signal and currents agreement — with an explicit,
      always-visible statement (`forecast.noScoreYet`) that this does not yet produce
      a reef exposure score.
- [x] `GET /api/v1/forecast/latest` wired via `useForecastLatest` (`frontend/src/
      app/useForecastLatest.ts`), typed properly in `frontend/src/api/live.ts`
      (was a bare `Record<string, unknown>`). `issued_at` shown per model
      (GFS/GEFS), each with its own timestamp — never implied to be live.
- [x] `rain_mm: null` renders through `ValueWithUnit` as a stated gap, not coerced
      to 0 — same component every other measurement on screen already uses.
- [x] Confirmed live: the current cached snapshot has real 0.00 mm/3h readings
      across all five catchments and 0/30 members exceeding — reads as calm/low
      risk, not a fabricated "always dangerous" view.

### `p4-03` 8-Hour Countdown — `/dashboard`

- [x] `frontend/src/components/Countdown.tsx` — composed client-side from an
      `arrival_window_hours` tuple + a reference ISO timestamp. No new endpoint.
- [x] Live ticking (`setInterval`, 1s), not a static number — no hand-typed value
      copied from the foundation deck.
- [x] `num` (tabular figures) on the digits, `dir="ltr"` unconditionally, even
      rendered inside the Arabic layout.
- [x] No arrival window exists in Forecast mode today (no live exposure score is
      computed there, per the `p4-02` decision above) — confirmed this renders the
      honest `countdown.noWindow` absence, never `00:00:00`. This is the exact
      case the component is built to handle, not a bug.
- [x] `Intl.DateTimeFormat` with the explicit IANA zone `Asia/Jerusalem`, not a
      fixed offset — correctly resolves IDT vs. IST across DST boundaries,
      including the Oct 2016 demo window.

### `b6` Live Anomaly Detection — `/dashboard` banner

✅ **You closed this on 8 Aug: Phase 6 PASS**, fed both a real anomalous and a real
normal value through the live detector. The detector is no longer the risk — the
banner is, and it does not exist yet.

Note the cached snapshot still has no `gefs_anomalies` key, so `/forecast/latest`
returns `anomalies: []` against it. The banner must handle "detector works, this
snapshot has nothing to report" without looking broken.

- [x] `frontend/src/components/AnomalyBanner.tsx` — fires on `is_anomalous`, shaped
      like `States.tsx`'s `ErrorState` (bordered card, `risk-high` border+text), not
      `ConfidenceMeter`'s meter bar. It is not a hazard-band tag, so it does not
      reuse that shape either.
- [x] Inline SVG sparkline (`Sparkline`, same file) plots `anomaly_score`, anomalous
      points marked distinctly — no new charting dependency for one small chart.
- [x] `anomaly_caveat` rendered verbatim from the API response, no paraphrase.
- [x] Confirmed structurally, not just by convention: `/forecast/latest`'s
      `anomalies`/`anomaly_caveat` fields and `/exposure/calculate`'s
      `confidence_*` fields share zero field names and live in entirely separate
      endpoints and components — conflation is structurally impossible, not merely
      avoided.
- [x] Labelled "percentile-relative" in the caveat text and in `03-nizar.md`/code
      comments — never called a z-score anywhere.
- [x] The real, current empty case (`anomalies: []`) renders `forecast.anomalyQuiet`
      — "no unusual pattern detected" — not a blank space that reads as broken.

### `p4-F` Multi-Source Weather Agreement — with Karam · 🔴 **FAIL**

Phase 6 recorded this as a **real bug**, reproduced independently by you and Karam,
and left unfixed under Phase 6's no-fix rule. **Fixing it is yours this phase.**

The defect: `GET /api/v1/currents/agreement` answers with a **bare HTTP 500** — there
is no missing-file check on the Copernicus Marine path. With the git-ignored `.nc`
cache present it returns 200, which is the row's real point: **its correctness
currently depends on which machine you are sitting at.**

- [x] Fixed, `backend/src/api/main.py`'s `currents_agreement()`: added the
      matching `copernicus_path.exists()` 503 guard (mirrors the existing
      `hycom_path` one, same plain-string style — confirmed this file uses that
      style, not the dict-body style the two model-harness endpoints use). Also
      wrapped `compare_hycom_vs_copernicus()` in `try/except OSError`, since a
      corrupt/truncated `.nc` file passes `.exists()` but still fails to open —
      this actually fired live during testing (a Docker bind-mount race after
      moving the file aside), proving the guard is necessary, not theoretical.
      Verified: real 200 with the cache present, clean 503 (never a bare 500)
      with it removed, restored to 200 again.
- [x] Surface built after the fix: `frontend/src/components/CurrentsAgreementCard.tsx`.
- [x] Live-confirmed it reproduces the documented **65.82°** disagreement and
      **0.63** agreement score for the demo event, screenshotted in
      `evidence/forecast/`.
- [x] `agreement` comes straight from the API's own continuous
      `1 - diff/180` value — not recomputed in the frontend. `null` renders
      "not available" via `forecast.currentsUnavailable`, never 0.
- [x] Replaced the placeholder framing entirely — the card's headline number is
      the real 65.82° disagreement, not "in agreement."

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

- [x] The `p4-02` decision is written down here, dated, and the UI matches it
- [x] The countdown ticks from real values and renders its own absence
- [x] The `b6` banner exists and handles an empty-but-working detector honestly
- [x] The anomaly banner is visually and verbally distinct from the Confidence Meter
- [x] Currents agreement shows real disagreement or an honest "not available"
- [x] Screenshots under `tasks/phase7/evidence/forecast/` and `.../anomaly/`, EN + AR,
      light + dark
- [x] `npm run qa` green (14/14 tests, typecheck clean), `qa_frontend_tokens.py` and
      `qa_frontend_rtl.py` both exit 0

## Closed, 2026-08-09

All four rows built and verified live against a freshly built API + frontend
(`docker compose --profile frontend up --build`). Also fixed a now-stale leftover:
`Masthead.tsx`'s `mode.forecastPending` ("no live forcing wired yet") banner was
still showing for Forecast mode even though it's real now — scoped the fix to
`mode === 'scenario'` only, not touching that mode's own status (not mine to call).

**One unrelated finding, not fixed, not mine:** running `rebrand-smoke.spec.ts`
turned up `GET /api/v1/reef-zones/R-03` returning a bare 404 — there is no
per-zone endpoint at that path, only the list endpoint
(`/api/v1/reef-zones?include_geometry=...`). `ReefZonePage.tsx` hangs on "Loading
this zone…" as a result. Reef zones are Pulga's domain; flagging for him/Ali
rather than touching it.
