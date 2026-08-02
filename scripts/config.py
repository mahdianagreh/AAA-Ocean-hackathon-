"""Single source of truth for spatial constants — ReefShield Aqaba, Pulga workstream.

Import from here. Never hardcode a bounding box or an EPSG code anywhere else.
Authoritative source: tasks/00-contracts.md §1 (spatial contract) and §2 (ID contract).
"""

from pathlib import Path

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
# Contract states the ordering explicitly as "W, S, E, N — EPSG:4326", which is
# (lon_min, lat_min, lon_max, lat_max) — the same order shapely.geometry.box takes.
DOWNLOAD_BBOX = (34.80, 29.25, 35.15, 29.70)  # padded superset; download against this
ANALYSIS_BBOX = (34.90, 29.35, 35.05, 29.60)  # exact study area; UNVERIFIED per contract

# Alias kept because the implementation plan refers to AOI_BBOX. Points at the
# padded box, which is what every download and clip in this workstream uses.
AOI_BBOX = DOWNLOAD_BBOX

# --- CRS (contract §1) ------------------------------------------------------
AOI_CRS_STORAGE = "EPSG:4326"     # storage, exchange, GeoJSON
AOI_CRS_PROJECTED = "EPSG:32636"  # UTM 36N — ALL area / distance / slope maths


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
