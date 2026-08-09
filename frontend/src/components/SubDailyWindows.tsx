import { useTranslation } from 'react-i18next';
import type { EventSeries } from '../api/event';
import { ValueWithUnit } from './ValueWithUnit';

/** Peak sub-daily accumulation windows, beneath the daily hyetograph.
 *
 *  p4-16 asked for rolling 1/3/6/24h rainfall. There is no such SERIES in the
 *  repo — `rain_1h/3h/6h/24h_mm` are all-null in event_catchment_features.parquet,
 *  a real join that was never built. What DOES exist is four scalar extrema: the
 *  heaviest 1h/3h/6h/24h totals seen anywhere in the Aqaba grid during the storm.
 *
 *  So this shows those four, honestly, and says exactly what they are: maxima over
 *  the AOI grid cells, NOT the catchment daily mean plotted above, and NOT a
 *  rolling accumulation. The gap is not filled with the daily value — that is the
 *  one thing the task rules out, because the peak 3h (11.7 mm) exceeds the peak
 *  daily mean (10.2 mm) and pasting the daily figure in here would erase a real,
 *  informative difference between a cell peak and a spatial average. Provenance is
 *  modelled (derived from IMERG, not reported by the paper), rendered as the dashed
 *  rule ValueWithUnit draws for a modelled number.
 */
const WINDOWS: Array<{ key: string; hours: number }> = [
  { key: 'rain_1h_mm', hours: 1 },
  { key: 'rain_3h_mm', hours: 3 },
  { key: 'rain_6h_mm', hours: 6 },
  { key: 'rain_24h_mm', hours: 24 },
];

export function SubDailyWindows({ subdaily }: { subdaily: EventSeries['subdaily'] }) {
  const { t } = useTranslation();
  const windows = subdaily.wettest_windows ?? {};

  return (
    <section className="flex flex-col gap-3 glass-card p-3 hover:glass-card-hover transition-all duration-300 group" data-subdaily-windows="true">
      <h3 className="border-b border-hairline-2 pb-1 text-sm font-bold premium-gradient-text">
        {t('subdaily.title')}
      </h3>

      {/* Four stat tiles, LTR so the windows read in order in both languages — a
          bar of extrema, deliberately not a time series. */}
      <div dir="ltr" className="grid grid-cols-4 gap-1.5">
        {WINDOWS.map(({ key, hours }) => (
          <div
            key={key}
            className="flex flex-col gap-0.5 border border-hairline-2 px-2 py-2 text-center transition-all duration-300 hover:scale-105 hover:neon-glow hover:border-accent bg-surface/50"
            style={{ borderRadius: 'var(--radius-md)' }}
          >
            <span className="font-mono num text-2xs font-medium text-ink-2">
              {t('subdaily.window', { h: hours })}
            </span>
            <ValueWithUnit
              value={windows[key] ?? null}
              unit={t('units.mm')}
              digits={1}
              provenance="modelled"
              className="text-xs font-semibold"
            />
          </div>
        ))}
      </div>

      {/* The claim that must stay visible; the full derivation is on hover. */}
      <p className="m-0 max-w-prose text-2xs text-ink-3" title={t('subdaily.caveat')}>
        {t('subdaily.caveatShort')}
      </p>
    </section>
  );
}
