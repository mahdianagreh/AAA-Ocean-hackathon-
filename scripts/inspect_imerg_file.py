#!/usr/bin/env python
"""Inspect one IMERG HDF5 granule and test-slice the Aqaba padded box.

Read-only: opens the file with mode="r", writes nothing, saves nothing,
downloads nothing. Structure is discovered rather than hard-coded, so the
report stays honest if NASA changes the layout between versions.

    python scripts/inspect_imerg_file.py [path/to/granule.HDF5]
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import h5py
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILE = (
    PROJECT_ROOT
    / "data/raw/imerg/smoke_test"
    / "3B-HHR.MS.MRG.3IMERG.20161025-S000000-E002959.0000.V07B.HDF5"
)

# Aqaba padded box from the project contract
WEST, SOUTH, EAST, NORTH = 34.80, 29.25, 35.15, 29.70

RULE = "=" * 72


def decode(value):
    """HDF5 attributes come back as bytes or arrays; make them printable."""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, np.ndarray):
        if value.size == 1:
            return decode(value.item())
        return [decode(v) for v in value.tolist()]
    return value


def walk(h5obj, indent: int = 1) -> None:
    """Recursively print groups and datasets."""
    pad = "  " * indent
    for key, item in h5obj.items():
        if isinstance(item, h5py.Group):
            print(f"{pad}[group]   {item.name}")
            walk(item, indent + 1)
        else:
            print(f"{pad}[dataset] {item.name}  shape={item.shape} "
                  f"dtype={item.dtype}")


def collect_datasets(root) -> dict[str, h5py.Dataset]:
    found: dict[str, h5py.Dataset] = {}

    def visitor(name, obj):
        if isinstance(obj, h5py.Dataset):
            found[obj.name] = obj

    root.visititems(visitor)
    return found


def find(datasets: dict[str, h5py.Dataset], *candidates: str) -> str | None:
    """First dataset whose basename matches a candidate, case-insensitively."""
    lowered = {path: path.rsplit("/", 1)[-1].lower() for path in datasets}
    for candidate in candidates:
        for path, base in lowered.items():
            if base == candidate.lower():
                return path
    return None


def describe(dset: h5py.Dataset, label: str) -> None:
    print(f"  {label}")
    print(f"    path  : {dset.name}")
    print(f"    shape : {dset.shape}    dtype: {dset.dtype}")
    interesting = ("units", "Units", "_FillValue", "CodeMissingValue",
                   "scale_factor", "add_offset", "long_name", "LongName",
                   "DimensionNames", "standard_name")
    for attr in interesting:
        if attr in dset.attrs:
            print(f"    {attr:<15}: {decode(dset.attrs[attr])}")


def granule_timestamp(root, time_path: str | None, filename: str) -> None:
    print("  Granule timestamp")
    if time_path:
        tds = root[time_path]
        raw = np.atleast_1d(tds[...])
        units = decode(tds.attrs.get("units", b"")) or "(no units attribute)"
        print(f"    time values    : {raw.tolist()}")
        print(f"    time units     : {units}")
        # IMERG uses "seconds since 1980-01-06 00:00:00 UTC"
        if "since" in str(units):
            try:
                stamp = str(units).split("since", 1)[1].strip()
                stamp = stamp.replace("Z", "").replace(" UTC", "").strip()
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
                            "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
                    try:
                        epoch = datetime.strptime(stamp, fmt).replace(
                            tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError(f"unparsed epoch: {stamp!r}")
                unit_word = str(units).split()[0].lower()
                factor = {"seconds": 1, "minutes": 60,
                          "hours": 3600, "days": 86400}[unit_word]
                for value in raw.tolist():
                    resolved = epoch + timedelta(seconds=float(value) * factor)
                    print(f"    decoded UTC    : "
                          f"{resolved.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            except Exception as exc:  # noqa: BLE001
                print(f"    could not decode epoch ({exc})")
    else:
        print("    no time dataset present")

    # The filename carries the authoritative window: SHHMMSS-EHHMMSS
    for part in filename.split("."):
        if part.startswith("2") and "-S" in part:
            date, start, end = part.split("-")[0], "", ""
            pieces = part.split("-")
            start = pieces[1][1:] if len(pieces) > 1 else ""
            end = pieces[2][1:] if len(pieces) > 2 else ""
            print(f"    from filename  : {date[:4]}-{date[4:6]}-{date[6:8]} "
                  f"{start[:2]}:{start[2:4]}:{start[4:6]} -> "
                  f"{end[:2]}:{end[2:4]}:{end[4:6]} UTC (30-minute window)")
            break


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FILE
    if not path.exists():
        print(f"File not found: {path}")
        return 1

    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"\n{RULE}\nIMERG HDF5 INSPECTION (read-only)\n{RULE}")
    print(f"  file : {path.name}")
    print(f"  size : {size_mb:.2f} MB")

    with h5py.File(path, "r") as root:   # read-only: file is never altered
        print(f"\n{RULE}\n1. STRUCTURE\n{RULE}")
        top = list(root.keys())
        print(f"  Top-level groups: {top}")
        print("\n  Full tree:")
        walk(root)

        datasets = collect_datasets(root)
        precip_path = find(datasets, "precipitation", "precipitationCal")
        lat_path = find(datasets, "lat", "latitude")
        lon_path = find(datasets, "lon", "longitude")
        time_path = find(datasets, "time")

        print(f"\n{RULE}\n2. KEY DATASETS\n{RULE}")
        if not (precip_path and lat_path and lon_path):
            print("  Could not locate precipitation/lat/lon datasets.")
            return 1
        describe(root[precip_path], "Precipitation")
        describe(root[lat_path], "Latitude")
        describe(root[lon_path], "Longitude")
        if time_path:
            describe(root[time_path], "Time")
        else:
            print("  Time: not present")

        print()
        granule_timestamp(root, time_path, path.name)

        # --- geometry -----------------------------------------------------
        lat = root[lat_path][...].astype("float64")
        lon = root[lon_path][...].astype("float64")
        precip = root[precip_path]

        print(f"\n{RULE}\n3. GRID EXTENT\n{RULE}")
        print(f"  latitude  : min {lat.min():>8.3f}  max {lat.max():>8.3f}  "
              f"n={lat.size}  step={abs(lat[1] - lat[0]):.3f}")
        print(f"  longitude : min {lon.min():>8.3f}  max {lon.max():>8.3f}  "
              f"n={lon.size}  step={abs(lon[1] - lon[0]):.3f}")

        global_lat = lat.min() <= -89.0 and lat.max() >= 89.0
        global_lon = lon.min() <= -179.0 and lon.max() >= 179.0
        verdict = ("GLOBAL — the download was NOT spatially subset"
                   if global_lat and global_lon
                   else "already spatially subset")
        print(f"  coverage  : {verdict}")

        # --- axis order ---------------------------------------------------
        dim_names = decode(precip.attrs.get("DimensionNames", b""))
        squeezed = [n for n in precip.shape if n != 1]
        lat_first = (len(squeezed) >= 2
                     and squeezed[0] == lat.size and squeezed[1] == lon.size)
        lon_first = (len(squeezed) >= 2
                     and squeezed[0] == lon.size and squeezed[1] == lat.size)

        print(f"\n{RULE}\n4. AXIS ORDER\n{RULE}")
        print(f"  precipitation shape   : {precip.shape}")
        print(f"  DimensionNames attr   : {dim_names}")
        print(f"  lat size {lat.size}, lon size {lon.size}")
        if lon_first:
            print("  layout                : (time, LON, LAT)")
            print("  TRANSPOSE NEEDED      : YES — .T after squeeze to get "
                  "(lat, lon)")
        elif lat_first:
            print("  layout                : (time, LAT, LON)")
            print("  TRANSPOSE NEEDED      : NO — already (lat, lon)")
        else:
            print("  layout                : UNRECOGNISED — inspect manually")

        # --- Aqaba box slice (in memory only) -----------------------------
        lat_idx = np.where((lat >= SOUTH) & (lat <= NORTH))[0]
        lon_idx = np.where((lon >= WEST) & (lon <= EAST))[0]

        print(f"\n{RULE}\n5. AQABA PADDED BOX EXTRACTION (in memory only)\n{RULE}")
        print(f"  requested box         : W {WEST}  S {SOUTH}  "
              f"E {EAST}  N {NORTH}")
        print(f"  longitude cells       : {lon_idx.size}")
        print(f"  latitude cells        : {lat_idx.size}")

        if lat_idx.size == 0 or lon_idx.size == 0:
            print("  box selects no cells — check the coordinate convention")
            return 1

        print(f"  selected lat range    : {lat[lat_idx].min():.3f} -> "
              f"{lat[lat_idx].max():.3f}")
        print(f"  selected lon range    : {lon[lon_idx].min():.3f} -> "
              f"{lon[lon_idx].max():.3f}")

        # Slice with the file's native order, then normalise to (lat, lon).
        lo_s = slice(int(lon_idx[0]), int(lon_idx[-1]) + 1)
        la_s = slice(int(lat_idx[0]), int(lat_idx[-1]) + 1)
        if lon_first:
            block = precip[0, lo_s, la_s] if precip.ndim == 3 \
                else precip[lo_s, la_s]
            subset = np.asarray(block).T          # -> (lat, lon)
        else:
            block = precip[0, la_s, lo_s] if precip.ndim == 3 \
                else precip[la_s, lo_s]
            subset = np.asarray(block)

        print(f"  subset shape (lat,lon): {subset.shape}")

        fill = precip.attrs.get("_FillValue",
                                precip.attrs.get("CodeMissingValue"))
        fill_value = float(decode(fill)) if fill is not None else None
        data = subset.astype("float64")
        valid_mask = np.isfinite(data)
        if fill_value is not None:
            valid_mask &= ~np.isclose(data, fill_value)
        valid = data[valid_mask]

        print(f"  fill value            : {fill_value}")
        print(f"  valid cells           : {valid.size} of {data.size}")
        if valid.size:
            units = decode(precip.attrs.get("units",
                           precip.attrs.get("Units", b""))) or "unknown"
            print(f"  min precipitation     : {valid.min():.4f} {units}")
            print(f"  max precipitation     : {valid.max():.4f} {units}")
            print(f"  mean precipitation    : {valid.mean():.4f} {units}")
        else:
            print("  all cells are fill/missing in this 30-minute window")

        print(f"\n{RULE}\n6. FOR FUTURE INGESTION CODE\n{RULE}")
        print(f"  precipitation dataset : {precip_path}")
        print(f"  latitude dataset      : {lat_path}")
        print(f"  longitude dataset     : {lon_path}")
        print(f"  time dataset          : {time_path or '(none)'}")
        order = "(time, lon, lat) -> transpose to (lat, lon)" if lon_first \
            else "(time, lat, lon) -> no transpose"
        print(f"  read order            : {order}")
        print(f"{RULE}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
