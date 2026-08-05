#!/usr/bin/env python3
"""Assemble the one table the runoff model trains on.

One row per (event x catchment), joining every stream on `catchment_id`:

    rainfall     Karam   daily depth, percentile, anomaly ratio
    antecedent   Karam   soil moisture T-24/-72 h, prior 24/72 h/7 d rain, wind
    terrain      Mahdi   area, relief, slope, drainage density
    land & soil  Pulga   bare fraction, built-up, clay/sand/silt, erodibility
    urban        Pulga   road density, building fraction, mapped drainage
    label        Karam   runoff response, tiered

Partial inputs are recorded, never faked
----------------------------------------
A missing source is written into `feature_matrix_status.json` with the reason
and the owning task, and its columns are simply absent — not zero-filled, not
imputed. This follows `catchment_integration_status.json`, which recorded a
blocked dependency honestly rather than fabricating catchment polygons to get
a green run.

The rule that keeps the labels honest
-------------------------------------
ERA5-Land `sro` / `ssro` are LABELS. They are asserted out of the feature
list, because a target that also appears as an input produces a model that
scores near-perfectly and predicts nothing.

Usage
-----
    python scripts/build_feature_matrix.py
    python scripts/build_feature_matrix.py --require-complete   # CI-style gate
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

import pandas as pd  # noqa: E402

FEATURES = PROJECT_ROOT / "data" / "processed" / "features"
EVENTS = PROJECT_ROOT / "data" / "processed" / "events" / "events.parquet"
DAILY = FEATURES / "catchment_rainfall_daily.parquet"
CLIMATOLOGY = FEATURES / "catchment_rainfall_climatology.parquet"

OUT = FEATURES / "event_catchment_features.parquet"
STATUS = PROJECT_ROOT / "data" / "processed" / "events" / "feature_matrix_status.json"

#: Optional per-catchment sources, with the task that owns each.
OPTIONAL_SOURCES = {
    "terrain": (FEATURES / "catchment_terrain.parquet", "Mahdi — delineation"),
    "landcover": (FEATURES / "landcover_by_catchment.parquet",
                  "Pulga — tasks/phase2/04-pulga.md §0"),
    "soil": (FEATURES / "soil_by_catchment.parquet",
             "Pulga — tasks/phase2/04-pulga.md §0"),
    "urban": (FEATURES / "urban_by_catchment.parquet",
              "Pulga — tasks/phase2/04-pulga.md §0"),
}

#: Per-(event, catchment) sources. These join on TWO keys, not one, because the value
#: varies by event as well as by catchment — soil moisture before the storm is the whole
#: point of an antecedent feature. Joining these on catchment_id alone would silently
#: fan out the row count.
EVENT_SOURCES = {
    "antecedent": (FEATURES / "event_antecedents.parquet", "Karam — this task, §4"),
}

#: Never features. Asserted, not just documented.
#:
#: `label_` matters as much as the raw names. extract_event_antecedents.py deliberately
#: prefixes its two targets `label_surface_runoff_mm` / `label_subsurface_runoff_mm`, and
#: those do NOT start with "surface_runoff" — so a guard listing only the raw spellings
#: has a hole exactly where the real labels arrive. That is the shape of every bug this
#: project has hit: the safety net misses the one case that occurs.
LABEL_ONLY_PREFIXES = ("sro", "ssro", "surface_runoff", "subsurface_runoff", "label_")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger("matrix")


#: Columns that exist for joining, sorting or provenance and must NOT be trained on.
#:
#: `rank` is the important one and the least obvious. It is the storm's position in our
#: own catalogue by rainfall, so it correlates strongly with runoff and looks like a
#: brilliant predictor — but a live forecast has no rank. You cannot know where tomorrow's
#: storm places among 27 years of history until the history is complete. A model trained
#: on it scores well offline and cannot be deployed at all, which is worse than a model
#: that scores badly.
NON_FEATURE_COLUMNS = (
    "event_id", "catchment_id", "date", "event_date", "timestamp_utc",
    "rank", "selection_reason", "candidate_generation_scope",
    "search_scope_start_utc", "search_scope_end_utc", "is_exhaustive",
    "storm_start", "storm_end", "storm_days", "merged_event_ids",
    "wettest_catchment", "quality_flag", "source_geometry_status",
)


def feature_roles(matrix) -> dict:
    """Classify every column so the modeller can choose columns instead of guessing.

    The reason this exists: 115 of the 130 numeric columns are **constant within a
    catchment**. Across the whole table they take only five distinct values, one per
    catchment, so a tree that splits on `soil_clay_0_5cm` is not learning about soil —
    it is learning "this is AQ-C03". With ~390 labelled rows and five catchments that is
    the dominant overfitting risk, and no amount of extra rows fixes it: the cure is
    choosing which columns to hand the model, which is what this block enables.
    """
    static, varying, non_feature, non_numeric = [], [], [], []
    for column in matrix.columns:
        if column in NON_FEATURE_COLUMNS:
            non_feature.append(column)
        elif column.lower().startswith(LABEL_ONLY_PREFIXES):
            continue                      # labels are asserted out entirely
        elif matrix[column].dtype.kind not in "ifb":
            non_numeric.append(column)
        elif matrix.groupby("catchment_id")[column].nunique(dropna=False).max() <= 1:
            static.append(column)
        else:
            varying.append(column)

    return {
        "event_varying": sorted(varying),
        "static_per_catchment": sorted(static),
        "non_feature": sorted(non_feature),
        "non_numeric": sorted(non_numeric),
        "counts": {
            "event_varying": len(varying),
            "static_per_catchment": len(static),
            "non_feature": len(non_feature),
        },
        "guidance": (
            f"{len(static)} columns are constant within a catchment and therefore carry "
            f"only five distinct values in the whole table; {len(varying)} vary by event. "
            "Handing a tree all of them lets it identify the catchment instead of "
            "learning the process, which random CV will reward and leave-one-catchment-out "
            "will expose. Start from event_varying, add static features deliberately and "
            "few at a time, and compare random CV against LOCO — the gap between them is "
            "the leakage, measured."
        ),
        "never_train_on": (
            "`rank` is the trap in non_feature: it is this catalogue's rainfall ranking, "
            "so it predicts runoff well and does not exist for a live forecast. A model "
            "using it cannot be deployed."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-complete", action="store_true",
                        help="exit non-zero if any source is missing")
    args = parser.parse_args()

    for required in (EVENTS, DAILY, CLIMATOLOGY):
        if not required.exists():
            logger.error("%s missing", required.relative_to(PROJECT_ROOT))
            return 1

    events = pd.read_parquet(EVENTS)
    daily = pd.read_parquet(DAILY)
    climatology = pd.read_parquet(CLIMATOLOGY)

    daily["date"] = pd.to_datetime(daily["timestamp_utc"], utc=True).dt.normalize()
    events["date"] = pd.to_datetime(events["date"], utc=True)

    # The daily table carries a placeholder event_id ("DAILY-SWEEP") from the
    # sweep. Drop it before joining, or the merge produces event_id_x/_y and
    # the real identifier silently disappears.
    daily = daily.drop(columns=[c for c in ("event_id",) if c in daily.columns])

    # One row per (event, catchment): the rainfall that catchment saw that day.
    matrix = daily.merge(
        events[["event_id", "date", "rank", "selection_reason",
                "catchments_exceeding_p99"]],
        on="date", how="inner",
    )
    logger.info("base: %d row(s) = %d event(s) x %d catchment(s)",
                len(matrix), matrix["event_id"].nunique(),
                matrix["catchment_id"].nunique())

    depth = "precipitation_depth_mm"
    p99 = climatology.set_index("catchment_id")["p99_wet_mm"].to_dict()
    matrix["catchment_p99_wet_mm"] = matrix["catchment_id"].map(p99)
    matrix["rain_anomaly_ratio"] = (matrix[depth] / matrix["catchment_p99_wet_mm"]).round(4)

    present, missing = {}, {}
    for name, (path, owner) in OPTIONAL_SOURCES.items():
        if not path.exists():
            missing[name] = {
                "path": str(path.relative_to(PROJECT_ROOT)),
                "owner": owner,
                "reason": "file does not exist",
            }
            logger.warning("%-10s MISSING — %s", name, owner)
            continue
        frame = pd.read_parquet(path)
        if "catchment_id" not in frame.columns:
            missing[name] = {
                "path": str(path.relative_to(PROJECT_ROOT)),
                "owner": owner,
                "reason": "no catchment_id column to join on",
            }
            logger.error("%-10s has no catchment_id — cannot join", name)
            continue

        before = len(matrix)
        overlap = [c for c in frame.columns
                   if c in matrix.columns and c != "catchment_id"]
        matrix = matrix.merge(
            frame.drop(columns=overlap), on="catchment_id", how="left",
        )
        assert len(matrix) == before, (
            f"joining {name} changed the row count {before} -> {len(matrix)}; "
            "the source has duplicate catchment_id values"
        )
        present[name] = {
            "path": str(path.relative_to(PROJECT_ROOT)),
            "columns": int(len(frame.columns) - 1),
        }
        logger.info("%-10s joined  %d column(s)", name, len(frame.columns) - 1)

    # Per-(event, catchment) sources. Joined LEFT so an event whose ERA5 month has not
    # downloaded yet keeps its row with NaN antecedents, rather than vanishing from the
    # matrix — a shrinking row count is much harder to notice than a NaN column.
    for name, (path, owner) in EVENT_SOURCES.items():
        if not path.exists():
            missing[name] = {
                "path": str(path.relative_to(PROJECT_ROOT)),
                "owner": owner,
                "reason": "file does not exist",
            }
            logger.warning("%-10s MISSING — %s", name, owner)
            continue
        frame = pd.read_parquet(path)
        keys = ["event_id", "catchment_id"]
        if any(k not in frame.columns for k in keys):
            missing[name] = {
                "path": str(path.relative_to(PROJECT_ROOT)),
                "owner": owner,
                "reason": f"needs {keys} to join on",
            }
            logger.error("%-10s lacks %s — cannot join", name, keys)
            continue

        # Drop the labels HERE rather than relying on the guard below. The guard is the
        # backstop; a source that is known to carry its own targets should not be handing
        # them to the join in the first place.
        labels = [c for c in frame.columns
                  if any(c.lower().startswith(p) for p in LABEL_ONLY_PREFIXES)]
        frame = frame.drop(columns=labels)
        overlap = [c for c in frame.columns if c in matrix.columns and c not in keys]

        before = len(matrix)
        matrix = matrix.merge(frame.drop(columns=overlap), on=keys, how="left")
        assert len(matrix) == before, (
            f"joining {name} changed the row count {before} -> {len(matrix)}; "
            f"the source has duplicate {keys} pairs"
        )
        joined = len(frame.columns) - len(keys) - len(overlap)
        covered = int(matrix[frame.columns.difference(keys)[0]].notna().sum())
        present[name] = {
            "path": str(path.relative_to(PROJECT_ROOT)),
            "columns": int(joined),
            "labels_withheld": labels,
            "rows_with_values": covered,
            "rows_without_values": int(len(matrix) - covered),
        }
        logger.info("%-10s joined  %d column(s) on %s — %d/%d rows have values "
                    "(%d await ERA5); withheld labels %s",
                    name, joined, keys, covered, len(matrix),
                    len(matrix) - covered, labels)

    # Enforce the label rule structurally.
    leaked = [c for c in matrix.columns
              if any(c.lower().startswith(p) for p in LABEL_ONLY_PREFIXES)]
    if leaked:
        raise SystemExit(
            f"\nRunoff columns leaked into the feature matrix: {leaked}\n"
            "ERA5-Land runoff is the LABEL. A target that also appears as an "
            "input produces a model that scores near-perfectly and predicts "
            "nothing. Remove them from the joined source.\n"
        )

    matrix = matrix.sort_values(["rank", "catchment_id"]).reset_index(drop=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    matrix.to_parquet(OUT, index=False)

    status = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows": int(len(matrix)),
        "events": int(matrix["event_id"].nunique()),
        "catchments": int(matrix["catchment_id"].nunique()),
        "columns": int(len(matrix.columns)),
        "sources_present": present,
        "sources_missing": missing,
        "complete": not missing,
        "feature_roles": feature_roles(matrix),
        "label_rule": (
            "ERA5-Land surface/sub-surface runoff are labels only and are "
            "asserted out of this table."
        ),
        "note": (
            "Missing sources are absent, not zero-filled. A zero bare-ground "
            "fraction is a claim about the catchment; an absent column is a "
            "claim about our data, and only the second one is true."
        ),
    }
    STATUS.write_text(json.dumps(status, indent=2) + "\n")

    logger.info("wrote %s — %d rows x %d columns",
                OUT.relative_to(PROJECT_ROOT), len(matrix), len(matrix.columns))
    if missing:
        logger.warning("INCOMPLETE: %s still missing", ", ".join(missing))
        logger.warning("status -> %s", STATUS.relative_to(PROJECT_ROOT))
        if args.require_complete:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
