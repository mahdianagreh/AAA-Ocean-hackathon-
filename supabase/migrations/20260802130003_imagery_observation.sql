-- Transcribed from data-model.md §4.4 (Imagery and observation). Do not redesign.

CREATE TABLE satellite_scenes (
    id                  text PRIMARY KEY,           -- provider granule/scene ID
    source_id           text NOT NULL REFERENCES data_sources(id),
    platform            text,                       -- S2A|S2B|L8|L9
    acquisition_time    timestamptz NOT NULL,
    event_id            text REFERENCES events(id),
    days_from_event     numeric,                    -- signed: negative = pre-event
    role                text,                       -- candidate|pre_event|post_event
    cloud_pct_scene     numeric,
    cloud_pct_aoi_water numeric,                    -- the number that actually matters
    sun_glint_score     int CHECK (sun_glint_score BETWEEN 0 AND 3),
    plume_visible       text CHECK (plume_visible IN ('yes','partial','no','unknown')),
    usability_score     numeric,
    decision            text CHECK (decision IN ('selected','baseline','rejected','pending')),
    decision_reason     text,
    footprint           geometry(Polygon, 4326),
    local_path          text,
    reviewed_by         text,
    reviewed_at         timestamptz
);

CREATE TABLE observed_plumes (
    id                    bigserial PRIMARY KEY,
    event_id              text NOT NULL REFERENCES events(id),
    scene_id              text REFERENCES satellite_scenes(id),
    acquisition_time      timestamptz NOT NULL,
    index_used            text,                     -- ndssi|nsmi|red_green_ratio|reflectance_anomaly
    threshold_value       numeric,
    baseline_raster_id    bigint REFERENCES raster_assets(id),
    probability_raster_id bigint REFERENCES raster_assets(id),
    geom                  geometry(MultiPolygon, 4326),
    area_km2              numeric,
    centroid              geometry(Point, 4326),
    reef_overlap_km2      numeric,
    label_tier            text CHECK (label_tier IN ('gold','silver','bronze')),
    quality_score         numeric,
    qc_by                 text,
    qc_notes              text,
    is_provisional        boolean NOT NULL DEFAULT false
);
CREATE INDEX observed_plumes_geom_idx ON observed_plumes USING gist (geom);
