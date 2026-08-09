#!/usr/bin/env python3
"""Country boundaries and place labels for the frontend basemap.

The Gulf of Aqaba is a four-country basin roughly 25 km wide, and the map had no
political geography on it at all — one undifferentiated landmass. That is not a
cosmetic gap: the project's own framing is that a single storm system touches
several countries at once, and a viewer cannot see that without borders.

Source is **Natural Earth 10m admin-0** (public domain, v5.1.1), clipped to a
margin around TERRAIN_AOI and committed under `frontend/public/basemap/` like
every other layer — DoD item 9 is "works with wifi off", so nothing is fetched
at runtime. 10m rather than 110m because at a ~120 km view the coarser set
visibly cuts corners along the Gulf shore.

Two outputs:

  admin.geojson         boundary LINES, dissolved, land borders only
  admin_labels.geojson  country and city label POINTS, bilingual

**On naming.** The labels are Natural Earth's own `NAME` / `NAME_AR`, used
verbatim rather than edited here. Four entities intersect this view in that
dataset: Jordan, Egypt, Saudi Arabia and Palestine — Natural Earth carries the last
with `TYPE='Disputed'`, and that attribute is passed through to the layer rather
than being resolved by this script. The Palestinian territories do not intersect
this map extent in this dataset; the West Bank lies well north of the terrain
box, so a "Palestine" label placed here would be geographically wrong. If the
team wants different naming, change it here against a cited reference, not by
hand-editing the emitted GeoJSON.

Run:

    python3 scripts/frontend_admin.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

import geopandas as gpd  # noqa: E402
from shapely.geometry import box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from config.spatial import TERRAIN_AOI, CRS_STORAGE, CRS_MEASURE  # noqa: E402

NE = ROOT / "data" / "raw" / "naturalearth" / "ne_10m_admin_0_countries.shp"
COORD_DP = 5  # ~1 m at this latitude, same as frontend_basemap.py

# Margin beyond TERRAIN_AOI. The map is routinely panned a little past the box,
# and a border that stops dead at the AOI edge reads as a data error.
MARGIN_DEG = 0.75

# Where country labels are allowed to sit.
#
# A point label only renders when its point is on screen, and the dashboard opens
# fitted to MARINE_AOI — a ~25 x 39 km box at the head of the Gulf. Labels placed
# at each country's representative point land 60-100 km away (Egypt at 34.42,
# Jordan at 35.91) and are therefore never visible at the view the app actually
# opens at. So the label point is the representative point of the country's
# intersection with THIS box instead: big enough to hold all four around the
# Gulf, small enough that every label stays near the water the map is about.
#
# Measured, not guessed: the opening view is 34.678-35.172 E, 29.238-29.612 N at
# z10.3 (read off m.getBounds() in the running app). A larger box put all four
# label points outside that rectangle, so none of them rendered — the labels were
# correct and simply off-screen. Inset slightly so a label is not flush against
# the frame edge.
LABEL_BOX = (34.70, 29.25, 35.15, 29.60)  # w, s, e, n

# Cities worth a label at this scale. Aqaba and Eilat sit at the head of the
# Gulf and are the paired sites in this project's own event record — the
# Oct 2016 flood is documented as the Aqaba-Eilat flood.
CITIES = [
    {"name_en": "Aqaba", "name_ar": "العقبة", "lon": 35.0064, "lat": 29.5321, "kind": "city"},
    {"name_en": "Eilat", "name_ar": "إيلات", "lon": 34.9482, "lat": 29.5577, "kind": "city"},
]


def round_coords(obj, dp=COORD_DP):
    if isinstance(obj, list):
        return [round_coords(o, dp) for o in obj]
    if isinstance(obj, (int, float)):
        return round(float(obj), dp)
    return obj


def _clean(v):
    """NaN -> None, numpy scalar -> Python scalar.

    Python's json module emits a bare `NaN` token by default. That is not valid
    JSON, and every browser's JSON.parse rejects it — so MapLibre drops the whole
    source silently and the layer renders nothing at all. It cost an hour here:
    the borders drew fine (no NaN in that file) while every label vanished,
    because pandas turned the cities' `visible_km2: None` into a float NaN when
    it built the column. `allow_nan=False` below makes that failure loud instead.
    """
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    if hasattr(v, "item"):
        v = v.item()
        return None if isinstance(v, float) and v != v else v
    return v


def write(out_dir: Path, name: str, gdf: gpd.GeoDataFrame, keep: tuple[str, ...]) -> None:
    gdf = gdf.to_crs(CRS_STORAGE)
    feats = []
    for _, row in gdf.iterrows():
        props = {k: _clean(row.get(k)) for k in keep}
        geom = json.loads(gpd.GeoSeries([row.geometry], crs=CRS_STORAGE).to_json())
        g = geom["features"][0]["geometry"]
        g["coordinates"] = round_coords(g["coordinates"])
        feats.append({"type": "Feature", "properties": props, "geometry": g})
    fc = {"type": "FeatureCollection", "features": feats}
    path = out_dir / f"{name}.geojson"
    path.write_text(json.dumps(fc, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    print(f"  {name:14s} {len(feats):4d} features   {path.stat().st_size:,} B")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "frontend" / "public" / "basemap"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if not NE.exists():
        print(f"missing {NE}\n  download ne_10m_admin_0_countries from naturalearth.com", file=sys.stderr)
        return 1

    w, s, e, n = TERRAIN_AOI.wsen
    view = box(w - MARGIN_DEG, s - MARGIN_DEG, e + MARGIN_DEG, n + MARGIN_DEG)

    ne = gpd.read_file(NE).to_crs(CRS_STORAGE)
    hit = ne[ne.intersects(view)].copy()
    print(f"  countries in view: {', '.join(sorted(hit['NAME']))}")

    # Clip polygons to the view, then take boundaries. Dissolving the union first
    # would merge the countries into one blob and lose every internal border,
    # which is the only thing this layer exists to draw.
    hit["geometry"] = hit.geometry.intersection(view)
    hit = hit[~hit.geometry.is_empty].copy()

    # Boundary lines, minus the clip frame itself — a rectangle drawn around the
    # whole map is not a border and reads as a bug.
    frame = view.boundary.buffer(0.002)
    lines = []
    for _, row in hit.iterrows():
        b = row.geometry.boundary.difference(frame)
        if b.is_empty:
            continue
        lines.append({"geometry": b, "name_en": row["NAME"], "name_ar": row["NAME_AR"],
                      "type": row["TYPE"]})
    bounds = gpd.GeoDataFrame(lines, crs=CRS_STORAGE)
    write(out, "admin", bounds, keep=("name_en", "name_ar", "type"))

    # Label points. `representative_point` guarantees a point inside the clipped
    # polygon — a centroid can fall outside a concave country and land the label
    # in the sea, which happens to Egypt here once Sinai is clipped.
    label_box = box(*LABEL_BOX)
    rows = []
    for _, row in hit.iterrows():
        geom = row.geometry.intersection(label_box)
        if geom.is_empty:
            print(f"    {row['NAME']}: no area inside LABEL_BOX, label skipped")
            continue
        # Place the label in the largest visible piece, not in a sliver.
        if geom.geom_type == "MultiPolygon":
            geom = max(geom.geoms, key=lambda g: g.area)
        area_km2 = (gpd.GeoSeries([geom], crs=CRS_STORAGE)
                    .to_crs(CRS_MEASURE).iloc[0].area / 1e6)
        rows.append({
            "geometry": geom.representative_point(),
            "name_en": row["NAME"], "name_ar": row["NAME_AR"],
            "kind": "country", "type": row["TYPE"],
            "visible_km2": round(area_km2, 1),
        })
    for c in CITIES:
        rows.append({
            "geometry": gpd.points_from_xy([c["lon"]], [c["lat"]], crs=CRS_STORAGE)[0],
            "name_en": c["name_en"], "name_ar": c["name_ar"],
            "kind": c["kind"], "type": None, "visible_km2": None,
        })
    labels = gpd.GeoDataFrame(rows, crs=CRS_STORAGE)
    write(out, "admin_labels", labels, keep=("name_en", "name_ar", "kind", "type", "visible_km2"))

    print("\n  label placement:")
    for _, r in labels.iterrows():
        print(f"    {r['kind']:8s} {str(r['name_en']):14s} "
              f"{r.geometry.x:8.4f}, {r.geometry.y:7.4f}"
              + (f"   visible {r['visible_km2']:,} km²" if r["visible_km2"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
