import { useTranslation } from 'react-i18next';
import { bandForScore, BAND_CLASS, type HazardBand } from '../api/types';
import type { SeasonalCalendar as SeasonalCalendarData } from '../api/live';
import { Link } from './Link';
import { ValueWithUnit } from './ValueWithUnit';

/** The twelve-month seasonal calendar, at /events.
 *
 *  FRAMING, STATED ON SCREEN, NOT JUST HERE: these cells rank calendar months by
 *  RAINFALL INTENSITY, not reef exposure. The sediment model is anchored to one
 *  October event, so an exposure-scored calendar would read flat everywhere but
 *  October and misrepresent the seasonality the rainfall record actually shows
 *  (scripts/29_seasonal_risk_calendar.py's framing note). Mislabelling this as
 *  reef risk is a claim the system cannot support, so the caption says what it is.
 *
 *  The hazard ramp is used here for its one honest job — a monotonic,
 *  greyscale-safe intensity encoding — over each month's peak daily depth relative
 *  to the wettest month. It is never colour alone: every cell prints its peak
 *  depth and storm count, which are the load-bearing figures; the fill only orders
 *  them at a glance. Months with no storms in the record render as a neutral gap,
 *  never as band `minimal`, which would imply a measured-low reading.
 */
export function SeasonalCalendar({ data }: { data: SeasonalCalendarData }) {
  const { t, i18n } = useTranslation('pages');
  const locale = i18n.language.startsWith('ar') ? 'ar-JO-u-nu-latn' : 'en-GB';
  const monthName = (m: number) =>
    new Intl.DateTimeFormat(locale, { month: 'long', timeZone: 'UTC' }).format(
      new Date(Date.UTC(2020, m - 1, 1)),
    );

  // One shared scale: each month's peak depth against the wettest month, so the
  // ramp orders months relative to one another rather than to an absolute score.
  const peak = Math.max(1e-6, ...data.months.map((m) => m.max_daily_mm ?? 0));

  return (
    <div className="flex flex-col gap-3" data-seasonal-calendar="true">
      <p className="m-0 max-w-prose text-2xs text-ink-2">{t('events.calendar.framingNote')}</p>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {data.months.map((m) => {
          const has = m.event_count > 0 && m.max_daily_mm !== null;
          const rel = has ? ((m.max_daily_mm as number) / peak) * 100 : 0;
          const band = has ? bandForScore(rel) : null;
          // Numbers sit on the neutral surface so they stay legible and AA-safe;
          // the hazard colour rides an intensity meter, where length AND hue both
          // carry the reading and no value is ever set against a coloured ground.
          const cell = (
            <div
              className="flex h-full flex-col gap-1.5 border border-hairline bg-surface p-3"
              style={{ borderRadius: 'var(--radius-md)' }}
              data-month={m.month}
              data-band={band ?? 'none'}
            >
              <span className="text-xs font-semibold text-ink">{monthName(m.month)}</span>
              {has ? (
                <>
                  <ValueWithUnit
                    value={m.max_daily_mm}
                    unit={t('units.mmPerDay')}
                    digits={1}
                    provenance="measured"
                    className="text-sm font-bold"
                  />
                  <div
                    className="h-1.5 w-full overflow-hidden bg-surface-2"
                    style={{ borderRadius: 'var(--radius-hairline)' }}
                    aria-hidden="true"
                  >
                    <span
                      className={`block h-full border ${BAND_CLASS[band as HazardBand]}`}
                      style={{ inlineSize: `${Math.max(4, rel)}%`, borderRadius: 'var(--radius-hairline)' }}
                    />
                  </div>
                  <span className="text-2xs text-ink-2">
                    {t('events.calendar.storms', { n: m.event_count })}
                  </span>
                </>
              ) : (
                <span className="text-2xs text-ink-2">{t('events.calendar.noEvents')}</span>
              )}
            </div>
          );

          // The heaviest storm of the month is the natural deep-link, matching the
          // catalogue's row links. Only where one exists.
          return m.worst_event_id ? (
            <Link
              key={m.month}
              to={`/dashboard/replay/${encodeURIComponent(m.worst_event_id)}`}
              title={t('events.calendar.worstLink', { id: m.worst_event_id })}
              className="block no-underline"
            >
              {cell}
            </Link>
          ) : (
            <div key={m.month}>{cell}</div>
          );
        })}
      </div>

      <p className="m-0 text-2xs text-ink-3">
        {data.provenance === 'snapshot'
          ? t('events.calendar.snapshotNote')
          : t('events.calendar.liveNote')}
      </p>
    </div>
  );
}
