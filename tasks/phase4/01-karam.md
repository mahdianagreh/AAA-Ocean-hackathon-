# Karam — Phase 4

> **Update, 6 Aug — this file's own premise was wrong on one point, corrected below,
> plus items 1/2/3/4/5 done.**
>
> **The plume is not still a stub.** Abd's `05-abd.md` and the plan's "one fact" are
> stale — they audited a branch that hadn't merged `0de8c26` (the real particle-engine
> wiring) yet. Live-checked just now: `is_stub: false`,
> `model_version: custom_2d-calibrated-AQ-2016-10-28`. Tell Abd and whoever ran the
> audit before the team schedules around a blocker that's already closed.
>
> **What actually landed, this file's items:**
> - **1/2 — `/api/v1/events` served 5 markdown-parsed events with no ranking columns
>   at all, not the 675-event catalogue "already live" this file claimed.** Fixed:
>   `da.event_catalogue()` reads `events.parquet` directly; `/events` and
>   `/events/{id}` now serve all 675, sorted by `rank`, each optionally carrying its
>   literature label on top. **Canonical ranking is `rank`/`max_daily_mm`** — real,
>   complete (675/675, `is_exhaustive: true`), daily-total by construction (its one
>   documented limitation). **`max_anomaly_ratio` is NOT the ranking column** — ranks
>   storms differently, exposed for reference only. Tell Ali this before he builds
>   the leaderboard.
>   **`events_by_intensity.parquet` is stale, not curated** — built against an old
>   100-event catalogue, and its 83/100 split is just which events had ≥130
>   downloaded half-hourly granules locally, not a "most intense" or literature
>   filter. Don't expose it. Re-run `scripts/rank_events_by_intensity.py` against the
>   real 675-event catalogue once the in-progress half-hourly IMERG sweep finishes —
>   a follow-up, not a Phase 4 blocker.
> - **3 — `scripts/29_seasonal_risk_calendar.py`** written, bucketing all 675 events
>   by month → `data/processed/features/seasonal_risk_calendar.parquet`. **Framing:
>   rainfall intensity, not exposure** — exposure is anchored to one October event and
>   would read flat everywhere else. Tell Ali this before the calendar UI starts.
> - **4 — `confidence_adjustment = 0.6` was a literal constant, confirmed via the
>   audit, now fixed.** `exposure_calculate()` derives it from the real cached GEFS
>   exceedance snapshot (`da.gefs_exceedance_for()`): `agreement = |exceedance_prob −
>   0.5| × 2`, times the existing coarse-currents/bathymetry penalty. **The agreement
>   formula is a proposal, not settled — confirm with Nizar**, per his file; he owns
>   whether "confidence" should mean ensemble agreement at all. Components
>   (`confidence_members_exceeding/_total/_threshold_value_mm`) are now on
>   `formula_terms`, not just a sentence.
> - **5 — dive-site POIs in `places.geojson` had zero stable ID** (`drop_id=True` in
>   `scripts/frontend_basemap.py`, source had a real `osm_id` that was just being
>   dropped). Fixed: `osm_id` now survives into the output, 115/115 unique. Regenerated
>   live, diffed against the previous file — only the ID field changed, nothing else.
>   Also fixed two pre-existing crashes in `bilingual()`/`parse_other_tags()` (NaN-is-
>   truthy bug) that blocked re-running the export at all. **Pulga: `osm_id` is the
>   join key for the nearest-reef-zone join.**
>
> Five files changed on `main`: `backend/src/api/{main,data_access,schemas}.py`,
> `scripts/frontend_basemap.py`, new `scripts/29_seasonal_risk_calendar.py`. All
> 527 tests green, live-verified against the running container, not just typechecked.

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

- [x] Confirm `/api/v1/events` actually returns the ranking columns — it didn't at all
      (5-event markdown list, no ranking fields). Fixed: `EventOut` extended,
      `da.event_catalogue()` added, `/events` now serves all 675 sorted by `rank`.
- [x] Not a Pulga ask after all — the endpoint change was small enough to do directly.
- [x] Told Ali (see update note above): `rank`/`max_daily_mm` is the canonical ranking,
      not `max_anomaly_ratio`, and why.

---

## 2 · Historical Event Search (feature G) — ✅ confirm, then hand to Ali

Same story: 675 real catalogued events already live behind `/api/v1/events` and
`/api/v1/events/{event_id}`. This needs a search UI, not new data.

- [x] `/events/{event_id}` now returns date, wettest catchment, rank, intensity columns
      and the literature label in one call — confirmed live.
- [x] No pagination — 675 rows shipped whole, as planned. Told Ali.

---

## 3 · Seasonal Risk Calendar (feature K) — ✅ write the bucketing script

- [x] `scripts/29_seasonal_risk_calendar.py` written and run —
      `data/processed/features/seasonal_risk_calendar.parquet`, count + peak/mean
      `max_daily_mm` per calendar month.
- [x] Decided and stated: **rainfall intensity, not exposure.** Exposure is anchored
      to one October event and would read flat everywhere else — see the script's own
      docstring for the full reasoning. Told Ali before he starts the calendar UI.

---

## 4 · The Confidence Meter's exceedance threshold (feature 5) — 🟡 this is the real gap

The audit flagged this precisely: a real 30-member GEFS ensemble exists (Nizar's), but
what it's compared *against* — the exceedance threshold that turns ensemble spread into
"confidence" — may still be a placeholder rather than your real per-catchment
climatology.

- [x] Checked — it WAS a hardcoded `0.6` literal, confidence engine never read the
      climatology at all. Fixed: `exposure_calculate()` now derives
      `confidence_adjustment` from `da.gefs_exceedance_for(cid)`, which is already
      built from the real climatology via `forecast_pipeline.py`.
- [x] Wired: `agreement = |exceedance_prob − 0.5| × 2`, × the existing
      currents/bathymetry penalty. **Not settled — this exact mapping needs your
      confirmation, Nizar**, per the "neither of you can ship this alone" rule. If you
      want a different definition of "confidence," the accessor
      (`da.gefs_exceedance_for`) and the call site (`main.py`, `exposure_calculate()`)
      are both small and easy to change.

---

## 5 · Dive Site Safety Status (feature B) — ✅ your data, needs a join

`scripts/13_frontend_basemap.py` already derives `places.geojson` with dive sites,
`name_ar`/`name_en` populated — this was the artifact that beat Pulga's parallel exporter
in Phase 3 precisely because it was bilingual and already correct. That data is real and
committed.

- [x] Confirmed — they had NO stable ID at all (`drop_id=True` in
      `scripts/frontend_basemap.py`, the real filename). Fixed: the source OSM layer's
      own `osm_id` now survives into `places.geojson`, 115/115 unique, diffed against
      the previous file to confirm nothing else changed.
- [ ] The actual join is still Pulga's (needs server-side exposure data). **Pulga: the
      confirmed key is `osm_id` on every places.geojson feature.**

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
