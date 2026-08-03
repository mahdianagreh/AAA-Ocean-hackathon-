"""The validation harness - the actual deliverable.

Two splitters, one metrics function, one comparison table. Both predictors
go through identical code, which is the only way "did the model beat the
baseline" is an honest question.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TEMPORAL_CUTOFF_YEAR = 2015   # train <= 2014, test >= 2015


@dataclass
class FoldResult:
    fold: str
    n_train: int
    n_test: int
    n_pos_test: int
    ap: float | None
    roc_auc: float | None
    brier: float | None
    base_rate: float
    note: str = ""

    @property
    def trustworthy(self) -> bool:
        """Fewer than 5 positives and every metric here is noise."""
        return self.n_pos_test >= 5


@dataclass
class Report:
    model: str
    split: str
    folds: list[FoldResult] = field(default_factory=list)

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame([f.__dict__ for f in self.folds])

    def pooled(self) -> dict:
        """Mean over folds that have enough positives to mean anything."""
        ok = [f for f in self.folds if f.trustworthy and f.ap is not None]
        if not ok:
            return {"ap": None, "roc_auc": None, "brier": None, "n_folds": 0}
        return {
            "ap": float(np.mean([f.ap for f in ok])),
            "roc_auc": float(np.mean([f.roc_auc for f in ok])),
            "brier": float(np.mean([f.brier for f in ok])),
            "n_folds": len(ok),
        }


def score(y_true: np.ndarray, p: np.ndarray) -> dict:
    from sklearn.metrics import (average_precision_score, brier_score_loss,
                                 roc_auc_score)

    out = {"base_rate": float(np.mean(y_true)) if len(y_true) else float("nan")}
    if len(np.unique(y_true)) < 2:
        # a fold with one class has no ranking metric - say so, do not fake it
        out.update(ap=None, roc_auc=None,
                   brier=float(brier_score_loss(y_true, p)) if len(y_true) else None)
        return out
    out.update(
        ap=float(average_precision_score(y_true, p)),
        roc_auc=float(roc_auc_score(y_true, p)),
        brier=float(brier_score_loss(y_true, p)),
    )
    return out


def _run(make_predictor, df, feats, splits, split_name) -> Report:
    rep = Report(model=make_predictor().name, split=split_name)
    for fold_name, tr_idx, te_idx in splits:
        tr, te = df.loc[tr_idx], df.loc[te_idx]
        y_tr = tr["runoff_label"].to_numpy()
        y_te = te["runoff_label"].to_numpy()

        if len(te) == 0 or len(tr) == 0:
            continue
        if len(np.unique(y_tr)) < 2:
            rep.folds.append(FoldResult(
                fold_name, len(tr), len(te), int(y_te.sum()),
                None, None, None, float(np.mean(y_te)) if len(y_te) else float("nan"),
                note="training fold has one class - skipped"))
            continue

        model = make_predictor().fit(tr[feats], y_tr)
        p = model.predict_proba(te[feats])
        s = score(y_te, p)
        rep.folds.append(FoldResult(
            fold=fold_name, n_train=len(tr), n_test=len(te),
            n_pos_test=int(y_te.sum()), ap=s["ap"], roc_auc=s["roc_auc"],
            brier=s["brier"], base_rate=s["base_rate"],
            note="" if int(y_te.sum()) >= 5 else "too few positives to trust",
        ))
    return rep


def leave_one_catchment_out(make_predictor, df: pd.DataFrame, feats: list[str]) -> Report:
    """Hold out one catchment entirely, five times.

    Static features are constant within a catchment, so a random split lets
    the model recognise which catchment a row belongs to and score
    beautifully while learning nothing. This is a data-design constraint,
    not a tuning preference.
    """
    splits = [
        (c, df.index[df.catchment_id != c], df.index[df.catchment_id == c])
        for c in sorted(df.catchment_id.unique())
    ]
    return _run(make_predictor, df, feats, splits, "loco")


def temporal_holdout(make_predictor, df: pd.DataFrame, feats: list[str],
                     cutoff_year: int = TEMPORAL_CUTOFF_YEAR) -> Report:
    """Train on everything before the cutoff, test on everything after.

    October 2016 must be genuinely unseen for the headline claim to mean
    anything.
    """
    yr = pd.to_datetime(df.event_time_utc, utc=True).dt.year
    tr = df.index[yr < cutoff_year]
    te = df.index[yr >= cutoff_year]
    return _run(make_predictor, df, feats,
                [(f"<{cutoff_year} -> >={cutoff_year}", tr, te)], "temporal")


def compare(reports: list[Report]) -> pd.DataFrame:
    """The table the model card is built around."""
    rows = []
    for r in reports:
        p = r.pooled()
        rows.append({
            "model": r.model, "split": r.split,
            "folds_used": p["n_folds"], "AP": p["ap"],
            "ROC_AUC": p["roc_auc"], "Brier": p["brier"],
        })
    return pd.DataFrame(rows)


def calibration_table(y_true: np.ndarray, p: np.ndarray, bins: int = 5) -> pd.DataFrame:
    """Predicted vs observed frequency - the calibration curve, as numbers.

    This is the evidence that calibration worked, rather than the assertion
    that it was applied.
    """
    q = pd.qcut(pd.Series(p), bins, duplicates="drop")
    g = pd.DataFrame({"p": p, "y": y_true}).groupby(q, observed=True)
    out = g.agg(n=("y", "size"), predicted=("p", "mean"), observed=("y", "mean"))
    return out.reset_index(drop=True)
