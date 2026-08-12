"""Phase 9 — the response-recommendation swarm's orchestration core.

`tasks/phase9/00-phase9-plan.md` §5-§6. Mahdi's proposed piece (model/orchestration);
persistence goes through `response_recommendations.py`, the severity brief through
`severity_brief.py`. This module owns: the 5-agent roster, per-role grounding via the
existing BM25 layer (`rag/index.py`), the round loop with early convergence, the
judge, and the gaps agent.

GROUNDING DISCIPLINE
---------------------
Same rule as `rag/answer.py`: a citation list is built from what was actually
retrieved/given, never from what the model claims it used. Every specialist prompt
receives the severity brief (real numbers, always trustworthy) plus up to 5 chunks
from `rag_index.retrieve()` for that role's grounding query. `_valid_evidence()`
below drops any cited item that is neither a provided chunk_id nor a `brief.`-
prefixed path — an invented citation is removed, not trusted, which can leave a
turn with `evidence_cited: []`. That is the honest outcome for a claim with
nothing real behind it, not a reason to fabricate a citation for it.
"""

from __future__ import annotations

import difflib

from models import ollama_client as oc

MAX_ROUNDS = 3
CONVERGENCE_RATIO = 0.85
CLUSTER_RATIO = 0.7

# role -> (title, grounding query). Queries target this corpus's own documented
# scope (docs/data_dictionary.md, docs/Ali/research/*, pitch_limitations.md) —
# see tasks/phase9/00-phase9-plan.md §5's "Grounding" column for the source each
# maps to.
AGENT_ROSTER = [
    {
        "role": "aseza",
        "title": "ASEZA / Marine Park Authority",
        "brief": "The regulator's seat — protected-zone closures, permitting, "
                 "public notices for the Aqaba Marine Reserve.",
        "grounding_query": "ASEZA Aqaba Marine Park Authority protected zone "
                            "closures permitting bylaw",
    },
    {
        "role": "marine_science",
        "title": "Marine Science / Reef Ecology",
        "brief": "Reef-specific mitigation: dive-site closures, coral/seagrass "
                 "triage priority by zone, monitoring deployment.",
        "grounding_query": "reef zone sensitivity coral seagrass monitoring "
                            "marine park overlap",
    },
    {
        "role": "port_ops",
        "title": "Port & Industrial Operations",
        "brief": "Stormwater containment and operational holds for the outlets "
                 "that route through the container terminal, tank farms, and "
                 "the enclosed harbour basin.",
        "grounding_query": "outlet container terminal tank farm harbour basin "
                            "stormwater containment",
    },
    {
        "role": "civil_defense",
        "title": "Municipal / Civil Defense",
        "brief": "Human safety first: a wadi flash flood is a road/crossing "
                 "hazard before it is a marine one. Evacuation and closure "
                 "guidance.",
        "grounding_query": "wadi flash flood rain to coast lag time evacuation "
                            "road crossing hazard",
    },
    {
        "role": "tourism",
        "title": "Tourism & Dive Operators",
        "brief": "Practical downstream guidance for the dive operators who "
                 "receive this alert.",
        "grounding_query": "dive operators tourism alert distribution free tier",
    },
]

_SYSTEM_PREAMBLE = (
    "You are a specialist advisor in a multi-agent storm-response debate for the "
    "ReefShield Aqaba sediment-plume warning system. You will be shown a severity "
    "brief built from real, already-computed numbers, and optionally reference "
    "material retrieved from this project's own documentation. You must propose or "
    "critique ONE concrete action from your seat's perspective. "
    "Cite every factual claim: use a chunk_id from the reference material, or a "
    "'brief.<field>' path into the severity brief. If you have neither for a claim, "
    "state that you cannot ground it and do not make the claim. "
    "Respond with strict JSON: "
    '{"proposal": string, "evidence_cited": [string], "abstained": boolean}. '
    'Set "abstained": true only if you have no groundable action to propose.'
)


def _valid_evidence(cited: list, chunk_ids: set[str]) -> list[str]:
    if not isinstance(cited, list):
        return []
    return [
        c for c in cited
        if isinstance(c, str) and (c in chunk_ids or c.startswith("brief."))
    ]


def _agent_messages(
    agent: dict, brief: dict, chunks: list[dict], transcript: list[dict], round_num: int,
) -> list[dict]:
    lines = [
        f"Your seat: {agent['title']}. {agent['brief']}",
        f"Round {round_num} of up to {MAX_ROUNDS}.",
        f"Severity brief: {brief}",
    ]
    if chunks:
        lines.append("Reference material (cite by chunk_id):")
        for c in chunks:
            lines.append(f"- chunk_id={c['chunk_id']!r} [{c['source_file']}#{c['section']}]: "
                         f"{c['excerpt']}")
    else:
        lines.append("No reference material was retrieved for your seat this round — "
                     "ground claims only in the severity brief, or abstain.")
    if transcript:
        lines.append("Prior transcript (all rounds, all seats so far):")
        for t in transcript:
            lines.append(f"- round {t['round']} [{t['agent_role']}]: {t['content']}")
    return [
        {"role": "system", "content": _SYSTEM_PREAMBLE},
        {"role": "user", "content": "\n".join(lines)},
    ]


def run_round(
    brief: dict, transcript: list[dict], round_num: int,
    retrieve=None,
) -> list[dict]:
    """One round: all 5 specialists in parallel, `think: false`. Returns turns —
    `[{"agent_role", "content", "evidence_cited"}]` — in roster order, ready to
    persist via `response_recommendations.add_turn`. A specialist whose call fails
    (`ollama_client` returns None for that slot) contributes an explicit failure
    turn rather than silently vanishing from the round."""
    if retrieve is None:
        from rag.index import retrieve as retrieve

    chunk_sets, calls = [], []
    for agent in AGENT_ROSTER:
        chunks = retrieve(agent["grounding_query"], k=5)
        chunk_sets.append(chunks)
        calls.append(_agent_messages(agent, brief, chunks, transcript, round_num))

    results = oc.chat_json_parallel(calls, think=False)

    turns = []
    for agent, chunks, result in zip(AGENT_ROSTER, chunk_sets, results):
        chunk_ids = {c["chunk_id"] for c in chunks}
        if result is None:
            turns.append({
                "agent_role": agent["role"],
                "content": "[no response — the model call failed or returned "
                           "unparseable output this round]",
                "evidence_cited": [],
            })
            continue
        data = result["data"]
        if data.get("abstained"):
            content = "[abstained — no groundable action this round]"
        else:
            content = str(data.get("proposal", "")).strip() or "[empty proposal]"
        turns.append({
            "agent_role": agent["role"],
            "content": content,
            "evidence_cited": _valid_evidence(data.get("evidence_cited", []), chunk_ids),
        })
    return turns


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _similar(a: str, b: str, ratio: float) -> bool:
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio() >= ratio


def rounds_converged(prev_turns: list[dict], curr_turns: list[dict]) -> bool:
    """True if every role's proposal this round is a near-duplicate of last round's —
    the plan's "same core proposal survives 2 consecutive rounds unchanged" check."""
    prev_by_role = {t["agent_role"]: t["content"] for t in prev_turns}
    for t in curr_turns:
        prior = prev_by_role.get(t["agent_role"])
        if prior is None or not _similar(prior, t["content"], CONVERGENCE_RATIO):
            return False
    return True


def pick_final_candidate(turns: list[dict]) -> tuple[str, list[str]]:
    """(text, contributing_roles) — the largest near-duplicate cluster among a
    round's proposals, representative = its longest text. Ties broken by roster
    order (stable sort), never by an invented tiebreak number."""
    real_turns = [t for t in turns if not t["content"].startswith("[")]
    if not real_turns:
        return "No specialist produced a groundable proposal this round.", []

    clusters: list[list[dict]] = []
    for t in real_turns:
        placed = False
        for cluster in clusters:
            if _similar(cluster[0]["content"], t["content"], CLUSTER_RATIO):
                cluster.append(t)
                placed = True
                break
        if not placed:
            clusters.append([t])

    best = max(clusters, key=len)
    representative = max(best, key=lambda t: len(t["content"]))
    return representative["content"], [t["agent_role"] for t in best]


def run_judge(brief: dict, candidate: str, transcript: list[dict], retrieve=None) -> dict:
    """`think: true` — the ~26s reasoning cost is spent here on purpose (§4/§6.4).
    Grounded on a fresh retrieval against the candidate text itself, same BM25
    layer `/ask` uses. Returns `{"verdict", "reasoning", "evidence_cited"}`."""
    if retrieve is None:
        from rag.index import retrieve as retrieve

    chunks = retrieve(candidate, k=5)
    chunk_ids = {c["chunk_id"] for c in chunks}
    lines = [
        "You are the judge in a storm-response recommendation debate. Approve or "
        "reject the candidate recommendation below. Reject if it makes any claim "
        "not supported by the severity brief or the reference material — name the "
        "specific unsupported claim in your reasoning if you reject.",
        f"Severity brief: {brief}",
        f"Candidate recommendation: {candidate}",
    ]
    if chunks:
        lines.append("Reference material (cite by chunk_id):")
        for c in chunks:
            lines.append(f"- chunk_id={c['chunk_id']!r}: {c['excerpt']}")
    lines.append("Full debate transcript:")
    for t in transcript:
        lines.append(f"- round {t['round']} [{t['agent_role']}]: {t['content']}")
    lines.append(
        'Respond with strict JSON: {"verdict": "approved"|"rejected", '
        '"reasoning": string, "evidence_cited": [string]}.'
    )
    messages = [
        {"role": "system", "content": "You are a strict evidence-grounding judge. "
                                       "You never approve an unsupported claim."},
        {"role": "user", "content": "\n".join(lines)},
    ]
    result = oc.chat_json(messages, think=True)
    data = result["data"]
    verdict = data.get("verdict") if data.get("verdict") in ("approved", "rejected") else "rejected"
    return {
        "verdict": verdict,
        "reasoning": str(data.get("reasoning", "")).strip() or "(no reasoning returned)",
        "evidence_cited": _valid_evidence(data.get("evidence_cited", []), chunk_ids),
    }


def run_gaps(brief: dict, final_recommendation: str, transcript: list[dict]) -> list[dict]:
    """`think: true`, post-approval only (§6.5) — "what's missing / what could
    fail / what's unverified" ships attached to the recommendation, never
    separately, never omitted."""
    lines = [
        "The debate below converged on the final recommendation shown. Identify what "
        "is missing, what could fail, or what remains unverified about it — this "
        "ships attached to the recommendation, so be concrete and specific to this "
        "storm's numbers, not generic caveats.",
        f"Severity brief: {brief}",
        f"Final recommendation: {final_recommendation}",
    ]
    lines.append(
        'Respond with strict JSON: {"gaps": [{"description": string, '
        '"severity": "low"|"medium"|"high"}]}.'
    )
    messages = [
        {"role": "system", "content": "You are the limitations agent. You find real "
                                       "gaps, not boilerplate disclaimers."},
        {"role": "user", "content": "\n".join(lines)},
    ]
    result = oc.chat_json(messages, think=True)
    gaps = result["data"].get("gaps", [])
    out = []
    for g in gaps if isinstance(gaps, list) else []:
        if isinstance(g, dict) and g.get("description"):
            out.append({
                "description": str(g["description"]),
                "severity": g.get("severity") if g.get("severity") in
                            ("low", "medium", "high") else None,
            })
    return out


def run_swarm(recommendation_id: str, brief: dict, store=None) -> dict:
    """Top-level orchestration for one `response_recommendations` row. Persists
    every turn/verdict/gap as it happens (so a crash mid-swarm leaves a real
    partial audit trail, not silence), then finalizes. Returns the final stored
    record (`response_recommendations.get_recommendation`'s shape)."""
    if store is None:
        from models import response_recommendations as store

    transcript: list[dict] = []
    prev_round: list[dict] | None = None
    converged = False
    round_num = 0

    for round_num in range(1, MAX_ROUNDS + 1):
        turns = run_round(brief, transcript, round_num)
        for t in turns:
            store.add_turn(recommendation_id, round_num, t["agent_role"],
                          t["content"], t["evidence_cited"])
        transcript.extend({"round": round_num, **t} for t in turns)
        if prev_round is not None and rounds_converged(prev_round, turns):
            converged = True
            break
        prev_round = turns

    store.update_status(recommendation_id, "proposed", rounds_used=round_num,
                        converged=converged)

    last_round_turns = [t for t in transcript if t["round"] == round_num]
    candidate, contributing = pick_final_candidate(last_round_turns)

    verdict = run_judge(brief, candidate, transcript)
    store.add_verdict(recommendation_id, verdict["verdict"], verdict["reasoning"],
                      verdict["evidence_cited"])

    if verdict["verdict"] == "rejected":
        # One revision round only (§6.4) — feed the rejection back, not an
        # open-ended loop.
        round_num += 1
        revision_note = {
            "round": round_num, "agent_role": "judge",
            "content": f"REJECTED: {verdict['reasoning']}",
        }
        transcript.append(revision_note)
        revised_turns = run_round(brief, transcript, round_num)
        for t in revised_turns:
            store.add_turn(recommendation_id, round_num, t["agent_role"],
                          t["content"], t["evidence_cited"])
        transcript.extend({"round": round_num, **t} for t in revised_turns)
        store.update_status(recommendation_id, "proposed", rounds_used=round_num)

        candidate, contributing = pick_final_candidate(revised_turns)
        verdict2 = run_judge(brief, candidate, transcript)
        store.add_verdict(recommendation_id, verdict2["verdict"], verdict2["reasoning"],
                          verdict2["evidence_cited"])
        if verdict2["verdict"] == "rejected":
            final_recommendation = (
                f"[APPROVED WITH CAVEAT — contested by judge after revision: "
                f"{verdict2['reasoning']}] {candidate}"
            )
        else:
            final_recommendation = candidate
    else:
        final_recommendation = candidate

    store.update_status(recommendation_id, "judge_approved",
                        final_recommendation=final_recommendation)

    gaps = run_gaps(brief, final_recommendation, transcript)
    for g in gaps:
        store.add_gap(recommendation_id, g["description"], g["severity"])

    return store.update_status(
        recommendation_id, "finalized",
        final_recommendation=final_recommendation,
        complete=True,
    )
