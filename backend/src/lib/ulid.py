"""Crockford base32 ULID generation.

Extracted from `exposure/store.py::_new_ulid` (Phase 3) so every SQLite-backed
store this project adds — `exposure_runs`, and now `candidate_sites`,
`sampling_feedback`, `reef_zone_photos` — generates IDs the same way instead of
re-implementing the same ~15 lines three more times. Behaviour is unchanged:
`exposure/store.py::new_run_id` now calls `new_ulid()` here rather than its own
private copy, and `tests/test_run_id_contract.py` stays green untouched, since it
tests the output format, not which module produced it.
"""

from __future__ import annotations

import secrets
import time

# Crockford base32: excludes I, L, O, U to avoid transcription confusion.
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid() -> str:
    """A real ULID: 48-bit millisecond timestamp + 80-bit randomness, 26 chars.

    Lexicographic sort order matches creation order at millisecond granularity,
    because the timestamp occupies the leading characters. Two IDs minted in the
    same millisecond are not ordered relative to each other (their random suffix
    decides), which matches the standard ULID spec and is fine here — nothing in
    this project orders by ID at sub-millisecond precision.
    """
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    value = (ts_ms << 80) | secrets.randbits(80)  # 128 significant bits
    # 26 chars * 5 bits = 130 bits; the top 2 bits are always 0 since value has
    # only 128 significant bits — Python's arbitrary-width ints yield 0 for shifts
    # past the top, so no explicit padding is needed.
    return "".join(_CROCKFORD[(value >> (5 * (25 - i))) & 0x1F] for i in range(26))
