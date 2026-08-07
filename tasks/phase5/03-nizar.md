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
- [ ] **A4.2 — Copernicus Marine vs. HYCOM comparison.** `compare_hycom_vs_copernicus()`
      is real and already produced real output (65.8° current-direction disagreement
      at the mooring's peak-response time, `docs/qa_screenshots/currents_01_hycom_vs_copernicus.png`)
      — this is genuinely done work, not a stub. **What's actually missing right
      now:** the `.nc` cache files it needs (`hycom_aoi_*.nc`,
      `copernicus_marine_aoi_*.nc`) are absent from `data/raw/currents/` on disk and
      inside the running container. Re-fetch them and confirm the comparison is
      re-runnable, not just documented from a past run. If re-fetching isn't feasible
      this phase, say explicitly in `docs/data_dictionary.md` that this is a static
      exhibit from 3 Aug, not a live capability — the current phrasing risks implying
      otherwise.
- [x] **A4.3 — frozen "today" offline snapshot seeded.** Confirmed:
      `scripts/build_forecast_snapshot.py` → `data/processed/forecasts/latest_snapshot.json`,
      real GEFS/GFS metadata, confirmed live via `GET /api/v1/forecast/latest`. No
      action needed.

---

## 1 · B6 — Live Anomaly Detection on Forecast Streams

**Model & data**

- [ ] Lightweight anomaly detector — isolation forest, or a simple statistical
      z-score against catchment climatology (start with the z-score; it's
      explainable in one sentence to a judge, which an isolation forest score is
      not). Running on the live GFS/GEFS/ERA5-Land ingestion stream.
- [ ] Read `catchment_rainfall_climatology.parquet` directly as the "what's normal"
      baseline — it's the one real climatology artifact this project already has;
      don't compute a second, independently-derived one just for this feature.

**Backend & storage**

- [ ] New `forecast_anomalies` table, populated on every scheduled ingestion run.
      This is a new artifact — confirm the name doesn't collide with anything in
      `tasks/00-contracts.md` (it doesn't; it's new).

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
