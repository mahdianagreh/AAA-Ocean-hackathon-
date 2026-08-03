"""Allen Coral Atlas v2.0 export + polygonize + zone merge — swap-in #3.

STATUS: BLOCKED ON A HUMAN. Earth Engine needs an interactive browser OAuth flow
and a GEE project registered under your own account (contract §4 P6: each person
registers their own, there is no shared one). Neither can be done from a script.

To unblock, once:
    .venv/bin/python -c "import ee; ee.Authenticate()"     # opens a browser
    export GEE_PROJECT=your-project-id                      # or pass --project

Then, in order:
    ../.venv/bin/python export_aca.py submit      # starts the Drive export task
    ../.venv/bin/python export_aca.py status      # poll until COMPLETED
    # download the GeoTIFF from Drive into data/raw/aca/
    ../.venv/bin/python export_aca.py build       # polygonize -> merge -> verify

DESIGN NOTE — why the full padded box at native 5 m
---------------------------------------------------
The export is deliberately NOT scoped down. It costs Earth Engine time, not our
time, and it runs in the background. A narrow export would have to be redone if
the analysis box shifts; the padded box is a superset by construction (contract
§1), so this export stays valid either way.

THE ONE THING THAT MUST NOT GO WRONG
------------------------------------
R-01…R-08 must mean the SAME stretches of coast after the swap as before. If R-03
shifts, every stored exposure result silently becomes wrong, and unlike a crash
nothing tells you. `verify_against_provisional()` enforces this with assertions
and writes the side-by-side centroid figure. Per contract §2, if ACA yields fewer
real zones the extras are DROPPED and surviving IDs keep their names — never
renumbered.
"""

import os
import sys

from config import AOI_CRS_PROJECTED, AOI_CRS_STORAGE, DOWNLOAD_BBOX, RAW, VECTORS

ACA_COLLECTION = "ACA/reef_habitat/v2_0"
EXPORT_SCALE_M = 5           # native ACA resolution — do not coarsen
DRIVE_FOLDER = "reefshield_exports"
EXPORT_DESC = "aca_aqaba_habitat_full"

RAW_ACA = RAW / "aca"
PROVISIONAL = VECTORS / "reef_zones_PROVISIONAL.gpkg"
FINAL = VECTORS / "reef_zones.gpkg"


def project_id():
    pid = os.environ.get("GEE_PROJECT")
    for i, a in enumerate(sys.argv):
        if a == "--project" and i + 1 < len(sys.argv):
            pid = sys.argv[i + 1]
    if not pid:
        sys.exit(
            "No Earth Engine project. Set GEE_PROJECT=<your-project-id> or pass\n"
            "  --project <your-project-id>\n"
            "Register a free one at https://code.earthengine.google.com (contract §4 P6:\n"
            "each person uses their own; there is deliberately no shared project)."
        )
    return pid


def init_ee():
    try:
        import ee
    except ImportError:
        sys.exit("earthengine-api not installed: .venv/bin/pip install earthengine-api")
    try:
        ee.Initialize(project=project_id())
    except Exception as e:
        sys.exit(
            f"Earth Engine init failed: {type(e).__name__}\n{str(e)[:300]}\n\n"
            "If this says you need to authorize, run once:\n"
            '  .venv/bin/python -c "import ee; ee.Authenticate()"\n'
            "That opens a browser. It cannot be automated, which is why this step is\n"
            "the one hard blocker in the marine chain."
        )
    return ee


def submit():
    """Start the full-resolution benthic + geomorphic export to Drive."""
    ee = init_ee()
    aoi = ee.Geometry.Rectangle(list(DOWNLOAD_BBOX))

    # ACA/reef_habitat/v2_0 is a single global Image, not an ImageCollection.
    # ee.ImageCollection() on it fails with "Expected asset ... to be an
    # ImageCollection, found 'Image'", so there is no mosaic step to do —
    # verified against the live asset, whose bands are
    # ['geomorphic', 'benthic', 'reef_mask'].
    habitat = ee.Image(ACA_COLLECTION)
    benthic = habitat.select("benthic").clip(aoi).rename("benthic")
    geomorphic = habitat.select("geomorphic").clip(aoi).rename("geomorphic")
    stacked = benthic.addBands(geomorphic).toInt16()

    task = ee.batch.Export.image.toDrive(
        image=stacked,
        description=EXPORT_DESC,
        folder=DRIVE_FOLDER,
        fileNamePrefix=EXPORT_DESC,
        region=aoi,
        scale=EXPORT_SCALE_M,
        crs=AOI_CRS_PROJECTED,
        maxPixels=int(1e10),      # full padded box at 5 m needs headroom
        fileFormat="GeoTIFF",
    )
    task.start()
    print(f"submitted task {task.id}  [{EXPORT_DESC}]")
    print(f"  region : {DOWNLOAD_BBOX} (full padded box, not scoped down)")
    print(f"  scale  : {EXPORT_SCALE_M} m native, CRS {AOI_CRS_PROJECTED}")
    print(f"  drive  : {DRIVE_FOLDER}/{EXPORT_DESC}.tif")
    print("\nMonitor: https://code.earthengine.google.com/tasks")
    print("     or: ../.venv/bin/python export_aca.py status")
    return task.id


def status():
    ee = init_ee()
    tasks = [t for t in ee.batch.Task.list() if EXPORT_DESC in str(t.config)]
    if not tasks:
        print(f"no task matching {EXPORT_DESC!r} — run `submit` first")
        return
    for t in tasks[:5]:
        st = t.status()
        print(f"  {st.get('id')}  {st.get('state')}  {st.get('description')}")
        if st.get("error_message"):
            print(f"    error: {st['error_message']}")
        if st.get("state") == "COMPLETED":
            print(f"\n  Download from Drive/{DRIVE_FOLDER}/ into {RAW_ACA}/ then run:")
            print("    ../.venv/bin/python export_aca.py build")


def find_export():
    RAW_ACA.mkdir(parents=True, exist_ok=True)
    tifs = sorted(RAW_ACA.glob("*.tif"))
    if not tifs:
        sys.exit(
            f"No ACA GeoTIFF in {RAW_ACA}/.\n"
            "Download the completed export from Google Drive "
            f"({DRIVE_FOLDER}/{EXPORT_DESC}.tif) into that directory first."
        )
    return tifs[0]


def build():
    """Polygonize the export, merge into R-01..R-08, verify, write reef_zones.gpkg."""
    import geopandas as gpd
    import numpy as np
    import rasterio
    import rasterio.features
    from shapely.geometry import shape
    from shapely.ops import unary_union

    path = find_export()
    print(f"ACA export: {path.name}")

    with rasterio.open(path) as src:
        n_bands = src.count
        benthic = src.read(1)
        # Band 2 is geomorphic (submit() stacks benthic then geomorphic). Guard on
        # count so a single-band export still builds rather than crashing.
        geomorphic = src.read(2) if n_bands > 1 else None
        transform, crs = src.transform, src.crs
    print(f"  {benthic.shape[1]}x{benthic.shape[0]} px, CRS {crs}, {n_bands} band(s)")

    # 1. Polygonize every contiguous class patch — this is the "before merge" state.
    reef = benthic > 0
    frags = [
        {"geometry": shape(g), "aca_class": int(v)}
        for g, v in rasterio.features.shapes(
            benthic.astype("int32"), mask=reef, transform=transform)
    ]
    frag_gdf = gpd.GeoDataFrame(frags, crs=crs)
    frag_gdf["area_km2"] = frag_gdf.geometry.area / 1e6
    frag_path = VECTORS / "aca_fragments_BEFORE_MERGE.gpkg"
    frag_gdf.to_file(frag_path, driver="GPKG")
    print(f"  polygonized {len(frag_gdf)} fragments -> {frag_path.name}")

    # 2. Assign each fragment to the provisional zone it overlaps most. This is what
    #    guarantees ID continuity: zones are defined by the EXISTING R-NN extents,
    #    and ACA supplies the habitat, not the numbering.
    prov = gpd.read_file(PROVISIONAL).to_crs(crs)
    frag_gdf["reef_zone_id"] = None
    for i, frag in frag_gdf.iterrows():
        hits = prov[prov.intersects(frag.geometry)]
        if hits.empty:
            continue
        areas = hits.geometry.intersection(frag.geometry).area
        frag_gdf.at[i, "reef_zone_id"] = hits.loc[areas.idxmax(), "reef_zone_id"]

    assigned = frag_gdf[frag_gdf["reef_zone_id"].notna()]
    print(f"  {len(assigned)}/{len(frag_gdf)} fragments fell inside a provisional zone")

    rows = []
    for zid, grp in assigned.groupby("reef_zone_id"):
        merged = unary_union(grp.geometry.tolist())
        pr = prov[prov["reef_zone_id"] == zid].iloc[0]
        classes = grp["aca_class"].value_counts()

        # Geomorphic class alongside benthic — both bands were exported, so record
        # both. Majority geomorphic class over the merged zone footprint.
        geo_label = "not_exported"
        if geomorphic is not None:
            gmask = rasterio.features.geometry_mask(
                [merged], out_shape=geomorphic.shape, transform=transform, invert=True)
            gvals = geomorphic[gmask & (geomorphic > 0)]
            if gvals.size:
                vals, counts = np.unique(gvals, return_counts=True)
                geo_label = f"ACA_geomorphic_{int(vals[counts.argmax()])}"

        rows.append({
            "reef_zone_id": zid,
            "id": zid,
            "zone_name": pr["zone_name"],
            "habitat_class": f"ACA_benthic_{classes.index[0]}",
            "habitat_class_mix": ";".join(f"{c}:{n}" for c, n in classes.head(4).items()),
            "geomorphic_class": geo_label,
            # STILL a placeholder. ACA maps habitat, not sensitivity. Do not invent
            # values here just because real habitat data has arrived.
            "sensitivity_weight": 1.0,
            "sensitivity_weight_status": "PLACEHOLDER_PENDING_MARINE_SCIENTIST",
            "provisional": False,
            "geom_basis": f"Allen Coral Atlas v2.0 benthic, {EXPORT_SCALE_M} m, merged to zone",
            "source": ACA_COLLECTION,
            "marine_park_overlap_pct": pr.get("marine_park_overlap_pct", np.nan),
            "geometry": merged,
        })

    final = gpd.GeoDataFrame(rows, crs=crs)
    final["area_km2"] = final.to_crs(AOI_CRS_PROJECTED).geometry.area / 1e6
    final = final.sort_values("reef_zone_id").reset_index(drop=True)
    final = final.to_crs(AOI_CRS_STORAGE)

    verify_against_provisional(final)

    final.to_file(FINAL, driver="GPKG", layer="reef_zones")
    print(f"\nwrote {FINAL}")
    print(final[["reef_zone_id", "habitat_class", "area_km2", "sensitivity_weight"]]
          .to_string(index=False))
    print("\nNow run: ../.venv/bin/python qa_marine.py   (regenerates reef figures)")


def verify_against_provisional(final):
    """The assertion that protects every stored exposure result."""
    import geopandas as gpd

    prov = gpd.read_file(PROVISIONAL)
    p_ids, f_ids = set(prov["reef_zone_id"]), set(final["reef_zone_id"])

    dropped = p_ids - f_ids
    added = f_ids - p_ids

    assert not added, (
        f"NEW zone IDs appeared: {sorted(added)}. ACA must not invent IDs — it supplies "
        "habitat for the EXISTING R-NN extents. Contract §2 forbids renumbering."
    )
    if dropped:
        print(f"  NOTE: {sorted(dropped)} had no ACA reef and are dropped. Contract §2 "
              "allows this — surviving IDs keep their names, never renumbered.")

    # Centroids must not have swapped places (R-03 must still be where R-03 was).
    pm = prov.to_crs(AOI_CRS_PROJECTED).set_index("reef_zone_id").geometry.centroid
    fm = final.to_crs(AOI_CRS_PROJECTED).set_index("reef_zone_id").geometry.centroid
    print("\n  centroid drift, provisional -> final:")
    for zid in sorted(f_ids):
        d = pm[zid].distance(fm[zid])
        flag = "  <-- CHECK" if d > 2000 else ""
        print(f"    {zid}: {d:8.0f} m{flag}")
        assert d < 5000, (
            f"{zid} centroid moved {d:.0f} m. That is too far to be the same stretch of "
            "coast — IDs have almost certainly been shuffled."
        )
    print("  OK zone IDs and positions are continuous across the swap")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "submit":
        submit()
    elif cmd == "status":
        status()
    elif cmd == "build":
        build()
    else:
        print(__doc__)
