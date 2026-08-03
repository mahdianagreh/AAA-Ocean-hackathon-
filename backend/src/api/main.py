"""ReefShield Aqaba — API.

Deliberately thin. Pulga owns the real backend (Phase 2 workstream 4); this
exists so `docker compose up` produces something that answers on day one,
and so the model layer has a real serving surface to be wired into rather
than a hypothetical one.

Every endpoint that cannot answer honestly returns 503 with the reason,
never a placeholder number. A fabricated prediction in a warning system is
worse than an error, because it looks like it works.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(os.environ.get("REEFSHIELD_ROOT", "/app"))
CATCHMENTS = ROOT / "data/processed/vectors/catchments.gpkg"
TERRAIN = ROOT / "data/processed/features/catchment_terrain.parquet"
# Model artifacts are not a single known filename. Versions are minted per
# training run and recorded in data/models/model_versions.jsonl; the model
# layer resolves the latest one. The API does not know the layout on purpose -
# see backend/src/models/artifacts.py.

app = FastAPI(
    title="ReefShield Aqaba",
    version="0.1.0",
    description="Wadi-to-reef sediment impact forecasting. Phase 2 skeleton.",
)

# The frontend is a separate origin in development (5173 -> 8000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get(
        "REEFSHIELD_CORS_ORIGINS", "http://localhost:5173").split(",") if o],
    allow_methods=["*"],
    allow_headers=["*"],
)


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
            text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return os.environ.get("GIT_SHA", "unknown")


# ── the geometry contract, settled 2 Aug ────────────────────────────────
OUTLETS_GEOJSON = ROOT / "data/processed/vectors/outlets.geojson"


def _outlets_from_disk() -> list[dict] | None:
    """Read the outlets, caveats included, from the file that owns them.

    scripts/12_culvert_crosscheck.py writes both the GeoPackage and this
    GeoJSON. Reading it here means the AQ-O04 harbour warning has exactly one
    source: an earlier version of this module carried its own copy of that
    text, which is precisely how a safety caveat drifts out of sync with the
    data it describes.

    Plain json rather than geopandas - the serving image has no geospatial
    stack, and five point features do not justify adding one.
    """
    if not OUTLETS_GEOJSON.exists():
        return None
    try:
        import json
        with OUTLETS_GEOJSON.open() as fh:
            fc = json.load(fh)
        out = []
        for feat in fc.get("features", []):
            p = dict(feat.get("properties") or {})
            lon, lat = feat["geometry"]["coordinates"][:2]
            p["lon"], p["lat"] = round(lon, 5), round(lat, 5)
            out.append(p)
        return out or None
    except Exception:
        # A malformed file must not take the API down; fall through to the
        # embedded contract values, which are the same numbers.
        return None


# Fallback only, for when the data volume is not mounted. These mirror
# tasks/00-contracts.md §2; the file on disk is authoritative.
GEOMETRY = [
    {"catchment_id": "AQ-C01", "name": "Wadi Yutum", "area_km2": 4453.08,
     "outlet_id": "AQ-O01", "lon": 34.97073, "lat": 29.54560,
     "position_confidence": "plausible",
     "caveat": "Engineered Wadi Yutum flood channel; mouth verified at the "
               "shoreline. Area carries ±4% from separating endorheic basins "
               "from DEM artifacts."},
    {"catchment_id": "AQ-C02", "name": None, "area_km2": 64.85,
     "outlet_id": "AQ-O02", "lon": 34.97643, "lat": 29.47270,
     "position_confidence": "low",
     "caveat": "Routed channel crosses the container terminal and reclaimed "
               "land; mouth position uncertain to several hundred metres."},
    {"catchment_id": "AQ-C03", "name": None, "area_km2": 59.90,
     "outlet_id": "AQ-O03", "lon": 34.96416, "lat": 29.38167,
     "position_confidence": "low",
     "caveat": "Routed channel follows a road corridor between tank farms and "
               "lands on a jetty; mouth position uncertain."},
    {"catchment_id": "AQ-C04", "name": None, "area_km2": 42.67,
     "outlet_id": "AQ-O04", "lon": 34.96622, "lat": 29.36052,
     "position_confidence": "low",
     "caveat": "Discharges into an enclosed harbour basin; sediment released "
               "here settles in the basin rather than dispersing into the "
               "Gulf. A plume simulation from this coordinate will be "
               "confidently wrong."},
    {"catchment_id": "AQ-C05", "name": None, "area_km2": 35.64,
     "outlet_id": "AQ-O05", "lon": 34.95998, "lat": 29.35737,
     "position_confidence": "good",
     "caveat": "Natural braided wadi bed, mouth at the shore, reef offshore."},
]


class Health(BaseModel):
    status: str
    version: str
    commit: str
    time_utc: str
    model_available: bool
    data_volume_mounted: bool


@app.get("/health", response_model=Health, tags=["ops"])
def health() -> Health:
    """Liveness plus what this instance can actually do.

    The healthcheck in the Dockerfile hits this, so it must stay cheap and
    must not depend on Supabase - a network blip should not restart the API.
    It must also survive the model layer being unimportable, which is why the
    registry lookup is guarded rather than allowed to 500 the whole endpoint.
    """
    try:
        from models import artifacts
        model_available = artifacts.latest_version() is not None
    except Exception:
        model_available = False

    return Health(
        status="ok",
        version=app.version,
        commit=git_sha(),
        time_utc=datetime.now(timezone.utc).isoformat(),
        model_available=model_available,
        data_volume_mounted=CATCHMENTS.exists(),
    )


@app.get("/api/v1/catchments", tags=["geometry"])
def catchments():
    """The five catchments and their outlets, with the caveats attached.

    `caveat` travels in the response on purpose. The AQ-O04 harbour warning
    living only in a report is how it gets forgotten.
    """
    return {"count": len(GEOMETRY), "catchments": GEOMETRY,
            "source": "Copernicus GLO-30 30 m, D8 routing, endorheic basins excluded",
            "contract": "tasks/00-contracts.md §2"}


@app.get("/api/v1/outlets", tags=["geometry"])
def outlets():
    """Release points, with every caveat attached.

    `caveat` travels in the response on purpose: the AQ-O04 harbour warning
    living only in a report is how a plume gets released into an enclosed
    basin and nobody notices.
    """
    disk = _outlets_from_disk()
    rows = disk or GEOMETRY
    keys = ("outlet_id", "catchment_id", "lon", "lat", "position_confidence",
            "caveat", "culvert_verdict", "unmodelled_coastal_culverts",
            "nearest_culvert_m", "upstream_km2")
    verified = [r for r in rows if r.get("position_confidence") != "low"]
    return {
        "count": len(rows),
        "verified_against_imagery": len(verified),
        "share_of_discharge_verified": 0.964,
        "source": "data/processed/vectors/outlets.geojson" if disk
                  else "embedded contract values — data volume not mounted",
        "outlets": [{k: r[k] for k in keys if k in r} for r in rows],
    }


class PredictRequest(BaseModel):
    catchment_id: str = Field(..., pattern=r"^AQ-C\d{2}$")
    rain_3h_mm: float = Field(..., ge=0)
    rain_24h_mm: float | None = Field(None, ge=0)
    soil_moisture_t24h: float | None = Field(None, ge=0, le=1)


@app.post("/api/v1/runoff/predict", tags=["model"])
def predict(req: PredictRequest):
    """Runoff probability for one catchment.

    503 until a trained artifact exists. The model layer is built and
    validated, but the feature matrix has not been delivered — every rainfall
    granule is being re-pulled against the corrected AOI. Returning a number
    here before that would be a fabrication with a confidence attached.
    """
    # Imported here, not at module scope: it pulls xgboost and shap, and the
    # API should still boot and answer /health when the model layer cannot.
    from models.runoff_model import predict_one

    try:
        return predict_one(req.model_dump(exclude_none=True))
    except FileNotFoundError as exc:
        # No registered model. The reason is the exception's own message, which
        # names the ledger and the command that fixes it - repeating it here
        # would be a second copy to drift.
        raise HTTPException(
            status_code=503,
            detail={
                "error": "no trained model registered",
                "why": str(exc),
                "blocked_on": "data/processed/features/event_catchment_features.parquet",
                "harness_status": "built and validated - backend/src/models, "
                                  "tests/test_runoff_model.py",
            },
        ) from exc
    except KeyError as exc:                       # unknown version id requested
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/models", tags=["model"])
def models():
    """What is being served, and whether it is real.

    Exists so the dashboard can show provenance rather than asserting a number
    is trustworthy. Returns 503 rather than an empty object when nothing is
    registered, so a caller cannot mistake absence for a healthy default.
    """
    from models.runoff_model import available_versions, model_info

    try:
        info = model_info()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail={"error": "no trained model registered", "why": str(exc)},
        ) from exc
    return {"serving": info, "versions": [v["id"] for v in available_versions()]}
