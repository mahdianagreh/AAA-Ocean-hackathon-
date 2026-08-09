import type { ReactNode } from 'react';

/** The one shared data-table treatment, per Phase 8.
 *
 *  Page 2 (Reef Zones) establishes it; Pages 7 (Validation) and 12 (Data
 *  Explorer) reuse it, so the three do not become three hand-rolled <table>s
 *  that drift apart. Foam White (`--surface-2`) header, hairline row dividers,
 *  consistent cell padding on the 8-point grid.
 *
 *  The responsive answer is a real affordance, not silent horizontal scroll:
 *  at/above `sm` it is a table inside a keyboard-focusable scroll region; below
 *  `sm` it collapses to a card stack, one card per row, label:value pairs. Both
 *  branches read from the same column definitions, so there is one source of
 *  truth for what each column is and how its cell renders.
 */

export interface Column<T> {
  key: string;
  header: ReactNode;
  /** Renders the cell for a row. Numbers should come through <ValueWithUnit>. */
  cell: (row: T, index: number) => ReactNode;
  /** Logical alignment; `end` is right in LTR and left in RTL — use it for numerics. */
  align?: 'start' | 'center' | 'end';
  headerClassName?: string;
  cellClassName?: string;
  /** Label shown beside the value in the card-stack (narrow) layout. Defaults to `header`. */
  cardLabel?: ReactNode;
  /** Set for a sortable column so the <th> announces its sort state. The header
   *  node itself supplies the clickable control; this only wires aria-sort. */
  ariaSort?: 'ascending' | 'descending' | 'none';
}

const alignClass: Record<NonNullable<Column<unknown>['align']>, string> = {
  start: 'text-start',
  center: 'text-center',
  end: 'text-end',
};

export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  ariaLabel,
  caption,
  className = '',
}: {
  columns: ReadonlyArray<Column<T>>;
  rows: ReadonlyArray<T>;
  getRowKey: (row: T, index: number) => string;
  /** Names the table for screen readers and the scroll region. Pass translated text. */
  ariaLabel: string;
  /** Optional visible caption above the table. */
  caption?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {caption ? <p className="m-0 text-2xs text-ink-3">{caption}</p> : null}

      {/* Wide layout: a real table in a focusable scroll region. */}
      <div
        role="region"
        aria-label={ariaLabel}
        tabIndex={0}
        className="hidden overflow-x-auto rule sm:block focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2"
        style={{ outlineColor: 'var(--accent)' }}
      >
        <table className="w-full border-collapse text-xs" aria-label={ariaLabel}>
          <thead>
            <tr className="bg-surface-2">
              {columns.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={c.ariaSort}
                  className={`whitespace-nowrap border-b border-hairline px-4 py-3 text-2xs font-bold uppercase tracking-wide text-ink-2 ${alignClass[c.align ?? 'start']} ${c.headerClassName ?? ''}`}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={getRowKey(row, i)} className="border-b border-hairline last:border-b-0">
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={`px-4 py-3 align-top text-ink ${alignClass[c.align ?? 'start']} ${c.cellClassName ?? ''}`}
                  >
                    {c.cell(row, i)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Narrow layout: card stack, one card per row. The affordance the task
          asks for instead of a silent horizontal scrollbar. */}
      <ul className="m-0 flex list-none flex-col gap-3 p-0 sm:hidden">
        {rows.map((row, i) => (
          // Surface (white), not the surface-2 glass tint, so a nullable cell's
          // --ink-3 "missing" marker stays AA-compliant on the mobile card.
          <li key={getRowKey(row, i)} className="flex flex-col gap-2 rule bg-surface p-4">
            {columns.map((c) => (
              <div key={c.key} className="flex flex-wrap items-baseline justify-between gap-2">
                {/* ink-2, not ink-3: this label sits on the glass-panel card
                    (a --surface-2 tint), where --ink-3 fails AA contrast. */}
                <span className="text-2xs font-bold uppercase tracking-wide text-ink-2">
                  {c.cardLabel ?? c.header}
                </span>
                <span className="text-xs text-ink">{c.cell(row, i)}</span>
              </div>
            ))}
          </li>
        ))}
      </ul>
    </div>
  );
}
