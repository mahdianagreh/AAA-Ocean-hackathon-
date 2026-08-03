"""Spatial constants for the scripts/ chain — ReefShield Aqaba.

Import from here. Never hardcode a bounding box or an EPSG code anywhere else.

The numbers themselves now live in ``backend/src/config/spatial.py``, which is
the project-wide contract. This module re-exports them so the scripts/ chain
and the backend can never drift apart, and adds the ID and land-cover
constants that only this chain needs.

Authoritative source: tasks/00-contracts.md §1 (spatial) and §2 (IDs).
"""

import importlib.util
from pathlib import Path

# --- Earth Engine -----------------------------------------------------------
EE_PROJECT_ID = "reefshield-aqaba-504407"

# --- Paths ------------------------------------------------------------------
# Resolved from this file so scripts work regardless of the working directory.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
VECTORS = PROCESSED / "vectors"
FEATURES = PROCESSED / "features"
DOCS = REPO_ROOT / "docs"
QA = DOCS / "qa_screenshots"

# --- Bounding boxes (contract §1) -------------------------------------------
# Re-exported from the project-wide contract. Ordering is "W, S, E, N —
# EPSG:4326", i.e. (lon_min, lat_min, lon_max, lat_max), the order
# shapely.geometry.box takes.
# Loaded by file path, not by name: this module is itself called `config`, and
# so is the backend package, so a plain `from config.spatial import ...` would
# resolve back to this half-initialised module. Importing by location is
# unambiguous and works no matter which directory a script is run from.
def _load_spatial_contract():
    spec = importlib.util.spec_from_file_location(
        "reefshield_spatial_contract",
        REPO_ROOT / "backend" / "src" / "config" / "spatial.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_spatial = _load_spatial_contract()


def load_spatial_contract():
    """Public accessor for the backend spatial-contract module.

    Exposed because `from config.spatial import ...` cannot work from scripts/ —
    `config` resolves to THIS module, which is not a package. Anything in scripts/
    that needs the contract's own helpers (BBox methods, verify_against_files)
    should call this rather than re-inventing the by-path import.
    """
    return _spatial

TERRAIN_AOI = _spatial.TERRAIN_AOI
MARINE_AOI = _spatial.MARINE_AOI
AQABA_AOI = _spatial.AQABA_AOI
CRS_STORAGE = _spatial.CRS_STORAGE
CRS_MEASURE = _spatial.CRS_MEASURE

LAND_BBOX = TERRAIN_AOI.wsen      # DEM, hydrology, rainfall, land cover, soil
MARINE_BBOX = MARINE_AOI.wsen     # bathymetry, coastline, reef zones, imagery
DOWNLOAD_BBOX = AQABA_AOI.wsen    # the union — download against this or wider

# Alias kept because the implementation plan refers to AOI_BBOX.
AOI_BBOX = DOWNLOAD_BBOX

# RE-PULL COMPLETE, 2 Aug 2026. Everything in this workstream that had been fetched
# against the retired pre-v2 box has been refetched against TERRAIN_AOI:
#
#     WorldCover   1 tile -> 2 tiles (N27E033 + N30E033), mosaicked then clipped
#     SoilGrids    12 rasters re-pulled; 188x155 -> 481x526
#     OSM          re-clipped; roads 3,845 -> 8,289, drainage 200 -> 1,402
#
# Marine artefacts were deliberately NOT refetched: MARINE_AOI is unchanged between
# contract v1 and v2, and the coverage check confirms the depth field still covers
# its extent.
#
# The retired box's coordinates are deliberately NOT written here. They are recorded
# once, in backend/src/config/spatial.py's docstring, and
# tests/test_spatial_contract.py fails the build if any other module repeats them —
# a literal in a comment is exactly what gets copy-pasted back into code under
# deadline pressure.
#
# Evidence for the correction: docs/aoi_coverage_report_20260802.txt (19 files short
# before, 7 after, each remaining one explained). Re-run
# `python scripts/check_aoi_coverage.py` after adding any new raw source.

# --- CRS (contract §1) ------------------------------------------------------
AOI_CRS_STORAGE = CRS_STORAGE     # EPSG:4326 — storage, exchange, GeoJSON
AOI_CRS_PROJECTED = CRS_MEASURE   # EPSG:32636 — ALL area / distance / slope maths


def geographic_aspect(lat: float = None) -> float:
    """Matplotlib `aspect` that makes a degrees-extent plot geographically true.

    imshow defaults to aspect='equal', which draws 1 degree of longitude the same
    length as 1 degree of latitude. At Aqaba's latitude 1 deg lon is only ~97 km
    against ~111 km for 1 deg lat, so an unaspected plot in EPSG:4326 comes out
    ~14% too wide. Any QA figure drawn in degrees must pass this to set_aspect,
    or shapes on it are not the shapes on the ground — which matters when the
    figure is the thing being trusted over the numbers.

    Plots drawn in EPSG:32636 need none of this; metres are already isotropic.
    """
    import math

    if lat is None:
        lat = (DOWNLOAD_BBOX[1] + DOWNLOAD_BBOX[3]) / 2
    return 1.0 / math.cos(math.radians(lat))

# --- AOI files --------------------------------------------------------------
PADDED_BOX_PATH = RAW / "aoi" / "aqaba_padded_box.geojson"
ANALYSIS_BOX_PATH = DATA / "aoi" / "aqaba_aoi.geojson"  # path fixed by contract §3

# --- ID contract (§2) -------------------------------------------------------
REEF_ZONE_ID_FMT = "R-{:02d}"       # R-01 … R-08, owner: Pulga
CATCHMENT_ID_FMT = "AQ-C{:02d}"     # AQ-C01 … AQ-C05, owner: Mahdi
OUTLET_ID_FMT = "AQ-O{:02d}"        # AQ-O01 ↔ AQ-C01, owner: Mahdi
N_REEF_ZONES = 8

# --- ESA WorldCover v200 class codes ----------------------------------------
# NOT sequential. Hardcoded deliberately; do not "simplify" into a range().
WORLDCOVER_CLASSES = {
    10: "tree_cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare_sparse_vegetation",
    70: "snow_ice",
    80: "permanent_water_bodies",
    90: "herbaceous_wetland",
    95: "mangroves",
    100: "moss_lichen",
}
