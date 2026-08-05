"""The `Value{value, unit, provenance}` wrapper — issue #14.

Units baked into a formatted string (`"2.18 g/L"`) break two ways: RTL reorders it
into `"g/L 2.18"`, and a client that wants the number has to parse it back out. The
fix from OPEN-ISSUES.md #6/#14 is a wrapper the client never has to parse: unit and
provenance travel next to the number, always.

`unit` and `provenance` are REQUIRED on Value — that's the mechanism OPEN-ISSUES.md
#6 describes: "a Value without provenance fails type-check, so an unlabelled number
cannot reach the screen." `value` alone is optional, since a gap (predicted_runoff_m3
being None) still has a definite unit and a definite reason for its absence.

THE SHAPE IS NOT INVENTED HERE, AND THAT MATTERS. An earlier version of this class
gave `provenance` the shape of this file's unrelated `Provenance{kind, detail}`
class. That was wrong: `frontend/src/api/types.ts` already declares its own
`Value.provenance: 'measured'|'reported'|'converted'|'modelled'`, and
`ValueWithUnit.tsx` already renders it by indexing a lookup table with that string
— an object would have silently rendered with no data-quality styling, not crashed,
which is the worse failure mode. `Value.provenance` now matches the frontend's real
type exactly.

`OutletOut.upstream_km2` and `.nearest_culvert_m` were ALSO an earlier version's
mistake: `frontend/src/api/types.ts`'s `Outlet` interface already declares both as
bare `number`, predating this pass, and `SideRail.tsx:147` already reads
`o.upstream_km2` as a number. Wrapping them in `Value` would have broken that read
the moment live mode (rather than fixtures) actually populated them. Both fields
stay bare floats; `Value` itself remains as correctly-shaped, tested infrastructure
for the next field that needs it, rather than forced onto a field whose consumer
contract was already fixed.
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
    "REEFSHIELD_EXPOSURE_DB", str(Path(tempfile.mkdtemp()) / "test_value_wrapper.sqlite")
)

#: Matches frontend/src/api/types.ts:16 exactly.
CANONICAL_VALUE_PROVENANCE = ("measured", "reported", "converted", "modelled")


def test_value_requires_unit_and_provenance():
    from pydantic import ValidationError

    from api.schemas import Value

    with pytest.raises(ValidationError):
        Value(value=1.0)  # missing unit and provenance — must fail, not default


def test_value_provenance_matches_the_frontends_own_vocabulary_exactly():
    """Regression guard for the shape bug: Value.provenance must be the frontend's
    flat string enum, never this file's unrelated Provenance{kind, detail} class."""
    from api.schemas import Value

    field = Value.model_fields["provenance"]
    allowed = set(getattr(field.annotation, "__args__", ()) or ())
    assert allowed == set(CANONICAL_VALUE_PROVENANCE), (
        f"Value.provenance allows {allowed}, expected exactly "
        f"{set(CANONICAL_VALUE_PROVENANCE)} — frontend/src/api/types.ts:16"
    )


def test_value_permits_a_missing_number_but_not_a_missing_unit():
    from api.schemas import Value

    v = Value(value=None, unit="m3", provenance="modelled")
    assert v.value is None
    assert v.unit == "m3"  # the unit survives even when the number does not


def test_outlets_upstream_km2_and_nearest_culvert_m_are_bare_numbers():
    """The regression test for the actual bug: these two fields must match
    frontend/src/api/types.ts's Outlet interface (both `number`) exactly, not a
    Value object — SideRail.tsx already reads them as plain numbers."""
    from api.main import PREFIX, app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    rows = client.get(f"{PREFIX}/outlets").json()
    assert rows, "no outlets returned"
    for row in rows:
        for field in ("upstream_km2", "nearest_culvert_m"):
            assert row[field] is None or isinstance(row[field], (int, float)), (
                f"{field} is {type(row[field])}, not a bare number: {row[field]!r} — "
                f"this would break SideRail.tsx:147's o.{field} read"
            )


def test_no_endpoint_bakes_a_unit_into_a_bare_string():
    """Regression guard for the exact anti-pattern issue #14 names: '2.18 g/L' as
    one string a client has to regex apart. Scans every live JSON response for a
    string value that looks like `<number><unit>`."""
    import re

    from api.main import PREFIX, app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    baked_unit = re.compile(r"^-?\d+(\.\d+)?\s?(g/L|mm/day|mm/hr|km2|km²|m3|°C|ppt|‰)$")

    offenders = []

    def scan(obj, path):
        if isinstance(obj, dict):
            for k, v in obj.items():
                scan(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                scan(v, f"{path}[{i}]")
        elif isinstance(obj, str) and baked_unit.match(obj.strip()):
            offenders.append((path, obj))

    for route in ("/catchments", "/reef-zones", "/outlets", "/events"):
        r = client.get(f"{PREFIX}{route}")
        if r.status_code == 200:
            scan(r.json(), route)

    assert not offenders, f"unit baked into a string value: {offenders}"
