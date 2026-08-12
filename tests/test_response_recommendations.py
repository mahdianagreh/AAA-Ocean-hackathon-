"""Phase 9 — response-recommendation swarm (tasks/phase9/00-phase9-plan.md).

No test here calls the real Ollama daemon or the real BM25 corpus: `run_round`/
`run_judge` take an injectable `retrieve`, and `ollama_client.chat_json`/
`chat_json_parallel` are monkeypatched to deterministic fakes. That keeps this
suite green on a machine with no Ollama installed — consistent with the rest of
this project's "missing external resource -> skip or fake, never a flaky test"
discipline. The real Ollama round-trip was smoke-tested manually while building
this (measured latencies match tasks/phase9/00-phase9-plan.md §4 within noise).
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

os.environ.setdefault(
    "REEFSHIELD_RECOMMENDATIONS_DB",
    str(Path(tempfile.mkdtemp()) / "test_recommendations.sqlite"),
)
os.environ.setdefault(
    "REEFSHIELD_EXPOSURE_DB", str(Path(tempfile.mkdtemp()) / "test_exposure.sqlite")
)

ANCHOR_EVENT = "AQ-2016-10-28"


def _sample_run() -> dict:
    return {
        "run_id": "sim_TESTRUN00000000000000001",
        "event_id": ANCHOR_EVENT,
        "outlet_id": "AQ-O04",
        "created_at": "2026-08-11T00:00:00+00:00",
        "results": [
            {
                "reef_zone_id": "R-03",
                "risk_score": 92.0,
                "risk_level": "critical",
                "max_exposure_probability": 0.88,
                "zone_fraction_affected": 0.5,
                "arrival_window_hours": (8.0, 12.0),
                "confidence": 0.7,
                "formula_terms": {
                    "sediment_class": "Extreme",
                    "relative_sediment_intensity": 0.95,
                    "transmission_loss": 0.2,
                },
            },
            {
                "reef_zone_id": "R-01",
                "risk_score": 15.0,
                "risk_level": "minimal",
                "max_exposure_probability": 0.05,
                "zone_fraction_affected": 0.01,
                "arrival_window_hours": None,
                "confidence": 0.9,
                "formula_terms": {"sediment_class": None},
            },
        ],
    }


# ------------------------------------------------------------------- severity brief

def test_severity_brief_max_risk_is_the_worst_zone_not_the_first():
    from models.severity_brief import build_severity_brief

    run = _sample_run()
    brief = build_severity_brief(
        run,
        zones_meta={"R-03": {"zone_name": "North Reef", "marine_park_overlap_pct": 78.0},
                    "R-01": {"zone_name": "South Reef"}},
        outlets_meta={"AQ-O04": {"source_caveat": "enclosed harbour basin"}},
        mooring=None,
    )
    assert brief["max_risk_level"] == "critical"
    assert brief["outlet_caveat"] == "enclosed harbour basin"
    assert brief["zones"][0]["reef_zone_id"] == "R-03"  # sorted by risk_score desc


def test_severity_brief_never_invents_tonnage_for_a_non_anchor_event():
    from models.severity_brief import build_severity_brief

    run = _sample_run()
    run["event_id"] = "AQ-2013-02-XX"  # not the demo event, no mooring record
    brief = build_severity_brief(run, zones_meta={}, outlets_meta={}, mooring=None)
    assert brief["sediment_mass"]["sediment_mass_total_t"] is None
    assert "No mooring record" in brief["sediment_mass"]["note"]


def test_severity_brief_reports_real_mooring_tonnage_when_present():
    from models.severity_brief import build_severity_brief

    run = _sample_run()
    mooring = {"magnitude": {"sediment_mass_total_t": 24400}, "source_citation": "Kalman 2025"}
    brief = build_severity_brief(run, zones_meta={}, outlets_meta={}, mooring=mooring)
    assert brief["sediment_mass"]["sediment_mass_total_t"] == 24400
    assert brief["sediment_mass"]["source"] == "Kalman 2025"


# ------------------------------------------------------------------------------ store

def test_store_round_trips_a_full_recommendation():
    from models import response_recommendations as rr

    rec = rr.create_recommendation("sim_x", ANCHOR_EVENT, "auto", {"k": "v"}, "gemma4:31b")
    assert rec["status"] == "running"

    rr.add_turn(rec["id"], 1, "aseza", "close the beach", ["chunk1"])
    rr.add_verdict(rec["id"], "approved", "well grounded", ["chunk1"])
    rr.add_gap(rec["id"], "no info on tide state", "low")

    final = rr.update_status(
        rec["id"], "finalized", final_recommendation="close the beach",
        rounds_used=1, converged=True, complete=True,
    )
    assert final["status"] == "finalized"
    assert final["completed_at"] is not None
    assert len(final["turns"]) == 1 and final["turns"][0]["agent_role"] == "aseza"
    assert len(final["verdicts"]) == 1
    assert len(final["gaps"]) == 1


def test_store_rejects_human_override_with_no_user():
    from models import response_recommendations as rr

    try:
        rr.create_recommendation("sim_x", ANCHOR_EVENT, "human_override", {}, "gemma4:31b")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_store_status_never_writes_an_unrecognised_value():
    from models import response_recommendations as rr

    rec = rr.create_recommendation("sim_y", ANCHOR_EVENT, "auto", {}, "gemma4:31b")
    try:
        rr.update_status(rec["id"], "not_a_real_status")
        assert False, "expected ValueError"
    except ValueError:
        pass


# ------------------------------------------------------------------ orchestration

def test_valid_evidence_drops_invented_chunk_ids():
    from models.recommendation_swarm import _valid_evidence

    provided = {"docs/a.md#1#0", "docs/b.md#1#1"}
    cited = ["docs/a.md#1#0", "brief.zones[0].risk_level", "docs/made-up.md#9#9"]
    assert _valid_evidence(cited, provided) == ["docs/a.md#1#0", "brief.zones[0].risk_level"]


def test_rounds_converged_requires_every_role_unchanged():
    from models.recommendation_swarm import rounds_converged

    prev = [{"agent_role": "aseza", "content": "Close the north beach for 48 hours"},
            {"agent_role": "tourism", "content": "Notify dive operators immediately"}]
    same = [{"agent_role": "aseza", "content": "Close the north beach for 48h"},
            {"agent_role": "tourism", "content": "Notify dive operators immediately"}]
    changed = [{"agent_role": "aseza", "content": "Close the north beach for 48h"},
               {"agent_role": "tourism", "content": "Deploy a new mooring buoy instead"}]
    assert rounds_converged(prev, same) is True
    assert rounds_converged(prev, changed) is False


def test_pick_final_candidate_picks_the_largest_cluster():
    from models.recommendation_swarm import pick_final_candidate

    turns = [
        {"agent_role": "aseza", "content": "Close the north reef dive sites for 48 hours"},
        {"agent_role": "marine_science", "content": "Close the north reef dive sites for 48h"},
        {"agent_role": "tourism", "content": "Deploy an alternate mooring buoy this week"},
    ]
    text, contributors = pick_final_candidate(turns)
    assert set(contributors) == {"aseza", "marine_science"}
    assert "north reef" in text.lower()


def test_pick_final_candidate_with_only_refusals_says_so():
    from models.recommendation_swarm import pick_final_candidate

    turns = [{"agent_role": "aseza", "content": "[abstained — no groundable action this round]"}]
    text, contributors = pick_final_candidate(turns)
    assert contributors == []
    assert "No specialist" in text


def test_run_swarm_end_to_end_with_a_fake_llm(monkeypatch):
    """Injects a fake retrieve() and monkeypatches ollama_client so the full
    orchestration path (rounds -> convergence -> judge -> gaps -> finalized) runs
    with no network at all, and asserts on the shape it leaves in the store."""
    from models import ollama_client as oc
    from models import recommendation_swarm as sw
    from models import response_recommendations as rr

    def fake_retrieve(query, k=5):
        return [{"chunk_id": "docs/fake.md#1#0", "source_file": "docs/fake.md",
                 "section": "1", "excerpt": "fake grounding text", "score": 1.0}]

    def fake_chat_json_parallel(calls, think=False, model=oc.MODEL):
        return [{"data": {"proposal": "Close the affected reef zones for 48 hours",
                          "evidence_cited": ["docs/fake.md#1#0"], "abstained": False},
                "thinking": None} for _ in calls]

    def fake_chat_json(messages, think=False, model=oc.MODEL):
        # The judge and the gaps agent both call chat_json (not the parallel one).
        joined = " ".join(m["content"] for m in messages)
        if "judge" in messages[0]["content"].lower():
            return {"data": {"verdict": "approved", "reasoning": "grounded",
                             "evidence_cited": ["docs/fake.md#1#0"]}, "thinking": None}
        return {"data": {"gaps": [{"description": "tide state unknown", "severity": "low"}]},
                "thinking": None}

    monkeypatch.setattr(oc, "chat_json_parallel", fake_chat_json_parallel)
    monkeypatch.setattr(oc, "chat_json", fake_chat_json)

    brief = {"max_risk_level": "critical", "zones": [{"reef_zone_id": "R-03"}]}
    rec = rr.create_recommendation("sim_z", ANCHOR_EVENT, "auto", brief, oc.MODEL)

    real_run_round, real_run_judge = sw.run_round, sw.run_judge
    monkeypatch.setattr(
        sw, "run_round",
        lambda brief, transcript, round_num: real_run_round(
            brief, transcript, round_num, retrieve=fake_retrieve
        ),
    )
    monkeypatch.setattr(
        sw, "run_judge",
        lambda brief, candidate, transcript: real_run_judge(
            brief, candidate, transcript, retrieve=fake_retrieve
        ),
    )

    final = sw.run_swarm(rec["id"], brief, store=rr)

    assert final["status"] == "finalized"
    assert final["completed_at"] is not None
    # Converges immediately: the fake always returns the same proposal, so round 2
    # matches round 1 and the loop stops there rather than spending a 3rd round.
    assert final["rounds_used"] == 2
    assert final["converged"] is True
    assert "Close the affected reef zones" in final["final_recommendation"]
    assert len(final["verdicts"]) == 1
    assert final["verdicts"][0]["verdict"] == "approved"
    assert len(final["gaps"]) == 1
    assert final["gaps"][0]["gap_description"] == "tide state unknown"
    # 5 roles x 2 rounds, every turn persisted.
    assert len(final["turns"]) == 10


# --------------------------------------------------------------- trigger endpoint

def _client():
    from api.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


def _store_run(run_id: str, results: list[dict]) -> None:
    """Writes straight to exposure.store — bypasses the real particle engine so
    the test controls risk_level exactly, same shortcut `test_reef_zone_photos.py`
    style tests would use for a fixed scenario."""
    from exposure import store

    store.save_run(
        run_id=run_id, event_id=ANCHOR_EVENT, outlet_id="AQ-O04",
        results=results, model_versions={"exposure_engine": "test"},
    )


def _zone_result(zone_id: str, risk_level: str, risk_score: float) -> dict:
    return {
        "reef_zone_id": zone_id, "risk_score": risk_score, "risk_level": risk_level,
        "max_exposure_probability": 0.5, "zone_fraction_affected": 0.1,
        "arrival_window_hours": None, "confidence": 0.5,
        "formula_terms": {"sediment_class": "Low"},
    }


def _noop_background(monkeypatch):
    """The trigger endpoint's background task runs synchronously inside
    TestClient's request/response cycle — mock it so these tests never touch the
    real Ollama daemon."""
    import api.main as main

    monkeypatch.setattr(main, "_run_swarm_background", lambda rec_id, brief: None)


def test_trigger_rejects_an_unknown_run(monkeypatch):
    from api.main import PREFIX

    _noop_background(monkeypatch)
    client = _client()
    r = client.post(f"{PREFIX}/recommendations/trigger",
                    json={"run_id": "sim_DOESNOTEXIST00000000000"})
    assert r.status_code == 404


def test_trigger_below_gate_without_override_is_refused(monkeypatch):
    from api.main import PREFIX

    _noop_background(monkeypatch)
    client = _client()
    _store_run("sim_LOWRISK0000000000000001", [_zone_result("R-01", "moderate", 45.0)])
    r = client.post(f"{PREFIX}/recommendations/trigger",
                    json={"run_id": "sim_LOWRISK0000000000000001"})
    assert r.status_code == 409


def test_trigger_at_or_above_gate_runs_automatically_with_no_auth(monkeypatch):
    from api.main import PREFIX

    _noop_background(monkeypatch)
    client = _client()
    _store_run("sim_HIGHRISK000000000000001", [_zone_result("R-01", "high", 65.0)])
    r = client.post(f"{PREFIX}/recommendations/trigger",
                    json={"run_id": "sim_HIGHRISK000000000000001"})
    assert r.status_code == 200
    body = r.json()
    assert body["triggered_by"] == "auto"
    assert body["status"] == "running"
    assert body["triggered_by_user"] is None


def test_trigger_override_without_auth_is_rejected(monkeypatch):
    from api.main import PREFIX

    _noop_background(monkeypatch)
    client = _client()
    _store_run("sim_OVERRIDENOAUTH00000001", [_zone_result("R-01", "moderate", 45.0)])
    r = client.post(f"{PREFIX}/recommendations/trigger",
                    json={"run_id": "sim_OVERRIDENOAUTH00000001",
                          "min_risk_level_override": "low"})
    assert r.status_code == 401


def test_trigger_override_with_auth_logs_the_user(monkeypatch):
    from api.main import PREFIX, app
    from api import auth

    _noop_background(monkeypatch)
    app.dependency_overrides[auth.get_current_user_optional] = (
        lambda: auth.CurrentUser(sub="user-123", email="ops@example.com")
    )
    try:
        client = _client()
        _store_run("sim_OVERRIDEAUTH000000001", [_zone_result("R-01", "moderate", 45.0)])
        r = client.post(f"{PREFIX}/recommendations/trigger",
                        json={"run_id": "sim_OVERRIDEAUTH000000001",
                              "min_risk_level_override": "low"})
        assert r.status_code == 200
        body = r.json()
        assert body["triggered_by"] == "human_override"
        assert body["triggered_by_user"] == "user-123"
    finally:
        app.dependency_overrides.pop(auth.get_current_user_optional, None)


def test_get_recommendation_404_then_200(monkeypatch):
    from api.main import PREFIX

    _noop_background(monkeypatch)
    client = _client()
    r = client.get(f"{PREFIX}/recommendations/rec_DOESNOTEXIST0000000000001")
    assert r.status_code == 404

    _store_run("sim_GETTEST00000000000001", [_zone_result("R-01", "critical", 90.0)])
    created = client.post(f"{PREFIX}/recommendations/trigger",
                          json={"run_id": "sim_GETTEST00000000000001"}).json()
    r2 = client.get(f"{PREFIX}/recommendations/{created['id']}")
    assert r2.status_code == 200
    assert r2.json()["id"] == created["id"]
