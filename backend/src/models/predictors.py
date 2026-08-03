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
        Ia = IA_RATIO * S                initial abstraction (0.05, not 0.2 -
                                         see IA_RATIO for why)
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

    # Initial abstraction ratio. The textbook 0.2 is calibrated on humid
    # catchments and is unusable here: it puts Ia at 12.7-20.4 mm, while
    # Aqaba's MAXIMUM daily rainfall in 27 years is 21.6 mm and the p99 is
    # 6.9 mm. At 0.2 the formula returned Q=0 on 11,798 of 11,810 rows - a
    # constant, whose average precision is just the base rate, so "the model
    # beat the baseline" compared against nothing.
    #
    # 0.05 is the documented arid-region value (Woodward et al. 2003, and the
    # basis of the NRCS Ia/S revision). It puts Ia at 3.2-5.1 mm, which is the
    # right order for storms of a few millimetres.
    IA_RATIO = 0.05

    def __init__(self) -> None:
        self._scale: float | None = None

    # Column names differ between the event matrix and the full-population set
    # (rain_24h_mm vs precipitation_mm_day, soil_moisture_t24h vs
    # soil_moisture). Candidates in preference order rather than one hardcoded
    # name, so the baseline works on both without a second implementation.
    RAIN_CANDIDATES = ("rain_24h_mm", "precipitation_mm_day", "rain_3h_mm",
                       "precipitation_depth_mm")
    SM_CANDIDATES = ("soil_moisture_t24h", "soil_moisture", "soil_moisture_lag1d",
                     "soil_moisture_t_minus_24h")
    BARE_CANDIDATES = ("bare_fraction", "frac_bare_sparse_vegetation")

    @staticmethod
    def _first(X: pd.DataFrame, names) -> np.ndarray | None:
        for n in names:
            if n in X.columns:
                v = pd.to_numeric(X[n], errors="coerce").to_numpy(dtype=float)
                return np.nan_to_num(v, nan=0.0)
        return None

    def _curve_number(self, X: pd.DataFrame) -> np.ndarray:
        cn = np.full(len(X), self.CN_BASE)
        bare = self._first(X, self.BARE_CANDIDATES)
        if bare is not None:
            cn = cn + self.CN_BARE * (bare - 0.5)
        sm = self._first(X, self.SM_CANDIDATES)
        if sm is not None:
            dryness = np.clip(1.0 - sm / self.SM_CAPACITY, 0, 1)
            cn = cn + self.CN_DRY * (dryness - 0.5)
        if "slope_mean_deg" in X.columns:
            slope = np.nan_to_num(
                pd.to_numeric(X["slope_mean_deg"], errors="coerce").to_numpy(float),
                nan=10.0)
            cn = cn + self.CN_SLOPE * (slope - 10.0)
        return np.clip(cn, 30.0, 98.0)

    def runoff_depth(self, X: pd.DataFrame) -> np.ndarray:
        """Q in mm. Exposed because Component B needs runoff volume."""
        p = self._first(X, self.RAIN_CANDIDATES)
        if p is None:
            raise KeyError(
                f"no rainfall column found; tried {self.RAIN_CANDIDATES}, "
                f"got {list(X.columns)}"
            )
        s = 25400.0 / self._curve_number(X) - 254.0
        ia = self.IA_RATIO * s
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


class WeightedGBM(Predictor):
    """XGBoost trained on resampled data, calibrated on natural prevalence.

    Differs from CalibratedGBM in where the calibrator comes from.
    CalibratedGBM uses internal cross-validation on whatever it is handed - fine
    when that data is at deployment prevalence, wrong here, because the fit set
    is deliberately resampled to 20% positive and Platt's intercept would encode
    a 1-in-5 prior. Applied to a 7.9% population every probability comes out
    inflated: correct ranking, wrong numbers, and only the numbers reach a user.

    So the calibration set is passed in explicitly. It must be
      (a) unseen by the classifier, and
      (b) at natural prevalence.
    See models/imbalance.py for how the fold is split to guarantee both.
    """

    name = "weighted_gbm"

    def __init__(self, *, scale_pos_weight: float = 1.0, n_estimators: int = 300,
                 max_depth: int = 4, learning_rate: float = 0.05,
                 min_child_weight: float = 4.0, random_state: int = 20260803):
        self.params = dict(
            n_estimators=n_estimators, max_depth=max_depth,
            learning_rate=learning_rate, subsample=0.85, colsample_bytree=0.85,
            reg_lambda=2.0, min_child_weight=min_child_weight,
            random_state=random_state, eval_metric="logloss", n_jobs=2,
            scale_pos_weight=scale_pos_weight,
        )
        self.raw = None
        self._platt: tuple[float, float] | None = None
        self._features: list[str] = []

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "WeightedGBM":
        """Classifier only. Uncalibrated until calibrate() is called."""
        from xgboost import XGBClassifier

        self._features = list(X.columns)
        self.raw = XGBClassifier(**self.params)
        self.raw.fit(X, y)
        return self

    def margin(self, X: pd.DataFrame) -> np.ndarray:
        """Raw log-odds, before any sigmoid.

        Platt is fitted on the margin rather than on predict_proba: applying a
        sigmoid first compresses the extremes, which is exactly where
        overconfidence lives, so fitting after it throws away the resolution
        needed to measure the distortion.
        """
        return self.raw.predict(X[self._features], output_margin=True)

    def calibrate(self, X_cal: pd.DataFrame, y_cal: np.ndarray) -> "WeightedGBM":
        """Fit A, B in p = 1/(1+exp(A*margin+B)) by minimising log loss.

        A = -1, B = 0 recovers the plain sigmoid, so this is not an extra layer
        - it is declining to assume two numbers that can be measured.
        """
        from sklearn.linear_model import LogisticRegression

        if len(np.unique(y_cal)) < 2:
            self._platt = None          # cannot calibrate on one class; say so
            return self
        s = self.margin(X_cal).reshape(-1, 1)
        lr = LogisticRegression(C=1e10, solver="lbfgs")   # unregularised
        lr.fit(s, y_cal)
        # sklearn gives p = sigmoid(w*s + b); Platt's form is
        # 1/(1+exp(A*s+B)), so A = -w and B = -b.
        self._platt = (float(-lr.coef_[0][0]), float(-lr.intercept_[0]))
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        s = self.margin(X)
        if self._platt is None:
            return 1.0 / (1.0 + np.exp(-s))     # plain sigmoid, uncalibrated
        a, b = self._platt
        return 1.0 / (1.0 + np.exp(a * s + b))

    @property
    def is_calibrated(self) -> bool:
        return self._platt is not None

    @property
    def platt_params(self) -> dict:
        if self._platt is None:
            return {"A": None, "B": None, "note": "uncalibrated"}
        a, b = self._platt
        return {"A": round(a, 4), "B": round(b, 4),
                "note": "A=-1, B=0 would be the plain sigmoid"}

    def shap_values(self, X: pd.DataFrame):
        import shap
        return shap.TreeExplainer(self.raw).shap_values(X[self._features])


class MagnitudeGBM(Predictor):
    """Regress log runoff magnitude, then calibrate the prediction to a probability.

    The classifier throws the target away at the threshold: a day at 0.0021 mm
    and one at 0.19 mm carry the same label, though they are two orders of
    magnitude apart. Regressing on log(sro) keeps that ordering and uses the
    whole target.

    The predicted magnitude is then a SCORE, and Platt maps it to P(target=1) on
    the natural-prevalence calibration set - the same machinery as WeightedGBM,
    fed a different score. So the two are directly comparable: identical splits,
    identical metrics, and only the thing being learned differs.

    log, not raw: sro spans 0 to 0.21 mm over four orders of magnitude, and a
    squared-error fit on raw values would be dominated by the handful of largest
    days and ignore the boundary entirely.
    """

    name = "magnitude_gbm"

    # Floor before the log. Smaller than the smallest nonzero sro in the data
    # (~1e-6 mm), so it separates true zeros from small positives instead of
    # collapsing them together.
    EPS = 1e-7

    def __init__(self, *, n_estimators: int = 400, max_depth: int = 4,
                 learning_rate: float = 0.05, min_child_weight: float = 4.0,
                 random_state: int = 20260803):
        self.params = dict(
            n_estimators=n_estimators, max_depth=max_depth,
            learning_rate=learning_rate, subsample=0.85, colsample_bytree=0.85,
            reg_lambda=2.0, min_child_weight=min_child_weight,
            random_state=random_state, n_jobs=2, objective="reg:squarederror",
        )
        self.raw = None
        self._platt: tuple[float, float] | None = None
        self._features: list[str] = []

    def fit(self, X: pd.DataFrame, y: np.ndarray) -> "MagnitudeGBM":
        """`y` is runoff magnitude in mm, NOT the binary target."""
        from xgboost import XGBRegressor

        self._features = list(X.columns)
        self.raw = XGBRegressor(**self.params)
        self.raw.fit(X, np.log(np.asarray(y, dtype=float) + self.EPS))
        return self

    def margin(self, X: pd.DataFrame) -> np.ndarray:
        """Predicted log magnitude. Used as the score for ranking and calibration."""
        return self.raw.predict(X[self._features])

    def calibrate(self, X_cal: pd.DataFrame, y_cal: np.ndarray) -> "MagnitudeGBM":
        """`y_cal` is the BINARY target here - the regressor is being mapped to
        a probability of exceeding the threshold."""
        from sklearn.linear_model import LogisticRegression

        if len(np.unique(y_cal)) < 2:
            self._platt = None
            return self
        s = self.margin(X_cal).reshape(-1, 1)
        lr = LogisticRegression(C=1e10, solver="lbfgs").fit(s, y_cal)
        self._platt = (float(-lr.coef_[0][0]), float(-lr.intercept_[0]))
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        s = self.margin(X)
        if self._platt is None:
            # No calibrator: rank-preserving squash so AP is still computable,
            # but the values are not probabilities and must not be displayed.
            return (s - s.min()) / max(np.ptp(s), 1e-9)
        a, b = self._platt
        return 1.0 / (1.0 + np.exp(a * s + b))

    @property
    def is_calibrated(self) -> bool:
        return self._platt is not None

    @property
    def platt_params(self) -> dict:
        if self._platt is None:
            return {"A": None, "B": None, "note": "uncalibrated"}
        a, b = self._platt
        return {"A": round(a, 4), "B": round(b, 4), "note": "fitted on log-magnitude"}

    def shap_values(self, X: pd.DataFrame):
        import shap
        return shap.TreeExplainer(self.raw).shap_values(X[self._features])
