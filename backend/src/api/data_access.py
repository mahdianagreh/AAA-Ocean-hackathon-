"""Read the contract artifacts once, cache them, hand out plain dicts.

The routes never touch a file path or a GeoDataFrame directly — they ask this
module. That keeps two things true:

  * There is exactly one place that knows where a contract artifact lives, so when
    Nizar's shared session layer lands, only this module changes.
  * Nothing reads a 5 MB GeoPackage per request. Loads are memoised, and a plume
    simulation does not re-run because someone dragged a time slider.

MISSING IS MISSING. Every loader returns None (or an empty list) when its artifact
is absent, and `/health` reports which are missing. Nothing here fabricates a
placeholder to keep a response shaped — standing law #1 and #2.
"""

from __future__ import annotations

import hashlib
import json
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
VECTORS = DATA / "processed" / "vectors"
FEATURES = DATA / "processed" / "features"
DOCS = ROOT / "docs"

ARTIFACTS: dict[str, Path] = {
    "catchments": VECTORS / "catchments.gpkg",
    "outlets": VECTORS / "outlets.gpkg",
    "reef_zones": VECTORS / "reef_zones.gpkg",
    "reef_zones_provisional": VECTORS / "reef_zones_PROVISIONAL.gpkg",
    "coastline": VECTORS / "coastline.gpkg",
    "landcover": FEATURES / "landcover_by_catchment.parquet",
    "soil": FEATURES / "soil_by_catchment.parquet",
    "urban": FEATURES / "urban_by_catchment.parquet",
    "event_dates": DOCS / "event_dates.md",
    "data_dictionary": DOCS / "data_dictionary.md",
}


def artifact_status() -> dict[str, bool]:
    return {name: path.exists() for name, path in ARTIFACTS.items()}


# Display names, and ONLY where the repo actually documents one. `AQ-C01 — Wadi
# Yutum` appears in tasks/00-contracts.md; AQ-C02..C05 are unnamed there, and
# inventing plausible wadi names for them would be fabricated geography sitting in
# a user-facing label. They render as their IDs until someone documents a name.
CATCHMENT_NAMES: dict[str, dict[str, str]] = {
    "AQ-C01": {"en": "Wadi Yutum", "ar": "وادي اليتيم"},
}


def catchment_label(catchment_id: str, language: str = "en") -> str:
    entry = CATCHMENT_NAMES.get(catchment_id)
    if not entry:
        return catchment_id
    return entry.get(language, entry["en"])


def _geo(path: Path, layer: str | None = None):
    import geopandas as gpd

    if not path.exists():
        return None
    return gpd.read_file(path, layer=layer) if layer else gpd.read_file(path)


def _geojson(geom) -> dict:
    """Shapely geometry -> GeoJSON dict, imported lazily to keep import cost off
    the module load path (geopandas pulls in a lot)."""
    import shapely

    return json.loads(shapely.to_geojson(geom))


def _clean(value: Any) -> Any:
    """JSON-safe scalars. NaN becomes None — a gap stays a gap."""
    import math

    if value is None:
        return None
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if hasattr(value, "item"):
        try:
            return _clean(value.item())
        except Exception:
            return str(value)
    if isinstance(value, (str, int, bool)):
        return value
    return str(value)


# ------------------------------------------------------------------ catchments

@lru_cache(maxsize=1)
def catchments(include_geometry: bool = True) -> list[dict]:
    gdf = _geo(ARTIFACTS["catchments"])
    if gdf is None:
        return []
    idcol = "catchment_id" if "catchment_id" in gdf.columns else "id"
    gdf = gdf.to_crs("EPSG:4326")

    out = []
    for _, r in gdf.iterrows():
        rec = {
            "catchment_id": r[idcol],
            "outlet_id": _clean(r.get("outlet_id")),
            "area_km2": _clean(r.get("area_km2")),
        }
        if include_geometry:
            rec["geometry"] = _geojson(r.geometry)
        out.append(rec)
    return sorted(out, key=lambda x: x["catchment_id"])


@lru_cache(maxsize=1)
def _feature_table(name: str) -> dict[str, dict]:
    import pandas as pd

    path = ARTIFACTS[name]
    if not path.exists():
        return {}
    df = pd.read_parquet(path)
    idcol = "catchment_id"
    return {
        row[idcol]: {k: _clean(v) for k, v in row.items() if k != idcol}
        for _, row in df.iterrows()
    }


def training_row(event_id: str, catchment_id: str) -> dict | None:
    """The real feature row for one (event, catchment), or None.

    Exists because the exposure endpoint was asking the runoff model for a synthetic
    `30 mm/3h` with no other features. The model needs 20, and the sediment magnitude is
    a curve-number depth driven by `precipitation_mm_day` — absent, that depth is 0, the
    sediment index is 0, and since exposure is a PRODUCT of five terms every reef zone
    came back `minimal` regardless of the plume. A synthetic request is fine for shaping
    a response and useless for computing one.

    Returns None rather than a default row when the event is not in the training set:
    an invented feature vector produces a confident number about a storm we never
    measured, which is the failure this project keeps having to undo.
    """
    import pandas as pd

    path = FEATURES / "training_set_full.parquet"
    if not path.exists():
        return None

    frame = pd.read_parquet(path)
    if "date" not in frame.columns or "catchment_id" not in frame.columns:
        return None

    # Event ids are AQ-YYYY-MM-DD; the training set is keyed by date, so the id is
    # parsed rather than matched as a string — the contract owns the format.
    try:
        day = pd.to_datetime(event_id.removeprefix("AQ-")).date()
    except (ValueError, TypeError):
        return None

    hit = frame[(pd.to_datetime(frame["date"]).dt.date == day)
                & (frame["catchment_id"] == catchment_id)]
    if hit.empty:
        return None
    return {k: _clean(v) for k, v in hit.iloc[0].items()}


def landcover_for(cid: str) -> dict | None:
    return _feature_table("landcover").get(cid)


def soil_for(cid: str) -> dict | None:
    return _feature_table("soil").get(cid)


def urban_for(cid: str) -> dict | None:
    return _feature_table("urban").get(cid)


# ------------------------------------------------------------------ reef zones

@lru_cache(maxsize=1)
def reef_zones(include_geometry: bool = True) -> tuple[list[dict], bool]:
    """(zones, is_provisional). Prefers the real ACA export when it exists."""
    real = ARTIFACTS["reef_zones"]
    prov = ARTIFACTS["reef_zones_provisional"]
    path, is_prov = (real, False) if real.exists() else (prov, True)

    gdf = _geo(path, layer="reef_zones")
    if gdf is None:
        gdf = _geo(path)
    if gdf is None:
        return [], True
    gdf = gdf.to_crs("EPSG:4326")

    out = []
    for _, r in gdf.iterrows():
        rec = {
            "reef_zone_id": r["reef_zone_id"],
            "zone_name": _clean(r.get("zone_name")),
            "habitat_class": _clean(r.get("habitat_class")),
            "area_km2": _clean(r.get("area_km2")),
            "sensitivity_weight": _clean(r.get("sensitivity_weight")) or 1.0,
            "sensitivity_weight_status": _clean(r.get("sensitivity_weight_status"))
            or "PLACEHOLDER_PENDING_MARINE_SCIENTIST",
            "marine_park_overlap_pct": _clean(r.get("marine_park_overlap_pct")),
            "depth_median_m": _clean(r.get("depth_median_m")),
            # Added by Karam's ACA build. depth_land_cell_pct is not decoration: the
            # 50 m bathymetry under a 20-50 m reef strip reads as land for 39-100% of
            # cells, so this is the field that says whether a depth is usable at all.
            "depth_land_cell_pct": _clean(r.get("depth_land_cell_pct")),
            "habitat_class_code": _clean(r.get("habitat_class_code")),
            "habitat_class_mix": _clean(r.get("habitat_class_mix")),
            "geomorphic_class": _clean(r.get("geomorphic_class")),
        }
        if include_geometry:
            rec["geometry"] = _geojson(r.geometry)
        out.append(rec)
    return sorted(out, key=lambda x: x["reef_zone_id"]), is_prov


def reef_zones_gdf():
    """GeoDataFrame form, for the exposure engine's overlay."""
    real = ARTIFACTS["reef_zones"]
    prov = ARTIFACTS["reef_zones_provisional"]
    path = real if real.exists() else prov
    gdf = _geo(path, layer="reef_zones")
    return gdf if gdf is not None else _geo(path)


# --------------------------------------------------------------------- outlets

# Outlet position confidence. AQ-O04's caveat is the one that must always travel.
OUTLET_CONFIDENCE = {
    "AQ-O01": "good", "AQ-O02": "plausible", "AQ-O03": "plausible",
    "AQ-O04": "low", "AQ-O05": "plausible",
}


@lru_cache(maxsize=1)
def outlets() -> list[dict]:
    gdf = _geo(ARTIFACTS["outlets"])
    if gdf is None:
        return []
    gdf = gdf.to_crs("EPSG:4326")
    idcol = "outlet_id" if "outlet_id" in gdf.columns else "id"

    out = []
    for _, r in gdf.iterrows():
        oid = r[idcol]
        pt = r.geometry.centroid
        out.append({
            "outlet_id": oid,
            "catchment_id": _clean(r.get("catchment_id")),
            "lon": float(pt.x),
            "lat": float(pt.y),
            "position_confidence": OUTLET_CONFIDENCE.get(oid, "plausible"),
        })
    return sorted(out, key=lambda x: x["outlet_id"])


# ---------------------------------------------------------------------- events

@lru_cache(maxsize=1)
def events() -> list[dict]:
    """Parse the documented event list. Source of truth is docs/event_dates.md.

    Deliberately a parse of the committed document rather than a hardcoded list:
    the dates came from two papers, and duplicating them here would create a second
    version that could drift from the one the RAG corpus cites.
    """
    import re

    path = ARTIFACTS["event_dates"]
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")

    seen: dict[str, dict] = {}
    for m in re.finditer(r"\bAQ-(\d{4})-(\d{2})-(\d{2})\b", text):
        eid = m.group(0)
        if eid in seen:
            continue
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.end())
        line = text[line_start: line_end if line_end != -1 else len(text)]
        seen[eid] = {
            "event_id": eid,
            "start": f"{m.group(1)}-{m.group(2)}-{m.group(3)}",
            "end": None,
            "label": line.strip(" |#*-")[:180] or None,
            "source": "docs/event_dates.md",
        }
    return sorted(seen.values(), key=lambda x: x["event_id"])


# ---------------------------------------------------------------- data sources

@lru_cache(maxsize=1)
def data_sources() -> list[dict]:
    """The Data Sources panel. Hand-maintained here, mirroring the data dictionary.

    Not parsed out of the markdown: the dictionary is prose for humans, and a
    brittle parser silently dropping a limitation would be worse than a list that
    a person keeps in step with it. `tests/test_api_contracts.py` asserts every
    entry names a file that exists.
    """
    return [
        {
            "name": "ESA WorldCover",
            "product_version": "v200, 2021 epoch",
            "access_date": "2026-08-02",
            "access_method": "AWS S3 open data; tiles N27E033 + N30E033, mosaicked",
            "spatial_resolution": "10 m",
            "licence": "CC BY 4.0 (© ESA WorldCover project 2021)",
            "limitations": [
                "2021 epoch only, no time series — the 2013 and 2016 events are both "
                "modelled against 2021 land cover.",
                "10 m cannot resolve individual streets; the built_up class bundles "
                "roads, yards and parking with roofs.",
            ],
            "qa_figures": [
                "worldcover_01_raw_tiles_before_mosaic.png",
                "worldcover_02_clipped_to_aoi.png",
                "worldcover_06_v2_mosaic_seam_check.png",
                "worldcover_07_aq_c01_bareground_v2.png",
            ],
        },
        {
            "name": "ISRIC SoilGrids",
            "product_version": "v2.0",
            "access_date": "2026-08-02",
            "access_method": "WCS 2.0.1 GetCoverage, 6 variables x 2 depths",
            "spatial_resolution": "250 m",
            "licence": "CC BY 4.0",
            "limitations": [
                "Globally model-derived, not surveyed — usable only as a relative "
                "erodibility ranking between catchments.",
                "Ships an undeclared 0 nodata over water, masked to NaN on read.",
            ],
            "qa_figures": [
                "soilgrids_07_texture_triangle_by_catchment.png",
                "soilgrids_08_unit_conversion_before_after.png",
                "soilgrids_09_within_catchment_variance.png",
            ],
        },
        {
            "name": "OpenStreetMap (Jordan extract)",
            "product_version": "Geofabrik jordan-latest.osm.pbf",
            "access_date": "2026-08-02",
            "access_method": "ogr2ogr -clipsrc against data/aoi/terrain_aoi.geojson",
            "spatial_resolution": "vector",
            "licence": "ODbL 1.0 (© OpenStreetMap contributors)",
            "limitations": [
                "Absence of a mapped feature is not evidence of absence; only positive "
                "matches are used as outlet corrections.",
                "A Jordan-only extract cannot contain features west of 34.87 E, so the "
                "AOI's western edge is empty by construction, not by error.",
            ],
            "qa_figures": [
                "osm_01_roads_over_satellite.png",
                "osm_04_culverts_all_numbered.png",
                "osm_05_culvert_top5_insets.png",
            ],
        },
        {
            "name": "Reef zones (Allen Coral Atlas)",
            "product_version": "Allen Coral Atlas v2.0 (ACA/reef_habitat/v2_0)",
            "access_date": "2026-08-03",
            "access_method": (
                "Earth Engine reduceToVectors at native 5 m over MARINE_AOI, living-reef "
                "benthic classes (Coral/Algae, Seagrass) merged onto the existing R-NN "
                "zone extents"
            ),
            "spatial_resolution": "5 m",
            "licence": "CC BY 4.0 (Allen Coral Atlas)",
            "limitations": [
                "Scope is Jordan's coast. The 8 named zones hold 0.742 km2, which is "
                "86.8% of the living reef the Atlas maps on Jordan's coastal corridor. A "
                "further 3.338 km2 sits inside the same bounding box on the Egyptian and "
                "Israeli shores and is deliberately out of scope.",
                "The earlier provisional geometry claimed 5.69 km2 — 7.7x the real "
                "figure — because it assumed a uniform 250 m strip along the whole "
                "coastline. Any number derived from the provisional area is an "
                "overestimate.",
                "sensitivity_weight remains a 1.0 placeholder labelled in the file "
                "schema; the Atlas maps habitat, not sensitivity.",
                "The Atlas maps optically shallow reef only; deeper habitat is absent.",
                "Two zones report a positive median elevation because the ~450 m "
                "bathymetry disagrees with the Atlas's 5 m reef extent near shore.",
            ],
            "qa_figures": [
                "reef_01_provisional_over_satellite.png",
                "reef_03_overlap_bug_before_after.png",
                "reef_04_marine_park_validation.png",
            ],
        },
        {
            "name": "Bathymetry",
            "product_version": "GMRT (substituted for GEBCO 15 arc-second)",
            "access_date": "2026-08-01",
            "access_method": "gmrt.org GridServer, resolution=max",
            "spatial_resolution": "~53 m grid; ~450 m effective",
            "licence": "open (GMRT / GEBCO attribution)",
            "limitations": [
                "Effective resolution ~450 m cannot resolve the Gulf's drop-off, reef "
                "shelf, small channels or harbour structures.",
                "The 53 m grid spacing is not 53 m of resolution.",
            ],
            "qa_figures": [
                "depth_02_sign_convention_22_control_points.png",
                "depth_03_nodata_bug_before_after.png",
                "coastline_02_osm_vs_gmrt_agreement.png",
            ],
            "substituted": True,
            "substitution_note": (
                "Every programmatic GEBCO route is closed: WCS returns empty "
                "capabilities, the download endpoint rejects POST with 405, BODC tile "
                "paths 404, and the WMS returns a rendered RGB image rather than "
                "elevation values. GMRT's deep-water source in this region is GEBCO. "
                "Cross-checked against NOAA NCEI (0.2 m on the basin minimum) and "
                "against OSM's independent coastline (62 m median). The file is named "
                "gmrt_aqaba.tif, not gebco_aqaba.tif, and the pipeline prefers a real "
                "GEBCO grid automatically if one is added."
            ),
        },
    ]


# ----------------------------------------------------------------------- cache

class TTLCache:
    """Small TTL cache keyed on a hash of the request payload.

    Keyed on content, not wall clock alone: the same scenario requested twice must
    hit cache even minutes apart, which is the whole point when a user is dragging
    a time slider back and forth over the same parameters.
    """

    def __init__(self, ttl_seconds: float = 900.0, maxsize: int = 256):
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._store: dict[str, tuple[float, Any]] = {}
        self.hits = 0
        self.misses = 0

    @staticmethod
    def key(*parts: Any) -> str:
        blob = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    def get(self, key: str):
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        ts, value = entry
        if time.monotonic() - ts > self.ttl:
            del self._store[key]
            self.misses += 1
            return None
        self.hits += 1
        return value

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self.maxsize:
            oldest = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest]
        self._store[key] = (time.monotonic(), value)

    def stats(self) -> dict:
        return {"hits": self.hits, "misses": self.misses, "size": len(self._store)}


PLUME_CACHE = TTLCache(ttl_seconds=1800)
EXPOSURE_CACHE = TTLCache(ttl_seconds=1800)


def clear_all_caches() -> None:
    catchments.cache_clear()
    reef_zones.cache_clear()
    outlets.cache_clear()
    events.cache_clear()
    data_sources.cache_clear()
    _feature_table.cache_clear()
    PLUME_CACHE._store.clear()
    EXPOSURE_CACHE._store.clear()
