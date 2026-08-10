import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { Session } from '@supabase/supabase-js';
import { supabase } from '../api/supabaseClient';

/** Phase 8, Track B (tasks/00-contracts.md §9) — the ONLY place session state
 *  lives. No component reads `supabase.auth` directly; everything goes
 *  through `useAuth()`.
 *
 *  Session persistence/refresh is Supabase's own client (`persistSession`,
 *  `autoRefreshToken` in `supabaseClient.ts`) — this just subscribes to it
 *  and tells the two failure modes apart: an explicit sign-out (`signOut()`
 *  was called here) versus a refresh that failed silently in the background,
 *  which must surface as a visible "your session ended" state rather than
 *  quietly 401-ing every panel mid-demo. */

interface AuthState {
  session: Session | null;
  loading: boolean;
  /** True only when a session existed and then disappeared WITHOUT this
   *  context's own `signOut()` being the cause — a real expiry/refresh
   *  failure, not a user action. */
  sessionExpired: boolean;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
  clearSessionExpired: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);
  const signingOutRef = useRef(false);

  useEffect(() => {
    if (!supabase) {
      setLoading(false);
      return;
    }

    void supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });

    const { data: sub } = supabase.auth.onAuthStateChange((event, next) => {
      setSession((prev) => {
        if (event === 'SIGNED_OUT' && prev && !signingOutRef.current) {
          // Had a session, lost it, and we didn't ask for that — a refresh
          // failure, not a click on "sign out".
          setSessionExpired(true);
        }
        return next;
      });
      signingOutRef.current = false;
    });

    return () => sub.subscription.unsubscribe();
  }, []);

  async function signIn(email: string, password: string) {
    if (!supabase) return { error: 'auth-not-configured' };
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    // Never distinguish "wrong email" from "wrong password" — same message
    // either way, since the user list is a short list of named institutions.
    return { error: error ? 'invalid-credentials' : null };
  }

  async function signOut() {
    if (!supabase) return;
    signingOutRef.current = true;
    await supabase.auth.signOut();
  }

  return (
    <AuthContext.Provider
      value={{
        session,
        loading,
        sessionExpired,
        signIn,
        signOut,
        clearSessionExpired: () => setSessionExpired(false),
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth() must be used inside <AuthProvider>');
  return ctx;
}
