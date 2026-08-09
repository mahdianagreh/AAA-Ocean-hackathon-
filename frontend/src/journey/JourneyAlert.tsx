import { useTranslation } from 'react-i18next';

/** The runoff warning that "pops in" ahead of the rain phase, driven by the
 *  same real numbers the phase body text already quotes -- not a second,
 *  invented signal. This is a historical replay, not a live forecast, so the
 *  copy says "recorded", never "predicted" or "forecast" (CLAUDE.md's label
 *  rule extends to language, not just data: this project has a documented
 *  runoff *classifier*, but nothing here re-runs it — the warning is built
 *  from the same measured rainfall the Hyetograph panel shows).
 *
 *  The comparison point is each catchment's own real 99th-percentile day
 *  (`rainfall_p99_by_catchment`, `catchment_rainfall_climatology.parquet` --
 *  the same file `rain_over_p99`, one of the trained runoff model's real
 *  features, is built from) — a real, defensible "this was unusual for this
 *  specific catchment" statement, not a bare mm figure with no context.
 */

export interface JourneyAlertCatchment {
  catchmentId: string;
  peakMm: number;
  p99Mm: number | null;
}

export function JourneyAlert({
  catchments,
  dateUtc,
  onDismiss,
}: {
  catchments: JourneyAlertCatchment[];
  dateUtc: string | null;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  if (catchments.length === 0) return null;

  const ratio = (c: JourneyAlertCatchment) => (c.p99Mm && c.p99Mm > 0 ? c.peakMm / c.p99Mm : null);
  const worst = catchments.reduce((a, b) => ((ratio(b) ?? 0) > (ratio(a) ?? 0) ? b : a));
  const worstRatio = ratio(worst);

  return (
    <div
      role="alert"
      data-journey-alert="true"
      className="relative col-start-1 row-start-1 m-3 w-[min(92%,34rem)] self-start justify-self-center
                 rounded-card border border-risk-high-stroke bg-surface p-3 shadow-lg"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold text-risk-high">{t('journey.alert.title')}</p>
        <button
          type="button"
          onClick={onDismiss}
          data-journey-alert-dismiss="true"
          className="text-2xs text-ink-3 hover:text-ink"
        >
          {t('journey.alert.dismiss')}
        </button>
      </div>
      <p className="mt-1 text-2xs text-ink-2">
        {t('journey.alert.body', {
          count: catchments.length,
          date: dateUtc?.slice(0, 10) ?? '',
          ratio: worstRatio ? worstRatio.toFixed(1) : '—',
          worstId: worst.catchmentId,
        })}
      </p>
      <ul className="mt-1.5 flex flex-col gap-0.5">
        {catchments.map((c) => {
          const r = ratio(c);
          return (
            <li key={c.catchmentId} className="text-2xs text-ink-3">
              <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num text-ink-2">
                {c.catchmentId}
              </span>
              {' — '}
              {t('journey.alert.catchmentLine', {
                mm: c.peakMm.toFixed(1),
                ratio: r ? r.toFixed(1) : '—',
              })}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
