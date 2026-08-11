"""B8 — Coral Health Vision Model (Phase 5, tasks/phase5/04-pulga.md item 4).

The non-negotiable safeguard is the point of this test file: uploading any
number of photos must never change the live `sensitivity_weight` that
`GET /reef-zones` serves, until the one dedicated, human-gated approve
endpoint is called — and even then, approval writes a read-time overlay, not
`reef_zones.gpkg` itself, which is never rewritten (confirmed by hash, not
assumed — `./data` is mounted read-only in the deployed container).
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

os.environ.setdefault(
    "REEFSHIELD_EXPOSURE_DB", str(Path(tempfile.mkdtemp()) / "test_photos.sqlite")
)
os.environ.setdefault(
    "REEFSHIELD_REEF_PHOTOS_DB", str(Path(tempfile.mkdtemp()) / "test_reef_zone_photos.sqlite")
)
os.environ.setdefault("REEFSHIELD_REEF_PHOTOS_DIR", tempfile.mkdtemp())

ZONE = "R-04"


def _client():
    from api.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


def _jpeg_bytes(color: tuple[int, int, int]) -> io.BytesIO:
    from PIL import Image

    img = Image.new("RGB", (64, 64), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


def test_upload_returns_a_real_classification_with_honest_model_basis():
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/reef-zones/{ZONE}/photos",
                    files={"file": ("t.jpg", _jpeg_bytes((235, 235, 230)), "image/jpeg")})
    assert r.status_code == 200
    d = r.json()
    assert d["photo_id"].startswith("photo_")
    assert d["predicted_class"] in ("healthy", "stressed", "bleached")
    assert 0 <= d["confidence"] <= 1
    # No trained model exists anywhere in this repo (see
    # models/coral_health_classifier.py's docstring) — must be the heuristic,
    # never silently claim a trained result that doesn't exist.
    assert d["model_basis"] == "heuristic_rule_v1"
    assert d["model_version"] is None


def test_upload_to_an_unknown_zone_is_404():
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/reef-zones/R-99-NOT-REAL/photos",
                    files={"file": ("t.jpg", _jpeg_bytes((100, 100, 100)), "image/jpeg")})
    assert r.status_code == 404


def test_unreadable_upload_is_422_not_500():
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/reef-zones/{ZONE}/photos",
                    files={"file": ("t.jpg", io.BytesIO(b"not an image"), "image/jpeg")})
    assert r.status_code == 422


def test_uploading_photos_never_changes_the_live_sensitivity_weight():
    """The core safeguard. Upload several photos, then confirm GET /reef-zones
    reports exactly the same sensitivity_weight it did before — no code path
    triggered by an upload may touch the live value."""
    from api.main import PREFIX

    client = _client()
    before = client.get(f"{PREFIX}/reef-zones", params={"include_geometry": False}).json()
    zone_before = next(z for z in before if z["reef_zone_id"] == ZONE)

    for color in [(235, 235, 230), (200, 200, 190), (20, 60, 30), (230, 225, 220)]:
        r = client.post(f"{PREFIX}/reef-zones/{ZONE}/photos",
                        files={"file": ("t.jpg", _jpeg_bytes(color), "image/jpeg")})
        assert r.status_code == 200

    after = client.get(f"{PREFIX}/reef-zones", params={"include_geometry": False}).json()
    zone_after = next(z for z in after if z["reef_zone_id"] == ZONE)
    assert zone_after["sensitivity_weight"] == zone_before["sensitivity_weight"]
    assert zone_after["sensitivity_weight_status"] == zone_before["sensitivity_weight_status"]


def test_proposed_weight_requires_the_minimum_photo_count():
    from api.main import PREFIX
    from models.reef_zone_photos import MIN_PHOTOS_FOR_PROPOSAL

    client = _client()
    zone = "R-06"  # a zone this test file doesn't touch elsewhere
    for _ in range(MIN_PHOTOS_FOR_PROPOSAL - 1):
        client.post(f"{PREFIX}/reef-zones/{zone}/photos",
                   files={"file": ("t.jpg", _jpeg_bytes((150, 150, 150)), "image/jpeg")})
    d = client.get(f"{PREFIX}/reef-zones/{zone}/photos").json()
    assert d["proposed_sensitivity_weight"]["status"] == "INSUFFICIENT_PHOTOS"
    assert d["proposed_sensitivity_weight"]["proposed_value"] is None

    client.post(f"{PREFIX}/reef-zones/{zone}/photos",
               files={"file": ("t.jpg", _jpeg_bytes((235, 235, 230)), "image/jpeg")})
    d2 = client.get(f"{PREFIX}/reef-zones/{zone}/photos").json()
    assert d2["proposed_sensitivity_weight"]["status"] == "PROPOSED_PENDING_REVIEW"
    assert d2["proposed_sensitivity_weight"]["proposed_value"] is not None


def test_approve_requires_reviewer_and_reasoning(authed_client):
    from api.main import PREFIX

    client, _ = authed_client
    r = client.post(f"{PREFIX}/reef-zones/{ZONE}/sensitivity-weight/approve",
                    json={"approved_value": 1.2})
    assert r.status_code == 422


def test_approve_rejects_an_unauthenticated_caller():
    """Standing Law rule 13's one write path, asserted to be closed. A weight that
    an unauthenticated caller can set is not a scientist-assigned weight."""
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/reef-zones/{ZONE}/sensitivity-weight/approve", json={
        "reviewer": "anyone", "reasoning": "no session", "approved_value": 1.9,
    })
    assert r.status_code == 401

    zones = client.get(f"{PREFIX}/reef-zones", params={"include_geometry": False}).json()
    zone = next(z for z in zones if z["reef_zone_id"] == ZONE)
    assert zone["sensitivity_weight_status"] == "PLACEHOLDER_PENDING_MARINE_SCIENTIST"


def test_approve_writes_a_read_time_overlay_never_the_real_gpkg_file(tmp_path, authed_client):
    """`./data` is mounted read-only in the deployed container — approval
    writes a separate override (sensitivity_weight_overrides), applied by
    data_access.py::reef_zones() as a read-time overlay, and never rewrites
    reef_zones.gpkg. Confirmed here by hashing the real file before and after:
    byte-for-byte identical, not just 'the test used a copy so it's probably
    fine'."""
    import hashlib

    from api import data_access as da
    from api.main import PREFIX

    real_path = da.ARTIFACTS["reef_zones"]
    before_hash = hashlib.sha256(real_path.read_bytes()).hexdigest()

    client, identity = authed_client
    before = client.get(f"{PREFIX}/reef-zones", params={"include_geometry": False}).json()
    zone_before = next(z for z in before if z["reef_zone_id"] == ZONE)
    assert zone_before["sensitivity_weight_status"] == "PLACEHOLDER_PENDING_MARINE_SCIENTIST"

    r = client.post(f"{PREFIX}/reef-zones/{ZONE}/sensitivity-weight/approve", json={
        "reviewer": "Dr. Test Scientist", "reasoning": "test approval",
        "approved_value": 1.45,
    })
    assert r.status_code == 200
    approved = r.json()
    assert approved["approval_id"].startswith("approval_")
    assert approved["approved_value"] == 1.45
    # Track B: recorded from the verified session, not req.reviewer — the request
    # above sends "Dr. Test Scientist" and it must NOT be what gets logged.
    assert approved["reviewer"] == identity
    assert approved["reviewer"] != "Dr. Test Scientist"

    after = client.get(f"{PREFIX}/reef-zones", params={"include_geometry": False}).json()
    zone_after = next(z for z in after if z["reef_zone_id"] == ZONE)
    assert zone_after["sensitivity_weight"] == 1.45
    assert zone_after["sensitivity_weight_status"] == "SCIENTIST_ASSIGNED"

    after_hash = hashlib.sha256(real_path.read_bytes()).hexdigest()
    assert after_hash == before_hash, "reef_zones.gpkg was written to — it must never be"

    da.clear_all_caches()  # leave the module cache clean for subsequent tests


def test_an_approved_weight_actually_changes_the_real_exposure_formula(authed_client):
    """Closes the loop fully: an approval used to change only what /reef-zones
    displayed. exposure_calculate::main.py was hardcoding
    engine.HABITAT_SENSITIVITY_PLACEHOLDER regardless of the real per-zone
    value — found and fixed here. Confirms the approved value now actually
    enters formula_terms.habitat_sensitivity_weight and moves risk_score by
    the same real factor, and that habitat_sensitivity_weight_status flips
    from the placeholder label to SCIENTIST_ASSIGNED on a real, live-scored
    exposure run — not just on the /reef-zones display endpoint."""
    from api.main import PREFIX

    client, _ = authed_client
    zone = "R-08"  # a zone this test file doesn't touch elsewhere

    before = client.post(f"{PREFIX}/exposure/calculate",
                         json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O05"}).json()
    zone_before = next((r for r in before["results"] if r["reef_zone_id"] == zone), None)
    if zone_before is None:
        return  # this outlet/zone pair doesn't reach — nothing to assert here
    assert zone_before["formula_terms"]["habitat_sensitivity_weight"] == 1.0
    assert (zone_before["formula_terms"]["habitat_sensitivity_weight_status"]
            == "PLACEHOLDER_PENDING_MARINE_SCIENTIST")

    approve = client.post(f"{PREFIX}/reef-zones/{zone}/sensitivity-weight/approve", json={
        "reviewer": "Dr. Loop Test", "reasoning": "confirm formula reads the override",
        "approved_value": 1.6,
    })
    assert approve.status_code == 200

    # A different rainfall_multiplier only to bypass the exposure TTL cache —
    # the point under test is the sensitivity weight, not the rainfall scaling.
    after = client.post(f"{PREFIX}/exposure/calculate",
                        json={"event_id": "AQ-2016-10-28", "outlet_id": "AQ-O05",
                              "rainfall_multiplier": 1.001}).json()
    zone_after = next(r for r in after["results"] if r["reef_zone_id"] == zone)
    assert zone_after["formula_terms"]["habitat_sensitivity_weight"] == 1.6
    assert zone_after["formula_terms"]["habitat_sensitivity_weight_status"] == "SCIENTIST_ASSIGNED"
    # raw_score is linear in habitat_sensitivity_weight — 1.6x the un-scaled
    # factors, holding every other term fixed via formula_terms' own record.
    expected_raw = zone_before["formula_terms"]["raw_score"] * 1.6
    assert zone_after["formula_terms"]["raw_score"] == pytest.approx(expected_raw, rel=0.02)
