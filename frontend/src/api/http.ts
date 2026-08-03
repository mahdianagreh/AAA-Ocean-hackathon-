import { API_BASE, type ApiClient } from './client';
import type { Catchment, Health, Outlet, ReefZone } from './types';
import { fixtureClient } from './fixtures';

/** The HTTP implementation, against the live API.
 *
 *  Three of the five endpoints work today. Where one does not exist yet, this
 *  falls back to the fixture — deliberately, and it says so in the console rather
 *  than silently. The alternative is a blank panel in rehearsal, which is exactly
 *  what 07 §5's contract tests exist to prevent.
 */

async function json<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`);
  if (!r.ok) {
    // The model endpoints answer 503 with a dict body naming what they are
    // blocked on. Preserve it — that detail is the useful part.
    let detail = '';
    try {
      detail = JSON.stringify((await r.json()) as unknown);
    } catch {
      detail = r.statusText;
    }
    throw new Error(`${path}: HTTP ${r.status} ${detail}`);
  }
  return (await r.json()) as T;
}

export function httpClient(): ApiClient {
  const fallback = fixtureClient();

  return {
    kind: 'http',

    // NOTE: /health, not /api/v1/health. The planning docs say the latter; the
    // API serves the former (main.py:134). OPEN-ISSUES.md item 5.
    health() {
      return json<Health>('/health');
    },

    async catchments() {
      const r = await json<{ catchments: Catchment[] }>('/api/v1/catchments');
      return r.catchments;
    },

    async outlets() {
      const r = await json<{ outlets: Outlet[] }>('/api/v1/outlets');
      return r.outlets;
    },

    async reefZones(): Promise<ReefZone[]> {
      // /api/v1/reef-zones does not exist — OPEN-ISSUES.md item 1, Day-1 ask #8.
      // Falling back rather than throwing keeps the map complete, and the warning
      // keeps it from being mistaken for a working endpoint.
      console.warn(
        '[api] /api/v1/reef-zones is not implemented; using the committed GeoJSON. ' +
          'See docs/OPEN-ISSUES.md item 1.',
      );
      return fallback.reefZones();
    },
  };
}
