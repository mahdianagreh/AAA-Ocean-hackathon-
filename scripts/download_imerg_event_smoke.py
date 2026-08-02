#!/usr/bin/env python
"""Download and validate the documented 3-hour IMERG smoke-test window.

Window comes from the timing contract in ``docs/event_dates.md``
(``smoke_test_3h_window_utc``), parsed at runtime so this script cannot
drift from the contract. That window is a PIPELINE TEST window — it is
explicitly not the event's wettest 3 hours.

Proves multi-granule Harmony downloads work. Performs NO aggregation and
NO rolling-window maths.

Nothing sensitive is printed: no credentials, tokens, cookies, auth headers,
or Harmony result URLs — only local filenames.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

from ingestion.imerg import (  # noqa: E402
    DOWNLOAD_BBOX,
    download_imerg_subset,
    read_imerg_subset,
)

CONTRACT = PROJECT_ROOT / "docs" / "event_dates.md"
DEST = PROJECT_ROOT / "data" / "raw" / "imerg" / "event_smoke_3h"

# Fallback values, kept in sync with docs/event_dates.md ->
# primary_event.engineering.smoke_test_3h_window_utc
FALLBACK_START = "2016-10-27T03:00:00Z"
FALLBACK_END = "2016-10-27T05:59:59Z"

EXPECTED_FILES = 6
EXPECTED_SHAPE = (1, 5, 4)
EXPECTED_FIRST = "2016-10-27T03:00:00"
EXPECTED_LAST = "2016-10-27T05:30:00"
GRANULE_MINUTES = 30

ALLOWED_NAMES = {
    "precipitation", "lat", "lon", "time",
    "lat_bnds", "lon_bnds", "time_bnds", "latv", "lonv", "nv",
    "crs", "spatial_ref",
}

RULE = "=" * 72


def read_window_from_contract() -> tuple[str, str, str]:
    """Parse smoke_test_3h_window_utc from docs/event_dates.md.

    Returns (start, end, provenance). Falls back to the module constants if
    the contract cannot be parsed, and says so in the provenance string.
    """
    if not CONTRACT.exists():
        return FALLBACK_START, FALLBACK_END, "fallback (contract file missing)"

    text = CONTRACT.read_text()
    block = re.search(
        r"smoke_test_3h_window_utc:\s*\n(?P<body>(?:\s+\w+:.*\n)+)", text
    )
    if not block:
        return FALLBACK_START, FALLBACK_END, "fallback (block not found)"

    body = block.group("body")
    start = re.search(r"start:\s*(\S+)", body)
    end = re.search(r"end:\s*(\S+)", body)
    if not (start and end):
        return FALLBACK_START, FALLBACK_END, "fallback (start/end not found)"

    return start.group(1), end.group(1), f"parsed from {CONTRACT.name}"


def parse_iso_z(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def expected_granule_count(start: datetime, end: datetime) -> int:
    """How many half-hourly granules START inside [start, end]."""
    span = (end - start).total_seconds()
    if span < 0:
        raise ValueError("end precedes start")
    return int(span // (GRANULE_MINUTES * 60)) + 1


def data_raw_ignored() -> str | None:
    probe = "data/raw/imerg/event_smoke_3h/probe.nc"
    result = subprocess.run(
        ["git", "check-ignore", "-v", probe],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def existing_files() -> list[Path]:
    if not DEST.is_dir():
        return []
    return sorted(p for p in DEST.glob("*.nc*") if p.is_file())


def timestamp_string(dataset) -> str:
    """Formatted UTC timestamp of the single time step."""
    value = np.atleast_1d(dataset["time"].values)[0]
    if hasattr(value, "strftime"):          # cftime object
        return value.strftime("%Y-%m-%dT%H:%M:%S")
    return str(np.datetime_as_string(value, unit="s"))


def to_datetime(dataset) -> datetime:
    """Timezone-aware datetime for spacing arithmetic."""
    return datetime.strptime(
        timestamp_string(dataset), "%Y-%m-%dT%H:%M:%S"
    ).replace(tzinfo=timezone.utc)


def main() -> int:
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )

    print(f"\n{RULE}\nIMERG 3-HOUR EVENT SMOKE TEST (download + validate)\n{RULE}")

    start_raw, end_raw, provenance = read_window_from_contract()
    start, end = parse_iso_z(start_raw), parse_iso_z(end_raw)
    print(f"  window source     : {provenance}")
    print(f"  start             : {start_raw}")
    print(f"  end               : {end_raw}")
    print(f"  bbox              : {DOWNLOAD_BBOX}")
    print("  note              : PIPELINE TEST window, not the wettest 3 h")

    # --- step 4: safety limit, BEFORE submission ------------------------
    predicted = expected_granule_count(start, end)
    print(f"  predicted granules: {predicted}")
    if predicted > EXPECTED_FILES:
        print(f"\n  ABORT: window could yield {predicted} granules, "
              f"limit is {EXPECTED_FILES}. Nothing submitted.")
        return 1
    if predicted != EXPECTED_FILES:
        print(f"\n  ABORT: expected exactly {EXPECTED_FILES} granules, "
              f"window implies {predicted}. Nothing submitted.")
        return 1

    # --- step 2: git ignore gate + reuse existing files -----------------
    ignore_rule = data_raw_ignored()
    if not ignore_rule:
        print("\n  ABORT: data/raw is NOT ignored by Git. Nothing downloaded.")
        return 1
    print(f"  git ignore        : {ignore_rule}")

    present = existing_files()
    print(f"  existing files    : {len(present)}")
    if len(present) >= EXPECTED_FILES:
        print("  reusing existing download — nothing re-requested "
              "(no files removed)")
        paths = present
    elif present:
        print(f"  ABORT: {len(present)} partial file(s) already present. "
              "Inspect or move them manually; nothing is removed "
              "automatically.")
        return 1
    else:
        print("\n  submitting Harmony request ...")
        paths = download_imerg_subset(
            start_time=start_raw,
            end_time=end_raw,
            output_dir=DEST,
            bbox=DOWNLOAD_BBOX,
        )
        print(f"  downloaded        : {len(paths)} file(s)")

    if len(paths) > EXPECTED_FILES:
        print(f"\n  WARNING: {len(paths)} files present, more than the "
              f"expected {EXPECTED_FILES}.")

    # --- step 5: per-file report ---------------------------------------
    print(f"\n{RULE}\nPER-FILE VALIDATION\n{RULE}")
    records = []
    for path in sorted(paths):
        dataset = read_imerg_subset(path)
        try:
            precip = dataset["precipitation"]
            values = np.asarray(precip.values, dtype="float64")
            valid = values[~np.isnan(values)]
            names = set(map(str, dataset.variables)) | set(
                map(str, dataset.coords))

            record = {
                "name": path.name,
                "size_kb": path.stat().st_size / 1024,
                "timestamp": timestamp_string(dataset),
                "dt": to_datetime(dataset),
                "dims": tuple(precip.dims),
                "shape": tuple(precip.shape),
                "lat_range": (float(dataset["lat"].min()),
                              float(dataset["lat"].max())),
                "lon_range": (float(dataset["lon"].min()),
                              float(dataset["lon"].max())),
                "min": float(valid.min()) if valid.size else float("nan"),
                "max": float(valid.max()) if valid.size else float("nan"),
                "mean": float(valid.mean()) if valid.size else float("nan"),
                "valid": int(valid.size),
                "missing": int(values.size - valid.size),
                "unexpected": sorted(names - ALLOWED_NAMES),
            }
        finally:
            dataset.close()
        records.append(record)

        print(f"\n  {record['name']}")
        print(f"    size            : {record['size_kb']:.1f} KB")
        print(f"    timestamp       : {record['timestamp']}Z")
        print(f"    dims / shape    : {record['dims']} / {record['shape']}")
        print(f"    latitude range  : {record['lat_range'][0]:.3f} -> "
              f"{record['lat_range'][1]:.3f}")
        print(f"    longitude range : {record['lon_range'][0]:.3f} -> "
              f"{record['lon_range'][1]:.3f}")
        print(f"    precip min/max  : {record['min']:.4f} / "
              f"{record['max']:.4f} mm/hr")
        print(f"    precip mean     : {record['mean']:.4f} mm/hr")
        print(f"    valid / missing : {record['valid']} / {record['missing']}")

    # --- step 6: final validation --------------------------------------
    print(f"\n{RULE}\nFINAL VALIDATION\n{RULE}")
    checks: list[tuple[str, bool, str]] = []

    unique_names = {r["name"] for r in records}
    checks.append((f"exactly {EXPECTED_FILES} files",
                   len(records) == EXPECTED_FILES, str(len(records))))
    checks.append(("all filenames unique",
                   len(unique_names) == len(records),
                   f"{len(unique_names)} unique"))

    stamps = [r["timestamp"] for r in records]
    times = sorted(r["dt"] for r in records)
    checks.append((f"exactly {EXPECTED_FILES} unique timestamps",
                   len(set(stamps)) == EXPECTED_FILES,
                   str(len(set(stamps)))))
    checks.append(("timestamps sorted ascending",
                   [r["dt"] for r in records] == times, "file order == time order"))

    gaps = [(b - a) for a, b in zip(times, times[1:])]
    spacing_ok = all(g == timedelta(minutes=GRANULE_MINUTES) for g in gaps)
    checks.append((f"spacing exactly {GRANULE_MINUTES} minutes", spacing_ok,
                   ", ".join(str(int(g.total_seconds() // 60)) + "m"
                             for g in gaps) or "n/a"))

    first = stamps[0] if stamps else ""
    last = stamps[-1] if stamps else ""
    checks.append((f"first timestamp {EXPECTED_FIRST}",
                   first == EXPECTED_FIRST, first))
    checks.append((f"last timestamp {EXPECTED_LAST}",
                   last == EXPECTED_LAST, last))

    shapes_ok = all(r["shape"] == EXPECTED_SHAPE for r in records)
    checks.append((f"every shape {EXPECTED_SHAPE}", shapes_ok,
                   str({r["shape"] for r in records})))

    unexpected = sorted({v for r in records for v in r["unexpected"]})
    checks.append(("no unrelated science variables", not unexpected,
                   str(unexpected) if unexpected else "none"))

    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=PROJECT_ROOT,
        capture_output=True, text=True, check=True,
    ).stdout
    leaked = [ln for ln in status.splitlines()
              if ".nc" in ln.lower() or "event_smoke_3h" in ln]
    checks.append(("no generated data in git status", not leaked,
                   str(leaked) if leaked else "clean"))

    for label, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:<38} {detail}")

    total_kb = sum(r["size_kb"] for r in records)
    nonzero = [r for r in records if r["max"] > 0]

    print(f"\n{RULE}\nSUMMARY\n{RULE}")
    print(f"  files downloaded  : {len(records)}")
    print(f"  timestamps        : "
          f"{', '.join(s.split('T')[1] for s in stamps)} UTC "
          f"on {stamps[0].split('T')[0] if stamps else '?'}")
    print(f"  total size        : {total_kb:.1f} KB")
    print(f"  non-zero rainfall : "
          f"{'YES in ' + str(len(nonzero)) + ' file(s)' if nonzero else 'NO — all cells 0.0 mm/hr'}")
    print("  aggregation       : NONE performed (no sums, no rolling windows)")

    all_pass = all(ok for _, ok, _ in checks)
    print(f"\n{RULE}")
    print(f"  VERDICT: {'GO' if all_pass else 'NO-GO'} for multi-granule "
          "IMERG ingestion")
    print(f"{RULE}\n")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
