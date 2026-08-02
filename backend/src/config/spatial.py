"""The spatial contract — the single source of truth for every bounding box.

Import from here. **Never write a bounding box literal anywhere else.**
`tests/test_spatial_contract.py` fails the build if you do.

Why this module exists
----------------------
Until 2 August 2026 seven modules each carried their own copy of

    (34.80, 29.25, 35.15, 29.70)

and that box was wrong by roughly 37x. Wadi Yutum drains from about 90 km
inland, out to 35.89 E, so the box cut off ~85 % of the catchment that
generates the event this project is built around. Nothing raised an error —
the downloads succeeded, they just covered the wrong area, which is the
failure mode `tasks/mahdi-blockers.md` §1 warns about: *"nothing throws an
error, the numbers just come out quietly wrong."*

The most likely consequence is already on record: `docs/event_dates.md`
notes that the derived rainfall peak falls *after* the documented flood
arrival, the opposite of the paper's ordering, and names this box as the
suspected cause.

The contract, per `tasks/00-contracts.md` §1
-------------------------------------------
The project needs **two extents, not one**:

    TERRAIN_AOI   land side. Must cover the FULL contributing catchments.
                  DEM, hydrology, rainfall, land cover, soil.

    MARINE_AOI    sea side. Must reach far enough seaward to hold a 24 h
                  plume. Currents, bathymetry, imagery, reef zones.

    AQABA_AOI     the union. Download against this or wider; clip to the
                  relevant extent at analysis time, not download time.

Ordering is a classic silent failure, so no caller ever reorders by hand —
ask the box for the ordering the API wants (`wsen`, `cds_area`, `nwse`).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AOI_DIR = PROJECT_ROOT / "data" / "aoi"


class BBox(NamedTuple):
    """A geographic bounding box in EPSG:4326 degrees.

    Stored west/south/east/north because that is the order
    `tasks/00-contracts.md` writes it in and the order `shapely.geometry.box`
    takes. Every other ordering is derived, never retyped.
    """

    west: float
    south: float
    east: float
    north: float

    @property
    def wsen(self) -> tuple[float, float, float, float]:
        """(west, south, east, north) — Harmony, shapely.box, rasterio."""
        return (self.west, self.south, self.east, self.north)

    @property
    def cds_area(self) -> list[float]:
        """[north, west, south, east] — Copernicus CDS `area`."""
        return [self.north, self.west, self.south, self.east]

    @property
    def nwse(self) -> tuple[float, float, float, float]:
        """(north, west, south, east) — some THREDDS/OPeNDAP helpers."""
        return (self.north, self.west, self.south, self.east)

    def contains(self, other: "BBox") -> bool:
        """True when `other` lies entirely inside this box."""
        return (
            self.west <= other.west
            and self.south <= other.south
            and self.east >= other.east
            and self.north >= other.north
        )

    def union(self, other: "BBox") -> "BBox":
        return BBox(
            min(self.west, other.west),
            min(self.south, other.south),
            max(self.east, other.east),
            max(self.north, other.north),
        )

    @property
    def span_deg(self) -> tuple[float, float]:
        """(longitude span, latitude span) in degrees."""
        return (self.east - self.west, self.north - self.south)

    def as_geojson_feature(self, name: str, note: str = "") -> dict:
        w, s, e, n = self
        return {
            "type": "Feature",
            "properties": {"name": name, "note": note, "bbox": [w, s, e, n]},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
            },
        }

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.west}, {self.south}, {self.east}, {self.north}"


# ---------------------------------------------------------------------------
# The contract. Changing a number here changes it everywhere, by design.
# ---------------------------------------------------------------------------

#: Land side. Derived from the delineated catchments by
#: ``scripts/02_provisional_catchments.py`` — measured, not guessed.
TERRAIN_AOI = BBox(34.75, 29.15, 35.94, 30.30)

#: Sea side. Hand-set in ``scripts/01_make_aoi.py``; must hold a 24 h plume.
MARINE_AOI = BBox(34.80, 29.25, 35.05, 29.60)

#: Download superset. Computed, never typed — see the assertion below.
AQABA_AOI = TERRAIN_AOI.union(MARINE_AOI)

#: Storage, exchange, GeoJSON, PostGIS.
CRS_STORAGE = "EPSG:4326"

#: UTM 36N. **Every** area, distance and slope calculation. An area in km²
#: computed from degrees is wrong; there are no exceptions.
CRS_MEASURE = "EPSG:32636"

#: The box this contract replaced, kept only so the guard test can recognise
#: it if someone pastes it back in. Never use it for anything.
RETIRED_BOX = (34.80, 29.25, 35.15, 29.70)

#: Committed contract files, per `tasks/00-contracts.md` §3.
AOI_FILES = {
    "terrain_aoi": AOI_DIR / "terrain_aoi.geojson",
    "marine_aoi": AOI_DIR / "marine_aoi.geojson",
    "aqaba_aoi": AOI_DIR / "aqaba_aoi.geojson",
}

# Structural invariants. These hold at import time so a bad edit fails loudly
# and immediately rather than producing quietly wrong downloads.
assert TERRAIN_AOI.contains(MARINE_AOI), (
    "MARINE_AOI must lie inside TERRAIN_AOI, or the union box stops being a "
    "superset and per-source clipping silently diverges."
)
assert AQABA_AOI.contains(TERRAIN_AOI) and AQABA_AOI.contains(MARINE_AOI)
assert TERRAIN_AOI.wsen != RETIRED_BOX and MARINE_AOI.wsen != RETIRED_BOX


class AOIFileMismatch(ValueError):
    """A committed AOI GeoJSON disagrees with the constants in this module."""


def load_aoi_bbox(name: str) -> BBox:
    """Read a committed AOI GeoJSON and return its bounding box.

    The GeoJSON files are what other people's tooling (QGIS, ``ogr2ogr
    -clipsrc``, Earth Engine) actually reads, so they are the half of the
    contract that lives outside Python. `verify_against_files()` keeps the
    two halves honest.
    """
    path = AOI_FILES.get(name)
    if path is None:
        raise KeyError(f"unknown AOI {name!r}; expected one of {sorted(AOI_FILES)}")
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. Regenerate it with scripts/01_make_aoi.py "
            "and scripts/02_provisional_catchments.py."
        )

    feature = json.loads(path.read_text())["features"][0]
    declared = feature.get("properties", {}).get("bbox")
    if declared:
        return BBox(*declared)

    ring = feature["geometry"]["coordinates"][0]
    lons = [pt[0] for pt in ring]
    lats = [pt[1] for pt in ring]
    return BBox(min(lons), min(lats), max(lons), max(lats))


def verify_against_files(tolerance: float = 1e-9) -> dict[str, BBox]:
    """Assert the committed GeoJSON files match the constants above.

    Raises `AOIFileMismatch` on any disagreement. Returns what was read, so a
    caller can log it.
    """
    expected = {
        "terrain_aoi": TERRAIN_AOI,
        "marine_aoi": MARINE_AOI,
        "aqaba_aoi": AQABA_AOI,
    }
    seen: dict[str, BBox] = {}
    for name, want in expected.items():
        got = load_aoi_bbox(name)
        seen[name] = got
        drift = [abs(a - b) for a, b in zip(got, want)]
        if max(drift) > tolerance:
            raise AOIFileMismatch(
                f"{AOI_FILES[name].name} says ({got}) but "
                f"config.spatial.{name.upper()} says ({want}). "
                "One of them was edited without the other — fix both before "
                "anyone downloads against the wrong extent."
            )
    return seen


__all__ = [
    "BBox",
    "TERRAIN_AOI",
    "MARINE_AOI",
    "AQABA_AOI",
    "CRS_STORAGE",
    "CRS_MEASURE",
    "RETIRED_BOX",
    "AOI_FILES",
    "AOIFileMismatch",
    "load_aoi_bbox",
    "verify_against_files",
]
