# Nizar — Supabase, Forecasts, Currents, and Live Anomaly Detection

**Phase 5 · Workstream 3**
Read [`00-phase5-plan.md`](00-phase5-plan.md) first.

---

## Why this phase matters

Your Part A items are in the best shape of anyone's — two of three are fully closed
with live evidence, and the third is a real, already-solved capability that just
can't be re-exercised in this container today. That leaves real room this phase for
your one owned Part B feature, which is explicitly framed by its own spec as
infrastructure, not a polished demo piece — build it honestly as exactly that.

---

## 0 · Close your Phase 2 items — Day 0/1

- [x] **A4.1 — GEFS exceedance vs. real per-catchment p99.** Confirmed live:
      `backend/src/db/loaders/forecast_pipeline.py` computes exceedance against
      `catchment_rainfall_climatology`'s real p99 per catchment, and
      `data/processed/forecasts/latest_snapshot.json` shows three different real
      threshold values (`AQ-C01: 2.9613`, `AQ-C02: 2.3467`, `AQ-C03: 2.3243`) — not
      the old flat 15mm placeholder. No action needed.
- [x] **A4.2 — Copernicus Marine vs. HYCOM comparison.** **Closed, 2026-08-07 — the
      "missing `.nc` files" premise above was stale, not current.** Live-verified
      against `docker compose up --build api`: all four cache files
      (`hycom_aoi_recent.nc`, `copernicus_marine_aoi_recent.nc`,
      `hycom_aoi_AQ-2016-10-28.nc`, `copernicus_marine_aoi_AQ-2016-10-28.nc`) are
      present in `data/raw/currents/`, dated 3 Aug, and the container sees them via
      `docker-compose.yml`'s bind mount. `GET /api/v1/currents/agreement` returns the
      real, matching **65.82° disagreement** with defaults, no re-fetch needed.
      Proved genuine cache-dependence (not a silent network fallback) by moving the
      `.nc` files aside and re-hitting the endpoint — it failed cleanly with "No
      cached current data," then succeeded again once restored. No re-fetch was
      needed; no `docs/data_dictionary.md` correction needed either — it already
      distinguishes the "today" vs. historical/backtest numbers correctly (§8, Phase 2
      update, 2026-08-03).
      - **Bonus finding for Abd (his `05-abd.md` A5.1):** his file's premise that
        `hycom_aoi_AQ-2016-10-28.nc` is "absent from the container" was the same stale
        claim — live-checked `POST /api/v1/plume/simulate` and it already reports real
        HYCOM forcing (`currents: HYCOM GLBu0.08/expt_91.2 historical archive, cached
        data/raw/currents/hycom_aoi_AQ-2016-10-28.nc`), not the zero-current
        placeholder. The currents half of his open checkbox is already resolved.
      - **Wind is a separate, genuinely permanent gap**, not a caching issue: no
        historical marine wind source exists in this repo at all (GFS/GEFS/ECMWF are
        forecast-only; ERA5-Land ingests `u10`/`v10` but is land-only, so it wouldn't
        cover marine cells even if cached, and no ERA5-Land raw cache exists on this
        machine anyway). Documented permanently in `docs/forcing_limitations.md`'s new
        "Wind forcing" section rather than left as an API-only caveat string.
- [x] **A4.3 — frozen "today" offline snapshot seeded.** Confirmed:
      `scripts/build_forecast_snapshot.py` → `data/processed/forecasts/latest_snapshot.json`,
      real GEFS/GFS metadata, confirmed live via `GET /api/v1/forecast/latest`. No
      action needed.

---

## 1 · B6 — Live Anomaly Detection on Forecast Streams

**Model & data**

- [x] **Closed, 2026-08-07.** Built a **percentile-relative anomaly score**, not a
      textbook z-score: `catchment_rainfall_climatology` only delivers percentiles
      (p50/p90/p95/p99/p99_9), not a mean/std or the raw daily series, and
      fabricating one would violate "nothing is interpolated." `is_anomalous =
      rain_mm > p99`, `anomaly_score` is a continuous position past p50 (same
      continuous-not-cutoff shape as the confidence/currents-agreement formulas) —
      explainable in one sentence: "today's forecast exceeds the 99th percentile of
      N years of historical rainfall for this catchment." Pure function:
      `backend/src/processing/anomaly_detection.py`, 5 unit tests
      (`tests/test_anomaly_detection.py`), all passing.
- [x] Reads `catchment_rainfall_climatology` directly (via the Postgres table, same
      one Karam's loader populates) as the "what's normal" baseline — no second,
      independently-derived climatology built.

**Backend & storage**

- [x] New `forecast_anomalies` table
      (`supabase/migrations/20260807120000_forecast_anomalies.sql`, applied to
      Supabase), zero collisions confirmed against `tasks/00-contracts.md`. Wired
      into `backend/src/db/loaders/forecast_pipeline.py` right after the existing
      exceedance block — same manual-run cadence as everything else in this repo (no
      scheduler exists anywhere; "populated on every scheduled ingestion run" means
      "populated whenever this script runs," consistent with `forecast_exceedance`).
      Exposed via `GET /api/v1/forecast/latest`'s new `anomalies` + `anomaly_caveat`
      fields (`scripts/build_forecast_snapshot.py` now also freezes this into the
      offline snapshot, same "wifi off" discipline as everything else the endpoint
      serves); confirmed live against the old cached snapshot (empty `anomalies: []`,
      `anomaly_caveat` present, no crash).
- ⚠️ **Not yet live-verified with a real, non-empty row — infrastructure blocker,
      not a code gap, 2026-08-07.** The unit tests (5, all passing,
      `tests/test_anomaly_detection.py`) prove the scoring logic; the loader/schema/
      API wiring is code-complete and reviewed. What's missing is a real end-to-end
      run: `forecast_pipeline.py` needs a fresh GFS/GEFS fetch (repeatedly hit
      AWS byte-range GEFS grib downloads coming back truncated — fixed with a
      skip-and-continue handler, see the loader's docstring) *and* a live Postgres
      write via the Supabase pooler, and the **pooler itself became unresponsive**
      partway through this session — TCP connects instantly
      (`nc -zv aws-1-ap-northeast-2.pooler.supabase.com 6543` succeeds) but the
      Postgres protocol handshake never completes, for `psql` too, not just this
      loader. Most likely cause: several `kill -9`'d attempts earlier in this
      session (needed to escape the corrupted-grib retries before the fix landed)
      left orphaned sessions the pooler hadn't reaped. Waited ~3 min and retried
      once — still hung. **Recommend someone check the Supabase project's
      connection-pool count on the dashboard**; the code itself needs nothing
      further once a connection goes through.

**Dashboard sub-features (for Ali to build)**

- A distinct-colored "unusual pattern detected" banner, visually separate from the
  formal risk bands, above the normal risk card.
- A rolling sparkline of the live forecast stream with anomalous points marked.
- The one design rule worth writing down here, since it's easy to get wrong by
  accident: **"early signal, formal threshold not yet crossed" is a different
  statement from "72% of ensemble members agree," and the UI must never conflate the
  two** — put this directly in this feature's own copy/spec, not just in conversation.

**Limitation to state on the same screen this ships on:** a z-score/isolation-forest
flag against ~27 years of climatology is a statistical outlier signal, not a
validated early-warning system — it has never been checked against a real flood
event's lead time. Say this plainly; "anomaly detected" reads as more authoritative
than it is if left unqualified.

---

## Definition of done

1. A4.2 — either the comparison is confirmed re-runnable with fresh `.nc` files, or
   `docs/data_dictionary.md` is corrected to call it a static 3 Aug exhibit.
2. B6 — `forecast_anomalies` populated on a real scheduled run, banner/sparkline
   wired, and the confidence-meter framing rule stated in the feature's own written
   spec.
