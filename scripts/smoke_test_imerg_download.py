#!/usr/bin/env python
"""One-granule IMERG download smoke test.

Proves the full path works end to end: authenticate -> search -> download a
single granule to disk. Deliberately downloads ONE granule, never the full
96-granule window.

Reuses authenticate() from backend/src/ingestion/imerg.py unchanged.
Nothing sensitive is printed: no credentials, no signed URLs, no headers.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

import earthaccess  # noqa: E402

from ingestion.imerg import authenticate, search_imerg  # noqa: E402

DEST = PROJECT_ROOT / "data" / "raw" / "imerg" / "smoke_test"
IGNORE_RULE = "data/raw/"


def ensure_data_raw_ignored() -> str:
    """Gate: refuse to download until data/raw/ is ignored by Git.

    Returns the rule that covers it, adding it to .gitignore if absent.
    """
    probe = "data/raw/imerg/smoke_test/probe.HDF5"
    result = subprocess.run(
        ["git", "check-ignore", "-v", probe],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()

    gitignore = PROJECT_ROOT / ".gitignore"
    existing = gitignore.read_text() if gitignore.exists() else ""
    if not existing.endswith("\n"):
        existing += "\n"
    gitignore.write_text(existing + IGNORE_RULE + "\n")

    recheck = subprocess.run(
        ["git", "check-ignore", "-v", probe],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if recheck.returncode != 0:
        raise RuntimeError(
            f"Added '{IGNORE_RULE}' to .gitignore but Git still does not "
            "ignore the download path. Aborting before writing data."
        )
    return recheck.stdout.strip() + "   (rule added just now)"


def hdf5_visible_to_git() -> list[str]:
    """Any HDF5 file Git can see (tracked or untracked-but-not-ignored)."""
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        line
        for line in result.stdout.splitlines()
        if ".HDF5" in line.upper() or "smoke_test" in line
    ]


def main() -> int:
    # --- Step 7: verify the ignore rule BEFORE any bytes hit disk ---------
    ignore_rule = ensure_data_raw_ignored()

    authenticate()  # existing logic, untouched

    results = search_imerg(
        start_date="2016-10-25T00:00:00",
        end_date="2016-10-25T00:29:59",
        count=1,
    )
    searched = len(results)
    if searched == 0:
        print("No granules found — nothing to download.")
        return 1

    DEST.mkdir(parents=True, exist_ok=True)

    # Pass a LIST of exactly one granule, not a bare DataGranule.
    one_granule = results[:1]
    earthaccess.download(one_granule, local_path=str(DEST))

    files = sorted(p for p in DEST.iterdir() if p.is_file())
    if not files:
        print("Download reported success but no file landed in the folder.")
        return 1

    downloaded = max(files, key=lambda p: p.stat().st_size)
    size_mb = downloaded.stat().st_size / (1024 * 1024)
    visible = hdf5_visible_to_git()

    print()
    print("=" * 62)
    print("IMERG one-granule download smoke test")
    print("=" * 62)
    print(f"  Granules searched : {searched}")
    print(f"  Downloaded path   : {downloaded}")
    print(f"  File name         : {downloaded.name}")
    print(f"  File size (MB)    : {size_mb:.2f}")
    print(f"  File exists       : {downloaded.exists()}")
    print(f"  Git sees HDF5     : {'YES -> ' + str(visible) if visible else 'NO'}")
    print(f"  Ignore rule       : {ignore_rule}")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
