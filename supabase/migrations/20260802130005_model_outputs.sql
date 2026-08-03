-- Transcribed from data-model.md §4.6 (Model outputs). Do not redesign.

CREATE TABLE model_versions (
    id                 text PRIMARY KEY,            -- 'runoff_xgb_v3'
    component          text NOT NULL,               -- C|D|E
    algorithm          text,
    trained_at         timestamptz,
    training_event_ids text[],
    cv_scheme          text,                        -- 'leave_one_catchment_out'
    hyperparams        jsonb,
    metrics            jsonb,
    artifact_path      text,
    git_commit         text
);

CREATE TABLE runoff_predictions (
    id                     bigserial PRIMARY KEY,
    event_id               text REFERENCES events(id),
    catchment_id           text NOT NULL REFERENCES catchments(id),
    model_version_id       text REFERENCES model_versions(id),
    mode                   text NOT NULL,           -- historical|forecast|scenario
    forecast_run_id        text REFERENCES forecast_runs(id),
    runoff_probability     numeric CHECK (runoff_probability BETWEEN 0 AND 1),
    severity               text CHECK (severity IN ('none','low','medium','high','extreme')),
    confidence             numeric,
    rule_baseline_index    numeric,                 -- transparent baseline, kept alongside the ML output
    sediment_class         text CHECK (sediment_class IN ('low','medium','high','extreme')),
    sediment_index         numeric,
    feature_attributions   jsonb,                   -- SHAP values → Component H "top drivers"
    created_at             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (event_id, catchment_id, model_version_id, mode)
);
