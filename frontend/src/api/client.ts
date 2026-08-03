import type { Catchment, Health, Outlet, ReefZone } from './types';

/** One client interface, two implementations, selected by env var.
 *
 *  07 §5: components never know which is live. That boundary is not only an
 *  architecture preference — 10-performance-and-offline.md requires the
 *  deterministic demo mode to work "without network **and without the API**", so
 *  the fixture implementation *is* the demo path, not a development convenience.
 *
 *  Fixtures are built from real repo artefacts, never invented. Invented fixtures
 *  produce a UI that fits numbers which never arrive.
 */
export interface ApiClient {
  readonly kind: 'fixtures' | 'http';
  health(): Promise<Health>;
  catchments(): Promise<Catchment[]>;
  outlets(): Promise<Outlet[]>;
  reefZones(): Promise<ReefZone[]>;
}

/** The 503 both model endpoints return today is a state, not an error.
 *
 *  `data/models/` does not exist, so /api/v1/models and /api/v1/runoff/predict
 *  answer 503 with a *dict* body naming what they are blocked on. That is the
 *  honest state of the project — the harness is built and validated, no artefact
 *  is registered — and the UI should say so rather than show a failure toast.
 *  Modelling it as a discriminated union from day one keeps that possible. */
export interface NotReady {
  kind: 'not_ready';
  error: string;
  why?: string;
  blocked_on?: string;
  harness_status?: string;
}

export type Result<T> = { kind: 'ok'; value: T } | NotReady | { kind: 'error'; message: string };

export const DATA_SOURCE = (import.meta.env.VITE_DATA_SOURCE ?? 'fixtures') as
  | 'fixtures'
  | 'http';

export const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
