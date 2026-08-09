import { useTranslation } from 'react-i18next';
import type { CurrentsAgreement } from '../api/live';
import { ValueWithUnit } from './ValueWithUnit';

/** p4-F — Multi-Source Weather Agreement, the currents reading. Shows the
 *  real HYCOM-vs-Copernicus-Marine disagreement for the demo event, not the
 *  foundation deck's placeholder "three green dots, all agree" — the honest
 *  number here is 65.82 degrees of disagreement, which is more informative
 *  than a reassuring tick. `null` (cache aged out, or the fix's new 503 guard
 *  fired) renders "not available", never 0 or a fabricated fallback.
 */
export function CurrentsAgreementCard({ data }: { data: CurrentsAgreement | null }) {
  const { t } = useTranslation();

  return (
    <section className="flex flex-col gap-1" data-currents-agreement="true">
      <h2 className="border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
        {t('forecast.currentsTitle')}
      </h2>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-ink-2">{t('forecast.currentsDisagreement')}</span>
        <ValueWithUnit value={data?.direction_diff_deg ?? null} unit="°" digits={1} />
      </div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-ink-2">{t('forecast.currentsAgreementScore')}</span>
        <ValueWithUnit value={data?.agreement ?? null} digits={2} />
      </div>
      {data?.caveats.map((c, i) => (
        <p key={i} className="text-2xs text-ink-3">
          {c.message}
        </p>
      ))}
      {!data ? <p className="text-2xs text-ink-3">{t('forecast.currentsUnavailable')}</p> : null}
    </section>
  );
}
