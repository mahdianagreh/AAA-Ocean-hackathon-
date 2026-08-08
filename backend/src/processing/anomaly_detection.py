"""
B6 — Live Anomaly Detection on Forecast Streams.

Deliberately NOT a z-score: `catchment_rainfall_climatology` only delivers
percentiles (p50/p90/p95/p99/p99_9), not a mean/std or the underlying daily
series (see `db/loaders/karam_rainfall.py`'s module docstring). Fabricating a
mean/std from percentiles would be an interpolation the project's data rules
forbid ("nothing is interpolated"). This module instead scores a live rain
total by where it falls relative to the real climatology percentiles —
explainable in one sentence, no invented statistic.

This is a statistical outlier signal against ~27 years of daily-IMERG-derived
climatology, not a validated early-warning system — it has never been checked
against a real flood event's lead time. Every score carries that caveat in its
own payload (rule 9: caveats travel as data), not just in this docstring.
"""

from __future__ import annotations

CAVEAT = (
    "Statistical outlier signal vs. climatology, not a validated early-warning "
    "system -- never checked against a real flood event's lead time."
)

_BANDS = ("p50", "p90", "p95", "p99", "p99_9")


def compute_anomaly(rain_mm: float, climatology_row: dict) -> dict:
    """Scores one live rainfall total against one catchment's real percentile
    climatology.

    `climatology_row` must carry p50/p90/p95/p99/p99_9 and n_windows for the
    matching (catchment_id, window_hours, source_id) -- exactly the row
    `catchment_rainfall_climatology` already stores, no derived statistic added.

    Returns a `formula_terms`-equivalent dict: every input that produced
    `anomaly_score`/`is_anomalous`, reconstructable later, plus the caveat
    baked into the payload itself.
    """
    p50 = climatology_row["p50"]
    p99 = climatology_row["p99"]
    p99_9 = climatology_row["p99_9"]

    band = "below_p50"
    for name in _BANDS:
        if rain_mm > climatology_row[name]:
            band = f"above_{name}"

    denom = max(p99_9 - p50, 1e-6)
    anomaly_score = max(0.0, (rain_mm - p50) / denom)
    is_anomalous = rain_mm > p99

    return {
        "rain_mm": rain_mm,
        "climatology_p50": p50,
        "climatology_p90": climatology_row["p90"],
        "climatology_p95": climatology_row["p95"],
        "climatology_p99": p99,
        "climatology_p99_9": p99_9,
        "n_windows": climatology_row["n_windows"],
        "percentile_band": band,
        "anomaly_score": anomaly_score,
        "is_anomalous": is_anomalous,
        "caveat": CAVEAT,
    }
