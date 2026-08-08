import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from 'react';
import { hrefWithSearch, navigate } from '../app/useRoute';

/** An in-app link.
 *
 *  It renders a real <a href>, not a div with onClick. That is not pedantry:
 *  a real anchor gets keyboard focus, an accessible role, a status-bar preview,
 *  middle-click-to-new-tab and Cmd-click for free, and axe runs over every page
 *  in this suite. Only an unmodified left click is intercepted — anything with a
 *  modifier key, or a non-primary button, is left to the browser so those
 *  behaviours keep working. */
export function Link({
  to,
  children,
  onNavigate,
  ...rest
}: {
  to: string;
  children: ReactNode;
  onNavigate?: () => void;
} & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, 'href'>) {
  const href = hrefWithSearch(to);

  const onClick = (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.defaultPrevented) return;
    if (e.button !== 0) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

    e.preventDefault();
    navigate(href);
    onNavigate?.();
  };

  return (
    <a href={href} onClick={onClick} {...rest}>
      {children}
    </a>
  );
}
