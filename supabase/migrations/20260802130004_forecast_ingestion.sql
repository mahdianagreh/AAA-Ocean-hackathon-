-- Transcribed from data-model.md §4.5 (Forecast ingestion). Do not redesign.
-- Owner: Nizar. Feeds forecast_catchment_rainfall (member=0 deterministic GFS,
-- member=1..N GEFS ensemble) and forecast_exceedance (the dashboard's confidence number).

CREATE TABLE forecast_runs (
    id             text PRIMARY KEY,                -- 'gfs_2026-07-31T00Z'
    source_id      text NOT NULL REFERENCES data_sources(id),
    model          text NOT NULL,                   -- gfs|gefs|ifs|aifs
    reference_time timestamptz NOT NULL,
    n_members      int NOT NULL DEFAULT 1,
    max_lead_hours int,
    raw_path       text,
    ingested_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (model, reference_time)
);

CREATE TABLE forecast_catchment_rainfall (
    forecast_run_id    text NOT NULL REFERENCES forecast_runs(id) ON DELETE CASCADE,
    catchment_id       text NOT NULL REFERENCES catchments(id),
    lead_hours         int  NOT NULL,
    member             int  NOT NULL DEFAULT 0,     -- 0 = deterministic / ensemble mean
    rain_mm            numeric,
    wind_speed_ms      numeric,
    wind_direction_deg numeric,
    PRIMARY KEY (forecast_run_id, catchment_id, lead_hours, member)
);

-- The dashboard's confidence number, materialised.
CREATE TABLE forecast_exceedance (
    forecast_run_id  text NOT NULL REFERENCES forecast_runs(id) ON DELETE CASCADE,
    catchment_id     text NOT NULL REFERENCES catchments(id),
    window_hours     int  NOT NULL,
    threshold_mm     numeric NOT NULL,
    threshold_source text,                          -- e.g. 'climatology p99'
    members_total    int,
    members_exceeding int,
    exceedance_prob  numeric CHECK (exceedance_prob BETWEEN 0 AND 1),
    PRIMARY KEY (forecast_run_id, catchment_id, window_hours)
);
