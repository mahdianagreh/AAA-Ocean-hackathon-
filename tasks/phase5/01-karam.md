# Karam — Integration Lead & Rainfall/Reanalysis Pipeline

**Phase 5 · Workstream 1**
Read [`00-phase5-plan.md`](00-phase5-plan.md) first.

---

## Why this phase matters

Phase 2 closed the big structural risks in your stream — the AOI correction, the
675-event catalogue, the real per-catchment GEFS threshold. What's left is five
specific, checkable items, and one of them (the dependency manifest) is a five-minute
fix, not a research task. This phase is entirely about closing them properly — there's
no new feature on your list this time, so there's no reason any of these five slip.

---

## 0 · Close your Phase 2 items — Day 0/1

Verified against the real repo on 7 Aug — not re-derived from memory.

- [x] **A1.1 — Rainfall re-pulled over corrected `TERRAIN_AOI`; Oct-2016 ordering
      anomaly resolved.** Confirmed: `docs/event_dates.md` documents the resolution,
      backed by `data/processed/events/ordering_anomaly_analysis.json`
      (`"resolved": true`). Per-catchment numbers match exactly.
      **The scan-window edge case is now actually fixed, not just logged** —
      re-checking it surfaced a second, larger problem: the cell-level
      wettest-window table (1h/3h/6h/24h) had never been re-pulled over the
      corrected AOI at all — only the catchment-aggregated numbers had. Extended
      the scan window to `2016-10-30T00:00:00Z`, re-ran
      `scripts/process_imerg_oct2016_event.py` (240 granules, 100% complete,
      validated), and both problems resolved at once: new values are
      1h 9.645mm / 3h 15.415mm / 6h 18.425mm / 24h 23.090mm, none at a window
      edge. Also fixed a stale `EXPECTED_GRID=(5,4)` self-check constant in that
      script left over from before the AOI correction (should have been
      `(13,13)` all along — nobody had re-run the script end-to-end since the
      correction to notice). Full before/after and why in `docs/event_dates.md`.
- [x] **A1.2 — `event_catchment_features.parquet` is a real, complete joined
      matrix.** Confirmed: (500, 139), 100 events × 5 catchments, 1998–2022.
      **Found the real reason for the null columns, not just the symptom**:
      `rain_1h/3h/6h/24h_mm` were clearly meant to be joined from
      `daily_intensity.parquet`'s `peak_1h/3h/6h_mm` (real, non-null, 11,810
      rows) — that join was simply never built, and the same null pattern
      appears in `catchment_rainfall_daily.parquet` too. Documented in
      `docs/data_dictionary.md` §1b rather than dropped — dropping would erase
      the record that a real, buildable join is what's actually missing.
- [x] **A1.3 — the daily 2000→2026 IMERG sweep.** Confirmed
      `catchment_rainfall_daily.parquet` **is** the real daily series — 50,675
      rows = 10,135 days × 5 catchments, 1998-01-01 to 2025-09-30, every row
      `quality_flag: GOOD` / `source_geometry_status: REAL`, matching the
      climatology summary's `n_days` exactly. No separate, more complete daily
      artefact exists anywhere else. Documented in full in
      `docs/data_dictionary.md` §1b, including the column list.
- [x] **A1.4 — dependency manifest.** Went with the documentation route (either
      was fine per this file). Added a paragraph to `CLAUDE.md` under Commands
      explaining the per-service split is intentional (api image stays small
      and fast to rebuild; worker carries the heavier geospatial stack) and
      giving the two-file local-install command.
- [ ] **A1.5 — the repo-ownership/continuity conversation.** Not something I can
      close myself — asked Karam whether it's happened yet.

---

## Definition of done

1. A1.1's scan-window edge case is fixed, not just logged — done, see above.
2. A1.2's four all-null columns are documented, not removed — done.
3. A1.3 says, in `docs/data_dictionary.md`, exactly what climatology artifact exists
   today — done, confirmed it's the real daily series.
4. A1.4 — a dependency manifest question has an explicit answer, not silence — done.
5. A1.5 — the ownership conversation has happened and is logged, or is explicitly
   scheduled with a date. **Still open, waiting on Karam.**
