# Pulga — Tasks Tracker

**Last updated:** 2026-08-03, after merging `origin/main` (Karam's ACA swap-in)

- Reproduce from zero: [docs/README_pulga.md](../../docs/README_pulga.md)
- Provenance & limitations: [docs/data_dictionary.md](../../docs/data_dictionary.md)
- Model card: [docs/model_card.md](../../docs/model_card.md)
- QA figures: [docs/qa_screenshots/MANIFEST.md](../../docs/qa_screenshots/MANIFEST.md)
- Judge-facing: [docs/pitch_limitations.md](../../docs/pitch_limitations.md)
- **Karam's handoff:** [docs/HANDOFF_pulga_2026-08-03.md](../../docs/HANDOFF_pulga_2026-08-03.md)

> **All 12 Definition-of-Done items closed.** Earth Engine works, the real Allen Coral
> Atlas zones are in, and the whole repo suite is **419 passed, 0 failed**.

---

## §9 Definition of Done — 12 / 12

| # | Item | Status |
|---|---|---|
| 1 | `check_aoi_coverage.py` run, gap report saved | **done** — `docs/aoi_coverage_report_20260802.txt`, annotated |
| 2 | WorldCover v2 mosaic (2 tiles), seam-checked, screenshotted | **done** — seam discontinuity 0.01 pp |
| 3 | SoilGrids + OSM re-pulled against `TERRAIN_AOI` | **done** — SoilGrids 526×481, OSM 8,289 roads |
| 4 | 3 feature tables on real catchments, fixture deleted, areas cross-checked | **done** — all 5 within 0.1% of contract |
| 5 | Earth Engine authenticated and verified working | **done** — see the project-id note below |
| 6 | Real ACA zones, `verify_against_provisional()` passed, weight still placeholder | **done** — 8/8 IDs, 1.235 km², all 1.0 |
| 7 | FastAPI serving every §17 endpoint, typed, cached, caveats as data | **done** — 20 routes, all 12 §17 paths |
| 8 | Exposure engine, `formula_terms` stored, EPSG:32636 | **done** — 12 tests |
| 9 | `/explain` exact number-fidelity | **done** — 9 tests, EN + AR |
| 10 | `/ask` citation coverage, `docs/ali` excluded | **done** — 9 tests, 13/13 corpus files |
| 11 | `data_dictionary.md` — AOI re-pull **and** ACA export with versions and dates | **done** |
| 12 | Day-12 gate grep | **done** — 3 declared `_PROVISIONAL`, 0 `FIXTURE` |

---

## What the merge with Karam changed

He did the EE unblock and a full ACA swap while this branch was working on the same
thing. **His implementation was better and was taken wholesale.** He found four defects,
three of which this branch never spotted:

| # | defect | why it was invisible |
|---|---|---|
| 1 | Fragments assigned whole to their best-overlap zone | R-05 came out at 475 m² while 0.068 km² of its reef was credited to neighbours. This branch found this one independently. |
| 2 | `habitat_class` held the raw integer `ACA_benthic_13` | A text column that reaches the map popup, Postgres and RAG answers |
| 3 | Dominant class counted by **piece**, not area | 25 single-pixel rock specks outvoted the coral patch that *is* the zone |
| 4 | Geometry attributes inherited from the provisional file | `marine_park_overlap_pct` described a hand-drawn box, not reef |

His class tables are read off the live asset and re-verified every build — geomorphic 22
is *Reef Slope*, and the plausible guess (24, *Back Reef Slope*) would have mislabelled
five of eight zones with no error.

**Kept from this branch:** the FastAPI surface, exposure engine, `/explain`, `/ask` —
which his handoff lists as 5-of-14 and "not started".

---

## Reef areas changed 4.6× — anything computed before this is wrong

`5.69 km² → 1.235 km²`. The old figure was the area of hand-drawn 250 m boxes; the new
one is what the Atlas maps as habitat. The **per-zone ranking changed too**, not just the
totals.

| zone | km² | dominant habitat | in Marine Park | depth land-cell % |
|---|---:|---|---:|---:|
| R-01 | 0.463 | Coral/Algae | 0% | 39.2 |
| R-02 | 0.037 | Coral/Algae | 0% | **100.0** |
| R-03 | 0.011 | Coral/Algae | 0% | 0.0 |
| R-04 | 0.147 | Coral/Algae | 96.9% | 19.3 |
| R-05 | 0.069 | Coral/Algae | 100% | 0.0 |
| R-06 | 0.186 | Coral/Algae | 100% | 52.1 |
| R-07 | 0.127 | **Rock** | 92.4% | 74.5 |
| R-08 | 0.196 | **Rock** | 10.3% | 51.3 |

### Three caveat changes this forced

1. **The 250 m width caveat is obsolete and was removed** for real geometry. The outline
   is the Atlas's own 5 m polygons, so an absolute km² is defensible. Shipping the old
   caveat would have been a false statement about a 5 m product.
2. **`reef_shallow_only` replaces it** — a fraction of a zone is still the better framing,
   but because the Atlas maps optically shallow reef only, not because the width is a guess.
3. **`depth_is_land_dominated` added.** Depth is now the weakest field, not the geometry:
   the bathymetry is 50 m under a 20–50 m reef strip, so 39–100% of cells read as land.
   `R-02` is **null** — no water cell at all — and is never coerced to 0. Verified that
   R-02 and R-07 warn while R-05 (0% land) correctly does not.

---

## Regressions I introduced in the merge, and fixed

Taking "theirs" wholesale for data files reverted two things:

- **OSM went back to the old small box** — 3,845 roads, stopping at 29.7 N. Re-clipped
  to `TERRAIN_AOI`: 8,289 roads.
- **AQ-C01's road length was understated 6.4×** (387 km vs 2,482 km) because the urban
  table had been rebuilt from that small-box OSM. This is the §1 coverage bug reappearing
  in the feature table that feeds the runoff model, on the catchment that is 96% of the
  basin. Re-aggregated.
- **Three §6.1 figures became orphans** — the seam check, the AQ-C01 bare-ground plot and
  the provisional-vs-final centroid map existed on disk with no script able to regenerate
  them, because his `qa_land.py` has neither. Restored from history and adapted to his
  `tiles_for()` / `WORLDCOVER_DIR` API rather than duplicating helpers.

## Earth Engine project id — the handoff and reality disagree

Measured, not assumed:

```
reefshield-aqaba-504407   WORKS
reefshield-aqaba-504406   fails — "Caller does not have required permission"
reefshield-aqaba-504318   fails — same
```

`HANDOFF_pulga_2026-08-03.md` §5 names **-504406** as the one to use. On this machine it
is the one that fails. `export_aca.py project_id()` now falls back to the verified id
instead of exiting when no env var is set, and records the discrepancy in-code. **One of
the two records is wrong and someone should settle it.**

---

## Still open, not mine to close

- **`sensitivity_weight` is still 1.0** and still `PLACEHOLDER_PENDING_MARINE_SCIENTIST`.
  Contract swap #5. `habitat_class` and `marine_park_overlap_pct` are exactly the measured
  inputs a marine scientist needs — hand them over, do not convert them.
- **Credential rotation.** Karam's handoff §5 records that the Earthdata password, the CDS
  token and the Supabase superuser password have each been exposed in a chat transcript and
  are **not yet rotated**. Separately, `.env` was committed in `2f0a6d6` on
  `origin/pulga-branch`; gitignoring it does not remove it from history.
- **`reef_zones_PROVISIONAL.gpkg` stays on disk** — retained for the swap-in diff only.
  The Day-12 grep will match it; it is a *declared* placeholder, which §6.3 permits, but
  say so out loud rather than being surprised.
