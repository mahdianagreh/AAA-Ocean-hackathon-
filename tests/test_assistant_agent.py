"""Assistant tool-calling loop (`models/assistant_agent.py`), fully mocked —
`ollama_client.chat_json` is monkeypatched to a canned sequence of responses and
`dispatch` is a fake standing in for `main.py`'s real `_assistant_dispatch`, same
mocking style as `test_response_recommendations.py`'s swarm test. No network, no
live Ollama needed.
"""

from __future__ import annotations


def fake_chat_json_sequence(*responses):
    it = iter(responses)

    def fake(messages, think=False, model=None):
        return next(it)

    return fake


def make_dispatch(alert_score: float = 92.0):
    zones = {"R-03": {"reef_zone_id": "R-03", "zone_name": "Tourist Camp"}}

    def dispatch(tool: str, args: dict):
        if tool == "get_alerts":
            return {"alerts": [{
                "reef_zone_id": "R-03",
                "zone_name": "Tourist Camp",
                "risk_level": "critical",
                "risk_score": alert_score,
                "arrival_window_hours": [8.0, 12.0],
            }]}
        if tool == "get_reef_zone":
            return zones.get(args.get("zone_id"))
        raise KeyError(f"unknown tool {tool!r}")

    return dispatch


def test_tool_dispatch_feeds_real_value_into_answer(monkeypatch):
    from models import ollama_client as oc
    from models import assistant_agent as agent

    monkeypatch.setattr(oc, "chat_json", fake_chat_json_sequence(
        {"data": {"action": "call_tool", "tool": "get_alerts", "args": {}}, "thinking": None},
        {"data": {"action": "answer", "text": "R-03 is at risk_score 92.0, critical.",
                  "suggested_route": None}, "thinking": None},
    ))

    result = agent.run_assistant_turn(
        "what's the alert for R-03?", [], "en", make_dispatch(alert_score=92.0)
    )

    assert result["tools_used"] == [{"tool": "get_alerts", "args": {}, "summary": "1 alert(s)"}]
    assert "92.0" in result["text"]
    assert result["caveats"] == []


def test_fabricated_number_gets_a_caveat_not_a_silent_pass(monkeypatch):
    from models import ollama_client as oc
    from models import assistant_agent as agent

    monkeypatch.setattr(oc, "chat_json", fake_chat_json_sequence(
        {"data": {"action": "call_tool", "tool": "get_alerts", "args": {}}, "thinking": None},
        {"data": {"action": "answer", "text": "The risk score is 999.",
                  "suggested_route": None}, "thinking": None},
        # The corrective retry still gets it wrong — must degrade to a caveat,
        # not ship a fabricated number silently.
        {"data": {"action": "answer", "text": "The risk score is still 999.",
                  "suggested_route": None}, "thinking": None},
    ))

    result = agent.run_assistant_turn(
        "what's the risk score?", [], "en", make_dispatch(alert_score=92.0)
    )

    assert result["caveats"], "an unverifiable number must produce a caveat"
    assert result["caveats"][0]["severity"] == "warning"


def test_fabricated_number_is_fixed_by_a_successful_retry(monkeypatch):
    from models import ollama_client as oc
    from models import assistant_agent as agent

    monkeypatch.setattr(oc, "chat_json", fake_chat_json_sequence(
        {"data": {"action": "call_tool", "tool": "get_alerts", "args": {}}, "thinking": None},
        {"data": {"action": "answer", "text": "The risk score is 999.",
                  "suggested_route": None}, "thinking": None},
        # This time the retry gets it right — no caveat needed.
        {"data": {"action": "answer", "text": "The risk score is 92.0.",
                  "suggested_route": None}, "thinking": None},
    ))

    result = agent.run_assistant_turn(
        "what's the risk score?", [], "en", make_dispatch(alert_score=92.0)
    )

    assert result["caveats"] == []
    assert "92.0" in result["text"]


def test_whitelisted_route_survives(monkeypatch):
    from models import ollama_client as oc
    from models import assistant_agent as agent

    monkeypatch.setattr(oc, "chat_json", fake_chat_json_sequence(
        {"data": {"action": "answer", "text": "Check the alerts page.",
                  "suggested_route": "/alerts"}, "thinking": None},
    ))
    result = agent.run_assistant_turn("where do I see alerts", [], "en", make_dispatch())
    assert result["suggested_route"] == "/alerts"


def test_hallucinated_route_is_dropped_not_surfaced(monkeypatch):
    from models import ollama_client as oc
    from models import assistant_agent as agent

    monkeypatch.setattr(oc, "chat_json", fake_chat_json_sequence(
        {"data": {"action": "answer", "text": "Go check it out.",
                  "suggested_route": "/totally-made-up-page"}, "thinking": None},
    ))
    result = agent.run_assistant_turn("where do I go", [], "en", make_dispatch())
    assert result["suggested_route"] is None


def test_dynamic_route_with_real_zone_id_survives(monkeypatch):
    from models import ollama_client as oc
    from models import assistant_agent as agent

    monkeypatch.setattr(oc, "chat_json", fake_chat_json_sequence(
        {"data": {"action": "answer", "text": "That zone has its own page.",
                  "suggested_route": "/reef-zones/R-03"}, "thinking": None},
    ))
    result = agent.run_assistant_turn("tell me about R-03", [], "en", make_dispatch())
    assert result["suggested_route"] == "/reef-zones/R-03"


def test_dynamic_route_with_fake_zone_id_is_dropped(monkeypatch):
    from models import ollama_client as oc
    from models import assistant_agent as agent

    monkeypatch.setattr(oc, "chat_json", fake_chat_json_sequence(
        {"data": {"action": "answer", "text": "That zone has its own page.",
                  "suggested_route": "/reef-zones/R-99"}, "thinking": None},
    ))
    result = agent.run_assistant_turn("tell me about R-99", [], "en", make_dispatch())
    assert result["suggested_route"] is None


def test_unknown_tool_name_does_not_crash_the_loop(monkeypatch):
    from models import ollama_client as oc
    from models import assistant_agent as agent

    monkeypatch.setattr(oc, "chat_json", fake_chat_json_sequence(
        {"data": {"action": "call_tool", "tool": "totally_fake_tool", "args": {}}, "thinking": None},
        {"data": {"action": "answer", "text": "I couldn't look that up.",
                  "suggested_route": None}, "thinking": None},
    ))

    result = agent.run_assistant_turn("do something weird", [], "en", make_dispatch())

    assert result["text"] == "I couldn't look that up."
    assert "fail" in result["tools_used"][0]["summary"].lower()
