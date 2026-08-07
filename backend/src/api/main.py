"""ReefShield Aqaba API — every endpoint from concept §17.

Run:  .venv/bin/uvicorn backend.src.api.main:app --reload
Docs: http://127.0.0.1:8000/docs

DESIGN NOTES THAT MATTER MORE THAN THE ROUTES
---------------------------------------------
* Shapes are the contract. `schemas.py` is the deliverable; these handlers are the
  implementation behind it. Where a real model does not exist yet the response is
  shaped correctly and flagged `is_stub=True` with a critical caveat, rather than
  being absent — the frontend cannot build against a 404.

* Caveats travel in the payload. Never only in a doc. See `caveats.py`.

* Nothing here opens a database connection. Reads go through `data_access`, which
  is the single place that knows where a contract artifact lives. Exposure runs
  persist through `exposure.store`, which writes local SQLite behind two functions —
  see its docstring for why that is still right now that Nizar's Supabase session
  layer exists.

* Missing is missing. If an artifact is absent the endpoint says so — it does not
  invent a plausible placeholder to keep its shape.

MERGE NOTE, 3 Aug 2026
----------------------
origin/main carried a deliberately thin API whose own docstring said "Pulga owns the
real backend; this exists so `docker compose up` answers on day one". This file
supersedes it, but four things from it were kept rather than discarded because they
are deployment contract, not scaffolding:

  * `/health` at the UNVERSIONED path — the Dockerfile HEALTHCHECK targets it
  * CORS origins from `REEFSHIELD_CORS_ORIGINS`, which Compose already sets
  * `REEFSHIELD_ROOT` for the container data volume
  * `/api/v1/models` and the real `runoff_model.predict_one` wiring

`/runoff/predict` now tries the real model first and falls back to the stub only when
no artifact is registered, so it upgrades itself when training lands.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from exposure import engine, store
from ingestion import ocean_currents as oc
from models import particle_engine, plume_forcing
from rag import answer as rag_answer
from rag import corpus as rag_corpus
from rag import explain as rag_explain
from rag import index as rag_index
from . import caveats as cav
from . import data_access as da
from .schemas import (
    AlertOut,
    AskRequest,
    AskResponse,
    BacktestRequest,
    BacktestResult,
    CatchmentOut,
    Caveat,
    DataSourceOut,
    DiveSiteOut,
    DriverOut,
    EventOut,
    ExplainRequest,
    ExplainResponse,
    ExposureRequest,
    ExposureResult,
    ExposureRun,
    HealthOut,
    MooringMarker,
    MooringOut,
    OutletOut,
    PlumeContour,
    PlumeRequest,
    PlumeResult,
    Provenance,
    ReefZoneOut,
    RunoffPrediction,
    RunoffRequest,
    Value,
)

API_VERSION = "0.2.0"
PREFIX = "/api/v1"
ROOT = Path(os.environ.get("REEFSHIELD_ROOT", Path(__file__).resolve().parents[3]))
PLUME_CALIBRATION_PATH = ROOT / "data" / "models" / "plume_calibration.json"


def _load_plume_calibration() -> dict | None:
    """The winning (diffusion, windage, settling, regime) tuple from
    `scripts/28_calibrate_plume_engine.py`, if that has been run. A sidecar,
    like `data/models/sediment_anchor.json` -- never baked into the engine
    module, so a recalibration is a file swap, not a redeploy."""
    if not PLUME_CALIBRATION_PATH.exists():
        return None
    try:
        return json.loads(PLUME_CALIBRATION_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _particle_engine_version() -> str:
    calibration = _load_plume_calibration()
    if calibration:
        return f"custom_2d-calibrated-{calibration['event_id']}"
    return "custom_2d-uncalibrated"


def _reef_zones_version() -> str:
    """Report which reef-zone artifact is actually being served.

    Resolved rather than hardcoded: this string ends up in every stored exposure
    run's `model_versions`, and a run recorded as PROVISIONAL when it was computed
    against the real Atlas export would be unreconstructable later.
    """
    return "PROVISIONAL" if da.reef_zones()[1] else "AllenCoralAtlas-v2_0"


MODEL_VERSIONS = {
    "exposure_engine": "0.2.0",
    "runoff_model": "stub-0.1",
    "particle_engine": _particle_engine_version(),
    "reef_zones": _reef_zones_version(),
    "bathymetry": "GMRT-substituted-for-GEBCO",
}

app = FastAPI(
    title="ReefShield Aqaba API",
    version=API_VERSION,
    description=(
        "Sediment-plume risk to Aqaba's coral reefs. Every response that carries a "
        "limitation ships it as structured `caveats`, so the UI can render a caveat "
        "beside the number it qualifies."
    ),
)

# The frontend is a separate origin during development.
# Origins come from the environment so the container can be locked down without a
# code change. Carried over from origin/main's API, which Docker Compose already
# configures this way; defaulting to the Vite dev port keeps local work unchanged.
#
# PLUS a regex fallback for any localhost/127.0.0.1 port. Found by actually running
# the frontend against this API rather than assuming the fixed list was enough:
# API_PORT=8100 and a non-default frontend port (needed on this project's own dev
# machine, repeatedly, because 8000/5173 are often already taken by something else)
# made every live call fail with a CORS error that has nothing to do with the API
# itself. That is exactly the failure mode this project keeps naming — a correct
# backend that LOOKS broken — except inverted: here the frontend looks broken while
# the backend is fine. Safe to widen this way because the API never leaves
# localhost; it is a wifi-off local demo tool, not a public deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get(
        "REEFSHIELD_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",") if o],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------- ops liveness (Docker)

def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
            text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return os.environ.get("GIT_SHA", "unknown")


@app.get("/health", tags=["ops"])
def ops_health():
    """Liveness for the container. Kept at the UNVERSIONED path on purpose.

    The Dockerfile's HEALTHCHECK hits `/health`, so this path is part of the
    deployment contract and must not move to /api/v1. It stays cheap and must not
    depend on Supabase — a network blip should not restart the API — and it must
    survive the model layer being unimportable, hence the guarded lookup.

    `/api/v1/health` is the richer, artifact-aware version for the dashboard.
    """
    try:
        from models import artifacts
        model_available = artifacts.latest_version() is not None
    except Exception:
        model_available = False

    return {
        "status": "ok",
        "version": API_VERSION,
        "commit": git_sha(),
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "model_available": model_available,
        "data_volume_mounted": (ROOT / "data/processed/vectors/catchments.gpkg").exists(),
    }


@app.get(f"{PREFIX}/models", tags=["model"])
def models():
    """What is being served, and whether it is real.

    From origin/main: the dashboard shows provenance rather than asserting a number
    is trustworthy. 503 rather than an empty object, so a caller cannot mistake
    absence for a healthy default.
    """
    try:
        from models.runoff_model import available_versions, model_info
    except Exception as exc:
        raise HTTPException(503, {
            "error": "model layer unavailable",
            "why": f"{type(exc).__name__}: {exc}",
        }) from exc
    try:
        info = model_info()
    except FileNotFoundError as exc:
        raise HTTPException(503, {
            "error": "no trained model registered", "why": str(exc),
        }) from exc
    return {"serving": info, "versions": [v["id"] for v in available_versions()]}


# ---------------------------------------------------------------------- health

@app.get(f"{PREFIX}/health", response_model=HealthOut, tags=["meta"])
def health():
    status = da.artifact_status()
    missing = [k for k, present in status.items() if not present]

    reasons = []
    if "reef_zones" in missing:
        reasons.append(
            "reef_zones.gpkg absent — serving reef_zones_PROVISIONAL.gpkg. The Allen "
            "Coral Atlas export is blocked on Earth Engine browser authentication."
        )
    for name in ("landcover", "soil", "urban"):
        if name in missing:
            reasons.append(f"{name}_by_catchment.parquet absent — run aggregate_catchments.py")
    if "catchments" in missing:
        reasons.append("catchments.gpkg absent — geometry endpoints will be empty")

    return HealthOut(
        status="ok" if not reasons else "degraded",
        version=API_VERSION,
        artifacts_present=status,
        degraded_reason=reasons,
    )


@app.get(f"{PREFIX}/data-sources", response_model=list[DataSourceOut], tags=["meta"])
def data_sources():
    """Drives the UI's Data Sources panel. Provenance is a product surface here."""
    return [DataSourceOut(**s) for s in da.data_sources()]


# ------------------------------------------------------------------ catchments

def _catchment_out(rec: dict, detail: bool) -> CatchmentOut:
    cid = rec["catchment_id"]
    caveats = cav.catchment_area_uncertainty()
    prov = [Provenance(kind="derived", detail="30 m DEM delineation (Mahdi/Karam)")]

    lc = soil = urban = None
    if detail:
        lc = da.landcover_for(cid)
        soil = da.soil_for(cid)
        urban = da.urban_for(cid)
        if lc:
            caveats += cav.landcover_epoch()
            prov.append(Provenance(kind="source", detail="ESA WorldCover v200 2021, 10 m"))
        if soil:
            caveats += cav.soil_is_modelled()
            prov.append(Provenance(kind="source", detail="ISRIC SoilGrids v2.0, 250 m"))
        if urban:
            prov.append(Provenance(kind="source", detail="OpenStreetMap, ODbL 1.0"))

    return CatchmentOut(
        catchment_id=cid,
        outlet_id=rec.get("outlet_id"),
        area_km2=rec.get("area_km2") or 0.0,
        geometry=rec.get("geometry") if detail else None,
        landcover=lc,
        soil=soil,
        urban=urban,
        provenance=prov,
        caveats=caveats,
    )


@app.get(f"{PREFIX}/catchments", response_model=list[CatchmentOut], tags=["geometry"])
def list_catchments(
    include_geometry: bool = Query(False, description="GeoJSON is large; off by default"),
):
    recs = da.catchments(include_geometry=True)
    if not recs:
        raise HTTPException(503, "catchments.gpkg is not present")
    return [_catchment_out(r, detail=include_geometry) for r in recs]


@app.get(f"{PREFIX}/catchments/{{catchment_id}}", response_model=CatchmentOut,
         tags=["geometry"])
def get_catchment(catchment_id: str):
    for r in da.catchments(include_geometry=True):
        if r["catchment_id"] == catchment_id:
            return _catchment_out(r, detail=True)
    raise HTTPException(404, f"unknown catchment {catchment_id}")


@app.get(f"{PREFIX}/outlets", response_model=list[OutletOut], tags=["geometry"])
def list_outlets():
    """`caveat` prefers the geometry team's own per-outlet text over the harbour-only
    fallback, so AQ-O02/AQ-O03's "unmodelled path to the sea" candidate corrections
    and AQ-O01/AQ-O05's positive verifications reach the screen too — not only
    AQ-O04's. `cav.harbour_outlet()` still backstops AQ-O04 specifically, so a
    missing or edited source caveat can never silently drop that one warning.

    `upstream_km2`/`nearest_culvert_m` are passed through as plain floats, matching
    `frontend/src/api/types.ts`'s `Outlet` interface exactly (it already declares
    both as `number`, predating this pass) — NOT wrapped in `Value`, which would
    have broken `SideRail.tsx:147`'s existing `o.upstream_km2` read the moment live
    mode replaced fixtures.

    Each row is copied before mutation regardless: `da.outlets()` is `@lru_cache`d,
    so writing into its dicts in place is unsafe for any future field that does
    need transforming here.
    """
    out = []
    for raw in da.outlets():
        o = dict(raw)
        source_caveat = o.pop("source_caveat", None)
        harbour = cav.harbour_outlet(o["outlet_id"])
        caveat = source_caveat or (harbour[0].message if harbour else None)
        out.append(OutletOut(**o, caveat=caveat))
    return out


# ------------------------------------------------------------------ reef zones

@app.get(f"{PREFIX}/reef-zones", response_model=list[ReefZoneOut], tags=["geometry"])
def list_reef_zones(include_geometry: bool = Query(True)):
    zones, is_provisional = da.reef_zones(include_geometry=True)
    if not zones:
        raise HTTPException(503, "no reef zone artifact present")

    out = []
    for z in zones:
        caveats = cav.sensitivity_placeholder(z["sensitivity_weight_status"])

        if is_provisional:
            # The 250 m width assumption applies ONLY to the hand-placed geometry.
            caveats += cav.reef_zone_width()
            caveats += cav.provisional_reef_zones()
            if z["reef_zone_id"] in ("R-01", "R-02"):
                caveats.append(Caveat(
                    field="reef_zone_id",
                    message=(
                        f"{z['reef_zone_id']} covers developed beach and port frontage "
                        "where reef presence is doubtful. If the Allen Coral Atlas export "
                        "yields fewer real zones, this one may be dropped — the remaining "
                        "IDs keep their names and are never renumbered."
                    ),
                    severity="warning",
                    source="docs/data_dictionary.md §4",
                ))
        else:
            # Real ACA geometry. Emphatically NOT the 250 m assumption any more —
            # saying so would be a false statement about a 5 m Atlas product. What
            # does apply is that the named zones miss most of the mapped reef, and
            # that our depth grid disagrees with the Atlas in places.
            caveats += (cav.reef_area_correction() + cav.reef_scope_is_jordan()
                        + cav.reef_shallow_only()
                        + cav.depth_is_land_dominated(
                            z['reef_zone_id'], z.get('depth_land_cell_pct'),
                            z.get('depth_median_m')))
        out.append(ReefZoneOut(
            **{k: v for k, v in z.items() if k != "geometry"},
            geometry=z.get("geometry") if include_geometry else None,
            caveats=caveats,
        ))
    return out


# ---------------------------------------------------------------------- events

def _merged_events() -> list[dict]:
    """The real 675-event catalogue, each row optionally carrying its
    literature label/source on top of the real ranking columns.

    Base is `da.event_catalogue()` (exhaustive, real ranking) rather than
    `da.events()` (5-event markdown parse) -- Phase 4 found the API was never
    serving the catalogue at all. A literature-documented event (e.g.
    AQ-2016-10-28) keeps its human-readable label; every event keeps `rank`.
    """
    catalogue = da.event_catalogue()
    literature = {e["event_id"]: e for e in da.events()}
    if not catalogue:
        # No catalogue artifact on disk -- serve the literature list alone
        # rather than nothing, but say every row is missing its ranking.
        return list(literature.values())

    merged = []
    for row in catalogue:
        # Built field-by-field, not `**row` + overrides: `catalogue` is the
        # lru_cache'd list itself, and mutating a shared cached dict in place
        # (e.g. via .pop()) would corrupt it for every later request.
        lit = literature.get(row["event_id"])
        merged.append({
            "event_id": row["event_id"],
            "start": row["date"],
            "end": None,
            "label": lit["label"] if lit else None,
            "source": lit["source"] if lit else "data/processed/events/events.parquet",
            "caveats": [],
            "rank": row["rank"],
            "max_daily_mm": row["max_daily_mm"],
            "mean_daily_mm": row["mean_daily_mm"],
            "max_anomaly_ratio": row["max_anomaly_ratio"],
            "catchments_exceeding_p99": row["catchments_exceeding_p99"],
            "wettest_catchment": row["wettest_catchment"],
            "storm_days": row["storm_days"],
            "is_exhaustive": row["is_exhaustive"],
        })
    # A literature event absent from the catalogue would be a real gap worth
    # seeing, not a silent drop -- append it with its ranking fields at their
    # EventOut default of None, never fabricated.
    catalogued_ids = {r["event_id"] for r in catalogue}
    merged.extend(lit for eid, lit in literature.items() if eid not in catalogued_ids)
    return merged


@app.get(f"{PREFIX}/events", response_model=list[EventOut], tags=["events"])
def list_events():
    evs = _merged_events()
    if not evs:
        raise HTTPException(503, "no event catalogue or docs/event_dates.md present")
    return [EventOut(**e) for e in evs]


@app.get(f"{PREFIX}/events/{{event_id}}", response_model=EventOut, tags=["events"])
def get_event(event_id: str):
    for e in _merged_events():
        if e["event_id"] == event_id:
            return EventOut(**e)
    raise HTTPException(404, f"unknown event {event_id}")


@app.get(f"{PREFIX}/events/{{event_id}}/mooring", response_model=MooringOut,
         tags=["events"])
def event_mooring(event_id: str):
    """A thin read-through of the Kalman et al. (2025) mooring record — Phase 4,
    Real Sensor Proof Overlay. Shape matches frontend/public/fixtures/event.json's
    already-shipped `mooring` object field-for-field, so flipping fixture -> live
    needs no frontend change.

    404, not an empty/default object, when this event has no mooring record —
    today that is every event except AQ-2016-10-28.
    """
    raw = da.mooring_for(event_id)
    if raw is None:
        raise HTTPException(404, f"no mooring record for {event_id}")

    parsed = raw["_parsed"]
    m = raw["magnitude"]
    return MooringOut(
        event_id=raw["event_id"],
        source_citation=raw["source_citation"],
        source_doi=raw["source_doi"],
        source_file=raw["source_file"],
        position=raw["position"],
        markers=[
            MooringMarker(key="turbidity_onset", t=parsed["onset"], provenance="converted"),
            MooringMarker(key="turbidity_cleared", t=parsed["clear"], provenance="converted"),
        ],
        elevated_duration_hours=Value(
            value=raw["timing_utc"]["elevated_duration_hours"], unit="h",
            provenance="converted"),
        peak_suspended_sediment=Value(
            value=m["peak_suspended_sediment_g_l"], unit="g/L", provenance="reported"),
        salinity_minimum=Value(
            value=m["salinity_minimum_psu"], unit="PSU", provenance="reported"),
        salinity_anomaly=Value(
            value=m["salinity_anomaly_delta_psu"], unit="‰", provenance="reported",
            uncertainty={"sigma": m["salinity_anomaly_sigma"]}),
        sediment_mass_total=Value(
            value=m["sediment_mass_total_t"], unit="t", provenance="reported"),
        series_available=False,
        caveats=[],
    )


#: Real coastal dive/wreck sites (Gorgon 1, Cedar Pride Shipwreck, King Abdullah
#: reef, ...) measured 0-997 m from their nearest reef zone. Everything else
#: tagged `kind: dive` in the source OSM extract is a Wadi Rum desert attraction
#: (Barrah Canyon, sand dunes, petroglyphs) at 32,500 m or more — a 32x jump with
#: nothing between the two clusters. 2,000 m is a round number inside that gap,
#: not a fitted threshold; it exists to flag the mismatch, not to hide it.
DIVE_SITE_IMPLAUSIBLE_DISTANCE_M = 2000.0


@app.get(f"{PREFIX}/dive-sites", response_model=list[DiveSiteOut], tags=["geometry"])
def list_dive_sites():
    """Dive-site POIs joined to their nearest reef zone — Phase 4, feature B
    (Dive Site Safety Status). Karam's 6 Aug handoff: `osm_id` is now a stable
    join key in `places.geojson` (115/115 unique, confirmed against the source
    OSM re-extract).

    Returns the geometric join only — nearest_reef_zone_id and distance_m — not
    a risk score. A "safety status" needs an event/outlet-scoped exposure result,
    which this endpoint has no parameters for; the caller cross-references
    nearest_reef_zone_id against whatever `/alerts` or `/exposure/calculate`
    result it already has for the event it's showing, rather than this endpoint
    re-deriving that per dive site.
    """
    out = []
    for s in da.dive_sites_with_nearest_zone():
        caveats = []
        if s["distance_m"] is not None and s["distance_m"] > DIVE_SITE_IMPLAUSIBLE_DISTANCE_M:
            caveats.append(Caveat(
                field="nearest_reef_zone_id",
                message=(
                    f"{s['distance_m']:,.0f} m from the nearest reef zone. The "
                    "source OSM category (\"kind: dive\") also carries Wadi Rum "
                    "desert attractions alongside real coastal dive sites, and "
                    "this POI is far enough inland that it is very unlikely to "
                    "be an actual dive site — treat the join as unreliable for "
                    "this one, not as a real safety association."
                ),
                severity="warning",
                source="backend/src/api/data_access.py:dive_sites",
            ))
        out.append(DiveSiteOut(**s, caveats=caveats))
    return out


# -------------------------------------------------------------------- forecast

_ANOMALY_CAVEAT = (
    "Statistical outlier signal vs. climatology, not a validated early-warning "
    "system -- never checked against a real flood event's lead time. This is a "
    "different statement from the exceedance/confidence numbers above (\"N% of "
    "ensemble members agree\") and must render as a visually distinct UI element, "
    "never merged into the formal confidence meter."
)


@app.get(f"{PREFIX}/forecast/latest", tags=["forecast"])
def forecast_latest():
    """The cached GFS/GEFS snapshot — never a live network call.

    "Live" means "latest cached forecast" (tasks/phase3/00-phase3-plan.md): the
    real GFS/GEFS/Postgres pull happens ahead of time via
    scripts/build_forecast_snapshot.py, and this endpoint only ever reads that
    frozen file. The UI shows each model's `issued_at` so "cached, not live" is
    stated rather than implied.

    `anomalies` (B6) is a percentile-relative outlier score against Karam's real
    climatology, distinct from `exceedance` (the formal ensemble-agreement
    confidence number) -- see `_ANOMALY_CAVEAT` and
    `backend/src/processing/anomaly_detection.py`. Frontend: the "unusual
    pattern detected" banner is early/exploratory signal; the confidence meter
    is the formal number. Never conflate the two in copy or color.
    """
    snap = da.forecast_snapshot()
    if snap is None:
        raise HTTPException(
            503,
            "No forecast snapshot present. Run scripts/build_forecast_snapshot.py "
            "to freeze the latest GFS/GEFS run.",
        )
    return {
        "issued_at": {
            model: run["reference_time"] for model, run in snap["models"].items()
        },
        "models": snap["models"],
        "catchment_rainfall": snap["gfs_catchment_rainfall"],
        "exceedance": snap["gefs_exceedance"],
        "anomalies": snap.get("gefs_anomalies", []),
        "anomaly_caveat": _ANOMALY_CAVEAT,
    }


# -------------------------------------------------------- multi-source currents

# The demo event's mooring peak-response time, and the nearest point BOTH
# historical current archives resolve simultaneously (per
# docs/forcing_limitations.md — a systematic 0.01 deg scan of the whole marine
# AOI found zero points both models resolve at once; this is the nearest
# shared one, 6 km from the outlet). Defaults, not requirements — override via
# query params to compare "today" instead.
_DEMO_EVENT_TIME = "2016-10-28T06:50:00"
_DEMO_AGREEMENT_LON = 34.85
_DEMO_AGREEMENT_LAT = 29.30


@app.get(f"{PREFIX}/currents/agreement", tags=["forecast"])
def currents_agreement(
    lon: float = Query(default=_DEMO_AGREEMENT_LON),
    lat: float = Query(default=_DEMO_AGREEMENT_LAT),
    time: str = Query(
        default=_DEMO_EVENT_TIME,
        description="ISO 8601. Defaults to the demo event's mooring peak-response "
        "time, per docs/forcing_limitations.md's own instruction to use that number "
        "over 'today's' figure for anything backtest-facing.",
    ),
    historical: bool = Query(
        default=True,
        description="True: read the cached AQ-2016-10-28 archives (HYCOM "
        "GLBu0.08/expt_91.2, Copernicus GLORYS12V1). False: read the live/rolling "
        "'recent' cache instead.",
    ),
):
    """Multi-source weather agreement — the currents reading of Feature F.

    "Multi-Source Weather Agreement" (tasks/phase4/00-phase4-plan.md, feature F)
    names no single comparison; HYCOM-vs-Copernicus-Marine currents is the one
    reading with real, network-free, already-honest numbers today (the other
    candidates -- GFS-vs-GEFS rainfall, GFS-vs-IFS via `ecmwf.gfs_vs_ifs_agreement`
    -- are either unbuilt or use an independently-invented threshold; see the
    dated note in tasks/phase4/00-phase4-plan.md).

    Never a live fetch: reads whichever cached `.nc` pair is already on disk
    (data/raw/currents/), exactly like `get_historical_interpolator()`. Reports a
    CONTINUOUS agreement score (1.0 at 0 deg disagreement, 0.0 at 180 deg) rather
    than reusing `qa_currents.py`'s hardcoded 15 deg good/bad cutoff -- that
    cutoff is exactly the kind of second, independently-invented threshold this
    feature is told not to introduce alongside item 2's ensemble-agreement
    formula.
    """
    import numpy as np

    if historical:
        hycom_path = oc.RAW_DIR / "hycom_aoi_AQ-2016-10-28.nc"
        copernicus_path = oc.RAW_DIR / "copernicus_marine_aoi_AQ-2016-10-28.nc"
    else:
        hycom_path = oc.RAW_DIR / "hycom_aoi_recent.nc"
        copernicus_path = oc.RAW_DIR / "copernicus_marine_aoi_recent.nc"

    if not hycom_path.exists():
        raise HTTPException(
            503, f"No cached current data at {hycom_path} for this window."
        )

    try:
        parsed_time = np.datetime64(time)
    except ValueError as exc:
        raise HTTPException(422, f"unparseable time {time!r}: {exc}") from exc

    comparison = oc.compare_hycom_vs_copernicus(
        lon=lon, lat=lat, time=parsed_time,
        hycom_path=hycom_path, copernicus_path=copernicus_path,
    )
    # NaN, not None, when a point/time falls outside a cached grid's resolved
    # cells or its time range (e.g. the "recent" cache aging past its fetch
    # window). A gap is a gap, per the project's standing rule -- and it's what
    # stops FastAPI's default JSON encoder from 500ing on a bare nan.
    comparison = {
        k: (None if isinstance(v, float) and np.isnan(v) else v)
        for k, v in comparison.items()
    }

    diff = comparison.get("direction_diff_deg")
    agreement = max(0.0, 1.0 - diff / 180.0) if diff is not None else None

    return {
        **comparison,
        "agreement": agreement,
        "window": "historical (AQ-2016-10-28 mooring peak)" if historical else "live/recent",
        "sources": {
            "hycom": "HYCOM GLBu0.08/expt_91.2" if historical else "HYCOM GLBy0.08 (latest)",
            "copernicus_marine": "GLORYS12V1 multiyear reanalysis" if historical
                else "GLOBAL_ANALYSISFORECAST_PHY_001_024",
        },
        "caveats": [
            {
                "field": "agreement",
                "message": "Both models mask the provisional outlet (34.96, 29.52) as "
                            "unresolved/land identically -- corroborating, not "
                            "contradicting, evidence for the ~9km resolution limit. "
                            "See docs/forcing_limitations.md.",
                "severity": "warning",
                "source": "backend/src/ingestion/ocean_currents.py",
            },
        ],
    }


# ---------------------------------------------------------------------- runoff

#: Raw rainfall-depth features the `rainfall_multiplier` scenario knob scales.
#: Deliberately excludes rain_over_p50/p90/p99 and rain_self_percentile — those are
#: percentile ranks against the historical record, and "150% of the 90th percentile"
#: is not a meaningful operation. Scaling only the raw-mm terms is a real, defensible
#: perturbation; recomputing percentiles against a scaled value would be a second,
#: much larger piece of work (re-deriving the historical distribution per request)
#: that Phase 4 does not attempt.
RAINFALL_MM_COLUMNS = ("precipitation_mm_day", "precip_prior_1d_mm",
                       "precip_prior_3d_mm", "precip_prior_7d_mm")


def _apply_rainfall_multiplier(row: dict, multiplier: float) -> dict:
    if multiplier == 1.0:
        return row
    return {**row, **{c: row[c] * multiplier for c in RAINFALL_MM_COLUMNS
                      if row.get(c) is not None}}


def _squash_sediment_index(index, anchor_index, sediment_class) -> tuple[float, str]:
    """The raw sediment index is unbounded; every caller that needs 0-1 squashes
    it by ratio / (1 + ratio) against the anchor event — extracted so the two
    call sites (exposure_calculate, runoff_predict) cannot silently drift onto
    two different formulas for the same number.

    NOT a linear ratio clamped at 1.0, which was the first attempt and was worse
    than the zero it replaced: October 2016 is only 12th of 2,362 days by this
    magnitude, so every storm at or above it pinned to exactly 1.000 and the term
    stopped discriminating at all — three different events came back with an
    identical sediment intensity. This map is monotonic, never saturates, and
    puts the one documented major flood at 0.5 — the honest shape for a single
    calibration point, which has nothing justifying a linear extrapolation far
    above it.
    """
    from models.sediment_proxy import ANCHOR_EVENT

    ratio = max(0.0, float(index) / float(anchor_index))
    intensity = ratio / (1.0 + ratio)
    source = (
        f"sediment_index {float(index):,.0f} = {ratio:.2f}x {ANCHOR_EVENT}, "
        f"squashed by r/(1+r) to {intensity:.3f} (class {sediment_class}); "
        "anchor maps to 0.500"
    )
    return intensity, source


@app.post(f"{PREFIX}/runoff/predict", response_model=RunoffPrediction, tags=["model"])
def runoff_predict(req: RunoffRequest):
    """Real model when a trained artifact is registered; stub otherwise.

    Mahdi's model layer is built and validated, but it is blocked on the feature
    matrix (`event_catchment_features.parquet`) while rainfall is re-pulled against
    the corrected AOI. So this tries the real predictor FIRST and falls back to the
    stub only when nothing is registered — that way the endpoint upgrades itself the
    moment training lands, with no change here and no change to the response shape.

    The import is local, not module-scope: the real predictor pulls xgboost and shap,
    and the API must still boot and answer /health when the model layer cannot load.
    """
    if not any(c["catchment_id"] == req.catchment_id for c in da.catchments()):
        raise HTTPException(404, f"unknown catchment {req.catchment_id}")

    # Prefer a real feature row (da.training_row) over the request's own fields.
    #
    # Mahdi found (docs/HANDOFF_pulga_2026-08-06.md) that predict_one() on the bare
    # request dict — catchment_id/rainfall_mm_3h/antecedent_index, none of which
    # match the model's 20 real feature names — still runs cleanly and returns a
    # CONFIDENT-LOOKING, FIXED result: identical runoff_probability, identical
    # feature_attributions, regardless of catchment or event. TreeSHAP does not
    # fail on an all-NaN row, so `feature_attributions_status` stays None in this
    # case too — the model cannot self-report that this happened. It has to be
    # caught here, not trusted from predict_one()'s output.
    training_row = da.training_row(req.event_id, req.catchment_id) if req.event_id else None
    base_features = training_row if training_row is not None else req.model_dump(exclude_none=True)
    features = _apply_rainfall_multiplier(base_features, req.rainfall_multiplier)

    try:
        from models.runoff_model import predict_one

        real = predict_one(
            features, transmission_loss_override=req.transmission_loss_override)
    except (FileNotFoundError, ImportError, ModuleNotFoundError):
        real = None            # nothing registered yet — fall through to the stub
    except KeyError as exc:    # unknown version id explicitly requested
        raise HTTPException(404, str(exc)) from exc

    if real is not None:
        # Trust the model's own numbers; do not re-derive or rescale them here.
        #
        # Read the keys the model ACTUALLY returns. Three of the four this block used to
        # ask for do not exist in `predict_one`'s output, and every one failed softly:
        #
        #   predicted_runoff_m3  absent -> defaulted to 0.0, so a real prediction was
        #                        rendered as "0 m3 of runoff". A fabricated zero
        #                        presented as a model output is the one thing this
        #                        project must never ship.
        #   model_version        absent -> fell back to "runoff-real" and the provenance
        #                        line read "Mahdi's runoff model None", so which artefact
        #                        produced a stored number was unrecoverable. The key is
        #                        `model_version_id`.
        #   relative_sediment_intensity  absent -> the chained fallback quietly served
        #                        `runoff_probability` under a sediment label. It returned
        #                        a real number, which is why nothing looked wrong.
        #
        # Component A is a runoff CLASSIFIER, not a volume regressor: there is no m3 to
        # report, so the field is None and reads as a gap. `sediment_index` is the
        # sediment measure and is unanchored — comparable between requests, no absolute
        # meaning — which `sediment_basis` states and which travels as a caveat.
        # The raw index is unbounded (e.g. 145,434 for the anchor storm) — this
        # schema's relative_sediment_intensity is ge=0/le=1, and constructing
        # RunoffPrediction below with the raw index would raise a
        # ValidationError. This was unreachable before Phase 4's training_row
        # preference: every prior caller sent a bare request, which produces a
        # small, already-in-range sediment_index (see the honesty branch
        # above) rather than a real anchored one. Squash exactly the way
        # exposure_calculate does — same formula, one function, so the two
        # cannot silently drift onto different numbers for the same input.
        sediment_index = real.get("sediment_index")
        anchor_index = real.get("anchor_index_for_normalisation")
        if sediment_index is not None and anchor_index:
            sediment_intensity, sediment_intensity_source = _squash_sediment_index(
                sediment_index, anchor_index, real.get("sediment_class"))
        else:
            sediment_intensity = float(real.get("runoff_probability", 0.0))
            sediment_intensity_source = str(real.get("sediment_basis", "unanchored"))
        minimal_request_caveats = []
        if training_row is not None:
            # Renamed at this boundary to match frontend/src/api/predictions.ts's
            # PredictionDriver{key, contribution, value} exactly — the model's own
            # names (`feature`, `shap`) never reach the response. See schemas.DriverOut.
            drivers = [
                DriverOut(key=d["feature"], contribution=d["shap"], value=d["value"])
                for d in (real.get("feature_attributions") or [])
            ]
            feature_attributions_status = real.get("feature_attributions_status")
        else:
            # See the comment above `training_row` for why this branch exists:
            # a bare request produces a fixed, catchment/event-independent result
            # that predict_one() itself cannot flag. Suppressed here rather than
            # returned as if real — a plausible-looking chart of drivers that do
            # not depend on the input is worse than no chart.
            drivers = []
            feature_attributions_status = (
                "not meaningful — no training-set feature row for this request "
                f"(event_id={req.event_id!r}); only rainfall_mm_3h/antecedent_index "
                "were supplied, not the 20 features the model reads, so this "
                "result would be identical across every catchment and event"
            )
            minimal_request_caveats = [Caveat(
                field="runoff_probability",
                message="No event_id matched a real training-set feature row, so "
                        "runoff_probability, sediment_index and every other "
                        "real-path field here were computed from a mostly-absent "
                        "feature vector — the same fixed result regardless of "
                        "catchment or event. Supply event_id for a date/catchment "
                        "in the training set for a meaningful prediction.",
                severity="critical",
                source="docs/HANDOFF_pulga_2026-08-06.md",
            )]
        return RunoffPrediction(
            catchment_id=req.catchment_id,
            predicted_runoff_m3=None,
            relative_sediment_intensity=sediment_intensity,
            runoff_probability=real.get("runoff_probability"),
            severity=real.get("severity"),
            confidence=real.get("confidence"),
            # Lowercased, and None is preserved rather than replaced. The proxy emits
            # "Medium" (capitalised) and returns None when it has not run; `.get(k, default)`
            # does not help with the second case because the key IS present and holds None.
            sediment_class=(str(real["sediment_class"]).lower()
                            if real.get("sediment_class") is not None else None),
            model_version=str(real.get("model_version_id", "unregistered")),
            is_stub=False,
            drivers=drivers,
            feature_attributions_status=feature_attributions_status,
            rainfall_multiplier=req.rainfall_multiplier,
            transmission_loss=real.get("transmission_loss"),
            provenance=[
                Provenance(kind="derived",
                           detail=f"Mahdi's runoff model {real.get('model_version_id')}"),
                Provenance(kind="source", detail=str(real.get("basis", "unknown"))),
            ],
            caveats=(cav.landcover_epoch() + cav.soil_is_modelled()
                     + minimal_request_caveats
                     + [Caveat(field="predicted_runoff_m3",
                               message="Component A predicts runoff OCCURRENCE, not "
                                       "volume. No m3 figure exists; this is a gap, "
                                       "not a zero.",
                               severity="critical",
                               source="backend/src/models/runoff_model.py"),
                        Caveat(field="relative_sediment_intensity",
                               message=sediment_intensity_source,
                               severity="warning",
                               source="backend/src/models/sediment_proxy.py")]),
        )

    lc = da.landcover_for(req.catchment_id) or {}
    bare = lc.get("frac_bare_sparse_vegetation")

    # Monotonic in rainfall and in bare-ground fraction so the stub at least moves
    # in physically sensible directions while the UI is built against it.
    bare_term = bare if isinstance(bare, (int, float)) else 0.9
    intensity = max(0.0, min(1.0, (req.rainfall_mm_3h / 60.0) * (0.5 + 0.5 * bare_term)))
    area = next((c["area_km2"] or 0.0 for c in da.catchments()
                 if c["catchment_id"] == req.catchment_id), 0.0)
    runoff_m3 = req.rainfall_mm_3h * 1e-3 * area * 1e6 * 0.35

    cls = ("extreme" if intensity > 0.75 else "high" if intensity > 0.5
           else "medium" if intensity > 0.25 else "low")

    return RunoffPrediction(
        catchment_id=req.catchment_id,
        predicted_runoff_m3=runoff_m3,
        relative_sediment_intensity=intensity,
        sediment_class=cls,
        model_version=MODEL_VERSIONS["runoff_model"],
        is_stub=True,
        provenance=[
            Provenance(kind="stub", detail="Placeholder response; not a prediction"),
            Provenance(kind="source", detail="frac_bare_sparse_vegetation from WorldCover v2"),
        ],
        caveats=cav.stub_model("The runoff model") + cav.landcover_epoch(),
    )


# ----------------------------------------------------------------------- plume

#: Built once per process, keyed by event_id -- constructing the fast current
#: interpolator costs one xarray load + one RegularGridInterpolator build (a
#: few hundred ms), not per-request work.
_CURRENT_FN_CACHE: dict[str, tuple] = {}


def _current_fn_for_event(event_id: str) -> tuple:
    """Real historical currents where a cached archive exists, a documented
    placeholder otherwise. `get_historical_interpolator` only ever resolves
    `AQ-2016-10-28` (05-abd.md's one demo event; see docs/event_dates.md) --
    any other event_id genuinely has no current forcing behind it yet.

    Never fetches over the network at request time: DoD item 9 is "works
    with wifi off", and a live endpoint reaching out mid-demo is exactly the
    Harmony-preview class of failure this project keeps naming. Run
    `scripts/28_calibrate_plume_engine.py` once beforehand -- it caches the
    HYCOM archive as a side effect of calibrating against it.
    """
    if event_id in _CURRENT_FN_CACHE:
        return _CURRENT_FN_CACHE[event_id]

    cache_file = oc.RAW_DIR / f"hycom_aoi_{event_id}.nc"
    if cache_file.exists():
        import xarray as xr

        interpolator = oc.CurrentFieldInterpolator(xr.open_dataset(cache_file))
        result = (
            plume_forcing.fast_current_fn(interpolator),
            f"HYCOM GLBu0.08/expt_91.2 historical archive, cached {cache_file.relative_to(ROOT)}",
        )
    else:
        result = (
            particle_engine.ConstantCurrentField(0.0, 0.0),
            f"PLACEHOLDER: ConstantCurrentField(0, 0) -- no cached historical current "
            f"archive for {event_id} ({cache_file.name} absent). Run "
            "scripts/28_calibrate_plume_engine.py once to fetch it.",
        )
    _CURRENT_FN_CACHE[event_id] = result
    return result


def _sediment_class_for(event_id: str, catchment_id: str | None) -> str | None:
    """Mahdi's sediment class for this event/catchment, if a feature row
    exists -- used only to scale release magnitude (particle count), never to
    change the physics. `None` (no row, or the real model unavailable) keeps
    the release unscaled rather than guessing a severity."""
    if not catchment_id:
        return None
    row = da.training_row(event_id, catchment_id)
    if row is None:
        return None
    try:
        from models.runoff_model import predict_one

        cls = predict_one(row).get("sediment_class")
    except (FileNotFoundError, ImportError, ModuleNotFoundError, KeyError):
        return None
    # runoff_predictions.sediment_class values are capitalized ("High"); the
    # particle engine's SEDIMENT_CLASS_PARTICLE_SCALE keys are lowercase.
    return cls.lower() if isinstance(cls, str) else None


def _real_contours(req: PlumeRequest, outlet: dict):
    """Run the real particle engine and contour its output.

    Returns `(rows, provenance_detail, caveats)` -- `rows` are plain dicts
    shaped like `PlumeContour`'s fields (`t_hours`, `probability`, `geometry`
    as a GeoJSON dict in EPSG:4326), ready for the response and for
    `engine.intersect_plume_with_zones` after a GeoDataFrame wrap.
    """
    try:
        release = particle_engine.load_release_point(req.outlet_id)
    except particle_engine.HarbourBasinReleaseError:
        # Still simulated -- refusing outright would make AQ-O04 the one
        # outlet with no picture at all. cav.harbour_outlet() carries the
        # "not representative Gulf exposure" warning on every response either
        # way, so acknowledging here does not hide anything.
        release = particle_engine.load_release_point(
            req.outlet_id, acknowledge_harbour_caveat=True)

    release_time = da.flood_arrival_utc(req.event_id)
    if release_time is None:
        raise HTTPException(
            422,
            f"{req.event_id} has no converted.flood_arrival_utc in docs/event_dates.md "
            "-- the particle engine needs a real release time and will not guess one",
        )

    calibration = _load_plume_calibration()
    calibrated_here = bool(calibration) and calibration.get("event_id") == req.event_id
    base_params = calibration["params"] if calibrated_here else {}

    sediment_class = _sediment_class_for(req.event_id, release.catchment_id)
    particle_count = particle_engine.particle_count_for_sediment_class(
        req.n_particles, sediment_class)
    # Capped regardless of the sediment-class multiplier (up to 2x): a cold
    # run costs ~particle_count x n_steps current_fn calls, and this endpoint
    # must return in seconds on first call, not minutes. da.PLUME_CACHE makes
    # every repeat call with the same parameters instant.
    particle_count = min(particle_count, 3000)

    params = particle_engine.ParticleEngineParams(
        diffusion_m2_s=(req.diffusion_m2_s if req.diffusion_m2_s is not None
                         else base_params.get("diffusion_m2_s", 1.0)),
        windage_fraction=(req.windage if req.windage is not None
                           else base_params.get("windage_fraction", 0.03)),
        settling_velocity_mm_s=base_params.get("settling_velocity_mm_s", 0.5),
        transport_regime=base_params.get("transport_regime", "hypopycnal"),
        particle_count=particle_count,
        duration_hours=float(req.horizon_hours),
    )

    current_fn, current_source = _current_fn_for_event(req.event_id)
    wind_fn = particle_engine.ConstantWindField(0.0, 0.0)

    # Known, documented gotcha (tasks/nizar.md, 06-ali.md §5): some outlets sit on
    # a cell the ~9 km current grid masks as land, so `current_fn` returns NaN
    # there and `simulate()`'s own `nan_to_num(..., nan=0.0)` silently makes the
    # release point current-free -- transport becomes diffusion/settling only,
    # not current-driven. That is a real, first-order fact about this specific
    # run, not a footnote, so it is checked and surfaced here rather than left to
    # be discovered by noticing the plume never travels far.
    release_u, release_v = current_fn(release.lon, release.lat, release_time, 0.0)
    current_masked_at_release = bool(math.isnan(release_u) or math.isnan(release_v))

    sim = particle_engine.simulate(
        release, release_time, current_fn=current_fn, wind_fn=wind_fn,
        params=params, seed=0,
    )

    from shapely.ops import unary_union

    steps = [t for t in (3, 6, 9, 12, 18, 24, 36, 48) if t <= req.horizon_hours] or [req.horizon_hours]
    dt_hours = params.time_step_minutes / 60.0
    n_steps = sim.lons.shape[0] - 1
    rows = []
    for t_hours in steps:
        step_idx = min(round(t_hours / dt_hours), n_steps)
        contour_levels = particle_engine.kernel_density_contours(
            sim.lons[step_idx], sim.lats[step_idx])
        for level, polygons in contour_levels.items():
            if not polygons:
                continue  # this density level was never reached at this timestep
            geom = polygons[0] if len(polygons) == 1 else unary_union(polygons)
            rows.append({"t_hours": float(t_hours), "probability": float(level),
                         "geometry": da._geojson(geom)})

    caveats = (cav.particle_engine_forcing(
                    current_source, forcing_is_placeholder=True, calibrated=calibrated_here)
               + cav.harbour_outlet(req.outlet_id)
               + cav.bathymetry_substitution())
    if release.caveat:
        caveats.append(Caveat(field="outlet_id", message=release.caveat,
                               severity="critical", source="05-abd.md"))
    if current_masked_at_release:
        caveats.append(Caveat(
            field="contours",
            message=(
                f"{req.outlet_id}'s release point falls on a cell the current grid "
                "masks as land (NaN u/v, treated as zero current per simulate()'s own "
                "documented nan_to_num rule). This run's transport is diffusion and "
                "settling only, not current-driven, until it drifts onto a resolved "
                "cell -- a real reason a plume can stay tight near the outlet even "
                "over a long horizon, not evidence that nothing is happening."
            ),
            severity="warning",
            source="tasks/nizar.md",
        ))

    detail = (f"custom_2d particle engine, {particle_count} particles, "
              f"{sim.times[-1] - sim.times[0]}, currents: {current_source}")
    return rows, detail, caveats


@app.post(f"{PREFIX}/plume/simulate", response_model=PlumeResult, tags=["model"])
def plume_simulate(req: PlumeRequest):
    """Real particle transport. Cached on the scenario, so a slider drag or an
    animation frame step does not re-run the simulation."""
    outlet = next((o for o in da.outlets() if o["outlet_id"] == req.outlet_id), None)
    if outlet is None:
        raise HTTPException(404, f"unknown outlet {req.outlet_id}")

    key = da.TTLCache.key("plume", req.event_id, req.outlet_id, req.horizon_hours,
                          req.n_particles, req.diffusion_m2_s, req.windage)
    cached = da.PLUME_CACHE.get(key)
    if cached is not None:
        return cached

    rows, detail, caveats = _real_contours(req, outlet)

    result = PlumeResult(
        run_id=f"plume_{req.event_id}_{req.outlet_id}_{req.horizon_hours}h",
        event_id=req.event_id,
        outlet_id=req.outlet_id,
        contours=[PlumeContour(**r) for r in rows],
        model_version=MODEL_VERSIONS["particle_engine"],
        is_stub=False,
        provenance=[Provenance(kind="derived", detail=detail)],
        caveats=caveats,
    )
    da.PLUME_CACHE.set(key, result)
    return result


@app.get(f"{PREFIX}/plume/map", tags=["model"],
         responses={200: {"content": {"image/png": {}}}})
def plume_map(
    event_id: str,
    outlet_id: str,
    horizon_hours: int = Query(24, ge=1, le=120),
    upto_hours: float | None = Query(
        None, description="Draw only contours at or before this time — one animation frame"),
    with_exposure: bool = Query(
        True, description="Colour reef zones by their exposure risk level"),
    clip_to_sea: bool = Query(
        True, description="False shows the unclipped output, which is how the stub's "
                          "circles-over-the-city fault becomes visible"),
):
    """The prediction as a picture: real satellite imagery, real plume, real reef.

    Answers "the model says a flood is coming — where does the mud go?" without
    generating anything. A diffusion model has never seen Aqaba: it would draw a
    confident wrong coastline with an invented plume, and because the result would look
    like satellite imagery it would read as an OBSERVATION. That is unusable here, where
    the validation story is "the satellite could not see the plume, so we said so".

    Every pixel has a provenance, listed in the footer burned into the image, so the
    picture stays self-describing if someone screenshots it into a slide.

    Returns image/png. The extent is fixed by the baked basemap, so successive
    `upto_hours` values register against each other as animation frames.
    """
    from fastapi.responses import Response

    from rendering import plume_map as renderer

    plume = plume_simulate(PlumeRequest(event_id=event_id, outlet_id=outlet_id,
                                        horizon_hours=horizon_hours))
    contours = [c.model_dump() for c in plume.contours]

    # Exposure is best-effort: a picture of where the plume goes is useful even when the
    # scoring cannot run, so a failure here downgrades the reef colouring rather than
    # failing the whole request.
    by_zone: dict[str, dict] = {}
    if with_exposure:
        try:
            run = exposure_calculate(ExposureRequest(
                event_id=event_id, outlet_id=outlet_id, horizon_hours=horizon_hours))
            by_zone = {r.reef_zone_id: {"risk_level": r.risk_level,
                                        "risk_score": r.risk_score}
                       for r in run.results}
        except HTTPException:
            by_zone = {}

    png = renderer.render(
        contours,
        event_id=event_id, outlet_id=outlet_id, horizon_hours=horizon_hours,
        exposure_by_zone=by_zone, upto_hours=upto_hours, clip_to_sea=clip_to_sea,
    )
    return Response(
        content=png, media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
            # Machine-readable provenance beside the burned-in footer, so a client can
            # label the image without parsing pixels.
            "X-ReefShield-Plume-Source": "stub" if plume.is_stub else "particle-engine",
            "X-ReefShield-Basemap": ("esri-worldimagery-baked"
                                     if renderer.load_basemap() else "absent"),
            "X-ReefShield-Generated-Imagery": "none",
        },
    )


@app.get(f"{PREFIX}/plume/map/frames", tags=["model"])
def plume_map_frames(event_id: str, outlet_id: str,
                     horizon_hours: int = Query(24, ge=1, le=120)):
    """The timesteps available to animate, and the URL for each frame.

    Returned rather than assumed so the client never guesses a `upto_hours` the
    simulation did not produce.
    """
    from rendering import plume_map as renderer

    plume = plume_simulate(PlumeRequest(event_id=event_id, outlet_id=outlet_id,
                                        horizon_hours=horizon_hours))
    times = renderer.frame_times(c.model_dump() for c in plume.contours)
    base = (f"{PREFIX}/plume/map?event_id={event_id}&outlet_id={outlet_id}"
            f"&horizon_hours={horizon_hours}")
    return {
        "event_id": event_id,
        "outlet_id": outlet_id,
        "frame_count": len(times),
        "frames": [{"t_hours": t, "url": f"{base}&upto_hours={t:g}"} for t in times],
        "basemap_present": renderer.load_basemap() is not None,
        "plume_source": "stub" if plume.is_stub else "particle-engine",
    }


# -------------------------------------------------------------------- exposure

@app.post(f"{PREFIX}/exposure/calculate", response_model=ExposureRun, tags=["exposure"])
def exposure_calculate(req: ExposureRequest):
    """Component D. Real formula, real EPSG:32636 geometry, real formula_terms.

    The plume input is the real particle engine (see `_real_contours`) — the
    exposure formula itself was written before that landed and never needed a
    change; swapping the contour source did not touch a line of it.
    """
    outlet = next((o for o in da.outlets() if o["outlet_id"] == req.outlet_id), None)
    if outlet is None:
        raise HTTPException(404, f"unknown outlet {req.outlet_id}")

    zones_gdf = da.reef_zones_gdf()
    if zones_gdf is None or zones_gdf.empty:
        raise HTTPException(503, "no reef zone artifact present")
    if req.reef_zone_ids:
        zones_gdf = zones_gdf[zones_gdf["reef_zone_id"].isin(req.reef_zone_ids)]
        if zones_gdf.empty:
            raise HTTPException(404, f"no such reef zones: {req.reef_zone_ids}")

    key = da.TTLCache.key("exposure", req.event_id, req.outlet_id, req.horizon_hours,
                          tuple(sorted(req.reef_zone_ids or [])), req.catchment_id,
                          req.rainfall_multiplier, req.transmission_loss_override)
    cached = da.EXPOSURE_CACHE.get(key)
    if cached is not None:
        return cached

    # Sediment intensity, from the REAL feature row for this event and catchment.
    #
    # This asked the model for a synthetic `30 mm/3h` and nothing else, and the result
    # was always 0.0 — so every reef zone read `minimal` no matter what the plume did,
    # because exposure is a product of five terms. The model needs 20 features, and the
    # sediment magnitude is a curve-number depth driven by `precipitation_mm_day`; with
    # that column absent the depth is 0, the index is 0, and the whole product collapses.
    # A synthetic request is right for shaping a response and wrong for computing one.
    #
    # Falls back to the previous behaviour when the event is not in the training set,
    # and SAYS which happened in formula_terms — a stored run whose sediment term came
    # from a placeholder must be distinguishable later from one that did not.
    cid = req.catchment_id or outlet.get("catchment_id")
    intensity, intensity_source = 0.5, "default 0.5 (no catchment supplied)"
    # Per-request model_versions: MODEL_VERSIONS is the static fallback, but when
    # a real trained artifact actually produced the intensity number — whether via
    # the training-row path below or the runoff_predict() fallback — that real
    # model_version_id must be what gets persisted, not the stub string. A stored
    # run whose formula_terms claims "runoff_model: stub-0.1" while a real model
    # produced the intensity number is exactly the silent stub DoD item 3 forbids.
    run_model_versions = dict(MODEL_VERSIONS)
    if cid:
        row = da.training_row(req.event_id, cid)
        if row is not None:
            try:
                from models.runoff_model import predict_one

                real = predict_one(
                    _apply_rainfall_multiplier(row, req.rainfall_multiplier),
                    transmission_loss_override=req.transmission_loss_override)
                if real.get("model_version_id"):
                    run_model_versions["runoff_model"] = real["model_version_id"]
                index = real.get("sediment_index")
                anchor_index = real.get("anchor_index_for_normalisation")
                if index is not None and anchor_index:
                    intensity, intensity_source = _squash_sediment_index(
                        index, anchor_index, real.get("sediment_class"))
                if req.rainfall_multiplier != 1.0:
                    intensity_source += (
                        f" [rainfall_multiplier={req.rainfall_multiplier}x applied to "
                        "raw rainfall depth only; percentile-rank features reflect "
                        "the original storm, not the scaled one]")
            except (FileNotFoundError, ImportError, ModuleNotFoundError, KeyError) as exc:
                intensity_source = (
                    f"default 0.5 — real model unavailable ({type(exc).__name__})")
        else:
            pred = runoff_predict(RunoffRequest(
                catchment_id=cid, rainfall_mm_3h=30.0, event_id=req.event_id,
                rainfall_multiplier=req.rainfall_multiplier,
                transmission_loss_override=req.transmission_loss_override))
            intensity = pred.relative_sediment_intensity
            if pred.is_stub:
                intensity_source = (
                    f"PLACEHOLDER: {req.event_id} has no feature row, so this is the "
                    f"stub at 30 mm/3h for {cid}, not a measurement")
            else:
                intensity_source = (
                    f"PLACEHOLDER fallback: {req.event_id} has no feature row for the "
                    f"sediment anchor, but runoff model {pred.model_version} at "
                    f"30 mm/3h for {cid} was used for intensity")
                run_model_versions["runoff_model"] = pred.model_version

    # Confidence: real per-catchment GEFS ensemble agreement (Nizar's forecast
    # pipeline, via Karam's own p99 climatology as the exceedance threshold) times
    # a fixed qualitative penalty for the currents/bathymetry substitutions that
    # apply regardless of forecast skill.
    #
    # agreement = 1 at a unanimous ensemble (all 30 members on the same side of the
    # threshold -- most trustworthy), 0 at an exact 50/50 split (least trustworthy).
    #
    # Confirmed by Nizar, 7 Aug: this is the right shape for "confidence" here. Live-
    # verified against AQ-C05 (0/30 members exceeding -> agreement 1.00 -> 0.8, capped
    # correctly by the currents/bathymetry penalty regardless of the unanimous
    # ensemble). "Confidence" meaning ensemble agreement, not e.g. model skill or
    # historical accuracy, is the correct reading for what this term qualifies: how
    # much the plume-direction and reef-exposure numbers should be trusted given
    # known forcing limitations, which ensemble spread on the RAINFALL side does not
    # actually speak to on its own -- but it is the best proxy this repo has without
    # a second, independent skill metric, and it is honestly labelled as such via
    # confidence_adjustment_reason. No functional change from the formula below.
    exceedance = da.gefs_exceedance_for(cid) if cid else None
    if exceedance is not None:
        agreement = abs(exceedance["exceedance_prob"] - 0.5) * 2.0
        confidence_adjustment = agreement * 0.8  # 0.8: currents/bathymetry penalty
        confidence_adjustment_reason = (
            f"{exceedance['members_exceeding']}/{exceedance['members_total']} GEFS "
            f"members exceed the {exceedance['threshold_mm']:.2f} mm/24h threshold "
            f"({exceedance['threshold_source']}) -> agreement {agreement:.2f}, "
            "x0.8 for coarse global current model + GMRT-substituted bathymetry"
        )
    else:
        confidence_adjustment = 0.6
        confidence_adjustment_reason = (
            "PLACEHOLDER 0.6 -- no GEFS exceedance row for "
            f"{cid or 'this catchment'} in the cached forecast snapshot"
        )
    confidence = engine.confidence_label(confidence_adjustment)

    # Goes through plume_simulate() (and its cache), not a private call of its own
    # -- the picture in /plume/map and the score here must come from the SAME
    # particle cloud, not two independently-simulated ones that happen to agree.
    plume = plume_simulate(PlumeRequest(event_id=req.event_id, outlet_id=req.outlet_id,
                                        horizon_hours=req.horizon_hours))
    import geopandas as gpd
    from shapely.geometry import shape as _shape

    contours = gpd.GeoDataFrame(
        {"t_hours": [c.t_hours for c in plume.contours],
         "probability": [c.probability for c in plume.contours]},
        geometry=[_shape(c.geometry) for c in plume.contours],
        crs="EPSG:4326",
    )
    overlay = engine.intersect_plume_with_zones(contours, zones_gdf)

    # Keep the provisional flag rather than discarding it with [0]: it selects which
    # geometry caveat is TRUE, and a caveat nobody re-reads after a data swap is how
    # the obsolete 250 m width claim survived here after /reef-zones had dropped it.
    meta_zones, zones_are_provisional = da.reef_zones(include_geometry=False)
    zone_meta = {z["reef_zone_id"]: z for z in meta_zones}

    results: list[ExposureResult] = []
    for zid in sorted(zones_gdf["reef_zone_id"].unique()):
        summary = engine.summarise_zone(
            zid, overlay,
            relative_sediment_intensity=intensity,
            confidence_adjustment=confidence_adjustment,
            horizon_hours=float(req.horizon_hours),
            sensitivity_weight=engine.HABITAT_SENSITIVITY_PLACEHOLDER,
        )
        if summary is None:
            continue  # not reached is reported as not reached, never as zero risk

        summary["formula_terms"].update({
            "relative_sediment_intensity_source": intensity_source,
            "confidence_adjustment_reason": confidence_adjustment_reason,
            # Components, not just the composed sentence -- a sentence can't be
            # translated cleanly, components can (docs/OPEN-ISSUES.md #4).
            "confidence_members_exceeding": exceedance["members_exceeding"] if exceedance else None,
            "confidence_members_total": exceedance["members_total"] if exceedance else None,
            "confidence_threshold_value_mm": exceedance["threshold_mm"] if exceedance else None,
            "plume_source": "SYNTHETIC_STUB" if plume.is_stub else "REAL_PARTICLE_ENGINE",
            "model_versions": run_model_versions,
        })
        # Per-result caveats are ZONE-scoped. Anything that qualifies the whole run
        # — the outlet's harbour warning, the risk-band note — is attached once at
        # run level instead of repeated on every zone. Ali's UI would otherwise
        # render the same critical warning N times on one panel, which trains a
        # reader to skim past exactly the text that matters most.
        #
        # The plume's own caveats (real-engine forcing limitations, or
        # stub_model() if it ever falls back) travel with it rather than being
        # rebuilt here, so this can never drift from what /plume/map is
        # actually showing for the same run.
        zone_caveats = [
            c for c in cav.build_exposure_caveats(
                req.outlet_id, zone_meta.get(zid), provisional=zones_are_provisional)
            if c.field not in ("outlet_id", "risk_level")
        ] + [c for c in plume.caveats if c.field not in ("outlet_id",)]

        results.append(ExposureResult(
            **summary,
            confidence=confidence,
            caveats=zone_caveats,
        ))

    run_caveats = (cav.harbour_outlet(req.outlet_id) + cav.risk_band_thresholds()
                   + cav.reef_area_correction() + cav.reef_scope_is_jordan())

    # An empty result list is a real finding, not a failure — but it must say so.
    # Returning a bare [] looks identical to a broken query, and a reviewer would
    # reasonably assume the engine fell over.
    if not results:
        import geopandas as gpd
        from shapely.geometry import Point

        pt = gpd.GeoSeries([Point(outlet["lon"], outlet["lat"])], crs="EPSG:4326").to_crs(
            engine.CRS_MEASURE
        ).iloc[0]
        zutm = zones_gdf.to_crs(engine.CRS_MEASURE)
        d = zutm.geometry.distance(pt)
        nearest_id = zutm.loc[d.idxmin(), "reef_zone_id"]
        # Equal-area equivalent radius rather than exterior.length/(2*pi): the
        # real engine's contours can be MultiPolygon (disjoint KDE lobes), which
        # has no single .exterior the circle-only formula assumed.
        contours_utm = contours.to_crs(engine.CRS_MEASURE) if not contours.empty else contours
        reach_m = (max(math.sqrt(c.area / math.pi) for c in contours_utm.geometry)
                   if not contours_utm.empty else 0.0)

        run_caveats.append(Caveat(
            field="results",
            message=(
                f"No reef zone is reached from {req.outlet_id} within "
                f"{req.horizon_hours} h. The nearest zone is {nearest_id} at "
                f"{d.min():.0f} m, and the plume's largest modelled extent is "
                f"{reach_m:.0f} m. This is reported as no exposure, NOT as zero-risk "
                "exposure — a zone that was not reached is a different statement from "
                "a zone that was reached with negligible effect."
            ),
            severity="info",
            source="backend/src/exposure/engine.py",
        ))

    run_id = store.new_run_id()
    store.save_run(
        run_id=run_id,
        event_id=req.event_id,
        outlet_id=req.outlet_id,
        results=[r.model_dump() for r in results],
        model_versions=run_model_versions,
        caveats=[c.model_dump() for c in run_caveats],
    )

    run = ExposureRun(
        run_id=run_id,
        event_id=req.event_id,
        outlet_id=req.outlet_id,
        created_at=datetime.now(timezone.utc),
        results=results,
        model_versions=run_model_versions,
        caveats=run_caveats,
    )
    da.EXPOSURE_CACHE.set(key, run)
    return run


@app.get(f"{PREFIX}/exposure/runs/{{run_id}}", tags=["exposure"])
def get_exposure_run(run_id: str):
    """Reconstruct a stored run, formula_terms included. The audit path."""
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"unknown run {run_id}")
    return run


# ------------------------------------------------------------------- backtests

@app.post(f"{PREFIX}/backtests/run", response_model=BacktestResult, tags=["exposure"])
def backtest_run(req: BacktestRequest):
    """Honest refusal: there is no observed plume mask to score against.

    The Sentinel-2 search found nothing for October 2016, for a documented physical
    reason — the in-situ mooring shows the signal lasted ~31 hours and both usable
    satellite passes were 2.5-3.5 days later. Returning `not_possible` with that
    explanation is the correct answer; returning a fabricated skill score is not.
    """
    return BacktestResult(
        run_id=f"bt_{req.event_id}",
        event_id=req.event_id,
        status="not_possible",
        metrics=None,
        baseline_metrics=None,
        note=(
            "No satellite-observed plume mask exists for this event. Two independent "
            "cloud-free sensors (Sentinel-2 2016-11-02, Landsat 8 2016-11-01) show no "
            "sediment signal, and the Kalman et al. (2025) mooring 250 m off the "
            "discharge point shows the turbidity signal had returned to background by "
            "17:15 local on 29 October — 2.5-3.5 days before either pass. Scoring "
            "against an absent observation would fabricate a metric."
        ),
        caveats=[Caveat(
            field="metrics",
            message=(
                "Backtest metrics are unavailable by physical necessity, not by "
                "omission. See docs/pitch_limitations.md §9."
            ),
            severity="info",
            source="docs/pitch_limitations.md §9",
        )],
    )


@app.get(f"{PREFIX}/backtests/{{run_id}}", response_model=BacktestResult,
         tags=["exposure"])
def get_backtest(run_id: str):
    return backtest_run(BacktestRequest(event_id=run_id.removeprefix("bt_")))


# -------------------------------------------------------------------- alerts

@app.get(f"{PREFIX}/alerts", response_model=list[AlertOut], tags=["exposure"])
def list_alerts(
    min_level: str = Query("moderate"),
    event_id: str | None = Query(None, description="Scope to one event"),
    outlet_id: str | None = Query(None, description="Scope to one outlet"),
):
    """Alerts derived from a stored exposure run, never recomputed here.

    Scoped by event/outlet when supplied. Without a scope this takes the newest run
    overall, which is NOT necessarily the scenario the caller last requested — a
    cached exposure response does not write a new run. Each alert therefore carries
    `source_run_id` so what is on screen can always be traced to the exact
    formula_terms that produced it.
    """
    order = [b[2] for b in engine.RISK_BANDS]
    try:
        floor = order.index(min_level)
    except ValueError:
        raise HTTPException(400, f"min_level must be one of {order}")

    results, source_run_id = store.latest_results(event_id=event_id, outlet_id=outlet_id)
    if not results:
        return []
    zone_meta = {z["reef_zone_id"]: z for z in da.reef_zones(include_geometry=False)[0]}

    out = []
    for r in results:
        if order.index(r["risk_level"]) < floor:
            continue
        zid = r["reef_zone_id"]
        name = (zone_meta.get(zid) or {}).get("zone_name") or zid
        window = r.get("arrival_window_hours")
        win_en = f" in {window[0]:.0f}–{window[1]:.0f} h" if window else ""
        win_ar = f" خلال {window[0]:.0f}–{window[1]:.0f} ساعة" if window else ""
        out.append(AlertOut(
            alert_id=f"alert_{source_run_id}_{zid}",
            source_run_id=source_run_id,
            reef_zone_id=zid,
            risk_level=r["risk_level"],
            risk_score=r["risk_score"],
            issued_at=datetime.now(timezone.utc),
            arrival_window_hours=window,
            headline_en=f"{name}: {r['risk_level']} sediment exposure risk{win_en}",
            headline_ar=f"{name}: خطر تعرّض للرواسب {r['risk_level']}{win_ar}",
            caveats=cav.risk_band_thresholds() + cav.sensitivity_placeholder(
                (zone_meta.get(zid) or {}).get("sensitivity_weight_status", "")
            ),
        ))
    # Highest risk first — Phase 4. Never sorted before; a client building a
    # priority list (feature A) or a coastal comparison (feature I) off this
    # endpoint got whatever order store.latest_results() happened to produce.
    out.sort(key=lambda a: a.risk_score, reverse=True)
    return out


# ------------------------------------------------------------- explain and ask

@app.post(f"{PREFIX}/explain", response_model=ExplainResponse, tags=["language"])
def explain(req: ExplainRequest):
    """Phrases numbers it is handed. Computes none, rounds none, invents none."""
    if not any(c["catchment_id"] == req.catchment_id for c in da.catchments()):
        raise HTTPException(404, f"unknown catchment {req.catchment_id}")

    level = "high"
    if req.plume_probability is not None:
        level = engine.risk_level(min(100.0, req.plume_probability * 100))

    text, source_numbers = rag_explain.build_explanation(
        catchment_id=req.catchment_id,
        risk_level=level,
        language=req.language,
        shap_drivers=req.shap_drivers,
        plume_probability=req.plume_probability,
        arrival_window_hours=req.arrival_window_hours,
        confidence=req.confidence,
        reef_zone_id=req.reef_zone_id,
        rainfall_percentile=req.rainfall_percentile,
        catchment_label=da.catchment_label(req.catchment_id, req.language),
    )

    # Self-check on the way out. If the template ever drops or alters a number this
    # fires here, in the response path, not in a test somebody skipped.
    missing = rag_explain.numbers_present(text, source_numbers)
    if missing:
        raise HTTPException(
            500, f"number fidelity failure — not verbatim in output: {missing}"
        )

    return ExplainResponse(
        text=text,
        language=req.language,
        source_numbers=source_numbers,
        generator="deterministic_template",
        caveats=[Caveat(
            field="text",
            message=(
                "This paragraph is generated from a fixed template. Numbers are "
                "interpolated exactly as supplied and are never recomputed or rounded "
                "by the phrasing layer."
            ),
            severity="info",
            source="backend/src/rag/explain.py",
        )],
    )


@app.post(f"{PREFIX}/ask", response_model=AskResponse, tags=["language"])
def ask(req: AskRequest):
    """RAG over the technical corpus. An uncited answer is not shippable."""
    chunks = rag_index.retrieve(req.question, k=req.k)
    text, citations = rag_answer.generate_cited_answer(
        req.question, chunks, language=req.language
    )
    n_files = rag_corpus.summary()["n_files_present"]

    if not chunks:
        return AskResponse(answer=text, citations=[], language=req.language,
                           corpus_files_searched=n_files)

    # Hard guarantee, in the request path: an answer built from retrieved chunks
    # must carry citations. This assertion should never fire.
    assert citations, "an uncited answer is not shippable"

    return AskResponse(answer=text, citations=citations, language=req.language,
                       corpus_files_searched=n_files)


@app.get(f"{PREFIX}/ask/corpus", tags=["language"])
def ask_corpus():
    """What /ask can actually see. Makes the docs/ali exclusion inspectable."""
    return {**rag_corpus.summary(), **rag_index.index_stats()}


@app.get(f"{PREFIX}/cache-stats", tags=["meta"])
def cache_stats():
    return {"plume": da.PLUME_CACHE.stats(), "exposure": da.EXPOSURE_CACHE.stats()}
