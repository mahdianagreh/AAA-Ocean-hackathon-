import { useTranslation } from 'react-i18next';
import type { ForecastAnomaly } from '../api/live';

/** b6 — Live Anomaly Detection. Deliberately NOT shaped like `ConfidenceMeter`
 *  (no meter bar, no `bg-accent` fill) — the backend's own `anomaly_caveat`
 *  string says this must render as a visually distinct element, never
 *  conflated with the Confidence Meter (p4-05): different inputs, different
 *  claim. Shape follows `States.tsx`'s `ErrorState` (bordered card, coloured
 *  border + text) rather than a hazard-band tag, and reuses `risk-high` rather
 *  than `risk-critical` — this is an early statistical signal, not an error
 *  and not a validated risk level.
 *
 *  Percentile-relative, not a z-score (`catchment_rainfall_climatology` only
 *  has percentiles) — labelled as such, not presented as more precise than it is.
 */
export function AnomalyBanner({
  anomalies,
  caveat,
}: {
  anomalies: ForecastAnomaly[];
  caveat: string;
}) {
  const { t } = useTranslation();
  const flagged = anomalies.filter((a) => a.is_anomalous);

  return (
    <section className="flex flex-col gap-2" data-anomaly-banner="true">
      <h2 className="border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
        {t('forecast.anomalyTitle')}
      </h2>

      {flagged.length > 0 ? (
        <div
          role="status"
          className="flex flex-col gap-1 rounded-card border border-risk-high-stroke bg-surface p-3"
        >
          <p className="text-xs font-semibold text-risk-high">
            {t('forecast.anomalyDetected', { count: flagged.length })}
          </p>
          <ul className="flex flex-col gap-0.5">
            {flagged.map((a) => (
              <li key={`${a.catchment_id}-${a.window_hours}`} className="text-2xs text-ink-2">
                <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">
                  {a.catchment_id}
                </span>{' '}
                — {t(`forecast.percentileBand.${a.percentile_band}`, {
                  defaultValue: a.percentile_band,
                })}
              </li>
            ))}
          </ul>
          <Sparkline anomalies={anomalies} />
        </div>
      ) : (
        // The detector working and finding nothing is a real, positive result —
        // must not look like a broken/empty component.
        <p className="text-2xs text-ink-3" data-anomaly-quiet="true">
          {t('forecast.anomalyQuiet')}
        </p>
      )}

      {/* Rendered verbatim, per this feature's own rule — not paraphrased. */}
      <p className="text-2xs text-ink-3">{caveat}</p>
    </section>
  );
}

/** Rolling forecast stream, anomalous points marked by `anomaly_score`. Inline
 *  SVG — no new charting dependency for one small sparkline. */
function Sparkline({ anomalies }: { anomalies: ForecastAnomaly[] }) {
  const { t } = useTranslation();
  if (anomalies.length === 0) return null;

  const width = 240;
  const height = 32;
  const maxScore = Math.max(1, ...anomalies.map((a) => a.anomaly_score));
  const step = anomalies.length > 1 ? width / (anomalies.length - 1) : 0;
  const points = anomalies.map((a, i) => {
    const x = i * step;
    const y = height - (Math.min(a.anomaly_score, maxScore) / maxScore) * height;
    return { x, y, anomalous: a.is_anomalous };
  });
  const path = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="h-8 w-full"
      role="img"
      aria-label={t('forecast.sparklineLabel')}
    >
      <path d={path} fill="none" className="stroke-ink-3" strokeWidth={1} />
      {points
        .filter((p) => p.anomalous)
        .map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={2.5} className="fill-risk-high" />
        ))}
    </svg>
  );
}
