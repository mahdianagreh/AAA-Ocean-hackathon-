import { useEffect, useState } from 'react';

/** Two routes do not justify a router.
 *
 *  03 §1 locks the information architecture to one screen: `/` is the map, and
 *  the limitations text and provenance panel are overlays rather than routes.
 *  `/specimen` is the dev-only component gallery. That is the whole surface, so
 *  react-router-dom would be ~15 KB and a dependency to keep current in exchange
 *  for nothing. Revisit only if a phase genuinely adds a third destination.
 */
export type Route = '/' | '/specimen';

export function useRoute(): Route {
  const [path, setPath] = useState(() => window.location.pathname);

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  return path.replace(/\/+$/, '') === '/specimen' ? '/specimen' : '/';
}

/** True when the specimen route should be reachable. Dev always; a built image
 *  only with VITE_SPECIMEN=1, so the Playwright walk and the compose dev
 *  container can both still reach it. */
export const specimenEnabled =
  import.meta.env.DEV || import.meta.env.VITE_SPECIMEN === '1';
