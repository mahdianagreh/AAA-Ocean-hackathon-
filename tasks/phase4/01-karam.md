# Karam — Phase 4

Integration lead. Read [`00-phase4-plan.md`](00-phase4-plan.md) first.

Your rainfall pipeline is the reason five of these rows are ✅ instead of 🔴 — 675 real
storm events, real per-catchment climatology, real 1/3/6/24h rolling columns, all
git-tracked and already live behind `/api/v1/events`. Phase 4 doesn't ask you to collect
anything new. It asks you to expose what's already sitting in your parquet files as
features a judge can actually click through, and to fix the one threshold that's still a
placeholder.

---

## 1 · Rain Intensity Ranking (feature 8) — ✅ confirm, then hand to Ali

`events.parquet` already has `max_daily_mm`, `mean_daily_mm`, `max_anomaly_ratio`,
`catchments_exceeding_p99` across all 675 storms. `events_by_intensity.parquet` exists
separately — check it's the same ranking or reconcile which one is canonical before Ali
builds against it.

- [ ] Confirm `/api/v1/events` actually returns the ranking columns (I saw the file has
      them; I didn't check the API response shape includes them — do that).
- [ ] If it doesn't, that's a Pulga ask, not new work for you: the data exists, the
      endpoint just needs the columns added to `EventOut`.
- [ ] Tell Ali which column is "the" intensity ranking. Don't let the UI pick between
      `max_daily_mm` and `max_anomaly_ratio` without a documented reason — those rank
      storms differently and a slide showing the wrong one is worse than no ranking.

---

## 2 · Historical Event Search (feature G) — ✅ confirm, then hand to Ali

Same story: 675 real catalogued events already live behind `/api/v1/events` and
`/api/v1/events/{event_id}`. This needs a search UI, not new data.

- [ ] Confirm the event detail endpoint returns enough fields for a search result card
      (date, wettest catchment, intensity) without Ali having to make a second call per
      row.
- [ ] Flag to Ali if pagination matters — 675 rows is fine to ship whole, but say so
      explicitly rather than let the frontend guess.

---

## 3 · Seasonal Risk Calendar (feature K) — ✅ write the bucketing script

- [ ] Write the month-bucketing script over `events.parquet` — group the 675 events by
      calendar month, report count and max intensity per month. This is new code, but it's
      a script over data you already have, not a new pipeline.
- [ ] Decide once, in writing: does "risk" here mean rainfall intensity (yours) or
      exposure score (Pulga's, and currently capped at "minimal" per the audit — see
      [`00-phase4-plan.md`](00-phase4-plan.md))? If it's exposure, the calendar will look
      flat everywhere except October, because that's the only month with a real anchor.
      Say which one you're building before Ali starts on the calendar UI.

---

## 4 · The Confidence Meter's exceedance threshold (feature 5) — 🟡 this is the real gap

The audit flagged this precisely: a real 30-member GEFS ensemble exists (Nizar's), but
what it's compared *against* — the exceedance threshold that turns ensemble spread into
"confidence" — may still be a placeholder rather than your real per-catchment
climatology.

- [ ] Check `catchment_rainfall_climatology.parquet` (5 rows, all catchments, real) —
      confirm it's actually the value the confidence calculation reads, not a hardcoded
      constant sitting next to it in the code.
- [ ] If it's a placeholder, wire the real climatology in. If it's already correct,
      say so in writing so this stops being flagged 🟡 — an honest "already fixed" is as
      valuable as a fix.
- [ ] Coordinate directly with Nizar — he owns the ensemble-spread half of this number,
      you own the threshold half. Neither of you can ship this alone.

---

## 5 · Dive Site Safety Status (feature B) — ✅ your data, needs a join

`scripts/13_frontend_basemap.py` already derives `places.geojson` with dive sites,
`name_ar`/`name_en` populated — this was the artifact that beat Pulga's parallel exporter
in Phase 3 precisely because it was bilingual and already correct. That data is real and
committed.

- [ ] Confirm the dive-site POIs in `places.geojson` carry stable IDs a reef-zone join can
      key on.
- [ ] The actual join — nearest reef zone, pull its live exposure score — is Pulga's to
      write (it needs server-side exposure data). Hand him the confirmed POI shape rather
      than let him reverse-engineer it from the geojson.

---

## 6 · Integration check — the pattern you already own

Every phase so far has had a seam bug that produced plausible output with no error. Before
calling any ✅ row in the plan actually done:

- [ ] Re-run your Phase 3 check: events, feature rows and reef zones in whatever the
      current serving layer is (API or DB) must match the parquet/gpkg exactly. If Nizar's
      persistence layer picked up new rows this phase, re-verify zero orphans.
- [ ] Watch specifically for the ranking-column question in item 1 and the
      exposure-vs-rainfall question in item 3 — both are exactly the kind of "two people
      building against two different definitions of the same word" seam that's bitten this
      project three times already (`sediment_class`, `position_confidence`,
      `predicted_runoff_m3`).

---

## Definition of done

1. Rain Intensity Ranking columns confirmed live in the API response, canonical column
   named.
2. Historical Event Search's data shape confirmed sufficient for Ali's search UI.
3. Seasonal Risk Calendar bucketing script written, "rainfall vs exposure" decided and
   stated.
4. Confidence Meter's threshold confirmed real or fixed — not a placeholder.
5. Dive-site POI shape confirmed stable and handed to Pulga for the join.
6. Integration check re-run, zero orphans, ranking/exposure definitions written down.

## What you depend on

| From | What | Blocked? |
|---|---|---|
| **Nizar** | GEFS ensemble spread for the confidence meter | Partial — your threshold half doesn't need him to start |
| **Pulga** | the reef-zone join for dive sites, the ranking columns in the API | No — hand him your confirmed shapes, don't wait |
