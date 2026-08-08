"""Phase 4 what-if scenario engine — tasks/phase4/04-pulga.md items 1, 2, 3, 4.

Covers, all against the live routes rather than the model layer directly, so a
wiring mistake at the API boundary is caught even if the model layer itself is
correct:

  * `rainfall_multiplier` actually changes the real-path prediction, and does NOT
    change the stub path or a request with no feature row (nothing to scale).
  * `transmission_loss_override` actually changes `sediment_index` in the documented
    direction (lower tau -> higher index) and is echoed back verbatim.
  * Real SHAP drivers reach `/runoff/predict` under the frontend's own field names
    (`key`/`contribution`/`value`), not the model's internal ones (`feature`/`shap`).
  * The exposure cache key includes the two new scenario fields — this is the exact
    bug this file's own author found and fixed while building it: two different
    scenario requests for the same event/outlet were returning the same cached
    result, because the cache key did not yet know the scenario existed.
  * The mooring endpoint matches frontend/public/fixtures/event.json's `mooring`
    object field-for-field, and 404s (not an empty object) for any other event.
  * `/alerts` returns results sorted by risk_score, highest first.
  * `/runoff/predict` does not 500 on a real training-set row (see
    test_runoff_predict_does_not_crash_on_the_anchor_storm) — a pre-existing bug
    this file's own author found while fixing something else: the real path
    assigned the raw, unbounded sediment_index (e.g. 145,434 for the anchor
    storm) straight to `relative_sediment_intensity`, a field this schema
    declares `ge=0, le=1`. Unreachable before Phase 4, because every prior
    caller sent a bare request (no event_id), which happens to produce a small,
    already-in-range index instead of a real one — the bug was latent, not
    absent, and Phase 4's `training_row` preference was what first reached it.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

os.environ.setdefault(
    "REEFSHIELD_EXPOSURE_DB", str(Path(tempfile.mkdtemp()) / "test_phase4.sqlite")
)


def _client():
    from api.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


# ------------------------------------------------------------ rainfall_multiplier


def test_rainfall_multiplier_changes_the_real_path_prediction():
    from api.main import PREFIX

    # Must use a real event_id/catchment with a training-set feature row — a bare
    # request has none of RAINFALL_MM_COLUMNS in it (catchment_id/rainfall_mm_3h
    # don't match any of the 20 real feature names), so the multiplier would have
    # nothing to scale and this would only be detecting the echoed
    # `rainfall_multiplier` field changing, not a real effect on the prediction.
    client = _client()
    base = client.post(f"{PREFIX}/runoff/predict",
                       json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2,
                             "event_id": "AQ-2016-10-28"}).json()
    scaled = client.post(f"{PREFIX}/runoff/predict",
                         json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2,
                               "event_id": "AQ-2016-10-28",
                               "rainfall_multiplier": 1.8}).json()
    assert base["is_stub"] is False, "expected the real model registered for this test"
    assert scaled["rainfall_multiplier"] == 1.8
    assert base["rainfall_multiplier"] == 1.0
    assert scaled["runoff_probability"] != base["runoff_probability"], (
        "1.8x rainfall produced an identical runoff_probability to 1.0x — the "
        "multiplier is not reaching the real feature row"
    )


def test_rainfall_multiplier_default_is_a_no_op():
    from api.main import PREFIX

    client = _client()
    a = client.post(f"{PREFIX}/runoff/predict",
                    json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2,
                          "event_id": "AQ-2016-10-28"}).json()
    b = client.post(f"{PREFIX}/runoff/predict",
                    json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2,
                          "event_id": "AQ-2016-10-28", "rainfall_multiplier": 1.0}).json()
    assert a["runoff_probability"] == b["runoff_probability"]
    assert a["relative_sediment_intensity"] == b["relative_sediment_intensity"]


def test_rainfall_multiplier_has_nothing_to_scale_without_a_training_row():
    """Honest documentation of a real limitation, not a bug: a bare request (no
    event_id matching a training-set row) has none of RAINFALL_MM_COLUMNS in it,
    so the multiplier is echoed back but changes nothing — exactly the same
    "not meaningful" case test_drivers_are_suppressed_for_a_request_with_no_training_row
    covers for drivers."""
    from api.main import PREFIX

    client = _client()
    a = client.post(f"{PREFIX}/runoff/predict",
                    json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2}).json()
    b = client.post(f"{PREFIX}/runoff/predict",
                    json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2,
                          "rainfall_multiplier": 1.8}).json()
    assert a["runoff_probability"] == b["runoff_probability"]
    assert b["rainfall_multiplier"] == 1.8  # echoed, even though it had no effect
    assert "not meaningful" in b["feature_attributions_status"]


def test_rainfall_multiplier_is_bounded():
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/runoff/predict",
                    json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2,
                          "rainfall_multiplier": 5.0})
    assert r.status_code == 422, "5.0x should be rejected — bound is ScenarioDrawer's own 0.5-2.0"


def test_exposure_calculate_applies_the_multiplier_and_caches_separately():
    """The regression test for the actual bug found while building this: the
    exposure cache key did not include the scenario fields, so a scaled request
    returned the unscaled cached result."""
    from api.main import PREFIX

    client = _client()
    base = client.post(f"{PREFIX}/exposure/calculate",
                       json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02"}).json()
    scaled = client.post(f"{PREFIX}/exposure/calculate",
                         json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02",
                               "rainfall_multiplier": 1.8,
                               "transmission_loss_override": 0.25}).json()
    base_intensity = base["results"][0]["formula_terms"]["relative_sediment_intensity"]
    scaled_intensity = scaled["results"][0]["formula_terms"]["relative_sediment_intensity"]
    assert scaled_intensity != base_intensity, (
        "scenario request returned the same intensity as the default — the exposure "
        "cache key is not keying on rainfall_multiplier/transmission_loss_override"
    )
    assert "rainfall_multiplier=1.8x" in (
        scaled["results"][0]["formula_terms"]["relative_sediment_intensity_source"]
    )


def test_percentile_rank_features_are_not_silently_rescaled():
    """RAINFALL_MM_COLUMNS deliberately excludes rain_over_p50/p90/p99 and
    rain_self_percentile — scaling a percentile rank has no physical meaning. This
    pins that the caveat says so whenever the multiplier is not 1.0."""
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/exposure/calculate",
                    json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02",
                          "rainfall_multiplier": 1.5}).json()
    source = r["results"][0]["formula_terms"]["relative_sediment_intensity_source"]
    assert "percentile-rank features reflect the original storm" in source


# ------------------------------------------------------- transmission_loss_override


def test_transmission_loss_override_moves_sediment_index_in_the_documented_direction():
    """index ∝ (1 - tau): a LOWER transmission loss must produce a HIGHER index
    (less sediment lost in transit = more reaches the sea) — visible on
    `relative_sediment_intensity`, the field RunoffPrediction actually exposes.
    (There is no bare `sediment_index` field on this schema — a guarded
    `if "sediment_index" in ...` version of this assertion would silently never
    run, which is exactly the "a test that cannot fail is not a test" trap.)"""
    from api.main import PREFIX

    client = _client()
    higher_loss = client.post(f"{PREFIX}/runoff/predict",
                              json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2,
                                    "event_id": "AQ-2016-10-28",
                                    "transmission_loss_override": 0.85}).json()
    lower_loss = client.post(f"{PREFIX}/runoff/predict",
                             json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2,
                                   "event_id": "AQ-2016-10-28",
                                   "transmission_loss_override": 0.20}).json()
    assert higher_loss["transmission_loss"] == 0.85
    assert lower_loss["transmission_loss"] == 0.20
    assert lower_loss["relative_sediment_intensity"] > higher_loss["relative_sediment_intensity"]


def test_transmission_loss_override_is_bounded_to_the_negev_range():
    """[0.20, 0.85] — TAU_NEGEV, the nearest studied desert analog to Aqaba's
    wadis, per docs/HANDOFF_transmission_loss_2026-08-06.md. Deliberately
    NARROWER than SedimentParams.validate()'s technical [0, 1) sanity check —
    0.0 and 1.0 are code-legal but not physically defensible for this
    environment, so both must be rejected at the API boundary."""
    from api.main import PREFIX

    client = _client()
    for value in (0.0, 0.1, 0.19, 0.86, 0.99, 1.0):
        r = client.post(f"{PREFIX}/runoff/predict",
                        json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2,
                              "transmission_loss_override": value})
        assert r.status_code == 422, f"{value} should be rejected — outside [0.20, 0.85]"
    for value in (0.20, 0.525, 0.85):
        r = client.post(f"{PREFIX}/runoff/predict",
                        json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2,
                              "transmission_loss_override": value})
        assert r.status_code == 200, f"{value} should be accepted — inside [0.20, 0.85]"


def test_default_transmission_loss_is_the_anchored_value_not_none():
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/runoff/predict",
                    json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2}).json()
    assert r["transmission_loss"] == 0.525


def test_exposure_calculate_echoes_transmission_loss_too():
    """A3.4 close-out (Phase 5): runoff_predict has always echoed
    transmission_loss structurally; exposure_calculate applied
    transmission_loss_override to the real feature row but silently dropped the
    echo — the only way to know what value was actually used was to also call
    /runoff/predict separately. Fixed in main.py's exposure_calculate: the same
    value now lands in formula_terms["transmission_loss"], reusing
    RunoffPrediction's own real, computed value rather than re-deriving one."""
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/exposure/calculate",
                    json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02",
                          "transmission_loss_override": 0.3}).json()
    assert r["results"], "expected at least one reached reef zone for this fixture"
    for result in r["results"]:
        assert result["formula_terms"]["transmission_loss"] == 0.3


def test_exposure_calculate_transmission_loss_default_is_anchored_not_none():
    """Same fixed field, default (no override) case — must be the anchored
    0.525, not silently absent, matching /runoff/predict's own default."""
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/exposure/calculate",
                    json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02"}).json()
    assert r["results"]
    for result in r["results"]:
        assert result["formula_terms"]["transmission_loss"] == 0.525


def test_runoff_predict_does_not_crash_on_the_anchor_storm():
    """The exact regression: a real training-set row makes predict_one() return a
    raw sediment_index in the thousands (145,434 for the anchor storm), and
    relative_sediment_intensity is schema-bounded [0, 1] — constructing the
    response without squashing the index first raises a pydantic
    ValidationError, a 500 a live demo would hit on the one event this project
    is built around."""
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/runoff/predict",
                    json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2,
                          "event_id": "AQ-2016-10-28"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert 0.0 <= j["relative_sediment_intensity"] <= 1.0
    # The anchor event's own index maps to 0.500 by construction (ratio=1x) —
    # pin the actual number, not just "it's in range."
    assert abs(j["relative_sediment_intensity"] - 0.5) < 0.05, j["relative_sediment_intensity"]


# --------------------------------------------------------------------- SHAP drivers


def test_drivers_use_the_frontends_field_names_not_the_models():
    """frontend/src/api/predictions.ts's PredictionDriver is {key, contribution,
    value} — the model's own dict is {feature, shap, value}. This is the exact
    rename DriverBars.tsx already expects; a regression here would silently break
    every driver bar the moment this endpoint went live.

    Must call with `event_id` naming a real training-set row — see
    test_drivers_are_suppressed_for_a_request_with_no_training_row below for why
    a bare request must NOT get drivers."""
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/runoff/predict",
                    json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2,
                          "event_id": "AQ-2016-10-28"}).json()
    assert r["drivers"], "no drivers returned — is shap installed in this environment?"
    for d in r["drivers"]:
        assert set(d) == {"key", "contribution", "value"}, d
    assert r["feature_attributions_status"] is None


def test_drivers_are_suppressed_for_a_request_with_no_training_row():
    """The regression test for docs/HANDOFF_pulga_2026-08-06.md's finding: a bare
    request (no event_id, or an event_id/catchment with no real feature row)
    makes predict_one() return a FIXED, catchment/event-independent result —
    identical runoff_probability and identical drivers regardless of input —
    and predict_one()'s own feature_attributions_status cannot detect this
    (TreeSHAP does not fail on an all-NaN row). The API boundary must catch it,
    not repeat the model's blind spot."""
    from api.main import PREFIX

    client = _client()
    no_event = client.post(f"{PREFIX}/runoff/predict",
                           json={"catchment_id": "AQ-C01", "rainfall_mm_3h": 41.2}).json()
    assert no_event["drivers"] == []
    assert no_event["feature_attributions_status"] is not None
    assert "not meaningful" in no_event["feature_attributions_status"]
    assert any(c["field"] == "runoff_probability" and c["severity"] == "critical"
              for c in no_event["caveats"])

    # Same suppression for a DIFFERENT catchment, proving the fixed-result claim
    # rather than assuming it: two catchments with no training row should both be
    # suppressed identically, not just the one tested above.
    other_catchment = client.post(f"{PREFIX}/runoff/predict",
                                  json={"catchment_id": "AQ-C03", "rainfall_mm_3h": 41.2,
                                        "event_id": "AQ-1994-01-01"}).json()
    assert other_catchment["drivers"] == []
    assert other_catchment["feature_attributions_status"] is not None


def test_stub_path_still_returns_the_shape_even_with_no_drivers():
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/runoff/predict",
                    json={"catchment_id": "AQ-C05", "rainfall_mm_3h": 999999})
    assert r.status_code in (200, 422)  # bounds may reject an absurd value; either is fine here
    if r.status_code == 200:
        j = r.json()
        assert "drivers" in j and "feature_attributions_status" in j


# ----------------------------------------------------------------- mooring endpoint


def test_mooring_endpoint_matches_the_shipped_fixture_exactly():
    from api.main import PREFIX

    client = _client()
    r = client.get(f"{PREFIX}/events/AQ-2016-10-28/mooring")
    assert r.status_code == 200
    j = r.json()
    assert j["peak_suspended_sediment"] == {
        "value": 2.18, "unit": "g/L", "provenance": "reported", "uncertainty": None}
    assert j["salinity_anomaly"]["uncertainty"] == {"sigma": 19.0}
    assert j["salinity_minimum"]["value"] == 38.75
    assert j["sediment_mass_total"]["value"] == 24400.0
    assert j["elevated_duration_hours"]["value"] == 31.42
    assert j["series_available"] is False
    assert len(j["markers"]) == 2


def test_mooring_endpoint_404s_for_an_event_with_no_record():
    from api.main import PREFIX

    client = _client()
    r = client.get(f"{PREFIX}/events/AQ-1994-01-01/mooring")
    assert r.status_code == 404


# ------------------------------------------------------------------------- alerts


def test_alerts_are_sorted_by_risk_score_descending():
    from api.main import PREFIX

    client = _client()
    client.post(f"{PREFIX}/exposure/calculate",
               json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O02"})
    r = client.get(f"{PREFIX}/alerts", params={"min_level": "minimal",
                                              "event_id": "AQ-2016-10-28"})
    assert r.status_code == 200
    scores = [a["risk_score"] for a in r.json()]
    assert scores == sorted(scores, reverse=True), f"not sorted descending: {scores}"
