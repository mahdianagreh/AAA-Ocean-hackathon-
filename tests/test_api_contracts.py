"""API contract and caveat-coverage tests.

Run: .venv/bin/python tests/test_api_contracts.py

Covers:
  * every concept §17 endpoint exists and returns the declared shape;
  * the caveat-coverage table the plan asks for — which endpoint fires which
    caveat under which condition, enumerated and verified, because a caveat that
    exists in code but never reaches a payload is the same as not having it;
  * stub responses are unmistakably flagged;
  * caching actually caches.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_tmp = tempfile.mkdtemp()
os.environ["REEFSHIELD_EXPOSURE_DB"] = str(Path(_tmp) / "api_test.sqlite")

from fastapi.testclient import TestClient  # noqa: E402

from backend.src.api import data_access as da  # noqa: E402
from backend.src.api.main import PREFIX, app  # noqa: E402

client = TestClient(app)
FAILURES: list[str] = []


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILURES.append(name)


# Concept §17, verbatim.
REQUIRED_ROUTES = [
    ("GET", "/health"), ("GET", "/data-sources"),
    ("GET", "/catchments"), ("GET", "/catchments/{catchment_id}"),
    ("GET", "/reef-zones"),
    ("GET", "/events"), ("GET", "/events/{event_id}"),
    ("POST", "/runoff/predict"), ("POST", "/plume/simulate"),
    ("POST", "/exposure/calculate"),
    ("POST", "/backtests/run"), ("GET", "/backtests/{run_id}"),
    ("GET", "/alerts"), ("POST", "/explain"), ("POST", "/ask"),
]


def test_every_required_route_is_registered():
    registered = {(m, r.path) for r in app.routes
                  for m in getattr(r, "methods", set())}
    for method, path in REQUIRED_ROUTES:
        full = f"{PREFIX}{path}"
        check(f"{method} {path}", (method, full) in registered, "not registered")


def test_health_reports_artifacts_honestly():
    r = client.get(f"{PREFIX}/health")
    check("health 200", r.status_code == 200)
    j = r.json()
    check("health lists artifact presence", isinstance(j["artifacts_present"], dict))
    # reef_zones.gpkg genuinely does not exist yet — health must say so.
    if not j["artifacts_present"].get("reef_zones"):
        check("degraded status when the real ACA export is absent",
              j["status"] == "degraded" and any("Coral Atlas" in x
                                                for x in j["degraded_reason"]),
              f"status={j['status']} reasons={j['degraded_reason']}")


def test_data_sources_reference_real_qa_figures():
    r = client.get(f"{PREFIX}/data-sources")
    check("data-sources 200", r.status_code == 200)
    qa_dir = ROOT / "docs" / "qa_screenshots"
    missing = []
    for src in r.json():
        for fig in src["qa_figures"]:
            if not (qa_dir / fig).exists():
                missing.append(f"{src['name']}:{fig}")
    check("every QA figure named by data-sources exists on disk", not missing,
          f"missing {missing}")
    check("every source declares at least one limitation",
          all(src["limitations"] for src in r.json()))
    subs = [s for s in r.json() if s["substituted"]]
    check("the GMRT substitution is declared with a note",
          len(subs) == 1 and "GEBCO" in (subs[0]["substitution_note"] or ""),
          f"{[s['name'] for s in subs]}")


def test_catchments_shape_and_ids():
    r = client.get(f"{PREFIX}/catchments")
    check("catchments 200", r.status_code == 200)
    ids = [c["catchment_id"] for c in r.json()]
    check(f"AQ-C01..AQ-C05 present {ids}",
          ids == ["AQ-C01", "AQ-C02", "AQ-C03", "AQ-C04", "AQ-C05"])

    r1 = client.get(f"{PREFIX}/catchments/AQ-C01")
    j = r1.json()
    check("AQ-C01 detail includes geometry", j["geometry"] is not None)
    check("AQ-C01 detail includes landcover features", bool(j["landcover"]))
    check("AQ-C01 area matches the geometry contract (4453.1 +-5%)",
          abs(j["area_km2"] - 4453.1) / 4453.1 < 0.05, f"got {j['area_km2']}")
    check("unknown catchment 404s", client.get(f"{PREFIX}/catchments/AQ-C99").status_code == 404)


def test_reef_zones_shape():
    r = client.get(f"{PREFIX}/reef-zones")
    zones = r.json()
    check("reef-zones 200", r.status_code == 200)
    check(f"8 zones R-01..R-08 ({len(zones)})",
          [z["reef_zone_id"] for z in zones] == [f"R-0{i}" for i in range(1, 9)])
    check("every zone weight is the 1.0 placeholder",
          all(z["sensitivity_weight"] == 1.0 for z in zones))
    check("every zone is labelled PLACEHOLDER_PENDING_MARINE_SCIENTIST",
          all(z["sensitivity_weight_status"] == "PLACEHOLDER_PENDING_MARINE_SCIENTIST"
              for z in zones))


def test_stub_endpoints_are_flagged():
    r = client.post(f"{PREFIX}/runoff/predict",
                    json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2})
    j = r.json()
    check("runoff is flagged is_stub", j["is_stub"] is True)
    check("runoff carries a critical stub caveat",
          any(c["severity"] == "critical" and c["field"] == "is_stub"
              for c in j["caveats"]))

    r = client.post(f"{PREFIX}/plume/simulate",
                    json={"event_id": "AQ-2016-10-25", "outlet_id": "AQ-O02"})
    j = r.json()
    check("plume is flagged is_stub", j["is_stub"] is True)
    check("plume contours are non-empty", len(j["contours"]) > 0)


def test_exposure_contract_and_formula_terms():
    r = client.post(f"{PREFIX}/exposure/calculate",
                    json={"event_id": "AQ-2016-10-25", "outlet_id": "AQ-O02",
                          "horizon_hours": 24})
    check("exposure 200", r.status_code == 200)
    j = r.json()
    check("at least one zone scored from AQ-O02", len(j["results"]) > 0)
    if not j["results"]:
        return

    res = j["results"][0]
    for field in ("risk_score", "risk_level", "max_exposure_probability",
                  "zone_fraction_affected", "confidence", "formula_terms"):
        check(f"result carries {field}", field in res)
    check("risk_score within 0-100", 0 <= res["risk_score"] <= 100)
    check("zone_fraction_affected within 0-1", 0 <= res["zone_fraction_affected"] <= 1)

    ft = res["formula_terms"]
    for term in ("plume_probability", "relative_sediment_intensity",
                 "exposure_duration_weight", "habitat_sensitivity_weight",
                 "confidence_adjustment", "raw_score", "risk_score"):
        check(f"formula_terms includes {term}", term in ft)
    check("formula_terms records the measurement CRS as EPSG:32636",
          ft.get("measure_crs") == "EPSG:32636", f"got {ft.get('measure_crs')}")
    check("formula_terms records that the plume input is a stub",
          ft.get("plume_source") == "SYNTHETIC_STUB")

    # The audit path: a stored run must reconstruct.
    rid = j["run_id"]
    r2 = client.get(f"{PREFIX}/exposure/runs/{rid}")
    check("stored run reloads by run_id", r2.status_code == 200)
    check("reloaded run preserves formula_terms",
          bool(r2.json()["results"][0]["formula_terms"]))
    check("unknown run_id 404s",
          client.get(f"{PREFIX}/exposure/runs/nope").status_code == 404)


def test_unreached_zones_are_explained_not_silently_empty():
    r = client.post(f"{PREFIX}/exposure/calculate",
                    json={"event_id": "AQ-2016-10-25", "outlet_id": "AQ-O01",
                          "horizon_hours": 24})
    j = r.json()
    if j["results"]:
        print("        (AQ-O01 now reaches a zone; skipping the empty-result check)")
        return
    check("an empty result set carries an explanatory caveat",
          any(c["field"] == "results" and "not reached" in c["message"]
              for c in j["caveats"]),
          f"caveats: {[c['field'] for c in j['caveats']]}")


def test_backtest_refuses_honestly():
    r = client.post(f"{PREFIX}/backtests/run", json={"event_id": "AQ-2016-10-25"})
    j = r.json()
    check("backtest status is not_possible", j["status"] == "not_possible")
    check("backtest returns no fabricated metrics", j["metrics"] is None)
    check("backtest explains why in terms of the mooring evidence",
          "mooring" in (j["note"] or "").lower())


def test_explain_and_ask_contracts():
    r = client.post(f"{PREFIX}/explain", json={
        "catchment_id": "AQ-C01", "language": "en",
        "shap_drivers": [{"feature": "rainfall_3h_mm", "value": 41.2}],
        "plume_probability": 0.72, "arrival_window_hours": [8, 12],
        "confidence": "moderate", "reef_zone_id": "R-04", "rainfall_percentile": 99})
    check("explain 200", r.status_code == 200)
    j = r.json()
    check("explain declares its generator",
          j["generator"] == "deterministic_template")
    check("explain returns source_numbers", bool(j["source_numbers"]))
    check("explain uses the documented catchment name", "Wadi Yutum" in j["text"])

    r = client.post(f"{PREFIX}/ask", json={"question": "Why is the reef sensitivity 1.0?"})
    j = r.json()
    check("ask 200 with citations", r.status_code == 200 and len(j["citations"]) > 0)
    check("every citation names a source file and section",
          all(c["source_file"] and c["section"] for c in j["citations"]))

    r = client.get(f"{PREFIX}/ask/corpus")
    check("corpus endpoint excludes docs/ali",
          any("docs/ali" in d for d in r.json()["excluded_dirs"]))


def test_alerts_read_from_stored_runs():
    client.post(f"{PREFIX}/exposure/calculate",
                json={"event_id": "AQ-2016-10-25", "outlet_id": "AQ-O02"})
    # Scoped to the scenario just requested. Unscoped would read whichever run is
    # newest in the table, which a cached response leaves unchanged.
    r = client.get(f"{PREFIX}/alerts", params={"min_level": "minimal",
                                              "event_id": "AQ-2016-10-25",
                                              "outlet_id": "AQ-O02"})
    check("alerts 200", r.status_code == 200)
    check("alerts derive from a stored run", len(r.json()) > 0)
    if r.json():
        a = r.json()[0]
        check("alert headline is bilingual",
              bool(a["headline_en"]) and bool(a["headline_ar"]))
        check("alert carries the risk-band caveat",
              any(c["field"] == "risk_level" for c in a["caveats"]))
        check("alert is traceable to a stored run", bool(a["source_run_id"]))
        check("that run reconstructs with formula_terms",
              bool(client.get(f"{PREFIX}/exposure/runs/{a['source_run_id']}")
                   .json()["results"][0]["formula_terms"]))
    check("bad min_level rejected",
          client.get(f"{PREFIX}/alerts", params={"min_level": "wat"}).status_code == 400)


# ------------------------------------------------------- caveat coverage table

CAVEAT_MATRIX = [
    # (label, callable returning a response json, condition, expected field)
    ("reef-zones / placeholder weight",
     lambda: client.get(f"{PREFIX}/reef-zones").json()[0]["caveats"],
     "always", "sensitivity_weight"),
    ("reef-zones / 250 m width assumption",
     lambda: client.get(f"{PREFIX}/reef-zones").json()[0]["caveats"],
     "always", "area_km2"),
    ("reef-zones / provisional geometry",
     lambda: client.get(f"{PREFIX}/reef-zones").json()[0]["caveats"],
     "reef_zones.gpkg absent", "reef_zone_id"),
    ("outlets / AQ-O04 harbour basin",
     lambda: [{"field": "outlet_id", "message": o["caveat"] or ""}
              for o in client.get(f"{PREFIX}/outlets").json()
              if o["outlet_id"] == "AQ-O04"],
     "outlet is AQ-O04", "outlet_id"),
    ("catchments / area uncertainty",
     lambda: client.get(f"{PREFIX}/catchments/AQ-C01").json()["caveats"],
     "always", "area_km2"),
    ("catchments / land cover epoch",
     lambda: client.get(f"{PREFIX}/catchments/AQ-C01").json()["caveats"],
     "landcover present", "landcover"),
    ("catchments / soil is modelled",
     lambda: client.get(f"{PREFIX}/catchments/AQ-C01").json()["caveats"],
     "soil present", "soil"),
    ("runoff / stub flagged",
     lambda: client.post(f"{PREFIX}/runoff/predict",
                         json={"catchment_id": "AQ-C01",
                               "rainfall_mm_3h": 10}).json()["caveats"],
     "always while stubbed", "is_stub"),
    ("plume / bathymetry substitution",
     lambda: client.post(f"{PREFIX}/plume/simulate",
                         json={"event_id": "E", "outlet_id": "AQ-O02"}).json()["caveats"],
     "always", "geometry"),
    ("exposure / risk band thresholds",
     lambda: client.post(f"{PREFIX}/exposure/calculate",
                         json={"event_id": "E", "outlet_id": "AQ-O02"}).json()["caveats"],
     "always", "risk_level"),
    ("exposure / AQ-O04 harbour basin",
     lambda: client.post(f"{PREFIX}/exposure/calculate",
                         json={"event_id": "E", "outlet_id": "AQ-O04"}).json()["caveats"],
     "outlet is AQ-O04", "outlet_id"),
    ("explain / template disclosure",
     lambda: client.post(f"{PREFIX}/explain",
                         json={"catchment_id": "AQ-C01"}).json()["caveats"],
     "always", "text"),
    ("backtests / metrics unavailable",
     lambda: client.post(f"{PREFIX}/backtests/run",
                         json={"event_id": "E"}).json()["caveats"],
     "always", "metrics"),
]


def test_caveat_coverage_table():
    print("\n  caveat coverage — which condition fires which caveat, verified")
    print(f"  {'fires?':7s} {'field':18s} {'condition':26s} where")
    for label, getter, condition, field in CAVEAT_MATRIX:
        try:
            caveats = getter()
            fired = any(c.get("field") == field and c.get("message")
                        for c in caveats)
        except Exception as e:
            fired, condition = False, f"ERROR {type(e).__name__}"
        print(f"  {'YES' if fired else 'NO ':7s} {field:18s} {condition:26s} {label}")
        if not fired:
            FAILURES.append(f"caveat not reached: {label}")
    check("every enumerated caveat actually reaches a payload",
          not [f for f in FAILURES if f.startswith("caveat not reached")])


def test_cache_actually_caches():
    da.PLUME_CACHE._store.clear()
    da.PLUME_CACHE.hits = da.PLUME_CACHE.misses = 0
    body = {"event_id": "AQ-2016-10-25", "outlet_id": "AQ-O03", "horizon_hours": 24}
    client.post(f"{PREFIX}/plume/simulate", json=body)
    client.post(f"{PREFIX}/plume/simulate", json=body)
    stats = da.PLUME_CACHE.stats()
    check(f"identical plume request hits cache (hits={stats['hits']})",
          stats["hits"] >= 1, f"{stats}")


if __name__ == "__main__":
    print("API contract and caveat-coverage tests\n")
    print(" routes")
    test_every_required_route_is_registered()
    print("\n meta")
    test_health_reports_artifacts_honestly()
    test_data_sources_reference_real_qa_figures()
    print("\n geometry")
    test_catchments_shape_and_ids()
    test_reef_zones_shape()
    print("\n models and exposure")
    test_stub_endpoints_are_flagged()
    test_exposure_contract_and_formula_terms()
    test_unreached_zones_are_explained_not_silently_empty()
    test_backtest_refuses_honestly()
    print("\n language")
    test_explain_and_ask_contracts()
    print("\n alerts and caching")
    test_alerts_read_from_stored_runs()
    test_cache_actually_caches()
    test_caveat_coverage_table()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        sys.exit(1)
    print("API contracts verified; every enumerated caveat reaches a payload")
