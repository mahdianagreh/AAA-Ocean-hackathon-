"""Simulation run IDs must be `sim_{ULID}`, per tasks/00-contracts.md's ID contract.

`exposure.store.new_run_id()` used to emit `sim_{YYYYMMDDTHHMMSS}_{uuid4hex8}` —
plausible, unique, roughly time-ordered, and not the format the contract specifies.
Nothing enforced the two staying in sync, which is exactly the class of drift
CLAUDE.md's ID-contract section warns about: a join key that quietly stops matching
what any downstream reader (Nizar's Supabase layer, a script parsing the log) expects
of a `sim_` id.

A real ULID is 26 Crockford-base32 characters: 48-bit millisecond timestamp then
80-bit randomness. This pins the shape so a future edit that reverts to a
timestamp-plus-uuid format fails loudly instead of silently.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

#: Crockford base32 — excludes I, L, O, U.
_CROCKFORD_CHARS = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


def test_run_id_has_the_sim_prefix():
    from exposure.store import new_run_id

    assert new_run_id().startswith("sim_")


def test_run_id_ulid_segment_is_26_crockford_base32_chars():
    from exposure.store import new_run_id

    rid = new_run_id()
    ulid_part = rid.removeprefix("sim_")
    assert len(ulid_part) == 26, f"ULID segment is {len(ulid_part)} chars, want 26: {rid!r}"
    assert set(ulid_part) <= _CROCKFORD_CHARS, (
        f"{rid!r} contains characters outside Crockford base32 "
        f"(no I, L, O, U): {set(ulid_part) - _CROCKFORD_CHARS}"
    )


def test_run_ids_are_unique_across_many_calls():
    from exposure.store import new_run_id

    ids = {new_run_id() for _ in range(500)}
    assert len(ids) == 500, "collision within 500 calls — the random segment is too small"


def test_run_ids_sort_by_creation_time_at_millisecond_granularity():
    """The whole point of a ULID over a bare UUID: lexicographic sort order should
    track creation order once calls are far enough apart to land in different
    milliseconds. (Two calls within the same millisecond are not ordered relative
    to each other — that is the ULID spec, not a bug here.)"""
    from exposure.store import new_run_id

    earlier = new_run_id()
    time.sleep(0.01)
    later = new_run_id()
    assert later > earlier, f"{later!r} does not sort after {earlier!r}"


def test_the_old_timestamp_uuid_format_is_gone():
    """Regression guard for the exact format this replaced."""
    import re

    from exposure.store import new_run_id

    old_format = re.compile(r"^sim_\d{8}T\d{6}_[0-9a-f]{8}$")
    for _ in range(10):
        assert not old_format.match(new_run_id()), (
            "new_run_id() reverted to the old sim_{timestamp}_{uuid8} format"
        )
