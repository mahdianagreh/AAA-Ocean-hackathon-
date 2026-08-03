-- Transcribed from data-model.md §4.2 (Static geography). Do not redesign.

CREATE TABLE catchments (
    id                      text PRIMARY KEY,       -- AQ-C01 … AQ-C05
    name                    text,
    geom                    geometry(MultiPolygon, 4326) NOT NULL,
    area_km2                numeric NOT NULL,
    perimeter_km            numeric,
    mean_elev_m             numeric,
    relief_m                numeric,
    mean_slope_deg          numeric,
    max_slope_deg           numeric,
    drainage_density_km_km2 numeric,
    stream_length_km        numeric,
    longest_flowpath_km     numeric,
    max_flow_accum_cells    bigint,
    time_of_concentration_min numeric,
    dem_source_id           text REFERENCES data_sources(id),
    delineation_method      text,                   -- 'd8_whitebox' | 'hydrobasins_l9'
    notes                   text,                   -- record any manual DEM correction here
    is_provisional          boolean NOT NULL DEFAULT true,
    updated_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX catchments_geom_idx ON catchments USING gist (geom);

CREATE TABLE outlets (
    id              text PRIMARY KEY,               -- AQ-O01, matches its catchment number
    catchment_id    text NOT NULL UNIQUE REFERENCES catchments(id),
    geom            geometry(Point, 4326) NOT NULL,
    method          text,                           -- 'dem_pourpoint' | 'manual_imagery'
    snap_distance_m numeric,                        -- how far it moved from the raw pour point
    is_provisional  boolean NOT NULL DEFAULT true
);
CREATE INDEX outlets_geom_idx ON outlets USING gist (geom);

CREATE TABLE catchment_surface_features (
    catchment_id            text PRIMARY KEY REFERENCES catchments(id),
    landcover_source_id     text REFERENCES data_sources(id),
    landcover_year          int,
    bare_ground_pct         numeric,
    built_up_pct            numeric,
    vegetation_pct          numeric,
    water_pct               numeric,
    class_fractions         jsonb,                  -- full WorldCover histogram
    clay_pct_0_5            numeric,
    sand_pct_0_5            numeric,
    silt_pct_0_5            numeric,
    soc_g_per_kg_0_5        numeric,
    bulk_density_0_5        numeric,
    coarse_fragments_pct_0_5 numeric,
    clay_pct_5_15           numeric,
    sand_pct_5_15           numeric,
    silt_pct_5_15           numeric,
    erodibility_proxy       numeric,                -- derived, relative, unitless
    road_length_km          numeric,
    building_footprint_km2  numeric,
    impervious_pct_est      numeric,
    is_provisional          boolean NOT NULL DEFAULT true,
    updated_at              timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE reef_zones (
    id                 text PRIMARY KEY,            -- R-01 … R-08
    name               text,
    geom               geometry(MultiPolygon, 4326) NOT NULL,
    area_km2           numeric NOT NULL,
    habitat_class      text,                        -- ACA geomorphic class
    benthic_class      text,                        -- ACA benthic class
    mean_depth_m       numeric,
    sensitivity_weight numeric NOT NULL DEFAULT 1.0,
    sensitivity_basis  text NOT NULL
        DEFAULT 'PLACEHOLDER: uniform 1.0, team assumption, not scientifically derived',
    nearest_outlet_id  text REFERENCES outlets(id),
    distance_to_outlet_m numeric,
    source_id          text REFERENCES data_sources(id),
    is_provisional     boolean NOT NULL DEFAULT true
);
CREATE INDEX reef_zones_geom_idx ON reef_zones USING gist (geom);
