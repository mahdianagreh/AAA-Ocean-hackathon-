"""One vocabulary for `position_confidence` — issue #7, the seam vocabulary bug.

`/api/v1/outlets` used to answer with a hand-typed guess
(`OUTLET_CONFIDENCE = {"AQ-O01": "good", "AQ-O02": "plausible", ...}`) written before
`outlets.geojson` carried real per-outlet confidence from Mahdi's DEM/culvert
cross-check (`scripts/06_catchments.py::POSITION_CONFIDENCE`). The guess diverged from
the geometry team's own analysis on 3 of 5 outlets:

    outlet    geojson (ground truth)    API's old guess
    AQ-O02    low                       plausible   <- understated a flagged risk
    AQ-O03    low                       plausible   <- understated a flagged risk
    AQ-O05    high                      plausible   <- understated real confidence

The frontend's own type union (`frontend/src/api/types.ts:82`,
`'low' | 'plausible' | 'good' | 'high'`) already documents that it had to cover both
vocabularies defensively — `frontend/public/basemap/outlets.geojson` (Ali's own
derivation, straight from the source) has always shown `high`/`low`, while the live
API showed `good`/`plausible`/`low` for the same five outlets. That divergence is
exactly the class of bug this project's CLAUDE.md calls a "plausible, wrong output
with no error": nothing crashed, the map and the side panel just disagreed.

The rule: a value that crosses a module boundary is a contract, same discipline as
`AQ-C01` or `R-03`. This test pins the canonical vocabulary and asserts the API now
reads it from source instead of re-guessing it.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

os.environ.setdefault(
    "REEFSHIELD_EXPOSURE_DB", str(Path(tempfile.mkdtemp()) / "test_position_conf.sqlite")
)

#: The canonical vocabulary. Matches scripts/06_catchments.py::POSITION_CONFIDENCE
#: exactly, plus "unchecked" for any outlet that table has no entry for.
CANONICAL = ("high", "low", "unchecked")

#: Ground truth, transcribed from scripts/06_catchments.py::POSITION_CONFIDENCE by
#: rank. Any drift here from a future edit to that table should fail loudly rather
#: than silently re-diverge the way OUTLET_CONFIDENCE did.
EXPECTED = {
    "AQ-O01": "high",
    "AQ-O02": "low",
    "AQ-O03": "low",
    "AQ-O04": "low",
    "AQ-O05": "high",
}


def test_the_api_schema_accepts_exactly_the_canonical_vocabulary():
    from api.schemas import OutletOut

    field = OutletOut.model_fields["position_confidence"]
    allowed = set(getattr(field.annotation, "__args__", ()) or ())
    assert allowed == set(CANONICAL), (
        f"OutletOut.position_confidence allows {allowed}, expected exactly "
        f"{set(CANONICAL)} — the old 'good'/'plausible' vocabulary must not return"
    )


def test_outlets_endpoint_emits_only_canonical_values():
    from api.main import PREFIX, app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    rows = client.get(f"{PREFIX}/outlets").json()
    assert rows, "no outlets returned — cannot verify vocabulary against nothing"
    for row in rows:
        assert row["position_confidence"] in CANONICAL, (
            f"{row['outlet_id']} emitted {row['position_confidence']!r}, "
            f"not one of {CANONICAL}"
        )


def test_outlets_endpoint_matches_the_geometry_teams_own_analysis():
    """The regression test for the actual bug: values must match the source table,
    not a hand-typed API-side guess that can silently drift from it."""
    from api.main import PREFIX, app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    rows = {r["outlet_id"]: r["position_confidence"] for r in client.get(f"{PREFIX}/outlets").json()}
    for outlet_id, expected in EXPECTED.items():
        assert rows.get(outlet_id) == expected, (
            f"{outlet_id}: API says {rows.get(outlet_id)!r}, "
            f"scripts/06_catchments.py says {expected!r}"
        )


def test_no_hardcoded_confidence_table_survives_in_data_access():
    """OUTLET_CONFIDENCE was the bug. If it comes back, it will silently re-diverge
    from outlets.geojson the same way, so its absence is asserted directly."""
    import api.data_access as da

    assert not hasattr(da, "OUTLET_CONFIDENCE"), (
        "OUTLET_CONFIDENCE has returned to data_access.py — this is the hand-typed "
        "guess that diverged from the real geometry cross-check on 3 of 5 outlets. "
        "Read position_confidence from the outlets artifact instead."
    )
