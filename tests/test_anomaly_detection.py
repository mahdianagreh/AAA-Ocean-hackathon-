import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from processing.anomaly_detection import compute_anomaly  # noqa: E402

CLIMATOLOGY_ROW = {
    "p50": 1.0,
    "p90": 5.0,
    "p95": 8.0,
    "p99": 15.0,
    "p99_9": 30.0,
    "n_windows": 10135,
}


def test_below_median_is_not_anomalous():
    result = compute_anomaly(0.2, CLIMATOLOGY_ROW)
    assert result["is_anomalous"] is False
    assert result["percentile_band"] == "below_p50"
    assert result["anomaly_score"] == 0.0


def test_above_p99_is_anomalous():
    result = compute_anomaly(20.0, CLIMATOLOGY_ROW)
    assert result["is_anomalous"] is True
    assert result["percentile_band"] == "above_p99"
    assert result["anomaly_score"] > 0


def test_score_is_continuous_not_a_hard_cutoff():
    just_under = compute_anomaly(14.9, CLIMATOLOGY_ROW)
    just_over = compute_anomaly(15.1, CLIMATOLOGY_ROW)
    assert just_under["is_anomalous"] is False
    assert just_over["is_anomalous"] is True
    assert just_over["anomaly_score"] > just_under["anomaly_score"]
    assert abs(just_over["anomaly_score"] - just_under["anomaly_score"]) < 0.02


def test_every_result_carries_the_caveat():
    result = compute_anomaly(1.0, CLIMATOLOGY_ROW)
    assert "never checked against a real flood event" in result["caveat"]


def test_reconstructable_from_stored_terms():
    result = compute_anomaly(9.0, CLIMATOLOGY_ROW)
    for key in ("rain_mm", "climatology_p50", "climatology_p99", "climatology_p99_9", "n_windows"):
        assert key in result
