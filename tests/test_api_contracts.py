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

import json
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


def test_event_catalogue_is_real_and_ranked():
    """Phase 4, 01-karam.md item 1/2: /api/v1/events used to serve only the 5
    events mentioned in docs/event_dates.md's prose, with no ranking columns at
    all. It must now serve the real 675-event catalogue, ranked by `rank`
    (max_daily_mm) -- the canonical ranking, not `max_anomaly_ratio`."""
    r = client.get(f"{PREFIX}/events")
    check("events 200", r.status_code == 200)
    evs = r.json()
    check(f"real catalogue, not the 5-event markdown list ({len(evs)})", len(evs) >= 675)
    check("every catalogued event carries rank",
          sum(1 for e in evs if e["rank"] is not None) >= 675)
    ranked = [e for e in evs if e["rank"] is not None]
    check("sorted by rank ascending",
          [e["rank"] for e in ranked] == sorted(e["rank"] for e in ranked))
    check("rank 1 has the highest max_daily_mm",
          ranked[0]["max_daily_mm"] == max(e["max_daily_mm"] for e in ranked))

    r2 = client.get(f"{PREFIX}/events/AQ-2016-10-28")
    check("demo event 200", r2.status_code == 200)
    demo = r2.json()
    check("demo event carries its real rank", demo["rank"] is not None)
    check("demo event keeps its literature label",
          demo["label"] == "AQ-2016-10-28" and demo["source"] == "docs/event_dates.md")

    check("unknown event 404s",
          client.get(f"{PREFIX}/events/AQ-9999-01-01").status_code == 404)


def test_stub_endpoints_are_flagged():
    """Whichever branch answers, the endpoint must declare which one it was.

    This used to assert "runoff is_stub is True". That was true when it was written
    and stopped being true the moment a trained artifact was registered, so a correct
    upgrade turned the test red. What holds in BOTH modes is the invariant worth
    testing: the response says where its numbers came from, and never renders an
    absent number as a zero.
    """
    r = client.post(f"{PREFIX}/runoff/predict",
                    json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2})
    j = r.json()
    check("runoff declares is_stub as a bool", isinstance(j["is_stub"], bool))

    if j["is_stub"]:
        check("stubbed runoff carries a critical is_stub caveat",
              any(c["severity"] == "critical" and c["field"] == "is_stub"
                  for c in j["caveats"]))
        check("stubbed runoff names itself a stub in provenance",
              any(p["kind"] == "stub" for p in j["provenance"]))
    else:
        # Component A is a runoff CLASSIFIER, not a volume regressor, so there is no
        # m3 to report. A 0.0 here would be a fabricated model output presented as a
        # prediction — the failure febc24a fixed. It must read as a gap.
        check("real runoff reports no fabricated volume",
              j["predicted_runoff_m3"] is None,
              f"got {j['predicted_runoff_m3']!r}")
        check("real runoff explains the absent volume as a gap",
              any(c["severity"] == "critical" and c["field"] == "predicted_runoff_m3"
                  for c in j["caveats"]))
        check("real runoff names the model artefact it used",
              j["model_version"] not in (None, "", "unregistered"),
              f"got {j['model_version']!r}")
        check("real runoff carries a derived provenance entry",
              any(p["kind"] == "derived" for p in j["provenance"]))

    # Wired to the real particle engine (5 Aug 2026, backend/src/api/main.py's
    # _real_contours) -- AQ-2016-10-28 is the one event with a real release
    # time (docs/event_dates.md) and calibrated params, so this is no longer
    # the synthetic-circle stub.
    r = client.post(f"{PREFIX}/plume/simulate",
                    json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02"})
    j = r.json()
    check("plume is no longer flagged is_stub", j["is_stub"] is False)
    check("plume declares a derived provenance entry",
          any(p["kind"] == "derived" for p in j["provenance"]))
    check("plume contours are non-empty", len(j["contours"]) > 0)

    # An undocumented event genuinely has no release time -- the engine must
    # refuse, not guess one (docs/event_dates.md rule 1).
    r = client.post(f"{PREFIX}/plume/simulate",
                    json={"event_id": "AQ-9999-01-01", "outlet_id": "AQ-O02"})
    check("plume simulate 422s for an event with no documented flood_arrival_utc",
          r.status_code == 422, f"got {r.status_code}: {r.text}")


def test_exposure_contract_and_formula_terms():
    r = client.post(f"{PREFIX}/exposure/calculate",
                    json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02",
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
    check("formula_terms records the plume input as the real particle engine",
          ft.get("plume_source") == "REAL_PARTICLE_ENGINE", f"got {ft.get('plume_source')!r}")

    # Phase 4, 01-karam.md item 4: confidence_adjustment used to be a literal
    # 0.6 regardless of input. It must now be derived from the real cached
    # GEFS exceedance snapshot -- the reason string is the tell, since AQ-C02's
    # exceedance_prob happens to be 0.0 today too (agreement 1.0 either way).
    check("confidence_adjustment_reason is computed from real GEFS members, "
          "not the old fixed sentence",
          "GEFS members" in ft.get("confidence_adjustment_reason", "")
          and "agreement" in ft.get("confidence_adjustment_reason", ""),
          f"got {ft.get('confidence_adjustment_reason')!r}")
    for field in ("confidence_members_exceeding", "confidence_members_total",
                  "confidence_threshold_value_mm"):
        check(f"formula_terms includes {field}", field in ft)

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
                    json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O01",
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
                json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02"})
    # Scoped to the scenario just requested. Unscoped would read whichever run is
    # newest in the table, which a cached response leaves unchanged.
    r = client.get(f"{PREFIX}/alerts", params={"min_level": "minimal",
                                              "event_id": "AQ-2016-10-28",
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


def _runoff_predict():
    return client.post(f"{PREFIX}/runoff/predict",
                       json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 10}).json()


CAVEAT_MATRIX = [
    # (label, callable returning a response json, condition, expected field)
    ("reef-zones / placeholder weight",
     lambda: client.get(f"{PREFIX}/reef-zones").json()[0]["caveats"],
     "always", "sensitivity_weight"),
    # Labelled by FIELD, and both the width caveat and the shallow-only caveat use
    # area_km2 — which is why this row kept passing after the geometry swap made one
    # of them false. test_obsolete_width_claim_is_gone checks the CLAIM, not the field.
    ("reef-zones / area qualifier present",
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
    # The field depends on which branch serves, so it is resolved at run time rather
    # than frozen into the row. Registering a trained artifact flipped the endpoint
    # from stub to real and this row went red on a correct upgrade; the caveat that
    # must always be present is the one declaring the mode, not the stub one.
    #   stub -> `is_stub`, critical, "not a prediction"
    #   real -> `predicted_runoff_m3`, critical, "a gap, not a zero"
    ("runoff / serving mode declared",
     lambda: _runoff_predict()["caveats"],
     "always", lambda: "is_stub" if _runoff_predict()["is_stub"]
                       else "predicted_runoff_m3"),
    ("plume / bathymetry substitution",
     # "E" won't do any more: the real particle engine needs a real release
     # time, parsed from docs/event_dates.md, which only AQ-2016-10-28 has.
     lambda: client.post(f"{PREFIX}/plume/simulate",
                         json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02"}).json()["caveats"],
     "always", "geometry"),
    ("exposure / risk band thresholds",
     lambda: client.post(f"{PREFIX}/exposure/calculate",
                         json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02"}).json()["caveats"],
     "always", "risk_level"),
    ("exposure / AQ-O04 harbour basin",
     lambda: client.post(f"{PREFIX}/exposure/calculate",
                         json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O04"}).json()["caveats"],
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


def test_obsolete_width_claim_is_gone():
    """No payload may assert the 250 m width while real ACA geometry is loaded.

    This shipped. /reef-zones gated the width caveat behind `is_provisional` when the
    Atlas geometry landed; /exposure/calculate built its caveats through a different
    helper that emitted it unconditionally, so every exposure result asserted "reef
    zone width is a flat 250 m assumption" about the Atlas's own 5 m polygons — a
    false statement about a 5 m product, delivered as a caveat, i.e. in the one place
    a reader is entitled to trust.

    CAVEAT_MATRIX could not catch it: it matches on `field`, and both the width
    caveat and reef_shallow_only report `area_km2`. So this asserts on the claim.

    A HISTORICAL mention is fine and is deliberately still shipped — reef_area_correction
    explains that the old 5.69 km² figure came from 250 m strips. What must not appear
    is the present-tense assertion that the width IS an assumption today.
    """
    _, is_provisional = da.reef_zones(include_geometry=False)
    if is_provisional:
        print("\n  provisional geometry loaded — the width caveat is CORRECT; skipping")
        return

    payloads = {
        "reef-zones": client.get(f"{PREFIX}/reef-zones").json(),
        "exposure/calculate": client.post(
            f"{PREFIX}/exposure/calculate",
            json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02"}).json(),
        "alerts": client.get(f"{PREFIX}/alerts").json(),
    }
    for name, payload in payloads.items():
        blob = json.dumps(payload, ensure_ascii=False)
        check(f"{name} does not assert the width is a 250 m assumption",
              "width is a flat 250 m assumption" not in blob,
              f"{name} still carries the obsolete width claim")

    # And the replacement must actually be there, or the fix removed a qualifier
    # instead of correcting it.
    # The replacement reports `zone_fraction_affected`, not `area_km2`: it qualifies the
    # fraction the engine outputs, whereas the width caveat qualified the absolute area.
    # Different field because it is a different claim, which is the whole distinction.
    exposure = payloads["exposure/calculate"]
    zone_caveats = exposure["results"][0]["caveats"] if exposure.get("results") else []
    check("exposure results carry the shallow-only qualifier instead",
          any(c["field"] == "zone_fraction_affected" and "shallow" in c["message"].lower()
              for c in zone_caveats),
          f"fields present: {[c['field'] for c in zone_caveats]}")


def test_caveat_coverage_table():
    print("\n  caveat coverage — which condition fires which caveat, verified")
    print(f"  {'fires?':7s} {'field':18s} {'condition':26s} where")
    for label, getter, condition, field in CAVEAT_MATRIX:
        # `field` may be a callable when which caveat is required depends on how the
        # endpoint is currently serving. Resolved here so the row states the rule,
        # not a snapshot of today's deployment.
        want = field
        try:
            want = field() if callable(field) else field
            caveats = getter()
            fired = any(c.get("field") == want and c.get("message")
                        for c in caveats)
        except Exception as e:
            fired, condition = False, f"ERROR {type(e).__name__}"
            want = want if isinstance(want, str) else "?"
        print(f"  {'YES' if fired else 'NO ':7s} {want:18s} {condition:26s} {label}")
        if not fired:
            FAILURES.append(f"caveat not reached: {label}")
    check("every enumerated caveat actually reaches a payload",
          not [f for f in FAILURES if f.startswith("caveat not reached")])


def test_cache_actually_caches():
    da.PLUME_CACHE._store.clear()
    da.PLUME_CACHE.hits = da.PLUME_CACHE.misses = 0
    body = {"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O03", "horizon_hours": 24}
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
    test_obsolete_width_claim_is_gone()
    test_caveat_coverage_table()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        sys.exit(1)
    print("API contracts verified; every enumerated caveat reaches a payload")
