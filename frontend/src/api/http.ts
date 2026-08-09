import { API_BASE, type ApiClient } from './client';
import type { Catchment, Health, Outlet, ReefZone } from './types';
import { fixtureClient } from './fixtures';

/** The HTTP implementation, against the live API.
 *
 *  It merges rather than replaces, and that is the whole design of this file.
 *
 *  The API's geometry endpoints are thinner than the committed snapshot: a
 *  `CatchmentOut` carries catchment_id, outlet_id, area_km2, geometry, landcover,
 *  soil, urban, provenance and caveats — and no `name`, `lon`, `lat`,
 *  `position_confidence` or `caveat`, all of which the map and the side rail
 *  read. The same is true of outlets. So taking the API response wholesale
 *  produces objects that satisfy the type only by accident and render as blanks.
 *
 *  Two real bugs lived here until 8 Aug 2026, both invisible because
 *  VITE_DATA_SOURCE defaults to `fixtures` and this file was therefore almost
 *  never executed:
 *
 *    1. catchments() and outlets() unwrapped `{catchments: [...]}` and
 *       `{outlets: [...]}`. The API returns a BARE ARRAY. So both returned
 *       `undefined`, and the first `.map()` in useRiskCards threw — a blank
 *       dashboard, with the stack pointing at the consumer rather than here.
 *    2. reefZones() claimed /api/v1/reef-zones "does not exist". It does, and
 *       serves eight real Allen Coral Atlas zones.
 *
 *  Both are fixed below. The snapshot supplies the display fields the API does
 *  not serve; the API supplies the live values. If the API is unreachable the
 *  snapshot answers alone, which is what keeps the wifi-off requirement true.
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

/** Accepts either a bare array or a single-key envelope around one.
 *
 *  The API returns bare arrays today. Tolerating both costs one line and means a
 *  future envelope change degrades to "no live rows" instead of a crash. */
function asList<T>(body: unknown, key: string): T[] {
  if (Array.isArray(body)) return body as T[];
  if (body && typeof body === 'object') {
    const inner = (body as Record<string, unknown>)[key];
    if (Array.isArray(inner)) return inner as T[];
  }
  return [];
}

/** Overlay live rows onto snapshot rows, keyed by id.
 *
 *  Snapshot first, so a field the API does not serve survives; then only those
 *  API values that are actually present, so a null from the API cannot blank a
 *  field the snapshot knew. Snapshot rows with no live counterpart are kept —
 *  dropping them would silently shrink the map. */
function mergeById<T extends object>(
  snapshot: T[],
  live: Array<Record<string, unknown>>,
  idKey: keyof T & string,
): T[] {
  const byId = new Map(live.filter((r) => r[idKey] != null).map((r) => [String(r[idKey]), r]));
  return snapshot.map((base) => {
    const hit = byId.get(String((base as Record<string, unknown>)[idKey]));
    if (!hit) return base;
    const merged: Record<string, unknown> = { ...(base as Record<string, unknown>) };
    for (const [k, v] of Object.entries(hit)) {
      if (v !== null && v !== undefined) merged[k] = v;
    }
    return merged as T;
  });
}

/** Live where possible, snapshot where not, and never a throw.
 *
 *  A failed live call must not take the map down: the snapshot is a complete,
 *  committed answer on its own. The warning names which one is on screen. */
async function liveOrSnapshot<T extends object>(
  path: string,
  key: string,
  idKey: keyof T & string,
  snapshot: () => Promise<T[]>,
): Promise<T[]> {
  const base = await snapshot();
  try {
    const rows = asList<Record<string, unknown>>(await json<unknown>(path), key);
    if (rows.length === 0) {
      console.warn(`[api] ${path} returned no rows; using the committed snapshot.`);
      return base;
    }
    return mergeById(base, rows, idKey);
  } catch (e) {
    console.warn(`[api] ${path} unavailable (${(e as Error).message}); using the committed snapshot.`);
    return base;
  }
}

export function httpClient(): ApiClient {
  const fallback = fixtureClient();

  return {
    kind: 'http',

    // NOTE: /health, not /api/v1/health. The planning docs say the latter; the
    // API serves both, and this one is the container's HEALTHCHECK contract.
    health() {
      return json<Health>('/health');
    },

    catchments() {
      return liveOrSnapshot<Catchment>(
        '/api/v1/catchments',
        'catchments',
        'catchment_id',
        () => fallback.catchments(),
      );
    },

    outlets() {
      return liveOrSnapshot<Outlet>(
        '/api/v1/outlets',
        'outlets',
        'outlet_id',
        () => fallback.outlets(),
      );
    },

    reefZones() {
      // Real ACA geometry and the live sensitivity_weight_status, over the
      // snapshot's display fields. `provisional` is not an API field — it stays
      // whatever the snapshot says, because it describes the weighting rather
      // than the geometry.
      return liveOrSnapshot<ReefZone>(
        '/api/v1/reef-zones?include_geometry=false',
        'reef_zones',
        'reef_zone_id',
        () => fallback.reefZones(),
      );
    },
  };
}
