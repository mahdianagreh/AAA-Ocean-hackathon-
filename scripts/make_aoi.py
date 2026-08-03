"""Verify the AOI files on disk match the spatial contract. Writes nothing.

Run: ../.venv/bin/python make_aoi.py   (from scripts/)

WHY THIS NO LONGER WRITES ANYTHING
----------------------------------
Until 2 August 2026 this script generated `data/raw/aoi/aqaba_padded_box.geojson`
and `data/aoi/aqaba_aoi.geojson` from its own constants. The project now has a
single spatial contract at `backend/src/config/spatial.py`, and that contract owns
`data/aoi/{terrain,marine,aqaba}_aoi.geojson`.

Two writers for one contract file is the same class of problem the ID contract
exists to prevent: whichever ran last would win, silently, and the loser's numbers
would already be downstream. So this script was reduced to a check. It fails loudly
if the files and the contract disagree, which is the only job worth having here.

The old constants are deliberately gone rather than commented out — a commented-out
bounding box is exactly what gets copy-pasted back in on a deadline, and
`tests/test_spatial_contract.py` asserts no module carries a bbox literal.
"""

import sys

from pulga_config import LAND_BBOX, MARINE_BBOX, load_spatial_contract


def main():
    # Not `from config.spatial import ...` — see load_spatial_contract's docstring.
    spatial = load_spatial_contract()

    print("Spatial contract (backend/src/config/spatial.py)")
    print(f"  TERRAIN_AOI  {spatial.TERRAIN_AOI.wsen}")
    print(f"  MARINE_AOI   {spatial.MARINE_AOI.wsen}")
    print(f"  AQABA_AOI    {spatial.AQABA_AOI.wsen}")

    # The contract ships its own file/constant comparison — use it rather than
    # writing a second, subtly different version of the same check.
    try:
        verified = spatial.verify_against_files()
    except Exception as e:
        sys.exit(f"\nAOI files disagree with the contract: {type(e).__name__}: {e}")

    print(f"\n  OK {len(verified)} AOI file(s) on disk match the contract exactly")
    for name, bbox in sorted(verified.items()):
        print(f"     {name:14s} {bbox.wsen}")

    # What scripts/ imports must be the same numbers, or this chain is clipping to
    # something the rest of the project has never heard of.
    assert LAND_BBOX == spatial.TERRAIN_AOI.wsen, (
        f"scripts/config.LAND_BBOX {LAND_BBOX} != contract TERRAIN_AOI "
        f"{spatial.TERRAIN_AOI.wsen}"
    )
    assert MARINE_BBOX == spatial.MARINE_AOI.wsen, (
        f"scripts/config.MARINE_BBOX {MARINE_BBOX} != contract MARINE_AOI "
        f"{spatial.MARINE_AOI.wsen}"
    )
    print("\n  OK scripts/config re-exports resolve to the same boxes")

    t, m = spatial.TERRAIN_AOI, spatial.MARINE_AOI
    overlap = not (m.east < t.west or m.west > t.east
                   or m.north < t.south or m.south > t.north)
    assert overlap, "TERRAIN_AOI and MARINE_AOI do not overlap — one of them is wrong"
    print("  OK terrain and marine extents overlap at the coast")


if __name__ == "__main__":
    main()
