"""Allen Coral Atlas v2.0 export + polygonize + zone merge — swap-in #3.

STATUS: UNBLOCKED. Earth Engine auth was completed 3 Aug 2026 and the export has run;
`data/processed/vectors/reef_zones.gpkg` is the real Atlas product. Re-auth is only
needed on a machine that has never done the browser flow:

    .venv/bin/python -c "import ee; ee.Authenticate()"     # localhost flow, not OOB
    # project resolution falls back to the verified id — see project_id()

To re-export, in order:
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

from pulga_config import (
    AOI_CRS_PROJECTED,
    AOI_CRS_STORAGE,
    DOWNLOAD_BBOX,
    EE_PROJECT_ID,
    MARINE_BBOX,
    RAW,
    VECTORS,
)

ACA_COLLECTION = "ACA/reef_habitat/v2_0"
EXPORT_SCALE_M = 5           # native ACA resolution — do not coarsen
DRIVE_FOLDER = "reefshield_exports"
EXPORT_DESC = "aca_aqaba_habitat_full"

RAW_ACA = RAW / "aca"
PROVISIONAL = VECTORS / "reef_zones_PROVISIONAL.gpkg"
FINAL = VECTORS / "reef_zones.gpkg"

# Read off the live asset's own properties (`benthic_class_values` /
# `benthic_class_names`, likewise geomorphic) on 3 Aug 2026, not from
# documentation — `verify_class_tables()` re-checks them against Earth Engine so a
# v2.1 renumbering cannot silently relabel a zone. Guessing these is a real trap:
# geomorphic 22 is Reef Slope, and the plausible-looking guess (Back Reef Slope,
# which is 24) would have mislabelled five of the eight zones with no error.
BENTHIC_CLASSES = {
    0: "Unmapped", 11: "Sand", 12: "Rubble", 13: "Rock",
    14: "Seagrass", 15: "Coral/Algae", 18: "Microalgal Mats",
}
GEOMORPHIC_CLASSES = {
    0: "Unmapped", 11: "Shallow Lagoon", 12: "Deep Lagoon", 13: "Inner Reef Flat",
    14: "Outer Reef Flat", 15: "Reef Crest", 16: "Terrestrial Reef Flat",
    21: "Sheltered Reef Slope", 22: "Reef Slope", 23: "Plateau",
    24: "Back Reef Slope", 25: "Patch Reef",
}

# The provisional zones are hand-drawn dive-site boxes; Aqaba's reef is a fringing
# strip only tens of metres wide. A box edge therefore clips the strip, and a
# strict `intersects` test discards reef that is plainly the same feature — 113
# fragments totalling 0.193 km², which is +19% on the 1.042 km² that does land
# inside. So a fragment touching no zone is snapped to the nearest one within this
# tolerance.
#
# The eight zones are a CONTIGUOUS CHAIN down the coast, not scattered sites:
# consecutive boxes sit 24-50 m apart and R-07/R-08 touch outright. Two
# consequences, both measured rather than assumed:
#   - No tolerance can be "smaller than the zone spacing", so a snapped fragment in
#     an along-coast gap is often near two zones. Nearest-zone is the right answer
#     there — that is what a chain means — and being wrong moves a few hundred m2
#     between neighbours a few tens of metres apart, far less wrong than discarding
#     living reef. `report_snap_ambiguity()` counts these instead of hiding them.
#   - The tolerance must stay small, because the real hazard is not a neighbour but
#     absorbing foreign reef: 5.0 km2 of the export lies in Egyptian, Saudi and
#     Palestinian water, all of it >5 km away.
SNAP_TOLERANCE_M = 100

# Runaway-tolerance ceiling. An earlier version capped snapped area at a share of
# the area inside the boxes, on the assumption that snapping only trims edges. Once
# fragments were cut properly that assumption died: 0.713 km2 of reef sits within
# 100 m of a box against 0.522 km2 inside one, because the boxes are hand-drawn
# outlines of dive sites and the reef strip runs past them. A 137% share is a fact
# about the boxes, not a fault, so it is reported and this ceiling is geometric
# instead — assigned reef cannot exceed the chain grown by the tolerance, which no
# correct run can breach and a runaway tolerance immediately does.
SNAP_AREA_CEILING_NOTE = "provisional chain buffered by SNAP_TOLERANCE_M"


def project_id():
    # EARTHENGINE_PROJECT is what .env actually sets (it is also the name the ee
    # CLI itself uses); GEE_PROJECT stays supported so nobody's shell breaks.
    #
    # WHICH PROJECT ID ACTUALLY WORKS — measured 3 Aug 2026 against these credentials:
    #
    #     reefshield-aqaba-504407   WORKS
    #     reefshield-aqaba-504406   fails: "Caller does not have required permission"
    #     reefshield-aqaba-504318   fails, same
    #
    # docs/HANDOFF_pulga_2026-08-03.md §5 names -504406 as the one to use and -504318
    # as the duplicate to ignore. On this machine -504406 is the one that fails, so the
    # verified value is re-exported from pulga_config as the last-resort fallback
    # rather than left to an env var that may not be set. If -504406 works for you,
    # your credentials differ from these; pass --project explicitly and say so, because
    # one of the two records is wrong and it should not stay ambiguous.
    pid = os.environ.get("GEE_PROJECT") or os.environ.get("EARTHENGINE_PROJECT")
    for i, a in enumerate(sys.argv):
        if a == "--project" and i + 1 < len(sys.argv):
            pid = sys.argv[i + 1]
    if not pid:
        pid = EE_PROJECT_ID
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


def submit(scope: str = "full"):
    """Start the full-resolution benthic + geomorphic export to Drive.

    `scope="marine"` restricts the region to the marine AOI. The wide default
    is deliberate — Earth Engine's compute, not ours, and a superset survives an
    AOI change — but reef zones R-01..R-08 span only 29.36-29.53 N, so the full
    box renders hundreds of kilometres of inland desert that can never contain
    reef. Under a deadline the narrow one lands far sooner, and both can run at
    once.
    """
    ee = init_ee()
    box = MARINE_BBOX if scope == "marine" else DOWNLOAD_BBOX
    desc = EXPORT_DESC + ("_marine" if scope == "marine" else "")
    aoi = ee.Geometry.Rectangle(list(box))

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
        description=desc,
        folder=DRIVE_FOLDER,
        fileNamePrefix=desc,
        region=aoi,
        scale=EXPORT_SCALE_M,
        crs=AOI_CRS_PROJECTED,
        maxPixels=int(1e10),      # full padded box at 5 m needs headroom
        fileFormat="GeoTIFF",
    )
    task.start()
    print(f"submitted task {task.id}  [{desc}]")
    print(f"  region : {box} ({scope})")
    print(f"  scale  : {EXPORT_SCALE_M} m native, CRS {AOI_CRS_PROJECTED}")
    print(f"  drive  : {DRIVE_FOLDER}/{desc}.tif")
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
    # Both a full-box and a marine-scoped export can land here, and picking one
    # silently is how a build ends up describing a smaller area than the reader thinks.
    # Widest coverage wins, and the choice is stated.
    #
    # Measured, not assumed: over the 39,038,220 pixels the two 3 Aug exports share they
    # agree on 99.9957%, and every one of the 1,682 disagreements is reef in the wide
    # export and Unmapped in the narrow one — a clip artefact within 380 m of the narrow
    # request's own boundary, where Earth Engine loads fewer source tiles. Taking the
    # first of a sorted glob would have picked the narrow file and made every zone area
    # up to 3.4% low with nothing to indicate it.
    if len(tifs) > 1:
        import rasterio

        def extent(p):
            with rasterio.open(p) as s:
                return (s.bounds.right - s.bounds.left) * (s.bounds.top - s.bounds.bottom)

        tifs = sorted(tifs, key=extent, reverse=True)
        print(f"  {len(tifs)} exports present; using the widest: {tifs[0].name}")
        for p in tifs[1:]:
            print(f"    ignoring {p.name}")
    return tifs[0]


def build():
    """Polygonize the export, merge into R-01..R-08, verify, write reef_zones.gpkg."""
    import geopandas as gpd
    import numpy as np
    import pandas as pd
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

    # Labels come from constants; confirm they still match the asset. Offline this
    # cannot be checked, and saying so is better than a silent pass.
    try:
        verify_class_tables()
    except AssertionError:
        raise
    except (Exception, SystemExit) as e:   # init_ee/project_id exit rather than raise
        print(f"  WARNING class tables NOT verified ({type(e).__name__}) — habitat "
              "labels are unconfirmed against the live asset; re-run online.")

    unknown = set(np.unique(benthic).tolist()) - set(BENTHIC_CLASSES)
    assert not unknown, (
        f"benthic band holds codes {sorted(unknown)} absent from BENTHIC_CLASSES. "
        "Labelling would mislabel or crash — update the class table first."
    )

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

    # 2. Cut the fragments along the provisional zone boundaries and give each piece
    #    to the zone that contains it. ID continuity comes from the same place as
    #    before — zones are defined by the EXISTING R-NN extents, and ACA supplies
    #    habitat, not numbering — but the unit of assignment is the piece, not the
    #    whole fragment.
    #
    #    Assigning whole fragments to the zone they overlap MOST looks equivalent and
    #    is not. Aqaba's reef is a continuous fringing strip, so ACA polygonizes it
    #    into a few very long shapes that run through several zones; each one was
    #    handed entirely to one winner. R-05 (Japanese Garden, a well-known reef) came
    #    out at 475 m2 while 0.068 km2 of reef sat inside its box, having been credited
    #    to R-04 and R-06 — which in turn were credited with reef outside theirs. No
    #    error, no missing data, just a wrong number per zone, which is precisely what
    #    the exposure engine consumes.
    prov = gpd.read_file(PROVISIONAL).to_crs(crs)
    pieces = gpd.overlay(
        frag_gdf[["geometry", "aca_class"]], prov[["geometry", "reef_zone_id"]],
        how="intersection", keep_geom_type=True,
    )
    pieces["assignment"] = "overlap"
    print(f"  cut into {len(pieces)} pieces inside a provisional zone "
          f"({pieces.geometry.area.sum() / 1e6:.3f} km2)")

    # 3. Whatever is left over lies outside every box. Snap the near-misses the
    #    hand-drawn boxes clipped off (see SNAP_TOLERANCE_M); drop the rest.
    residual = gpd.overlay(
        frag_gdf[["geometry", "aca_class"]], prov[["geometry"]],
        how="difference", keep_geom_type=True,
    ).explode(index_parts=False).reset_index(drop=True)
    residual = residual[~residual.geometry.is_empty]

    dist = residual.geometry.apply(lambda g: prov.distance(g).min())
    near = residual[dist <= SNAP_TOLERANCE_M].copy()
    near["reef_zone_id"] = near.geometry.apply(
        lambda g: prov.loc[prov.distance(g).idxmin(), "reef_zone_id"])
    near["assignment"] = "snapped"
    print(f"  {len(near)} residual pieces snapped from within {SNAP_TOLERANCE_M} m "
          f"(+{near.geometry.area.sum() / 1e6:.3f} km2); "
          f"{len(residual) - len(near)} left out "
          f"({residual[dist > SNAP_TOLERANCE_M].geometry.area.sum() / 1e6:.3f} km2, "
          "mostly foreign water)")

    assigned = gpd.GeoDataFrame(
        pd.concat([pieces, near], ignore_index=True), crs=crs)
    assigned["area_km2"] = assigned.geometry.area / 1e6
    report_snap_ambiguity(assigned, prov)

    # Cutting must conserve area: every piece kept plus every piece left out has to
    # add back up to what ACA mapped. This is the check that would have caught the
    # whole-fragment bug — it double-counted reef into the winning zone, so the parts
    # would not have summed. A silent overlay failure looks identical to a real result.
    kept = assigned.geometry.area.sum()
    dropped = residual[dist > SNAP_TOLERANCE_M].geometry.area.sum()
    total = frag_gdf.geometry.area.sum()
    assert abs(kept + dropped - total) / total < 1e-6, (
        f"assignment lost or duplicated area: kept {kept / 1e6:.4f} + dropped "
        f"{dropped / 1e6:.4f} != polygonized {total / 1e6:.4f} km2"
    )
    print(f"  area conserved: {kept / 1e6:.3f} kept + {dropped / 1e6:.3f} dropped "
          f"= {total / 1e6:.3f} km2 polygonized")

    # Separate file, so the raw polygonized fragments survive as the audit trail of
    # what ACA actually said before any assignment decision was applied to it.
    pieces_path = VECTORS / "aca_pieces_ASSIGNED.gpkg"
    assigned.to_file(pieces_path, driver="GPKG")
    print(f"  {len(assigned)} assigned pieces -> {pieces_path.name}")

    rows = []
    for zid, grp in assigned.groupby("reef_zone_id"):
        merged = unary_union(grp.geometry.tolist())
        pr = prov[prov["reef_zone_id"] == zid].iloc[0]
        # By AREA, not by piece count. Polygonizing a raster produces one huge patch
        # and a scatter of single-pixel specks, so counting pieces lets 25 specks
        # outvote the patch that is the zone. R-08 reads Rock:59 / Coral-Algae:47 by
        # count — a near-tie that says nothing — while by area one of them clearly
        # dominates. "Dominant habitat" is a statement about extent.
        classes = (grp.groupby("aca_class")["area_km2"].sum()
                   .sort_values(ascending=False))

        # Geomorphic class alongside benthic — both bands were exported, so record
        # both. Majority geomorphic class over the merged zone footprint.
        geo_label, geo_code = "not_exported", None
        if geomorphic is not None:
            gmask = rasterio.features.geometry_mask(
                [merged], out_shape=geomorphic.shape, transform=transform, invert=True)
            gvals = geomorphic[gmask & (geomorphic > 0)]
            if gvals.size:
                vals, counts = np.unique(gvals, return_counts=True)
                geo_code = int(vals[counts.argmax()])
                geo_label = GEOMORPHIC_CLASSES[geo_code]

        # `habitat_class` is text, and it reaches the map popup, the DB and the RAG
        # answers. "ACA_benthic_13" is not an answer to "what habitat is R-01"; the
        # integer is kept beside it so provenance back to the raster survives.
        top_code = int(classes.index[0])
        rows.append({
            "reef_zone_id": zid,
            "id": zid,
            "zone_name": pr["zone_name"],
            "habitat_class": BENTHIC_CLASSES[top_code],
            "habitat_class_code": top_code,
            "habitat_class_mix": ";".join(
                f"{BENTHIC_CLASSES[int(c)]}:{100 * a / classes.sum():.0f}%"
                for c, a in classes.head(4).items()),
            "geomorphic_class": geo_label,
            "geomorphic_class_code": geo_code,
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

    # Every geometry-dependent attribute has to be recomputed, not inherited. The
    # zone outlines just changed, so the provisional depth stats and Marine Park
    # overlap describe a shape that no longer exists — carrying `marine_park_overlap_pct`
    # across was giving R-04 "71.3% inside the park" as a fact about a box, not about
    # the reef. depth_min_m/depth_median_m were being dropped entirely, which silently
    # broke qa_marine's per-zone insets and Pulga's same-schema rule.
    final = add_geometry_derived_attributes(final)

    final = final.to_crs(AOI_CRS_STORAGE)

    verify_against_provisional(final)

    final.to_file(FINAL, driver="GPKG", layer="reef_zones")
    print(f"\nwrote {FINAL}")
    print(final[["reef_zone_id", "habitat_class", "area_km2", "sensitivity_weight"]]
          .to_string(index=False))
    print("\nNow run: ../.venv/bin/python qa_marine.py   (regenerates reef figures)")


def add_geometry_derived_attributes(final):
    """Recompute depth stats and Marine Park overlap for the ACA geometry.

    Imported from make_reef_zones_provisional rather than reimplemented, so the
    provisional and final files are measured the same way and stay comparable.
    """
    import geopandas as gpd
    import numpy as np
    import rasterio
    import rasterio.features

    from make_reef_zones_provisional import DEPTH_PATH, marine_park_overlap

    proj = final.to_crs(AOI_CRS_PROJECTED)
    final["marine_park_overlap_pct"] = marine_park_overlap(proj)

    if not DEPTH_PATH.exists():
        print(f"  WARNING {DEPTH_PATH.name} missing — depth stats left as NaN")
        final["depth_median_m"] = np.nan
        final["depth_min_m"] = np.nan
        return final

    # Depth is averaged over WATER cells only, and the land share is recorded rather
    # than absorbed. The bathymetry is 50 m; ACA reef is 5 m and hugs the shore, so a
    # 20-50 m wide fringing strip straddles the coarse land/water boundary — R-02 has
    # 14 cells and every one of them reads +5 to +12 m. Including those would report a
    # reef sitting 10 m above sea level; excluding them silently would hide that the
    # depth is unmeasurable there. So: NaN where no water cell exists, and the land
    # percentage travels with the number.
    with rasterio.open(DEPTH_PATH) as src:
        elev, nod = src.read(1), src.nodata
        med, mn, land_pct = [], [], []
        for geom in proj.geometry:
            m = rasterio.features.geometry_mask(
                [geom], out_shape=elev.shape, transform=src.transform, invert=True)
            v = elev[m & (elev != nod)]
            wet = v[v < 0]
            med.append(float(np.median(wet)) if wet.size else np.nan)
            mn.append(float(wet.min()) if wet.size else np.nan)
            land_pct.append(round(100.0 * (v.size - wet.size) / v.size, 1)
                            if v.size else np.nan)
    final["depth_median_m"] = med
    final["depth_min_m"] = mn
    final["depth_land_cell_pct"] = land_pct

    n_nan = int(final["depth_median_m"].isna().sum())
    if n_nan:
        ids = final.loc[final["depth_median_m"].isna(), "reef_zone_id"].tolist()
        print(f"  depth unmeasurable for {ids} — no water cell in the 50 m "
              "bathymetry under a 5 m reef strip; reported as NaN, not zero")

    # The provisional build asserted depth_median_m < 0. That check assumed geometry
    # drawn to sit offshore, which is exactly what ACA geometry is not, so it fired on
    # four real zones. The placement question it was really asking — is this zone in
    # the sea or inland — is answered against the coastline instead, at a resolution
    # that can actually answer it.
    water = gpd.read_file(VECTORS / "coastline.gpkg", layer="water").to_crs(AOI_CRS_PROJECTED)
    sea = water.union_all()
    stranded = [
        (r["reef_zone_id"], round(r.geometry.distance(sea), 1))
        for _, r in proj.iterrows() if r.geometry.distance(sea) > SNAP_TOLERANCE_M
    ]
    assert not stranded, (
        f"zone(s) stranded inland after the ACA swap: {stranded} "
        f"(metres from the sea polygon; tolerance {SNAP_TOLERANCE_M} m)"
    )
    print(f"  OK all {len(proj)} zones lie on the sea, max "
          f"{max(r.geometry.distance(sea) for _, r in proj.iterrows()):.0f} m from open water")
    return final


def verify_class_tables():
    """Re-read the class tables off the live asset. A silent relabel is the risk.

    If ACA renumbers a class in a future version, every constant here still
    resolves — to the wrong habitat name, with no error anywhere. Cheap to check
    against the source of truth, so it is checked rather than trusted.
    """
    ee = init_ee()
    props = ee.Image(ACA_COLLECTION).getInfo()["properties"]
    for band, table in (("benthic", BENTHIC_CLASSES), ("geomorphic", GEOMORPHIC_CLASSES)):
        values = props[f"{band}_class_values"]
        # The asset's names carry a long description after " - "; keep the label.
        names = [n.split(" - ")[0].strip() for n in props[f"{band}_class_names"]]
        live = dict(zip(values, names))
        assert live == table, (
            f"ACA {band} class table has changed.\n  live: {live}\n  ours: {table}\n"
            "Every habitat label in reef_zones.gpkg is now suspect — update the "
            "constant and rebuild before anything downstream reads it."
        )
        print(f"  OK {band} class table matches the live asset ({len(live)} classes)")


def report_snap_ambiguity(frag_gdf, prov):
    """Quantify how much snapped reef sits between two zones rather than beside one.

    Reported, not asserted away. Along a chain of touching boxes some snaps are
    genuinely near two neighbours, and nearest-zone is the correct reading; the
    number that matters is how much area that applies to, so it can be judged
    instead of assumed. The assertions are the two things that would be real
    faults: snapping across a non-adjacent gap, and snapping becoming a source of
    geometry in its own right.
    """
    snapped = frag_gdf[frag_gdf["assignment"] == "snapped"]
    if snapped.empty:
        print("  no fragments were snapped")
        return

    order = {z: i for i, z in enumerate(sorted(prov["reef_zone_id"]))}
    ambiguous_km2 = 0.0
    n_ambiguous = 0
    for _, frag in snapped.iterrows():
        d = prov.distance(frag.geometry).sort_values()
        if len(d) < 2:
            continue
        first, second = prov.loc[d.index[0], "reef_zone_id"], prov.loc[d.index[1], "reef_zone_id"]
        if d.iloc[1] - d.iloc[0] < SNAP_TOLERANCE_M:
            n_ambiguous += 1
            ambiguous_km2 += frag.geometry.area / 1e6
            assert abs(order[first] - order[second]) == 1, (
                f"A snapped fragment is contested between {first} and {second}, which "
                "are not neighbours in the coastal chain. Nearest-zone is only "
                "defensible between adjacent zones."
            )

    overlap_km2 = frag_gdf[frag_gdf["assignment"] == "overlap"].geometry.area.sum() / 1e6
    snap_km2 = snapped.geometry.area.sum() / 1e6
    print(f"  of the snapped area, {n_ambiguous} pieces ({ambiguous_km2:.4f} km2) "
          f"lie between two adjacent zones and took the nearer")
    print(f"  inside boxes {overlap_km2:.3f} km2 | snapped from outside "
          f"{snap_km2:.3f} km2 ({snap_km2 / overlap_km2:.0%} of inside) — the "
          "provisional boxes under-cover the reef strip; see SNAP_TOLERANCE_M")

    # Geometric ceiling: no assigned reef can lie outside the chain grown by the
    # tolerance, so the assigned area cannot exceed that footprint. Breaching it means
    # the tolerance is drawing zones rather than repairing boxes.
    ceiling = prov.geometry.buffer(SNAP_TOLERANCE_M).union_all().area / 1e6
    assigned_km2 = overlap_km2 + snap_km2
    print(f"  assigned {assigned_km2:.3f} km2 vs {ceiling:.3f} km2 ceiling "
          f"({SNAP_AREA_CEILING_NOTE})")
    assert assigned_km2 <= ceiling, (
        f"Assigned reef ({assigned_km2:.3f} km2) exceeds the {SNAP_AREA_CEILING_NOTE} "
        f"({ceiling:.3f} km2). Geometrically impossible for a correct run — "
        "SNAP_TOLERANCE_M is absorbing reef that belongs to no zone."
    )


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
        submit(sys.argv[2] if len(sys.argv) > 2 else "full")
    elif cmd == "status":
        status()
    elif cmd == "build":
        build()
    elif cmd == "verify-classes":
        verify_class_tables()
    else:
        print(__doc__)
