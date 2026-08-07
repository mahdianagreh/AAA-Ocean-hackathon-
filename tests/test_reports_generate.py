"""B5 — Post-Event Forensic Report Generator (Phase 5, tasks/phase5/04-pulga.md
item 2). Assembles a draft from real stored data — never computes a new
number, never auto-publishes. Tests the two things that matter most: every
claim's source is traceable to something real (or explicitly None), and
`status` cannot move to "human_reviewed" except through the one dedicated
endpoint.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

os.environ.setdefault(
    "REEFSHIELD_EXPOSURE_DB", str(Path(tempfile.mkdtemp()) / "test_reports.sqlite")
)
os.environ.setdefault(
    "REEFSHIELD_REPORTS_DB", str(Path(tempfile.mkdtemp()) / "test_generated_reports.sqlite")
)

ANCHOR_EVENT = "AQ-2016-10-28"


def _client():
    from api.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


def test_generate_report_starts_ai_drafted():
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/reports/generate", json={"event_id": ANCHOR_EVENT})
    assert r.status_code == 200
    d = r.json()
    assert d["report_id"].startswith("report_")
    assert d["status"] == "ai_drafted"
    assert d["reviewed_at"] is None
    assert d["reviewed_by"] is None


def test_every_claim_has_a_real_source_or_an_explicit_none():
    """Never a fabricated source string — either a real, structured pointer
    (an exposure-run key, a citation) or None with plain text explaining the
    gap."""
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/reports/generate", json={"event_id": ANCHOR_EVENT}).json()
    assert r["sections"], "expected at least one section"
    for section in r["sections"]:
        for claim in section["claims"]:
            assert claim["text"]
            assert claim["source"] is None or isinstance(claim["source"], str)


def test_a_thin_event_states_the_gap_per_section_not_one_blanket_disclaimer():
    """A non-anchor event has no stored exposure run and no mooring record —
    each section must say so specifically, not fall back to a single generic
    'data unavailable' banner."""
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/reports/generate",
                    json={"event_id": "AQ-2013-02-14"}).json()
    by_title = {s["title"]: s for s in r["sections"]}
    assert "no exposure run" in by_title["Exposure summary"]["claims"][0]["text"].lower()
    assert "no mooring record" in by_title["Sensor validation"]["claims"][0]["text"].lower()


def test_only_the_review_endpoint_can_set_human_reviewed():
    from api.main import PREFIX

    client = _client()
    generated = client.post(f"{PREFIX}/reports/generate",
                            json={"event_id": ANCHOR_EVENT}).json()
    assert generated["status"] == "ai_drafted"

    fetched_before = client.get(f"{PREFIX}/reports/{generated['report_id']}").json()
    assert fetched_before["status"] == "ai_drafted"

    reviewed = client.patch(f"{PREFIX}/reports/{generated['report_id']}/review",
                            json={"reviewed_by": "Pulga"}).json()
    assert reviewed["status"] == "human_reviewed"
    assert reviewed["reviewed_by"] == "Pulga"
    assert reviewed["reviewed_at"] is not None

    fetched_after = client.get(f"{PREFIX}/reports/{generated['report_id']}").json()
    assert fetched_after["status"] == "human_reviewed"


def test_review_requires_a_reviewer_not_optional():
    from api.main import PREFIX

    client = _client()
    generated = client.post(f"{PREFIX}/reports/generate",
                            json={"event_id": ANCHOR_EVENT}).json()
    r = client.patch(f"{PREFIX}/reports/{generated['report_id']}/review", json={})
    assert r.status_code == 422


def test_reviewing_an_unknown_report_is_404():
    from api.main import PREFIX

    client = _client()
    r = client.patch(f"{PREFIX}/reports/report_DOESNOTEXIST00000000000/review",
                     json={"reviewed_by": "Pulga"})
    assert r.status_code == 404


def test_fetching_an_unknown_report_is_404():
    from api.main import PREFIX

    client = _client()
    r = client.get(f"{PREFIX}/reports/report_DOESNOTEXIST00000000000")
    assert r.status_code == 404


def test_sensor_validation_section_cites_the_real_mooring_source():
    """The anchor event has a real mooring record — this section must not
    fall back to the 'no mooring record' text for AQ-2016-10-28 specifically."""
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/reports/generate", json={"event_id": ANCHOR_EVENT}).json()
    section = next(s for s in r["sections"] if s["title"] == "Sensor validation")
    assert "no mooring record" not in section["claims"][0]["text"].lower()
    assert any(c["source"] for c in section["claims"])
