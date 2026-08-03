import { useTranslation } from 'react-i18next';
import type { HazardBand } from '../api/types';
import { HAZARD_RANGES } from '../api/types';
import { ValueWithUnit } from './ValueWithUnit';
import { ConfidenceMeter, type ConfidenceComponents } from './ConfidenceMeter';
import { DriverBars, type Driver } from './DriverBars';

/** Literal class names, never `bg-risk-${band}`.
 *
 *  Tailwind scans source statically, so an interpolated class is not a string in
 *  the file and the utility is never generated. That bug shipped once already in
 *  the Phase 0 specimen: the strokes rendered because they were inline styles, and
 *  every fill silently fell back to the canvas. It read as a washed-out ramp
 *  rather than a missing one, which is why it survived a passing test suite. */
const BAND_CLASS: Record<HazardBand, string> = {
  minimal: 'bg-risk-minimal text-risk-minimal-on border-risk-minimal-stroke',
  low: 'bg-risk-low text-risk-low-on border-risk-low-stroke',
  moderate: 'bg-risk-moderate text-risk-moderate-on border-risk-moderate-stroke',
  high: 'bg-risk-high text-risk-high-on border-risk-high-stroke',
  critical: 'bg-risk-critical text-risk-critical-on border-risk-critical-stroke',
};

export interface RiskCardData {
  catchment_id: string;
  name: string | null;
  band: HazardBand;
  score: number;
  runoff_probability: number | null;
  drivers: Driver[];
  confidence: ConfidenceComponents;
  /** The caveat travels with the card, not in a footer someone can forget. */
  caveat?: string;
  /** True when the numbers are a stand-in rather than model output. 01 §6.6:
   *  provisional data is labelled in the UI, not only in the repo. */
  provisional?: boolean;
}

/** The risk card — scenes 3 and 8.
 *
 *  One focal element: the band, which is the decision. Everything else is
 *  demoted, because the officer's question is "do I send someone to this
 *  catchment", and the score, the drivers and the confidence are all support for
 *  that one answer.
 */
export function RiskCard({ data }: { data: RiskCardData }) {
  const { t } = useTranslation();

  return (
    <article className="flex flex-col gap-3 rule bg-surface p-3" data-risk-card={data.catchment_id}>
      <header className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col">
          <span
            dir="ltr"
            style={{ unicodeBidi: 'isolate' }}
            className="font-mono num text-2xs text-ink-3"
          >
            {data.catchment_id}
          </span>
          <span dir="auto" style={{ unicodeBidi: 'isolate' }} className="truncate text-sm">
            {data.name ?? t('rail.unnamed')}
          </span>
        </div>

        {/* The band leads: the largest, highest-contrast thing on the card. Every
            hazard fill carries a 1px stroke at the next band up, because `minimal`
            measures 1.29 against canvas and a fill alone is not a boundary. */}
        <div
          data-band={data.band}
          className={`flex shrink-0 flex-col items-end border px-2 py-1 ${BAND_CLASS[data.band]}`}
        >
          <span className="text-sm font-semibold">{t(`hazard.${data.band}`)}</span>
          <span
            dir="ltr"
            style={{ unicodeBidi: 'isolate' }}
            className="font-mono num text-2xs"
          >
            {HAZARD_RANGES[data.band]}
          </span>
        </div>
      </header>

      <dl className="flex flex-col gap-1 text-xs">
        <div className="flex items-baseline justify-between gap-2">
          <dt className="text-ink-2">{t('risk.score')}</dt>
          <dd>
            <ValueWithUnit value={data.score} digits={0} provenance="modelled" />
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-2">
          <dt className="text-ink-2">{t('risk.runoffProbability')}</dt>
          <dd>
            {/* null renders as a gap, which is the honest state while the model
                endpoint answers 503. */}
            <ValueWithUnit value={data.runoff_probability} digits={3} provenance="modelled" />
          </dd>
        </div>
      </dl>

      <DriverBars drivers={data.drivers} />
      <ConfidenceMeter c={data.confidence} />

      {data.caveat ? (
        <p className="border-t border-hairline pt-2 text-2xs text-ink-3">{data.caveat}</p>
      ) : null}

      {data.provisional ? (
        <p className="text-2xs text-risk-high">{t('risk.provisional')}</p>
      ) : null}
    </article>
  );
}
