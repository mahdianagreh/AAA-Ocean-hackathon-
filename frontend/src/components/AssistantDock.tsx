import { useTranslation } from 'react-i18next';
import { Link } from './Link';

/** The persistent assistant surface.
 *
 *  Phase 7 asks for the assistant reachable from every dashboard page, not only
 *  /assistant and not only via the rail link a user has to hunt for. This is a
 *  fixed dock, bottom-end (so it flips to bottom-start in RTL via a logical
 *  inset), present on every dashboard page except the assistant page itself and
 *  the map — the map already carries the assistant in its masthead and overlay.
 *
 *  Navy ground with foam-white label: fixed brand furniture like the rail, so it
 *  reads at 14.6:1 in both themes and never inverts. It links rather than opening
 *  an inline panel, keeping Phase 8's "no new features" line — it surfaces the
 *  existing route, it does not build a second assistant. */
export function AssistantDock() {
  const { t } = useTranslation('nav');
  const label = t('assistant');
  return (
    <Link
      to="/assistant"
      data-assistant-dock="true"
      aria-label={label}
      title={label}
      className="fixed bottom-6 z-40 flex items-center gap-2 rounded-full px-4 py-3 text-xs font-bold no-underline shadow-lg transition-opacity hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
      style={{
        insetInlineEnd: '1.5rem',
        background: 'var(--brand-navy)',
        color: 'var(--brand-foam)',
        // --accent (not --brand-aqua): the ring is offset onto the light page
        // canvas, where brand-aqua is only ~2.3:1 — below WCAG 1.4.11's 3:1.
        outlineColor: 'var(--accent)',
      }}
    >
      <svg
        width="18"
        height="18"
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="8" cy="8" r="5.5" />
        <path d="M6.4 6.3 A1.7 1.7 0 1 1 8 9 V10" />
        <circle cx="8" cy="11.8" r="0.6" fill="currentColor" />
      </svg>
      <span className="hidden sm:inline">{label}</span>
    </Link>
  );
}
