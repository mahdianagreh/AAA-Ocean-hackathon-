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
      **One narrower thing is still genuinely open**, not closed: the 6h/24h maxima
      abut the scan-window's edge. Extend the scan window and re-check those two
      specific figures before quoting them anywhere final.
- [x] **A1.2 — `event_catchment_features.parquet` is a real, complete joined
      matrix.** Confirmed: (500, 139), 100 events × 5 catchments, 1998–2022.
      **Real, undocumented gap found**: `rain_1h_mm`, `rain_3h_mm`, `rain_6h_mm`,
      `rain_24h_mm` are 100% null across all 500 rows. Either document why (superseded
      by the `precipitation_*` columns?) or drop them — a 100%-null column with no
      explanation is exactly the kind of thing a judge's question finds first.
- [ ] **A1.3 — the daily 2000→2026 IMERG sweep.** What exists,
      `catchment_rainfall_climatology.parquet`, is real but is a **5-row per-catchment
      percentile summary** (`n_days=10135` each), not a daily series. If a daily series
      genuinely exists elsewhere (`catchment_rainfall_daily.parquet` was located but
      not opened during verification), document exactly what it is and where it lives
      in `docs/data_dictionary.md`. If it doesn't exist, say that instead — "missing is
      never zero" applies to documentation claims too. Anyone building against
      climatology data this phase can then read the doc directly, rather than needing
      to ask.
- [ ] **A1.4 — dependency manifest.** No manifest exists at the repo root; real ones
      exist per-service (`backend/requirements-api.txt`, `backend/requirements-worker.txt`,
      `frontend/package.json`). Either add a thin root-level `pyproject.toml` that
      points at the two backend requirement files (so `pip install -e .` from the
      root works for a new contributor), or add one paragraph to the top-level
      `README`/`CLAUDE.md` explaining the per-service split is intentional. Either
      is fine — silence on the question is not.
- [ ] **A1.5 — the repo-ownership/continuity conversation.** This can't be verified
      from a file, which is itself the finding: if it hasn't happened, it's still the
      single highest-probability reason this doesn't continue past the hackathon, and
      it costs nothing to fix. Have it this week, and drop one line in
      `docs/OPEN-ISSUES.md` recording that it happened and what was decided.

---

## Definition of done

1. A1.1's remaining scan-window edge case is either fixed or explicitly logged as a
   known residual limitation in `docs/event_dates.md`.
2. A1.2's four all-null columns are documented or removed.
3. A1.3 says, in `docs/data_dictionary.md`, exactly what climatology artifact exists
   today and what (if anything) is still missing — no ambiguity left standing.
4. A1.4 — a dependency manifest question has an explicit answer, not silence.
5. A1.5 — the ownership conversation has happened and is logged, or is explicitly
   scheduled with a date.
