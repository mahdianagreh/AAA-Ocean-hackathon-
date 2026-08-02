# SRTM cross-check of the delineation

**Date:** 2 August 2026
**Method:** `scripts/09_srtm_crosscheck.py` — identical chain, second elevation model, warped onto the exact GLO-30 grid so comparison is cell-for-cell.

| | Mission | Flown |
|---|---|---|
| Ours | Copernicus GLO-30 (TanDEM-X) | 2011–2015 |
| Check | NASA SRTM 1 arc-second | 2000 |

---

## Headline: position holds, area does not

| Outlet | GLO-30 | SRTM | Area diff | Mouth shift |
|---|---:|---:|---:|---:|
| **AQ-O01** Wadi Yutum | 4,453.1 km² | 2,561.3 km² | **−42.5%** | 579 m |
| AQ-O02 | 64.9 km² | 67.0 km² | +3.4% | 547 m |
| AQ-O03 | 59.9 km² | 59.9 km² | −0.0% | 319 m |
| AQ-O04 | 42.7 km² | 42.8 km² | +0.2% | 488 m |
| AQ-O05 | 35.6 km² | 42.8 km² | +20.0% | 466 m |

**Every mouth agrees to within 600 m.** Two independent radar missions, eleven years apart, put all five discharge points in the same place — including Wadi Yutum's, at 579 m. Outlet *position* is the robust result.

**The four small catchments agree on area too** — three within 3.4%, one at 20%. For 30 m routing over 35–65 km² basins, that is close agreement.

**Wadi Yutum's area does not agree at all**, and that is the number the whole project leans on.

---

## Why the area diverges — it is the conditioning, not the terrain

Running both DEMs through both depression-handling settings isolates it:

| | `fill=False` | `fill=True` |
|---|---:|---:|
| GLO-30 | 4,453 km² | 6,282 km² |
| SRTM | **2,561 km²** | **6,413 km²** |

**With `fill=True` the two DEMs agree within 2%.** They see the same terrain and the same total topographic catchment, about 6,300–6,400 km².

**With `fill=False` they diverge by a factor of 1.7.** That setting preserves closed depressions, and whether a given depression stays closed depends on its depth against the DEM's noise floor. SRTM is older, C-band, and noisier, so it traps far more flow in sinks.

So `fill=False` is doing something real — preserving endorheic basins that genuinely never reach the Gulf — but it is a **crude proxy** for that, and the result is sensitive to which DEM you run it on.

---

## What this means for the 4,453 km² figure

Honest position: **contributing area for Wadi Yutum is uncertain across roughly 2,600–6,400 km², and 4,453 is a defensible central estimate rather than a measurement.**

The case for keeping 4,453 as the working number:

- HydroBASINS independently gives **4,690 km²** exorheic, and GLO-30 with `fill=False` lands within 5% of it.
- GLO-30 is the better DEM here — newer, finer vertical precision, and no voids in this AOI.
- `fill=True` is clearly wrong: it annexes 1,767 km² that HydroSHEDS explicitly flags `ENDO>0`.

The case for caution, which should not be buried:

- HydroSHEDS is SRTM-derived, yet SRTM run through *our* `fill=False` gives 2,561 km². So HydroSHEDS is not using this crude a method, and the 4,453 ↔ 4,690 agreement is partly fortunate.
- Runoff volume scales with contributing area. A factor-of-1.7 uncertainty on the dominant catchment propagates straight into sediment load and plume magnitude.

**Recommended follow-up:** stop using `fill=False` as a proxy. Identify endorheic basins explicitly — closed depressions above a size and depth threshold — mask them, then condition normally. That is deterministic and DEM-noise-independent, and it would replace a lucky number with a defended one.

---

## For the team

**Karam** — the 4,453 km² catchment boundary is sound in shape but its *area* carries real uncertainty. Rainfall totals aggregated over it inherit that.

**Nizar** — release points are the robust part. All five agree between missions to within 600 m, so the plume origin is not the weak link.

**Pitch** — "two independent radar missions eleven years apart place every outlet within 600 m" is a strong, true claim. Do not extend it to catchment area, where they differ by 42% on the catchment that matters.

---

## Files

- `outlet_comparison.csv` — per-outlet areas and shifts
- `data/interim/srtm/` — the parallel hydrology chain

## Reproduce

```bash
.venv/bin/python scripts/09_srtm_crosscheck.py
```
