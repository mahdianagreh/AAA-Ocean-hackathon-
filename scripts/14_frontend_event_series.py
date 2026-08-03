#!/usr/bin/env python3
"""Derive the demo event's time series for the frontend, and be honest about gaps.

The vertical slice needs one thing the repo does not yet serve: a time axis with
values on it. This assembles what genuinely exists for AQ-2016-10-28 and marks
what does not, rather than interpolating to make a prettier chart.

WHAT EXISTS, MEASURED:
  - daily catchment rainfall, 5 catchments x 6 days, from
    catchment_rainfall_daily.parquet. Real, and coarse.
  - the wettest 1h/3h/6h/24h windows, from AQ-2016-10-28_summary.json. Real, but
    they are extrema over the AOI, not a series.
  - three mooring timestamps from Kalman et al. 2025: turbidity onset, cleared,
    and the peak magnitude. Real, published, and only three points.

WHAT DOES NOT EXIST:
  - any sub-daily rainfall series per catchment. rain_3h_mm and rain_24h_mm are
    NaN across the whole event window in the daily parquet, the 156-granule
    half-hourly product's values are not committed (data/processed/events/*.nc is
    gitignored), and the summary JSON carries only the grid's shape and extrema.
  - the mooring's 5-minute record. The JSON holds summary points, not the series.

So the frontend gets a series with real values at real timestamps and explicit
nulls in between. 09 rule 4: missing is never zero, and a gap renders as a gap.
Filling those gaps would be inventing the measurements the whole project exists
to avoid inventing.

    docker compose run --rm --entrypoint "" \\
      -v "$PWD/frontend/public/fixtures:/out" \\
      worker python /app/scripts/14_frontend_event_series.py --out /out
"""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# scripts/config.py was deleted on main while this frontend was being built, and the
# spatial constants moved to backend/src/config/spatial.py. Other scripts now resolve
# their own paths (see scripts/export_web_layers.py), so this does the same rather than
# reintroducing a module main deliberately removed.
#
# The AOIs are still imported rather than retyped: tests/test_spatial_contract.py exists
# precisely because a hardcoded bounding box is how the AOI silently regressed once
# already, and RETIRED_BOX is asserted against in spatial.py for the same reason.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
from config import spatial as _spatial  # noqa: E402


class cfg:  # noqa: N801 — kept lowercase so the call sites below read unchanged
    """The handful of paths and constants this script needs."""

    DATA = ROOT / "data"
    PROCESSED = DATA / "processed"
    VECTORS = PROCESSED / "vectors"
    FEATURES = PROCESSED / "features"
    REPO_ROOT = ROOT
    TERRAIN_AOI = _spatial.TERRAIN_AOI
    MARINE_AOI = _spatial.MARINE_AOI
    AQABA_AOI = _spatial.AQABA_AOI
    AOI_CRS_STORAGE = _spatial.CRS_STORAGE
    AOI_CRS_PROJECTED = _spatial.CRS_MEASURE

EVENT_ID = "AQ-2016-10-28"
# The window the demo scrubs. Starts before the rain and ends after the mooring
# cleared, so the whole arc is on the axis rather than cropped to the peak.
WINDOW = ("2016-10-26", "2016-10-30")


def daily_rainfall():
    """Per-catchment daily rainfall. Real values, six days, no interpolation."""
    path = cfg.FEATURES / "catchment_rainfall_daily.parquet"
    d = pd.read_parquet(path)
    d["timestamp_utc"] = pd.to_datetime(d["timestamp_utc"], utc=True, format="mixed")
    lo, hi = (pd.Timestamp(x, tz="UTC") for x in WINDOW)
    d = d[(d.timestamp_utc >= lo) & (d.timestamp_utc <= hi)].copy()

    series = {}
    for cid, g in d.groupby("catchment_id"):
        g = g.sort_values("timestamp_utc")
        series[cid] = [
            {
                "t": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                # None, not 0.0 — a quality-flagged or absent day is a gap.
                "mm": None if pd.isna(v) else round(float(v), 4),
                "coverage": None if pd.isna(c) else round(float(c), 3),
            }
            for ts, v, c in zip(g.timestamp_utc, g.precipitation_mm_day, g.coverage_fraction)
        ]
    return series, str(path.relative_to(cfg.REPO_ROOT))


def subdaily_status():
    """State plainly that there is no sub-daily series, and why.

    The UI needs this as data rather than as a comment, because 09 rule 8 says
    never claim exactness — and a time slider that steps in days while the event's
    own peak was a 3-hour window has to say so on screen.
    """
    summary = json.loads((cfg.PROCESSED / "events" / f"{EVENT_ID}_summary.json").read_text())
    ww = summary.get("wettest_windows", {})
    w3 = summary.get("wettest_3h_window_utc", {})
    grid = summary.get("grid", {})

    return {
        "available": False,
        "reason_key": "series.noSubDaily",
        "granules": summary.get("granules", {}).get("expected"),
        "grid_shape_time_lat_lon": grid.get("shape_time_lat_lon"),
        # Extrema, not a series — labelled so the UI cannot plot them as one.
        "extrema_not_a_series": True,
        "wettest_windows": {
            k: (round(float(v["max_mm"]), 3) if isinstance(v, dict) and "max_mm" in v else None)
            for k, v in ww.items()
        },
        "wettest_3h_window_utc": {
            "start": w3.get("start"),
            "end": w3.get("end"),
            "max_rain_3h_mm": round(float(w3["max_rain_3h_mm"]), 3) if "max_rain_3h_mm" in w3 else None,
            "derivation": w3.get("derivation"),
        },
    }


def mooring_markers():
    """The validation target: three real timestamps and the reported magnitudes.

    Every value carries the provenance tag from the source file. 07 §2 makes that
    structural — a reported number, a timezone-converted number and a computed
    number are three different things.
    """
    src = cfg.PROCESSED / "marine" / f"mooring_target_{EVENT_ID}.json"
    m = json.loads(src.read_text())
    t, mag, pos = m["timing_utc"], m["magnitude"], m["position"]

    return {
        "source_citation": m["source_citation"],
        "source_doi": m["source_doi"],
        "position": {
            "lon": pos["lon"],
            "lat": pos["lat"],
            "depth_m": pos["depth_m"],
            "uncertainty_radius_m": pos["uncertainty_radius_m"],
            "provenance": pos["provenance"],
            "note": pos["note"],
        },
        "markers": [
            {
                "key": "turbidity_onset",
                "t": t["turbidity_onset"],
                # "reported (timezone-converted…)" is a conversion, not a raw report
                "provenance": "converted",
            },
            {"key": "turbidity_cleared", "t": t["turbidity_cleared"], "provenance": "converted"},
        ],
        "elevated_duration_hours": {
            "value": t["elevated_duration_hours"],
            "unit": "h",
            "provenance": "converted",
        },
        "peak_suspended_sediment": {
            "value": mag["peak_suspended_sediment_g_l"],
            "unit": "g/L",
            "provenance": "reported",
        },
        "salinity_minimum": {
            "value": mag["salinity_minimum_psu"],
            "unit": "PSU",
            "provenance": "reported",
        },
        "salinity_anomaly": {
            "value": mag["salinity_anomaly_delta_psu"],
            "unit": "‰",
            "provenance": "reported",
            "uncertainty": {"sigma": mag["salinity_anomaly_sigma"]},
        },
        "sediment_mass_total": {
            "value": mag["sediment_mass_total_t"],
            "unit": "t",
            "provenance": "reported",
        },
        # There is no 5-minute series in the repo — only these summary points.
        "series_available": False,
        "source_file": str(src.relative_to(cfg.REPO_ROOT)),
    }


def event_catalogue(limit=25):
    """The historical event list, for the mode's event selector."""
    path = cfg.PROCESSED / "events" / "events.parquet"
    if not path.exists():
        return []
    d = pd.read_parquet(path).sort_values("rank").head(limit)
    out = []
    for _, r in d.iterrows():
        out.append(
            {
                "event_id": r["event_id"],
                "date": pd.Timestamp(r["date"]).strftime("%Y-%m-%d"),
                "rank": int(r["rank"]),
                "max_daily_mm": round(float(r["max_daily_mm"]), 3),
                "wettest_catchment": r["wettest_catchment"],
                "storm_days": int(r["storm_days"]) if pd.notna(r.get("storm_days")) else None,
                "selection_reason": r.get("selection_reason"),
            }
        )
    return out


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rainfall, rain_src = daily_rainfall()
    payload = {
        "event_id": EVENT_ID,
        "window_utc": {"start": f"{WINDOW[0]}T00:00:00Z", "end": f"{WINDOW[1]}T00:00:00Z"},
        "rainfall_daily": {
            "unit": "mm/day",
            "provenance": "modelled",
            "source": rain_src,
            "note": "NASA GPM IMERG V07, aggregated per catchment. Daily resolution.",
            "by_catchment": rainfall,
        },
        "subdaily": subdaily_status(),
        "mooring": mooring_markers(),
    }

    (out / "event.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    cat = event_catalogue()
    (out / "events.json").write_text(json.dumps(cat, ensure_ascii=False, indent=1))

    print("ReefShield frontend event series")
    print("=" * 62)
    for cid, pts in rainfall.items():
        vals = [p["mm"] for p in pts if p["mm"] is not None]
        gaps = sum(1 for p in pts if p["mm"] is None)
        print(f"  {cid}  {len(pts)} days  peak {max(vals):7.3f} mm  gaps {gaps}")
    print()
    print(f"  sub-daily series available: {payload['subdaily']['available']}"
          "   <- stated as data, not hidden")
    print(f"  wettest 3h window: {payload['subdaily']['wettest_3h_window_utc']['start']}"
          f" -> {payload['subdaily']['wettest_3h_window_utc']['end']}"
          f"  ({payload['subdaily']['wettest_3h_window_utc']['max_rain_3h_mm']} mm)")
    print(f"  mooring markers: {len(payload['mooring']['markers'])}"
          f"  (5-minute series available: {payload['mooring']['series_available']})")
    print(f"  event catalogue: {len(cat)} of 100 ranked events")
    print()
    total = sum(f.stat().st_size for f in out.glob("*.json"))
    print(f"  {len(list(out.glob('*.json')))} files, {total:,} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
