import type { ReactNode } from 'react';

/** A clean vertical timeline (icon + timestamp + label), shared so a "list of
 *  events in time" never reverts to a plain <dl>. Vertical rather than
 *  absolutely-positioned horizontal because it stays correct under RTL with pure
 *  logical properties.
 *
 *  Each entry's dot colour is driven by provenance form, the project's honesty
 *  rule: a measured timestamp and a modelled one are different kinds of claim, so
 *  they read differently (solid measured vs dashed-hue modelled) rather than
 *  identically. */

export interface TimelineEntry {
  key: string;
  label: ReactNode;
  /** ISO timestamp or any short string; rendered LTR-isolated as a mono value. */
  time: string;
  /** Small provenance / kind tag under the time. */
  meta?: ReactNode;
  provenance?: 'measured' | 'reported' | 'converted' | 'modelled' | string;
}

function dotColor(provenance: TimelineEntry['provenance']): string {
  if (provenance === 'modelled') return 'var(--data-modelled)';
  // reported/converted use --ink-3 rather than the ~88%-transparent envelope
  // fill, so a dot stroke stays visible; the meta text still names the kind.
  if (provenance === 'converted' || provenance === 'reported') return 'var(--ink-3)';
  return 'var(--data-measured)';
}

export function Timeline({ entries, ariaLabel }: { entries: ReadonlyArray<TimelineEntry>; ariaLabel?: string }) {
  if (entries.length === 0) return null;
  return (
    <ol className="relative m-0 flex list-none flex-col gap-4 p-0 ps-6" aria-label={ariaLabel}>
      {/* The connecting rail, on the inline-start edge (flips in RTL). */}
      <span aria-hidden="true" className="absolute inset-y-2 start-[4px] w-px bg-hairline-2" />
      {entries.map((e) => (
        <li key={e.key} className="relative flex flex-col gap-0.5">
          <span
            aria-hidden="true"
            className="absolute top-1 h-2.5 w-2.5 rounded-full border-2"
            style={{ insetInlineStart: '-1.5rem', background: 'var(--surface)', borderColor: dotColor(e.provenance) }}
          />
          <span className="text-xs font-semibold text-ink">{e.label}</span>
          <span className="flex flex-wrap items-baseline gap-2">
            <code dir="ltr" style={{ unicodeBidi: 'isolate' }} className="num font-mono text-2xs text-ink-2">
              {e.time}
            </code>
            {e.meta ? <span className="text-2xs text-ink-3">{e.meta}</span> : null}
          </span>
        </li>
      ))}
    </ol>
  );
}
