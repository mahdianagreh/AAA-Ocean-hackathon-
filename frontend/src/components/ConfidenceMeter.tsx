import { useTranslation } from 'react-i18next';
import type { Value } from '../api/types';
import { ValueWithUnit } from './ValueWithUnit';

/** Components, never a pre-formatted sentence — 07 §4, Day-1 ask #6.
 *
 *  The API is asked for `{members_exceeding, members_total, threshold_label,
 *  threshold_value}` so the UI can compose "22 of 30 members exceed…" in the
 *  active language. A formatted English string cannot be translated at render
 *  time, and what the model layer currently returns (`confidence_terms`, with
 *  `catchment_ap` sometimes an English string like "0.412 (mean - AQ-C06 not in
 *  LOCO folds)") is untranslatable as-is. See OPEN-ISSUES.md item 4.
 *
 *  This is also the one figure the UI is allowed to call a probability. Unlike the
 *  plume's relative-density levels, an ensemble exceedance fraction genuinely is
 *  one — 07 §4 says so explicitly.
 */
export interface ConfidenceComponents {
  members_exceeding: number;
  members_total: number;
  /** i18n key, not prose, for the same reason the drivers use keys. */
  threshold_key: string;
  threshold_value: Value;
}

export function ConfidenceMeter({ c }: { c: ConfidenceComponents }) {
  const { t } = useTranslation();
  const pct = c.members_total > 0 ? (c.members_exceeding / c.members_total) * 100 : 0;

  return (
    <div className="flex flex-col gap-1" data-confidence="true">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="text-ink-2">{t('risk.confidenceLabel')}</span>
        {/* Composed here, in the active language, from the parts. */}
        <span className="text-end">
          {t('risk.confidence', {
            n: c.members_exceeding,
            total: c.members_total,
            threshold: t(c.threshold_key),
          })}
        </span>
      </div>

      {/* A meter, with a real ARIA role rather than a styled div. Its fill
          direction follows reading direction — 06 §3 lists progress fill under
          "mirrors", unlike the time axis. */}
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={c.members_total}
        aria-valuenow={c.members_exceeding}
        aria-label={t('risk.confidenceLabel')}
        className="h-1 w-full bg-surface-2"
      >
        <div className="h-full bg-accent" style={{ inlineSize: `${pct}%` }} />
      </div>

      <p className="text-2xs text-ink-3">
        {t(c.threshold_key)}: <ValueWithUnit
          value={c.threshold_value.value}
          unit={c.threshold_value.unit}
          digits={2}
          provenance={c.threshold_value.provenance}
        />
      </p>
    </div>
  );
}
