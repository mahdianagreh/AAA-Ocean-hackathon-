"""Anchor the sediment proxy, and persist it so request time gets a class.

WHAT WAS MISSING
----------------
Mahdi established the hard part in scripts/26: the sediment formula only ranks the
one documented major flood correctly when its magnitude input is the rule-based
curve-number runoff depth driven by IMERG rainfall — 12th of 2,362 days (PASS) —
because the two ERA5-derived inputs inherit ERA5's underestimate of that storm
(176th and 193rd, both FAIL).

`runoff_model.predict` already feeds the right thing: `baseline.runoff_depth(X)` IS
that CN depth. What was missing is the SCALE. `SedimentProxy._k` starts as None,
`is_anchored` is False, so `classify()` is skipped and every response comes back
`sediment_class: null` with an UNANCHORED note. The exposure formula then multiplies
by a sediment term of zero and every reef zone reads `minimal` — a product of five
terms, one of which is nothing.

This writes the anchor once so the loader can apply it.

WHY A SIDECAR FILE AND NOT A RE-TRAINED ARTEFACT
-----------------------------------------------
`k` is a calibration constant, not a learned parameter. Re-saving Mahdi's `.joblib`
to carry it would mean rewriting a trained artefact to store one float, and would
invalidate its git_commit provenance for a change that has nothing to do with
training. A sidecar keeps the artefact immutable and the anchor auditable.

WHY THE INDEX IS STORED, NOT JUST k
-----------------------------------
`k = mass / index_at_anchor`, so `k` is only valid for the formula and feature set
that produced that index. Change a term in `SedimentProxy.index()`, or change which
columns the model consumes, and the stored `k` silently becomes a wrong
tonnes-per-index scale — the failure mode being confident wrong masses, not an
error. So the index is stored too, and `runoff_model` RE-COMPUTES it at load and
refuses to anchor if it has drifted.

Run:
    ../.venv/bin/python 27_anchor_sediment_proxy.py
    ../.venv/bin/python 27_anchor_sediment_proxy.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend" / "src"))

TRAINING_SET = PROJECT_ROOT / "data" / "processed" / "features" / "training_set_full.parquet"
ANCHOR_FILE = PROJECT_ROOT / "data" / "models" / "sediment_anchor.json"

#: The index and k must agree to this relative tolerance at load time. Tight enough
#: that a changed formula term is caught, loose enough to survive float ordering.
DRIFT_TOLERANCE = 1e-6


def compute_anchor_index(bundle, frame):
    """The proxy's index for the anchor event, via the CN depth the model serves.

    Deliberately routed through `bundle["baseline"].runoff_depth`, the same call
    `predict()` makes, rather than recomputing a depth here. If the two ever diverge
    the anchor would be calibrated against a magnitude the live path never sees.
    """
    import pandas as pd

    from models.sediment_proxy import ANCHOR_CATCHMENT, ANCHOR_EVENT

    day = pd.to_datetime(ANCHOR_EVENT.removeprefix("AQ-")).date()
    frame = frame.copy()
    frame["_day"] = pd.to_datetime(frame["date"]).dt.date
    row = frame[(frame["_day"] == day) & (frame["catchment_id"] == ANCHOR_CATCHMENT)]
    if row.empty:
        sys.exit(
            f"anchor row absent: {ANCHOR_EVENT} / {ANCHOR_CATCHMENT} is not in "
            f"{TRAINING_SET.name}. The anchor cannot be invented from a nearby day — "
            "the mass belongs to that catchment on that date."
        )
    if len(row) > 1:
        sys.exit(f"{len(row)} rows for the anchor event; expected exactly one")

    feats = bundle["row"]["features"]
    X = row.reindex(columns=feats)
    depth = bundle["baseline"].runoff_depth(X)
    index = float(bundle["sediment"].index(X, depth)[0])
    return index, float(depth[0]), feats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import pandas as pd

    from models import artifacts
    from models.sediment_proxy import (
        ANCHOR_BANDS,
        ANCHOR_CATCHMENT,
        ANCHOR_EVENT,
        ANCHOR_MASS_T,
        CLASSES,
    )

    if not TRAINING_SET.exists():
        sys.exit(f"{TRAINING_SET} missing — run Mahdi's scripts/13 first")

    bundle = artifacts.load()
    frame = pd.read_parquet(TRAINING_SET)
    index, depth, feats = compute_anchor_index(bundle, frame)

    if index <= 0:
        sys.exit(
            f"anchor index is {index}, which cannot be calibrated. The CN runoff depth "
            f"for {ANCHOR_EVENT} came out {depth} mm — check that "
            "`precipitation_mm_day` is present in the training set, since the depth is "
            "driven by it and a missing column yields zero without erroring."
        )

    k = ANCHOR_MASS_T / index

    print(f"anchor event      {ANCHOR_EVENT} / {ANCHOR_CATCHMENT}")
    print(f"CN runoff depth   {depth:.4f} mm   (IMERG-driven, the input scripts/26 passed)")
    print(f"sediment index    {index:,.4f}")
    print(f"published mass    {ANCHOR_MASS_T:,.0f} t   Kalman et al. (2025)")
    print(f"k                 {k:.8f} t per index unit")
    print()
    print("resulting class bands, as fractions of the anchor index:")
    edges = [b * index for b in ANCHOR_BANDS]
    for name, lo, hi in zip(CLASSES,
                            [0.0, *edges],
                            [*edges, float("inf")]):
        hi_s = "inf" if hi == float("inf") else f"{hi:,.0f}"
        print(f"  {name:8s} {lo:>14,.0f} .. {hi_s:>14s}"
              + ("   <- the anchor event lands here" if lo <= index < hi else ""))

    if args.dry_run:
        print("\nDRY RUN: nothing written")
        return 0

    ANCHOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    ANCHOR_FILE.write_text(json.dumps({
        "anchor_event": ANCHOR_EVENT,
        "anchor_catchment": ANCHOR_CATCHMENT,
        "mass_t": ANCHOR_MASS_T,
        "mass_source": "Kalman et al. (2025), 10.5194/nhess-25-3201-2025",
        "index_at_anchor": index,
        "cn_runoff_depth_mm": depth,
        "k_tonnes_per_index": k,
        "magnitude_input": "RuleBaseline.runoff_depth, curve-number, IMERG-driven",
        "magnitude_input_rationale": (
            "scripts/26: the two ERA5-derived magnitude inputs rank the anchor event "
            "176th and 193rd of 2,362 days (FAIL) because they inherit ERA5's "
            "underestimate of it; this one ranks it 12th (PASS) and is never fit to "
            "ERA5 sro."
        ),
        "model_version_id": bundle["row"]["id"],
        "feature_count": len(feats),
        "drift_tolerance": DRIFT_TOLERANCE,
        "verify_at_load": (
            "runoff_model recomputes index_at_anchor and refuses to anchor if it has "
            "moved by more than drift_tolerance. k is only valid for the formula and "
            "feature set that produced this index; a stale k yields confident wrong "
            "tonnages rather than an error."
        ),
        "one_point_caveat": (
            "ONE measurement fixes the SCALE, never the SHAPE. The formula has six "
            "terms and a single point constrains one degree of freedom, so any mass for "
            "a different event is an extrapolation along an unverified curve. Relative "
            "classes remain the honest output."
        ),
        "written_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "written_by": "scripts/27_anchor_sediment_proxy.py",
    }, indent=2) + "\n")

    print(f"\nwrote {ANCHOR_FILE.relative_to(PROJECT_ROOT)}")
    print("runoff_model applies it on next load; /runoff/predict will return a class.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
