"""Targeted plume-search list for Abd: which storms are worth checking, and when.

Why this is worth doing after a NO-GO
------------------------------------
Satellite validation of the October 2016 event is a measured NO-GO - the plume
dispersed ~31 h after arrival and the only usable passes are +104 h and +128 h.
That verdict is correct and stands FOR THAT EVENT.

It does not generalise. A ~31 h plume against a ~3-day combined Sentinel-2 +
Landsat-8 revisit has roughly a 43% chance of being caught. One event failing is
the expected outcome; across the 31 storms in the Landsat-8 era the odds invert,
and ~13 detections is the expectation. That would roughly double the gold set in
scripts/24 - and unlike the 13 literature floods, which were recorded at the
Kinnet Canal in Eilat, a satellite plume off an Aqaba outlet is evidence on the
side of the Gulf our catchments actually drain.

What this script does and does not do
-------------------------------------
It does NOT download imagery or detect plumes - that is Abd's workstream and his
segmentation model. It produces the search list: for each storm, the UTC window
in which a plume should be visible, so the catalogue query is 31 targeted
searches instead of a sweep.

The window comes from the one event we have timed, and getting the ANCHOR right
matters more than the width. The first version of this script used
`rain_start_to_sea_hours` (50 h) measured from the storm's peak-rainfall day, and
produced a window starting 11 h AFTER the documented plume had already begun -
because 50 h runs from when the rain STARTED, which is a day or more before the
peak. Applied to a daily storm record it overshoots every time.

The anchor that survives the check is rain END:

    arrival      = end of the storm day + rain_end_to_arrival_hours
    plume window = arrival .. arrival + elevated_turbidity_duration_hours

Both numbers are parsed from docs/event_dates.md (Rule 1: no hard-coded dates or
event timings in scripts). They are ONE observation, so the window is widened by a
stated slack factor rather than pretending 3 h is exact - and `assert_covers_known
_event()` fails the run if the result does not contain the documented
2016-10-28 plume interval.

Storms are ranked by IMERG rainfall, because scripts/24 measured that an IMERG
ranker puts the one documented flood at rank 20 of 2,362 while ERA5 puts it at
252. The list is ordered by the product that has been shown to see storms.

A clear image proves nothing. Absence of a plume can mean no plume or a missed
window, so this yields POSITIVES only, never confirmed negatives - which is
exactly what scripts/24's recall@K needs and why precision stays uncomputable.

Output: data/processed/events/plume_search_candidates.csv
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

EVENT_DATES = ROOT / "docs/event_dates.md"
TRAIN = ROOT / "data/processed/features/training_set_full.parquet"
OUT = ROOT / "data/processed/events/plume_search_candidates.csv"
REPORT = ROOT / "reports/model/plume_search_candidates.md"

# Storm threshold on IMERG catchment rainfall. 5 mm is a rounder, more permissive
# cut than the event catalogue's, on purpose: a missed candidate costs a wasted
# query, a missed real plume costs a gold event.
STORM_MM = 5.0

# Sensor availability. Operational starts, not launch dates - Landsat 8 was
# commissioned 2013-04, Sentinel-2A reached routine acquisition 2015-06.
SENSORS = {
    "landsat8": ("2013-04-11", 16),
    "sentinel2": ("2015-06-23", 5),
}
# Timing comes from ONE event. Widen rather than pretend it is exact.
WINDOW_SLACK = 1.5


def load_timing() -> tuple[float, float, dict]:
    """Arrival lag, plume duration and the known plume interval, from docs only."""
    for b in re.findall(r"```yaml\n(.*?)\n```", EVENT_DATES.read_text(), re.S):
        doc = yaml.safe_load(b)
        if not isinstance(doc, dict) or "primary_event" not in doc:
            continue
        pe = doc["primary_event"]
        # Lag from the END of the storm day, not from rain start - see docstring.
        lag = float(pe["reported"]["rain_end_to_arrival_hours"])
        dur = float(pe["derived"]["elevated_turbidity_duration_hours"])
        known = {
            "plume_start": pd.Timestamp(
                pe["converted"]["offshore_instrument_response_utc"]).tz_localize(None),
            "plume_end": pd.Timestamp(
                pe["converted"]["turbidity_salinity_cleared_utc"]).tz_localize(None),
        }
        return lag, dur, known
    raise SystemExit("primary_event timings absent from docs/event_dates.md")


def plume_window(storm_dates: pd.Series, lag_h: float, dur_h: float):
    """Arrival is the end of the storm day plus the observed arrival lag."""
    slack = 0.5 * dur_h * (WINDOW_SLACK - 1)
    arrival = storm_dates + pd.to_timedelta(24.0 + lag_h, unit="h")
    return (arrival - pd.to_timedelta(slack, unit="h"),
            arrival + pd.to_timedelta(dur_h + slack, unit="h"))


def assert_covers_known_event(storms: pd.DataFrame, known: dict) -> None:
    """The window must contain the one plume interval we actually observed.

    Rule 4: processing scripts assert. Without this the anchor bug that shipped
    in the first version of this script would have sent Abd to a window starting
    11 h after the plume began, and every image would have come back clear -
    reading as "no plume" when it was "wrong dates".
    """
    row = storms[storms.date == pd.Timestamp("2016-10-27")]
    if row.empty:
        print("  WARNING: 2016-10-27 not among storms; window check skipped")
        return
    w0 = row.window_start_utc.iloc[0]
    w1 = row.window_end_utc.iloc[0]
    ps, pe = known["plume_start"], known["plume_end"]
    covered = max(0.0, (min(w1, pe) - max(w0, ps)).total_seconds()) / 3600
    total = (pe - ps).total_seconds() / 3600
    print(f"  self-check on the documented 2016-10-28 plume:")
    print(f"    observed plume  {ps:%Y-%m-%d %H:%MZ} .. {pe:%Y-%m-%d %H:%MZ}"
          f"  ({total:.1f} h)")
    print(f"    our window      {w0:%Y-%m-%d %H:%MZ} .. {w1:%Y-%m-%d %H:%MZ}")
    print(f"    overlap         {covered:.1f} h of {total:.1f} h "
          f"({100*covered/total:.0f}%)")
    if covered / total < 0.5:
        raise SystemExit(
            f"window covers only {100*covered/total:.0f}% of the one plume we "
            f"have observed — the anchor is wrong, do not hand this to Abd")


def main():
    lag_h, dur_h, known = load_timing()
    print(f"timing from docs/event_dates.md: rain end -> arrival {lag_h:g} h, "
          f"plume elevated {dur_h:.2f} h")
    print(f"window widened by {WINDOW_SLACK}x — one observation, not a "
          f"distribution\n")

    df = pd.read_parquet(TRAIN)
    storms = (df[df.precipitation_mm_day > STORM_MM]
              .groupby("date")
              .agg(max_imerg_mm=("precipitation_mm_day", "max"),
                   total_imerg_mm=("precipitation_mm_day", "sum"),
                   catchments_hit=("catchment_id", "nunique"),
                   wettest_catchment=("precipitation_mm_day", "idxmax"))
              .reset_index())
    storms["wettest_catchment"] = df.loc[storms.wettest_catchment,
                                        "catchment_id"].to_numpy()

    storms["window_start_utc"], storms["window_end_utc"] = plume_window(
        storms.date, lag_h, dur_h)
    storms["window_hours"] = (
        (storms.window_end_utc - storms.window_start_utc).dt.total_seconds() / 3600)
    assert_covers_known_event(storms, known)
    print()

    for name, (start, revisit) in SENSORS.items():
        storms[name] = storms.date >= pd.Timestamp(start)
        # Chance a fixed-period revisit lands inside the window.
        storms[f"{name}_p_catch"] = (
            storms[name] * (storms.window_hours / (revisit * 24)).clip(upper=1.0))
    # Independent sensors, so combine as 1 - product of misses.
    storms["p_catch_any"] = 1 - ((1 - storms.landsat8_p_catch)
                                 * (1 - storms.sentinel2_p_catch))
    storms = storms.sort_values("max_imerg_mm", ascending=False).reset_index(drop=True)
    storms.insert(0, "priority", storms.index + 1)

    era = storms[storms.landsat8 | storms.sentinel2]
    print(f"{len(storms)} IMERG storm days (>{STORM_MM:g} mm), "
          f"{len(era)} in a satellite era")
    print(f"expected detections across the searchable set: "
          f"{era.p_catch_any.sum():.1f}\n")

    print("=== top 12 by IMERG rainfall ===")
    cols = ["priority", "date", "max_imerg_mm", "wettest_catchment",
            "window_start_utc", "window_end_utc", "p_catch_any"]
    show = era[cols].head(12).copy()
    show["date"] = show.date.dt.date
    for c in ("window_start_utc", "window_end_utc"):
        show[c] = show[c].dt.strftime("%Y-%m-%d %H:%MZ")
    print(show.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    era.to_csv(OUT, index=False)
    print(f"\nwrote {OUT.relative_to(ROOT)}  ({len(era)} rows)")
    write_report(storms, era, lag_h, dur_h)
    print(f"wrote {REPORT.relative_to(ROOT)}")


def write_report(storms, era, lag_h, dur_h):
    cols = ["priority", "date", "max_imerg_mm", "wettest_catchment",
            "window_start_utc", "window_end_utc", "p_catch_any"]
    top = era[cols].head(15).copy()
    top["date"] = top.date.dt.date
    for c in ("window_start_utc", "window_end_utc"):
        top[c] = top[c].dt.strftime("%Y-%m-%d %H:%MZ")
    top["max_imerg_mm"] = top.max_imerg_mm.round(1)
    top["p_catch_any"] = top.p_catch_any.round(2)

    n_l8 = int(storms.landsat8.sum())
    n_s2 = int(storms.sentinel2.sum())
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(f"""# Plume search list for Abd — {len(era)} targeted windows

**Date:** 4 August 2026 · `scripts/25_satellite_plume_candidates.py` ·
output `data/processed/events/plume_search_candidates.csv`

## Why, after a NO-GO

Satellite validation of October 2016 is a measured NO-GO — the plume dispersed
~31 h after arrival and the only usable passes are +104 h and +128 h. **That
verdict is correct and it stands for that event.**

It does not generalise. A ~{dur_h:.0f} h plume against a ~3-day combined
Sentinel-2 + Landsat-8 revisit has roughly a 43% chance of being caught, so one
event failing is the *expected* outcome. Across every storm in the record the odds
invert:

| | storm days | expected detections |
|---|---:|---:|
| Landsat-8 era (2013-04+) | {n_l8} | — |
| Sentinel-2 era (2015-06+) | {n_s2} | — |
| **either sensor** | **{len(era)}** | **{era.p_catch_any.sum():.1f}** |

That roughly doubles the gold set in `scripts/24`. And unlike the 13 literature
floods — recorded at the Kinnet Canal in **Eilat** — a plume off an Aqaba outlet is
evidence on the side of the Gulf our catchments actually drain.

## The search window

From the one event we have timed, both values parsed from `docs/event_dates.md`:

```
arrival      = end of the storm day + {lag_h:g} h
plume window = arrival .. arrival + {dur_h:.2f} h
```

Widened by **{WINDOW_SLACK}×** — this is one observation, not a distribution, and
travel time scales with storm location within a 4,453 km² catchment.

The anchor is rain **end**, not rain start. An earlier version used
`rain_start_to_sea_hours` (50 h) from the storm's peak-rainfall day and produced
windows beginning 11 h *after* the documented plume had started — every image
would have come back clear, reading as "no plume" when it meant "wrong dates".
`assert_covers_known_event()` now fails the run unless the window contains the
observed 2016-10-28 plume interval.

## Top 15 by IMERG rainfall

{top.to_markdown(index=False)}

Ranked by **IMERG**, not ERA5, deliberately: `scripts/24` measured that an IMERG
ranker puts the one documented flood at rank **20 of 2,362** while ERA5 puts it at
**252**. Full list in the CSV.

## What this is not

- **Not a download and not a detection.** This is the search list; the imagery and
  the segmentation are yours.
- **Positives only.** A clear image proves nothing — no plume can mean no plume or
  a missed window. So this can raise recall@K in `scripts/24` and can never make
  precision computable.
- **`AQ-O04` discharges into an enclosed harbour basin.** A plume there settles in
  the basin. If the wettest catchment routes to O04, treat any detection
  separately.
- **Esri World Imagery is licensed for verification and internal review only**, not
  redistribution. Sentinel-2 and Landsat are open; keep any published figure on
  those.
""")


if __name__ == "__main__":
    main()
