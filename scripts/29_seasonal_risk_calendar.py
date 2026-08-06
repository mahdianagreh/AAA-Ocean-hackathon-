#!/usr/bin/env python3
"""Bucket the real 675-event catalogue by calendar month.

Phase 4, 01-karam.md item 3. Not a new pipeline -- a script over
`data/processed/events/events.parquet`, which already carries a real per-event
`max_daily_mm` for every one of the 675 rainfall-detected storms
(`scripts/build_event_catalogue.py`).

FRAMING DECISION, STATED HERE RATHER THAN LEFT IMPLICIT
--------------------------------------------------------
This calendar buckets by **rainfall intensity**, not exposure score. The sediment
model is anchored to exactly one event (AQ-2016-10-28, October) --
`data/models/sediment_anchor.json` -- so an exposure-scored calendar would read as
flat everywhere except October, which misrepresents what the rainfall record
actually shows about seasonality. If a later phase wants an exposure-based
calendar instead, that is a different feature with a different name, not a
reinterpretation of this file's columns.

Run: .venv/bin/python scripts/29_seasonal_risk_calendar.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVENTS_PATH = PROJECT_ROOT / "data" / "processed" / "events" / "events.parquet"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "features" / "seasonal_risk_calendar.parquet"

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def build_calendar(events: pd.DataFrame) -> pd.DataFrame:
    events = events.copy()
    events["month"] = pd.to_datetime(events["date"]).dt.month

    by_month = events.groupby("month").agg(
        event_count=("event_id", "size"),
        max_daily_mm=("max_daily_mm", "max"),
        mean_daily_mm=("max_daily_mm", "mean"),
    )
    by_month["worst_event_id"] = by_month.index.map(
        lambda m: events.loc[events.loc[events["month"] == m, "max_daily_mm"].idxmax(), "event_id"]
    )

    calendar = pd.DataFrame({"month": range(1, 13)}).set_index("month")
    calendar = calendar.join(by_month, how="left")
    calendar["event_count"] = calendar["event_count"].fillna(0).astype(int)
    calendar["month_name"] = [MONTH_NAMES[m - 1] for m in calendar.index]
    calendar = calendar.reset_index()[
        ["month", "month_name", "event_count", "max_daily_mm", "mean_daily_mm", "worst_event_id"]
    ]
    return calendar


def main() -> None:
    if not EVENTS_PATH.exists():
        raise FileNotFoundError(
            f"{EVENTS_PATH} not present -- run scripts/build_event_catalogue.py first"
        )
    events = pd.read_parquet(EVENTS_PATH, columns=["event_id", "date", "max_daily_mm"])
    calendar = build_calendar(events)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    calendar.to_parquet(OUTPUT_PATH, index=False)

    print("Seasonal risk calendar (rainfall intensity, not exposure score)")
    print("=" * 64)
    for _, row in calendar.iterrows():
        peak = f"{row['max_daily_mm']:.1f} mm" if pd.notna(row["max_daily_mm"]) else "no events"
        worst = row["worst_event_id"] if pd.notna(row["worst_event_id"]) else "-"
        print(f"  {row['month_name']:10s} {row['event_count']:3d} event(s)  "
              f"peak {peak:>10s}  worst {worst}")
    print()
    print(f"wrote {OUTPUT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
