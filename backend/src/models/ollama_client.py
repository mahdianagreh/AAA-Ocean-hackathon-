"""Thin HTTP wrapper over a local Ollama daemon — the swarm's only LLM call site.

Phase 9 (`tasks/phase9/00-phase9-plan.md` §4). Stdlib `urllib` only, deliberately: this
is the first place the codebase calls a generative model at all (`rag/answer.py`'s own
`generate_with_llm` is an unimplemented hook, not wired), and it talks to `localhost`
only — no key, no external dependency to add to either requirements file for that.

`think` is NOT a stylistic knob. Measured 11 Aug on this hardware: `think: false` is
~3.4s warm, `think: true` is ~25.8s warm (~8x). The plan reserves thinking mode for the
judge and gaps agent specifically; every specialist round call passes `think=False`.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

MODEL = "gemma4:31b"
_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
_TIMEOUT_S = 240
# think:true carries a full multi-round debate transcript into context by the time
# the judge/gaps agent run (§6.4-§6.5) — much bigger than the short standalone
# prompts §4 benchmarked. Found 11 Aug: a judge call over a 3-round, 5-role
# transcript blew the original 120s client timeout even though the daemon was
# still working, not hung. Give reasoning calls their own longer budget rather
# than raising the default for every call.
_THINK_TIMEOUT_S = 240


class OllamaUnavailable(RuntimeError):
    """The daemon didn't respond — never silently returned a stub."""


def chat(
    messages: list[dict],
    think: bool = False,
    json_mode: bool = False,
    model: str = MODEL,
) -> dict:
    """One turn. Returns {"content": str, "thinking": str | None}.

    `messages` is the raw Ollama chat list (`[{"role": ..., "content": ...}]`) —
    callers build the system/user split, this function does not template prompts.
    """
    payload = {
        "model": model,
        "messages": messages,
        "think": think,
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"

    req = urllib.request.Request(
        f"{_BASE_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout = _THINK_TIMEOUT_S if think else _TIMEOUT_S
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise OllamaUnavailable(
            f"Ollama at {_BASE_URL} did not respond for model {model!r}: {exc}"
        ) from exc

    message = body.get("message", {})
    return {"content": message.get("content", ""), "thinking": message.get("thinking")}


def chat_json(messages: list[dict], think: bool = False, model: str = MODEL) -> dict:
    """`chat()` with JSON mode, pre-parsed. Raises ValueError on unparseable content —
    a caller that cannot get structured output back is a refusal, not a guess at what
    the model meant."""
    result = chat(messages, think=think, json_mode=True, model=model)
    try:
        parsed = json.loads(result["content"])
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"model returned non-JSON content despite format=json: {result['content']!r}"
        ) from exc
    return {"data": parsed, "thinking": result["thinking"]}


def chat_json_parallel(
    calls: list[list[dict]], think: bool = False, model: str = MODEL
) -> list[dict | None]:
    """Run several `chat_json` calls concurrently — measured §4: ~7.9s wall-clock for
    3 concurrent `think:false` calls on this hardware, not ~3x the single-call time.
    One caller's failure does not fail the others; that slot's result is None and the
    caller decides whether a missing specialist turn still lets the round proceed."""
    def _one(messages: list[dict]) -> dict | None:
        try:
            return chat_json(messages, think=think, model=model)
        except (OllamaUnavailable, ValueError):
            return None

    with ThreadPoolExecutor(max_workers=len(calls) or 1) as pool:
        return list(pool.map(_one, calls))
