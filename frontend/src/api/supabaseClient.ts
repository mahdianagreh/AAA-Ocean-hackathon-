import { createClient } from '@supabase/supabase-js';

/** Phase 8, Track B (tasks/00-contracts.md §9). The anon/publishable key is
 *  safe to ship in the bundle by design — RLS is what actually protects data,
 *  not keeping this key secret. `persistSession`/`autoRefreshToken` are
 *  Supabase's own session-refresh implementation; `useAuth.tsx` subscribes
 *  to it rather than re-implementing token refresh.
 *
 *  `null` when the env vars are absent (e.g. a checkout that never ran
 *  Track B's setup) — every caller must handle that, the same "not available"
 *  discipline as `frontend/src/api/live.ts`'s best-effort functions. */
const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase = url && anonKey ? createClient(url, anonKey) : null;
