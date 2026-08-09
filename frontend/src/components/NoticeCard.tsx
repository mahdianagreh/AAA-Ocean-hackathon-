import type { ReactNode } from 'react';

/** The permanent, non-dismissible honesty notice — Phase 8, Track A. Was a
 *  bare `border-hairline-2 bg-surface-2` box on both auth screens, which reads
 *  as a hint. It is not a hint, it is the most important sentence on the
 *  page, so this restyles it UP (coloured border + icon), never down, and it
 *  is not dismissible — there is no close button and never should be.
 *
 *  Reuses `risk-high` rather than `risk-critical`: this is a stated
 *  limitation, not an error condition. Distinct in shape from `CaveatList`
 *  (which renders a dynamic API `caveats[]` array) on purpose — this is one
 *  fixed, hand-written claim, not a list of backend-supplied ones, and
 *  forcing one shape onto the other would be worse than two small,
 *  correct components. */
export function NoticeCard({
  id,
  title,
  children,
}: {
  id: string;
  title: ReactNode;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      className="flex flex-col gap-2 rounded-md border-2 border-risk-high-stroke bg-surface-2 p-4"
    >
      <div className="flex items-center gap-2">
        <span aria-hidden="true" className="text-sm text-risk-high">
          ⓘ
        </span>
        <h2 id={`${id}-title`} className="m-0 text-xs font-bold text-ink">
          {title}
        </h2>
      </div>
      <div className="flex flex-col gap-2 ps-6 text-xs leading-[1.6] text-ink-2">
        {children}
      </div>
    </section>
  );
}
