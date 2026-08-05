"""Adversarial verification of `/explain` and `/ask` through the live HTTP routes.

`tests/test_explain_fidelity.py` and `tests/test_ask_citations.py` are already
thorough at the unit level — they call `explain.build_explanation()` and
`index.retrieve()`/`rag_answer.generate_cited_answer()` directly. What neither one
does is call the actual FastAPI routes end to end, which is the thing a demo
actually hits. This file closes that gap and adds three adversarial cases that
were not yet pinned:

  1. `/explain` over the live route, both languages, several catchments — proves
     request validation, routing and the fidelity guarantee all compose correctly,
     not just the template function in isolation.
  2. A number-fidelity boundary case `numbers_present()` is already coded to
     handle (a source number that is a substring of a DIFFERENT, longer number in
     the text — e.g. source "72" against rendered text containing "720") but that
     had no test pinning the behavior explicitly.
  3. `/ask` refused on harder near-miss questions: genuinely out-of-corpus but
     topically adjacent, so a weak retriever could be tempted to answer from a
     shared word rather than refuse.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

os.environ.setdefault(
    "REEFSHIELD_EXPOSURE_DB", str(Path(tempfile.mkdtemp()) / "test_adversarial.sqlite")
)


def _client():
    from api.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


# --------------------------------------------------------------- /explain, live route

def test_explain_route_fidelity_multiple_catchments_both_languages():
    from api.main import PREFIX

    client = _client()
    catchment_ids = [c["catchment_id"] for c in client.get(f"{PREFIX}/catchments").json()][:3]
    assert catchment_ids, "no catchments available to test against"

    for cid in catchment_ids:
        for lang in ("en", "ar"):
            body = {
                "catchment_id": cid,
                "language": lang,
                "plume_probability": 0.7183,
                "arrival_window_hours": [8.5, 12.25],
                "confidence": "moderate",
                "reef_zone_id": "R-04",
                "rainfall_percentile": 99,
                "shap_drivers": [
                    {"feature": "rainfall_3h_mm", "value": 41.2, "contribution": 0.31},
                ],
            }
            r = client.post(f"{PREFIX}/explain", json=body)
            assert r.status_code == 200, f"{cid}/{lang}: {r.status_code} {r.text}"
            j = r.json()
            for expected in ("71.83", "8.5", "12.25"):
                assert expected in j["text"], (
                    f"{cid}/{lang}: {expected!r} missing from {j['text']!r}"
                )
            assert j["generator"] == "deterministic_template"


def test_explain_route_rejects_unknown_catchment():
    from api.main import PREFIX

    client = _client()
    r = client.post(f"{PREFIX}/explain", json={"catchment_id": "AQ-C99", "language": "en"})
    assert r.status_code == 404


# ------------------------------------------------- numbers_present boundary adversary

def test_numbers_present_catches_a_source_number_extended_in_the_text():
    """The exact tampering the boundary-aware regex exists to catch: source number
    72 must not be considered "present" just because the text contains 720 or 72.4.
    """
    from rag.explain import numbers_present

    source = {"plume_probability_pct": 72}
    assert not numbers_present("72% probability of exposure", source), (
        "sanity: 72 alone must be found"
    )
    assert numbers_present("720% probability of exposure", source), (
        "72 was found as a substring of 720 — the tampering guard regressed"
    )
    assert numbers_present("72.4% probability of exposure", source), (
        "72 was found as a substring of 72.4 — the tampering guard regressed"
    )


def test_numbers_present_finds_a_number_next_to_punctuation():
    """The boundary regex must not be so strict it rejects legitimate adjacency —
    e.g. a number immediately followed by a comma or a closing parenthesis."""
    from rag.explain import numbers_present

    source = {"value": 72}
    assert not numbers_present("the figure (72) is exact", source)
    assert not numbers_present("at 72, confidence is moderate", source)


# --------------------------------------------------------------------- /ask, harder refusals

# Genuinely out-of-corpus, but each shares vocabulary with something the corpus DOES
# discuss — the failure mode a weak retriever would show is answering from the
# shared word rather than the actual absence of documented information.
#
# The Egyptian-scope case is FIXED (2026-08-05): index._SCOPE_EXCLUSIVE_TERMS now
# rejects a chunk that doesn't itself name a country the question named. It is not
# quoted literally here in a way that matters — this file is a test, not part of
# rag.corpus.CORPUS_FILES, so nothing here reaches the index — but the fix and the
# earlier self-contamination incident are documented in docs/model_card.md
# E-Retrieval limitation #3 rather than repeated here.
MUST_REFUSE_FIXED = [
    "What is the reef sensitivity weight for the Egyptian side of the Gulf?",
]

# These three reproduce DIFFERENT root causes — wrong specific attribution ("NOAA's
# main website"), wrong entity ("Jordanian government open data portal" vs. the
# dataset licenses the corpus actually documents), and wrong time/specificity
# ("Eilat... 2024" against a documented 2016 event) — none of which a geography
# blocklist generalizes to. Each needs real qualifier-aware retrieval or re-ranking,
# not a per-string patch; attempting one now risks overfitting to exactly these
# three sentences without fixing the underlying class of bug. Tracked, not silently
# accepted.
MUST_REFUSE_STILL_OPEN = [
    "How accurate is the bathymetry data used by NOAA's main website?",
    "What licence does the Jordanian government use for its open data portal?",
    "Is there a mooring near Eilat measuring turbidity in 2024?",
]


def test_ask_refuses_the_fixed_scope_exclusion_case():
    from api.main import PREFIX

    client = _client()
    for q in MUST_REFUSE_FIXED:
        r = client.post(f"{PREFIX}/ask", json={"question": q, "language": "en"})
        assert r.status_code == 200, f"{q}: {r.status_code}"
        j = r.json()
        assert not j["citations"], (
            f"{q!r} was answered with citations {j['citations']} instead of refused — "
            "the _SCOPE_EXCLUSIVE_TERMS guard regressed"
        )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "DISCOVERED GAP, not fixed — recorded in docs/model_card.md E-Retrieval "
        "Known limitations #3. These three reproduce different root causes (wrong "
        "specific attribution, wrong entity, wrong time/specificity) that a geography "
        "blocklist does not generalize to. Real qualifier-aware retrieval or a "
        "re-ranking step would fix this properly; a per-string patch for exactly "
        "these three sentences would overfit to the test rather than the bug class, "
        "so none was attempted. xfail(strict=True) so this stays visibly tracked."
    ),
)
def test_ask_refuses_near_miss_questions_with_other_root_causes():
    from api.main import PREFIX

    client = _client()
    for q in MUST_REFUSE_STILL_OPEN:
        r = client.post(f"{PREFIX}/ask", json={"question": q, "language": "en"})
        assert r.status_code == 200, f"{q}: {r.status_code}"
        j = r.json()
        assert not j["citations"], (
            f"{q!r} was answered with citations {j['citations']} instead of refused"
        )


def test_ask_citations_are_never_prose_even_on_refusal():
    """Issue #13: citations must be a structured array on every response, not a
    prose fallback string, whether the question is answered or refused."""
    from api.main import PREFIX

    client = _client()
    for q in ["What is the reef sensitivity weight for R-04?", *MUST_REFUSE_FIXED, *MUST_REFUSE_STILL_OPEN[:1]]:
        r = client.post(f"{PREFIX}/ask", json={"question": q, "language": "en"})
        j = r.json()
        assert isinstance(j["citations"], list), (
            f"{q!r}: citations is {type(j['citations'])}, not a list"
        )
        for c in j["citations"]:
            assert isinstance(c, dict) and "source_file" in c and "excerpt" in c
