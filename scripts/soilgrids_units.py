"""SoilGrids unit conversion — isolated here so the unit test and the pipeline
share exactly one definition of the factors.

SoilGrids v2.0 ships every property as a scaled integer. Applying the wrong
divisor is the classic silent 10x error: nothing crashes, the rasters look fine,
and the erodibility ranking handed to the runoff model is quietly meaningless.

Factors below are the documented ISRIC mapped-units divisors. They are asserted
against the data itself in tests/test_soilgrids_units.py rather than trusted —
the texture-sum identity (clay + sand + silt = 100%) pins the texture divisor
exactly, because a 10x error would land the sum at 1000 or 10 instead of 100.
"""

import numpy as np
import rasterio

# RAW is re-exported so callers (and tests) can locate data/raw/soilgrids without
# importing the settings module themselves.
#
# origin/main carried an importlib-by-path shim here to dodge a name collision:
# `from config import RAW` resolved to whichever `config` landed on sys.path first,
# and backend/src has a `config` package, so under pytest it picked the wrong one.
# That workaround is no longer needed — the ambiguity was removed at the root by
# renaming this chain's settings module to `pulga_config`. See conftest.py.
from pulga_config import RAW

# variable -> (divisor, converted unit, plausible physical range after conversion)
CONVERSIONS = {
    "clay": (10.0, "%", (0.0, 100.0)),
    "sand": (10.0, "%", (0.0, 100.0)),
    "silt": (10.0, "%", (0.0, 100.0)),
    "soc": (10.0, "g/kg", (0.0, 600.0)),
    "bdod": (100.0, "kg/dm3", (0.1, 2.5)),
    "cfvo": (10.0, "vol%", (0.0, 100.0)),
}

DEPTHS = ["0-5cm", "5-15cm"]

# The WCS GeoTIFFs arrive with NO nodata tag declared, yet 25.5% of cells are
# exactly 0 — matching the sea fraction of the AOI. Those are nodata, not soil
# with zero clay. Left unmasked they would drag every catchment mean toward zero.
UNDECLARED_NODATA = 0


def raw_path(variable: str, depth: str):
    return RAW / "soilgrids" / f"{variable}_{depth}_mean.tif"


def load_converted(variable: str, depth: str):
    """Return (converted_array_float32_with_nan, profile). NaN = no data."""
    if variable not in CONVERSIONS:
        raise KeyError(f"unknown SoilGrids variable {variable!r}")
    divisor, _, _ = CONVERSIONS[variable]

    with rasterio.open(raw_path(variable, depth)) as src:
        raw = src.read(1)
        profile = src.profile.copy()

    arr = raw.astype("float32")
    arr[raw == UNDECLARED_NODATA] = np.nan
    return arr / divisor, profile
