# Karam — Integration Lead & Rainfall/Reanalysis Pipeline

**Phase 5 · Workstream 1**
**Feeds:** Mahdi (B3), Pulga (B4)
Read [`00-phase5-plan.md`](00-phase5-plan.md) first.

---

## Why this phase matters

Phase 2 closed the big structural risks in your stream — the AOI correction, the
675-event catalogue, the real per-catchment GEFS threshold. What's left is five
specific, checkable items, and one of them (the dependency manifest) is a five-minute
fix, not a research task. Close those first; your Part B role is support on two other
people's features, not a feature of your own to carry solo this phase.

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
      not opened during verification), point B4's site-scoring agent (below) and
      B6's anomaly detector (Nizar's file) at it directly and say so in
      `docs/data_dictionary.md`. If it doesn't exist, say that instead — "missing is
      never zero" applies to documentation claims too.
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

## Your role in B3 · Cross-Site Transfer Learning (primary: Mahdi, [`02-mahdi.md`](02-mahdi.md))

Mahdi owns the fine-tuning pipeline itself. What he needs from you is the same thing
Phase 1's contract already gave every other stream: a **reusable ingestion path for a
new site's rainfall/reanalysis data**, shaped exactly like Aqaba's, so his transfer
script doesn't special-case its input format per site.

- [ ] Generalize your IMERG/ERA5-Land ingestion scripts to accept a bounding box and
      site identifier as parameters instead of the hardcoded Aqaba AOI import — same
      "ask the box, never retype the literal" discipline `backend/src/config/spatial.py`
      already enforces, extended to a second site.
- [ ] Confirm the output schema for a new site's rainfall features matches
      `event_catchment_features.parquet`'s column set exactly, so Mahdi's fine-tuning
      script needs zero column-mapping code.
- [ ] Hand Mahdi one real or realistic second-site bounding box to test against before
      freeze — a transfer-learning pipeline nobody has run once is not a shipped
      feature.

**Limitation to state, not hide:** a site with zero validated local events has no way
to check whether the fine-tuned model is any good — this is exactly what B3's
"model maturity" badge (Mahdi's dashboard spec) exists to say honestly on screen,
never smoothed over.

---

## Your role in B4 · Automated Site-Scoring Agent (primary: Pulga, [`04-pulga.md`](04-pulga.md))

Pulga's agent scores a candidate coastline against the six-criterion rubric
(`docs/Ali/research/01-signature.md` C1–C6), grounding every score in a retrieved
fact. Several of those criteria are climate/rainfall facts — your domain.

- [ ] Confirm which of C1–C6 are rainfall/climate-derived (likely: storm frequency,
      rainfall intensity percentile, antecedent wetness patterns) and provide a
      retrievable, cited data source for each — the same `catchment_rainfall_climatology`-
      style aggregate, generalized to an arbitrary bounding box per B3's ingestion work
      above, so B4 and B3 share one generalized pipeline rather than two.
- [ ] Every number the agent cites for these criteria must be traceable to a real
      file/row, per Standing Law rule 10 — hand Pulga the exact provenance string
      format your other pipelines already use (`docs/data_dictionary.md`'s product
      ID/version/access-date convention), so the agent's citations look like every
      other provenance string in this project, not a new invented format.

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
6. B3's generalized rainfall-ingestion pipeline is handed to Mahdi with one real test
   bounding box.
7. B4's climate-criteria data sources are handed to Pulga with real provenance strings.

---

## Handoffs

| Teammate | What they get | When |
|---|---|---|
| **Mahdi** | Generalized rainfall/reanalysis ingestion pipeline (bbox + site_id parameterized), one test bounding box | Day 3 |
| **Pulga** | Climate-criteria data sources + provenance-string format for the site-scoring agent | Day 3 |
| **Nizar** | Pointer to whichever climatology artifact is confirmed real (A1.3), for his B6 anomaly detector | Day 2 |

## What you depend on

| From | What | Blocked? |
|---|---|---|
| — | Nothing here blocks starting immediately — A1's items are all your own files, and B3/B4's support role starts once you generalize your own ingestion, not once someone else delivers something | No |
| **Pulga** | Confirmation of which climate-criteria sources actually got wired into B4 | No — informational close-of-loop, not a blocker (Day 3) |
