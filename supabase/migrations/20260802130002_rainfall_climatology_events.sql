-- Transcribed from data-model.md §4.3 (Rainfall, climatology, events). Do not redesign.

CREATE TABLE catchment_rainfall (
    catchment_id text NOT NULL REFERENCES catchments(id),
    ts           timestamptz NOT NULL,              -- UTC, start of the accumulation step
    source_id    text NOT NULL REFERENCES data_sources(id),
    rain_mm      numeric NOT NULL,                  -- accumulation over the native step
    PRIMARY KEY (catchment_id, ts, source_id)
);

CREATE TABLE catchment_rainfall_climatology (
    catchment_id  text NOT NULL REFERENCES catchments(id),
    window_hours  int  NOT NULL,                    -- 1, 3, 6, 24
    source_id     text NOT NULL REFERENCES data_sources(id),
    p50 numeric, p90 numeric, p95 numeric, p99 numeric, p99_9 numeric,
    max_observed_mm numeric,
    n_windows     bigint,
    period_start  date,
    period_end    date,
    PRIMARY KEY (catchment_id, window_hours, source_id)
);

CREATE TABLE events (
    id                text PRIMARY KEY,             -- AQ-2016-10-25
    start_time        timestamptz NOT NULL,
    end_time          timestamptz,
    peak_time         timestamptz,
    event_type        text NOT NULL DEFAULT 'historical',  -- historical|forecast|scenario
    detection_method  text,                         -- imerg_percentile|literature|manual
    label_tier        text CHECK (label_tier IN ('gold','silver','bronze')),
    quality_score     numeric CHECK (quality_score BETWEEN 0 AND 1),
    chirps_agrees     boolean,                      -- independent cross-check flag
    source_references jsonb,                        -- DOIs / URLs confirming the date
    is_demo_event     boolean NOT NULL DEFAULT false,
    notes             text,
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- The ML training table. One row per (event, catchment).
-- Static features are JOINED from catchments / catchment_surface_features at fit time,
-- deliberately not copied here — copying them is how a training set drifts out of sync
-- with the geography it describes.
CREATE TABLE event_catchment_features (
    event_id                text NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    catchment_id            text NOT NULL REFERENCES catchments(id),
    rain_30min_max_mm       numeric,
    rain_1h_mm              numeric,
    rain_3h_mm              numeric,
    rain_6h_mm              numeric,
    rain_24h_mm             numeric,
    rain_percentile_3h      numeric,
    rain_percentile_24h     numeric,
    antecedent_rain_7d_mm   numeric,
    soil_moisture_t24       numeric,
    soil_moisture_t72       numeric,
    era5_surface_runoff_m   numeric,
    era5_subsurface_runoff_m numeric,
    wind_speed_ms           numeric,
    wind_direction_deg      numeric,
    current_u_ms            numeric,
    current_v_ms            numeric,
    extra_features          jsonb,                  -- anything added after freeze
    -- labels
    runoff_observed         boolean,
    severity_observed       text CHECK (severity_observed IN ('none','low','medium','high','extreme')),
    label_source            text,                   -- 'satellite_plume'|'literature'|'inferred'
    PRIMARY KEY (event_id, catchment_id)
);
