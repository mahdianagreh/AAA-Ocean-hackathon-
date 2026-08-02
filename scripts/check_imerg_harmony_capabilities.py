#!/usr/bin/env python
"""Check what NASA Harmony can do for the IMERG collection.

Metadata only: queries the public /capabilities endpoint, prints a report,
and saves a sanitized copy of the response. No subset request is made, no
granule is downloaded, and no credentials are sent unless the server
explicitly demands them (in which case the script stops and says so).

Nothing sensitive is printed or stored: no tokens, cookies, headers, or
signed URLs — the saved JSON is filtered before it touches disk.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

OUTPUT_FILE = PROJECT_ROOT / "docs" / "imerg_harmony_capabilities.json"

ENDPOINT = "https://harmony.earthdata.nasa.gov/capabilities"
PARAMS = {"shortName": "GPM_3IMERGHH", "version": "2"}
TIMEOUT = 60

RULE = "=" * 70

# Keys never written to disk or printed, in case the payload ever carries them.
SENSITIVE_KEYS = {
    "authorization", "cookie", "cookies", "set-cookie", "token",
    "access_token", "refresh_token", "bearer", "edl_token", "session",
    "sessionid", "password", "secret", "apikey", "api_key",
    "x-amz-security-token", "signature", "credentials", "headers", "auth",
}


def sanitize(value):
    """Recursively drop sensitive keys and any signed/query-string URLs."""
    if isinstance(value, dict):
        clean = {}
        for key, val in value.items():
            if key.lower() in SENSITIVE_KEYS:
                clean[key] = "<omitted>"
                continue
            clean[key] = sanitize(val)
        return clean
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str) and value.startswith("http") and "?" in value:
        # Strip query strings — that is where signatures and tokens hide.
        return value.split("?", 1)[0] + "?<query-omitted>"
    return value


def flag(value) -> str:
    if value is True:
        return "YES"
    if value is False:
        return "NO"
    if value is None:
        return "not reported"
    return str(value)


def find_variables(payload: dict) -> dict[str, list[str]]:
    """Group variable names/paths by the concept they relate to."""
    wanted = {
        "precipitation": ("precip",),
        "latitude": ("lat",),
        "longitude": ("lon",),
        "time": ("time",),
    }
    groups: dict[str, list[str]] = {key: [] for key in wanted}

    raw = payload.get("variables") or []
    labels: list[str] = []
    for item in raw:
        if isinstance(item, str):
            labels.append(item)
        elif isinstance(item, dict):
            label = item.get("name") or item.get("path") or item.get("id")
            if label:
                path = item.get("path")
                labels.append(
                    f"{label}   (path: {path})" if path and path != label
                    else str(label)
                )

    for label in labels:
        low = label.lower()
        for concept, needles in wanted.items():
            if any(n in low for n in needles):
                groups[concept].append(label)
    return groups


def service_names(payload: dict) -> list[str]:
    services = payload.get("services") or []
    names = []
    for svc in services:
        if isinstance(svc, str):
            names.append(svc)
        elif isinstance(svc, dict):
            name = svc.get("name") or svc.get("id") or svc.get("href")
            if name:
                names.append(str(name))
    return names


def _requires_earthdata_login(resp: requests.Response) -> bool:
    """True when Harmony bounces the request to Earthdata Login."""
    if resp.status_code in (401, 403):
        return True
    location = resp.headers.get("location", "")
    return (resp.is_redirect or resp.is_permanent_redirect) and \
        "urs.earthdata.nasa.gov" in location


def fetch_capabilities() -> requests.Response | None:
    """Anonymous first; authenticate only if the server demands it."""
    # Step 1: unauthenticated probe. Redirects are NOT followed, so no
    # request is ever sent onward to the login host.
    probe = requests.get(
        ENDPOINT, params=PARAMS, timeout=TIMEOUT, allow_redirects=False
    )
    print(f"  anonymous probe status : {probe.status_code}")

    if not _requires_earthdata_login(probe):
        print("  auth                   : not required")
        return probe

    print("  auth                   : REQUIRED — server redirects to "
          "Earthdata Login")
    print("                           retrying with existing "
          "authenticate() from imerg.py")

    from ingestion.imerg import authenticate  # existing logic, unmodified

    auth = authenticate()
    session = auth.get_session()   # EDL-aware session; never printed
    resp = session.get(ENDPOINT, params=PARAMS, timeout=TIMEOUT)
    print(f"  authenticated status   : {resp.status_code}")
    return resp


def main() -> int:
    print(f"\n{RULE}\nNASA HARMONY CAPABILITIES CHECK — IMERG\n{RULE}")
    print(f"  endpoint : {ENDPOINT}")
    print(f"  params   : {PARAMS}")

    try:
        response = fetch_capabilities()
    except requests.RequestException as exc:
        print(f"\n  request failed: {type(exc).__name__}: {exc}")
        return 1

    if response is None or response.status_code != 200:
        code = "none" if response is None else response.status_code
        print(f"\n  Could not retrieve capabilities (status {code}).")
        return 1

    ctype = response.headers.get("content-type", "")
    if "json" not in ctype.lower():
        print(f"\n  Response was {ctype!r}, not JSON — cannot report "
              "capabilities.")
        return 1

    try:
        payload = response.json()
    except ValueError:
        print("\n  Response was not valid JSON — cannot report capabilities.")
        return 1

    bbox = payload.get("bboxSubset")
    variable = payload.get("variableSubset")
    shape = payload.get("shapeSubset")
    concat = payload.get("concatenate")

    print(f"\n{RULE}\nCOLLECTION\n{RULE}")
    print(f"  1. conceptId           : {payload.get('conceptId')}")
    print(f"  2. shortName           : {payload.get('shortName')}")
    print(f"  3. capabilitiesVersion : "
          f"{payload.get('capabilitiesVersion')}")

    print(f"\n{RULE}\nSUBSETTING SUPPORT\n{RULE}")
    print(f"  4. bboxSubset          : {flag(bbox)}")
    print(f"  5. variableSubset      : {flag(variable)}")
    print(f"  6. shapeSubset         : {flag(shape)}")
    print(f"  7. concatenate         : {flag(concat)}")

    print(f"\n{RULE}\n8. OUTPUT FORMATS\n{RULE}")
    formats = payload.get("outputFormats") or []
    if formats:
        for fmt in formats:
            print(f"  - {fmt}")
    else:
        print("  none reported")

    print(f"\n{RULE}\n9. APPLICABLE HARMONY SERVICES\n{RULE}")
    names = service_names(payload)
    if names:
        for name in names:
            print(f"  - {name}")
    else:
        print("  none reported")

    print(f"\n{RULE}\n10. RELEVANT VARIABLES\n{RULE}")
    groups = find_variables(payload)
    total_vars = len(payload.get("variables") or [])
    print(f"  ({total_vars} variables listed in total)")
    for concept, matches in groups.items():
        print(f"\n  {concept}:")
        if matches:
            for match in matches[:12]:
                print(f"    - {match}")
            if len(matches) > 12:
                print(f"    ... and {len(matches) - 12} more")
        else:
            print("    none found")

    # --- save sanitized copy ------------------------------------------
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(sanitize(payload), indent=2, sort_keys=True) + "\n"
    )
    print(f"\n{RULE}\nSAVED\n{RULE}")
    print(f"  sanitized JSON -> {OUTPUT_FILE.relative_to(PROJECT_ROOT)}")
    print(f"  bytes          : {OUTPUT_FILE.stat().st_size}")

    # --- verdict ------------------------------------------------------
    print(f"\n{RULE}\nVERDICT\n{RULE}")
    if bbox and variable:
        print("  A. Bounding-box AND variable subsetting are both supported.")
    elif bbox or variable:
        which = "bounding-box" if bbox else "variable"
        missing = "variable" if bbox else "bounding-box"
        print(f"  B. Only ONE is supported: {which} subsetting works, "
              f"{missing} subsetting does not.")
    else:
        print("  C. NEITHER bounding-box nor variable subsetting is "
              "supported.")
    print(f"{RULE}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
