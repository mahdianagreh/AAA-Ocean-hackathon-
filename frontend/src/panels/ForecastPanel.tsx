import { useTranslation } from 'react-i18next';
import { useForecastLatest } from '../app/useForecastLatest';
import { Row } from '../shell/SideRail';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { AnomalyBanner } from '../components/AnomalyBanner';
import { CurrentsAgreementCard } from '../components/CurrentsAgreementCard';
import { Countdown } from '../components/Countdown';

/** Forecast mode's real content — p4-02, p4-03, b6, p4-F together, since all
 *  four are "what does the live-cached forecast actually say right now."
 *
 *  Decision recorded 2026-08-09 (tasks/phase7/03-nizar.md): option (b),
 *  forecast-only. `ExposureRequest` has no rainfall field today, and wiring
 *  one in touches Pulga's exposure engine — real work, not something to do
 *  unilaterally days before a demo. This panel shows exactly what
 *  `/api/v1/forecast/latest` has (per-catchment rain, wind, real GEFS
 *  exceedance, the anomaly signal) and says plainly that it does not yet
 *  produce a reef exposure score — never silently reusing the historical
 *  training-row path while looking live.
 */
export function ForecastPanel({ active }: { active: boolean }) {
  const { t } = useTranslation();
  const { forecast, currents, loading } = useForecastLatest(active);

  if (!active) return null;

  if (loading && !forecast) {
    return <p className="text-xs text-ink-3">{t('rail.loading')}</p>;
  }

  if (!forecast) {
    return <p className="text-xs text-ink-3">{t('forecast.unreachable')}</p>;
  }

  const nearTerm = forecast.catchment_rainfall.filter((r) => r.lead_hours === 3);

  return (
    <>
      {/* "Cached, not live" stated, never implied — same discipline as the
          backend's own docstring. issued_at is one timestamp per model. */}
      <section className="flex flex-col gap-1">
        <h2 className="border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
          {t('forecast.title')}
        </h2>
        {Object.entries(forecast.issued_at).map(([model, ts]) => (
          <Row key={model} label={t(`forecast.model.${model}`, { defaultValue: model })}>
            <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num text-2xs">
              {new Date(ts).toISOString().replace('T', ' ').slice(0, 16)} UTC
            </span>
          </Row>
        ))}
        <p className="text-2xs text-ink-3">{t('forecast.noScoreYet')}</p>
      </section>

      <section className="flex flex-col gap-1">
        <h2 className="border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
          {t('forecast.rainfall')}
        </h2>
        {nearTerm.map((r) => {
          const exceed = forecast.exceedance.find((e) => e.catchment_id === r.catchment_id);
          return (
            <Row key={r.catchment_id} label={r.catchment_id}>
              <span className="flex items-baseline gap-2">
                <ValueWithUnit value={r.rain_mm} unit="mm/3h" digits={2} provenance="modelled" />
                {exceed ? (
                  <span className="text-2xs text-ink-3">
                    {t('forecast.exceedance', {
                      n: exceed.members_exceeding,
                      total: exceed.members_total,
                    })}
                  </span>
                ) : null}
              </span>
            </Row>
          );
        })}
      </section>

      {/* p4-03: no live exposure run exists in Forecast mode by this same
          decision, so there is no real arrival window here — this is exactly
          the honest-absence case the countdown is built to handle, not a bug. */}
      <section className="flex flex-col gap-1">
        <h2 className="border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
          {t('countdown.title')}
        </h2>
        <Countdown arrivalWindowHours={null} referenceTimeIso={null} />
      </section>

      <AnomalyBanner anomalies={forecast.anomalies} caveat={forecast.anomaly_caveat} />

      <CurrentsAgreementCard data={currents} />
    </>
  );
}
