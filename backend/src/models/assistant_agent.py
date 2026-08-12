"""AI Assistant tool-calling loop — gemma4:31b via `ollama_client.chat_json`.

Reuses the exact structured-JSON-output mechanism the Phase 9 swarm already
proved reliable with this model (`recommendation_swarm.py`), rather than
Ollama's native `tools` API — nothing in this codebase has ever sent that
parameter, and Gemma's chat-template support for it is unproven here. The model
is told the tool catalog as prompt text and must reply with one of two JSON
shapes; this loop parses that shape itself, the same way the swarm parses its
own agents' `{"proposal": ..., "evidence_cited": [...]}` shape.

NUMBER FIDELITY. This is the first module in the codebase that lets a model
generate prose (`rag/answer.py::generate_with_llm` stays an unimplemented stub —
CLAUDE.md's "never computes a number" rule is about that path, not this one).
The same discipline applies here, adapted for a conversational endpoint: every
numeric token in the model's final answer must appear, verbatim (formatting
variance allowed), among the tool results actually returned this turn. A
failure gets one corrective retry, then ships anyway with an attached caveat —
never a silent pass, and never a hard 500 the way `/explain` would for a
machine-checked, non-conversational response.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from models import assistant_tools as tools
from models import ollama_client as oc

MAX_TOOL_CALLS = 3
MAX_HISTORY_TURNS = 6

# Excludes digits embedded in an id/code (AQ-2016-10-28, R-03, sim_..._0001) via
# the lookaround, so a date or run id in the answer never trips the fidelity
# check — those aren't "a number", they're an opaque identifier.
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_-])-?\d[\d,]*\.?\d*(?![A-Za-z0-9_-])")


def _system_prompt(language: str) -> str:
    lang_line = "Answer in Arabic." if language == "ar" else "Answer in English."
    return (
        "You are the assistant for ReefShield Aqaba, a wadi-to-reef sediment "
        "forecasting system. " + lang_line + "\n\n"
        "You can call tools to look up this system's real, current data. Never "
        "state a number about this system's data unless it came from a tool "
        "result you actually received this conversation — if you don't have "
        "it, say so rather than guessing.\n\n"
        "Available tools:\n" + tools.tool_catalog_prompt() + "\n\n"
        'Reply with EXACTLY ONE JSON object, one of these two shapes:\n'
        '  {"action": "call_tool", "tool": "<name>", "args": {...}}\n'
        '  {"action": "answer", "text": "...", "suggested_route": "<path>" or null}\n\n'
        "Only set suggested_route when it points somewhere useful for what was "
        "just discussed, and only to one of:\n" + tools.route_whitelist_prompt() + "\n"
        "If nothing fits, use null — never invent a path."
    )


def _normalise_number(raw: str) -> str:
    s = raw.replace(",", "")
    if "." in s:
        s = s.rstrip("0").rstrip(".") or "0"
    return s


def _flatten_numbers(obj) -> set[str]:
    found: set[str] = set()
    if isinstance(obj, bool):
        return found
    if isinstance(obj, (int, float)):
        found.add(_normalise_number(str(obj)))
    elif isinstance(obj, str):
        # search_docs results are prose (a doc excerpt) — a number the model
        # quotes FROM that text (e.g. "58 storm events") is grounded even
        # though it's a substring, not a JSON numeric leaf. Found live: "12
        # real systems, 58 usable storm events" is a real quote from a
        # retrieved excerpt and was wrongly flagged before this scanned
        # strings too.
        found |= {_normalise_number(tok) for tok in _NUMBER_RE.findall(obj)}
    elif isinstance(obj, dict):
        for v in obj.values():
            found |= _flatten_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found |= _flatten_numbers(v)
    return found


def _numbers_verified(text: str, known: set[str]) -> bool:
    for tok in _NUMBER_RE.findall(text):
        norm = _normalise_number(tok)
        # Single digits are usually a count the model derived itself (e.g. "3
        # zones"), not a fact it needs to have retrieved verbatim.
        if len(norm.lstrip("-")) <= 1:
            continue
        if norm not in known:
            return False
    return True


def _summarise(tool_name: str, result: dict) -> str:
    if isinstance(result, dict) and "error" in result:
        return result["error"]
    if tool_name == "get_alerts":
        return f"{len(result.get('alerts', []))} alert(s)"
    if tool_name == "get_reef_zone":
        return result.get("zone_name", result.get("reef_zone_id", "not found")) if result else "not found"
    if tool_name == "get_event":
        return result.get("event_id", "not found") if result else "not found"
    if tool_name == "get_exposure_run":
        return result.get("run_id", "not found") if result else "not found"
    if tool_name == "get_data_sources":
        return f"{len(result)} source(s)"
    if tool_name == "search_docs":
        return f"{len(result.get('chunks', []))} document excerpt(s)"
    return "done"


def _fallback_text(language: str) -> str:
    return (
        "عذرًا، لم أستطع تكوين إجابة لهذا السؤال."
        if language == "ar"
        else "Sorry, I couldn't put together an answer to that."
    )


def _validate_route(path, dispatch: Callable[[str, dict], dict]) -> str | None:
    if not path or not isinstance(path, str):
        return None
    if path in tools.ROUTE_WHITELIST:
        return path
    m = re.fullmatch(r"/reef-zones/([\w-]+)", path)
    if m:
        try:
            zone = dispatch("get_reef_zone", {"zone_id": m.group(1)})
        except Exception:  # noqa: BLE001 — an unresolvable id is just "no suggestion"
            return None
        if zone:
            return path
    return None


def _safe_chat_json(messages: list[dict]):
    """None on malformed JSON (a refusal to guess, per `chat_json`'s own
    contract) — the caller treats that as an empty answer, not a crash."""
    try:
        return oc.chat_json(messages, think=False)
    except ValueError:
        return None


def run_assistant_turn(
    message: str,
    history: list[dict],
    language: str,
    dispatch: Callable[[str, dict], dict],
) -> dict:
    """`dispatch(tool_name, args) -> dict` is `main.py`'s closure over the real
    `da.*`/`store.*`/`rag_index.retrieve` calls — this module never imports
    those itself (see module docstring)."""
    messages: list[dict] = [{"role": "system", "content": _system_prompt(language)}]
    for turn in history[-MAX_HISTORY_TURNS:]:
        messages.append({"role": turn["role"], "content": turn["text"]})
    messages.append({"role": "user", "content": message})

    tools_used: list[dict] = []
    citations: list[dict] = []
    all_tool_results: list[dict] = []
    seen_chunk_ids: set[str] = set()

    def _run_tool(tool_name: str, args: dict) -> dict:
        try:
            result = dispatch(tool_name, args)
        except Exception as exc:  # noqa: BLE001 — fed back as an honest failure, not a crash
            return {"error": f"{tool_name} failed: {exc}"}
        if tool_name == "search_docs":
            for chunk in result.get("chunks", []):
                cid = chunk.get("chunk_id")
                if cid and cid not in seen_chunk_ids:
                    seen_chunk_ids.add(cid)
                    citations.append({
                        "source_file": chunk["source_file"],
                        "section": chunk["section"],
                        "excerpt": chunk["excerpt"],
                        "score": chunk.get("score"),
                    })
        return result

    for round_ in range(MAX_TOOL_CALLS + 1):
        force_answer = round_ == MAX_TOOL_CALLS
        turn_messages = list(messages)
        if force_answer:
            turn_messages.append({
                "role": "user",
                "content": "No more tool calls are available. Answer now with what you have.",
            })

        reply = _safe_chat_json(turn_messages)
        data = reply["data"] if reply and isinstance(reply["data"], dict) else {}
        action = data.get("action")

        if action == "call_tool" and not force_answer:
            tool_name = str(data.get("tool", ""))
            args = data.get("args") or {}
            if not isinstance(args, dict):
                args = {}
            result = _run_tool(tool_name, args)
            all_tool_results.append(result)
            tools_used.append({
                "tool": tool_name,
                "args": args,
                "summary": _summarise(tool_name, result),
            })
            messages.append({"role": "assistant", "content": json.dumps(data)})
            messages.append({
                "role": "user",
                "content": f"[tool result for {tool_name}]\n{json.dumps(result, default=str)}",
            })
            continue

        text = str(data.get("text") or "").strip() or _fallback_text(language)
        suggested_route = _validate_route(data.get("suggested_route"), dispatch)
        caveats: list[dict] = []

        known_numbers = set().union(*(_flatten_numbers(r) for r in all_tool_results)) if all_tool_results else set()
        if not _numbers_verified(text, known_numbers):
            turn_messages.append({"role": "assistant", "content": json.dumps(data)})
            turn_messages.append({
                "role": "user",
                "content": (
                    "That answer stated a number that doesn't match any tool "
                    "result you received. Rewrite the answer using only numbers "
                    "you actually retrieved, or say you don't have the figure."
                ),
            })
            retry = _safe_chat_json(turn_messages)
            retry_data = retry["data"] if retry and isinstance(retry["data"], dict) else {}
            retry_text = str(retry_data.get("text") or "").strip()
            if retry_text and _numbers_verified(retry_text, known_numbers):
                text = retry_text
                suggested_route = _validate_route(retry_data.get("suggested_route"), dispatch)
            else:
                caveats = [{
                    "field": "text",
                    "message": (
                        "This answer contains a figure that could not be verified "
                        "against the data this assistant actually retrieved."
                    ),
                    "severity": "warning",
                    "source": "backend/src/models/assistant_agent.py",
                }]

        return {
            "text": text,
            "tools_used": tools_used,
            "citations": citations,
            "suggested_route": suggested_route,
            "caveats": caveats,
        }

    # Unreachable — the force_answer round above always returns — kept only so
    # a future change to the loop bound fails loud rather than falling through.
    raise AssertionError("assistant loop exited without an answer")
