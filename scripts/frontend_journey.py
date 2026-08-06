#!/usr/bin/env python3
"""Derive the 3D Journey's plume + exposure fixture from the real, live API.

Feature 14 (tasks/phase4/00-phase4-plan.md, tasks/phase4/06-ali.md,
tasks/phase4/05-abd.md item 1's "what this closes"). The plume-cloud portion was
blocked until the real particle engine was wired in (0de8c26) -- it now is, so this
derives the one thing the 3D view needs that no other fixture script produces: the
real simulated plume, every reported timestep, for the one outlet with a cached
historical current archive (AQ-O02, AQ-2016-10-28).

WHY THE LIVE API, NOT A DIRECT MODEL CALL. scripts/frontend_predictions.py's own
docstring explains why its fixture calls backend.models functions directly instead of
the API: the API did not start in that environment (OPEN-ISSUES #21) and DoD item 9
needs the artefact committed regardless of whether a server is ever running. Here the
opposite trade applies. /api/v1/exposure/calculate's orchestration (sediment-intensity
fallback chain, confidence, formula_terms) lives in backend/src/api/main.py and is
substantial enough that reimplementing it by hand risks a silent divergence from what
the real endpoint actually returns -- exactly the "plausible, wrong output" failure
mode this project keeps naming. Calling the real, running endpoint guarantees the
fixture is byte-faithful to production behaviour. The output is still a committed,
offline-servable fixture afterward, same as every other frontend/public/fixtures/*
file -- only the derivation step needs a live process, not the shipped frontend.

    source .venv/bin/activate
    uvicorn api.main:app --host 127.0.0.1 --port 8001 --app-dir backend/src &
    python scripts/frontend_journey.py --api http://127.0.0.1:8001 \\
        --out frontend/public/fixtures
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
from config import spatial as _spatial  # noqa: E402

BASEMAP_DIR = ROOT / "frontend" / "public" / "basemap"
FIXTURES_DIR = ROOT / "frontend" / "public" / "fixtures"
#: 300 m in the real measurement CRS (EPSG:32636, per spatial.py's own contract),
#: not degrees -- a degree-based tolerance would mean a different real distance
#: depending on latitude, which this project's own CRS rule exists to prevent.
RUNOFF_SIMPLIFY_M = 300.0

EVENT_ID = "AQ-2016-10-28"
#: The one outlet with a cached historical HYCOM archive for this event (05-abd.md
#: item 1) -- the same outlet the model card and the HANDOFF doc use as evidence,
#: including its honestly-disclosed current-grid-masking caveat (see both docs).
OUTLET_ID = "AQ-O02"
HORIZON_HOURS = 24


def _post(base: str, path: str, body: dict) -> dict:
    req = Request(
        f"{base}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except URLError as exc:
        raise SystemExit(
            f"Could not reach {base}{path} ({exc}). This script derives from the "
            "live API, not a hand-reimplementation of its orchestration -- start it "
            "first: uvicorn api.main:app --app-dir backend/src (see this file's own "
            "docstring)."
        ) from exc


def _get(base: str, path: str) -> list | dict:
    with urlopen(f"{base}{path}", timeout=30) as resp:
        return json.loads(resp.read())


def _real_rainfall(catchment_id: str) -> dict | None:
    """The real daily rainfall this catchment measured around the event —
    `frontend/public/fixtures/event.json`, itself derived by
    scripts/frontend_event_series.py from `catchment_rainfall_daily.parquet`.
    Reused here, not re-derived, so the 3D scene's "heavy rainfall" phase is
    driven by the same number the Hyetograph panel already shows, not a second
    value that could quietly drift from it.

    Only a daily series exists (see event.ts's own docstring: no sub-daily
    record is in this repo) — so this returns the day of measured peak
    intensity for the catchment, not an intra-day curve. The 3D scene's rain
    phase is honest about that: one real measured number, not an invented
    ramp.
    """
    event_path = FIXTURES_DIR / "event.json"
    if not event_path.exists():
        return None
    event = json.loads(event_path.read_text())
    points = event.get("rainfall_daily", {}).get("by_catchment", {}).get(catchment_id, [])
    real_points = [p for p in points if p.get("mm") is not None]
    if not real_points:
        return None
    peak = max(real_points, key=lambda p: p["mm"])
    return {
        "peak_date_utc": peak["t"],
        "peak_mm": peak["mm"],
        "unit": event["rainfall_daily"]["unit"],
        "source": event["rainfall_daily"]["source"],
        "note": event["rainfall_daily"]["note"],
    }


def _real_runoff_lines(catchment_id: str) -> list[list[list[float]]]:
    """Real wadi drainage LineStrings physically inside this catchment's real
    polygon (spatial join against catchments.geojson/wadis.geojson, both
    already committed basemap layers) -- not invented flow paths. No
    catchment_id attribute exists on the wadi features themselves (OSM has no
    concept of a hydrological catchment), so membership is geometric, not
    tag-based.

    Simplified further than the basemap copy (300 m, vs. wadis.geojson's own
    80 m) -- this feeds an animated flow effect meant to read at a glance from
    the outlet camera distance, not a hydrological reference layer.
    """
    catchments_path = BASEMAP_DIR / "catchments.geojson"
    wadis_path = BASEMAP_DIR / "wadis.geojson"
    if not catchments_path.exists() or not wadis_path.exists():
        return []
    catchments = gpd.read_file(catchments_path)
    wadis = gpd.read_file(wadis_path)
    match = catchments[catchments["catchment_id"] == catchment_id]
    if match.empty:
        return []
    poly = match.geometry.iloc[0]
    within = wadis[wadis.intersects(poly)].copy()
    if within.empty:
        return []
    within = within.set_crs("EPSG:4326") if within.crs is None else within
    projected = within.to_crs(_spatial.CRS_MEASURE)
    projected["geometry"] = projected.geometry.simplify(RUNOFF_SIMPLIFY_M, preserve_topology=True)
    within = projected.to_crs("EPSG:4326")
    return [
        [[round(x, 5), round(y, 5)] for x, y in geom.coords]
        for geom in within.geometry
        if geom is not None and not geom.is_empty
    ]


def build(api_base: str) -> dict:
    plume = _post(
        api_base, "/api/v1/plume/simulate",
        {"event_id": EVENT_ID, "outlet_id": OUTLET_ID},
    )
    exposure = _post(
        api_base, "/api/v1/exposure/calculate",
        {"event_id": EVENT_ID, "outlet_id": OUTLET_ID, "horizon_hours": HORIZON_HOURS},
    )
    outlets = _get(api_base, "/api/v1/outlets")
    outlet = next(o for o in outlets if o["outlet_id"] == OUTLET_ID)

    # frames, grouped by timestep -- the shape the camera flythrough steps through
    by_t: dict[float, list[dict]] = {}
    for row in plume["contours"]:
        by_t.setdefault(row["t_hours"], []).append(
            {"probability": row["probability"], "geometry": row["geometry"]}
        )
    frames = [
        {"t_hours": t, "contours": by_t[t]}
        for t in sorted(by_t)
    ]

    results = exposure.get("results", [])
    reef_exposure = [
        {
            "reef_zone_id": r["reef_zone_id"],
            "risk_score": r["risk_score"],
            "risk_level": r["risk_level"],
        }
        for r in results
    ]

    # The current-grid-masking caveat, carried verbatim -- the 3D view says this on
    # screen rather than implying more current-driven realism than the run shows
    # (docs/model_card.md Component C, docs/HANDOFF_abd_2026-08-06.md §2.5).
    masking_caveat = next(
        (c["message"] for c in plume.get("caveats", []) if "masks as land" in c.get("message", "")),
        None,
    )

    catchment_id = outlet["catchment_id"]
    return {
        "event_id": EVENT_ID,
        "outlet_id": OUTLET_ID,
        "horizon_hours": HORIZON_HOURS,
        "release": {
            "lon": outlet["lon"],
            "lat": outlet["lat"],
            "catchment_id": catchment_id,
        },
        "is_stub": plume["is_stub"],
        "model_version": plume["model_version"],
        "plume_source": next(
            (r["formula_terms"]["plume_source"] for r in results), "REAL_PARTICLE_ENGINE"
        ),
        "frames": frames,
        "reef_exposure": reef_exposure,
        "current_masking_caveat": masking_caveat,
        "rainfall": _real_rainfall(catchment_id),
        "runoff_lines": _real_runoff_lines(catchment_id),
        "source": (
            f"POST /api/v1/plume/simulate + /api/v1/exposure/calculate against a "
            f"live run of backend/src/api/main.py, plus frontend/public/fixtures/event.json "
            f"(rainfall) and basemap catchments+wadis (runoff paths) "
            f"(scripts/frontend_journey.py)"
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://127.0.0.1:8001", help="base URL of a running API instance")
    ap.add_argument("--out", required=True, help="output directory for journey3d.json")
    args = ap.parse_args()

    print("ReefShield 3D Journey fixture")
    print("=" * 62)
    data = build(args.api.rstrip("/"))
    print(f"  event {data['event_id']}  outlet {data['outlet_id']}")
    print(f"  is_stub={data['is_stub']}  model_version={data['model_version']}")
    print(f"  {len(data['frames'])} timesteps, "
          f"{sum(len(f['contours']) for f in data['frames'])} contour polygons total")
    print(f"  reef zones reached: {[r['reef_zone_id'] for r in data['reef_exposure']]}")
    if data["current_masking_caveat"]:
        print(f"  current-masking caveat present: yes")
    if data["rainfall"]:
        print(f"  real rainfall peak: {data['rainfall']['peak_mm']} {data['rainfall']['unit']} "
              f"on {data['rainfall']['peak_date_utc'][:10]}")
    else:
        print("  real rainfall: none found for this catchment")
    print(f"  real runoff wadi lines within the release catchment: {len(data['runoff_lines'])}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "journey3d.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(f"\n  wrote {path} ({path.stat().st_size:,} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
