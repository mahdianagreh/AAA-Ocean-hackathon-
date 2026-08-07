"""Candidate-site IDs must be `site_{ULID}` — Phase 5, B4's new namespace.

Mirrors `tests/test_run_id_contract.py`'s enforcement of `sim_{ULID}` exactly:
this project's convention is that a new frozen ID scheme gets a matching
static-scanning guard, the same way `tests/test_spatial_contract.py` guards the
AOI bounding boxes. `site_{ULID}` is confirmed, in `docs/data_dictionary.md`,
clear of the five existing frozen schemes (AQ-C, AQ-O, R-, AQ-YYYY-MM-DD,
sim_{ULID}) — a candidate site is never an Aqaba entity.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

#: Crockford base32 — excludes I, L, O, U.
_CROCKFORD_CHARS = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


def test_site_id_has_the_site_prefix():
    from models.candidate_sites import new_site_id

    assert new_site_id().startswith("site_")


def test_site_id_ulid_segment_is_26_crockford_base32_chars():
    from models.candidate_sites import new_site_id

    sid = new_site_id()
    ulid_part = sid.removeprefix("site_")
    assert len(ulid_part) == 26, f"ULID segment is {len(ulid_part)} chars, want 26: {sid!r}"
    assert set(ulid_part) <= _CROCKFORD_CHARS, (
        f"{sid!r} contains characters outside Crockford base32 "
        f"(no I, L, O, U): {set(ulid_part) - _CROCKFORD_CHARS}"
    )


def test_site_ids_are_unique_across_many_calls():
    from models.candidate_sites import new_site_id

    ids = {new_site_id() for _ in range(1000)}
    assert len(ids) == 1000, "collision within 1000 calls — the random segment is too small"


def test_site_ids_sort_by_creation_time_at_millisecond_granularity():
    from models.candidate_sites import new_site_id

    earlier = new_site_id()
    time.sleep(0.01)
    later = new_site_id()
    assert later > earlier, f"{later!r} does not sort after {earlier!r}"


def test_site_id_prefix_is_not_a_frozen_aqaba_scheme():
    """The five frozen schemes (tasks/00-contracts.md §2): AQ-C, AQ-O, R-,
    AQ-{YYYY}-{MM}-{DD}, sim_{ULID}. `site_` collides with none of them."""
    from models.candidate_sites import new_site_id

    sid = new_site_id()
    assert not sid.startswith("AQ-")
    assert not sid.startswith("R-")
    assert not sid.startswith("sim_")
