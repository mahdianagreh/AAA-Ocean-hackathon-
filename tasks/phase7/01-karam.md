# Phase 7 — Karam

**Owns:** rainfall, the event catalogue, climatology, ensemble confidence, dive sites.
**Pages:** `/events` (yours end to end) · the rainfall and confidence surfaces on
`/dashboard` · the dive-site layer.
**Rows:** `p4-05`, `p4-08`, `p4-16`, `p4-B`, `p4-F` (with Nizar), `p4-G`, `p4-K`.

Read [`00-phase7-plan.md`](00-phase7-plan.md) and
[`00-design-system.md`](00-design-system.md) first. This file assumes both.

---

## The brand, in the two lines you will actually use

Never write a colour — `python3 scripts/qa_frontend_tokens.py` fails the build on a
hex literal in `frontend/src/`.

```
grounds   bg-canvas  bg-surface  bg-surface-2   borders  border-hairline
ink       text-ink   text-ink-2  text-ink-3     accent   text-accent
hazard    BAND_CLASS from src/api/types.ts — never hand-map a band to a colour
```

Deep Navy `#0A1F4D` · Ocean Blue `#0D3D7A` · Marine Teal `#007A99` · Aqua `#00B7C3`
· Foam White `#E6F7FA`. Montserrat for text, IBM Plex Mono for every number (the
`num` utility), IBM Plex Sans Arabic for Arabic. Radii 8/12/16/20. Cards are
`<Card>`: white, 20px radius, hairline border, 24px padding.

**Your one recurring trap:** `--ink-3` on `--surface-2` fails AA in dark theme. Your
tables have a lot of secondary text on recessed rows — use `text-ink-2` there.

---

## Charts, specifically — this is most of your phase

You own more data-viz than anyone. Three rules that are already law here:

1. **One shared scale across small multiples.** The hyetograph draws one row per
   catchment against a single axis. Per-row scales make a dry catchment look like a
   flood, and it is invisible in review.
2. **Provenance is form, not hue.** Measured = solid rule, modelled = dashed
   (`stroke-measured` / `stroke-modelled`).
3. **Marine Teal `#007A99` is the "charts & data" colour** per the brand sheet — but
   the hazard ramp is functional and stays ochre→red. Do not blue the ramp.

---

## Your rows

### `p4-G` Historical Event Search — `/events`

✅ **Phase 6: PASS on the backend/data half** (your pass, 8 Aug). Ali's frontend half
is open — which in this phase means yours. The page exists and lists real events. It
is not done.

- [ ] Filter by event ID **and** label; state how many rows are hidden by the filter
      rather than silently truncating. 675 events, no pagination on the API.
- [ ] Sort by `rank` and by date, with `aria-sort` on the header.
- [ ] Each row links to `/dashboard/replay/{event_id}`. **Most will 422** — coordinate
      with Abd so the replay page explains that rather than looking broken.
- [ ] `label` is null for mined events. Render "Unlabelled" with the reason: only
      literature-documented events carry a name.
- [ ] Arabic: numerals stay LTR-isolated inside RTL rows.

### `p4-08` Rain Intensity Ranking — `/events`

- [ ] Rank on **`rank` and `max_daily_mm`**. **`max_anomaly_ratio` is stale — do not
      expose it.** `events_by_intensity.parquet` is stale too. This is written down
      in `tasks/phase4/01-karam.md` and is the easiest wrong number to ship.
- [ ] Per event, show where it sits against 26 years for that catchment — "top N%",
      with the N computed, not typed.
- [ ] The demo event `AQ-2016-10-28` must rank where the data puts it. It is the
      **best-instrumented** flood, **not the biggest** — Feb 2006 deposited more.
      Never label it "the largest".

### `p4-K` Seasonal Risk Calendar — `/events`

✅ **Phase 6: PASS on the data half** — you traced the calendar's data end to end.
There is still **no surface**. `scripts/29_seasonal_risk_calendar.py` exists;
`data/processed/features/seasonal_risk_calendar.parquet` is its output.

- [ ] **There is no endpoint.** Either add one, or ship the parquet as a committed
      fixture. Decide, write down which, and say so on the page.
- [ ] Month-by-month, twelve cells, hazard-ramp coloured with a text label per cell —
      never colour alone.
- [ ] **Frame it as rainfall intensity, not exposure.** Buckets are storms, not reef
      impact. Mislabelling this is a claim the system cannot support.

### `p4-05` Confidence Meter — `/dashboard`

✅ **The only fully-closed row in the project** — your threshold half and Nizar's
ensemble-formula sign-off both landed 8 Aug. Do not regress it; the work below is
what keeps it closed under the rebrand.

- [ ] Compose the sentence in-language from `formula_terms`:
      `confidence_members_exceeding`, `_total`, `_threshold_value_mm`. **Never a
      pre-formatted English string** — Arabic word order is not English word order.
- [ ] Phrase exactly: "X% of ensemble members exceed this catchment's Nth-percentile
      rainfall." A bare percentage means nothing and implies everything.
- [ ] When `confidence_adjustment` is the literal `PLACEHOLDER 0.6 --` fallback (no
      GEFS row), say so. It is prefixed in the payload precisely so you can detect it.
- [ ] **Do not conflate this with b6's anomaly banner.** Different inputs, different
      claim. Nizar owns that one.

### `p4-16` Rainfall Accumulation Chart — `/dashboard`

- [ ] Real rolling 1/3/6/24h columns from `catchment_rainfall_daily.parquet`.
- [ ] ⚠️ `rain_1h/3h/6h/24h_mm` are **all-null in `event_catchment_features.parquet`** —
      a real, buildable join that was never built (`tasks/phase5/01-karam.md`). Either
      build it or render the gap honestly. Do not fill it with the daily value.
- [ ] Mooring markers on the time axis (turbidity onset / cleared) stay.
- [ ] The time bar already says steps are daily while the storm peaked in 3 h. Keep
      that sentence visible — it is the honest frame for this whole chart.

### `p4-B` Dive Site Safety Status

Phase 6 PASS on the backend: 46 real POIs, real geodesic nearest-zone join.

- [ ] Surface on `/reef-zones/:id` (sites mapped to that zone) and as a map layer.
- [ ] **10 sites are within 2 km and trustworthy. The rest are 30–54 km inland** and
      carry an explicit "not a real safety association" caveat. Render that caveat —
      an inland site shown with a dive-safety status is actively misleading.
- [ ] Join key is `osm_id`, 115/115 unique. Never join on name.

### `p4-F` Multi-Source Weather Agreement — with Nizar · 🔴 **FAIL**

You found this in Phase 6 and left it unfixed, correctly. Nizar reproduced it
independently. **It gets fixed this phase — Nizar owns the fix, you own confirming
it.** The defect is a **bare HTTP 500** with no missing-file check on the Copernicus
Marine path; it returns 200 when the git-ignored `.nc` cache happens to be present.

- [ ] `agreement` is `1 − diff/180`, continuous. When the cache has aged out it
      returns `null` — render "not available", never 0, never 100%.

---

## Done means

Every row above meets all six gates in the plan. Specifically for you:

- [ ] `/events` renders 675 real rows, filters, sorts, and links out
- [ ] No chart uses `max_anomaly_ratio` anywhere
- [ ] The Confidence Meter sentence is composed from parts in both languages
- [ ] Every inland dive site carries its caveat
- [ ] Screenshots under `tasks/phase7/evidence/events/` and `.../confidence/`, EN + AR,
      light + dark
- [ ] `npm run qa` green, `python3 scripts/qa_frontend_tokens.py` exit 0
