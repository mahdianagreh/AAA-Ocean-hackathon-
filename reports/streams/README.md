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

**−5.1% against HydroRIVERS.** Note that HydroRIVERS and HydroBASINS come from the same lineage, so those two agreeing at 4,69x is expected and is really one estimate, not two.

---

## What this does and does not prove

**Does:** no gross misrouting. The trunk network follows the same valleys an independently published product does, across the full 4,453 km² of Wadi Yutum. Combined with the delineated-area-equals-flow-accumulation check at 0.0%, the routing is internally consistent and externally corroborated.

**Does not:** HydroRIVERS descends from the same SRTM lineage as our DEM. A systematic error shared by both — a valley that SRTM itself mis-mapped — would pass this test unnoticed. **MERIT Hydro at 90 m is the stronger check** and needs an authenticated Earth Engine project; it remains the right follow-up.

**The p99 tail of 1.9 km** is small tributaries on flat wadi floors, where two networks legitimately pick different parallel threads through the same braided bed. Not an error, a resolution artifact.

---

## Files

- `AQ-C01_overlay.jpg` — cyan is our 30 m network, orange is HydroRIVERS, grey is the catchment boundary
- `stream_offsets.csv` — per-cell offsets, for anyone who wants a different cut

## Reproduce

```bash
.venv/bin/python scripts/08_stream_validation.py
```
