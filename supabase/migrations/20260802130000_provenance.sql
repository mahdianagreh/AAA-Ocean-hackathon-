-- Transcribed from data-model.md §4.1 (Provenance). Do not redesign — raise
-- issues with Karam (integration lead) and change the source doc first.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE data_sources (
    id                   text PRIMARY KEY,          -- 'imerg_v07_final', 'cop_dem_glo30'
    name                 text NOT NULL,
    provider             text NOT NULL,             -- NASA, ESA, ECMWF, NOAA, ISRIC, ACA
    product              text NOT NULL,
    version              text,
    temporal_resolution  text,                      -- '30min', 'hourly', 'static'
    spatial_resolution_m numeric,
    native_crs           text,
    access_url           text,
    access_method        text,                      -- earthaccess|cdsapi|gee|aws-s3|http|copernicusmarine
    requires_account     boolean NOT NULL DEFAULT false,
    license              text NOT NULL,
    citation             text,
    first_accessed_at    timestamptz,
    last_checked_at      timestamptz,
    known_limitation     text,                      -- the §11 caveat, verbatim
    notes                text
);

CREATE TABLE raster_assets (
    id              bigserial PRIMARY KEY,
    kind            text NOT NULL,                  -- dem|flowacc|slope|landcover|depth|water_mask
                                                    -- |baseline_composite|spectral_index|plume_probability
    source_id       text REFERENCES data_sources(id),
    path            text NOT NULL UNIQUE,
    format          text NOT NULL DEFAULT 'COG',
    crs             text NOT NULL,
    pixel_size_m    numeric,
    bbox            geometry(Polygon, 4326),
    valid_time      timestamptz,                    -- NULL for static layers
    bytes           bigint,
    checksum_sha256 text,
    is_provisional  boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX raster_assets_bbox_idx ON raster_assets USING gist (bbox);
