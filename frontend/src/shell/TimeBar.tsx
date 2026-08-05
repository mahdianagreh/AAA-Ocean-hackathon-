import { useTranslation } from 'react-i18next';
import { TimeSlider } from '../components/TimeSlider';
import { useUi } from '../app/uiStore';
import type { EventData } from '../app/useEventData';

/** Time bar: full width beneath the map, drives every time-varying layer — 03 §3.
 *
 *  It also has to admit what the axis is. The steps are DAILY, because there is no
 *  sub-daily series in the repo — while the event's own peak was a three-hour
 *  window. 09 rule 8 says never claim exactness, and a slider stepping in days
 *  over an event that happened in hours has to say so on screen rather than let
 *  the interval imply a resolution we do not have.
 */
export function TimeBar({ data }: { data: EventData | null }) {
  const { t } = useTranslation();
  const cursor = useUi((s) => s.cursor);
  const setCursor = useUi((s) => s.setCursor);

  const marks = data
    ? data.series.mooring.markers.map((m) => ({
        t: m.t,
        key: m.key,
        label: t(`mooring.${m.key}`),
      }))
    : [];

  const w3 = data?.series.subdaily.wettest_3h_window_utc;

  return (
    <footer
      className="flex flex-col gap-1 border-t border-hairline bg-surface px-4 py-2"
      aria-label={t('time.label')}
    >
      <div className="flex items-center gap-4">
        {data ? (
          <TimeSlider steps={data.steps} value={cursor} onChange={setCursor} marks={marks} />
        ) : (
          <p className="flex-1 text-2xs text-ink-3">{t('rail.loading')}</p>
        )}
      </div>

      <div className="flex flex-wrap items-baseline justify-between gap-3 text-2xs text-ink-3">
        {/* The resolution caveat, stated where the control is. */}
        <span>
          {t('time.dailyOnly')}
          {w3?.max_rain_3h_mm != null ? (
            <>
              {' '}
              {t('time.wettest3h', {
                mm: w3.max_rain_3h_mm.toFixed(2),
                start: w3.start.replace('T', ' ').replace('Z', ''),
              })}
            </>
          ) : null}
        </span>
        <span>{t('time.attribution')}</span>
      </div>
    </footer>
  );
}
