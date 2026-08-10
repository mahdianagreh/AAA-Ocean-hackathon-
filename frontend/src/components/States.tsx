import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

/** The states 04-component-inventory.md requires, as real components.
 *
 *  "A component whose empty, error and stale states were never designed will
 *  improvise them on stage." So they are designed here, once, and reused — rather
 *  than each panel inventing its own spinner and its own error paragraph.
 *
 *  Four of the nine states are structural rather than visual (default, hover,
 *  focus-visible, active, disabled all live on the control itself). These are the
 *  five that are their own thing: loading, empty, error, stale, and the missing
 *  value that ValueWithUnit already owns.
 */

/** Loading. A line of text, not a spinner.
 *
 *  01 §7: nothing moves without being asked. A spinner is motion nobody requested,
 *  and on a fixture-backed view it appears for one frame and reads as a flicker. */
export function Loading({ what }: { what?: string }) {
  return (
    <p data-state="loading" className="text-xs text-ink-3" aria-live="polite">
      {what ?? '…'}
    </p>
  );
}

/** Empty — and this one is a first-class design problem, not a fallback.
 *
 *  03 §2: "Forecast must work on a dry day and show a correctly low number. A
 *  system that only demos during a storm is not demoable." So empty says WHY it is
 *  empty and what that means, because "no plume today" and "the plume layer failed
 *  to load" must never look the same.
 */
export function Empty({ title, body, icon }: { title: string; body?: string; icon?: ReactNode }) {
  // With an icon this becomes a centred, generously-padded first-class empty
  // state (used where the empty case is itself the story, e.g. /alerts); without
  // one it stays the compact inline note the data panels use.
  if (icon) {
    return (
      <div
        data-state="empty"
        className="flex flex-col items-center gap-3 rule bg-surface-2 px-6 py-12 text-center"
      >
        <span className="text-accent" aria-hidden="true">
          {icon}
        </span>
        <p className="m-0 text-sm font-semibold text-ink">{title}</p>
        {body ? <p className="m-0 max-w-prose text-xs text-ink-2">{body}</p> : null}
      </div>
    );
  }
  return (
    <div data-state="empty" className="flex flex-col gap-1 rule bg-surface-2 p-3">
      <p className="text-xs font-semibold">{title}</p>
      {body ? <p className="max-w-prose text-2xs text-ink-2">{body}</p> : null}
    </div>
  );
}

/** Error. role="alert", and it names the thing that failed rather than apologising. */
export function ErrorState({ message, what }: { message: string; what?: string }) {
  const { t } = useTranslation();
  return (
    <div data-state="error" role="alert" className="flex flex-col gap-1 rule border-risk-critical-stroke bg-surface p-3">
      <p className="text-xs font-semibold text-risk-critical">
        {what ?? t('states.errorTitle')}
      </p>
      <code
        dir="ltr"
        style={{ unicodeBidi: 'isolate' }}
        className="max-w-prose font-mono num text-2xs text-ink-2"
      >
        {message}
      </code>
    </div>
  );
}

/** Stale — "a real state in Forecast mode, not a hypothetical" (04).
 *
 *  Hatched, because that is the form language for an uncertainty envelope and
 *  stale data is exactly that: it was true, and may not be now. Form rather than
 *  colour, so it survives the projector and the photograph.
 */
export function Stale({ children, ageLabel }: { children: React.ReactNode; ageLabel: string }) {
  const { t } = useTranslation();
  return (
    <div data-state="stale" className="relative flex flex-col gap-1">
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          backgroundImage:
            'repeating-linear-gradient(45deg, var(--data-modelled) 0 1px, transparent 1px 5px)',
        }}
      />
      <div className="relative">{children}</div>
      <p className="relative text-2xs text-ink-3">
        {t('states.stale', { age: ageLabel })}
      </p>
    </div>
  );
}
