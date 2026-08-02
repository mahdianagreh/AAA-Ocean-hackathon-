# Outlet verification against satellite imagery

**Date:** 2 August 2026
**Method:** `scripts/07_outlet_imagery_check.py` — Esri World Imagery at z16, DEM stream network overlaid, dot size scaled by flow accumulation.
**Source of outlets:** `data/processed/vectors/outlets.gpkg`, D8 routing on Copernicus GLO-30.

---

## Verdict

| Outlet | Area | Verdict | What the imagery shows |
|---|---:|---|---|
| **AQ-O01** | 4,453.1 km² | **Plausible** | Channel runs straight N–S then turns to sea south of the Ayla lagoons. Consistent with Aqaba's engineered Wadi Yutum flood channel. Mouth at the shoreline. |
| **AQ-O02** | 64.9 km² | **Artifact** | Channel routes straight through the container terminal — across stacked containers and reclaimed land. |
| **AQ-O03** | 59.9 km² | **Suspect** | Channel follows a road corridor between oil storage tank farms; outlet lands on a tanker jetty, not a wadi mouth. |
| **AQ-O04** | 42.7 km² | **Problematic** | Marker sits in the middle of an **enclosed harbour basin**. Water does drain there, but a plume released inside a harbour behaves nothing like one released on open coast. |
| **AQ-O05** | 35.6 km² | **Good** | Visible braided wadi bed in natural desert terrain, mouth at the shore, fringing reef immediately adjacent. |

**One clean, one plausible, three compromised by port and industrial infrastructure.**

---

## The underlying problem

This is not a bug in the routing. It is what Jordan's coast actually is.

Aqaba's ~27 km shoreline is largely port, container terminal, tanker berths, industrial estate and reclaimed land. Only the southern stretch below the industrial zone remains natural. So for three of five catchments there is **no natural wadi mouth to find** — discharge reaches the sea through engineered stormwater outfalls whose positions are set by drainage design, not terrain.

Two compounding effects in the DEM:

1. **GLO-30 is a surface model.** Buildings, container stacks, embankments and tank farms are in the elevation values. Flow routes around them, or along the road corridors between them.
2. **Reclaimed land post-dates or is flattened in the DEM.** The container terminal is engineered flat, so routing across it is near-arbitrary.

---

## What this changes

**AQ-O04 is the one to worry about.** Its release point is inside an enclosed harbour. Sediment there would settle in the basin rather than disperse into the Gulf, so a particle simulation released at that coordinate would produce a confidently wrong plume. It should not be demoed without a caveat.

**AQ-O02 and AQ-O03 are uncertain to several hundred metres.** Their catchments are real and their areas are sound — it is only the mouth position that is unreliable.

**AQ-O01 and AQ-O05 are the defensible pair.** Together they carry 4,489 km², **96.4% of the modelled discharge**. AQ-O01 is Wadi Yutum, the event the whole project is built around; AQ-O05 is a clean natural wadi with reef directly offshore.

---

## Recommendation

1. **Demo on AQ-O01.** It is 96% of the discharge and the imagery supports it.
2. **Use AQ-O05 as the second case.** Clean terrain, adjacent reef, no infrastructure ambiguity.
3. **Mark AQ-O02/O03/O04 `position_confidence = "low"`** in the outlets table rather than dropping them — the catchments are valid, only the mouths are uncertain.
4. **Do not release a plume at AQ-O04** without stating that it discharges into an enclosed harbour.
5. **Ask for local drainage data.** ASEZA or the municipality would have stormwater outfall locations. That is the only real fix for the three industrial mouths, and it is a Phase 2 item — the concept doc already lists local drainage maps under Phase 2 calibration.

---

## Reproduce

```bash
.venv/bin/python scripts/07_outlet_imagery_check.py
```

Writes `AQ-O01.jpg` … `AQ-O05.jpg` and `_contact_sheet.jpg` to this directory. Tiles cache in `data/interim/tiles/`.
