"""Guard: exactly one bounding box definition exists in this repository.

Phase 1 shipped seven independent copies of the same wrong box. Nothing
raised — the downloads succeeded, they just covered ~15 % of the catchment
that generates the demo event. These tests exist so that cannot recur.

They are deliberately **static**: they read source text rather than importing
the modules, because Nizar's forecast and current modules need `herbie`,
`ecmwf-opendata` and `copernicusmarine`, which are not installed in every
environment. A contract guard that only runs on a fully-provisioned machine
is not a guard.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from config.spatial import (  # noqa: E402
    AQABA_AOI,
    MARINE_AOI,
    RETIRED_BOX,
    TERRAIN_AOI,
    BBox,
    verify_against_files,
)

# Files allowed to mention the retired box, because their job is to name it:
# the contract module defines it so this guard can recognise it, and the docs
# and configs explain what it was and why it changed.
RETIRED_BOX_ALLOWLIST = {
    "backend/src/config/spatial.py",
    "scripts/config.py",
    "scripts/check_aoi_coverage.py",
    "tests/test_spatial_contract.py",
    "configs/october_2016_demo.yaml",
    "configs/event_pipeline.example.yaml",
    "configs/imerg_early_live_demo.yaml",
}

SEARCH_DIRS = ("backend", "scripts", "src", "configs", "tests")
SEARCH_SUFFIXES = {".py", ".yaml", ".yml"}


def _source_files() -> list[Path]:
    found: list[Path] = []
    for directory in SEARCH_DIRS:
        root = PROJECT_ROOT / directory
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix in SEARCH_SUFFIXES and "__pycache__" not in path.parts:
                found.append(path)
    return sorted(found)


# --------------------------------------------------------------------------
# The contract itself
# --------------------------------------------------------------------------


def test_marine_lies_inside_terrain():
    assert TERRAIN_AOI.contains(MARINE_AOI)


def test_union_is_computed_not_typed():
    assert AQABA_AOI == TERRAIN_AOI.union(MARINE_AOI)
    assert AQABA_AOI.contains(TERRAIN_AOI)
    assert AQABA_AOI.contains(MARINE_AOI)


def test_terrain_reaches_the_full_wadi_yutum_catchment():
    """AQ-C01 drains to 35.89 E and ~30.2 N; the box must enclose that."""
    assert TERRAIN_AOI.east >= 35.89
    assert TERRAIN_AOI.north >= 30.20


def test_retired_box_is_not_the_contract():
    assert TERRAIN_AOI.wsen != RETIRED_BOX
    assert MARINE_AOI.wsen != RETIRED_BOX
    assert AQABA_AOI.wsen != RETIRED_BOX


def test_committed_geojson_matches_the_constants():
    """The GeoJSON files are the half of the contract QGIS and ogr2ogr read."""
    verify_against_files()


# --------------------------------------------------------------------------
# Ordering helpers — reordering by hand is a classic silent failure
# --------------------------------------------------------------------------


def test_ordering_helpers():
    box = BBox(1.0, 2.0, 3.0, 4.0)
    assert box.wsen == (1.0, 2.0, 3.0, 4.0)      # Harmony / shapely
    assert box.cds_area == [4.0, 1.0, 2.0, 3.0]  # CDS: N, W, S, E
    assert box.nwse == (4.0, 1.0, 2.0, 3.0)
    assert box.span_deg == (2.0, 2.0)


def test_contains_is_inclusive_of_its_own_edges():
    assert TERRAIN_AOI.contains(TERRAIN_AOI)


# --------------------------------------------------------------------------
# No stray literals anywhere
# --------------------------------------------------------------------------


def test_no_source_file_reintroduces_the_retired_box():
    # 34.80 and 34.8 are the same number but not the same string, and a float
    # in an f-string renders as the short form — so match both spellings or
    # the guard silently misses half the ways someone can retype the box.
    def num(value: float) -> str:
        return re.escape(f"{value:g}") + r"0*"

    w, s, e, n = (num(v) for v in RETIRED_BOX)
    sep = r"\s*,\s*"
    patterns = [
        re.compile(rf"{w}{sep}{s}{sep}{e}{sep}{n}"),   # W, S, E, N
        re.compile(rf"{n}{sep}{w}{sep}{s}{sep}{e}"),   # CDS: N, W, S, E
    ]
    offenders = []
    for path in _source_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel in RETIRED_BOX_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(p.search(text) for p in patterns):
            offenders.append(rel)

    assert not offenders, (
        "The retired bounding box reappeared in: "
        + ", ".join(offenders)
        + ". Import TERRAIN_AOI or MARINE_AOI from config.spatial instead — "
        "see that module's docstring for what this box got wrong."
    )


@pytest.mark.parametrize(
    "module, symbol",
    [
        ("backend/src/ingestion/imerg.py", "TERRAIN_AOI"),
        ("backend/src/ingestion/era5_land.py", "TERRAIN_AOI"),
        ("backend/src/ingestion/gfs.py", "TERRAIN_AOI"),
        ("backend/src/ingestion/gefs.py", "TERRAIN_AOI"),
        ("backend/src/ingestion/ecmwf.py", "TERRAIN_AOI"),
        ("backend/src/ingestion/ocean_currents.py", "MARINE_AOI"),
    ],
)
def test_every_ingestion_module_derives_its_extent(module, symbol):
    """Each module must take its box from the contract, not retype one."""
    text = (PROJECT_ROOT / module).read_text(encoding="utf-8")
    assert f"from config.spatial import {symbol}" in text, (
        f"{module} does not import {symbol} from the spatial contract."
    )
    literal = re.compile(r"^(DOWNLOAD_BBOX|AREA)\s*=\s*[\[(]\s*-?\d", re.M)
    assert not literal.search(text), (
        f"{module} assigns a bounding-box literal. Derive it from {symbol}."
    )


def test_ocean_currents_uses_the_marine_extent_not_the_terrain_one():
    """The sea side is a different box, and mixing them is a real error."""
    text = (PROJECT_ROOT / "backend/src/ingestion/ocean_currents.py").read_text()
    assert "MARINE_AOI" in text
    assert "TERRAIN_AOI" not in text


# --------------------------------------------------------------------------
# Configs
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "config_name",
    [
        "october_2016_demo.yaml",
        "event_pipeline.example.yaml",
        "imerg_early_live_demo.yaml",
    ],
)
def test_configs_declare_the_terrain_extent(config_name):
    spatial = yaml.safe_load((PROJECT_ROOT / "configs" / config_name).read_text())["spatial"]
    box = BBox(spatial["west"], spatial["south"], spatial["east"], spatial["north"])
    assert box == TERRAIN_AOI, (
        f"configs/{config_name} declares {box}, contract says {TERRAIN_AOI}."
    )
