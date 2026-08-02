#!/usr/bin/env python
"""One-granule NASA Harmony spatial + variable subset smoke test.

Requests ONLY Grid/precipitation inside the Aqaba padded box for a single
30-minute granule, downloads the NetCDF result, inspects it, and compares
the values against the already-downloaded global HDF5 granule.

Credentials are read from the repository-root .env and held in memory only.
Nothing sensitive is printed: no credentials, tokens, cookies, auth headers,
signed URLs, or complete Harmony result URLs — only bare filenames.

Writes nothing outside data/raw/imerg/harmony_smoke_test/.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import netCDF4
import numpy as np
from dotenv import load_dotenv
from harmony import BBox, Client, Collection, Request

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# --- authentication: .env only, variable names unchanged ----------------
load_dotenv(PROJECT_ROOT / ".env", override=False)
USERNAME = (os.getenv("EARTHDATA_USERNAME") or "").strip()
PASSWORD = (os.getenv("EARTHDATA_PASSWORD") or "").strip()

# --- request parameters ------------------------------------------------
CONCEPT_ID = "C2723754847-GES_DISC"

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

WEST, SOUTH, EAST, NORTH = _AOI.wsen
START = datetime(2016, 10, 25, 0, 0, 0, tzinfo=timezone.utc)
STOP = datetime(2016, 10, 25, 0, 29, 59, tzinfo=timezone.utc)
VARIABLE_PATH = "Grid/precipitation"
OUTPUT_FORMAT = "application/netcdf"
MAX_RESULTS = 1

DEST = PROJECT_ROOT / "data" / "raw" / "imerg" / "harmony_smoke_test"
CAPABILITIES = PROJECT_ROOT / "docs" / "imerg_harmony_capabilities.json"
GLOBAL_HDF5 = (
    PROJECT_ROOT / "data/raw/imerg/smoke_test"
    / "3B-HHR.MS.MRG.3IMERG.20161025-S000000-E002959.0000.V07B.HDF5"
)

RULE = "=" * 70
FILL_SENTINEL = -9999.9

# Names that are coordinates/bounds rather than science variables.
COORDINATE_NAMES = {
    "lat", "latitude", "lon", "longitude", "time",
    "lat_bnds", "lon_bnds", "time_bnds", "latv", "lonv", "nv",
    "crs", "spatial_ref",
}


def variable_concept_id(path: str) -> str | None:
    """Exact variable concept ID for `path`, from the saved capabilities."""
    if not CAPABILITIES.exists():
        return None
    payload = json.loads(CAPABILITIES.read_text())
    for entry in payload.get("variables") or []:
        if isinstance(entry, dict) and entry.get("name") == path:
            href = entry.get("href") or ""
            return href.rsplit("/", 1)[-1] or None
    return None


def data_raw_ignored() -> str | None:
    probe = "data/raw/imerg/harmony_smoke_test/probe.nc"
    result = subprocess.run(
        ["git", "check-ignore", "-v", probe],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def build_request(variables: list[str]) -> Request:
    return Request(
        collection=Collection(id=CONCEPT_ID),
        spatial=BBox(WEST, SOUTH, EAST, NORTH),
        temporal={"start": START, "stop": STOP},
        variables=variables,
        max_results=MAX_RESULTS,
        format=OUTPUT_FORMAT,
        concatenate=False,
    )


def submit_and_download(client: Client, request: Request) -> tuple[list[Path], str]:
    """Submit, wait, download. Returns (paths, sync-or-async description)."""
    job_id = client.submit(request)
    if not job_id:
        return [], "direct/synchronous result (no job id returned)"

    mode = "asynchronous job (Harmony returned a job id)"
    client.wait_for_processing(job_id, show_progress=False)

    DEST.mkdir(parents=True, exist_ok=True)
    futures = client.download_all(job_id, directory=str(DEST), overwrite=True)
    paths = [Path(f.result()) for f in futures]
    return paths, mode


def inspect_netcdf(path: Path) -> dict:
    """Pull structure and the precipitation field out of the NetCDF result."""
    info: dict = {"groups": [], "variables": [], "precip_path": None}

    with netCDF4.Dataset(path, "r") as ds:
        def walk(group, prefix=""):
            for name, var in group.variables.items():
                full = f"{prefix}/{name}".lstrip("/")
                info["variables"].append(
                    {"path": full, "name": name,
                     "shape": tuple(var.shape),
                     "dims": tuple(var.dimensions),
                     "dtype": str(var.dtype)}
                )
                if "precip" in name.lower() and info["precip_path"] is None:
                    info["precip_path"] = full
            for sub_name, sub in group.groups.items():
                sub_full = f"{prefix}/{sub_name}".lstrip("/")
                info["groups"].append(sub_full)
                walk(sub, sub_full)

        walk(ds)

        def resolve(full_path: str):
            node = ds
            parts = full_path.split("/")
            for part in parts[:-1]:
                node = node.groups[part]
            return node.variables[parts[-1]]

        # coordinates
        for key, needles in (("lat", ("lat", "latitude")),
                             ("lon", ("lon", "longitude"))):
            for entry in info["variables"]:
                if entry["name"].lower() in needles:
                    values = np.asarray(resolve(entry["path"])[...],
                                        dtype="float64").ravel()
                    info[f"{key}_range"] = (float(values.min()),
                                            float(values.max()))
                    info[f"{key}_n"] = int(values.size)
                    info[f"{key}_values"] = values
                    break

        if info["precip_path"]:
            pvar = resolve(info["precip_path"])
            info["precip_shape"] = tuple(pvar.shape)
            info["precip_dims"] = tuple(pvar.dimensions)
            info["precip_units"] = getattr(pvar, "units",
                                           getattr(pvar, "Units", None))
            fill = None
            for attr in ("_FillValue", "CodeMissingValue", "missing_value"):
                if hasattr(pvar, attr):
                    fill = float(np.asarray(getattr(pvar, attr)).ravel()[0])
                    break
            info["precip_fill"] = fill
            arr = np.asarray(pvar[...], dtype="float64")
            info["precip_values"] = np.squeeze(arr)

    return info


def aqaba_cells_from_global() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(precip[lat,lon], lat, lon) for the Aqaba box, from the global HDF5."""
    import h5py

    with h5py.File(GLOBAL_HDF5, "r") as f:      # read-only; file untouched
        lat = f["/Grid/lat"][...].astype("float64")
        lon = f["/Grid/lon"][...].astype("float64")
        la = np.where((lat >= SOUTH) & (lat <= NORTH))[0]
        lo = np.where((lon >= WEST) & (lon <= EAST))[0]
        block = f["/Grid/precipitation"][
            0, int(lo[0]):int(lo[-1]) + 1, int(la[0]):int(la[-1]) + 1
        ]
    return np.asarray(block).T, lat[la], lon[lo]   # -> (lat, lon)


def main() -> int:
    print(f"\n{RULE}\nHARMONY ONE-GRANULE SUBSET SMOKE TEST\n{RULE}")

    if not (USERNAME and PASSWORD):
        print("  EARTHDATA_USERNAME / EARTHDATA_PASSWORD missing from .env")
        return 1
    print("  credentials : loaded from .env (held in memory only)")

    ignore_rule = data_raw_ignored()
    if not ignore_rule:
        print("  data/raw is NOT ignored by Git — aborting before download.")
        return 1
    print(f"  git ignore  : {ignore_rule}")

    client = Client(auth=(USERNAME, PASSWORD))

    # --- 1. validation ------------------------------------------------
    request = build_request([VARIABLE_PATH])
    valid = request.is_valid()
    print(f"\n  1. request.is_valid()      : {valid}")
    if not valid:
        print(f"     messages: {request.error_messages()}")
        return 1

    # --- submit, with a single concept-ID retry -----------------------
    variable_used = VARIABLE_PATH
    try:
        paths, mode = submit_and_download(client, request)
    except Exception as exc:  # noqa: BLE001
        print(f"     Harmony rejected variable {VARIABLE_PATH!r}: "
              f"{type(exc).__name__}")
        concept = variable_concept_id(VARIABLE_PATH)
        if not concept:
            print("     No variable concept ID available — not retrying.")
            return 1
        print(f"     retrying once with variable concept ID {concept}")
        variable_used = concept
        retry = build_request([concept])
        if not retry.is_valid():
            print(f"     retry invalid: {retry.error_messages()}")
            return 1
        paths, mode = submit_and_download(client, retry)

    print(f"  2. result mode            : {mode}")
    print(f"     variable requested     : {variable_used}")

    files = [p for p in paths if p.exists()]
    print(f"  3. files downloaded       : {len(files)}")
    if not files:
        print("     nothing landed on disk")
        return 1

    out = files[0]
    size_kb = out.stat().st_size / 1024
    print(f"  4. output path            : {out}")
    print(f"  5. output size            : {size_kb:.1f} KB")

    # --- inspect ------------------------------------------------------
    info = inspect_netcdf(out)

    print(f"\n{RULE}\nNETCDF STRUCTURE\n{RULE}")
    print(f"  6. groups                 : "
          f"{info['groups'] or ['(root only)']}")
    print("     variables              :")
    for entry in info["variables"]:
        print(f"       - {entry['path']:<28} shape={entry['shape']} "
              f"dims={entry['dims']} {entry['dtype']}")

    print(f"\n  7. precipitation path     : {info['precip_path']}")
    print(f"  8. precip shape / dims    : {info.get('precip_shape')} / "
          f"{info.get('precip_dims')}")
    lat_rng = info.get("lat_range")
    lon_rng = info.get("lon_range")
    print(f"  9. latitude range         : "
          f"{lat_rng[0]:.3f} -> {lat_rng[1]:.3f}  (n={info.get('lat_n')})"
          if lat_rng else "  9. latitude range         : not present")
    print(f" 10. longitude range        : "
          f"{lon_rng[0]:.3f} -> {lon_rng[1]:.3f}  (n={info.get('lon_n')})"
          if lon_rng else " 10. longitude range        : not present")
    print(f" 11. precipitation units    : {info.get('precip_units')}")
    print(f" 12. fill value             : {info.get('precip_fill')}")

    subsetted = bool(
        lat_rng and lon_rng
        and lat_rng[0] >= SOUTH - 0.1 and lat_rng[1] <= NORTH + 0.1
        and lon_rng[0] >= WEST - 0.1 and lon_rng[1] <= EAST + 0.1
    )
    print(f" 13. spatially subsetted    : {'YES' if subsetted else 'NO'}")
    print(f" 14. coords auto-included   : "
          f"{'YES' if lat_rng and lon_rng else 'NO'}")

    science = [
        e["name"] for e in info["variables"]
        if e["name"].lower() not in COORDINATE_NAMES
        and "precip" not in e["name"].lower()
    ]
    print(f" 15. unrelated science vars : "
          f"{science if science else 'NONE — precipitation only'}")

    # --- comparison with the global HDF5 ------------------------------
    print(f"\n{RULE}\nCOMPARISON WITH GLOBAL HDF5\n{RULE}")
    ref, ref_lat, ref_lon = aqaba_cells_from_global()
    harmony = np.asarray(info.get("precip_values"))
    print(f"  global HDF5 Aqaba block   : {ref.shape} (lat, lon)")
    print(f"  harmony subset block      : {harmony.shape}")

    # Align orientation: Harmony may emit (lon, lat) like the source file.
    candidate = harmony
    if candidate.shape != ref.shape and candidate.T.shape == ref.shape:
        candidate = candidate.T
        print("  note                      : transposed Harmony block to "
              "match (lat, lon)")

    if candidate.shape != ref.shape:
        print("  shapes differ — comparing the overlapping top-left region")
        rows = min(candidate.shape[0], ref.shape[0])
        cols = min(candidate.shape[1], ref.shape[1])
        candidate = candidate[:rows, :cols]
        ref = ref[:rows, :cols]

    both_valid = (
        np.isfinite(candidate) & np.isfinite(ref)
        & ~np.isclose(candidate, FILL_SENTINEL, atol=0.5)
        & ~np.isclose(ref, FILL_SENTINEL, atol=0.5)
    )
    comparable = int(both_valid.sum())
    print(f"  comparable cells          : {comparable}")
    if comparable:
        diff = np.abs(candidate[both_valid] - ref[both_valid])
        max_diff = float(diff.max())
        tol = float(np.finfo(np.float32).eps) * max(
            1.0, float(np.abs(ref[both_valid]).max())
        )
        within = bool(np.allclose(candidate[both_valid], ref[both_valid],
                                 rtol=1e-6, atol=1e-6))
        print(f"  max absolute difference   : {max_diff:.10g}")
        print(f"  float32 tolerance used    : rtol=1e-6, atol=1e-6 "
              f"(eps-scaled ref: {tol:.3g})")
        print(f"  all values match          : {'YES' if within else 'NO'}")
    else:
        print("  no comparable cells — cannot verify values")

    # --- safety --------------------------------------------------------
    print(f"\n{RULE}\nSAFETY\n{RULE}")
    downloaded = sorted(p.name for p in DEST.iterdir() if p.is_file())
    print(f"  files in harmony_smoke_test: {len(downloaded)} -> {downloaded}")
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    ).stdout
    leaked = [ln for ln in status.splitlines()
              if ".nc" in ln.lower() or "harmony_smoke_test" in ln]
    print(f"  git sees downloaded data   : "
          f"{'YES -> ' + str(leaked) if leaked else 'NO'}")
    print(f"{RULE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
