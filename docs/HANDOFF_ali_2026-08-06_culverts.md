# Culvert & Drainage Correction Map — confirmed scope

Mahdi, Phase 4 task 4. Confirming this before you build, per your own task file's plan
to render it like the existing outlet layer.

## Confirmed: per-outlet fields are the whole story for what's servable today

`/api/v1/outlets` already returns, per outlet, live:

| outlet | culverts_within_2500m | nearest_culvert_m | unmodelled_coastal_culverts | culvert_verdict |
|---|---:|---:|---:|---|
| AQ-O01 | 2 | 2,138 m | 0 | none needed — DEM and OSM agree |
| **AQ-O02** | 3 | 312 m | **2** | **CANDIDATE CORRECTION — unmodelled path to the sea** |
| **AQ-O03** | 1 | 829 m | **1** | **CANDIDATE CORRECTION — unmodelled path to the sea** |
| AQ-O04 | 2 | 793 m | 0 | none needed |
| AQ-O05 | 2 | 243 m | 0 | none needed |

This is **5 rows, one per outlet** — no per-culvert endpoint exists, and building
against the outlet layer (as you already planned) is correct and complete for this
data. Nothing on my side blocks you.

## One distinction worth stating explicitly, so it's a choice and not an assumption

"27 mapped culverts" describes the total OSM extract used to compute the table above —
it does **not** mean 27 individual points are servable on the map. The individual
culvert geometries exist buried in `data/processed/vectors/osm_aqaba.gpkg` (features
tagged `tunnel=culvert`, filtered on the fly by `scripts/12_culvert_crosscheck.py`,
`load_culverts()`), but they are not persisted as their own layer and **nothing serves
them individually today**.

So there are two different maps this feature name could mean:

1. **5 outlet markers, flagged by their verdict** (`culvert_verdict`,
   `unmodelled_coastal_culverts`) — ready today, zero new backend work.
2. **27 individual culvert points**, each with its own status — would need a new
   endpoint; the raw geometry exists but nothing extracts/serves it yet.

Your plan is #1, and #1 is a fully honest, complete rendering of "candidate correction"
outlets — it is not a placeholder version of #2. If the feature is meant to show
individual culverts (e.g. so a viewer can see *which* 2 culverts near AQ-O02 are
unmodelled, not just that there are 2), say so now and I'll scope the new endpoint —
better now than after the outlet layer is built and someone asks "where are the actual
culvert dots."
