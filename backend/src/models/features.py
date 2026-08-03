"""The canonical feature set for Component A.

One definition, imported everywhere. The scripts each carried their own copy
while the set was still moving; it has settled, and three copies of a feature
list is three chances for the training set and the serving path to disagree
about what the model eats.

Configuration `CD-`, selected by the ablation sweep in
`scripts/17_ablation_sweep.py`: climatology-normalised rainfall + dry spell,
WITHOUT label weights. It won on every metric at once - mean AP, AQ-C01 AP,
pooled AP, F1 and Brier - which is worth noting because when the best variant
differs by metric you are usually looking at noise.

    combo   mean AP   AQ-C01   F1
    CD-     0.7414    0.5931   0.6417   <- this one
    -D-     0.7397    0.5662   0.6265
    C--     0.7359    0.5870   0.6238
    ---     0.7358    0.5531   0.6199
    (the four W variants occupy the bottom four rows)

Rule baseline for comparison: mean AP 0.2004.
"""

from __future__ import annotations

# ── excluded, and why ────────────────────────────────────────────────────
#
# soil_moisture (same day)
#     A daily MEAN, so it rises as the day's rain infiltrates - contemporaneous
#     with the target, not antecedent. r = +0.384 against the lags' +0.059 and
#     +0.015. With it in, it was the top driver at 2.21 mean |SHAP| against
#     rainfall's 0.44 and LOCO AP read 0.836. It does not look like a bug; it
#     looks like an excellent result.
#
# rank
#     This catalogue's rainfall ranking. It predicts runoff well and does not
#     exist for a live forecast - you cannot know where tomorrow's storm places
#     among 27 years of history. Scores well offline, cannot be deployed.
#
# catchments_exceeding_p99
#     Counted across the catchment set, so each row carries information about
#     the OTHER four catchments. Under leave-one-catchment-out the held-out
#     row's value is partly derived from the training catchments.
#
# sro / ssro
#     They derive the label. Feature and target at once is a tautology.
#
# label_weight
#     Available but not used. Downweighting four of five catchments discards
#     signal faster than it removes label noise at 928 positives - measured,
#     all four W variants ranked last.

RAINFALL = [
    "precipitation_mm_day",
    "precip_prior_1d_mm", "precip_prior_3d_mm", "precip_prior_7d_mm",
]

# Absolute mm do not transfer between catchments - 6 mm on 4,453 km2 is not
# 6 mm on 36 km2 - and transfer to an unseen catchment is exactly what LOCO
# tests. A position in the catchment's own wet-day distribution does transfer.
CLIMATOLOGY = [
    "rain_over_p50", "rain_over_p90", "rain_over_p99", "rain_self_percentile",
]

ANTECEDENT = [
    "soil_moisture_lag1d", "soil_moisture_lag3d",
    # Arid soil crusts when it bakes, and a crust sheds water rather than
    # absorbing it - which is why dry antecedent conditions RAISE runoff. The
    # moisture lags capture wetness but not the duration of dryness that forms
    # the crust. Counted strictly before the day, so no same-day leak.
    "dry_days_before",
]

# From the same ERA5 month files as the label; they were simply not being read.
# Legitimate despite being same-day, unlike soil moisture: wind and temperature
# are DRIVERS of the synoptic system delivering the storm, not RESPONSES to the
# rain, and GFS/GEFS forecast both - so a live prediction for tomorrow has them.
# Caveat for the model card: temperature on a rain day is partly lowered BY the
# rain, so its +0.048 contribution may be slightly inflated by the same
# mechanism in miniature.
SYNOPTIC = ["wind_speed_ms", "wind_direction_deg", "temp_c"]

# Cyclical so December and January sit adjacent rather than 11 apart, which an
# integer month would imply. Aqaba's rain is almost entirely Oct-Mar, and
# autumn convective storms behave differently from winter frontal ones.
SEASON = ["season_sin", "season_cos"]

# Four only, named for a physical reason rather than taken because they exist.
# 115 static columns are available and they carry five distinct values in the
# whole table; handing a tree all of them lets it identify the catchment
# instead of learning the process.
STATIC = ["area_km2", "slope_mean_deg", "drainage_density_km_km2",
          "elongation_ratio"]

FEATURES: list[str] = (RAINFALL + CLIMATOLOGY + ANTECEDENT + SYNOPTIC
                       + SEASON + STATIC)

EVENT_VARYING: list[str] = [f for f in FEATURES if f not in STATIC]

# Chosen by nested inner-LOCO in 16_tune_and_compare.py: 9 of 10 folds picked
# depth 6 / lr 0.03, deeper and slower than the earlier defaults of 4 / 0.05,
# which means the model had been slightly underfit.
PARAMS = dict(max_depth=6, learning_rate=0.03, min_child_weight=2.0)

TARGET = "target"
MAGNITUDE = "sro_mm_day"
GROUP = "catchment_id"


def check(df) -> list[str]:
    """Assert the frame carries the feature set, and no excluded column."""
    missing = [c for c in FEATURES if c not in df.columns]
    if missing:
        raise KeyError(f"training frame is missing {missing}")
    banned = [c for c in FEATURES
              if any(t in c.lower() for t in ("sro", "ssro", "rank", "label"))
              or c == "soil_moisture"]
    if banned:
        raise ValueError(f"excluded column in the feature set: {banned}")
    return list(FEATURES)
