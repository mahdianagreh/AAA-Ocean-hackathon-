"""P1 - Provisional catchments for Aqaba, from HydroBASINS level 12.

Placeholder geometry so Karam and Pulga can build their per-catchment
aggregation today. Boundaries are coarse and WILL be replaced by 30 m DEM
delineation. The IDs are final; the shapes are not.

Source: HydroBASINS v1.c, region 'eu' level 12.
NOTE: HydroSHEDS files the Middle East under 'eu' (Europe & Middle East),
NOT 'as'. The Asia file returns zero basins for Aqaba.
https://www.hydrosheds.org/products/hydrobasins

Structure found in the data
---------------------------
The Jordanian Gulf coast has TWO independent discharge points, not five:

  AQ-O01  Wadi Yutum system, 6458 km2, terminal basin 2120084740.
          Three branches converge into one terminal basin before the sea.
  AQ-O02  Southern coastal basin 2120084730, 375 km2, own outlet.

So catchments are split 4 + 1 across those two outlets. Several catchments
sharing one outlet is correct hydrology, not a modelling shortcut - the
runoff model wants them separate, the plume model releases from the shared
outlet.

Basins south of ~29.35 N are Saudi Arabia and are out of scope.

Outputs
-------
  data/processed/vectors/catchments_PROVISIONAL.gpkg
  data/aoi/terrain_aoi.geojson   (derived from the catchments, not guessed)
"""

import collections
import json
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data/raw/hydro/hybas_eu_lev12_v1c.shp"
OUT_CATCH = ROOT / "data/processed/vectors/catchments_PROVISIONAL.gpkg"
OUT_AOI = ROOT / "data/aoi/terrain_aoi.geojson"

READ_WINDOW = (34.4, 29.0, 36.2, 30.3)
UTM = 32636
AOI_PAD_DEG = 0.05

YUTUM_TERMINAL = 2120084740   # Wadi Yutum outlet basin, head of the Gulf
SOUTH_COASTAL = 2120084730    # independent basin south of Aqaba city


def build_upstream_index(gdf):
    up = collections.defaultdict(list)
    for hyd, nxt in zip(gdf.HYBAS_ID, gdf.NEXT_DOWN):
        up[nxt].append(hyd)
    return up


def upstream_set(up, root):
    """All basins draining through `root`, including root itself."""
    seen, stack = set(), [root]
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(up.get(node, []))
    return seen


def dissolve(gdf, ids, name, outlet_id, note):
    part = gdf[gdf.HYBAS_ID.isin(ids)]
    geom = part.union_all()
    return {
        "name": name,
        "outlet_id": outlet_id,
        "n_subbasins": len(part),
        "note": note,
        "geometry": geom,
    }


def main():
    if not SRC.exists():
        raise SystemExit(f"missing {SRC} - download HydroBASINS level 12 first")

    g = gpd.read_file(SRC, bbox=READ_WINDOW)
    up = build_upstream_index(g)

    term_own = {YUTUM_TERMINAL}
    branches = [b for b in up.get(YUTUM_TERMINAL, [])]

    parts = []
    for b in branches:
        ids = upstream_set(up, b)
        parts.append((b, ids))
    # largest branch first, so the main Wadi Yutum trunk is unambiguous
    parts.sort(key=lambda t: -len(t[1]))

    records = []
    for b, ids in parts:
        records.append(
            dissolve(g, ids, f"Yutum branch via {b}", "AQ-O01",
                     "drains into the Wadi Yutum terminal basin")
        )
    records.append(
        dissolve(g, term_own, "Yutum terminal basin", "AQ-O01",
                 "reaches the sea directly - shared outlet for AQ-O01")
    )
    records.append(
        dissolve(g, upstream_set(up, SOUTH_COASTAL), "Southern coastal basin",
                 "AQ-O02", "independent outlet south of Aqaba city")
    )

    out = gpd.GeoDataFrame(records, geometry="geometry", crs=4326)
    om = out.to_crs(UTM)
    out["area_km2"] = (om.area / 1e6).round(1)
    cent = om.geometry.centroid.to_crs(4326)
    out["clon"] = cent.x.round(4)
    out["clat"] = cent.y.round(4)

    out = out.sort_values("clat", ascending=False).reset_index(drop=True)
    out.insert(0, "catchment_id", [f"AQ-C{i + 1:02d}" for i in range(len(out))])
    out["provisional"] = True
    out["source"] = "HydroBASINS v1.c eu lev12"

    OUT_CATCH.parent.mkdir(parents=True, exist_ok=True)
    out.to_file(OUT_CATCH, driver="GPKG", layer="catchments")

    # terrain AOI derived from the catchments themselves, not guessed
    w, s, e, n = out.total_bounds
    w, s, e, n = (round(w - AOI_PAD_DEG, 2), round(s - AOI_PAD_DEG, 2),
                  round(e + AOI_PAD_DEG, 2), round(n + AOI_PAD_DEG, 2))
    OUT_AOI.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "name": "aqaba_terrain_aoi",
                            "bbox": [w, s, e, n],
                            "note": (
                                "Derived from the contributing catchments plus "
                                f"{AOI_PAD_DEG} deg pad. Covers full upstream area - "
                                "clipping tighter cuts off Wadi Yutum's headwaters."
                            ),
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
                        },
                    }
                ],
            },
            indent=2,
        )
        + "\n"
    )

    # union of terrain + marine = the project AOI referenced by the contract
    marine_path = ROOT / "data/aoi/marine_aoi.geojson"
    if marine_path.exists():
        mb = json.loads(marine_path.read_text())["features"][0]["properties"]["bbox"]
        uw, us, ue, un = (min(w, mb[0]), min(s, mb[1]), max(e, mb[2]), max(n, mb[3]))
        (ROOT / "data/aoi/aqaba_aoi.geojson").write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {
                                "name": "aqaba_aoi",
                                "bbox": [uw, us, ue, un],
                                "note": "Union of terrain_aoi and marine_aoi. "
                                        "Use as the download superset.",
                            },
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [[[uw, us], [ue, us], [ue, un],
                                                 [uw, un], [uw, us]]],
                            },
                        }
                    ],
                },
                indent=2,
            )
            + "\n"
        )
        print(f"wrote data/aoi/aqaba_aoi.geojson  (union) {[uw, us, ue, un]}")
    else:
        print("WARNING: marine_aoi.geojson missing - run scripts/01_make_aoi.py first")

    cols = ["catchment_id", "name", "outlet_id", "area_km2", "n_subbasins", "clon", "clat"]
    print(f"wrote {OUT_CATCH.relative_to(ROOT)}  ({len(out)} catchments)\n")
    print(out[cols].to_string(index=False))
    print(f"\ntotal area: {out.area_km2.sum():.1f} km2")
    print(f"outlets: {sorted(out.outlet_id.unique())}")
    print(f"\nwrote {OUT_AOI.relative_to(ROOT)}")
    print(f"terrain AOI (W,S,E,N): {[w, s, e, n]}")
    print(f"  {(e - w) * 111 * 0.87:.0f} km x {(n - s) * 111:.0f} km")


if __name__ == "__main__":
    main()
