"""Train and validate Component A - the runoff risk classifier.

Runs the rule baseline and the calibrated GBM through identical splits, so
the comparison is honest. Writes the model card as it goes, not at the end.

    .venv/bin/python scripts/11_train_runoff_model.py
    REEFSHIELD_FEATURE_SOURCE=parquet .venv/bin/python scripts/11_train_runoff_model.py
    .venv/bin/python scripts/11_train_runoff_model.py --no-static
"""

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend/src"))

from models import schema, validation                      # noqa: E402
from models.feature_store import get_feature_store          # noqa: E402
from models.predictors import CalibratedGBM, RuleBaseline   # noqa: E402

OUT = ROOT / "docs/model_card.md"


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=None)
    ap.add_argument("--no-static", action="store_true",
                    help="drop static terrain features - the ablation")
    args = ap.parse_args()

    store = get_feature_store(args.source)
    df, feats = store.load_training_matrix(include_static=not args.no_static)
    df = df.reset_index(drop=True)

    print(f"source: {store.provenance}")
    print(schema.describe(df, feats))
    print()

    reports = []
    for make in (RuleBaseline, CalibratedGBM):
        for fn in (validation.leave_one_catchment_out, validation.temporal_holdout):
            r = fn(make, df, feats)
            reports.append(r)
            print(f"--- {r.model} / {r.split} ---")
            cols = ["fold", "n_train", "n_test", "n_pos_test", "ap", "brier", "note"]
            print(r.frame()[cols].to_string(index=False))
            print()

    table = validation.compare(reports)
    print("=== comparison ===")
    print(table.to_string(index=False))

    loco_base = next(r for r in reports
                     if r.model == "rule_baseline" and r.split == "loco").pooled()
    loco_gbm = next(r for r in reports
                    if r.model == "calibrated_gbm" and r.split == "loco").pooled()
    verdict = "inconclusive"
    if loco_base["ap"] and loco_gbm["ap"]:
        d = loco_gbm["ap"] - loco_base["ap"]
        verdict = (f"GBM beats baseline by {d:+.3f} AP" if d > 0.02
                   else f"GBM does NOT clear the baseline ({d:+.3f} AP)")
    print(f"\nverdict: {verdict}")

    # calibration evidence on the temporal holdout
    yr = pd.to_datetime(df.event_time_utc, utc=True).dt.year
    tr, te = df[yr < 2015], df[yr >= 2015]
    calib = None
    gbm = None
    if len(te) and tr.runoff_label.nunique() > 1:
        gbm = CalibratedGBM().fit(tr[feats], tr.runoff_label.to_numpy())
        p = gbm.predict_proba(te[feats])
        calib = validation.calibration_table(te.runoff_label.to_numpy(), p)
        print("\n=== calibration on the temporal holdout ===")
        print(calib.to_string(index=False))
        print(f"calibrated: {gbm.is_calibrated}")

    write_card(store, df, feats, table, verdict, calib, gbm, args)
    print(f"\nwrote {OUT.relative_to(ROOT)}")


def write_card(store, df, feats, table, verdict, calib, gbm, args):
    synthetic = store.provenance.startswith("stub")
    banner = (
        "> ## THIS CARD DESCRIBES A SYNTHETIC RUN\n"
        "> The feature matrix does not exist yet — every rainfall granule has to be\n"
        "> re-pulled against the corrected AOI first. Numbers below come from a stub\n"
        "> with a known generating rule, and exist to prove the harness works.\n"
        "> **They are not results about Aqaba.**\n\n" if synthetic else ""
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(f"""# Model card — Component A, runoff risk classifier

**Generated:** `scripts/11_train_runoff_model.py` · commit `{git_sha()}`
**Feature source:** `{store.provenance}`
**Static features:** {"excluded (ablation)" if args.no_static else "included"}

{banner}---

## Data

```
{schema.describe(df, feats)}
```

Features used ({len(feats)}):

```
{chr(10).join('  ' + f for f in feats)}
```

**Label:** `runoff_label`, binary. Silver tier is ERA5-Land surface runoff exceeding
that catchment's own p99 within 24 h of the rainfall window — a *modelled* quantity
from ECMWF's land-surface scheme, not an observation. The single gold event is held
back and never trained on.

**`sro` and `ssro` are labels, never features.** Asserted in
`backend/src/models/schema.py`, not left as a comment.

---

## Results

{table.to_markdown(index=False)}

**Verdict:** {verdict}

Both predictors run through identical splits and identical metrics. If the rule
baseline wins, that is the reported result — a four-line formula matching gradient
boosting on a few hundred rows is a plausible outcome, not a failure to hide.

### Why these splits

**Leave-one-catchment-out.** Static terrain features are constant within a catchment,
so a random split lets the model recognise which catchment a row belongs to and score
beautifully while learning nothing. A data-design constraint, not a tuning preference.

The five folds are not equally informative: AQ-C01 is 96% of the drainage and carries
most positive labels. **All folds are reported; the mean alone would hide that.**

**Temporal holdout**, train ≤2014 / test ≥2015, so October 2016 is genuinely unseen.

### Why these metrics

Average precision leads, because floods are rare and accuracy is meaningless when
"never" scores well. Brier score measures the probability itself, which is what the
dashboard shows a user. ROC-AUC is reported but not led with — it stays flattering
under imbalance.

Any fold with fewer than 5 positives is flagged; its metrics are noise.

---

## Calibration

{"Platt scaling on the raw margin, fitted by internal cross-validation on the training fold only — never the test fold." if gbm is None or gbm.is_calibrated else "**Not applied:** too few positives to cross-validate a calibrator honestly. Reported uncalibrated rather than faked."}

{calib.to_markdown(index=False) if calib is not None else "_no holdout available_"}

Predicted against observed. A calibrated model tracks the two columns together.

---

## What this model cannot do

- **It does not predict a flood reaching the sea.** It predicts the Silver label —
  modelled runoff anomaly. One event has ground truth, and it is held out.
- **Five catchments is not a sample.** Any pattern across five points could be
  coincidence, and no validation scheme fixes that.
- **AQ-C01's area carries ±4%** from separating endorheic basins from DEM artifacts.
  Per-catchment totals inherit it.
- **It says nothing about the sea.** Transport is Component C; this feeds it a
  sediment class, nothing more.
""")


if __name__ == "__main__":
    main()
