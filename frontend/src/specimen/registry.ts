import type { ReactNode } from 'react';

/** One registration puts a primitive on all four specimen panes.
 *
 *  04-component-inventory.md: "Every component lands on /specimen the day it is
 *  written." Making that one function call rather than four edits is the only
 *  reason it will actually happen — a process that costs four edits gets skipped
 *  on the day it matters.
 */
export interface SpecimenEntry {
  /** Stable id, used in the DOM so Playwright can target a single section. */
  id: string;
  /** i18n key for the section heading. Never a literal — the specimen renders
   *  in Arabic too, and an English-only gallery cannot check Arabic. */
  titleKey: string;
  /** Optional i18n key for a note under the heading. */
  noteKey?: string;
  render: () => ReactNode;
}

const entries: SpecimenEntry[] = [];

export function registerSpecimen(entry: SpecimenEntry): void {
  if (entries.some((e) => e.id === entry.id)) return;
  entries.push(entry);
}

export function specimenEntries(): readonly SpecimenEntry[] {
  return entries;
}
