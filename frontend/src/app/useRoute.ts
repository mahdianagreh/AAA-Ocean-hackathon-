import { useEffect, useState } from 'react';

/** The router.
 *
 *  This used to be two routes and a ternary, on the reasoning that one screen
 *  does not justify a router dependency. The brand rebuild adds a marketing
 *  home, an auth pair and eleven dashboard destinations, so that reasoning has
 *  expired — but the conclusion has not. react-router is ~15 KB and a
 *  dependency to keep current; a table of patterns and a segment match is ~50
 *  lines and cannot break offline, which is the constraint that actually binds
 *  here (DoD item 9 — the app must run with wifi off, and every byte it needs
 *  has to be in the bundle already).
 *
 *  Note `/` is now the marketing home, NOT the map. The operational screen
 *  moved to `/dashboard`. Every Playwright spec that used to open `/` and expect
 *  a map was repointed in the same change.
 */

export type RouteName =
  | 'home'
  | 'login'
  | 'signup'
  | 'dashboard'
  | 'replay'
  | 'validation'
  | 'provenance'
  | 'limitations'
  | 'assistant'
  | 'reefZones'
  | 'reefZone'
  | 'events'
  | 'reports'
  | 'sitesScore'
  | 'alerts'
  | 'recommendation'
  | 'systemHealth'
  | 'dataExplorer'
  | 'account'
  | 'specimen'
  | 'backtests'
  | 'notFound';

export interface RouteMatch {
  name: RouteName;
  params: Record<string, string>;
  path: string;
}

/** Order matters: the first match wins, so literal segments are listed before
 *  the patterns that would also swallow them. `/reef-zones` must precede
 *  `/reef-zones/:id` for that reason, and `:id` never matches an empty segment. */
const ROUTES: ReadonlyArray<readonly [string, RouteName]> = [
  ['/', 'home'],
  ['/login', 'login'],
  ['/signup', 'signup'],
  ['/dashboard', 'dashboard'],
  ['/dashboard/validation', 'validation'],
  ['/dashboard/provenance', 'provenance'],
  // Both forms resolve to the same page. The bare form is what the nav rail
  // links to, because the rail cannot know which event you want and the project
  // rule is that no component hard-codes an event date — ReplayPage resolves the
  // default itself from the event catalogue.
  ['/dashboard/replay', 'replay'],
  ['/dashboard/replay/:eventId', 'replay'],
  ['/limitations', 'limitations'],
  ['/assistant', 'assistant'],
  ['/reef-zones', 'reefZones'],
  ['/reef-zones/:id', 'reefZone'],
  ['/events', 'events'],
  ['/reports', 'reports'],
  ['/sites/score', 'sitesScore'],
  ['/alerts', 'alerts'],
  // Both forms resolve to the same page, same reasoning as replay above: there
  // is no list endpoint to browse, so a bare hand-typed/bookmarked URL still
  // has to land somewhere rather than 404 — RecommendationPage shows its
  // empty state instead.
  ['/dashboard/recommendations', 'recommendation'],
  ['/dashboard/recommendations/:recommendationId', 'recommendation'],
  ['/system-health', 'systemHealth'],
  ['/data-explorer', 'dataExplorer'],
  ['/account', 'account'],
  ['/specimen', 'specimen'],
  ['/backtests', 'backtests'],
];

/** Strip trailing slashes, but keep the root as "/" rather than "". */
function normalise(pathname: string): string {
  const p = pathname.replace(/\/+$/, '');
  return p === '' ? '/' : p;
}

export function matchRoute(pathname: string): RouteMatch {
  const path = normalise(pathname);
  const parts = path.split('/').filter(Boolean);

  for (const [pattern, name] of ROUTES) {
    const pp = pattern.split('/').filter(Boolean);
    if (pp.length !== parts.length) continue;

    const params: Record<string, string> = {};
    let ok = true;
    for (let i = 0; i < pp.length; i++) {
      const seg = pp[i];
      if (seg.startsWith(':')) {
        if (!parts[i]) {
          ok = false;
          break;
        }
        params[seg.slice(1)] = decodeURIComponent(parts[i]);
      } else if (seg !== parts[i]) {
        ok = false;
        break;
      }
    }
    if (ok) return { name, params, path };
  }

  return { name: 'notFound', params: {}, path };
}

/** pushState does not fire popstate — that event is for the back/forward button
 *  only. Without a custom event of our own, a programmatic navigation would
 *  change the URL and leave the view on the previous screen, which looks like a
 *  dead link and is maddening to debug. */
const NAV_EVENT = 'aq:navigate';

export function navigate(to: string, opts: { replace?: boolean } = {}) {
  const current = window.location.pathname + window.location.search;
  if (to === current) return;

  if (opts.replace) window.history.replaceState({}, '', to);
  else window.history.pushState({}, '', to);

  window.dispatchEvent(new Event(NAV_EVENT));
}

export function useRoute(): RouteMatch {
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    const sync = () => setPath(window.location.pathname);
    window.addEventListener('popstate', sync);
    window.addEventListener(NAV_EVENT, sync);
    return () => {
      window.removeEventListener('popstate', sync);
      window.removeEventListener(NAV_EVENT, sync);
    };
  }, []);

  return matchRoute(path);
}

/** Preserves the query string across an in-app navigation.
 *
 *  ?lang / ?theme / ?mode seed the UI store on load, and the Playwright specs
 *  and the specimen route both drive the app through them. A link that dropped
 *  the search would silently reset an Arabic dark session to English light on
 *  the first click. */
export function hrefWithSearch(to: string): string {
  const search = window.location.search;
  return search ? `${to}${search}` : to;
}

/** True when the specimen route should be reachable. Dev always; a built image
 *  only with VITE_SPECIMEN=1, so the Playwright walk and the compose dev
 *  container can both still reach it. */
export const specimenEnabled =
  import.meta.env.DEV || import.meta.env.VITE_SPECIMEN === '1';
