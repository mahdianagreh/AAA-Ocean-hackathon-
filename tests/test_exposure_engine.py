"""Exposure engine tests — the formula, the CRS guard, and the audit trail.

Run: .venv/bin/python tests/test_exposure_engine.py

Includes the two cross-checks the plan asks for by name:
  * a synthetic circular-buffer baseline: closer zones must score higher and arrive
    sooner, or something is structurally wrong;
  * a hand-computed spot check: one score worked out by hand must equal the
    engine's, to the bit.
"""

import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point, box

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.src.exposure import engine, store  # noqa: E402

FAILURES: list[str] = []


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILURES.append(name)


# ------------------------------------------------------------------- formula

def test_formula_is_the_product():
    """No hidden reshaping: the score is the product x 100, exactly."""
    score, terms = engine.calculate_exposure(0.5, 0.4, 0.5, 1.0, 0.6)
    expected = 0.5 * 0.4 * 0.5 * 1.0 * 0.6 * 100
    check(f"score is the plain product ({score} == {expected})",
          abs(score - expected) < 1e-12)
    check("raw_score recorded", abs(terms["raw_score"] - expected / 100) < 1e-12)
    check("score_scale recorded so the x100 is auditable",
          terms["score_scale"] == 100.0)


def test_hand_computed_spot_check():
    """The plan's §4.6 item 2: one full score, worked by hand.

    plume 0.8143536762323635 x sediment 0.49689251809099155
          x duration 0.875 x sensitivity 1.0 x confidence 0.6
    """
    p, s, d, h, c = 0.8143536762323635, 0.49689251809099155, 0.875, 1.0, 0.6
    by_hand = p * s * d * h * c * 100
    score, terms = engine.calculate_exposure(p, s, d, h, c)
    check(f"hand-computed {by_hand:.10f} == engine {score:.10f}",
          abs(by_hand - score) < 1e-12,
          f"delta {abs(by_hand - score):.3e}")
    check("hand-computed lands in 'low' band", engine.risk_level(score) == "low",
          f"got {engine.risk_level(score)}")


def test_missing_input_raises_not_zeroes():
    """Standing law #1: a gap is a gap. Never silently a zero."""
    for bad in (None, float("nan")):
        try:
            engine.calculate_exposure(bad, 0.5, 0.5, 1.0, 1.0)
            check(f"missing plume_probability ({bad!r}) rejected", False,
                  "it was accepted")
        except ValueError:
            check(f"missing plume_probability ({bad!r}) rejected", True)


def test_out_of_range_rejected():
    try:
        engine.calculate_exposure(1.4, 0.5, 0.5, 1.0, 1.0)
        check("probability > 1 rejected", False, "accepted 1.4")
    except ValueError:
        check("probability > 1 rejected", True)


def test_risk_bands_cover_0_to_100():
    for score, expected in [(0, "minimal"), (20, "minimal"), (21, "low"),
                            (40, "low"), (55, "moderate"), (61, "high"),
                            (80, "high"), (81, "critical"), (100, "critical")]:
        got = engine.risk_level(score)
        check(f"score {score} -> {expected}", got == expected, f"got {got}")
    for bad in (-1, 101):
        try:
            engine.risk_level(bad)
            check(f"score {bad} rejected", False, "accepted")
        except ValueError:
            check(f"score {bad} rejected", True)


def test_sensitivity_placeholder_flagged_in_terms():
    _, terms = engine.calculate_exposure(0.5, 0.5, 0.5, 1.0, 1.0)
    check("placeholder weight is labelled in formula_terms",
          terms["habitat_sensitivity_weight_status"]
          == "PLACEHOLDER_PENDING_MARINE_SCIENTIST")
    _, terms2 = engine.calculate_exposure(0.5, 0.5, 0.5, 2.5, 1.0)
    check("a non-1.0 weight is labelled as scientist-assigned",
          terms2["habitat_sensitivity_weight_status"] == "SCIENTIST_ASSIGNED")


# ----------------------------------------------------------------- geometry

def test_measure_crs_is_enforced():
    """The bug class this workstream has already shipped once."""
    zones = gpd.GeoDataFrame(
        {"reef_zone_id": ["R-01"]},
        geometry=[box(34.96, 29.50, 34.97, 29.52)], crs="EPSG:4326",
    )
    plume = gpd.GeoDataFrame(
        {"t_hours": [3.0], "probability": [0.5]},
        geometry=[box(34.955, 29.495, 34.975, 29.525)], crs="EPSG:4326",
    )
    out = engine.intersect_plume_with_zones(plume, zones)
    check("overlay output is in EPSG:32636", out.crs.to_epsg() == 32636,
          f"got {out.crs}")

    # And the guard itself refuses a wrong frame.
    try:
        engine._assert_measure_crs(zones, "zones")
        check("_assert_measure_crs rejects EPSG:4326", False, "accepted 4326")
    except ValueError:
        check("_assert_measure_crs rejects EPSG:4326", True)

    try:
        engine._assert_measure_crs(zones.to_crs("EPSG:3857"), "zones")
        check("_assert_measure_crs rejects EPSG:3857", False, "accepted 3857")
    except ValueError:
        check("_assert_measure_crs rejects EPSG:3857", True)


def _radial_scenario():
    """Three zones at increasing distance from one outlet, plus growing contours."""
    outlet = gpd.GeoSeries([Point(34.97, 29.47)], crs="EPSG:4326").to_crs(
        engine.CRS_MEASURE).iloc[0]

    zones, ids = [], []
    for i, offset in enumerate([500, 1500, 3000], start=1):
        ids.append(f"R-{i:02d}")
        zones.append(Point(outlet.x - offset, outlet.y).buffer(250))
    zgdf = gpd.GeoDataFrame({"reef_zone_id": ids}, geometry=zones,
                            crs=engine.CRS_MEASURE)

    rows = []
    for t, radius, prob in [(3, 1000, 0.9), (6, 2000, 0.7), (12, 4000, 0.4)]:
        rows.append({"t_hours": float(t), "probability": prob,
                     "geometry": outlet.buffer(radius)})
    pgdf = gpd.GeoDataFrame(rows, crs=engine.CRS_MEASURE)
    return zgdf, pgdf


def test_closer_zones_score_higher_and_arrive_sooner():
    """The plan's §4.6 item 1: the circular-buffer baseline sanity check."""
    zones, plume = _radial_scenario()
    overlay = engine.intersect_plume_with_zones(plume, zones)

    summaries = []
    for zid in ["R-01", "R-02", "R-03"]:
        s = engine.summarise_zone(zid, overlay, relative_sediment_intensity=0.5,
                                  confidence_adjustment=1.0, horizon_hours=12.0)
        summaries.append(s)

    check("all three zones are reached", all(s is not None for s in summaries))
    if not all(summaries):
        return

    scores = [s["risk_score"] for s in summaries]
    arrivals = [s["arrival_window_hours"][0] for s in summaries]
    check(f"score decreases with distance {[round(x, 2) for x in scores]}",
          scores[0] > scores[1] > scores[2])
    check(f"arrival time increases with distance {arrivals}",
          arrivals[0] <= arrivals[1] <= arrivals[2])


def test_unreached_zone_is_none_not_zero():
    zones, plume = _radial_scenario()
    far = gpd.GeoDataFrame(
        {"reef_zone_id": ["R-99"]},
        geometry=[zones.geometry.iloc[0].centroid.buffer(200).union(
            zones.geometry.iloc[0])],
        crs=engine.CRS_MEASURE,
    )
    # A zone 50 km away cannot be in the overlay at all.
    outlet_far = gpd.GeoDataFrame(
        {"reef_zone_id": ["R-FAR"]},
        geometry=[Point(zones.geometry.iloc[0].centroid.x - 50_000,
                        zones.geometry.iloc[0].centroid.y).buffer(250)],
        crs=engine.CRS_MEASURE,
    )
    overlay = engine.intersect_plume_with_zones(
        plume, gpd.GeoDataFrame(
            {"reef_zone_id": list(far["reef_zone_id"]) + list(outlet_far["reef_zone_id"])},
            geometry=list(far.geometry) + list(outlet_far.geometry),
            crs=engine.CRS_MEASURE))
    s = engine.summarise_zone("R-FAR", overlay, 0.5, 1.0, 12.0)
    check("a zone the plume never reaches returns None, not a 0 score", s is None)


def test_fraction_never_exceeds_one():
    zones, plume = _radial_scenario()
    overlay = engine.intersect_plume_with_zones(plume, zones)
    check("zone_fraction_affected <= 1 for every row",
          bool((overlay["zone_fraction_affected"] <= 1.0 + 1e-9).all()))


# ------------------------------------------------------------------- storage

def test_formula_terms_round_trip(tmp_db):
    zones, plume = _radial_scenario()
    overlay = engine.intersect_plume_with_zones(plume, zones)
    s = engine.summarise_zone("R-01", overlay, 0.5, 0.6, 12.0)
    s["confidence"] = engine.confidence_label(0.6)

    rid = store.new_run_id()
    store.save_run(rid, "AQ-2016-10-25", "AQ-O02", [s], {"exposure_engine": "test"})
    back = store.get_run(rid)

    check("run reloads", back is not None)
    if not back:
        return
    check("formula_terms survive the round trip",
          back["results"][0]["formula_terms"] == s["formula_terms"],
          "terms differ after reload")
    check("risk_score survives exactly",
          back["results"][0]["risk_score"] == s["risk_score"])


def test_store_refuses_a_score_without_terms(tmp_db):
    try:
        store.save_run(store.new_run_id(), "E", "O",
                       [{"reef_zone_id": "R-01", "risk_score": 50,
                         "risk_level": "moderate", "max_exposure_probability": 0.5,
                         "zone_fraction_affected": 0.5, "formula_terms": {}}],
                       {})
        check("store rejects a result with empty formula_terms", False, "accepted")
    except ValueError:
        check("store rejects a result with empty formula_terms", True)


if __name__ == "__main__":
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        os.environ["REEFSHIELD_EXPOSURE_DB"] = str(Path(d) / "t.sqlite")
        tmp_db = True

        print("Exposure engine tests\n")
        print(" formula")
        test_formula_is_the_product()
        test_hand_computed_spot_check()
        test_missing_input_raises_not_zeroes()
        test_out_of_range_rejected()
        test_risk_bands_cover_0_to_100()
        test_sensitivity_placeholder_flagged_in_terms()

        print("\n geometry and CRS")
        test_measure_crs_is_enforced()
        test_closer_zones_score_higher_and_arrive_sooner()
        test_unreached_zone_is_none_not_zero()
        test_fraction_never_exceeds_one()

        print("\n formula_terms storage")
        test_formula_terms_round_trip(tmp_db)
        test_store_refuses_a_score_without_terms(tmp_db)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        sys.exit(1)
    print("exposure engine verified")
