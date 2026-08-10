# Culvert cross-check

**Date:** 3 August 2026 · `scripts/12_culvert_crosscheck.py`
**Sources:** `outlets.gpkg` (GLO-30 D8 routing) × `osm_aqaba.gpkg` layer
`drainage_features`, 46 features tagged `tunnel=culvert`

---

## Why

GLO-30 is a surface model. A road embankment is a solid ridge to it, so D8
routes flow **around** what a culvert carries flow **through**. Where a mapped
culvert sits on an embankment the router treated as a wall, the modelled
channel is wrong and the true outlet is seaward of the modelled one.

This is the only correction available for the three low-confidence outlets
without ASEZA stormwater data.

## The rule this analysis obeys

> Absence of a mapped feature is **not** evidence that no channel exists. OSM
> completeness for drainage in Aqaba is unverified. Only **positive** matches
> are usable.

So a "no culvert nearby" result below means *no information*, **not** *the
outlet is fine*. That asymmetry is the whole discipline of the check.

---

## Result

| outlet_id   |   culverts_2500m |   nearest_m |   unmodelled_coastal | verdict                                                                         | action                                                |
|:------------|-----------------:|------------:|---------------------:|:--------------------------------------------------------------------------------|:------------------------------------------------------|
| AQ-O01      |                2 |        2138 |                    0 | 2 culvert(s) nearby, all carrying a modelled channel                            | none needed — DEM and OSM agree on the drainage lines |
| AQ-O02      |                3 |         312 |                    2 | culvert 312 m away, 121 m from the coast, with NO modelled channel within 150 m | CANDIDATE CORRECTION — unmodelled path to the sea     |
| AQ-O03      |                1 |         829 |                    1 | culvert 829 m away, 270 m from the coast, with NO modelled channel within 150 m | CANDIDATE CORRECTION — unmodelled path to the sea     |
| AQ-O04      |                2 |         793 |                    0 | 2 culvert(s) nearby, all carrying a modelled channel                            | none needed — DEM and OSM agree on the drainage lines |
| AQ-O05      |                2 |         243 |                    0 | 2 culvert(s) nearby, all carrying a modelled channel                            | none needed — DEM and OSM agree on the drainage lines |

**2 candidate correction(s).**

---

## What this does and does not settle

**Settles:** where a culvert is mapped and seaward of the modelled mouth,
there is positive evidence the DEM stopped short, and a specific coordinate
to inspect.

**Does not settle:** anything about the outlets with no nearby culvert. Under
the rule above those are unchanged and remain low confidence — the check
found no evidence either way, which is different from finding it correct.

**Still needs ASEZA.** Mapped culverts are a subset of real stormwater
infrastructure. The port and tank-farm outlets discharge through engineered
systems that OSM does not describe, and no amount of open data substitutes
for the operator's drainage plans. Phase 2 in the concept doc.

---

## Caveats now stored in the data

`outlets.gpkg` carries a `caveat` column, so the warning travels with the
geometry rather than living only in a report. The API reads that column
instead of its own copy.

| outlet_id   | position_confidence   |
|:------------|:----------------------|
| AQ-O01      | high                  |
| AQ-O02      | low                   |
| AQ-O03      | low                   |
| AQ-O04      | low                   |
| AQ-O05      | high                  |

The AQ-O04 text in full:

> Discharges into an enclosed harbour basin; sediment released here settles in the basin rather than dispersing into the Gulf. A particle simulation from this coordinate will produce a confidently wrong plume. Do not demo without stating this.
