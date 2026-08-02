#!/usr/bin/env python
"""One-hour ERA5-Land access and download smoke test.

Requests exactly ONE variable at ONE timestamp over the Aqaba box, then
inspects the result. Proves Copernicus CDS authentication, licence acceptance
and NetCDF delivery before any production ingestion module is written.

Credentials are read by `cdsapi` from ~/.cdsapirc — never from .env, never
printed, never copied into the repository. No token, header or signed URL is
logged here.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import netCDF4
import numpy as np
import xarray as xr

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET = "reanalysis-era5-land"
VARIABLE = "volumetric_soil_water_layer_1"
YEAR, MONTH, DAY, TIME = "2016", "10", "27", "00:00"
# CDS area order is [North, West, South, East].

# The spatial contract lives in backend/src/config/spatial.py. Load it by
# location: this directory also contains a module called `config`, so a plain
# import by name is ambiguous.
def _spatial_contract():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "reefshield_spatial_contract",
        Path(__file__).resolve().parents[1] / "backend" / "src" / "config" / "spatial.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_AOI = _spatial_contract().TERRAIN_AOI

AREA = list(_AOI.cds_area)

DEST = PROJECT_ROOT / "data" / "raw" / "era5_land" / "smoke_test"
OUTPUT = DEST / "era5_land_soil_water_l1_20161027_0000.nc"

CDSAPIRC = Path.home() / ".cdsapirc"
HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"
CLASSIC_NETCDF_SIGNATURE = b"CDF"

# Names that are coordinates/bounds rather than science variables.
COORDINATE_NAMES = {
    "latitude", "longitude", "time", "valid_time", "number", "expver",
    "lat", "lon", "crs", "spatial_ref", "depthBelowLandLayer",
}

RULE = "=" * 72


def check_configuration() -> list[str]:
    """Structural checks on ~/.cdsapirc. Never reads out the token."""
    problems: list[str] = []
    if not CDSAPIRC.exists():
        problems.append(f"{CDSAPIRC} does not exist")
        return problems

    mode = oct(CDSAPIRC.stat().st_mode & 0o777)[2:]
    if mode != "600":
        problems.append(f"{CDSAPIRC} mode is {mode}, expected 600")

    text = CDSAPIRC.read_text()
    has_url = any(
        line.strip().startswith("url:")
        and "cds.climate.copernicus.eu/api" in line
        for line in text.splitlines()
    )
    has_key = any(
        line.strip().startswith("key:") and len(line.split(":", 1)[1].strip()) > 8
        for line in text.splitlines()
    )
    if not has_url:
        problems.append("no official 'url: https://cds.climate.copernicus.eu/api' line")
    if not has_key:
        problems.append("no non-empty 'key:' line")

    try:
        relative = CDSAPIRC.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        relative = None
    if relative is not None:
        problems.append(
            f"{CDSAPIRC} is INSIDE the repository — move it out of {PROJECT_ROOT}"
        )
    return problems


def data_raw_ignored() -> str | None:
    probe = "data/raw/era5_land/smoke_test/probe.nc"
    done = subprocess.run(
        ["git", "check-ignore", "-v", probe],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    return done.stdout.strip() if done.returncode == 0 else None


def file_signature(path: Path) -> tuple[str, bool]:
    head = path.read_bytes()[:8]
    if head.startswith(HDF5_SIGNATURE):
        return "HDF5 (NetCDF4)", True
    if head.startswith(CLASSIC_NETCDF_SIGNATURE):
        return "CDF (classic NetCDF)", True
    return repr(head[:8]), False


def describe(path: Path) -> int:
    signature, valid = file_signature(path)
    print(f"\n{RULE}\nFILE\n{RULE}")
    print(f"  2. output path        : {path}")
    print(f"  3. size               : {path.stat().st_size / 1024:.1f} KB")
    print(f"  4. exists / signature : {path.exists()} / {signature} "
          f"({'valid' if valid else 'INVALID'})")
    if not valid:
        return 1

    with netCDF4.Dataset(path, "r") as raw:
        groups = list(raw.groups)
    if groups:
        print(f"     netcdf groups      : {groups}")

    dataset = xr.open_dataset(path)
    try:
        print(f"\n{RULE}\nSTRUCTURE\n{RULE}")
        print(f"  5. dimensions         : {dict(dataset.sizes)}")
        print(f"  6. coordinates        : {sorted(map(str, dataset.coords))}")
        print(f"  7. data variables     : {sorted(map(str, dataset.data_vars))}")

        candidates = [
            name for name in dataset.data_vars
            if str(name).lower() in {"swvl1", "volumetric_soil_water_layer_1"}
            or "soil" in str(name).lower()
        ]
        if not candidates:
            candidates = list(dataset.data_vars)
        target = str(candidates[0])
        array = dataset[target]

        print(f"  8. soil-moisture var  : {target}")
        print(f"  9. dims / shape       : {tuple(array.dims)} / "
              f"{tuple(array.shape)}")

        time_name = next(
            (n for n in ("valid_time", "time") if n in dataset.coords), None
        )
        if time_name:
            values = np.atleast_1d(dataset[time_name].values)
            shown = [str(np.datetime_as_string(v, unit="s"))
                     if isinstance(v, np.datetime64) else str(v)
                     for v in values]
            print(f" 10. time value(s)     : {shown}  (coord {time_name!r})")
        else:
            print(" 10. time value(s)     : no time coordinate")

        lat_name = "latitude" if "latitude" in dataset.coords else "lat"
        lon_name = "longitude" if "longitude" in dataset.coords else "lon"
        lat = np.asarray(dataset[lat_name].values, dtype="float64")
        lon = np.asarray(dataset[lon_name].values, dtype="float64")
        print(f" 11. latitude range    : {lat.min():.3f} -> {lat.max():.3f} "
              f"(n={lat.size})")
        print(f" 12. longitude range   : {lon.min():.3f} -> {lon.max():.3f} "
              f"(n={lon.size})")

        units = array.attrs.get("units", array.attrs.get("Units", "not set"))
        print(f" 13. units             : {units}")

        fill = None
        for attribute in ("_FillValue", "missing_value"):
            if attribute in array.attrs:
                fill = array.attrs[attribute]
                break
        if fill is None:
            fill = array.encoding.get("_FillValue")
        print(f" 14. fill / missing    : "
              f"{fill if fill is not None else 'none declared'}  "
              f"(xarray masks to NaN on read)")

        values = np.asarray(array.values, dtype="float64")
        valid_values = values[np.isfinite(values)]
        print(f" 15. min / max / mean  : "
              f"{valid_values.min():.6f} / {valid_values.max():.6f} / "
              f"{valid_values.mean():.6f}"
              if valid_values.size else " 15. min / max / mean  : no valid data")
        print(f" 16. valid / missing   : {valid_values.size} / "
              f"{values.size - valid_values.size}")

        subsetted = (
            lat.min() >= AREA[2] - 0.5 and lat.max() <= AREA[0] + 0.5
            and lon.min() >= AREA[1] - 0.5 and lon.max() <= AREA[3] + 0.5
        )
        print(f" 17. spatially subset  : {'YES' if subsetted else 'NO'} "
              f"(requested N{AREA[0]} W{AREA[1]} S{AREA[2]} E{AREA[3]})")

        if lat.size > 1:
            order = "ASCENDING" if lat[1] > lat[0] else "DESCENDING"
        else:
            order = "single row — undetermined"
        print(f" 18. latitude order    : {order}")

        unrelated = sorted(
            str(n) for n in dataset.data_vars
            if str(n) != target and str(n).lower() not in COORDINATE_NAMES
        )
        print(f" 19. unrelated science : "
              f"{unrelated if unrelated else 'NONE — soil moisture only'}")
    finally:
        dataset.close()
    return 0


def main() -> int:
    print(f"\n{RULE}\nERA5-LAND ONE-HOUR SMOKE TEST\n{RULE}")

    problems = check_configuration()
    if problems:
        print("  CDS configuration invalid — nothing requested:")
        for item in problems:
            print(f"    - {item}")
        print("  See docs/data_access_setup.md section 2.")
        return 1
    print(f"  cdsapirc            : present, mode 600, official endpoint "
          f"(token not shown)")

    ignore_rule = data_raw_ignored()
    if not ignore_rule:
        print("  ABORT: data/raw is NOT ignored by Git. Nothing downloaded.")
        return 1
    print(f"  git ignore          : {ignore_rule}")

    DEST.mkdir(parents=True, exist_ok=True)
    existing = sorted(p.name for p in DEST.iterdir() if p.is_file())
    print(f"  existing files      : {len(existing)}"
          f"{' -> ' + str(existing) if existing else ''}")
    if OUTPUT.exists():
        print(f"  target already present ({OUTPUT.stat().st_size / 1024:.1f} KB)"
              " — reusing it, nothing deleted, nothing re-requested.")
        return describe(OUTPUT)

    request = {
        "variable": [VARIABLE],
        "year": YEAR,
        "month": MONTH,
        "day": DAY,
        "time": [TIME],
        "area": AREA,
        "data_format": "netcdf",
        "download_format": "unarchived",
    }
    print(f"\n  dataset             : {DATASET}")
    print(f"  variable            : {VARIABLE}")
    print(f"  timestamp           : {YEAR}-{MONTH}-{DAY} {TIME} UTC")
    print(f"  area [N, W, S, E]   : {AREA}")
    print("  submitting request ...", flush=True)

    # Imported here so a configuration failure never touches the client.
    import cdsapi

    try:
        client = cdsapi.Client()
        client.retrieve(DATASET, request, str(OUTPUT))
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        print(f"\n{RULE}\nREQUEST FAILED\n{RULE}")
        print(f"  {type(exc).__name__}: {message[:600]}")
        lowered = message.lower()
        if "licence" in lowered or "license" in lowered or "terms" in lowered:
            print("\n  This is a LICENCE ACCEPTANCE failure, not a code problem.")
            print("  Accept the ERA5-Land Terms of Use once, in a browser:")
            print("    https://cds.climate.copernicus.eu/datasets/"
                  "reanalysis-era5-land")
            print("  Then re-run this script unchanged. No workaround will be "
                  "implemented.")
        print(f"  1. request status     : FAILED")
        return 1

    print("  1. request status     : SUCCEEDED")
    status = describe(OUTPUT)

    print(f"\n{RULE}\nSAFETY\n{RULE}")
    files = sorted(p.name for p in DEST.iterdir() if p.is_file())
    print(f"  files in smoke_test   : {len(files)}")
    git_status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    ).stdout
    leaked = [ln for ln in git_status.splitlines()
              if ".nc" in ln.lower() or "era5" in ln.lower()]
    print(f"  git sees the NetCDF   : "
          f"{'YES -> ' + str(leaked) if leaked else 'NO'}")
    print(f"{RULE}\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
