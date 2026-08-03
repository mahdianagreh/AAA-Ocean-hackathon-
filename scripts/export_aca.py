"""Allen Coral Atlas v2.0 -> real reef_zones.gpkg. Contract swap-in #3.

Usage (Earth Engine auth is done — Karam completed it 3 Aug 2026):

    ../.venv/bin/python export_aca.py build     # vectorise in EE, write reef_zones.gpkg
    ../.venv/bin/python export_aca.py submit    # optional: full-res raster to Drive
    ../.venv/bin/python export_aca.py status    # poll a Drive task

TWO BUGS THIS FILE SHIPPED BEFORE AUTH EXISTED, BOTH FOUND THE MOMENT IT COULD RUN
---------------------------------------------------------------------------------
1. `ACA/reef_habitat/v2_0` is an **ee.Image**, not an ImageCollection. The old code
   called `ee.ImageCollection(...)` and would have died at submit with
   "Expected asset to be an ImageCollection, found 'Image'".
2. It exported over the **terrain** box. Reef habitat only exists in the sea, so that
   asked Earth Engine to render 19,700 km² of desert to find ~5 km² of reef. The
   export now uses MARINE_AOI, which is also what the plan specifies.

Neither was visible while the credentials were missing, which is worth recording: a
blocked step hides its own bugs, so "the script is ready" was a weaker claim than it
sounded.

WHY `build` VECTORISES IN EARTH ENGINE RATHER THAN VIA DRIVE
-----------------------------------------------------------
MARINE_AOI at 5 m is ~4,800 x 7,800 px per band — past `getDownloadURL`'s 32 MB cap,
so a raster round-trip needs Drive plus a manual download. But we do not need the
raster: we need polygons. `reduceToVectors` does the polygonisation server-side and
returns GeoJSON small enough to fetch directly, so the whole swap completes in one
command with no human step in the middle. `submit` is kept for anyone who wants the
raster itself.

CATEGORICAL DATA IS NEVER RESAMPLED. Class codes are labels, not quantities: averaging
11 (Sand) and 15 (Coral/Algae) yields 13 (Rock), which is a fabricated habitat. Every
reduction here runs at native scale with nearest-neighbour semantics.

THE ONE THING THAT MUST NOT GO WRONG
------------------------------------
R-01…R-08 must mean the SAME stretches of coast after the swap. ACA supplies habitat;
it does NOT get to renumber zones. Fragments are assigned to the EXISTING provisional
extents, and `verify_against_provisional` asserts no new IDs appear and no centroid
moves more than 5 km. Per contract §2, if ACA yields fewer zones the extras are
DROPPED and survivors keep their names.
"""

import json
import os
import sys

from pulga_config import (
    AOI_CRS_PROJECTED,
    AOI_CRS_STORAGE,
    EE_PROJECT_ID,
    MARINE_BBOX,
    RAW,
    VECTORS,
)

ACA_ASSET = "ACA/reef_habitat/v2_0"
NATIVE_SCALE_M = 5
DRIVE_FOLDER = "reefshield_exports"
EXPORT_DESC = "aca_aqaba_habitat_marine"

RAW_ACA = RAW / "aca"
PROVISIONAL = VECTORS / "reef_zones_PROVISIONAL.gpkg"
FINAL = VECTORS / "reef_zones.gpkg"
FRAGMENTS = VECTORS / "aca_fragments_BEFORE_MERGE.gpkg"

# Official class tables, read from the asset's own properties on 2026-08-03 rather
# than transcribed from a web page.
BENTHIC = {0: "Unmapped", 11: "Sand", 12: "Rubble", 13: "Rock", 14: "Seagrass",
           15: "Coral/Algae", 18: "Microalgal Mats"}
GEOMORPHIC = {0: "Unmapped", 11: "Shallow Lagoon", 12: "Deep Lagoon",
              13: "Inner Reef Flat", 14: "Outer Reef Flat", 15: "Reef Crest",
              16: "Terrestrial Reef Flat", 21: "Sheltered Reef Slope",
              22: "Reef Slope", 23: "Plateau", 24: "Back Reef Slope",
              25: "Patch Reef"}

# Benthic classes that are living reef habitat for exposure purposes. Sand, rubble and
# rock are mapped substrate, not the thing the platform protects; including them would
# inflate "reef area" with bare seabed.
LIVING_BENTHIC = {14, 15}  # Seagrass, Coral/Algae


def project_id():
    pid = (os.environ.get("GEE_PROJECT") or os.environ.get("EE_PROJECT_ID")
           or EE_PROJECT_ID)
    for i, a in enumerate(sys.argv):
        if a == "--project" and i + 1 < len(sys.argv):
            pid = sys.argv[i + 1]
    if not pid:
        sys.exit("No Earth Engine project. Set GEE_PROJECT or pass --project.")
    return pid


def init_ee():
    try:
        import ee
    except ImportError:
        sys.exit("earthengine-api not installed")
    try:
        ee.Initialize(project=project_id())
    except Exception as e:
        sys.exit(
            f"Earth Engine init failed: {type(e).__name__}\n{str(e)[:300]}\n\n"
            'Authorise once with:  .venv/bin/python -c "import ee; ee.Authenticate()"'
        )
    return ee


def aca_image(ee):
    """The ACA image and our AOI. One place that knows the asset is an Image."""
    return ee.Image(ACA_ASSET), ee.Geometry.Rectangle(list(MARINE_BBOX))


# --------------------------------------------------------------------- vectorise

def build():
    """Vectorise ACA benthic habitat in EE, merge onto existing zone IDs, write GPKG."""
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import shape
    from shapely.ops import unary_union

    ee = init_ee()
    img, aoi = aca_image(ee)
    print(f"ACA asset  : {ACA_ASSET} (ee.Image)")
    print(f"extent     : MARINE_AOI {MARINE_BBOX}")
    print(f"scale      : {NATIVE_SCALE_M} m native, no resampling")

    benthic = img.select("benthic").clip(aoi)

    # Server-side polygonisation. `reduceToVectors` groups contiguous equal-valued
    # pixels, so each output feature is one habitat patch carrying its class code.
    vectors = benthic.reduceToVectors(
        geometry=aoi,
        scale=NATIVE_SCALE_M,
        geometryType="polygon",
        eightConnected=False,
        labelProperty="benthic_code",
        reducer=ee.Reducer.countEvery(),
        maxPixels=int(1e10),
        bestEffort=False,
    )

    n = vectors.size().getInfo()
    print(f"  polygonised {n} benthic patches")
    if n == 0:
        sys.exit("ACA returned no benthic polygons over MARINE_AOI — investigate "
                 "before assuming there is no reef.")

    fc = vectors.getInfo()
    rows = []
    for feat in fc["features"]:
        code = int(feat["properties"]["benthic_code"])
        rows.append({
            "benthic_code": code,
            "benthic_class": BENTHIC.get(code, f"unknown_{code}"),
            "is_living_reef": code in LIVING_BENTHIC,
            "geometry": shape(feat["geometry"]),
        })

    frags = gpd.GeoDataFrame(rows, crs=AOI_CRS_STORAGE)
    frags["area_km2"] = frags.to_crs(AOI_CRS_PROJECTED).geometry.area / 1e6
    FRAGMENTS.parent.mkdir(parents=True, exist_ok=True)
    frags.to_file(FRAGMENTS, driver="GPKG")

    by_class = (frags.groupby("benthic_class")["area_km2"]
                .agg(["count", "sum"]).sort_values("sum", ascending=False))
    print("\n  benthic composition over MARINE_AOI:")
    for cls, r in by_class.iterrows():
        living = " (living reef)" if cls in ("Coral/Algae", "Seagrass") else ""
        print(f"    {cls:18s} {int(r['count']):5d} patches  {r['sum']:7.3f} km2{living}")
    print(f"  wrote {FRAGMENTS.name} — every fragment, before merge")

    # ---- assign fragments to the EXISTING zone extents -----------------------
    prov = gpd.read_file(PROVISIONAL)
    prov_utm = prov.to_crs(AOI_CRS_PROJECTED)
    frags_utm = frags.to_crs(AOI_CRS_PROJECTED)

    living = frags_utm[frags_utm["is_living_reef"]].copy()
    print(f"\n  {len(living)} living-reef patches "
          f"({living['area_km2'].sum():.3f} km2) to distribute across zones")

    # A provisional zone is a 250 m strip; real ACA habitat can sit just outside it,
    # so match on nearest-within-tolerance rather than strict intersection. 400 m is
    # the strip width plus a margin, and it is recorded in the output so the choice
    # is auditable rather than buried.
    MATCH_TOLERANCE_M = 400.0
    assigned = gpd.sjoin_nearest(
        living, prov_utm[["reef_zone_id", "zone_name", "geometry"]],
        how="left", max_distance=MATCH_TOLERANCE_M, distance_col="dist_m",
    )
    matched = assigned[assigned["reef_zone_id"].notna()]
    print(f"  {len(matched)}/{len(living)} matched within {MATCH_TOLERANCE_M:.0f} m "
          f"of a provisional zone")

    out_rows = []
    for zid, grp in matched.groupby("reef_zone_id"):
        merged = unary_union(grp.geometry.tolist())
        pr = prov[prov["reef_zone_id"] == zid].iloc[0]
        mix = grp.groupby("benthic_class")["area_km2"].sum().sort_values(ascending=False)

        geo_label = _geomorphic_majority(ee, merged)

        out_rows.append({
            "reef_zone_id": zid,
            "id": zid,
            "zone_name": pr["zone_name"],
            "habitat_class": mix.index[0],
            "habitat_class_mix": "; ".join(f"{k}:{v:.4f}km2" for k, v in mix.items()),
            "geomorphic_class": geo_label,
            # STILL a placeholder. Real habitat data arriving does NOT make this a
            # measurement — ACA maps habitat, not sensitivity.
            "sensitivity_weight": 1.0,
            "sensitivity_weight_status": "PLACEHOLDER_PENDING_MARINE_SCIENTIST",
            "provisional": False,
            "geom_basis": (f"Allen Coral Atlas v2.0 benthic, {NATIVE_SCALE_M} m, "
                           f"living-reef classes merged per zone "
                           f"(match tolerance {MATCH_TOLERANCE_M:.0f} m)"),
            "source": ACA_ASSET,
            "marine_park_overlap_pct": pr.get("marine_park_overlap_pct"),
            "geometry": merged,
        })

    if not out_rows:
        sys.exit("No living-reef patch matched any provisional zone — refusing to "
                 "write an empty reef_zones.gpkg.")

    final = gpd.GeoDataFrame(out_rows, crs=AOI_CRS_PROJECTED)
    final["area_km2"] = final.geometry.area / 1e6
    final = final.sort_values("reef_zone_id").reset_index(drop=True).to_crs(AOI_CRS_STORAGE)

    verify_against_provisional(final, prov)

    final.to_file(FINAL, driver="GPKG", layer="reef_zones")
    print(f"\nwrote {FINAL}")
    cols = ["reef_zone_id", "habitat_class", "geomorphic_class", "area_km2",
            "sensitivity_weight"]
    print(final[cols].to_string(index=False))
    print(f"\ntotal real reef area: {final.area_km2.sum():.3f} km2 "
          f"across {len(final)} zones "
          f"(provisional claimed {prov['area_km2'].sum():.2f} km2 across {len(prov)})")
    print("\nNext: ../.venv/bin/python qa_marine.py   (regenerates reef figures)")


def _geomorphic_majority(ee, geom_utm) -> str:
    """Majority ACA geomorphic class over one merged zone, at native scale."""
    import geopandas as gpd

    ll = gpd.GeoSeries([geom_utm], crs=AOI_CRS_PROJECTED).to_crs(AOI_CRS_STORAGE).iloc[0]
    try:
        img, _ = aca_image(ee)
        hist = (img.select("geomorphic")
                .reduceRegion(reducer=ee.Reducer.frequencyHistogram(),
                              geometry=ee.Geometry(json.loads(
                                  gpd.GeoSeries([ll]).to_json())["features"][0]["geometry"]),
                              scale=NATIVE_SCALE_M, maxPixels=int(1e9))
                .getInfo().get("geomorphic") or {})
        counts = {int(float(k)): v for k, v in hist.items() if float(k) > 0}
        if not counts:
            return "Unmapped"
        top = max(counts, key=counts.get)
        return GEOMORPHIC.get(top, f"unknown_{top}")
    except Exception as e:
        return f"unavailable ({type(e).__name__})"


def verify_against_provisional(final, prov=None, max_centroid_shift_km=5.0):
    """The assertion that protects every stored exposure result."""
    import geopandas as gpd

    if prov is None:
        prov = gpd.read_file(PROVISIONAL)

    p_ids, f_ids = set(prov["reef_zone_id"]), set(final["reef_zone_id"])
    added, dropped = f_ids - p_ids, p_ids - f_ids

    assert not added, (
        f"NEW zone IDs appeared: {sorted(added)}. ACA supplies habitat for the "
        "EXISTING R-NN extents; it does not get to invent IDs. Contract §2 forbids "
        "renumbering."
    )
    if dropped:
        print(f"\n  NOTE: {sorted(dropped)} have no ACA living-reef habitat and are "
              "dropped.\n  Contract §2 allows this — survivors keep their names, "
              "nothing is renumbered.")

    pm = prov.to_crs(AOI_CRS_PROJECTED).set_index("reef_zone_id").geometry.centroid
    fm = final.to_crs(AOI_CRS_PROJECTED).set_index("reef_zone_id").geometry.centroid
    print("\n  centroid drift, provisional -> ACA:")
    worst = 0.0
    for zid in sorted(f_ids):
        d_km = pm[zid].distance(fm[zid]) / 1000
        worst = max(worst, d_km)
        print(f"    {zid}: {d_km:6.3f} km")
        assert d_km < max_centroid_shift_km, (
            f"{zid} centroid moved {d_km:.2f} km, over the "
            f"{max_centroid_shift_km} km bound — IDs have probably been shuffled."
        )
    print(f"  OK {len(f_ids)}/{len(p_ids)} zones confirmed, no new IDs, "
          f"worst drift {worst:.3f} km")


# ------------------------------------------------------- optional Drive raster

def submit():
    ee = init_ee()
    img, aoi = aca_image(ee)
    stacked = img.select(["benthic", "geomorphic", "reef_mask"]).clip(aoi).toInt16()
    task = ee.batch.Export.image.toDrive(
        image=stacked, description=EXPORT_DESC, folder=DRIVE_FOLDER,
        fileNamePrefix=EXPORT_DESC, region=aoi, scale=NATIVE_SCALE_M,
        crs=AOI_CRS_PROJECTED, maxPixels=int(1e10), fileFormat="GeoTIFF",
    )
    task.start()
    print(f"submitted {task.id} [{EXPORT_DESC}] over MARINE_AOI at {NATIVE_SCALE_M} m")
    print("monitor: https://code.earthengine.google.com/tasks")


def status():
    ee = init_ee()
    tasks = [t for t in ee.batch.Task.list() if EXPORT_DESC in str(t.config)]
    if not tasks:
        print(f"no task matching {EXPORT_DESC!r}")
        return
    for t in tasks[:5]:
        st = t.status()
        print(f"  {st.get('id')}  {st.get('state')}")
        if st.get("error_message"):
            print(f"    error: {st['error_message']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "build":
        build()
    elif cmd == "submit":
        submit()
    elif cmd == "status":
        status()
    else:
        print(__doc__)
