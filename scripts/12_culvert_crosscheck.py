"""Part 5 — cross-check the routed channels against OSM culverts, and write
the caveat into the outlets table.

Why culverts specifically
-------------------------
GLO-30 is a surface model, so a road embankment is a solid ridge and D8 routes
flow *around* it. A culvert carries flow *through*. Wherever a mapped culvert
sits on an embankment the router treated as a wall, the modelled channel is
wrong — and the true outlet is seaward of wherever the DEM put it.

This is the only correction available for the three low-confidence outlets
without ASEZA stormwater data.

The rule that governs the whole analysis
----------------------------------------
Pulga's brief is explicit and it is inverted from the usual instinct:

    Absence of a mapped feature is NOT evidence that no channel exists. OSM
    completeness for drainage in Aqaba is unverified. Only POSITIVE matches
    are usable. Nothing here can rule a channel out.

So this script can move an outlet toward a culvert, or say nothing. It can
never conclude that an outlet is fine because no culvert was found nearby.

Outputs
    data/processed/vectors/outlets.gpkg   + caveat, + culvert columns
    reports/outlets/culvert_crosscheck.md
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
OUTLETS = ROOT / "data/processed/vectors/outlets.gpkg"
OSM = ROOT / "data/processed/vectors/osm_aqaba.gpkg"
DEM = ROOT / "data/processed/dem/dem_utm36n.tif"
WORK = ROOT / "data/interim/hydro"
OUTLETS_JSON = ROOT / "data/processed/vectors/outlets.geojson"
REPORT = ROOT / "reports/outlets/culvert_crosscheck.md"

UTM = 32636
# A culvert further than this from an outlet is a different drainage system,
# not a correction to this one.
SEARCH_RADIUS_M = 2500
# A modelled channel within this of a culvert means the DEM already routes
# that line - 30 m cells, so 150 m is 5 cells of slack for OSM's own
# positional error.
CHANNEL_MATCH_M = 150
# A culvert this close to the sea is a candidate coastal discharge point.
COASTAL_M = 500
# Only trunk channels, matching the threshold used for the stream validation.
MIN_UPSTREAM_KM2 = 10.0

# The caveat text. Written once, here, and read by the API - the version
# hardcoded in api/main.py during the Docker work was a second copy waiting to
# drift, and this replaces it.
CAVEATS = {
    "AQ-O01": "Engineered Wadi Yutum flood channel; mouth verified against "
              "imagery at the shoreline. Catchment area carries ±4% from "
              "separating endorheic basins from DEM artifacts.",
    "AQ-O02": "Routed channel crosses the container terminal and reclaimed "
              "land, which GLO-30 represents as solid surface. Mouth position "
              "uncertain to several hundred metres.",
    "AQ-O03": "Routed channel follows a road corridor between oil storage tank "
              "farms and terminates on a tanker jetty rather than a wadi mouth. "
              "Mouth position uncertain.",
    "AQ-O04": "Discharges into an enclosed harbour basin; sediment released "
              "here settles in the basin rather than dispersing into the Gulf. "
              "A particle simulation from this coordinate will produce a "
              "confidently wrong plume. Do not demo without stating this.",
    "AQ-O05": "Natural braided wadi bed, mouth verified at the shore with "
              "fringing reef immediately offshore.",
}


def load_culverts() -> gpd.GeoDataFrame:
    g = gpd.read_file(OSM, layer="drainage_features")
    c = g[g.tunnel == "culvert"].copy()
    if c.empty:
        raise SystemExit("no culverts in the OSM extract")
    return c.to_crs(UTM)


def modelled_stream_points() -> np.ndarray:
    """UTM coordinates of every trunk channel cell the DEM routed.

    Restricted to the same >=10 km2 threshold the HydroRIVERS validation used,
    so "no modelled channel here" means no trunk, not merely no hillslope
    rivulet.
    """
    import rasterio

    with rasterio.open(WORK / "streams.tif") as r:
        streams = r.read(1) > 0
        transform = r.transform
        px = abs(r.res[0] * r.res[1]) / 1e6
    with rasterio.open(WORK / "d8_accum.tif") as r:
        accum = r.read(1)

    trunk = streams & (accum >= MIN_UPSTREAM_KM2 / px)
    rr, cc = np.where(trunk)
    xs, ys = rasterio.transform.xy(transform, rr, cc)
    return np.column_stack([xs, ys])


def coastline() -> gpd.GeoSeries:
    """Sea boundary from the DEM, same definition the delineation used."""
    import rasterio
    from rasterio import features
    from shapely.geometry import shape

    sys.path.insert(0, str(ROOT / "scripts"))
    from hydro_common import read_dem, sea_mask

    arr, valid, _ = read_dem(DEM)
    with rasterio.open(DEM) as r:
        transform, crs = r.transform, r.crs
    mask = sea_mask(arr, valid, transform, crs)
    polys = [shape(gm) for gm, v in features.shapes(
        mask.astype("uint8"), mask=mask, transform=transform) if v == 1]
    polys.sort(key=lambda p: p.area, reverse=True)
    return gpd.GeoSeries([polys[0].boundary], crs=crs)


def main():
    for p in (OUTLETS, OSM, DEM):
        if not p.exists():
            raise SystemExit(f"missing {p}")

    outl = gpd.read_file(OUTLETS, layer="outlets").to_crs(UTM)
    culv = load_culverts()
    coast = coastline()
    print(f"{len(outl)} outlets · {len(culv)} mapped culverts")

    culv["dist_coast_m"] = culv.geometry.distance(coast.iloc[0])

    # ── the test ─────────────────────────────────────────────────────────
    # A first version asked whether a culvert lay SEAWARD of the outlet. That
    # can never fire: outlets are chosen as stream cells adjacent to the sea
    # mask, so they sit on the shoreline by construction and nothing is
    # seaward of them. It returned five clean nulls and proved only that the
    # question was wrong.
    #
    # The real failure mode is lateral, not inland. An embankment sends flow
    # sideways to exit somewhere else along the coast, so the symptom is a
    # mapped culvert that NO modelled channel passes through. That means the
    # DEM never routed water down that line at all.
    stream_pts = modelled_stream_points()
    print(f"{len(stream_pts):,} modelled channel cells (≥10 km² upstream)")

    culv["dist_to_modelled_channel_m"] = [
        float(np.min(np.hypot(stream_pts[:, 0] - g.x, stream_pts[:, 1] - g.y)))
        for g in culv.geometry.centroid
    ]
    culv["missed_by_dem"] = culv.dist_to_modelled_channel_m > CHANNEL_MATCH_M
    coastal = culv[culv.dist_coast_m <= COASTAL_M]
    unmodelled = coastal[coastal.missed_by_dem]

    print(f"{len(coastal)} culverts within {COASTAL_M} m of the coast, "
          f"of which {len(unmodelled)} carry no modelled channel")

    # Each unmodelled culvert is attributed to its NEAREST outlet only. Sharing
    # them across every outlet within 2.5 km flagged AQ-O05 - which imagery
    # already verified - for a culvert 2 km down the coast belonging to
    # somebody else's drainage. One culvert corrects at most one outlet.
    if not unmodelled.empty:
        owner = {}
        for idx, c in unmodelled.iterrows():
            dists = outl.geometry.distance(c.geometry)
            owner[idx] = outl.loc[dists.idxmin(), "outlet_id"]
        culv["assigned_outlet"] = pd.Series(owner)
    else:
        culv["assigned_outlet"] = None

    rows = []
    for _, o in outl.iterrows():
        d = culv.geometry.distance(o.geometry)
        near = culv.assign(dist_m=d)
        near = near[near.dist_m <= SEARCH_RADIUS_M].sort_values("dist_m")
        missed = near[(near.assigned_outlet == o.outlet_id)].sort_values("dist_m")

        if near.empty:
            verdict, action, best_m = "no mapped culvert within 2.5 km", \
                "none available — absence is not evidence", None
        elif missed.empty:
            verdict = (f"{len(near)} culvert(s) nearby, all carrying a modelled "
                       "channel")
            action = "none needed — DEM and OSM agree on the drainage lines"
            best_m = round(float(near.iloc[0].dist_m))
        else:
            b = missed.iloc[0]
            verdict = (f"culvert {b.dist_m:,.0f} m away, {b.dist_coast_m:,.0f} m "
                       f"from the coast, with NO modelled channel within "
                       f"{CHANNEL_MATCH_M} m")
            action = "CANDIDATE CORRECTION — unmodelled path to the sea"
            best_m = round(float(b.dist_m))

        rows.append({
            "outlet_id": o.outlet_id,
            "culverts_2500m": int(len(near)),
            "nearest_m": best_m,
            "unmodelled_coastal": int(len(missed)),
            "verdict": verdict,
            "action": action,
        })

    res = pd.DataFrame(rows)
    print()
    print(res[["outlet_id", "culverts_2500m", "nearest_m",
               "unmodelled_coastal", "action"]].to_string(index=False))

    # ---- write the caveat into the data ---------------------------------
    outl["caveat"] = outl.outlet_id.map(CAVEATS)
    if outl.caveat.isna().any():
        raise SystemExit(f"no caveat for {list(outl.loc[outl.caveat.isna(), 'outlet_id'])}")
    j = res.set_index("outlet_id")
    outl["culverts_within_2500m"] = outl.outlet_id.map(j.culverts_2500m)
    outl["nearest_culvert_m"] = outl.outlet_id.map(j.nearest_m)
    outl["unmodelled_coastal_culverts"] = outl.outlet_id.map(j.unmodelled_coastal)
    outl["culvert_verdict"] = outl.outlet_id.map(j.action)

    wgs = outl.to_crs(4326)
    wgs.to_file(OUTLETS, driver="GPKG", layer="outlets")
    print(f"\nwrote {OUTLETS.relative_to(ROOT)}  (+caveat, +culvert columns)")

    # GeoJSON alongside, so the API can read the caveats with stdlib json.
    # The alternative was hardcoding them in api/main.py - a second copy of a
    # safety warning, which is how the AQ-O04 harbour caveat gets forgotten -
    # or putting geopandas in the serving image for the sake of five rows.
    wgs.to_file(OUTLETS_JSON, driver="GeoJSON")
    print(f"wrote {OUTLETS_JSON.relative_to(ROOT)}  (read by the API)")

    write_report(res, culv, outl)
    print(f"wrote {REPORT.relative_to(ROOT)}")


def write_report(res, culv, outl):
    corrections = res[res.action.str.startswith("CANDIDATE")]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# Culvert cross-check

**Date:** 3 August 2026 · `scripts/12_culvert_crosscheck.py`
**Sources:** `outlets.gpkg` (GLO-30 D8 routing) × `osm_aqaba.gpkg` layer
`drainage_features`, {len(culv)} features tagged `tunnel=culvert`

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

{res.to_markdown(index=False)}

**{len(corrections)} candidate correction(s).**

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

{outl[["outlet_id", "position_confidence"]].to_markdown(index=False)}

The AQ-O04 text in full:

> {CAVEATS["AQ-O04"]}
""")


if __name__ == "__main__":
    main()
