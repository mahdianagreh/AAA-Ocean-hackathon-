import { useTranslation } from 'react-i18next';
import type { Value } from '../api/types';
import { ValueWithUnit } from './ValueWithUnit';

/** Signed SHAP contributions — 07 §4, Day-1 ask #5.
 *
 *  `key` is a stable i18n key, translated here. A human-readable English label
 *  from the API cannot become Arabic on screen, which is why the ask exists.
 *  `runoff_model.py` currently returns `{feature, shap, value}` with `feature` as
 *  a raw parquet column name — usable as a key by convention, but the rename and
 *  the `Value` wrapper are still owed. See OPEN-ISSUES.md item 3.
 *
 *  Diverging by *direction*, not by hue pair: a contribution that raises risk and
 *  one that lowers it point opposite ways from a shared centre line. Colour would
 *  need a second data hue this design system does not have, and direction survives
 *  greyscale and colour-blindness the way the provenance forms do.
 */
export interface Driver {
  key: string;
  /** Signed. Positive raises the predicted risk. */
  contribution: number;
  value: Value;
}

export function DriverBars({ drivers }: { drivers: Driver[] }) {
  const { t } = useTranslation();
  if (!drivers.length) return null;

  const max = Math.max(...drivers.map((d) => Math.abs(d.contribution)), 1e-6);

  return (
    <div className="flex flex-col gap-1" data-drivers="true">
      <h4 className="text-xs text-ink-2">{t('risk.drivers')}</h4>

      <ul className="flex flex-col gap-1">
        {drivers.map((d) => {
          const w = (Math.abs(d.contribution) / max) * 50; // half-width each side
          const positive = d.contribution >= 0;
          return (
            <li key={d.key} className="flex items-center gap-2 text-2xs">
              <span
                dir="auto"
                // w-36, because "Transmission loss (unmodelled)" truncated at w-28
                // and the parenthetical is the part that matters — a reader who
                // sees "Transmission loss (u…" learns nothing.
                className="w-36 shrink-0 truncate text-ink-2"
                title={t(`driver.${d.key}`)}
              >
                {t(`driver.${d.key}`)}
              </span>

              {/* The diverging axis is pinned LTR and genuinely does not mirror.
                  A bar extending right always means "raises risk"; mirroring it
                  with reading direction would invert what the chart says without
                  changing a single number. This is the same category as the chart
                  time axis in 06 §3 — physical on purpose. */}
              <span dir="ltr" className="relative h-3 min-w-0 flex-1 bg-surface-2">
                {/* rtl-ok: diverging centre line — the axis must not mirror, or a positive contribution would point the wrong way (06 §3, chart axes) */}
                <span aria-hidden="true" className="absolute inset-y-0 left-1/2 w-px bg-hairline-2" />
                <span
                  className={positive ? 'absolute inset-y-0.5 bg-ink-2' : 'absolute inset-y-0.5 bg-ink-3'}
                  // rtl-ok: same diverging axis — positive grows right, negative left, in both languages
                  style={positive ? { left: '50%', width: `${w}%` } : { right: '50%', width: `${w}%` }}
                  title={`${positive ? '+' : ''}${d.contribution.toFixed(3)}`}
                />
              </span>

              <span className="w-20 shrink-0 text-end">
                <ValueWithUnit
                  value={d.value.value}
                  unit={d.value.unit}
                  digits={2}
                  provenance={d.value.provenance}
                />
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
