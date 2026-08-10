-- Phase 8, Track B -- access_requests. Owner: Nizar.
-- Auth model decided in tasks/00-contracts.md §9: Signup never creates a
-- Supabase Auth user directly (approval-gated, not self-serve). This table
-- is the entire "Request access" flow's backend -- one row per request,
-- reviewed out-of-band by an admin holding the service-role key.
--
-- First table in this project with RLS on. anon (the key shipped in the
-- frontend bundle) may INSERT and nothing else -- no SELECT, no UPDATE, no
-- DELETE, so a request can never be read back, edited or enumerated by
-- anyone holding only the public key. service_role bypasses RLS entirely,
-- which is exactly the review path this is designed for.

CREATE TABLE access_requests (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       text NOT NULL,
    work_email      text NOT NULL,
    organization    text NOT NULL,
    role_title      text,
    org_type        text,
    use_case        text,
    status          text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected')),
    submitted_at    timestamptz NOT NULL DEFAULT now(),
    reviewed_at     timestamptz,
    reviewed_by     text
);

ALTER TABLE access_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "anon can submit a request"
    ON access_requests
    FOR INSERT
    TO anon
    WITH CHECK (true);

-- No SELECT/UPDATE/DELETE policy for anon or authenticated: deliberately
-- absent, not an oversight. Only service_role (which bypasses RLS) reviews
-- requests -- from a server-side admin action, never from the browser.
