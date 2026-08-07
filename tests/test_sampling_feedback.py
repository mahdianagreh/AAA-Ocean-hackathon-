"""B7 — Adaptive Sampling Recommender (Phase 5, tasks/phase5/04-pulga.md item
3). The single most important property: `adjusted_priority == risk_score`
exactly, for every zone, until real feedback accumulates — the fallback is
the literal default, not an approximation. `risk_score` itself must never
move because of this feature; `exposure/engine.py`'s own formula is untouched.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

os.environ.setdefault(
    "REEFSHIELD_EXPOSURE_DB", str(Path(tempfile.mkdtemp()) / "test_sampling.sqlite")
)
os.environ.setdefault(
    "REEFSHIELD_SAMPLING_FEEDBACK_DB",
    str(Path(tempfile.mkdtemp()) / "test_sampling_feedback.sqlite"),
)

ANCHOR_EVENT = "AQ-2016-10-28"
OUTLET = "AQ-O02"


def _client():
    from api.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


def _calculate(client, **overrides):
    from api.main import PREFIX

    body = {"event_id": ANCHOR_EVENT, "outlet_id": OUTLET, **overrides}
    return client.post(f"{PREFIX}/exposure/calculate", json=body).json()


def test_zero_feedback_means_adjusted_priority_equals_risk_score_exactly():
    client = _client()
    d = _calculate(client)
    assert d["results"], "expected at least one reached zone"
    for r in d["results"]:
        assert r["adjusted_priority"] == r["risk_score"]
        assert r["adjusted_priority_status"] == "NO_FEEDBACK_YET"


def test_feedback_endpoint_requires_a_real_stored_run():
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/reef-zones/R-01/feedback",
                    json={"run_id": "sim_DOESNOTEXIST00000000000", "outcome": "confirmed"})
    assert r.status_code == 404


def test_feedback_endpoint_requires_the_zone_to_be_in_that_run():
    from api.main import PREFIX

    client = _client()
    d = _calculate(client)
    real_run_id = d["run_id"]
    r = client.post(f"{PREFIX}/reef-zones/R-99-NOT-A-REAL-ZONE/feedback",
                    json={"run_id": real_run_id, "outcome": "confirmed"})
    assert r.status_code == 404


def test_feedback_below_the_minimum_gate_does_not_change_adjusted_priority():
    from api.main import PREFIX
    from models.sampling_feedback import MIN_FEEDBACK_FOR_ADJUSTMENT

    client = _client()
    d = _calculate(client)
    zone_id = d["results"][0]["reef_zone_id"]
    run_id = d["run_id"]

    for _ in range(MIN_FEEDBACK_FOR_ADJUSTMENT - 1):
        r = client.post(f"{PREFIX}/reef-zones/{zone_id}/feedback",
                        json={"run_id": run_id, "outcome": "confirmed"})
        assert r.status_code == 200

    d2 = _calculate(client, rainfall_multiplier=1.01)  # bypass the TTL cache
    zone2 = next(z for z in d2["results"] if z["reef_zone_id"] == zone_id)
    assert zone2["adjusted_priority_status"] == "NO_FEEDBACK_YET"
    assert zone2["adjusted_priority"] == zone2["risk_score"]


def test_feedback_at_the_minimum_gate_applies_and_never_inflates_the_score():
    from api.main import PREFIX
    from models.sampling_feedback import MIN_FEEDBACK_FOR_ADJUSTMENT

    client = _client()
    d = _calculate(client, rainfall_multiplier=1.02)
    zone_id = d["results"][0]["reef_zone_id"]
    run_id = d["run_id"]

    # Mixed outcomes so accuracy is not a trivial 100% or 0%.
    outcomes = ["confirmed"] * (MIN_FEEDBACK_FOR_ADJUSTMENT - 2) + ["not_confirmed"] * 2
    for outcome in outcomes:
        r = client.post(f"{PREFIX}/reef-zones/{zone_id}/feedback",
                        json={"run_id": run_id, "outcome": outcome})
        assert r.status_code == 200

    d2 = _calculate(client, rainfall_multiplier=1.03)
    zone2 = next(z for z in d2["results"] if z["reef_zone_id"] == zone_id)
    assert zone2["adjusted_priority_status"] == "FEEDBACK_APPLIED"
    # Accuracy is a fraction in [0, 1] — adjusted_priority can only move DOWN
    # from risk_score, never inflate it past the model's own output.
    assert zone2["adjusted_priority"] <= zone2["risk_score"]


def test_risk_score_itself_is_never_affected_by_feedback():
    """The formula in exposure/engine.py must stay byte-identical regardless
    of how much feedback accumulates — only adjusted_priority may move."""
    from api.main import PREFIX

    client = _client()
    before = _calculate(client, rainfall_multiplier=1.04)
    zone_id = before["results"][0]["reef_zone_id"]
    run_id = before["run_id"]
    risk_score_before = next(
        z for z in before["results"] if z["reef_zone_id"] == zone_id)["risk_score"]

    for _ in range(10):
        client.post(f"{PREFIX}/reef-zones/{zone_id}/feedback",
                   json={"run_id": run_id, "outcome": "not_confirmed"})

    after = _calculate(client, rainfall_multiplier=1.04)  # same scenario, cache hit or not
    risk_score_after = next(
        z for z in after["results"] if z["reef_zone_id"] == zone_id)["risk_score"]
    assert risk_score_after == risk_score_before
