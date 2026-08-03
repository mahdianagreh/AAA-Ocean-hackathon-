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

import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ..exposure import engine, store
from ..rag import answer as rag_answer
from ..rag import corpus as rag_corpus
from ..rag import explain as rag_explain
from ..rag import index as rag_index
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
    EventOut,
    ExplainRequest,
    ExplainResponse,
    ExposureRequest,
    ExposureResult,
    ExposureRun,
    HealthOut,
    OutletOut,
    PlumeContour,
    PlumeRequest,
    PlumeResult,
    Provenance,
    ReefZoneOut,
    RunoffPrediction,
    RunoffRequest,
)

API_VERSION = "0.2.0"
PREFIX = "/api/v1"

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
    "particle_engine": "stub-0.1",
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get(
        "REEFSHIELD_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",") if o],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------- ops liveness (Docker)

ROOT = Path(os.environ.get("REEFSHIELD_ROOT", Path(__file__).resolve().parents[3]))


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
        from ..models import artifacts
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
        from ..models.runoff_model import available_versions, model_info
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
    out = []
    for o in da.outlets():
        harbour = cav.harbour_outlet(o["outlet_id"])
        out.append(OutletOut(**o, caveat=harbour[0].message if harbour else None))
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
            caveats += cav.reef_area_correction() + cav.reef_scope_is_jordan()
            caveats += cav.reef_depth_disagreement()
        out.append(ReefZoneOut(
            **{k: v for k, v in z.items() if k != "geometry"},
            geometry=z.get("geometry") if include_geometry else None,
            caveats=caveats,
        ))
    return out


# ---------------------------------------------------------------------- events

@app.get(f"{PREFIX}/events", response_model=list[EventOut], tags=["events"])
def list_events():
    evs = da.events()
    if not evs:
        raise HTTPException(503, "docs/event_dates.md is not present")
    return [EventOut(**e) for e in evs]


@app.get(f"{PREFIX}/events/{{event_id}}", response_model=EventOut, tags=["events"])
def get_event(event_id: str):
    for e in da.events():
        if e["event_id"] == event_id:
            return EventOut(**e)
    raise HTTPException(404, f"unknown event {event_id}")


# ---------------------------------------------------------------------- runoff

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

    try:
        from ..models.runoff_model import predict_one

        real = predict_one(req.model_dump(exclude_none=True))
    except (FileNotFoundError, ImportError, ModuleNotFoundError):
        real = None            # nothing registered yet — fall through to the stub
    except KeyError as exc:    # unknown version id explicitly requested
        raise HTTPException(404, str(exc)) from exc

    if real is not None:
        # Trust the model's own numbers; do not re-derive or rescale them here.
        return RunoffPrediction(
            catchment_id=req.catchment_id,
            predicted_runoff_m3=float(real.get("predicted_runoff_m3", 0.0)),
            relative_sediment_intensity=float(
                real.get("relative_sediment_intensity",
                         real.get("runoff_probability", 0.0))),
            sediment_class=real.get("sediment_class", "moderate"),
            model_version=str(real.get("model_version", "runoff-real")),
            is_stub=False,
            provenance=[Provenance(kind="derived",
                                   detail=f"Mahdi's runoff model {real.get('model_version')}")],
            caveats=cav.landcover_epoch() + cav.soil_is_modelled(),
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
           else "moderate" if intensity > 0.25 else "low")

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

def _synthetic_contours(outlet_lon: float, outlet_lat: float, horizon: int):
    """Concentric growing contours around the outlet, for the exposure engine.

    NOT a plume model. It is the synthetic input the exposure engine is developed
    and tested against before the real particle engine lands, and it is labelled as
    such in every response that uses it. Buffers are built in UTM 36N so the radii
    are true metres.
    """
    import geopandas as gpd
    from shapely.geometry import Point

    pt = gpd.GeoSeries([Point(outlet_lon, outlet_lat)], crs="EPSG:4326").to_crs(
        engine.CRS_MEASURE
    ).iloc[0]

    steps = [t for t in (3, 6, 9, 12, 18, 24, 36, 48) if t <= horizon] or [horizon]
    rows = []
    for t in steps:
        radius_m = 600 * math.sqrt(t)          # diffusive spread ~ sqrt(time)
        probability = max(0.05, min(0.95, 0.9 * math.exp(-t / 30)))
        rows.append({"t_hours": float(t), "probability": probability,
                     "geometry": pt.buffer(radius_m)})
    return gpd.GeoDataFrame(rows, crs=engine.CRS_MEASURE)


@app.post(f"{PREFIX}/plume/simulate", response_model=PlumeResult, tags=["model"])
def plume_simulate(req: PlumeRequest):
    """STUB contours. Cached on the scenario, so a slider drag does not re-run it."""
    outlet = next((o for o in da.outlets() if o["outlet_id"] == req.outlet_id), None)
    if outlet is None:
        raise HTTPException(404, f"unknown outlet {req.outlet_id}")

    key = da.TTLCache.key("plume", req.event_id, req.outlet_id, req.horizon_hours,
                          req.n_particles, req.diffusion_m2_s, req.windage)
    cached = da.PLUME_CACHE.get(key)
    if cached is not None:
        return cached

    gdf = _synthetic_contours(outlet["lon"], outlet["lat"], req.horizon_hours)
    wgs = gdf.to_crs("EPSG:4326")

    result = PlumeResult(
        run_id=f"plume_{req.event_id}_{req.outlet_id}_{req.horizon_hours}h",
        event_id=req.event_id,
        outlet_id=req.outlet_id,
        contours=[
            PlumeContour(t_hours=r["t_hours"], probability=r["probability"],
                         geometry=da._geojson(r.geometry))
            for _, r in wgs.iterrows()
        ],
        model_version=MODEL_VERSIONS["particle_engine"],
        is_stub=True,
        provenance=[Provenance(
            kind="stub",
            detail="Synthetic sqrt(t) buffers in UTM 36N; not a transport simulation",
        )],
        caveats=(cav.stub_model("The particle engine")
                 + cav.harbour_outlet(req.outlet_id)
                 + cav.bathymetry_substitution()),
    )
    da.PLUME_CACHE.set(key, result)
    return result


# -------------------------------------------------------------------- exposure

@app.post(f"{PREFIX}/exposure/calculate", response_model=ExposureRun, tags=["exposure"])
def exposure_calculate(req: ExposureRequest):
    """Component D. Real formula, real EPSG:32636 geometry, real formula_terms.

    The plume input is currently the synthetic stub, and every response says so.
    The engine itself is not a stub — swapping the contour source does not change
    a line of it.
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
                          tuple(sorted(req.reef_zone_ids or [])), req.catchment_id)
    cached = da.EXPOSURE_CACHE.get(key)
    if cached is not None:
        return cached

    # Sediment intensity: from the runoff stub when a catchment is named, else the
    # outlet's own catchment. Reported in formula_terms either way.
    cid = req.catchment_id or outlet.get("catchment_id")
    intensity, intensity_source = 0.5, "default 0.5 (no catchment supplied)"
    if cid:
        pred = runoff_predict(RunoffRequest(catchment_id=cid, rainfall_mm_3h=30.0,
                                            event_id=req.event_id))
        intensity = pred.relative_sediment_intensity
        intensity_source = f"runoff stub for {cid} at 30 mm/3h"

    # Confidence: coarse global currents and a substituted bathymetry product are
    # both real reasons not to claim high confidence.
    confidence_adjustment = 0.6
    confidence = engine.confidence_label(confidence_adjustment)

    contours = _synthetic_contours(outlet["lon"], outlet["lat"], req.horizon_hours)
    overlay = engine.intersect_plume_with_zones(contours, zones_gdf)

    zone_meta = {z["reef_zone_id"]: z for z in da.reef_zones(include_geometry=False)[0]}

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
            "confidence_adjustment_reason":
                "coarse global current model + GMRT-substituted bathymetry",
            "plume_source": "SYNTHETIC_STUB",
            "model_versions": MODEL_VERSIONS,
        })
        # Per-result caveats are ZONE-scoped. Anything that qualifies the whole run
        # — the outlet's harbour warning, the risk-band note — is attached once at
        # run level instead of repeated on every zone. Ali's UI would otherwise
        # render the same critical warning N times on one panel, which trains a
        # reader to skim past exactly the text that matters most.
        zone_caveats = [
            c for c in cav.build_exposure_caveats(req.outlet_id, zone_meta.get(zid))
            if c.field not in ("outlet_id", "risk_level")
        ] + cav.stub_model("The plume input to this exposure run")

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
        reach_m = max(c.exterior.length / (2 * math.pi) for c in contours.geometry)

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
        model_versions=MODEL_VERSIONS,
        caveats=[c.model_dump() for c in run_caveats],
    )

    run = ExposureRun(
        run_id=run_id,
        event_id=req.event_id,
        outlet_id=req.outlet_id,
        created_at=datetime.now(timezone.utc),
        results=results,
        model_versions=MODEL_VERSIONS,
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
