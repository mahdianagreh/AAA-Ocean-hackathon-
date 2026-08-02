# Explicit endorheic masking

**Date:** 2 August 2026
**Method:** `scripts/10_endorheic_mask.py`
**Goal:** replace `fill=False` — a conditioning flag whose result moves with DEM noise — with an explicit, physically-motivated identification of closed basins.

---

## Why

`breach_depressions_least_cost(fill=False)` approximately preserves endorheic basins, but whether a depression survives depends on its depth against the DEM's noise floor. M2 showed how badly that bites:

| Wadi Yutum contributing area | `fill=False` | `fill=True` |
|---|---:|---:|
| Copernicus GLO-30 | 4,453 km² | 6,282 km² |
| NASA SRTM | 2,561 km² | 6,413 km² |

With `fill=True` the DEMs agree within 2% — the terrain is not in dispute. With `fill=False` they are 1.7× apart. So the flag, not the topography, was driving the headline number.

---

## Method

1. Fill depressions; take `filled − original` as depression depth.
2. Label connected depressions, keep those above an area **and** depth threshold.
3. **Selective conditioning** — use the filled surface everywhere *except* the kept basins, which are restored to original elevation. Flow now crosses DEM noise but still terminates inside real closed basins.
4. Walk the D8 network upstream from those basins.
5. Mask that area out; condition the remainder with `fill=True`, safe now that the real sinks are gone.

**Step 3 is the whole trick.** The first attempt filled everything and traced from sink points, which returned 0.5 km² — the fill had destroyed the sinks, so nothing drained into them.

---

## What the sinks look like (GLO-30)

Per-sink upstream area is the diagnostic that separates a playa from a blocked channel:

| Sink | Floor | Depth | Upstream | up/floor |
|---|---:|---:|---:|---:|
| 6645 | 101.7 km² | **27.6 m** | **1,562 km²** | 15× |
| 10431 | 20.5 km² | 4.0 m | 712 km² | 35× |
| 11676 | 1.8 km² | 3.8 m | 459 km² | **254×** |
| 14922 | 10.0 km² | 14.1 m | 391 km² | 39× |
| 19003 | 7.1 km² | 5.4 m | 286 km² | 40× |

**Sink 6645 alone captures 1,562 km²**, against HydroBASINS' independent 1,767 km² for the whole system. That is the main playa.

The shallow entries with extreme ratios are **not basins**. A 1.8 km² depression 3.8 m deep that traps 459 km² of upstream terrain is a road embankment or a DEM artifact across a wadi floor. Masking those would delete catchment that genuinely reaches the sea — which is exactly what happened at a 2 m threshold: 3,799 km² masked and Wadi Yutum cut to 2,728 km².

**Depth is the discriminator.** A basin needing >10 m of fill to overtop its rim is real topography.

---

## Result

| | GLO-30 | SRTM |
|---|---:|---:|
| Depressions found | 20,352 | **136,927** |
| Above 1 km² & 10 m | 3 | 27 |
| Endorheic area (10 m) | 2,036 km² | 4,836 km² |
| **Wadi Yutum (10 m)** | **4,349 km²** | 1,917 km² |
| Wadi Yutum (30 m) | — | 3,670 km² |

### It worked for GLO-30

Three independent approaches now agree within 8%:

| | Wadi Yutum |
|---|---:|
| Explicit masking, 10 m | 4,349 km² |
| `fill=False` proxy | 4,453 km² |
| HydroBASINS exorheic | 4,690 km² |

And the masked endorheic area, 2,036 km², sits +15% from HydroBASINS' 1,767 km².

**The two GLO-30 methods agree within 2.3%.** That is the reassuring part: for this DEM the number was never method-fragile. What was fragile was the *choice of DEM*.

### It did not fully solve DEM sensitivity

SRTM needs a 30 m threshold to give a comparable answer, and even then lands at 3,670 vs 4,349 — 16% apart.

But the spread narrowed a lot: **1.74× under `fill=False`, 1.19× under explicit masking at DEM-appropriate thresholds.**

**SRTM finds 136,927 depressions against GLO-30's 20,352 — 6.7× more.** That is the real finding. SRTM's vertical noise manufactures spurious deep sinks, so any depression-based method degrades on it. The M2 disagreement was never evidence that our number is wrong; it is evidence that SRTM is too noisy for this analysis. We can now say that with a number attached.

---

## Decision

**Keep 4,453 km² as the published figure.** Explicit masking gives 4,349 km² — a 2.3% difference, well inside the uncertainty of either method — so re-publishing would churn every document for no gain in accuracy.

What this work changes is not the number but its **standing**: it was a value produced by a conditioning flag, and it is now corroborated by a physically-motivated method that agrees with it, plus an independent product that agrees with both.

**Revised uncertainty statement.** M2 put contributing area somewhere in 2,600–6,400 km². That was too pessimistic — it treated SRTM as an equal witness. Restricted to GLO-30, where the depression count says the DEM is fit for the job, the range is **4,349–4,690 km², about ±4%.**

---

## Threshold caveat

`min_depth` must scale with the DEM's vertical noise floor: 10 m suits GLO-30, ~30 m suits SRTM. That is a judgement, not a constant, and any reuse of this script on another DEM needs it re-tuned. The depression count is a cheap guide — if a DEM yields six figures of depressions over this area, its noise floor is too high for a 10 m threshold to mean anything.

---

## Reproduce

```bash
.venv/bin/python scripts/10_endorheic_mask.py --min-depth 10
.venv/bin/python scripts/10_endorheic_mask.py --work data/interim/srtm --min-depth 30
```

Writes `endorheic_mask.tif`, `dem_selective.tif`, `sinks.shp` and `exo_accum.tif` into the work directory.
