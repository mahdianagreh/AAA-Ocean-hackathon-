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
    # Frozen by scripts/build_forecast_snapshot.py from forecast_runs/
    # forecast_catchment_rainfall/forecast_exceedance — the network-free demo path.
    # Live means "latest cached forecast" (tasks/phase3/00-phase3-plan.md), never a
    # request-time GFS/GEFS/Postgres call.
    "forecast_snapshot": DATA / "processed" / "forecasts" / "latest_snapshot.json",
    # The real 675-event rainfall-detected catalogue (scripts/build_event_catalogue.py).
    # Distinct from "event_dates" above: that file is the small, literature-cited
    # subset with paper provenance; this is the exhaustive daily-screening result.
    "event_catalogue": DATA / "processed" / "events" / "events.parquet",
    # Phase 5, B4 (site-scoring agent) — real evidence sources, Aqaba-only. A
    # bounding box outside where these three actually have coverage gets an
    # honest "insufficient_data" criterion, never a fabricated score.
    "osm_buildings": VECTORS / "osm_aqaba.gpkg",
    "osm_drainage": VECTORS / "osm_aqaba.gpkg",
    "rainfall_climatology": FEATURES / "catchment_rainfall_climatology.parquet",
    "bathymetry": DATA / "processed" / "bathymetry" / "depth_utm36n.tif",
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
def catchments_gdf():
    """GeoDataFrame form — Phase 5, B4 needs real catchment geometry to know
    which catchments' rainfall climatology (C2) applies to an arbitrary box,
    the same way `reef_zones_gdf()` exists for the exposure engine's overlay."""
    return _geo(ARTIFACTS["catchments"])


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


# One file today. Keyed by event_id rather than a glob, same reasoning as
# training_row()'s explicit date-parse — a per-event file is either the one that
# exists or it doesn't, and there is no pattern to infer one from the other yet.
MOORING_FILES: dict[str, Path] = {
    "AQ-2016-10-28": DATA / "processed" / "marine" / "mooring_target_AQ-2016-10-28.json",
}


def mooring_for(event_id: str) -> dict | None:
    """The parsed mooring record for one event, or None — same contract as
    training_row(): no file for this event is not an error, it is a gap the
    caller must be able to see rather than a synthesized default."""
    path = MOORING_FILES.get(event_id)
    if path is None or not path.exists():
        return None
    from models.calibration import load_mooring_target

    return load_mooring_target(path)


# Karam's basemap export (scripts/frontend_basemap.py), not a `data/processed/`
# contract path — it's committed for the frontend's offline map layer, and this
# reads the same file rather than a second derivation of the same POIs.
PLACES_PATH = ROOT / "frontend" / "public" / "basemap" / "places.geojson"


@lru_cache(maxsize=1)
def dive_sites() -> list[dict]:
    """Dive-site POIs, `kind == "dive"` in Karam's basemap export. `osm_id` is the
    stable join key — his 6 Aug handoff confirmed 115/115 unique, survives the OSM
    re-extract, where the file previously had no stable ID on any POI at all.

    Named "kind: dive" in the source, but that OSM category is broader than
    underwater dive sites — it also carries Wadi Rum desert attractions (Siq al
    Khazali, Barrah Canyon, sand dunes), tens of km inland from Aqaba. Returned
    as-is here, unfiltered further; `dive_sites_with_nearest_zone()` reports the
    real distance to the nearest reef zone so a caller can see which of these are
    actually coastal rather than trust the category name.
    """
    if not PLACES_PATH.exists():
        return []
    data = json.loads(PLACES_PATH.read_text())
    out = []
    for f in data.get("features", []):
        if f.get("properties", {}).get("kind") != "dive":
            continue
        # Geometry is MultiPoint, not Point, even for a single-location POI —
        # take the first point as the representative location.
        lon, lat = f["geometry"]["coordinates"][0]
        out.append({
            "osm_id": f["properties"]["osm_id"],
            "name_en": f["properties"].get("name_en"),
            "name_ar": f["properties"].get("name_ar"),
            "lon": lon,
            "lat": lat,
        })
    return out


def dive_sites_with_nearest_zone() -> list[dict]:
    """Each dive site joined to its nearest reef zone by real EPSG:32636 distance
    — never a lookup by proximity in degrees, which distorts distance differently
    north-south vs east-west (the same rule `exposure/engine.py` enforces via
    `_assert_measure_crs`). Distance is always reported, however large — a POI
    tens of km inland (see `dive_sites()`'s docstring) is not silently dropped,
    its distance just says so; the caller decides what counts as "too far to be
    a real dive-site safety concern," this function only measures.
    """
    sites = dive_sites()
    if not sites:
        return []
    zones = reef_zones_gdf()
    if zones is None or zones.empty:
        return [{**s, "nearest_reef_zone_id": None, "distance_m": None} for s in sites]

    import geopandas as gpd
    from shapely.geometry import Point

    from exposure.engine import CRS_MEASURE

    zones_utm = zones.to_crs(CRS_MEASURE)
    out = []
    for s in sites:
        pt = (gpd.GeoSeries([Point(s["lon"], s["lat"])], crs="EPSG:4326")
              .to_crs(CRS_MEASURE).iloc[0])
        d = zones_utm.geometry.distance(pt)
        idx = d.idxmin()
        out.append({
            **s,
            "nearest_reef_zone_id": zones_utm.loc[idx, "reef_zone_id"],
            "distance_m": float(d.loc[idx]),
        })
    return out


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
            # Phase 5, B8: a read-time overlay, applied below the loop, on top of
            # whatever the base .gpkg says — see reef_zone_photos.py's docstring
            # for why the override lives here rather than in a rewritten .gpkg
            # (./data is mounted read-only in the deployed container; found while
            # wiring approve_sensitivity_weight against it, not assumed).
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

    # Read-time overlay: a human-approved sensitivity_weight override, if one
    # exists for a zone. The base .gpkg above is never rewritten by this
    # function or by anything the running API calls.
    from models.reef_zone_photos import all_overrides

    overrides = all_overrides()
    for rec in out:
        override = overrides.get(rec["reef_zone_id"])
        if override is not None:
            rec["sensitivity_weight"] = override
            rec["sensitivity_weight_status"] = "SCIENTIST_ASSIGNED"

    return sorted(out, key=lambda x: x["reef_zone_id"]), is_prov


def reef_zones_gdf():
    """GeoDataFrame form, for the exposure engine's overlay."""
    real = ARTIFACTS["reef_zones"]
    prov = ARTIFACTS["reef_zones_provisional"]
    path = real if real.exists() else prov
    gdf = _geo(path, layer="reef_zones")
    return gdf if gdf is not None else _geo(path)


# ------------------------------------------------------ site-scoring evidence (B4)

@lru_cache(maxsize=1)
def osm_buildings_gdf():
    """`osm_aqaba.gpkg`'s `buildings` layer, EPSG:4326 — Aqaba-only coverage.

    A bounding box that doesn't overlap this extract's real footprint is not a
    gap in this function; it's a gap in the request, and the caller (B4's
    scoring agent) must report that honestly rather than treat an empty clip
    as a real zero.
    """
    return _geo(ARTIFACTS["osm_buildings"], layer="buildings")


@lru_cache(maxsize=1)
def osm_drainage_gdf():
    """`osm_aqaba.gpkg`'s `drainage_features` layer — real `intermittent` tags,
    the same field `docs/data_dictionary.md` §3 already cites for the 27
    culverts and the waterway-composition breakdown."""
    return _geo(ARTIFACTS["osm_drainage"], layer="drainage_features")


@lru_cache(maxsize=1)
def rainfall_climatology_df():
    """`catchment_rainfall_climatology.parquet` — one row per catchment, real
    p50/p99 percentiles. `None` if the artifact is absent, never an empty
    DataFrame standing in for missing data."""
    import pandas as pd

    path = ARTIFACTS["rainfall_climatology"]
    return pd.read_parquet(path) if path.exists() else None


def bathymetry_path() -> Path | None:
    """`depth_utm36n.tif`'s path, or None if the raster isn't on disk. Callers
    sample it lazily with rasterio rather than loading the whole grid here —
    this function is a path lookup, not a raster cache."""
    path = ARTIFACTS["bathymetry"]
    return path if path.exists() else None


def bathymetry_stats_for_bbox(bbox: tuple[float, float, float, float]) -> dict | None:
    """Real min/max depth sampled from `depth_utm36n.tif` inside an arbitrary
    EPSG:4326 box — Phase 5, B4's C4 criterion. `None` when the box doesn't
    overlap the raster at all (outside Aqaba, or the window reads nothing but
    nodata) — never a fabricated depth range standing in for missing coverage.

    A windowed read (`rasterio.windows.from_bounds`), not a full-band load —
    the raster is 20.7 MB and this may be called with a small box repeatedly.
    """
    path = bathymetry_path()
    if path is None:
        return None

    import geopandas as gpd
    import numpy as np
    import rasterio
    from rasterio.windows import from_bounds
    from shapely.geometry import box as shapely_box

    with rasterio.open(path) as src:
        bounds_utm = gpd.GeoSeries(
            [shapely_box(*bbox)], crs="EPSG:4326"
        ).to_crs(src.crs).total_bounds
        try:
            window = from_bounds(*bounds_utm, transform=src.transform)
            data = src.read(1, window=window)
        except (ValueError, IndexError):
            return None
        if data.size == 0:
            return None
        nodata = src.nodata
        valid = data if nodata is None else data[data != nodata]
        valid = valid[~np.isnan(valid)] if valid.size else valid
        if valid.size == 0:
            return None
        # Raster is negative-down elevation; depth is positive-down.
        depths = -valid
        return {
            "n_cells": int(valid.size),
            "min_depth_m": float(depths.min()),
            "max_depth_m": float(depths.max()),
        }


# --------------------------------------------------------------------- outlets

@lru_cache(maxsize=1)
def outlets() -> list[dict]:
    """Outlet metadata, position_confidence included, straight from Mahdi's analysis.

    Used to hold a hand-typed `OUTLET_CONFIDENCE = {"AQ-O01": "good", ...}` guess
    written before `outlets.geojson` carried real per-outlet confidence. That guess
    diverged from the geometry team's actual DEM/culvert cross-check in three of
    five rows — AQ-O02 and AQ-O03 (both "CANDIDATE CORRECTION — unmodelled path to
    the sea" in the source) read back as "plausible" instead of "low", and AQ-O05
    (a verified natural wadi mouth) read back as merely "plausible" instead of
    "high". `scripts/06_catchments.py`'s own POSITION_CONFIDENCE table is the
    source of truth; this now reads it rather than re-guessing it.
    """
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
            # "unchecked" is the fallback POSITION_CONFIDENCE.get() itself uses for
            # any outlet it has no entry for — never invent "plausible" here either.
            "position_confidence": _clean(r.get("position_confidence")) or "unchecked",
            "position_confidence_note": _clean(r.get("imagery_note")),
            "culvert_verdict": _clean(r.get("culvert_verdict")),
            "upstream_km2": _clean(r.get("upstream_km2")),
            "nearest_culvert_m": _clean(r.get("nearest_culvert_m")),
            "culverts_within_2500m": _clean(r.get("culverts_within_2500m")),
            "unmodelled_coastal_culverts": _clean(r.get("unmodelled_coastal_culverts")),
            "source_caveat": _clean(r.get("caveat")),
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


@lru_cache(maxsize=1)
def event_catalogue() -> list[dict]:
    """The real, exhaustive 675-event rainfall catalogue
    (scripts/build_event_catalogue.py), sorted by `rank` (1 = highest
    `max_daily_mm`). THE canonical ranking for "which storm was worst" — `rank`
    /`max_daily_mm`, not `max_anomaly_ratio`, which ranks storms differently and
    is exposed for reference only (Phase 4 §01-karam.md item 1).

    Deliberately separate from `events()`: that function's docstring calls
    docs/event_dates.md "the source of truth" for the small literature-cited
    list, and nothing else in this codebase depends on that contract — this is
    the exhaustive daily-screening result, source of the ranking/search data
    Phase 4 actually needs. Empty list if the artifact is absent — missing is
    missing, no fallback to the 5-event markdown list pretending to be 675.
    """
    import pandas as pd

    path = ARTIFACTS["event_catalogue"]
    if not path.exists():
        return []
    df = pd.read_parquet(path, columns=[
        "event_id", "date", "rank", "max_daily_mm", "mean_daily_mm",
        "max_anomaly_ratio", "catchments_exceeding_p99", "wettest_catchment",
        "storm_days", "is_exhaustive",
    ]).sort_values("rank")
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df.to_dict("records")


@lru_cache(maxsize=8)
def flood_arrival_utc(event_id: str):
    """The moment sediment reaches the sea, for `event_id` -- the release time
    a plume simulation starts from. Parsed from `docs/event_dates.md`'s
    machine-readable YAML block (`converted.flood_arrival_utc`), never
    hard-coded — that file's rule 1, same contract `scripts/28_calibrate_plume_engine.py`
    parses for the calibration run.

    Returns a tz-aware `datetime.datetime`, or `None` if the event has no
    entry there (an unresolved event, e.g. February 2013, or one outside the
    documented list) — the caller decides whether that is fatal.
    """
    import re
    from datetime import timezone

    import yaml

    path = ARTIFACTS["event_dates"]
    if not path.exists():
        return None
    blocks = re.findall(r"```yaml\n(.*?)```", path.read_text(encoding="utf-8"), re.S)
    if not blocks:
        return None
    parsed = yaml.safe_load(blocks[-1]) or {}
    for entry in parsed.values():
        if not isinstance(entry, dict) or entry.get("event_id") != event_id:
            continue
        arrival = (entry.get("converted") or {}).get("flood_arrival_utc")
        if arrival is None:
            return None
        # PyYAML's implicit timestamp resolver turns an unquoted ISO string
        # like `2016-10-28T00:00:00Z` into a native datetime already.
        if isinstance(arrival, str):
            from datetime import datetime as _dt

            arrival = _dt.fromisoformat(arrival.replace("Z", "+00:00"))
        return arrival if arrival.tzinfo else arrival.replace(tzinfo=timezone.utc)
    return None


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


@lru_cache(maxsize=1)
def forecast_snapshot() -> dict | None:
    """The frozen GFS/GEFS snapshot (scripts/build_forecast_snapshot.py), the
    only forecast data any endpoint may serve. None if the file is absent —
    missing is missing, never a live GFS/GEFS/Postgres call to fill the gap."""
    path = ARTIFACTS["forecast_snapshot"]
    if not path.exists():
        return None
    return json.loads(path.read_text())


def gefs_exceedance_for(catchment_id: str) -> dict | None:
    """This catchment's row from the cached snapshot's `gefs_exceedance` array --
    `exceedance_prob`/`members_exceeding`/`members_total` against Karam's real p99
    climatology (`catchment_rainfall_climatology`, `forecast_pipeline.py`). `None`
    when the snapshot is absent or has no row for this catchment -- the caller
    must treat that as a real gap, not fall back to a silent fabricated number."""
    snapshot = forecast_snapshot()
    if not snapshot:
        return None
    for row in snapshot.get("gefs_exceedance", []):
        if row.get("catchment_id") == catchment_id:
            return row
    return None


def clear_all_caches() -> None:
    catchments.cache_clear()
    catchments_gdf.cache_clear()
    reef_zones.cache_clear()
    outlets.cache_clear()
    events.cache_clear()
    event_catalogue.cache_clear()
    data_sources.cache_clear()
    _feature_table.cache_clear()
    forecast_snapshot.cache_clear()
    osm_buildings_gdf.cache_clear()
    osm_drainage_gdf.cache_clear()
    rainfall_climatology_df.cache_clear()
    PLUME_CACHE._store.clear()
    EXPOSURE_CACHE._store.clear()
