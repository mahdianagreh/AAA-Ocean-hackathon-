import { Select as RadixSelect } from 'radix-ui';
import type { ReactNode } from 'react';

/** A small brand-styled dropdown over Radix Select.
 *
 *  Radix supplies the hard parts — typeahead, roving focus, direction-aware
 *  keyboard nav, portalled listbox that escapes overflow — so a filter control
 *  can be a real selection instead of a free-text box the reader has to know the
 *  ID format to use. Everything visual comes from tokens; no colour is written
 *  here.
 */
export interface SelectOption {
  value: string;
  label: string;
}

export function Select({
  value,
  onChange,
  options,
  label,
  icon,
}: {
  value: string;
  onChange: (v: string) => void;
  options: ReadonlyArray<SelectOption>;
  label: string;
  icon?: ReactNode;
}) {
  return (
    <RadixSelect.Root value={value} onValueChange={onChange}>
      <RadixSelect.Trigger
        aria-label={label}
        className="inline-flex min-h-9 items-center gap-2 border border-hairline bg-surface px-3 text-xs text-ink transition-colors hover:border-hairline-2 data-[state=open]:border-accent"
        style={{ borderRadius: 'var(--radius-md)' }}
      >
        {icon ? <span className="text-ink-3">{icon}</span> : null}
        <RadixSelect.Value />
        <RadixSelect.Icon className="text-ink-3">
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" fill="none">
            <path d="M3 4.5 6 7.5 9 4.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </RadixSelect.Icon>
      </RadixSelect.Trigger>
      <RadixSelect.Portal>
        <RadixSelect.Content
          position="popper"
          sideOffset={4}
          className="z-50 overflow-hidden border border-hairline bg-surface"
          style={{ borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-md)' }}
        >
          <RadixSelect.Viewport className="p-1">
            {options.map((o) => (
              <RadixSelect.Item
                key={o.value}
                value={o.value}
                className="flex min-h-8 cursor-pointer select-none items-center gap-2 px-2.5 text-xs text-ink outline-none data-[highlighted]:bg-surface-2 data-[state=checked]:font-semibold"
                style={{ borderRadius: 'var(--radius-sm)' }}
              >
                <RadixSelect.ItemIndicator className="text-accent">
                  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" fill="none">
                    <path d="M2.5 6.5 5 9l4.5-5.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </RadixSelect.ItemIndicator>
                <RadixSelect.ItemText>{o.label}</RadixSelect.ItemText>
              </RadixSelect.Item>
            ))}
          </RadixSelect.Viewport>
        </RadixSelect.Content>
      </RadixSelect.Portal>
    </RadixSelect.Root>
  );
}
