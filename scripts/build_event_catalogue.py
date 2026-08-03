#!/usr/bin/env python3
"""Rank 28 years of daily rainfall into a candidate storm catalogue.

This is the point of stage 1. One confirmed event teaches a model nothing;
this produces the ~100 candidate storm days that stage 2 then resolves at
half-hourly intensity, and that the runoff classifier eventually trains on.

Percentiles
-----------
Computed over **wet days only** (>= WET_DAY_MM), following the ETCCDI
convention for R99p. Aqaba is hyper-arid: most days are exactly zero, so a
percentile taken over all days is dominated by dry days and a "99th
percentile" ends up describing ordinary drizzle. Both are recorded so the
choice is visible, but ranking uses the wet-day series.

Per catchment, not per box
--------------------------
Every threshold is per catchment. AQ-C01 reaches 90 km inland to the Ma'an
highlands and AQ-C05 is a 36 km2 coastal wadi; one shared threshold would
describe neither. This is what makes "exceeds this catchment's own 99th
percentile" a measurement rather than a guess — and it is the number Nizar's
GEFS exceedance probability needs.

Event dates come from the literature, never from here
-----------------------------------------------------
docs/event_dates.md rule 1: never hard-code an event date in a script. The
literature dates are parsed from that file's machine-readable block and force
-included in the catalogue regardless of their rank, because the daily screen
can under-rank a short violent burst — the known limitation of stage 1.

Usage
-----
    python scripts/build_event_catalogue.py
    python scripts/build_event_catalogue.py --top-n 150
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

import pandas as pd  # noqa: E402
import yaml  # noqa: E402

DAILY_PARQUET = (
    PROJECT_ROOT / "data" / "processed" / "features" / "catchment_rainfall_daily.parquet"
)
EVENT_DATES = PROJECT_ROOT / "docs" / "event_dates.md"
OUT_EVENTS = PROJECT_ROOT / "data" / "processed" / "events" / "events.parquet"
OUT_CLIMATOLOGY = (
    PROJECT_ROOT / "data" / "processed" / "features"
    / "catchment_rainfall_climatology.parquet"
)
OUT_SUMMARY = OUT_EVENTS.with_suffix(".summary.json")

#: A "wet day". The standard meteorological threshold, and the one ETCCDI uses.
WET_DAY_MM = 1.0

#: Percentiles retained for the climatology table.
PERCENTILES = (0.50, 0.75, 0.90, 0.95, 0.99, 0.999)

#: Percentile used to rank and to define an exceedance.
RANKING_PERCENTILE = 0.99

#: Kept deliberately generous. The daily screen can under-rank a short intense
#: burst that lands on a modest-total day, and a tight top-N would drop exactly
#: those. Cheap insurance: stage 2 only pays for the ones we keep.
DEFAULT_TOP_N = 100

DEPTH_COLUMN = "precipitation_depth_mm"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("catalogue")


def literature_dates() -> list[dict]:
    """Event dates parsed from docs/event_dates.md, never hard-coded here."""
    text = EVENT_DATES.read_text()
    blocks = re.findall(r"```yaml\n(.*?)```", text, re.S)
    if not blocks:
        logger.warning("no machine-readable block in %s", EVENT_DATES.name)
        return []

    parsed = yaml.safe_load(blocks[-1]) or {}
    found: list[dict] = []
    for key, entry in parsed.items():
        if not isinstance(entry, dict):
            continue
        event_id = str(entry.get("event_id", ""))
        if not event_id or event_id.startswith("TO_BE_"):
            logger.info("%s is unresolved in event_dates.md — not forced in", key)
            continue
        arrival = (entry.get("converted") or {}).get("flood_arrival_utc")
        if arrival is None:
            continue
        found.append(
            {
                "event_id": event_id,
                "date": pd.Timestamp(arrival).tz_convert("UTC").normalize(),
                "source": key,
            }
        )
    return found


def build_climatology(daily: pd.DataFrame) -> pd.DataFrame:
    """Per-catchment percentiles, over wet days and over all days."""
    rows = []
    for catchment_id, group in daily.groupby("catchment_id", sort=True):
        all_days = group[DEPTH_COLUMN].dropna()
        wet_days = all_days[all_days >= WET_DAY_MM]
        row = {
            "catchment_id": catchment_id,
            "window_hours": 24,
            "n_days": int(len(all_days)),
            "n_wet_days": int(len(wet_days)),
            "wet_day_threshold_mm": WET_DAY_MM,
            "wet_day_fraction": round(len(wet_days) / max(len(all_days), 1), 4),
            "mean_all_days_mm": round(float(all_days.mean()), 4) if len(all_days) else None,
        }
        for q in PERCENTILES:
            label = f"p{q * 100:g}".replace(".", "_")
            row[f"{label}_wet_mm"] = (
                round(float(wet_days.quantile(q)), 4) if len(wet_days) else None
            )
            row[f"{label}_all_mm"] = (
                round(float(all_days.quantile(q)), 4) if len(all_days) else None
            )
        rows.append(row)
    return pd.DataFrame(rows)



def group_into_storms(
    by_day: pd.DataFrame,
    max_gap_days: int = 1,
    protected_ids: set[str] | None = None,
) -> pd.DataFrame:
    """Merge consecutive wet days into single storms.

    A storm that starts on the evening of the 17th and peaks on the 18th
    appears in a daily record as two days. Ranked as two candidates it wins
    two of the catalogue's slots, and — far worse — the same storm can then
    land in both the training and the test split, where it makes the model
    look skilful at predicting something it has already seen.

    Measured before this was added: 99 candidate days were only 84 distinct
    storms, with 14 counted twice. The giveaway was pairs of consecutive days
    carrying *identical* peak 3-hour intensity, because both windows contained
    the same burst.

    The storm is named for its wettest day, so the ID points at the day the
    rainfall actually peaked — EXCEPT where a member day carries a literature
    ID, which always wins.

    That exception is not cosmetic. `docs/event_dates.md` fixes the canonical
    ID for the demo event as AQ-2016-10-28, the UTC flood-arrival date, and
    contract §2 says IDs are never renamed. Naming that storm for its wettest
    day silently renamed it to AQ-2016-10-27 and broke the join with every
    stored result that references the contract ID.
    """
    protected = protected_ids or set()
    if by_day.empty:
        return by_day.assign(storm_id=[], storm_days=[])

    ordered = by_day.sort_values("date").reset_index(drop=True)
    gaps = ordered["date"].diff().dt.days
    # A gap of NaN (first row) or > max_gap_days starts a new storm.
    ordered["storm_index"] = (gaps.isna() | (gaps > max_gap_days)).cumsum()

    storms = []
    for _, member_days in ordered.groupby("storm_index"):
        peak = member_days.loc[member_days["max_daily_mm"].idxmax()]
        named = set(member_days["event_id"]) & protected
        if named:
            # A literature ID in the storm takes precedence over the wettest
            # day, so the contract ID survives the merge.
            keeper = sorted(named)[0]
            peak = peak.copy()
            peak["event_id"] = keeper
            peak["date"] = member_days.loc[
                member_days["event_id"] == keeper, "date"
            ].iloc[0]
        storms.append({
            **peak.drop(labels=["storm_index"]).to_dict(),
            "storm_days": int(len(member_days)),
            "storm_start": member_days["date"].min(),
            "storm_end": member_days["date"].max(),
            "storm_total_mm": float(member_days["max_daily_mm"].sum()),
            "merged_event_ids": ",".join(sorted(member_days["event_id"])),
        })
    return pd.DataFrame(storms)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily", type=Path, default=DAILY_PARQUET)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    args = parser.parse_args()

    if not args.daily.exists():
        logger.error("%s missing — run scripts/aggregate_daily_to_catchments.py first",
                     args.daily)
        return 1

    daily = pd.read_parquet(args.daily)
    daily["date"] = pd.to_datetime(daily["timestamp_utc"], utc=True).dt.normalize()

    n_days = daily["date"].nunique()
    span = f"{daily['date'].min().date()} .. {daily['date'].max().date()}"
    logger.info("Event catalogue")
    logger.info("  daily rows   %d over %d distinct day(s), %s",
                len(daily), n_days, span)

    climatology = build_climatology(daily)
    OUT_CLIMATOLOGY.parent.mkdir(parents=True, exist_ok=True)
    climatology.to_parquet(OUT_CLIMATOLOGY, index=False)

    p_label = f"p{RANKING_PERCENTILE * 100:g}".replace(".", "_")
    thresholds = climatology.set_index("catchment_id")[f"{p_label}_wet_mm"].to_dict()
    logger.info("  wet-day p99 per catchment (mm): %s",
                {k: v for k, v in thresholds.items()})

    daily["catchment_p99_wet_mm"] = daily["catchment_id"].map(thresholds)
    daily["exceeds_p99"] = daily[DEPTH_COLUMN] >= daily["catchment_p99_wet_mm"]
    daily["anomaly_ratio"] = (
        daily[DEPTH_COLUMN] / daily["catchment_p99_wet_mm"]
    ).round(4)

    # One row per DAY: a storm hits the region, not a single catchment. Rank on
    # the wettest catchment that day, but carry the catchment-max and the count
    # of catchments that exceeded their own p99.
    by_day = (
        daily.groupby("date")
        .agg(
            max_daily_mm=(DEPTH_COLUMN, "max"),
            mean_daily_mm=(DEPTH_COLUMN, "mean"),
            wettest_catchment=(DEPTH_COLUMN, lambda s: daily.loc[s.idxmax(), "catchment_id"]),
            catchments_exceeding_p99=("exceeds_p99", "sum"),
            max_anomaly_ratio=("anomaly_ratio", "max"),
            min_valid_area_fraction=("valid_area_fraction", "min"),
        )
        .reset_index()
    )

    by_day["event_id"] = by_day["date"].dt.strftime("AQ-%Y-%m-%d")

    # Merge consecutive wet days into storms BEFORE ranking, so the top-N are
    # N distinct storms rather than N days that may include the same storm
    # twice. Only wet days can join a storm — otherwise every day in the
    # record chains into one run.
    wet = by_day[by_day["max_daily_mm"] >= WET_DAY_MM].copy()
    dry = by_day[by_day["max_daily_mm"] < WET_DAY_MM].copy()
    storms = group_into_storms(
        wet, protected_ids={item["event_id"] for item in literature_dates()}
    )
    if not dry.empty:
        dry = dry.assign(storm_days=1, storm_start=dry["date"],
                         storm_end=dry["date"],
                         storm_total_mm=dry["max_daily_mm"],
                         merged_event_ids=dry["event_id"])
        storms = pd.concat([storms, dry], ignore_index=True)

    merged_away = len(by_day) - len(storms)
    logger.info("  %d wet day(s) -> %d storm(s); %d duplicate day(s) merged",
                len(wet), len(storms), merged_away)

    by_day = storms.sort_values("max_daily_mm", ascending=False).reset_index(drop=True)
    by_day["rank"] = by_day.index + 1

    selected = by_day.head(args.top_n).copy()
    selected["selection_reason"] = f"top {args.top_n} by max catchment daily rainfall"

    # Force-include literature events regardless of rank.
    forced = literature_dates()
    for item in forced:
        # The literature date may have been merged into a storm named for a
        # neighbouring, wetter day — so match on membership, not just on the
        # storm's own date.
        match = by_day[
            by_day["merged_event_ids"].str.contains(item["event_id"], regex=False)
        ]
        if match.empty:
            match = by_day[by_day["date"] == item["date"]]
        if match.empty:
            logger.warning(
                "%s (%s) is not in the daily record — outside the swept range?",
                item["event_id"], item["date"].date(),
            )
            continue
        row = match.iloc[0]
        if row["event_id"] in set(selected["event_id"]):
            logger.info("%s already in the top %d at rank %d",
                        item["event_id"], args.top_n, int(row["rank"]))
            continue
        extra = match.copy()
        extra["selection_reason"] = (
            f"forced in from docs/event_dates.md ({item['source']}) — "
            f"ranked {int(row['rank'])} by daily total"
        )
        selected = pd.concat([selected, extra], ignore_index=True)
        logger.info("forced in %s (rank %d by daily screen)",
                    item["event_id"], int(row["rank"]))

    selected = selected.sort_values("rank").reset_index(drop=True)
    selected["candidate_generation_scope"] = "daily screening, stage 1 of 2"
    selected["search_scope_start_utc"] = str(daily["date"].min())
    selected["search_scope_end_utc"] = str(daily["date"].max())
    # True only once the whole record has been swept AND ranked.
    selected["is_exhaustive"] = bool(n_days >= 9000)

    OUT_EVENTS.parent.mkdir(parents=True, exist_ok=True)
    selected.to_parquet(OUT_EVENTS, index=False)

    summary = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "days_screened": int(n_days),
        "date_range": span,
        "candidates_selected": int(len(selected)),
        "top_n": args.top_n,
        "wet_day_threshold_mm": WET_DAY_MM,
        "ranking_percentile": RANKING_PERCENTILE,
        "percentile_basis": "wet days only (ETCCDI R99p convention)",
        "is_exhaustive": bool(selected["is_exhaustive"].iloc[0]) if len(selected) else False,
        "forced_from_literature": [f["event_id"] for f in forced],
        "wet_day_p99_mm_by_catchment": {k: v for k, v in thresholds.items()},
        "caveats": [
            "Ranked on DAILY totals. A short violent burst on an otherwise "
            "modest day can be under-ranked; intensity, not daily depth, is "
            "what floods a wadi. Mitigated by a generous top-N and by forcing "
            "in the literature dates — not eliminated. Belongs in the model card.",
            "Percentiles are per catchment. AQ-C01 reaches the Ma'an highlands "
            "and AQ-C05 is a coastal wadi; a shared threshold would describe "
            "neither.",
        ],
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, default=str) + "\n")

    logger.info("  selected     %d candidate day(s)", len(selected))
    logger.info("  exhaustive   %s", summary["is_exhaustive"])
    logger.info("wrote %s", OUT_EVENTS.relative_to(PROJECT_ROOT))
    logger.info("wrote %s", OUT_CLIMATOLOGY.relative_to(PROJECT_ROOT))

    logger.info("\n  top 5 candidate days:")
    for _, r in selected.head(5).iterrows():
        logger.info("    %-14s %6.2f mm  %s  (%d catchment(s) over p99)",
                    r["event_id"], r["max_daily_mm"], r["wettest_catchment"],
                    int(r["catchments_exceeding_p99"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
