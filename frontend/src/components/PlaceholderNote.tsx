import { useTranslation } from 'react-i18next';

/** Maps API placeholder flag strings to a human-readable sentence.
 *
 *  Kept in one place so PLACEHOLDER_PENDING_MARINE_SCIENTIST reads identically
 *  on /reef-zones, /reef-zones/:id, and /limitations — a second copy diverging
 *  under edit is exactly the failure the design system catches. */

const FLAG_MAP: Record<string, string> = {
  PLACEHOLDER_PENDING_MARINE_SCIENTIST: 'placeholder.sensitivity',
};

export function PlaceholderNote({ flag }: { flag: string }) {
  const { t } = useTranslation('tools');

  // Check if the flag starts with "PLACEHOLDER" (e.g. "PLACEHOLDER 0.6 -- ...")
  const isPlaceholder = flag.startsWith('PLACEHOLDER');
  const key = FLAG_MAP[flag] ?? (isPlaceholder ? 'placeholder.generic' : null);

  if (!key) return null;

  return (
    <p
      className="m-0 flex items-start gap-1.5 text-2xs text-ink-2"
      data-placeholder-note={flag}
    >
      <span className="mt-px inline-block h-3 w-3 shrink-0 border border-risk-high-stroke" aria-hidden />
      <span>{t(key, { flag, defaultValue: flag })}</span>
    </p>
  );
}
