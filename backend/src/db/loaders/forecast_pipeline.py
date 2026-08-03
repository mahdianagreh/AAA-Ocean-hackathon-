"""
Real per-catchment forecast pipeline: GFS (deterministic) + GEFS (30-member
ensemble) -> `forecast_runs`, `forecast_catchment_rainfall`, `forecast_exceedance`.

This is the actual "definition of done" item from tasks/phase2/03-nizar.md §6:
"GEFS exceedance running against Karam's real per-catchment p99" — not the AOI-mean
placeholder from Phase 1. Samples each ensemble member's precipitation field at
each catchment's centroid (nearest-neighbour — both grids are far coarser than
any catchment), accumulates a rolling 24h total, and compares it against that
catchment's own p99 from `catchment_rainfall_climatology` (window_hours=24,
source_id='imerg_v07_final') — the only grain Karam's climatology delivers.

Every run is timestamped by its own `reference_time`, so re-running this on a
different day creates a new `forecast_runs` row rather than overwriting the
previous one — each is a frozen snapshot in its own right.
"""

from __future__ import annotations

import sys
from pathlib import Path

import xarray as xr
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.db.client import session_scope  # noqa: E402
from src.ingestion.gefs import FORECAST_HOURS as GEFS_HOURS  # noqa: E402
from src.ingestion.gefs import fetch_gefs_members  # noqa: E402
from src.ingestion.gfs import FORECAST_HOURS as GFS_HOURS  # noqa: E402
from src.ingestion.gfs import fetch_gfs_run  # noqa: E402

ACCUMULATION_WINDOW_HOURS = 24
CLIMATOLOGY_SOURCE_ID = "imerg_v07_final"


def _get_catchment_centroids(session) -> list[dict]:
    rows = session.execute(
        text("SELECT id, ST_X(ST_Centroid(geom)) AS lon, ST_Y(ST_Centroid(geom)) AS lat FROM catchments")
    ).mappings().all()
    return [dict(r) for r in rows]


def _sample_point(ds: xr.Dataset, var: str, lon: float, lat: float) -> float:
    lon_grid = lon % 360  # GFS/GEFS grids are 0-360
    point = ds[var].sel(longitude=lon_grid, latitude=lat, method="nearest")
    return float(point.values)


def _sample_gfs_at_centroids(objs, centroids: list[dict]) -> list[dict]:
    """Returns rows: {catchment_id, lead_hours, rain_mm, wind_speed_ms, wind_direction_deg}."""
    import numpy as np

    rows = []
    for H in objs:
        local_paths = H.get_localFilePath(":APCP:surface|:(?:UGRD|VGRD):10 m above ground")
        paths = [local_paths] if isinstance(local_paths, (str, Path)) else list(local_paths)
        for p in paths:
            if not Path(p).exists():
                continue
            ds = xr.open_dataset(p, engine="cfgrib", backend_kwargs={"indexpath": ""})
            for c in centroids:
                rain_mm = _sample_point(ds, "tp", c["lon"], c["lat"]) if "tp" in ds else None
                u10 = _sample_point(ds, "u10", c["lon"], c["lat"]) if "u10" in ds else None
                v10 = _sample_point(ds, "v10", c["lon"], c["lat"]) if "v10" in ds else None
                wind_speed = float(np.hypot(u10, v10)) if u10 is not None and v10 is not None else None
                wind_dir = (
                    float((270 - np.degrees(np.arctan2(v10, u10))) % 360)
                    if u10 is not None and v10 is not None
                    else None
                )
                rows.append(
                    dict(
                        catchment_id=c["id"],
                        lead_hours=H.fxx,
                        rain_mm=rain_mm,
                        wind_speed_ms=wind_speed,
                        wind_direction_deg=wind_dir,
                    )
                )
    return rows


def _sample_gefs_at_centroids(members: dict[int, list], centroids: list[dict]) -> list[dict]:
    """Returns rows: {catchment_id, member, lead_hours, rain_mm}."""
    rows = []
    for member, objs in members.items():
        for H in objs:
            local_paths = H.get_localFilePath(":APCP:surface")
            paths = [local_paths] if isinstance(local_paths, (str, Path)) else list(local_paths)
            for p in paths:
                if not Path(p).exists():
                    continue
                ds = xr.open_dataset(p, engine="cfgrib", backend_kwargs={"indexpath": ""})
                for c in centroids:
                    rain_mm = _sample_point(ds, "tp", c["lon"], c["lat"])
                    rows.append(
                        dict(
                            catchment_id=c["id"],
                            member=member,
                            lead_hours=H.fxx,
                            rain_mm=rain_mm,
                            wind_speed_ms=None,
                            wind_direction_deg=None,
                        )
                    )
    return rows


UPSERT_FORECAST_RUN_SQL = text(
    """
    INSERT INTO forecast_runs (id, source_id, model, reference_time, n_members, max_lead_hours, raw_path)
    VALUES (:id, :source_id, :model, :reference_time, :n_members, :max_lead_hours, :raw_path)
    ON CONFLICT (model, reference_time) DO UPDATE SET
        n_members = EXCLUDED.n_members,
        max_lead_hours = EXCLUDED.max_lead_hours,
        raw_path = EXCLUDED.raw_path
    RETURNING id
    """
)

UPSERT_CATCHMENT_RAINFALL_SQL = text(
    """
    INSERT INTO forecast_catchment_rainfall (
        forecast_run_id, catchment_id, lead_hours, member, rain_mm, wind_speed_ms, wind_direction_deg
    ) VALUES (
        :forecast_run_id, :catchment_id, :lead_hours, :member, :rain_mm, :wind_speed_ms, :wind_direction_deg
    )
    ON CONFLICT (forecast_run_id, catchment_id, lead_hours, member) DO UPDATE SET
        rain_mm = EXCLUDED.rain_mm,
        wind_speed_ms = EXCLUDED.wind_speed_ms,
        wind_direction_deg = EXCLUDED.wind_direction_deg
    """
)

UPSERT_EXCEEDANCE_SQL = text(
    """
    INSERT INTO forecast_exceedance (
        forecast_run_id, catchment_id, window_hours, threshold_mm, threshold_source,
        members_total, members_exceeding, exceedance_prob
    ) VALUES (
        :forecast_run_id, :catchment_id, :window_hours, :threshold_mm, :threshold_source,
        :members_total, :members_exceeding, :exceedance_prob
    )
    ON CONFLICT (forecast_run_id, catchment_id, window_hours) DO UPDATE SET
        threshold_mm = EXCLUDED.threshold_mm,
        threshold_source = EXCLUDED.threshold_source,
        members_total = EXCLUDED.members_total,
        members_exceeding = EXCLUDED.members_exceeding,
        exceedance_prob = EXCLUDED.exceedance_prob
    """
)


def run() -> None:
    with session_scope() as session:
        centroids = _get_catchment_centroids(session)
    if not centroids:
        raise RuntimeError("No catchments in the database — run mahdi_terrain loader first.")

    # --- GFS: deterministic, member=0 ---
    print("Fetching GFS...")
    gfs_objs = fetch_gfs_run()
    gfs_reference_time = gfs_objs[0].date
    gfs_rows = _sample_gfs_at_centroids(gfs_objs, centroids)

    with session_scope() as session:
        gfs_run_id = session.execute(
            UPSERT_FORECAST_RUN_SQL,
            dict(
                id=f"gfs_{gfs_reference_time:%Y-%m-%dT%H}Z",
                source_id="noaa_gfs",
                model="gfs",
                reference_time=gfs_reference_time,
                n_members=1,
                max_lead_hours=max(GFS_HOURS),
                raw_path="data/raw/forecasts/gfs/",
            ),
        ).scalar_one()
        params = [dict(forecast_run_id=gfs_run_id, member=0, **row) for row in gfs_rows]
        if params:
            session.execute(UPSERT_CATCHMENT_RAINFALL_SQL, params)
    print(f"Wrote forecast_runs[{gfs_run_id}] + {len(gfs_rows)} forecast_catchment_rainfall rows (GFS).")

    # --- GEFS: 30-member ensemble ---
    print("Fetching GEFS (30 members)...")
    gefs_members = fetch_gefs_members()
    gefs_reference_time = next(iter(gefs_members.values()))[0].date
    gefs_rows = _sample_gefs_at_centroids(gefs_members, centroids)

    with session_scope() as session:
        gefs_run_id = session.execute(
            UPSERT_FORECAST_RUN_SQL,
            dict(
                id=f"gefs_{gefs_reference_time:%Y-%m-%dT%H}Z",
                source_id="noaa_gefs",
                model="gefs",
                reference_time=gefs_reference_time,
                n_members=30,
                max_lead_hours=max(GEFS_HOURS),
                raw_path="data/raw/forecasts/gefs/",
            ),
        ).scalar_one()
        params = [dict(forecast_run_id=gefs_run_id, **row) for row in gefs_rows]
        if params:
            session.execute(UPSERT_CATCHMENT_RAINFALL_SQL, params)
    print(f"Wrote forecast_runs[{gefs_run_id}] + {len(gefs_rows)} forecast_catchment_rainfall rows (GEFS).")

    # --- Exceedance: 24h rolling accumulation per member per catchment, vs real p99 ---
    print("Computing exceedance against Karam's real p99 climatology...")
    with session_scope() as session:
        climatology = {
            r["catchment_id"]: r["p99"]
            for r in session.execute(
                text(
                    "SELECT catchment_id, p99 FROM catchment_rainfall_climatology "
                    "WHERE window_hours = :w AND source_id = :s"
                ),
                dict(w=ACCUMULATION_WINDOW_HOURS, s=CLIMATOLOGY_SOURCE_ID),
            ).mappings().all()
        }

        for c in centroids:
            catchment_id = c["id"]
            threshold = climatology.get(catchment_id)
            if threshold is None:
                print(f"SKIP exceedance for {catchment_id}: no climatology row.")
                continue

            member_totals = {}
            for row in gefs_rows:
                if row["catchment_id"] != catchment_id or row["lead_hours"] > ACCUMULATION_WINDOW_HOURS:
                    continue
                if row["rain_mm"] is None:
                    continue
                member_totals.setdefault(row["member"], 0.0)
                member_totals[row["member"]] += row["rain_mm"]

            members_total = len(member_totals)
            members_exceeding = sum(1 for v in member_totals.values() if v > threshold)
            exceedance_prob = members_exceeding / members_total if members_total else None

            session.execute(
                UPSERT_EXCEEDANCE_SQL,
                dict(
                    forecast_run_id=gefs_run_id,
                    catchment_id=catchment_id,
                    window_hours=ACCUMULATION_WINDOW_HOURS,
                    threshold_mm=threshold,
                    threshold_source="catchment_rainfall_climatology p99, window_hours=24, imerg_v07_final",
                    members_total=members_total,
                    members_exceeding=members_exceeding,
                    exceedance_prob=exceedance_prob,
                ),
            )
            print(
                f"  {catchment_id}: {members_exceeding}/{members_total} members exceed "
                f"{threshold:.2f}mm (p99, 24h) -> exceedance_prob={exceedance_prob:.2f}"
            )


if __name__ == "__main__":
    run()
