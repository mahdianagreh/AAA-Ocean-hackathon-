"""Rain-intensity percentile (p4-08) and the seasonal calendar (p4-K).

Two Phase 7 additions to the events surface, each guarding an honesty rule:

  - `intensity_top_percent` places an event's daily depth in its wettest
    catchment's OWN ~28-year record, as a real empirical percentile — never
    `max_anomaly_ratio`, which is stale and ranks storms differently. The demo
    event AQ-2016-10-28 must read where the data puts it, which is NOT rank 1:
    it is the best-instrumented flood, not the biggest.

  - `GET /api/v1/seasonal-risk-calendar` buckets the 675-event catalogue by
    calendar month on RAINFALL INTENSITY, not exposure score, and answers 503
    (not an empty list) when its artifact is absent — missing is missing.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

os.environ.setdefault(
    "REEFSHIELD_EXPOSURE_DB", str(Path(tempfile.mkdtemp()) / "test_events_seasonal.sqlite")
)

DAILY = PROJECT_ROOT / "data" / "processed" / "features" / "catchment_rainfall_daily.parquet"
SEASONAL = PROJECT_ROOT / "data" / "processed" / "features" / "seasonal_risk_calendar.parquet"


def _client():
    from api.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


# ------------------------------------------------------------ intensity_top_percent

def test_events_carry_an_intensity_top_percent():
    from api.main import PREFIX

    sites = _client().get(f"{PREFIX}/events").json()
    assert sites, "no events served"
    assert all("intensity_top_percent" in e for e in sites)
    # At least the catalogued events (those with a wettest_catchment) get a number.
    with_catchment = [e for e in sites if e["wettest_catchment"]]
    assert all(e["intensity_top_percent"] is not None for e in with_catchment)


def test_intensity_top_percent_matches_the_daily_record():
    """The number is an empirical percentile of the real daily series, not a
    proxy. Recompute it straight from the parquet and demand agreement."""
    if not DAILY.exists():
        import pytest

        pytest.skip("catchment_rainfall_daily.parquet absent")

    from api.main import PREFIX

    df = pd.read_parquet(DAILY, columns=["catchment_id", "precipitation_mm_day"])
    events = _client().get(f"{PREFIX}/events").json()
    demo = next(e for e in events if e["event_id"] == "AQ-2016-10-28")

    cid, value = demo["wettest_catchment"], demo["max_daily_mm"]
    series = df[df.catchment_id == cid]["precipitation_mm_day"].dropna()
    expected = round(100.0 * (series >= value).sum() / len(series), 2)
    assert demo["intensity_top_percent"] == expected


def test_intensity_helper_is_none_safe_and_monotonic():
    """None in → None out (a gap, never a fabricated rank); a heavier day is
    rarer, so its top-percent is smaller."""
    from api import data_access as da

    assert da.intensity_top_percent(None, 10.0) is None
    assert da.intensity_top_percent("AQ-C03", None) is None
    assert da.intensity_top_percent("AQ-C99-not-real", 10.0) is None

    if DAILY.exists():
        light = da.intensity_top_percent("AQ-C03", 1.0)
        heavy = da.intensity_top_percent("AQ-C03", 15.0)
        assert light is not None and heavy is not None
        assert heavy <= light, "a heavier threshold cannot sit in a larger fraction of days"


def test_demo_event_is_not_the_biggest_storm():
    """AQ-2016-10-28 is the best-instrumented flood, not the largest. The ranking
    must place it below rank 1, and rank 1 must be a different event."""
    from api.main import PREFIX

    events = _client().get(f"{PREFIX}/events").json()
    demo = next(e for e in events if e["event_id"] == "AQ-2016-10-28")
    rank1 = min((e for e in events if e["rank"]), key=lambda e: e["rank"])
    assert demo["rank"] and demo["rank"] > 1
    assert rank1["event_id"] != "AQ-2016-10-28"


# --------------------------------------------------------------- seasonal calendar

def test_seasonal_calendar_is_twelve_months_in_order():
    from api.main import PREFIX

    r = _client().get(f"{PREFIX}/seasonal-risk-calendar")
    assert r.status_code == 200, r.text
    cal = r.json()
    assert [m["month"] for m in cal] == list(range(1, 13))
    assert cal[0]["month_name"] == "January"
    assert all(m["event_count"] >= 0 for m in cal)


def test_seasonal_month_links_to_its_worst_event():
    """`worst_event_id` is the deep-link target on each cell. October's worst is
    the demo event — the month it belongs to."""
    from api.main import PREFIX

    cal = _client().get(f"{PREFIX}/seasonal-risk-calendar").json()
    october = next(m for m in cal if m["month"] == 10)
    assert october["worst_event_id"] == "AQ-2016-10-28"


def test_seasonal_calendar_matches_its_artifact():
    if not SEASONAL.exists():
        import pytest

        pytest.skip("seasonal_risk_calendar.parquet absent")

    from api.main import PREFIX

    cal = _client().get(f"{PREFIX}/seasonal-risk-calendar").json()
    df = pd.read_parquet(SEASONAL).sort_values("month")
    assert len(cal) == len(df)
    assert [m["event_count"] for m in cal] == df["event_count"].tolist()
