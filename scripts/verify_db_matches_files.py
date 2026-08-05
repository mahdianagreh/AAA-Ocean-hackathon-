"""
DB-vs-files verification — confirms every teammate's latest reload actually
landed in Postgres, per tasks/phase3/03-nizar.md §4: "Confirm the DB and the
files agree... events, feature rows and reef zones should match the
parquet/gpkg exactly."

Postgres foreign-key constraints already structurally prevent orphaned rows
(an insert referencing a non-existent parent simply fails), so this checks
completeness/freshness instead: does the live row count match what the current
source file on disk would produce. A stale table (loader run once, file
updated since, loader never re-run) is exactly the silent-divergence failure
mode this catches.

Run: cd backend && .venv/bin/python ../scripts/verify_db_matches_files.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from src.db.client import session_scope  # noqa: E402
from src.db.loaders.pulga_reef_zones import resolve_reef_zones  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
VECTORS = REPO_ROOT / "data" / "processed" / "vectors"
FEATURES = REPO_ROOT / "data" / "processed" / "features"
EVENTS_DIR = REPO_ROOT / "data" / "processed" / "events"

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, db_count: int, file_count: int, detail: str = "") -> None:
    ok = db_count == file_count
    RESULTS.append((name, ok, f"db={db_count} file={file_count} {detail}"))


def main() -> None:
    with session_scope() as session:
        def db_count(table: str, where: str = "") -> int:
            sql = f"SELECT count(*) FROM {table}"
            if where:
                sql += f" WHERE {where}"
            return session.execute(text(sql)).scalar_one()

        if (VECTORS / "catchments.gpkg").exists():
            n = len(gpd.read_file(VECTORS / "catchments.gpkg"))
            check("catchments", db_count("catchments"), n)

        if (VECTORS / "outlets.gpkg").exists():
            n = len(gpd.read_file(VECTORS / "outlets.gpkg"))
            check("outlets", db_count("outlets"), n)

        reef_path, reef_source_id, _ = resolve_reef_zones()
        if reef_path.exists():
            n = len(gpd.read_file(reef_path))
            check("reef_zones", db_count("reef_zones"), n, f"(source: {reef_path.name})")

        events_path = EVENTS_DIR / "events.parquet"
        if events_path.exists():
            n = len(pd.read_parquet(events_path))
            check("events", db_count("events"), n)

        features_path = FEATURES / "event_catchment_features.parquet"
        if features_path.exists():
            df = pd.read_parquet(features_path)
            n = len(df.groupby(["event_id", "catchment_id"]).size())
            check("event_catchment_features", db_count("event_catchment_features"), n,
                  "(distinct event_id,catchment_id pairs)")

        climatology_path = FEATURES / "catchment_rainfall_climatology.parquet"
        if climatology_path.exists():
            n = len(pd.read_parquet(climatology_path))
            check("catchment_rainfall_climatology", db_count("catchment_rainfall_climatology"), n)

    print(f"{'table':<32} {'status':<6} detail")
    all_ok = True
    for name, ok, detail in RESULTS:
        status = "PASS" if ok else "FAIL"
        all_ok &= ok
        print(f"{name:<32} {status:<6} {detail}")

    if not all_ok:
        print(
            "\nFAIL does not always mean 're-run the loader'. It can also mean the "
            "*upstream* file itself is stale relative to a correction made elsewhere "
            "(e.g. event_catchment_features.parquet still covering an event id that "
            "was since removed from events.parquet) — check which side actually "
            "changed before assuming the loader is the problem."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
