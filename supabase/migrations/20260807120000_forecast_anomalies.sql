-- Phase 5, B6 -- Live Anomaly Detection on Forecast Streams.
-- Owner: Nizar. New artifact -- confirmed zero collisions with tasks/00-contracts.md.
--
-- Mirrors forecast_exceedance's shape exactly (same FK pair, same grain):
-- one row per (forecast_run_id, catchment_id, window_hours). Scored against
-- catchment_rainfall_climatology's real percentiles, not a fabricated
-- mean/std -- see backend/src/processing/anomaly_detection.py's docstring for
-- why this is a percentile-relative score, not a textbook z-score.

CREATE TABLE forecast_anomalies (
    forecast_run_id    text    NOT NULL REFERENCES forecast_runs(id) ON DELETE CASCADE,
    catchment_id       text    NOT NULL REFERENCES catchments(id),
    window_hours        int     NOT NULL,
    rain_mm             numeric NOT NULL,
    climatology_p50     numeric NOT NULL,
    climatology_p99     numeric NOT NULL,
    climatology_p99_9   numeric NOT NULL,
    percentile_band     text    NOT NULL,
    anomaly_score       numeric NOT NULL,
    is_anomalous        boolean NOT NULL,
    computed_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (forecast_run_id, catchment_id, window_hours)
);
