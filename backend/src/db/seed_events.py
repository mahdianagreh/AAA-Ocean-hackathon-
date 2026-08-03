"""
Seed the one demo event: AQ-2016-10-28, per tasks/phase2/00-phase2-plan.md's
"event contract". Everything else in the pipeline (event_catchment_features,
satellite_scenes, observed_plumes, simulation_runs, backtests) hangs off this row.

February 2013 is explicitly dead (no date, no usable imagery) and is not seeded.
"""

from __future__ import annotations

import datetime as dt
import json

from sqlalchemy import text

from src.db.client import session_scope

UPSERT_SQL = text(
    """
    INSERT INTO events (
        id, start_time, peak_time, event_type, detection_method,
        label_tier, quality_score, source_references, is_demo_event, notes
    ) VALUES (
        :id, :start_time, :peak_time, :event_type, :detection_method,
        :label_tier, :quality_score, :source_references, :is_demo_event, :notes
    )
    ON CONFLICT (id) DO UPDATE SET
        start_time = EXCLUDED.start_time,
        peak_time = EXCLUDED.peak_time,
        event_type = EXCLUDED.event_type,
        detection_method = EXCLUDED.detection_method,
        label_tier = EXCLUDED.label_tier,
        quality_score = EXCLUDED.quality_score,
        source_references = EXCLUDED.source_references,
        is_demo_event = EXCLUDED.is_demo_event,
        notes = EXCLUDED.notes
    """
)

DEMO_EVENT = dict(
    id="AQ-2016-10-28",
    # Reported flood arrival (Eilat), timezone-converted from IDT (UTC+3).
    start_time=dt.datetime(2016, 10, 28, 0, 0, tzinfo=dt.timezone.utc),
    # Offshore instrument response time, timezone-converted.
    peak_time=dt.datetime(2016, 10, 28, 6, 50, tzinfo=dt.timezone.utc),
    event_type="historical",
    detection_method="literature",
    label_tier="gold",
    quality_score=0.95,
    source_references=json.dumps(
        {
            "sediment_mass_tonnes": 24400,
            "sediment_mass_source": "Kalman et al. 2025",
            "mooring_salinity_min_permille": 38.75,
            "mooring_salinity_anomaly_permille": -1.75,
            "mooring_salinity_anomaly_sigma": 19,
            "mooring_turbidity_peak_g_per_l": 2.18,
            "mooring_turbidity_duration_hours": 31,
            "mooring_location": "250m offshore Kinnet Canal outlet, 13m depth",
            "flood_arrival_source": "reported, timezone-converted (IDT, UTC+3)",
        }
    ),
    is_demo_event=True,
    notes=(
        "The project's single event contract (tasks/phase2/00-phase2-plan.md). "
        "Satellite validation returned a NO-GO for this event (both S2 passes "
        "2.5-3.5 days late, plume already dispersed per the mooring record) — "
        "the mooring time series is the validation target instead. Feb 2013 is "
        "dead (no date, no usable imagery) and is not seeded."
    ),
)


def seed_events() -> int:
    with session_scope() as session:
        session.execute(UPSERT_SQL, DEMO_EVENT)
    return 1


if __name__ == "__main__":
    n = seed_events()
    print(f"Upserted {n} events row(s).")
