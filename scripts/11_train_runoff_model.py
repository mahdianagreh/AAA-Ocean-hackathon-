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

# docs/model_card.md is reserved for runs on the real feature matrix. It is the
# file the pitch, the API and any reviewer will read, so a synthetic run must
# not be able to land there - even correctly banner-marked, a card full of
# fabricated metrics in the canonical location is one copy-paste from becoming
# a claim about Aqaba.
OUT = ROOT / "docs/model_card.md"
OUT_SYNTHETIC = ROOT / "docs/archive/model_card_SYNTHETIC_harness_check.md"


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

    # ---- Component D: sediment proxy -----------------------------------
    from models.sediment_proxy import SedimentProxy

    base = RuleBaseline().fit(df[feats], df.runoff_label.to_numpy())
    q = base.runoff_depth(df[feats])
    sp = SedimentProxy()
    sed = sp.classify(df[feats], q)
    tau = sp.sensitivity_to_tau(df[feats], q)

    print("\n=== Component D · sediment class ===")
    print(sed.sediment_class.value_counts()
          .reindex(list(sp.classify.__globals__["CLASSES"])).fillna(0)
          .astype(int).to_string())
    print(f"basis: {sed.class_basis.iloc[0]}")
    print("\n=== transmission loss sensitivity (Ali's slider) ===")
    print(tau.to_string(index=False))

    card = write_card(store, df, feats, table, verdict, calib, gbm, args, sp, sed, tau)
    print(f"\nwrote {card.relative_to(ROOT)}")
    if store.is_synthetic:
        print("  SYNTHETIC RUN - docs/model_card.md was not touched.")

    persist(store, df, feats, reports, table, verdict, sp, sed, args)


def persist(store, df, feats, reports, table, verdict, sp, sed, args):
    """Fit the servable model and register it.

    The models fitted above are per-fold and per-split - they exist to measure,
    and each has seen only part of the data. Serving wants one model fitted on
    every labelled row, which is a separate fit and never one of the fold
    models reused.
    """
    from models import artifacts

    if store.is_synthetic:
        print("\nno artifact written: synthetic run.")
        print("  artifacts.save() refuses synthetic input - a .joblib cannot "
              "carry a banner.")
        return None

    from models.sediment_proxy import ANCHOR_CATCHMENT, ANCHOR_EVENT

    y = df.runoff_label.to_numpy()
    final = CalibratedGBM().fit(df[feats], y)
    final_base = RuleBaseline().fit(df[feats], y)

    # Anchor the sediment proxy before saving it. Unanchored, classify() bands
    # against within-dataset quantiles, which is meaningless one row at a time -
    # serving would return the top class for every request. Anchoring makes the
    # bands absolute, so a class means the same thing in every response.
    anchor = df[(df.event_id == ANCHOR_EVENT) & (df.catchment_id == ANCHOR_CATCHMENT)]
    if len(anchor):
        idx = sp.index(anchor[feats], final_base.runoff_depth(anchor[feats]))
        sp = sp.__class__(sp.params).calibrate_to_anchor(float(idx[0]))
        print(f"\nsediment proxy anchored on {ANCHOR_EVENT}/{ANCHOR_CATCHMENT}")
    else:
        print(f"\nsediment proxy NOT anchored: {ANCHOR_EVENT}/{ANCHOR_CATCHMENT} "
              "is absent from the matrix.")
        print("  Serving will return the index and withhold the class, by design.")

    # per-catchment LOCO average precision -> the confidence term at serving.
    # LOCO fold names are the held-out catchment ids.
    loco = next(r for r in reports
                if r.model == "calibrated_gbm" and r.split == "loco")
    catchment_scores = {
        f.fold: float(f.ap) for f in loco.folds if f.ap is not None
    }

    # training feature ranges, so serving can tell extrapolation from
    # interpolation instead of trusting an edge leaf
    ranges = {
        c: (float(df[c].min()), float(df[c].max()))
        for c in feats if pd.api.types.is_numeric_dtype(df[c]) and df[c].notna().any()
    }

    row = artifacts.save(
        gbm=final,
        baseline=final_base,
        sediment=sp,
        features=feats,
        training_event_ids=df.event_id.dropna().astype(str).tolist(),
        metrics={
            "verdict": verdict,
            "comparison": table.to_dict(orient="records"),
            "catchment_ap_loco": catchment_scores,
            "is_calibrated": bool(final.is_calibrated),
            "static_features_included": not args.no_static,
        },
        feature_source=store.provenance,
        is_synthetic=False,
        feature_ranges=ranges,
        catchment_scores=catchment_scores,
    )
    print(f"\nregistered {row.id}")
    print(f"  artifact: {row.artifact_path}")
    print(f"  events:   {len(row.training_event_ids)}")
    print(f"  ledger:   data/models/model_versions.jsonl")
    return row


def write_card(store, df, feats, table, verdict, calib, gbm, args, sp, sed, tau):
    from models.sediment_proxy import ANCHOR_EVENT, CLASSES

    # Rendered before the template, because the template is one f-string and
    # a nested .format() on it would collide with its own placeholders.
    sed_dist = (sed.sediment_class.value_counts()
                .reindex(list(CLASSES)).fillna(0).astype(int)
                .rename_axis("class").rename("rows").to_frame().to_markdown())
    sed_basis = sed.class_basis.iloc[0]
    anchor_event = ANCHOR_EVENT
    tau_default = sp.params.transmission_loss
    tau_table = tau.to_markdown(index=False)
    synthetic = store.is_synthetic
    banner = (
        "> ## THIS CARD DESCRIBES A SYNTHETIC RUN\n"
        "> The feature matrix does not exist yet — every rainfall granule has to be\n"
        "> re-pulled against the corrected AOI first. Numbers below come from a stub\n"
        "> with a known generating rule, and exist to prove the harness works.\n"
        "> **They are not results about Aqaba.**\n\n" if synthetic else ""
    )
    out = OUT_SYNTHETIC if synthetic else OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"""# Model card — Component A, runoff risk classifier

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

## Component D — sediment load proxy

**A formula, not a model.** Nothing here is trained.

```
sediment_index = b · f(θ) · E(clay, sand, silt, SOC) · Q · D · (1 − τ)
```

| Term | Meaning | Source |
|---|---|---|
| `b` | bare fraction, 0–1 — the erodible surface | ESA WorldCover |
| `f(θ)` | slope term, `(θ/12°)^1.3` — transport capacity | GLO-30 |
| `E` | erodibility from soil texture — what is detachable | SoilGrids |
| `Q` | runoff volume in m³ — the carrier | Component A baseline |
| `D` | drainage density, km/km² — channel access | GLO-30 |
| `τ` | transmission loss — what never arrives | **assumption, see below** |

Output is a **relative class**, not a mass, per concept §10.4.

{sed_dist}

Basis: {sed_basis}

### The anchor

One published measurement exists: **≈24,400 t** for {anchor_event} (Kalman et al. 2025).
It fixes the index→tonnes **scale**. It cannot validate the **shape** — a single point
constrains one degree of freedom and the formula has six terms. **One point is not a
curve.** Any mass reported for another event is extrapolation along an unverified line,
and `mass_estimate_t()` refuses to run until anchored rather than returning a
comfortable number.

### Transmission loss — the project's largest assumption, now visible

Between **13.2% and 98%** of a desert flood infiltrates the wadi bed and never reaches
the sea. The Negev, the nearest studied analogue, is **20–85%**. Everything before this
module implied **τ = 0** — the most optimistic value available, and certainly wrong.

Default **τ = {tau_default}**, the Negev midpoint. Chosen because it is the nearest
documented setting, *not* because it is measured here. It is not.

{tau_table}

τ enters as the linear factor (1 − τ), so the whole curve follows from one evaluation.
Every classified row carries the τ used, so the assumption travels with the number
instead of living in a document.

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
- **The sediment proxy is not calibrated**, only anchored at one point, and its τ is
  assumed rather than measured for these wadis.
""")
    return out


if __name__ == "__main__":
    main()
