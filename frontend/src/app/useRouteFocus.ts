import { useEffect, useRef } from 'react';

/** Moves focus to the page heading after an in-app navigation.
 *
 *  Phase 7: "move focus to the page heading, or keyboard users land nowhere."
 *  Without this, a hand-rolled SPA swaps the DOM under the router while the
 *  browser's focus stays on the link that was just clicked (or is lost to
 *  <body>), so a screen-reader user hears nothing and a keyboard user tabs from
 *  the top of a page they cannot see.
 *
 *  It targets [data-page-heading] (PageShell's H1); pages that bring their own
 *  frame — marketing, auth, the map — fall back to their first <h1>, which is
 *  made programmatically focusable on the fly. The very first mount is skipped:
 *  focus belongs where the browser put it on a fresh load, and only a genuine
 *  navigation should relocate it.
 */
export function useRouteFocus(routeKey: string) {
  const firstRun = useRef(true);

  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }

    // Let the new route commit and paint before we reach for its heading.
    const raf = requestAnimationFrame(() => {
      const el =
        document.querySelector<HTMLElement>('[data-page-heading]') ??
        document.querySelector<HTMLElement>('main h1') ??
        document.querySelector<HTMLElement>('h1');
      if (!el) return;
      if (el.tabIndex < 0 && !el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1');
      el.focus({ preventScroll: false });
    });

    return () => cancelAnimationFrame(raf);
  }, [routeKey]);
}
