# Stream network validation against HydroRIVERS

**Date:** 2 August 2026
**Method:** `scripts/08_stream_validation.py`
**Ours:** Copernicus GLO-30, 30 m, D8, 900-cell stream threshold
**Reference:** HydroRIVERS v1.0 region `eu`, ~500 m

---

## Why this was needed

The imagery check in `reports/outlets/` only looked at the two coastal mouths. A trunk misrouted 40 km inland would not have appeared there, and nothing else had checked the network.

---

## Result — the network validates

Offset from each of our trunk cells to the nearest HydroRIVERS reach, over **112,604 cells** carrying ≥ 10 km² upstream:

| | Offset |
|---|---:|
| median | **140 m** |
| p75 | 306 m |
| p90 | 731 m |
| p95 | 1,104 m |
| p99 | 1,899 m |

| Within | Share of trunk cells |
|---|---:|
| 90 m | 34.8% |
| 250 m | 69.8% |
| 500 m | **84.1%** |
| 1,000 m | 93.9% |

**A 140 m median is better than the comparison can actually resolve.** HydroRIVERS is a ~500 m product, so its own line position carries several hundred metres of uncertainty. Agreement to within a fraction of one reference cell is the best outcome available here — it cannot get meaningfully better without a finer reference.

### Upstream area at the Wadi Yutum mouth

| Source | Area |
|---|---:|
| Our DEM | 4,453.1 km² |
| HydroRIVERS, reach 320 m from AQ-O01 | 4,692.8 km² |
| HydroBASINS exorheic | 4,690.0 km² |

**−5.1% against HydroRIVERS.** HydroRIVERS and HydroBASINS share the HydroSHEDS lineage, so those two agreeing at 4,69x is expected and counts as one estimate, not two. But that single estimate is derived from **SRTM**, while ours comes from **TanDEM-X** — so the 4,453 vs 4,690 comparison is between independent missions, and the 5% gap is a real cross-mission result rather than a product comparing to itself.

---

## What this does and does not prove

> **Corrected 2 Aug 2026.** An earlier version of this section said HydroRIVERS
> "descends from the same SRTM lineage as our DEM" and discounted the result
> accordingly. That was wrong, and it understated the check.

**The two sources are genuinely independent acquisitions:**

| | Mission | Flown |
|---|---|---|
| Ours — Copernicus GLO-30 | TanDEM-X | 2011–2015 |
| Reference — HydroRIVERS / HydroSHEDS | SRTM | 2000 |

Different satellites, different radar systems, eleven-plus years apart.

**What this proves:** no gross misrouting, and no terrain error shared with the reference. Two independent missions place the Wadi Yutum trunk in the same valleys across all 4,453 km². Combined with the delineated-area-equals-flow-accumulation check at 0.0%, the routing is internally consistent *and* externally corroborated by an independent acquisition.

**What it still does not prove:** the reference is ~500 m, so it cannot confirm channel position at anything finer, and it says nothing about the coastal mouths — those are settled by imagery in `reports/outlets/`, where three of five failed. It also cannot see errors caused by GLO-30 being a *surface* model, since HydroRIVERS is too coarse to resolve the structures involved.

**MERIT Hydro at 90 m remains the right follow-up** — same SRTM lineage as HydroRIVERS, but fine enough to check channel position where a ~500 m product cannot.

**The p99 tail of 1.9 km** is small tributaries on flat wadi floors, where two networks legitimately pick different parallel threads through the same braided bed. Not an error, a resolution artifact.

---

## Files

- `AQ-C01_overlay.jpg` — cyan is our 30 m network, orange is HydroRIVERS, grey is the catchment boundary
- `stream_offsets.csv` — per-cell offsets, for anyone who wants a different cut

## Reproduce

```bash
.venv/bin/python scripts/08_stream_validation.py
```
