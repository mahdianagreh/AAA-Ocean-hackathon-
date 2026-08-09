"""P4 · Provisional reef zones — contract §4, Day 1.

Publishes 8 zones named R-01…R-08 north to south:

    data/processed/vectors/reef_zones_PROVISIONAL.gpkg

WHY THIS EXISTS: the exposure engine and the dashboard join on `reef_zone_id`.
They can be built end-to-end against these polygons while the real Allen Coral
Atlas export is prepared. The IDs and the count here are a CONTRACT — they must
survive unchanged into reef_zones.gpkg or every stored exposure result silently
becomes wrong (contract §5, swap-in #3).

GEOGRAPHY: Jordan holds the ~22 km eastern shore of the head of the Gulf of
Aqaba, from the Palestinian border (~29.538 N) to the Saudi border (~29.356 N). The
sea lies WEST of the shoreline, so every reef strip extends to LOWER easting
from the coast. Getting this backwards puts every zone on dry land.

HOW THE GEOMETRY IS DERIVED — and what is trustworthy in it
-----------------------------------------------------------
A first pass placed these boxes using a hand-fitted straight-line shoreline.
Checking it against the bathymetry showed it was ~600 m too far east at R-03…
R-05 (those boxes sat on dry land, +7 to +18 m elevation) and too far west at
R-07…R-08 (in 250-400 m of open water). Hand-fitting a curved coast does not
work. So:

  * ALONG-SHORE position is derived from the real water mask in
    depth_utm36n.tif — for each raster row we take the easternmost sea pixel.
    This is reliable to about one pixel (~50 m).

  * SEAWARD EXTENT is a flat assumption: REEF_STRIP_M metres from the shore.
    It is NOT derived from depth, deliberately. The Gulf of Aqaba drop-off is
    far steeper than the ~450 m true resolution of the bathymetry can resolve
    (the grid claims -372 m only 100 m offshore at R-02, which is an
    interpolation artefact, not a real slope). Deriving a reef edge from those
    contours would dress an artefact up as a measurement. The real seaward
    boundary comes from Allen Coral Atlas at the swap-in.

So: the zones are in the right PLACE along the coast, and their WIDTH is a
placeholder. Treat area_km2 accordingly — it is order-of-magnitude only.
"""

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.features
from pyproj import Transformer
from shapely.geometry import LineString, MultiPolygon
from shapely.geometry import box as shp_box
from shapely.ops import unary_union

from pulga_config import (
    AOI_CRS_PROJECTED,
    AOI_CRS_STORAGE,
    DOWNLOAD_BBOX,
    PROCESSED,
    VECTORS,
)

# Provisional seaward extent of the fringing reef. Aqaba's fringing reef is
# genuinely narrow; 250 m is a defensible placeholder, not a measurement.
REEF_STRIP_M = 250.0

# Jordanian coast limits. North: the Palestine/Jordan border meets the sea near
# 29.538 N — north of this is Eilat, not ours. South: the Saudi border at
# ~29.356 N. Clipping to this range keeps the zones on Jordanian coast.
JORDAN_LAT_N = 29.5360
JORDAN_LAT_S = 29.3560

# Zones ordered north -> south so the sequence is inferable without a legend.
# Latitudes follow the published positions of well-known Aqaba dive sites and
# the Aqaba Marine Park stretch.
ZONE_DEFS = [
    ("R-01", "North Aqaba / Ayla & Public Beach", 29.5300, 29.5050),
    ("R-02", "Port frontage / First Bay & Power Station", 29.5050, 29.4800),
    ("R-03", "Tourist Camp / north Marine Park boundary", 29.4800, 29.4620),
    ("R-04", "Marine Science Station / Cedar Pride", 29.4620, 29.4500),
    ("R-05", "Japanese Garden / Gorgonian", 29.4500, 29.4380),
    ("R-06", "Black Rock / Blue Coral", 29.4380, 29.4200),
    ("R-07", "Tala Bay / Seven Sisters", 29.4200, 29.4000),
    ("R-08", "Royal Diving Club / Yamanieh to Saudi border", 29.4000, 29.3560),
]

DEPTH_PATH = PROCESSED / "bathymetry" / "depth_utm36n.tif"


def jordan_shore_points():
    """Easternmost sea pixel per raster row = the Jordanian shoreline, in UTM."""
    if not DEPTH_PATH.exists():
        raise FileNotFoundError(
            f"{DEPTH_PATH} missing — run process_bathymetry.py first. The reef "
            "zones are anchored to the water mask, so bathymetry comes first."
        )
    with rasterio.open(DEPTH_PATH) as src:
        elev = src.read(1)
        water = (elev < 0) & (elev != src.nodata)

        t = Transformer.from_crs(AOI_CRS_STORAGE, AOI_CRS_PROJECTED, always_xy=True)
        _, north_n = t.transform(35.0, JORDAN_LAT_N)
        _, north_s = t.transform(35.0, JORDAN_LAT_S)

        pts = []
        for row in range(water.shape[0]):
            cols = np.where(water[row])[0]
            if len(cols) == 0:
                continue
            easting, northing = src.xy(row, cols.max())
            if north_s <= northing <= north_n:
                pts.append((easting, northing))

    pts.sort(key=lambda p: -p[1])  # north -> south
    print(f"  traced {len(pts)} shoreline points, "
          f"easting {min(p[0] for p in pts):.0f}-{max(p[0] for p in pts):.0f}")
    return pts


def marine_park_overlap(gdf):
    """Fraction of each zone inside the Aqaba Marine Park, from OSM.

    This is REAL data, and it is the first evidence-based input available for
    `sensitivity_weight`: a reef inside a legally protected reserve is a
    different management proposition from port frontage. It is deliberately
    stored as the raw overlap percentage and NOT converted into a weight — that
    conversion is the marine scientist's call, not ours. Handing them a measured
    number is useful; inventing a weight from it would be the exact failure the
    risk register warns about.

    Returns a list of percentages, or NaN if OSM has no protected area (the
    layer is optional, so a missing one must not break the reef zone build).
    """
    pa_path = VECTORS / "osm_aqaba.gpkg"
    if not pa_path.exists():
        return [float("nan")] * len(gdf)
    try:
        pa = gpd.read_file(pa_path, layer="protected_areas").to_crs(AOI_CRS_PROJECTED)
    except Exception:
        return [float("nan")] * len(gdf)

    park = pa[pa["protection_title"] == "Marine Park"]
    if park.empty:
        return [float("nan")] * len(gdf)

    park_geom = unary_union(park.geometry.tolist())
    return [
        round(g.intersection(park_geom).area / g.area * 100.0, 1) if g.area else float("nan")
        for g in gdf.geometry
    ]


def build():
    pts = jordan_shore_points()

    # Sea polygon, used to keep every strip on the water side of the shore.
    water_poly = unary_union(
        gpd.read_file(VECTORS / "coastline.gpkg", layer="water")
        .to_crs(AOI_CRS_PROJECTED)
        .geometry.tolist()
    )

    t = Transformer.from_crs(AOI_CRS_STORAGE, AOI_CRS_PROJECTED, always_xy=True)
    rows = []
    for zone_id, zone_name, lat_n, lat_s in ZONE_DEFS:
        _, n_max = t.transform(35.0, lat_n)
        _, n_min = t.transform(35.0, lat_s)
        seg = [p for p in pts if n_min <= p[1] <= n_max]
        if len(seg) < 2:
            raise RuntimeError(f"{zone_id}: only {len(seg)} shore points in band")

        shore = LineString(seg)
        # Buffer both ways then intersect with the sea: this keeps exactly the
        # seaward REEF_STRIP_M and never leaks onto land, whatever direction the
        # coast happens to run at this latitude.
        strip = shore.buffer(REEF_STRIP_M, cap_style=2).intersection(water_poly)

        # Clip back to the zone's own latitude band. Where the coast bends the
        # perpendicular buffer bleeds across the band boundary into the
        # neighbouring zone; without this, R-04 and R-05 overlap by ~1.5 ha and
        # any reef area inside the overlap is counted twice in the exposure score.
        wminx, _, wmaxx, _ = water_poly.bounds
        strip = strip.intersection(shp_box(wminx, n_min, wmaxx, n_max))

        if strip.is_empty:
            raise RuntimeError(f"{zone_id}: strip is empty — check the water mask")
        if isinstance(strip, MultiPolygon):
            strip = max(strip.geoms, key=lambda g: g.area)  # drop slivers

        rows.append(
            {
                "reef_zone_id": zone_id,
                # `id` duplicates `reef_zone_id`: contract §3 names the column
                # `id`, the implementation plan uses `reef_zone_id`. Carrying
                # both means either join key works and nobody has to guess.
                "id": zone_id,
                "zone_name": zone_name,
                "habitat_class": "unknown",
                "sensitivity_weight": 1.0,
                # Labelled in the FILE SCHEMA, not only in the docs — the risk
                # register's concern is teammates treating 1.0 as real data.
                "sensitivity_weight_status": "PLACEHOLDER_PENDING_MARINE_SCIENTIST",
                "provisional": True,
                "geom_basis": f"water-mask shoreline + {REEF_STRIP_M:.0f}m assumed strip",
                "source": "NOT Allen Coral Atlas — provisional, replace at swap-in #3",
                "geometry": strip,
            }
        )

    gdf = gpd.GeoDataFrame(rows, crs=AOI_CRS_PROJECTED)
    gdf["area_km2"] = gdf.geometry.area / 1e6  # already projected; correct by construction
    gdf["marine_park_overlap_pct"] = marine_park_overlap(gdf)

    # Depth context per zone. Reported for sanity only — see the module docstring
    # on why this is not used to define the geometry.
    with rasterio.open(DEPTH_PATH) as src:
        elev = src.read(1)
        nod = src.nodata
        med, mn = [], []
        for geom in gdf.geometry:
            m = rasterio.features.geometry_mask(
                [geom], out_shape=elev.shape, transform=src.transform, invert=True
            )
            v = elev[m & (elev != nod)]
            med.append(float(np.median(v)) if v.size else np.nan)
            mn.append(float(v.min()) if v.size else np.nan)
    gdf["depth_median_m"] = med
    gdf["depth_min_m"] = mn

    return gdf.to_crs(AOI_CRS_STORAGE)


def check(gdf):
    """Fail loudly rather than publish a broken contract file."""
    expected = [z[0] for z in ZONE_DEFS]
    assert list(gdf["reef_zone_id"]) == expected, "zone IDs out of contract order"
    assert gdf["reef_zone_id"].is_unique, "duplicate reef_zone_id"
    assert len(gdf) == 8, f"expected 8 zones, got {len(gdf)}"
    assert (gdf["sensitivity_weight"] == 1.0).all(), "contract §4 requires weight = 1.0"
    assert gdf.geometry.is_valid.all(), "invalid geometry"
    assert (gdf["area_km2"] > 0).all(), "zero-area zone"

    minx, miny, maxx, maxy = DOWNLOAD_BBOX
    b = gdf.total_bounds
    assert minx <= b[0] and b[2] <= maxx, f"zones escape AOI in lon: {b}"
    assert miny <= b[1] and b[3] <= maxy, f"zones escape AOI in lat: {b}"

    # Every zone must be in water. This is the check the first attempt failed.
    assert (gdf["depth_median_m"] < 0).all(), (
        f"zone(s) not in water: {gdf.loc[gdf.depth_median_m >= 0, 'reef_zone_id'].tolist()}"
    )

    # No overlaps — a reef area counted twice would inflate the headline
    # exposure number.
    u = gdf.to_crs(AOI_CRS_PROJECTED)
    for i in range(len(u)):
        for j in range(i + 1, len(u)):
            ov = u.geometry.iloc[i].intersection(u.geometry.iloc[j]).area
            assert ov < 1.0, f"{u.reef_zone_id.iloc[i]} overlaps {u.reef_zone_id.iloc[j]}: {ov:.1f} m2"


if __name__ == "__main__":
    pass

    gdf = build()
    check(gdf)

    out = VECTORS / "reef_zones_PROVISIONAL.gpkg"
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GPKG", layer="reef_zones")

    print(f"\nwrote {out}")
    cols = ["reef_zone_id", "zone_name", "area_km2", "depth_median_m", "depth_min_m",
            "sensitivity_weight"]
    print(gdf[cols].to_string(index=False))
    print(f"\ntotal provisional reef area: {gdf.area_km2.sum():.2f} km2 across {len(gdf)} zones")
    print("all zones verified in water (median depth < 0)")
