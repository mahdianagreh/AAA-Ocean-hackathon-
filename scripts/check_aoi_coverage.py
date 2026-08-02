#!/usr/bin/env python3
"""Report which files on disk do not cover the AOI they are supposed to.

Why this exists
---------------
Until 2 August 2026 every download in this project used a single box,

    34.80, 29.25, 35.15, 29.70

which reaches 29.70 N and 35.15 E. The terrain AOI now reaches **30.30 N and
35.94 E**, because Wadi Yutum drains about 90 km inland. So a file fetched
against the old box covers only part of AQ-C01 — and nothing about it looks
broken. It opens, it plots, it aggregates. The numbers are just wrong for the
85 % of the catchment that is missing.

That is the failure mode `tasks/mahdi-blockers.md` §1 describes: no crash, no
warning, results that look fine and are not. This script makes it visible.

Usage
-----
    python scripts/check_aoi_coverage.py            # summary
    python scripts/check_aoi_coverage.py --verbose  # every file

Exit status is 1 when anything fails to cover its AOI, so it can gate a
re-download step.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _spatial_contract():
    spec = importlib.util.spec_from_file_location(
        "reefshield_spatial_contract",
        REPO_ROOT / "backend" / "src" / "config" / "spatial.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SPATIAL = _spatial_contract()
TERRAIN_AOI = SPATIAL.TERRAIN_AOI
MARINE_AOI = SPATIAL.MARINE_AOI
BBox = SPATIAL.BBox

#: Which extent each data family is contractually required to cover.
#: Land sources follow the catchments; marine sources follow the plume.
TARGETS: list[tuple[str, str, object]] = [
    ("data/raw/imerg", "**/*.nc4", TERRAIN_AOI),
    ("data/raw/imerg", "**/*.nc", TERRAIN_AOI),
    ("data/raw/era5_land", "**/*.nc", TERRAIN_AOI),
    ("data/processed/events", "**/*.nc", TERRAIN_AOI),
    ("data/raw/worldcover", "**/*.tif", TERRAIN_AOI),
    ("data/raw/soilgrids", "**/*.tif", TERRAIN_AOI),
    ("data/interim", "worldcover_aqaba_clip.tif", TERRAIN_AOI),
    ("data/processed/vectors", "osm_aqaba.gpkg", TERRAIN_AOI),
    ("data/raw/bathymetry", "**/*.tif", MARINE_AOI),
    ("data/processed/bathymetry", "**/*.tif", MARINE_AOI),
    ("data/processed/vectors", "coastline.gpkg", MARINE_AOI),
    ("data/processed/vectors", "reef_zones*.gpkg", MARINE_AOI),
    ("data/processed/plume", "**/*.tif", MARINE_AOI),
    ("data/raw/currents", "**/*.nc", MARINE_AOI),
]

SKIPPED_FORMATS: set[str] = set()


# ---------------------------------------------------------------------------
# extent readers — each returns a BBox in EPSG:4326, or None if unreadable
# ---------------------------------------------------------------------------


#: IMERG delivers its grid inside a `Grid` group rather than at the file root,
#: so a plain open() yields an empty dataset. Same convention as
#: `ingestion.imerg.IMERG_GROUP`.
NETCDF_GROUPS = (None, "Grid")


def _netcdf_extent(path: Path):
    try:
        import xarray as xr
    except ImportError:
        SKIPPED_FORMATS.add("NetCDF (install xarray)")
        return None

    for group in NETCDF_GROUPS:
        try:
            with xr.open_dataset(path, decode_times=False, group=group) as ds:
                lat_name = next((n for n in ("lat", "latitude", "y") if n in ds.variables), None)
                lon_name = next((n for n in ("lon", "longitude", "x") if n in ds.variables), None)
                if not lat_name or not lon_name:
                    continue
                lat, lon = ds[lat_name].values, ds[lon_name].values
                return BBox(
                    float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max())
                )
        except Exception:
            continue
    return None


def _vector_extent(path: Path):
    try:
        import geopandas as gpd
    except ImportError:
        SKIPPED_FORMATS.add("vector (install geopandas)")
        return None
    try:
        frame = gpd.read_file(path)
        if frame.crs is not None and frame.crs.to_epsg() != 4326:
            frame = frame.to_crs(4326)
        w, s, e, n = frame.total_bounds
        return BBox(float(w), float(s), float(e), float(n))
    except Exception:
        return None


def _raster_extent(path: Path):
    try:
        import rasterio
        from rasterio.warp import transform_bounds
    except ImportError:
        SKIPPED_FORMATS.add("GeoTIFF (install rasterio)")
        return None
    try:
        with rasterio.open(path) as src:
            w, s, e, n = transform_bounds(src.crs, "EPSG:4326", *src.bounds, densify_pts=21)
            return BBox(float(w), float(s), float(e), float(n))
    except Exception:
        return None


READERS = {
    ".nc": _netcdf_extent, ".nc4": _netcdf_extent, ".h5": _netcdf_extent,
    ".gpkg": _vector_extent, ".geojson": _vector_extent, ".shp": _vector_extent,
    ".tif": _raster_extent, ".tiff": _raster_extent,
}


def missing_fraction(have: "BBox", need: "BBox") -> float:
    """Share of the required box the file does not cover, by area."""
    overlap_lon = max(0.0, min(have.east, need.east) - max(have.west, need.west))
    overlap_lat = max(0.0, min(have.north, need.north) - max(have.south, need.south))
    need_lon, need_lat = need.span_deg
    if need_lon <= 0 or need_lat <= 0:
        return 0.0
    return 1.0 - (overlap_lon * overlap_lat) / (need_lon * need_lat)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="list every file checked")
    args = parser.parse_args()

    print("Spatial contract — tasks/00-contracts.md §1")
    print(f"  TERRAIN_AOI  {TERRAIN_AOI}")
    print(f"  MARINE_AOI   {MARINE_AOI}\n")

    failures: list[tuple[Path, object, object, float]] = []
    checked = unreadable = 0

    for directory, pattern, required in TARGETS:
        root = REPO_ROOT / directory
        if not root.exists():
            continue
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            reader = READERS.get(path.suffix.lower())
            if reader is None:
                continue
            extent = reader(path)
            if extent is None:
                unreadable += 1
                continue
            checked += 1
            if required.contains(extent) or not extent.contains(required):
                gap = missing_fraction(extent, required)
                if gap > 1e-6:
                    failures.append((path, extent, required, gap))
                    continue
            if args.verbose:
                print(f"  ok    {path.relative_to(REPO_ROOT)}")

    if failures:
        print(f"{len(failures)} file(s) do not cover their required extent:\n")
        by_dir: dict[str, list] = {}
        for path, extent, required, gap in failures:
            by_dir.setdefault(str(path.relative_to(REPO_ROOT).parent), []).append((path, extent, gap))
        for parent, items in sorted(by_dir.items()):
            worst = max(g for _, _, g in items)
            print(f"  {parent}/  — {len(items)} file(s), up to {worst:.0%} of the AOI missing")
            sample_path, sample_extent, _ = items[0]
            print(f"      e.g. {sample_path.name}")
            print(f"           covers {sample_extent}")
        print()

    print(f"checked {checked} file(s); {len(failures)} short of their AOI; {unreadable} unreadable")
    for note in sorted(SKIPPED_FORMATS):
        print(f"  note: skipped some {note}")

    if failures:
        print(
            "\nRe-pull anything listed above before trusting a per-catchment\n"
            "aggregate computed from it. Coverage gaps do not raise — they just\n"
            "silently shrink the area every mean and total is taken over."
        )
        return 1

    print("\nEverything readable covers its required extent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
