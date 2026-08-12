-- Phase 9 -- response_recommendations, recommendation_turns, recommendation_verdicts,
-- recommendation_gaps. Owner: Nizar (schema), Mahdi (orchestration). See
-- tasks/phase9/00-phase9-plan.md for the full design; this file transcribes §7.
--
-- No RLS here, matching simulation_runs/reef_exposures/alerts (Phase 1-4's cross-cutting
-- tables) -- this is not a per-user-writable table like access_requests, it is written
-- by the worker (service_role) and read publicly like every other result table.

CREATE TABLE response_recommendations (
    id                      text PRIMARY KEY,        -- rec_{ULID}
    run_id                  text REFERENCES simulation_runs(id),
    event_id                text REFERENCES events(id),
    triggered_by            text NOT NULL
                                CHECK (triggered_by IN ('auto', 'human_override')),
    triggered_by_user       text,                     -- set only when triggered_by = human_override
    min_risk_level_override text,
    severity_brief          jsonb NOT NULL,
    final_recommendation    text,
    status                  text NOT NULL DEFAULT 'running'
                                CHECK (status IN ('running', 'proposed', 'judge_approved',
                                                   'judge_rejected', 'finalized')),
    rounds_used             int,
    converged               boolean,
    model                   text NOT NULL,            -- e.g. gemma-4-31b-local
    created_at              timestamptz NOT NULL DEFAULT now(),
    completed_at            timestamptz
);

-- Full audit trail of the debate -- every turn, every agent, every round.
CREATE TABLE recommendation_turns (
    id                 bigserial PRIMARY KEY,
    recommendation_id  text NOT NULL REFERENCES response_recommendations(id) ON DELETE CASCADE,
    round              int NOT NULL,
    agent_role         text NOT NULL
                            CHECK (agent_role IN ('severity_briefer', 'aseza', 'marine_science',
                                                   'port_ops', 'civil_defense', 'tourism')),
    content            text NOT NULL,
    evidence_cited     jsonb,             -- which corpus chunks it grounded on
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX recommendation_turns_rec_idx ON recommendation_turns (recommendation_id, round);

CREATE TABLE recommendation_verdicts (
    id                 bigserial PRIMARY KEY,
    recommendation_id  text NOT NULL REFERENCES response_recommendations(id) ON DELETE CASCADE,
    verdict            text NOT NULL CHECK (verdict IN ('approved', 'rejected')),
    evidence_cited     jsonb,
    reasoning          text NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE recommendation_gaps (
    id                 bigserial PRIMARY KEY,
    recommendation_id  text NOT NULL REFERENCES response_recommendations(id) ON DELETE CASCADE,
    gap_description    text NOT NULL,
    severity           text,
    created_at         timestamptz NOT NULL DEFAULT now()
);

-- alerts.recommended_action already exists as free text (Phase 1). This links it to the
-- full deliberation record without removing the text field -- an alert issued before
-- this phase, or one whose swarm run failed, still has a plain-text fallback.
ALTER TABLE alerts
    ADD COLUMN recommendation_id text REFERENCES response_recommendations(id);
