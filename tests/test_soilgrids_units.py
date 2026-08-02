"""Unit-conversion tests for SoilGrids — the check the risk register calls for.

Run:  .venv/bin/python tests/test_soilgrids_units.py

The important test is test_texture_sums_to_100. Clay + sand + silt is a closed
composition and must sum to 100% by definition, which pins the texture divisor
exactly: get it wrong by 10x and the sum lands at 1000 or 10. That turns "the
docs say divide by 10" into something actually verified against the data.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from soilgrids_units import CONVERSIONS, DEPTHS, RAW, load_converted  # noqa: E402

# The SoilGrids rasters are git-ignored (~250 m x 12 variables), so they exist
# only on a machine that has run scripts/download_soilgrids.py. Absent data is
# a skip, not a failure — the same convention the other data-dependent suites
# in this repo use, so a fresh clone still reports green.
_SOILGRIDS_PRESENT = (RAW / "soilgrids").is_dir() and any(
    (RAW / "soilgrids").glob("*.tif")
)

try:  # pytest is optional: this file is also run directly, per its docstring
    import pytest

    pytestmark = pytest.mark.skipif(
        not _SOILGRIDS_PRESENT,
        reason=("SoilGrids rasters absent — run scripts/download_soilgrids.py. "
                "They are git-ignored, so this is expected on a fresh clone."),
    )
except ImportError:  # pragma: no cover
    pytest = None

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILURES.append(name)


def test_texture_sums_to_100():
    """clay + sand + silt == 100%. Pins the texture divisor exactly."""
    for depth in DEPTHS:
        clay, _ = load_converted("clay", depth)
        sand, _ = load_converted("sand", depth)
        silt, _ = load_converted("silt", depth)
        total = clay + sand + silt
        valid = total[~np.isnan(total)]
        median = float(np.median(valid))
        check(
            f"texture sum at {depth} is ~100% (median {median:.2f})",
            95.0 <= median <= 105.0,
            f"median {median:.2f} — a 10x divisor error would show ~1000 or ~10",
        )


def test_ranges_are_physically_plausible():
    """Every converted variable must land inside its documented physical range."""
    for variable, (divisor, unit, (lo, hi)) in CONVERSIONS.items():
        for depth in DEPTHS:
            arr, _ = load_converted(variable, depth)
            valid = arr[~np.isnan(arr)]
            amin, amax = float(valid.min()), float(valid.max())
            check(
                f"{variable} {depth} within [{lo}, {hi}] {unit} "
                f"(observed {amin:.2f}-{amax:.2f})",
                lo <= amin and amax <= hi,
                f"divisor {divisor} looks wrong",
            )


def test_nodata_is_masked_not_zero():
    """The undeclared 0 nodata must become NaN, not a real zero measurement."""
    for variable in CONVERSIONS:
        arr, _ = load_converted(variable, "0-5cm")
        n_nan = int(np.isnan(arr).sum())
        check(
            f"{variable} 0-5cm has masked nodata ({n_nan} NaN cells)",
            n_nan > 0 and not (arr[~np.isnan(arr)] == 0).all(),
            "expected the sea cells to be NaN",
        )


def test_arid_soil_is_low_in_organic_carbon():
    """Sanity check against the region, not just against the units.

    Hyper-arid desert soil carries very little organic carbon. If soc came back
    at temperate-grassland levels, the divisor or the variable would be wrong.
    """
    soc, _ = load_converted("soc", "0-5cm")
    valid = soc[~np.isnan(soc)]
    median = float(np.median(valid))
    check(
        f"soc 0-5cm median is low for desert soil ({median:.2f} g/kg)",
        median < 30.0,
        f"median {median:.2f} g/kg is too high for hyper-arid Aqaba",
    )


if __name__ == "__main__":
    print("SoilGrids unit-conversion tests\n")
    test_texture_sums_to_100()
    test_ranges_are_physically_plausible()
    test_nodata_is_masked_not_zero()
    test_arid_soil_is_low_in_organic_carbon()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        sys.exit(1)
    print("all SoilGrids unit conversions verified")
