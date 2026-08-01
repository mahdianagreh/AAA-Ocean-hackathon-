#!/usr/bin/env python
"""Report which credentials are configured, and live-test the ones we can.

    python scripts/check_credentials.py            # presence check only
    python scripts/check_credentials.py --login    # also try real logins

Prints only PRESENT / MISSING and usernames — never a password or key.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ENV_FILE, env_name, settings  # noqa: E402

OK, NO, WARN = "\033[32m✓\033[0m", "\033[31m✗\033[0m", "\033[33m•\033[0m"

# (label, fields needed, note)
SOURCES = [
    ("NASA Earthdata      (IMERG, HLS, SRTM)",
     ["earthdata_username", "earthdata_password"], ""),
    ("Copernicus CDS      (ERA5-Land)",
     ["cdsapi_key"], "also accept the ERA5-Land licence once"),
    ("Copernicus Marine   (ocean currents)",
     ["cmems_username", "cmems_password"], ""),
    ("Copernicus DataSpace(Sentinel-2 L2A)",
     ["cdse_username", "cdse_password"], "or use the S3 keys"),
    ("Google Earth Engine (S2 / Allen Coral)",
     ["earthengine_project"], "browser auth, no password"),
    ("NOAA GFS / GEFS     (forecast)",
     [], "no account needed"),
]


def presence() -> int:
    print(f"\n  env file: {ENV_FILE}"
          f"{'' if ENV_FILE.exists() else '   <-- NOT FOUND'}")
    print(f"  data dir: {settings.data_dir}\n")
    ready = 0
    for label, fields, note in SOURCES:
        if not fields:
            print(f"  {OK} {label}  ({note})")
            ready += 1
            continue
        missing = [f for f in fields if not getattr(settings, f, "")]
        mark = NO if missing else OK
        ready += not missing
        detail = (f"missing: {', '.join(env_name(f) for f in missing)}"
                  if missing else "configured")
        print(f"  {mark} {label}  {detail}"
              + (f"  ({note})" if note and not missing else ""))
    print(f"\n  {ready}/{len(SOURCES)} sources ready\n")
    return ready


def try_logins() -> None:
    print("  live login tests")
    print("  " + "-" * 40)

    if settings.earthdata_username and settings.earthdata_password:
        try:
            import earthaccess

            auth = earthaccess.login(strategy="environment", persist=False)
            mark = OK if auth.authenticated else NO
            print(f"  {mark} NASA Earthdata as "
                  f"'{settings.earthdata_username}'")
        except Exception as exc:  # noqa: BLE001
            print(f"  {NO} NASA Earthdata — {type(exc).__name__}: {exc}")
    else:
        print(f"  {WARN} NASA Earthdata — skipped, not configured")

    if settings.cdsapi_key:
        try:
            import cdsapi

            cdsapi.Client(url=settings.cdsapi_url, key=settings.cdsapi_key)
            print(f"  {OK} Copernicus CDS client built")
        except ImportError:
            print(f"  {WARN} Copernicus CDS — `pip install cdsapi` first")
        except Exception as exc:  # noqa: BLE001
            print(f"  {NO} Copernicus CDS — {type(exc).__name__}: {exc}")
    else:
        print(f"  {WARN} Copernicus CDS — skipped, no CDSAPI_KEY")

    if settings.cmems_username and settings.cmems_password:
        try:
            import copernicusmarine  # noqa: F401

            print(f"  {OK} Copernicus Marine credentials present, "
                  "library importable")
        except ImportError:
            print(f"  {WARN} Copernicus Marine — "
                  "`pip install copernicusmarine` first")
    else:
        print(f"  {WARN} Copernicus Marine — skipped, not configured")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--login", action="store_true",
                        help="attempt real logins, not just presence")
    args = parser.parse_args()

    presence()
    if args.login:
        try_logins()
