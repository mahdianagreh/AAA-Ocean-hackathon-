"""Class imbalance: resample to train, keep natural prevalence to calibrate.

The dataset is 11,810 catchment-days at 7.9% positive. Two distinct problems
come out of that, and one fix cannot address both.

1. LEARNING. At 7.9% the trees can drive loss down while barely modelling the
   positive class. `min_child_weight` is a floor on the sum of hessians in a
   leaf, and for logistic loss h = p(1-p): starting at p = 0.079 gives
   h = 0.073, so a leaf needs ~55 positives before it is allowed to exist. We
   have 928 positives across 11 features and 5 catchments, so genuinely
   predictive regions holding fewer than 55 get pruned before they can
   contribute. Resampling to 20% and weighting the positive class raises the
   effective h and those branches survive.

2. NUMBERS. Fixing (1) deliberately distorts the loss being optimised, so the
   model no longer emits true probabilities - it emits inflated ones. Platt
   scaling fits p = 1/(1+exp(A*s+B)) and B absorbs the base rate, so a
   calibrator fitted where positives are 20% encodes a 1-in-5 prior. Applied
   where they are 7.9% every probability comes out too high.

So the classifier trains on resampled data, and the calibrator is fitted on
data at natural prevalence that the classifier never saw. The second stage
exists to repair what the first intentionally broke.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TARGET = "target"
STRATUM = "negative_stratum"

# Negatives per positive in the classifier-fit set. 1:4 lands at 20% positive.
# Lower and the negatives stop teaching the boundary; higher and recall falls
# away again.
NEG_PER_POS = 4

# Fraction of the non-test data reserved for calibration, split by TIME.
# Not random: consecutive days share a storm, soil moisture and prior rainfall,
# so a random split would let the calibrator score rows the classifier
# effectively already knows.
CALIB_FRACTION = 0.25


@dataclass
class FoldData:
    """One fold, split three ways. Only `fit` is resampled."""
    fit_X: pd.DataFrame
    fit_y: np.ndarray
    cal_X: pd.DataFrame
    cal_y: np.ndarray
    test_X: pd.DataFrame
    test_y: np.ndarray
    scale_pos_weight: float
    composition: dict

    def summary(self) -> str:
        c = self.composition
        return (f"fit {c['fit_rows']:,} ({c['fit_pos_rate']:.1%} pos, "
                f"{c['hard']} hard + {c['easy']:,} easy)  ·  "
                f"cal {c['cal_rows']:,} ({c['cal_pos_rate']:.1%})  ·  "
                f"test {c['test_rows']:,} ({c['test_pos_rate']:.1%})  ·  "
                f"spw {self.scale_pos_weight:.1f}")


def stratified_negative_sample(
    df: pd.DataFrame, *, neg_per_pos: int = NEG_PER_POS, seed: int = 20260803
) -> pd.DataFrame:
    """All positives, every hard negative, easy negatives to reach the ratio.

    Hard negatives - days with measurable rain that produced little runoff -
    are where the decision boundary is. There are only 656 in the whole
    dataset against 928 positives, so an even hard/easy split is arithmetically
    impossible: a fold needing 1,300 hard negatives has ~510 available. Taking
    every hard negative and filling with easy lands at 16-21% hard, which is
    the most the data allows.
    """
    rng = np.random.default_rng(seed)
    pos = df[df[TARGET] == 1]
    hard = df[(df[TARGET] == 0) & (df[STRATUM] == "hard")]
    easy = df[(df[TARGET] == 0) & (df[STRATUM] == "easy")]

    n_neg = len(pos) * neg_per_pos
    n_easy = max(0, n_neg - len(hard))
    if n_easy > len(easy):
        n_easy = len(easy)
    take = rng.choice(easy.index.to_numpy(), size=n_easy, replace=False) \
        if n_easy else np.array([], dtype=easy.index.dtype)

    out = pd.concat([pos, hard, easy.loc[take]])
    return out.sample(frac=1.0, random_state=seed)      # shuffle


def build_fold(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    features: list[str],
    *,
    calib_fraction: float = CALIB_FRACTION,
    neg_per_pos: int = NEG_PER_POS,
    seed: int = 20260803,
) -> FoldData:
    """Split one fold three ways: resampled fit, natural calibration, natural test.

    The calibration slice is the LATEST `calib_fraction` of the training data by
    date, so the classifier trains on the past and the calibrator is fitted on
    the period just before the test set - closer to deployment conditions than
    a random slice would be.
    """
    tr = train_df.sort_values("date")
    cut = int(len(tr) * (1.0 - calib_fraction))
    fit_raw, cal = tr.iloc[:cut], tr.iloc[cut:]

    fit = stratified_negative_sample(fit_raw, neg_per_pos=neg_per_pos, seed=seed)

    n_pos = int(fit[TARGET].sum())
    n_neg = len(fit) - n_pos
    # Weighting on top of resampling: resampling gets the ratio to 1:4, the
    # weight closes the remaining gap so positive-rich leaves clear
    # min_child_weight.
    spw = float(n_neg / max(n_pos, 1))

    comp = {
        "fit_rows": len(fit), "fit_pos": n_pos,
        "fit_pos_rate": n_pos / max(len(fit), 1),
        "hard": int((fit[STRATUM] == "hard").sum()),
        "easy": int((fit[STRATUM] == "easy").sum()),
        "cal_rows": len(cal), "cal_pos": int(cal[TARGET].sum()),
        "cal_pos_rate": cal[TARGET].mean() if len(cal) else float("nan"),
        "test_rows": len(test_df), "test_pos": int(test_df[TARGET].sum()),
        "test_pos_rate": test_df[TARGET].mean() if len(test_df) else float("nan"),
        "fit_date_max": str(fit_raw.date.max().date()) if len(fit_raw) else None,
        "cal_date_min": str(cal.date.min().date()) if len(cal) else None,
    }

    return FoldData(
        fit_X=fit[features], fit_y=fit[TARGET].to_numpy(),
        cal_X=cal[features], cal_y=cal[TARGET].to_numpy(),
        test_X=test_df[features], test_y=test_df[TARGET].to_numpy(),
        scale_pos_weight=spw, composition=comp,
    )


def hessian_floor_note(base_rate: float, min_child_weight: float,
                       spw: float = 1.0) -> str:
    """How many positives a leaf needs at this base rate. The concrete reason
    resampling is not cosmetic."""
    h = base_rate * (1 - base_rate) * spw
    return (f"base rate {base_rate:.1%} · h = {h:.4f} · "
            f"a leaf needs ~{min_child_weight / h:.0f} positives to clear "
            f"min_child_weight={min_child_weight:g}")
