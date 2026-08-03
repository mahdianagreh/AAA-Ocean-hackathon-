"""The feature contract, and the assertions that keep it honest.

One place, checked at the data boundary, so both the parquet source and the
Supabase source get the same guarantees.
"""

from __future__ import annotations

import re

import pandas as pd

CATCHMENT_ID = re.compile(r"^AQ-C\d{2}$")

KEYS = ["event_id", "catchment_id", "event_time_utc"]

# ERA5-Land runoff DERIVES the label. If either reaches the feature list the
# model predicts runoff from runoff: a tautology that scores near 1.0 and
# knows nothing. Substring match, because sro_24h_mm and ssro_max are just as
# fatal as the bare column.
FORBIDDEN_FEATURE_SUBSTRINGS = ("sro", "ssro", "runoff_label", "label_tier")

# Columns that are constant within a catchment. Harmless under
# leave-one-catchment-out; a perfect catchment fingerprint under a random
# split, which is why the split is not a free choice.
STATIC_FEATURES = [
    "area_km2", "relief_m", "slope_mean_deg", "slope_max_deg",
    "drainage_density_km_km2", "dist_to_coast_max_km", "dist_to_coast_mean_km",
    "elongation_ratio", "accum_mean_cells", "accum_p95_cells",
    "bare_fraction", "built_up_fraction", "clay_pct", "sand_pct", "silt_pct",
    "soc_g_kg", "road_density_km_km2",
]

DYNAMIC_FEATURES = [
    "rain_1h_mm", "rain_3h_mm", "rain_6h_mm", "rain_24h_mm",
    "rain_3h_percentile", "anomaly_score",
    "soil_moisture_t24h", "soil_moisture_t72h",
    "precip_prior_72h_mm", "precip_prior_7d_mm",
    "wind_speed_ms", "temp_2m_c",
]

LABEL = "runoff_label"
TIER = "label_tier"

# Minimum a matrix must carry to be trainable at all. Everything else is
# used when present and reported as absent when not - Karam delivers this
# incrementally and a partial matrix on Day 5 beats a full one on Day 8.
REQUIRED = KEYS + ["rain_3h_mm", LABEL]


class SchemaError(ValueError):
    """Raised at the data boundary, never deeper."""


def feature_columns(df: pd.DataFrame, include_static: bool = True) -> list[str]:
    """Feature columns actually present, in a stable order.

    Stable ordering matters: SHAP output, the model artifact and the stored
    model_versions row all have to line up across runs.
    """
    wanted = (STATIC_FEATURES if include_static else []) + DYNAMIC_FEATURES
    return [c for c in wanted if c in df.columns]


def assert_no_label_leakage(features: list[str]) -> None:
    """The single most important check in the project."""
    bad = [
        c for c in features
        if any(tok in c.lower() for tok in FORBIDDEN_FEATURE_SUBSTRINGS)
    ]
    if bad:
        raise SchemaError(
            f"label leakage: {bad} would let the model predict runoff from "
            "runoff. ERA5-Land runoff derives the target and is never a "
            "feature. See tasks/phase2/00-phase2-plan.md."
        )


def validate(df: pd.DataFrame, include_static: bool = True) -> list[str]:
    """Check a matrix at the boundary. Returns the feature list to train on."""
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SchemaError(f"matrix is missing required columns: {missing}")

    bad_ids = sorted({
        c for c in df.catchment_id.dropna().unique()
        if not CATCHMENT_ID.match(str(c))
    })
    if bad_ids:
        raise SchemaError(
            f"catchment_id must match AQ-C{{NN}} (contract §2); got {bad_ids}"
        )

    labels = set(pd.unique(df[LABEL].dropna()))
    if not labels <= {0, 1}:
        raise SchemaError(f"{LABEL} must be binary 0/1; got {sorted(labels)}")

    if df[LABEL].isna().any():
        raise SchemaError(
            f"{df[LABEL].isna().sum()} rows have a null {LABEL}. A row with no "
            "label is not a training row - drop it upstream, deliberately."
        )

    feats = feature_columns(df, include_static)
    if not feats:
        raise SchemaError("no recognised feature columns present")
    assert_no_label_leakage(feats)
    return feats


def describe(df: pd.DataFrame, feats: list[str]) -> str:
    """Short provenance summary for the model card."""
    n_pos = int(df[LABEL].sum())
    tiers = (
        df[TIER].value_counts().to_dict() if TIER in df.columns else {"unknown": len(df)}
    )
    static_present = [c for c in feats if c in STATIC_FEATURES]
    return (
        f"{len(df)} rows, {df.catchment_id.nunique()} catchments, "
        f"{df.event_id.nunique()} events\n"
        f"{n_pos} positive ({n_pos / len(df):.1%}), tiers {tiers}\n"
        f"{len(feats)} features ({len(static_present)} static, "
        f"{len(feats) - len(static_present)} dynamic)"
    )
