"""The two predictors, behind one interface.

Both expose fit / predict_proba, so the validation harness runs them through
identical splits and identical metrics. That is what makes "did the model
beat the baseline" an honest question rather than two numbers computed
different ways.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class Predictor(ABC):
    name: str = "predictor"

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "Predictor": ...

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """P(runoff) in [0, 1], one per row."""


class RuleBaseline(Predictor):
    """SCS curve-number runoff depth, mapped to a probability.

        S  = 25400 / CN - 254            potential retention, mm
        Ia = 0.2 S                       initial abstraction
        Q  = (P - Ia)^2 / (P - Ia + S)   runoff depth, mm   for P > Ia

    CN is raised by bare ground and dry antecedent soil and by slope, which
    is how the physical story enters a formula with nothing fitted.

    The only free parameter is the Q -> probability scaling, and it is set
    from the training set's positive rate rather than tuned, so the baseline
    stays a baseline instead of quietly becoming a second model.
    """

    name = "rule_baseline"

    CN_BASE = 74.0        # arid, sparse cover, hydrologic soil group C
    CN_BARE = 14.0        # fully bare vs fully vegetated
    CN_DRY = 6.0          # crusted dry surface sheds water
    CN_SLOPE = 0.45       # per degree of mean slope
    SM_CAPACITY = 0.45    # m3/m3, for normalising dryness

    def __init__(self) -> None:
        self._scale: float | None = None

    def _curve_number(self, X: pd.DataFrame) -> np.ndarray:
        cn = np.full(len(X), self.CN_BASE)
        if "bare_fraction" in X:
            cn = cn + self.CN_BARE * (X["bare_fraction"].to_numpy() - 0.5)
        if "soil_moisture_t24h" in X:
            sm = X["soil_moisture_t24h"].to_numpy()
            dryness = np.clip(1.0 - sm / self.SM_CAPACITY, 0, 1)
            cn = cn + self.CN_DRY * (dryness - 0.5)
        if "slope_mean_deg" in X:
            cn = cn + self.CN_SLOPE * (X["slope_mean_deg"].to_numpy() - 10.0)
        return np.clip(cn, 30.0, 98.0)

    def runoff_depth(self, X: pd.DataFrame) -> np.ndarray:
        """Q in mm. Exposed because Component B needs runoff volume."""
        p = X.get("rain_24h_mm", X.get("rain_3h_mm"))
        p = pd.to_numeric(p, errors="coerce").fillna(0.0).to_numpy()
        s = 25400.0 / self._curve_number(X) - 254.0
        ia = 0.2 * s
        excess = p - ia
        return np.where(excess > 0, excess ** 2 / (excess + s), 0.0)

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "RuleBaseline":
        q = self.runoff_depth(X)
        rate = float(np.mean(y)) if len(y) else 0.1
        # scale so the depth at the (1 - rate) quantile maps to p = 0.5
        pivot = np.quantile(q, 1.0 - rate) if q.size else 1.0
        self._scale = float(max(pivot, 1e-3))
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self._scale is None:
            raise RuntimeError("fit() first - the scale comes from the training set")
        q = self.runoff_depth(X)
        return 1.0 / (1.0 + np.exp(-(q - self._scale) / (0.35 * self._scale)))


class CalibratedGBM(Predictor):
    """XGBoost, then Platt scaling on the raw margin.

    The trees sum to a logit. Applying a plain sigmoid to it assumes the
    logit's scale is already right, which for boosted trees it is not -
    boosting inflates margins. Platt fits

        p = 1 / (1 + exp(A*margin + B))

    and A = -1, B = 0 recovers the plain sigmoid exactly. So calibration is
    not an extra layer; it is declining to assume two numbers that can be
    measured from held-out data.

    Platt rather than isotonic because isotonic is non-parametric and would
    trace noise at a few hundred rows. Two parameters survive small samples.

    Calibration is fitted by internal cross-validation ON THE TRAINING FOLD
    ONLY. The outer test fold is never seen - the same class of leakage as
    the runoff-as-feature tautology, in a different place.
    """

    name = "calibrated_gbm"

    def __init__(self, *, n_estimators: int = 220, max_depth: int = 3,
                 learning_rate: float = 0.06, calib_cv: int = 3,
                 random_state: int = 20260803):
        self.params = dict(
            n_estimators=n_estimators,
            max_depth=max_depth,          # shallow: few hundred rows
            learning_rate=learning_rate,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=2.0,               # the lambda in the leaf-weight formula
            min_child_weight=4.0,
            random_state=random_state,
            eval_metric="logloss",
            n_jobs=2,
        )
        self.calib_cv = calib_cv
        self.model = None
        self.raw = None
        self._features: list[str] = []

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "CalibratedGBM":
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.model_selection import StratifiedKFold
        from xgboost import XGBClassifier

        self._features = list(X.columns)
        n_pos = int(np.sum(y))
        # scale_pos_weight handles imbalance without resampling, which would
        # invent rows we do not have
        spw = float((len(y) - n_pos) / max(n_pos, 1))
        self.raw = XGBClassifier(**self.params, scale_pos_weight=spw)

        folds = int(min(self.calib_cv, max(2, n_pos)))
        if n_pos < 2 * folds:
            # too few positives to cross-validate the calibrator honestly;
            # train uncalibrated and say so rather than fake it
            self.raw.fit(X, y)
            self.model = None
            return self

        self.model = CalibratedClassifierCV(
            self.raw, method="sigmoid",          # Platt
            cv=StratifiedKFold(folds, shuffle=True,
                               random_state=self.params["random_state"]),
        )
        self.model.fit(X, y)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X = X[self._features]
        est = self.model if self.model is not None else self.raw
        return est.predict_proba(X)[:, 1]

    @property
    def is_calibrated(self) -> bool:
        return self.model is not None

    def shap_values(self, X: pd.DataFrame):
        """Exact TreeSHAP on the underlying booster.

        Exact rather than sampled - the general Shapley formula is exponential
        in the feature count, and tree ensembles admit a polynomial algorithm.
        That precision is one of the practical reasons to choose trees here.
        """
        import shap

        booster = self.raw
        if self.model is not None:
            booster = self.model.calibrated_classifiers_[0].estimator
        return shap.TreeExplainer(booster).shap_values(X[self._features])
