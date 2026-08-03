-- Transcribed from data-model.md §4.7 (Simulation, exposure, validation). Do not redesign.
-- Owner: Nizar (simulation_runs, plume_forecasts, reef_exposures, calibration_trials feed
-- from this stream's particle engine). backtests/backtest_metrics/alerts are cross-cutting.

CREATE TABLE simulation_runs (
    id                     text PRIMARY KEY,        -- sim_01JXYZ (ULID)
    event_id               text REFERENCES events(id),
    forecast_run_id        text REFERENCES forecast_runs(id),
    catchment_id           text REFERENCES catchments(id),
    outlet_id              text REFERENCES outlets(id),
    mode                   text NOT NULL,           -- historical|forecast|scenario
    engine                 text NOT NULL,           -- opendrift|custom_2d
    release_time           timestamptz NOT NULL,
    duration_hours         int,
    time_step_minutes      int,
    particle_count         int,
    sediment_class         text,
    diffusion_m2_s         numeric,
    settling_velocity_mm_s numeric,
    windage_fraction       numeric,
    current_source_id      text REFERENCES data_sources(id),
    wind_source_id         text REFERENCES data_sources(id),
    parameters             jsonb NOT NULL,          -- the request verbatim → reproducibility
    is_calibration_trial   boolean NOT NULL DEFAULT false,
    status                 text NOT NULL,           -- queued|running|completed|failed
    error_message          text,
    started_at             timestamptz,
    completed_at           timestamptz,
    runtime_seconds        numeric,
    git_commit             text,
    output_dir             text                     -- data/outputs/<run_id>/
);

-- Contoured probability polygons. NOT particles.
CREATE TABLE plume_forecasts (
    id                   bigserial PRIMARY KEY,
    run_id               text NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    forecast_hour        numeric NOT NULL,
    forecast_time        timestamptz,
    probability_level    numeric NOT NULL,          -- 0.10 | 0.25 | 0.50 | 0.75
    geom                 geometry(MultiPolygon, 4326),
    area_km2             numeric,
    centroid             geometry(Point, 4326),
    raster_id            bigint REFERENCES raster_assets(id),
    active_particle_count int,
    UNIQUE (run_id, forecast_hour, probability_level)
);
CREATE INDEX plume_forecasts_geom_idx ON plume_forecasts USING gist (geom);

CREATE TABLE reef_exposures (
    id                       bigserial PRIMARY KEY,
    run_id                   text NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    reef_zone_id             text NOT NULL REFERENCES reef_zones(id),
    max_exposure_probability numeric,
    overlap_km2_at_max       numeric,
    exposure_duration_hours  numeric,
    arrival_start            timestamptz,
    arrival_end              timestamptz,
    arrival_window_hours_low  numeric,
    arrival_window_hours_high numeric,
    risk_score               numeric CHECK (risk_score BETWEEN 0 AND 100),
    risk_level               text CHECK (risk_level IN ('low','moderate','high','severe')),
    confidence               numeric,
    formula_terms            jsonb NOT NULL,        -- each multiplicand of the §10.7 formula
    UNIQUE (run_id, reef_zone_id)
);

CREATE TABLE calibration_trials (
    id                     bigserial PRIMARY KEY,
    event_id               text NOT NULL REFERENCES events(id),
    observed_plume_id      bigint NOT NULL REFERENCES observed_plumes(id),
    run_id                 text REFERENCES simulation_runs(id),
    diffusion_m2_s         numeric,
    settling_velocity_mm_s numeric,
    windage_fraction       numeric,
    iou                    numeric,
    dice                   numeric,
    centroid_distance_m    numeric,
    area_ratio             numeric,
    is_selected            boolean NOT NULL DEFAULT false
);

CREATE TABLE backtests (
    id                text PRIMARY KEY,
    event_id          text NOT NULL REFERENCES events(id),
    run_id            text REFERENCES simulation_runs(id),
    observed_plume_id bigint REFERENCES observed_plumes(id),
    baseline          text,                         -- NULL = the model; else circular_buffer|wind_only|…
    blind             boolean NOT NULL DEFAULT true,
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- Long format: new metrics need no migration.
CREATE TABLE backtest_metrics (
    id                  bigserial PRIMARY KEY,
    backtest_id         text NOT NULL REFERENCES backtests(id) ON DELETE CASCADE,
    metric_name         text NOT NULL,              -- iou|dice|centroid_distance_m|direction_error_deg|…
    metric_value        numeric,
    unit                text,
    at_forecast_hour    numeric,
    at_probability_level numeric,
    UNIQUE (backtest_id, metric_name, at_forecast_hour, at_probability_level)
);

CREATE TABLE alerts (
    id                  bigserial PRIMARY KEY,
    issued_at           timestamptz NOT NULL DEFAULT now(),
    forecast_run_id     text REFERENCES forecast_runs(id),
    run_id              text REFERENCES simulation_runs(id),
    catchment_id        text REFERENCES catchments(id),
    reef_zone_ids       text[],
    severity            text,
    lead_time_hours     numeric,
    headline            text NOT NULL,
    explanation         text NOT NULL,              -- Component H narrative
    recommended_action  text,
    uncertainty_note    text NOT NULL,              -- forced: no alert ships without its caveat
    status              text NOT NULL DEFAULT 'draft'
);
