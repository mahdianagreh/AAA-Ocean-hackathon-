"""OSM drainage evidence for Mahdi's outlet correction -> docs/osm_dem_conflicts.md

Two parts, with different blocking status:

  PART 1 — culvert / drainage-outlet inventory. Needs only the OSM extract, so it
           is deliverable NOW. This is the part with real value: an annotated list
           with coordinates that can be acted on the same day.

  PART 2 — DEM-flow-path-vs-OSM conflict detection. Needs Mahdi's flow_paths.gpkg.
           Runs automatically if that file appears; otherwise the section is
           written as explicitly pending rather than silently omitted.

Handing over a raw GPKG makes the reader go hunting. The point of this script is
the annotated markdown.
"""

import geopandas as gpd
import pandas as pd

from pulga_config import AOI_CRS_PROJECTED, AOI_CRS_STORAGE, DOCS, PROCESSED, VECTORS

OSM_GPKG = VECTORS / "osm_aqaba.gpkg"
COASTLINE = VECTORS / "coastline.gpkg"
OUT_MD = DOCS / "osm_dem_conflicts.md"

# Mahdi's DEM flow paths — path per contract §3 conventions. Checked, not assumed.
FLOW_PATHS_CANDIDATES = [
    PROCESSED / "vectors" / "flow_paths.gpkg",
    PROCESSED / "dem" / "flow_paths.gpkg",
]

# A drainage feature this close to the sea is plausibly at or near an outlet.
COASTAL_BUFFER_M = 1500.0
# Tolerance for matching an OSM drainage feature to a DEM flow path.
DEM_MATCH_TOLERANCE_M = 50.0


def load_layers():
    drains = gpd.read_file(OSM_GPKG, layer="drainage_features").to_crs(AOI_CRS_PROJECTED)
    roads = gpd.read_file(OSM_GPKG, layer="roads").to_crs(AOI_CRS_PROJECTED)
    water = gpd.read_file(COASTLINE, layer="water").to_crs(AOI_CRS_PROJECTED)
    shoreline = water.union_all().boundary
    return drains, roads, shoreline


def describe(drains, roads, shoreline):
    """Annotate each drainage feature with coastal distance and nearest road."""
    named_roads = roads[roads["name"].notna()].copy()

    rows = []
    for _, d in drains.iterrows():
        geom = d.geometry
        dist_coast = geom.distance(shoreline)

        # Nearest named road, for a human-readable landmark in the description.
        near_road, near_road_dist = None, None
        if not named_roads.empty:
            cand = named_roads[named_roads.geometry.distance(geom) < 300]
            if not cand.empty:
                dd = cand.geometry.distance(geom)
                near_road = cand.loc[dd.idxmin(), "name"]
                near_road_dist = float(dd.min())

        centroid = gpd.GeoSeries([geom.centroid], crs=AOI_CRS_PROJECTED).to_crs(
            AOI_CRS_STORAGE
        ).iloc[0]

        rows.append(
            {
                "osm_id": d.get("osm_id"),
                "name": d.get("name"),
                "waterway": d.get("waterway"),
                "tunnel": d.get("tunnel"),
                "intermittent": d.get("intermittent"),
                "lat": round(centroid.y, 5),
                "lon": round(centroid.x, 5),
                "length_m": round(geom.length, 1),
                "dist_to_coast_m": round(dist_coast, 1),
                "near_road": near_road,
                "near_road_m": None if near_road_dist is None else round(near_road_dist, 1),
            }
        )
    return pd.DataFrame(rows)


def dem_conflicts(drains):
    """Part 2 — only possible once Mahdi's flow paths exist."""
    for p in FLOW_PATHS_CANDIDATES:
        if p.exists():
            flow = gpd.read_file(p).to_crs(AOI_CRS_PROJECTED)
            buffered = flow.geometry.buffer(DEM_MATCH_TOLERANCE_M).union_all()
            unmatched = drains[~drains.intersects(buffered)].copy()
            out = VECTORS / "osm_dem_drainage_conflicts.gpkg"
            unmatched.to_crs(AOI_CRS_STORAGE).to_file(out, driver="GPKG")
            return p, unmatched, out
    return None, None, None


def cell(value, dash="—"):
    """Render a possibly-missing attribute.

    `value or dash` does NOT work here: pandas stores a missing string as float
    NaN, and NaN is truthy, so the fallback never fires and the table prints
    literal "nan".
    """
    return dash if value is None or pd.isna(value) else str(value)


def write_report(df, flow_src, unmatched, conflict_gpkg):
    culverts = df[df["tunnel"] == "culvert"].sort_values("dist_to_coast_m")
    coastal = df[df["dist_to_coast_m"] <= COASTAL_BUFFER_M].sort_values("dist_to_coast_m")
    named = df[df["name"].notna()].sort_values("dist_to_coast_m")

    L = []
    L.append("# OSM drainage evidence for outlet correction\n")
    L.append("**From:** Pulga (Workstream A+B) · **To:** Mahdi (terrain / outlets)  ")
    L.append("**Source:** `data/processed/vectors/osm_aqaba.gpkg`, layer `drainage_features`  ")
    L.append(f"**Extract:** Geofabrik `jordan-latest.osm.pbf`, clipped to the padded AOI  ")
    L.append(f"**Features:** {len(df)} drainage lines, of which {len(culverts)} are tagged "
             f"`tunnel=culvert`\n")

    L.append("> **Read this before using anything below.** Absence of a mapped drainage")
    L.append("> feature in OSM is **not** evidence that no channel exists. OSM completeness")
    L.append("> for drainage infrastructure in Aqaba is unverified and probably patchy. Only")
    L.append("> **positive** matches — a feature that IS mapped — are usable as corrections.")
    L.append("> Nothing here can be used to rule a channel out.\n")

    L.append("---\n")
    L.append("## 1. Mapped culverts, nearest the coast first\n")
    L.append("Culverts are the highest-value features in this extract: a DEM routes surface")
    L.append("flow *around* an embankment, while a culvert carries it *through*. Where a")
    L.append("culvert crosses the coastal highway, the true outlet is seaward of wherever the")
    L.append("DEM puts it.\n")
    L.append("| # | lat | lon | waterway | length m | dist to coast m | nearest road |")
    L.append("|---:|---|---|---|---:|---:|---|")
    for i, (_, r) in enumerate(culverts.iterrows(), 1):
        L.append(f"| {i} | {r['lat']} | {r['lon']} | {cell(r['waterway'])} | "
                 f"{r['length_m']:.0f} | {r['dist_to_coast_m']:.0f} | {cell(r['near_road'])} |")

    L.append(f"\n## 2. Drainage features within {COASTAL_BUFFER_M:.0f} m of the shoreline\n")
    L.append("These are the candidate outlet positions — a mapped channel this close to the")
    L.append("sea is most likely reaching it.\n")
    L.append("| lat | lon | name | waterway | culvert | intermittent | dist to coast m |")
    L.append("|---|---|---|---|---|---|---:|")
    for _, r in coastal.iterrows():
        L.append(f"| {r['lat']} | {r['lon']} | {cell(r['name'])} | {cell(r['waterway'])} | "
                 f"{'yes' if r['tunnel'] == 'culvert' else ''} | {cell(r['intermittent'], '')} | "
                 f"{r['dist_to_coast_m']:.0f} |")

    L.append("\n## 3. Named wadis in the extract\n")
    L.append("Named features are worth checking by hand — a named wadi is usually a real,")
    L.append("locally-recognised channel rather than an incidental ditch.\n")
    L.append("| name | lat | lon | waterway | dist to coast m |")
    L.append("|---|---|---|---|---:|")
    for _, r in named.iterrows():
        L.append(f"| {r['name']} | {r['lat']} | {r['lon']} | {cell(r['waterway'])} | "
                 f"{r['dist_to_coast_m']:.0f} |")

    L.append("\n## 4. DEM flow paths vs OSM drainage\n")
    if flow_src is None:
        L.append("**STATUS: PENDING — blocked on Mahdi's DEM flow paths.**\n")
        L.append("This section compares each mapped OSM drainage feature against the")
        L.append("DEM-derived flow network and lists the ones that fall outside a")
        L.append(f"{DEM_MATCH_TOLERANCE_M:.0f} m buffer of any modelled flow path — those are")
        L.append("the candidate outlet corrections.\n")
        L.append("It runs automatically as soon as a flow-path file exists at either:\n")
        for p in FLOW_PATHS_CANDIDATES:
            L.append(f"- `{p.relative_to(p.parents[3])}`")
        L.append("\nRe-run: `.venv/bin/python scripts/osm_drainage_report.py`\n")
        L.append("Sections 1-3 above need nothing from anyone and are final.")
    else:
        L.append(f"Compared against `{flow_src.name}` with a "
                 f"{DEM_MATCH_TOLERANCE_M:.0f} m match tolerance.\n")
        L.append(f"**{len(unmatched)} of {len(df)} OSM drainage features have no DEM flow path "
                 f"within {DEM_MATCH_TOLERANCE_M:.0f} m.** Each is a candidate correction.\n")
        L.append(f"Geometry: `{conflict_gpkg}`\n")
        L.append("| lat | lon | name | waterway | culvert | dist to coast m |")
        L.append("|---|---|---|---|---|---:|")
        sub = describe_subset(unmatched)
        for _, r in sub.iterrows():
            L.append(f"| {r['lat']} | {r['lon']} | {cell(r['name'])} | {cell(r['waterway'])} | "
                     f"{'yes' if r['tunnel'] == 'culvert' else ''} | {r['dist_to_coast_m']:.0f} |")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(L) + "\n")
    print(f"wrote {OUT_MD}")
    print(f"  {len(culverts)} culverts, {len(coastal)} coastal features, {len(named)} named")


def describe_subset(unmatched):
    """Re-annotate an already-filtered set for the Part 2 table."""
    drains, roads, shoreline = load_layers()
    keep = set(unmatched["osm_id"].astype(str))
    sub = drains[drains["osm_id"].astype(str).isin(keep)]
    return describe(sub, roads, shoreline).sort_values("dist_to_coast_m")


if __name__ == "__main__":
    drains, roads, shoreline = load_layers()
    df = describe(drains, roads, shoreline)
    flow_src, unmatched, conflict_gpkg = dem_conflicts(drains)
    if flow_src is None:
        print("Mahdi's flow_paths.gpkg not found — Part 2 written as PENDING")
    write_report(df, flow_src, unmatched, conflict_gpkg)
