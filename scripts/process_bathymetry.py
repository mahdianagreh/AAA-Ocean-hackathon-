"""Bathymetry: depth field + water mask + coastline for the particle engine (Nizar).

Produces:
    data/processed/bathymetry/depth_utm36n.tif   (Float32 elevation, EPSG:32636)
    data/processed/vectors/coastline.gpkg        (layers: water, shoreline)

Figures live in qa_marine.py. This script ASSERTS; qa_marine VISUALISES.

SOURCE PROVENANCE — READ THIS BEFORE QUOTING A RESOLUTION
---------------------------------------------------------
The contract asks for GEBCO 15 arc-second. Every programmatic GEBCO route is
currently closed: wcs.gebco.net returns empty capabilities, download.gebco.net
rejects POST (405), and the BODC GeoTIFF tile paths 404. GEBCO's own portal is
an interactive web form, so it cannot be scripted.

We therefore ship GMRT (Global Multi-Resolution Topography, gmrt.org), which is
a synthesis whose deep-water source in this region IS GEBCO, served at a ~53 m
grid. Cross-check: GMRT and NOAA NCEI's independent global DEM mosaic agree on
the AOI minimum to within 0.2 m (-907.08 vs -907.27), so the underlying depths
are consistent between two independent providers.

`resolve_source()` prefers a canonical `gebco_aqaba.tif` if anyone drops one in
from the web form. Nothing else in this file changes when they do — that is the
swap-in, and it costs one download.

DO NOT read the ~53 m grid spacing as ~53 m of true resolution. Away from
multibeam tracks GMRT is interpolated from the coarser GEBCO grid, so the real
information content near shore is closer to GEBCO's ~450 m. This matters: the
Gulf of Aqaba has an exceptionally steep drop-off and the true reef shelf is
narrower than this grid can resolve. See docs/data_dictionary.md.
"""

import numpy as np
import rasterio
import rasterio.features
import rasterio.fill
import rasterio.warp
import geopandas as gpd
from shapely.geometry import shape

from pulga_config import AOI_CRS_PROJECTED, AOI_CRS_STORAGE, PROCESSED, RAW, VECTORS

# Control points for the sign-convention assertion. Every one was established by
# SAMPLING the grid, not by assuming — an inverted mask would make the particle
# engine treat land as sea, so this is an assert, not a hopeful comment.
#
# Expanded from 5 to 22 points spread over the full basin, because 5 points
# clustered near the city could all pass while the mask was wrong elsewhere. The
# expansion immediately paid for itself: two points first guessed as "gulf axis"
# at 29.62N and 29.56N came back as LAND at +533 m and +241 m. They are not in
# the sea at all — the gulf head is near 29.54N and north of it is Wadi Araba.
# They are retained below under honest names as land controls.
#
# Most points sit far from zero elevation so a 50 m grid shift could not flip
# one. Two exceptions are kept deliberately and are worth knowing about:
# "Aqaba city" (+24 m) and "N Wadi Araba" (+18 m) are genuinely low-lying land,
# and they are the useful ones — a near-shore point is where an inverted or
# shifted mask would actually show up first.
CONTROL_WATER = [
    ((34.960, 29.530), "head of gulf"),
    ((34.985, 29.520), "off Jordan 29.52N"),
    ((34.930, 29.500), "gulf axis 29.50N"),
    ((34.965, 29.470), "off Jordan 29.47N"),
    ((34.930, 29.450), "gulf axis 29.45N"),
    ((34.955, 29.440), "off Jordan 29.44N"),
    ((34.910, 29.400), "gulf axis 29.40N"),
    ((34.945, 29.380), "off Jordan 29.38N"),
    ((34.890, 29.350), "gulf axis 29.35N"),
    ((34.870, 29.300), "gulf axis 29.30N"),
    ((34.850, 29.255), "mid-gulf 29.25N"),
]
CONTROL_LAND = [
    ((35.020, 29.660), "N Wadi Araba"),
    ((34.900, 29.620), "NW hills above Wadi Araba"),
    ((34.920, 29.560), "N of gulf head, Wadi Araba floor"),
    ((34.930, 29.560), "Eilat side"),
    ((34.830, 29.550), "Sinai mountains W"),
    ((35.005, 29.522), "Aqaba city"),
    ((35.100, 29.500), "Jordan mountains E"),
    ((35.060, 29.450), "Wadi Yutum inland"),
    ((34.990, 29.330), "Saudi side S"),
    ((35.120, 29.300), "inland SE desert"),
    ((35.140, 29.260), "far SE desert"),
]

TARGET_RES_M = 50.0  # UTM 36N grid spacing for the depth field


def resolve_source():
    """Canonical GEBCO if present, else the GMRT stand-in. Never silently mix."""
    gebco = RAW / "bathymetry" / "gebco_aqaba.tif"
    gmrt = RAW / "bathymetry" / "gmrt_aqaba.tif"
    if gebco.exists():
        return gebco, "GEBCO (canonical grid)"
    if gmrt.exists():
        return gmrt, "GMRT (GEBCO-derived synthesis, stand-in)"
    raise FileNotFoundError(
        "No bathymetry in data/raw/bathymetry/. Expected gebco_aqaba.tif or gmrt_aqaba.tif"
    )


def verify_sign_convention(path, verbose=False):
    """Assert negative == below sea level across all 22 control points.

    Returns the sampled values so the QA figure can label each point with what
    was actually read, rather than re-sampling and risking a different answer
    from the figure than from the assertion.
    """
    results = []
    with rasterio.open(path) as src:
        for (lon, lat), label in CONTROL_WATER:
            v = float(list(src.sample([(lon, lat)]))[0][0])
            assert v < 0, f"SIGN CONVENTION INVERTED: {label} should be water, got {v:+.1f}"
            results.append({"lon": lon, "lat": lat, "label": label,
                            "expected": "water", "elev_m": v})
        for (lon, lat), label in CONTROL_LAND:
            v = float(list(src.sample([(lon, lat)]))[0][0])
            assert v > 0, f"SIGN CONVENTION INVERTED: {label} should be land, got {v:+.1f}"
            results.append({"lon": lon, "lat": lat, "label": label,
                            "expected": "land", "elev_m": v})

    print(f"  OK sign convention verified at {len(results)} control points "
          f"({len(CONTROL_WATER)} water, {len(CONTROL_LAND)} land): "
          "negative = below sea level, positive = land")
    if verbose:
        for r in results:
            print(f"      {r['expected']:5s} {r['label']:34s} {r['elev_m']:+9.1f} m")
    return results


def reproject_to_utm(src_path, dst_path):
    """Reproject the elevation grid to UTM 36N at TARGET_RES_M.

    GMRT ships ~0.3% of cells as bare NaN with no nodata tag declared. Two
    things must happen here or the handoff is unsafe:

      1. Those gaps are filled before warping. They are small and scattered,
         so inverse-distance fill is appropriate. Left alone, a NaN inside the
         sea body silently poisons any interpolation the particle engine does —
         a NaN particle position does not raise, it just quietly stops being a
         number.
      2. The output carries exactly ONE nodata representation, the declared
         -32768 sentinel. Shipping a file that mixes NaN with a declared
         sentinel guarantees a downstream reader handles one and not the other.
    """
    with rasterio.open(src_path) as src:
        arr = src.read(1).astype("float32")
        gaps = np.isnan(arr)
        if gaps.any():
            arr = rasterio.fill.fillnodata(
                arr, mask=(~gaps).astype("uint8"), max_search_distance=20
            )
            still = int(np.isnan(arr).sum())
            print(f"  filled {int(gaps.sum())} NaN gaps in source ({still} unfillable remain)")
            arr = np.where(np.isnan(arr), -32768.0, arr)

        transform, width, height = rasterio.warp.calculate_default_transform(
            src.crs, AOI_CRS_PROJECTED, src.width, src.height, *src.bounds,
            resolution=TARGET_RES_M,
        )
        meta = src.meta.copy()
        meta.update(
            crs=AOI_CRS_PROJECTED, transform=transform, width=width, height=height,
            dtype="float32", count=1, nodata=-32768.0, compress="deflate",
        )
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(dst_path, "w", **meta) as dst:
            dest = np.full((height, width), -32768.0, dtype="float32")
            rasterio.warp.reproject(
                source=arr,
                destination=dest,
                src_transform=src.transform, src_crs=src.crs,
                src_nodata=-32768.0,
                dst_transform=transform, dst_crs=AOI_CRS_PROJECTED,
                # Bilinear, not nearest: this is a continuous depth field that the
                # engine will interpolate on, so we want smooth gradients.
                resampling=rasterio.warp.Resampling.bilinear,
                dst_nodata=-32768.0,
            )
            assert not np.isnan(dest).any(), "NaN survived into the depth field"
            dst.write(dest, 1)

    print(f"  wrote {dst_path.name}  {width}x{height} @ {TARGET_RES_M:.0f} m, {AOI_CRS_PROJECTED}")
    return dst_path


def extract_coastline(depth_path, out_path):
    """Polygonize the water mask; emit water polygons + shoreline linework."""
    with rasterio.open(depth_path) as src:
        elev = src.read(1)
        transform, crs, nodata = src.transform, src.crs, src.nodata

    water = ((elev < 0) & (elev != nodata)).astype("uint8")

    polys = [
        shape(geom)
        for geom, val in rasterio.features.shapes(water, mask=water.astype(bool), transform=transform)
        if val == 1
    ]
    water_gdf = gpd.GeoDataFrame({"geometry": polys}, crs=crs)
    water_gdf["area_km2"] = water_gdf.geometry.area / 1e6

    # Keep only the sea body. Tiny interior "water" specks are interpolation
    # artefacts in the dry wadi floors, not real water, and they would punch
    # false holes in the particle engine's land barrier.
    water_gdf = water_gdf.sort_values("area_km2", ascending=False).reset_index(drop=True)
    dropped = (water_gdf["area_km2"] < 0.05).sum()
    water_gdf = water_gdf[water_gdf["area_km2"] >= 0.05].reset_index(drop=True)
    water_gdf["role"] = ["sea_body"] + ["water_other"] * (len(water_gdf) - 1)

    shoreline = gpd.GeoDataFrame(
        {"geometry": water_gdf.geometry.boundary}, crs=crs
    ).to_crs(AOI_CRS_STORAGE)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    water_gdf.to_crs(AOI_CRS_STORAGE).to_file(out_path, driver="GPKG", layer="water")
    shoreline.to_file(out_path, driver="GPKG", layer="shoreline")

    print(f"  wrote {out_path.name}: {len(water_gdf)} water polys "
          f"(largest {water_gdf.area_km2.iloc[0]:.1f} km2), dropped {dropped} specks < 0.05 km2")
    return water_gdf



if __name__ == "__main__":
    src_path, provenance = resolve_source()
    print(f"bathymetry source: {src_path.name}  [{provenance}]")

    controls = verify_sign_convention(src_path, verbose=True)
    depth_path = reproject_to_utm(src_path, PROCESSED / "bathymetry" / "depth_utm36n.tif")
    water_gdf = extract_coastline(depth_path, VECTORS / "coastline.gpkg")

    with rasterio.open(depth_path) as src:
        a = src.read(1)
        valid = a[a != src.nodata]
        print(f"\ndepth field: min {valid.min():.1f} m, max {valid.max():.1f} m, "
              f"{np.mean(valid < 0) * 100:.1f}% below sea level")
    print("READY FOR NIZAR: depth_utm36n.tif + coastline.gpkg")
