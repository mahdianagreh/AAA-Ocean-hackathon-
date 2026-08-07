"""B4 — Automated Site-Scoring Agent (Phase 5, tasks/phase5/04-pulga.md item 1).

Scores an arbitrary bounding box against the six-criterion rubric using this
project's own real processed datasets — never `docs/ali/*` (Standing Law rule
11), never a live external fetch (see `models/site_scoring.py`'s docstring).
This tests the honesty boundary directly: a box over Aqaba gets real,
non-fabricated scores; a box with no real data coverage gets
`status="insufficient_data"`, never a guessed number.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

os.environ.setdefault(
    "REEFSHIELD_EXPOSURE_DB", str(Path(tempfile.mkdtemp()) / "test_sites_score.sqlite")
)
os.environ.setdefault(
    "REEFSHIELD_CANDIDATE_SITES_DB",
    str(Path(tempfile.mkdtemp()) / "test_candidate_sites.sqlite"),
)

AQABA_BBOX = [34.90, 29.45, 35.00, 29.55]
FAR_AWAY_BBOX = [-30.0, 0.0, -29.9, 0.1]  # mid-Atlantic — no coverage anywhere


def _client():
    from api.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


def test_scoring_a_real_aqaba_box_returns_real_non_fabricated_scores():
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/sites/score", json={"bbox": AQABA_BBOX})
    assert r.status_code == 200
    d = r.json()
    assert d["site_id"].startswith("site_")
    by_criterion = {c["criterion"]: c for c in d["criteria"]}
    # C1 (drainage), C3 (reef proximity), C5 (development) all have real
    # coverage for an Aqaba box and must be genuinely scored, not fabricated.
    for crit in ("C1", "C3", "C5"):
        assert by_criterion[crit]["status"] == "scored", crit
        assert by_criterion[crit]["score"] is not None
        assert 0 <= by_criterion[crit]["score"] <= 2
        assert by_criterion[crit]["evidence"], f"{crit} scored with no evidence"


def test_c6_is_always_insufficient_data_even_for_aqaba():
    """No geospatial dataset can characterise the ABSENCE of other monitoring
    infrastructure — this must be honest everywhere, not just far away."""
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/sites/score", json={"bbox": AQABA_BBOX}).json()
    c6 = next(c for c in r["criteria"] if c["criterion"] == "C6")
    assert c6["status"] == "insufficient_data"
    assert c6["score"] is None


def test_a_box_with_no_real_coverage_reports_insufficient_data_not_a_guess():
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/sites/score", json={"bbox": FAR_AWAY_BBOX})
    assert r.status_code == 200
    d = r.json()
    by_criterion = {c["criterion"]: c for c in d["criteria"]}
    # C1 (OSM drainage), C2 (rainfall climatology), C4 (bathymetry), C5 (OSM
    # buildings) have zero real coverage anywhere near this box.
    for crit in ("C1", "C2", "C4", "C5"):
        assert by_criterion[crit]["status"] == "insufficient_data", crit
        assert by_criterion[crit]["score"] is None, crit
        assert by_criterion[crit]["evidence"], (
            f"{crit} reported insufficient_data with no cited reason"
        )


def test_every_score_carries_a_real_citation_in_the_ask_shape():
    """Reuses /ask's Citation shape verbatim — source_file, section, excerpt,
    score. Never a second citation format."""
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/sites/score", json={"bbox": AQABA_BBOX}).json()
    for c in r["criteria"]:
        for e in c["evidence"]:
            assert set(e) == {"source_file", "section", "excerpt", "score"}
            assert e["source_file"]
            assert e["excerpt"]


def test_the_one_site_caveat_is_always_present_regardless_of_box():
    from api.main import PREFIX

    client = _client()
    for bbox in (AQABA_BBOX, FAR_AWAY_BBOX):
        r = client.post(f"{PREFIX}/sites/score", json={"bbox": bbox}).json()
        assert any("exactly one site" in c["message"] for c in r["caveats"]), bbox


def test_narrative_is_deterministic_templating_not_a_generative_call():
    """Same question asked twice must produce byte-identical narrative text —
    there is no generative model anywhere in this path to introduce variance."""
    from api.main import PREFIX

    client = _client()
    r1 = client.post(f"{PREFIX}/sites/score", json={"bbox": AQABA_BBOX}).json()
    r2 = client.post(f"{PREFIX}/sites/score", json={"bbox": AQABA_BBOX}).json()
    assert r1["narrative"] == r2["narrative"]


def test_scored_site_is_persisted_and_retrievable():
    from api.main import PREFIX

    client = _client()
    posted = client.post(f"{PREFIX}/sites/score",
                         json={"bbox": AQABA_BBOX, "site_name": "Test Reach"}).json()
    fetched = client.get(f"{PREFIX}/sites/{posted['site_id']}")
    assert fetched.status_code == 200
    got = fetched.json()
    assert got["site_id"] == posted["site_id"]
    assert got["site_name"] == "Test Reach"
    assert got["criteria"] == posted["criteria"]


def test_unknown_site_id_is_404():
    from api.main import PREFIX

    client = _client()
    r = client.get(f"{PREFIX}/sites/site_DOESNOTEXIST00000000000")
    assert r.status_code == 404


def test_bbox_ordering_and_bounds_validation():
    """bbox is (west, south, east, north), EPSG:4326 — matches
    config.spatial.BBox.wsen exactly, never a different ordering."""
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/sites/score", json={"bbox": [34.90, 29.45, 35.00, 29.55]})
    assert r.status_code == 200
    assert tuple(r.json()["bbox"]) == (34.90, 29.45, 35.00, 29.55)
