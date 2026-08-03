"""
Loader: Karam's rainfall climatology, events, and event-catchment features ->
`catchment_rainfall_climatology`, `events`, `event_catchment_features`.

Sources:
    data/processed/features/catchment_rainfall_climatology.parquet
    data/processed/events/events.parquet
    data/processed/features/event_catchment_features.parquet

Note on climatology grain: only `window_hours=24` is delivered (daily IMERG sweep),
not the 1/3/6h windows originally scoped. `forecast_exceedance` (see
db/loaders/forecast_pipeline.py) is repointed to use this 24h p99 accordingly —
documented, not silently assumed.

Idempotent: every write upserts on the table's natural key.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from src.db.client import session_scope

REPO_ROOT = Path(__file__).resolve().parents[4]
FEATURES_DIR = REPO_ROOT / "data" / "processed" / "features"
EVENTS_DIR = REPO_ROOT / "data" / "processed" / "events"

CLIMATOLOGY_PARQUET = FEATURES_DIR / "catchment_rainfall_climatology.parquet"
EVENTS_PARQUET = EVENTS_DIR / "events.parquet"
EVENT_FEATURES_PARQUET = FEATURES_DIR / "event_catchment_features.parquet"

IMERG_SOURCE_ID = "imerg_v07_final"

UPSERT_CLIMATOLOGY_SQL = text(
    """
    INSERT INTO catchment_rainfall_climatology (
        catchment_id, window_hours, source_id, p50, p90, p95, p99, p99_9,
        max_observed_mm, n_windows
    ) VALUES (
        :catchment_id, :window_hours, :source_id, :p50, :p90, :p95, :p99, :p99_9,
        :max_observed_mm, :n_windows
    )
    ON CONFLICT (catchment_id, window_hours, source_id) DO UPDATE SET
        p50 = EXCLUDED.p50, p90 = EXCLUDED.p90, p95 = EXCLUDED.p95,
        p99 = EXCLUDED.p99, p99_9 = EXCLUDED.p99_9,
        max_observed_mm = EXCLUDED.max_observed_mm, n_windows = EXCLUDED.n_windows
    """
)


def load_climatology() -> int:
    """Loads the `_all_mm` percentile family (percentile over the full record,
    dry days included at 0) — matching the original design intent in the concept
    doc ("rank windows; keep those above p99... over the full record"), not the
    `_wet_mm` family (percentile among wet days only)."""
    if not CLIMATOLOGY_PARQUET.exists():
        print(f"SKIP climatology: missing {CLIMATOLOGY_PARQUET}")
        return 0

    df = pd.read_parquet(CLIMATOLOGY_PARQUET)
    n = 0
    with session_scope() as session:
        for _, row in df.iterrows():
            session.execute(
                UPSERT_CLIMATOLOGY_SQL,
                dict(
                    catchment_id=row["catchment_id"],
                    window_hours=int(row["window_hours"]),
                    source_id=IMERG_SOURCE_ID,
                    p50=float(row["p50_all_mm"]),
                    p90=float(row["p90_all_mm"]),
                    p95=float(row["p95_all_mm"]),
                    p99=float(row["p99_all_mm"]),
                    p99_9=float(row["p99_9_all_mm"]),
                    max_observed_mm=None,
                    n_windows=int(row["n_days"]),
                ),
            )
            n += 1
    return n


UPSERT_EVENT_SQL = text(
    """
    INSERT INTO events (
        id, start_time, event_type, detection_method, source_references, is_demo_event, notes
    ) VALUES (
        :id, :start_time, 'historical', 'imerg_percentile', :source_references, :is_demo_event, :notes
    )
    ON CONFLICT (id) DO UPDATE SET
        source_references = EXCLUDED.source_references,
        notes = EXCLUDED.notes
    """
)


def load_events() -> int:
    """Candidate events from Karam's IMERG percentile sweep. `AQ-2016-10-28` (the
    demo event) is already seeded by seed_events.py with literature-sourced
    detail — this loader does not overwrite its start_time/label_tier/quality_score,
    only augments source_references/notes for it and inserts the other candidates."""
    if not EVENTS_PARQUET.exists():
        print(f"SKIP events: missing {EVENTS_PARQUET}")
        return 0

    df = pd.read_parquet(EVENTS_PARQUET)
    n = 0
    with session_scope() as session:
        for _, row in df.iterrows():
            event_id = row["event_id"]
            is_demo = event_id == "AQ-2016-10-28"
            refs = json.dumps(
                {
                    "rank": int(row["rank"]),
                    "selection_reason": row["selection_reason"],
                    "wettest_catchment": row["wettest_catchment"],
                    "catchments_exceeding_p99": int(row["catchments_exceeding_p99"]),
                    "max_anomaly_ratio": float(row["max_anomaly_ratio"]),
                    "candidate_generation_scope": row["candidate_generation_scope"],
                    "is_exhaustive": bool(row["is_exhaustive"]),
                }
            )
            if is_demo:
                # Only touch source_references/notes — don't clobber the literature-sourced row.
                session.execute(
                    text(
                        "UPDATE events SET source_references = source_references || CAST(:refs AS jsonb) "
                        "WHERE id = :id"
                    ),
                    dict(id=event_id, refs=refs),
                )
            else:
                session.execute(
                    UPSERT_EVENT_SQL,
                    dict(
                        id=event_id,
                        start_time=row["date"],
                        source_references=refs,
                        is_demo_event=False,
                        notes=f"IMERG-percentile candidate, rank {int(row['rank'])}.",
                    ),
                )
            n += 1
    return n


UPSERT_FEATURES_SQL = text(
    """
    INSERT INTO event_catchment_features (
        event_id, catchment_id, rain_1h_mm, rain_3h_mm, rain_6h_mm, rain_24h_mm,
        rain_percentile_24h, extra_features
    ) VALUES (
        :event_id, :catchment_id, :rain_1h_mm, :rain_3h_mm, :rain_6h_mm, :rain_24h_mm,
        :rain_percentile_24h, :extra_features
    )
    ON CONFLICT (event_id, catchment_id) DO UPDATE SET
        rain_1h_mm = EXCLUDED.rain_1h_mm,
        rain_3h_mm = EXCLUDED.rain_3h_mm,
        rain_6h_mm = EXCLUDED.rain_6h_mm,
        rain_24h_mm = EXCLUDED.rain_24h_mm,
        rain_percentile_24h = EXCLUDED.rain_percentile_24h,
        extra_features = EXCLUDED.extra_features
    """
)


def load_event_catchment_features() -> int:
    """event_catchment_features has a UNIQUE (event_id, catchment_id) — the source
    parquet has one row per (event, catchment, timestamp); this keeps the row with
    the maximum precipitation_depth_mm per (event, catchment), matching the table's grain.

    Watch: this is a daily-resolution sweep. `rain_24h_mm` is mapped from
    `precipitation_depth_mm` (the actual daily accumulation carried by this
    dataset); `rain_1h_mm`/`rain_3h_mm`/`rain_6h_mm` are genuinely not computed
    here (0/500 non-null in the source) and are left NULL rather than derived
    or guessed."""
    if not EVENT_FEATURES_PARQUET.exists():
        print(f"SKIP event_catchment_features: missing {EVENT_FEATURES_PARQUET}")
        return 0

    df = pd.read_parquet(EVENT_FEATURES_PARQUET)
    idx = df.groupby(["event_id", "catchment_id"])["precipitation_depth_mm"].idxmax()
    df = df.loc[idx]

    n = 0
    with session_scope() as session:
        # Only insert for events that exist (the demo event + the candidates just loaded).
        existing_events = {
            r[0] for r in session.execute(text("SELECT id FROM events")).fetchall()
        }
        for _, row in df.iterrows():
            if row["event_id"] not in existing_events:
                continue
            extra = json.dumps(
                {
                    "coverage_fraction": float(row["coverage_fraction"]),
                    "valid_area_fraction": float(row["valid_area_fraction"]),
                    "quality_flag": row["quality_flag"],
                    "rain_anomaly_ratio": float(row["rain_anomaly_ratio"])
                    if pd.notna(row["rain_anomaly_ratio"])
                    else None,
                }
            )
            session.execute(
                UPSERT_FEATURES_SQL,
                dict(
                    event_id=row["event_id"],
                    catchment_id=row["catchment_id"],
                    rain_1h_mm=None,
                    rain_3h_mm=None,
                    rain_6h_mm=None,
                    rain_24h_mm=float(row["precipitation_depth_mm"])
                    if pd.notna(row["precipitation_depth_mm"])
                    else None,
                    rain_percentile_24h=float(row["catchment_p99_wet_mm"])
                    if pd.notna(row["catchment_p99_wet_mm"])
                    else None,
                    extra_features=extra,
                ),
            )
            n += 1
    return n


def run() -> None:
    print(f"Upserted {load_climatology()} catchment_rainfall_climatology rows.")
    print(f"Upserted {load_events()} events rows.")
    print(f"Upserted {load_event_catchment_features()} event_catchment_features rows.")


if __name__ == "__main__":
    run()
