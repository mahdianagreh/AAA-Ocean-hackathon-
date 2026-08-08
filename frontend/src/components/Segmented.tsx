import { ToggleGroup } from 'radix-ui';
import type { ReactNode } from 'react';

/** The brand segmented control: a recessed track with one raised, gradient pill.
 *
 *  Radix supplies what is genuinely hard — roving tabindex, arrow-key navigation
 *  that respects direction through DirectionProvider, and correct group
 *  semantics. Hand-rolling that is how a control ends up keyboard-inaccessible
 *  while looking finished.
 *
 *  The selected pill is the brand gradient, which does not invert with the
 *  theme, so its label is a fixed white rather than --ink-inverse (that token
 *  resolves to navy in dark theme and would be navy-on-navy). Selection is also
 *  never carried by colour alone: the pill raises with a shadow and the label
 *  goes semibold, both of which survive greyscale and colour-blindness.
 */

export interface SegmentedOption<T extends string> {
  value: T;
  label: string;
  /** Optional leading glyph. Decorative — the label is always present. */
  icon?: ReactNode;
  /** Extra attributes for the item, e.g. the data-mode hook the specs target. */
  data?: Record<string, string>;
}

const ON_GRADIENT = '#fff'; // token-ok: label on fixed brand gradient, which does not invert

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  size = 'md',
}: {
  value: T;
  onChange: (v: T) => void;
  options: ReadonlyArray<SegmentedOption<T>>;
  label: string;
  size?: 'sm' | 'md';
}) {
  const pad = size === 'sm' ? 'px-2.5 py-1.5' : 'px-3.5 py-2';

  return (
    <ToggleGroup.Root
      type="single"
      value={value}
      onValueChange={(v) => {
        // Radix emits '' when the pressed item is deselected. These groups are
        // exhaustive and one is always active, so ignore the empty case rather
        // than letting the view fall into no state at all.
        if (v) onChange(v as T);
      }}
      aria-label={label}
      className="inline-flex items-center gap-1 border border-hairline bg-surface-2 p-1"
      style={{ borderRadius: 'var(--radius-md)' }}
    >
      {options.map((o) => {
        const on = o.value === value;
        return (
          <ToggleGroup.Item
            key={o.value}
            value={o.value}
            {...(o.data ?? {})}
            className={[
              'inline-flex items-center gap-1.5 whitespace-nowrap text-xs transition-colors',
              pad,
              on ? 'font-bold' : 'font-semibold text-ink-2 hover:text-ink',
            ].join(' ')}
            style={{
              borderRadius: 'var(--radius-sm)',
              minBlockSize: '2rem',
              backgroundImage: on ? 'var(--brand-gradient)' : 'none',
              color: on ? ON_GRADIENT : undefined,
              boxShadow: on ? 'var(--shadow-sm)' : 'none',
            }}
          >
            {o.icon ? (
              <span aria-hidden="true" className="inline-flex">
                {o.icon}
              </span>
            ) : null}
            {o.label}
          </ToggleGroup.Item>
        );
      })}
    </ToggleGroup.Root>
  );
}
