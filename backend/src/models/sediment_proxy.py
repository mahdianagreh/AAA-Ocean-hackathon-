"""Component D - sediment load proxy.

A FORMULA, NOT A MODEL. Nothing here is trained, and the docs say so in
those words. Concept doc §10.4 asks for a relative class, not a mass,
because one anchor point does not calibrate a curve.

    sediment_index = b · f(θ) · E(clay, sand, silt, SOC) · Q · D · (1 − τ)

      b     bare fraction, 0–1                      the erodible surface
      f(θ)  slope term, (θ/θ_ref)^1.3               transport capacity
      E     erodibility from soil texture            what is detachable
      Q     runoff volume, m³, from Component A      the carrier
      D     drainage density, km/km²                 channel access
      τ     transmission loss, 0–1                   what never arrives

Every term is dimensionless and normalised to ~1 at reference conditions
except Q, so the index is proportional to runoff volume and modified by the
catchment's capacity to supply and move sediment.

Transmission loss
-----------------
τ is the project's largest hidden assumption. Between 13.2% and 98% of a
desert flood infiltrates the wadi bed and never reaches the sea; the Negev
range is 20–85%. The pipeline before this module implied τ = 0, the most
optimistic value available and certainly wrong.

It is an explicit parameter here with a documented default and range, and it
is exposed as a scenario control so it can be moved on screen. That converts
a silent flaw into a visible, defensible feature.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

# ── transmission loss ────────────────────────────────────────────────────
# Literature range across arid catchments: 0.132–0.98. Negev, the closest
# studied analogue to Aqaba's wadis: 0.20–0.85. Default is the Negev midpoint,
# chosen because it is the nearest documented setting - not because it is
# measured here. It is not.
TAU_DEFAULT = 0.525
TAU_NEGEV = (0.20, 0.85)
TAU_LITERATURE = (0.132, 0.98)

# Reference conditions - the point at which every dimensionless term equals 1.
# Loosely the mid-range of the five Aqaba catchments, so the index is O(Q).
THETA_REF_DEG = 12.0
D_REF_KM_KM2 = 0.9
BARE_REF = 0.70
SLOPE_EXPONENT = 1.3      # empirical sediment yield ~ S^1.0–1.4

# The one published number available: Kalman et al. 2025 report ≈24,400 t of
# suspended sediment for the October 2016 event. ONE POINT IS NOT A CURVE.
ANCHOR_EVENT = "AQ-2016-10-28"
ANCHOR_CATCHMENT = "AQ-C01"
ANCHOR_MASS_T = 24_400.0

CLASSES = ("Low", "Medium", "High", "Extreme")
# Thresholds as a fraction of the anchor event's index. The October 2016
# event is a documented major flood, so it should land in High rather than at
# the top of the scale - leaving Extreme meaningful for something worse.
ANCHOR_BANDS = (0.25, 0.75, 1.50)


@dataclass(frozen=True)
class SedimentParams:
    """Everything tunable, in one place, so a scenario is a value not a patch."""
    transmission_loss: float = TAU_DEFAULT
    theta_ref_deg: float = THETA_REF_DEG
    d_ref_km_km2: float = D_REF_KM_KM2
    bare_ref: float = BARE_REF
    slope_exponent: float = SLOPE_EXPONENT

    def validate(self) -> None:
        if not 0.0 <= self.transmission_loss < 1.0:
            raise ValueError(
                f"transmission_loss must be in [0, 1); got {self.transmission_loss}"
            )

    @property
    def tau_in_negev_range(self) -> bool:
        return TAU_NEGEV[0] <= self.transmission_loss <= TAU_NEGEV[1]

    def as_dict(self) -> dict:
        d = asdict(self)
        d["tau_in_negev_range"] = self.tau_in_negev_range
        return d


def erodibility(clay_pct, sand_pct, silt_pct, soc_g_kg) -> np.ndarray:
    """Relative detachability of the surface, ~1 at reference soil.

    Silt and fine sand detach most readily; clay is cohesive and resists;
    organic carbon binds aggregates and reduces it further. A simplified
    stand-in for a RUSLE K factor, and labelled as such - SoilGrids is
    globally modelled, so this is a ranking between catchments and never a
    measured soil property.
    """
    # accepts Series or ndarray - callers pass both
    clay = np.asarray(pd.to_numeric(pd.Series(clay_pct), errors="coerce"), dtype=float)
    sand = np.asarray(pd.to_numeric(pd.Series(sand_pct), errors="coerce"), dtype=float)
    silt = np.asarray(pd.to_numeric(pd.Series(silt_pct), errors="coerce"), dtype=float)
    soc = np.asarray(pd.to_numeric(pd.Series(soc_g_kg), errors="coerce"), dtype=float)

    detachable = silt + 0.30 * sand          # the erodible fraction, %
    cohesion = 1.0 - np.clip(clay / 100.0, 0, 0.6)
    organic = 1.0 - np.clip(soc / 60.0, 0, 0.5)
    e = (detachable / 30.0) * cohesion * organic   # /30 normalises to ~1
    return np.nan_to_num(e, nan=1.0)


class SedimentProxy:
    """Relative sediment index and class. Deterministic; nothing is fitted."""

    name = "sediment_proxy"

    def __init__(self, params: SedimentParams | None = None):
        self.params = params or SedimentParams()
        self.params.validate()
        self._k: float | None = None            # index → tonnes, set by anchoring

    # ── the formula ──────────────────────────────────────────────────────
    def index(self, X: pd.DataFrame, runoff_depth_mm) -> np.ndarray:
        """Relative sediment index. Proportional to runoff volume."""
        p = self.params
        n = len(X)

        def col(name, default):
            if name in X:
                v = pd.to_numeric(X[name], errors="coerce").to_numpy(float)
                return np.nan_to_num(v, nan=default)
            return np.full(n, default, dtype=float)

        bare = col("bare_fraction", p.bare_ref)
        slope = col("slope_mean_deg", p.theta_ref_deg)
        dens = col("drainage_density_km_km2", p.d_ref_km_km2)
        area_km2 = col("area_km2", 1.0)

        q_mm = np.asarray(runoff_depth_mm, dtype=float)
        # mm over km² → m³:  mm × 1e-3 m × km² × 1e6 m²/km² = ×1e3
        q_m3 = q_mm * area_km2 * 1_000.0

        b_term = bare / p.bare_ref
        s_term = (np.clip(slope, 0.1, None) / p.theta_ref_deg) ** p.slope_exponent
        d_term = dens / p.d_ref_km_km2
        e_term = erodibility(col("clay_pct", 21.0), col("sand_pct", 58.0),
                             col("silt_pct", 21.0), col("soc_g_kg", 3.0))

        return (b_term * s_term * e_term * d_term * q_m3
                * (1.0 - p.transmission_loss))

    # ── anchoring ────────────────────────────────────────────────────────
    def calibrate_to_anchor(self, index_at_anchor: float,
                            mass_t: float = ANCHOR_MASS_T) -> "SedimentProxy":
        """Set the index → tonnes scale from the one published measurement.

        This fixes the SCALE only. It cannot validate the SHAPE of the
        formula, because a single point constrains one degree of freedom and
        the formula has six terms. Any mass this produces for a different
        event is an extrapolation along an unverified curve.
        """
        if index_at_anchor <= 0:
            raise ValueError("anchor index must be positive")
        self._k = float(mass_t) / float(index_at_anchor)
        return self

    @property
    def is_anchored(self) -> bool:
        return self._k is not None

    def mass_estimate_t(self, X: pd.DataFrame, runoff_depth_mm) -> np.ndarray:
        """Tonnes. Requires anchoring, and is an extrapolation regardless."""
        if self._k is None:
            raise RuntimeError(
                "not anchored. Call calibrate_to_anchor() with the index for "
                f"{ANCHOR_EVENT}/{ANCHOR_CATCHMENT}, or use classify() - the "
                "concept doc asks for a relative class, not a mass."
            )
        return self.index(X, runoff_depth_mm) * self._k

    # ── the deliverable ──────────────────────────────────────────────────
    def classify(self, X: pd.DataFrame, runoff_depth_mm,
                 anchor_index: float | None = None) -> pd.DataFrame:
        """Low / Medium / High / Extreme, with the basis recorded per row.

        Banded against the anchor event where one is available, so the class
        means something absolute. Falls back to within-dataset quantiles and
        SAYS SO, because a relative-to-itself class is a different claim.
        """
        idx = self.index(X, runoff_depth_mm)
        ref = anchor_index if anchor_index is not None else (
            ANCHOR_MASS_T / self._k if self._k else None)

        if ref and ref > 0:
            edges = [b * ref for b in ANCHOR_BANDS]
            basis = f"banded against {ANCHOR_EVENT} (≈{ANCHOR_MASS_T:,.0f} t)"
        else:
            edges = list(np.quantile(idx, [0.5, 0.8, 0.95])) if len(idx) else [1, 2, 3]
            basis = "WITHIN-DATASET QUANTILES - no anchor, class is relative only"

        cls = np.array(CLASSES)[np.searchsorted(edges, idx, side="right")]
        return pd.DataFrame({
            "sediment_index": idx,
            "sediment_class": cls,
            "class_basis": basis,
            "transmission_loss": self.params.transmission_loss,
        }, index=X.index)

    # ── scenarios ────────────────────────────────────────────────────────
    def with_transmission_loss(self, tau: float) -> "SedimentProxy":
        """A scenario is a new instance, not a mutated one."""
        p = SedimentParams(**{**asdict(self.params), "transmission_loss": tau})
        clone = SedimentProxy(p)
        clone._k = self._k
        return clone

    def sensitivity_to_tau(self, X: pd.DataFrame, runoff_depth_mm,
                           taus=None) -> pd.DataFrame:
        """What the answer would be across the plausible range of τ.

        This is the table that turns the assumption into a stated uncertainty
        rather than a hidden one, and it is what Ali's slider moves along.
        """
        if taus is None:
            taus = [0.0, 0.20, 0.35, 0.525, 0.70, 0.85, 0.95]
        # τ enters the formula only as the linear factor (1 − τ), so the whole
        # curve follows from one evaluation. Computing it once also makes the
        # linearity visible rather than implied.
        base = float(np.mean(self.with_transmission_loss(0.0)
                             .index(X, runoff_depth_mm)))
        return pd.DataFrame([{
            "transmission_loss": t,
            "in_negev_range": TAU_NEGEV[0] <= t <= TAU_NEGEV[1],
            "is_default": abs(t - TAU_DEFAULT) < 1e-9,
            "mean_index": base * (1.0 - t),
            "vs_tau_zero": 1.0 - t,
        } for t in taus])
