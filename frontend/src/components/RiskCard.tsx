import { useTranslation } from 'react-i18next';
import type { HazardBand } from '../api/types';
import { BAND_CLASS, HAZARD_RANGES } from '../api/types';
import { ValueWithUnit } from './ValueWithUnit';
import { ConfidenceMeter, type ConfidenceComponents } from './ConfidenceMeter';
import { DriverBars, type Driver } from './DriverBars';

export interface RiskCardData {
  catchment_id: string;
  name: string | null;
  band: HazardBand;
  score: number;
  runoff_probability: number | null;
  /** Always null on every current path — the registered model is a classifier,
   *  not a volume regressor. Rendered as a stated gap rather than left off the
   *  card, so absence reads as "not modelled" rather than "forgotten". */
  predicted_runoff_m3: number | null;
  /** The catchment's own area, always shown.
   *
   *  Not a driver. It reached the screen only as a stand-in driver until a real
   *  model was registered, and the model's top-4 SHAP attributions do not rank
   *  `area_km2` on these rows — so the number silently left the rail, and the map
   *  polygon became the only path to it. 09 rule 7 says the map is never the only
   *  path to a fact, so this is a field of the card, not an accident of ranking. */
  area_km2: number;
  drivers: Driver[];
  confidence: ConfidenceComponents;
  /** The caveat travels with the card, not in a footer someone can forget. */
  caveat?: string;
  /** True when the numbers are a stand-in rather than model output. 01 §6.6:
   *  provisional data is labelled in the UI, not only in the repo. */
  provisional?: boolean;
  /** Set when these numbers came from a registered artefact. Shown on the card,
   *  because "which model said this" is the first thing anyone asks of a prediction
   *  — and it is what makes a stored prediction reproducible at all. */
  modelVersion?: string;
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
    <article className="flex flex-col gap-3 glass-card p-4 hover:glass-card-hover group" data-risk-card={data.catchment_id}>
      <header className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col justify-center">
          <span
            dir="ltr"
            style={{ unicodeBidi: 'isolate' }}
            className="font-mono num text-2xs font-bold text-accent group-hover:neon-glow transition-all"
          >
            {data.catchment_id}
          </span>
          <span dir="auto" style={{ unicodeBidi: 'isolate' }} className="truncate text-md font-bold text-ink">
            {data.name ?? t('rail.unnamed')}
          </span>
        </div>

        {/* The band leads: the largest, highest-contrast thing on the card. Every
            hazard fill carries a 1px stroke at the next band up, because `minimal`
            measures 1.29 against canvas and a fill alone is not a boundary. */}
        <div
          data-band={data.band}
          className={`flex shrink-0 flex-col items-end border px-3 py-1.5 transition-transform duration-300 group-hover:scale-105 ${BAND_CLASS[data.band]} ${data.band === 'high' || data.band === 'critical' ? 'shadow-[0_0_15px_var(--risk-critical)]' : ''}`}
          style={{ borderRadius: 'var(--radius-md)' }}
        >
          <span className="text-sm font-bold uppercase tracking-wider">{t(`hazard.${data.band}`)}</span>
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
            {/* A registered model fills this. null renders as a gap, which is the
                honest state on the one path that has no probability to report:
                what-if mode cannot re-run the model in the browser. */}
            <ValueWithUnit value={data.runoff_probability} digits={3} provenance="modelled" />
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-2">
          <dt className="text-ink-2">{t('rail.area')}</dt>
          <dd>
            {/* modelled, not measured: this is a DEM watershed delineation, and the
                same 4,453 km² that carries 96% of the discharge. */}
            <ValueWithUnit value={data.area_km2} unit="km²" digits={2} provenance="modelled" />
          </dd>
        </div>
        <div className="flex items-baseline justify-between gap-2">
          <dt className="text-ink-2">{t('risk.predictedVolume')}</dt>
          <dd>
            {/* Always null: core-A, "predicted_runoff_m3 is deliberately null
                (classifier, not regressor). Render the gap; do not compute a
                substitute." A gap here says the model was asked and had no
                volume to give — never absent, which would read as never asked. */}
            <ValueWithUnit value={data.predicted_runoff_m3} unit="m³" digits={0} provenance="modelled" />
          </dd>
        </div>
      </dl>

      {data.predicted_runoff_m3 === null ? (
        <p className="text-2xs text-ink-3">{t('risk.predictedVolumeCaveat')}</p>
      ) : null}

      <DriverBars drivers={data.drivers} />
      <ConfidenceMeter c={data.confidence} />

      {data.caveat ? (
        <p className="border-t border-hairline pt-2 text-2xs text-ink-3">{data.caveat}</p>
      ) : null}

      {data.modelVersion ? (
        <p className="flex flex-wrap items-baseline gap-1.5 border-t border-hairline pt-2 text-2xs text-ink-3">
          {t('risk.modelledBy')}
          <code
            dir="ltr"
            style={{ unicodeBidi: 'isolate' }}
            className="font-mono num text-ink-2"
          >
            {data.modelVersion}
          </code>
        </p>
      ) : null}

      {data.provisional ? (
        // A coloured MARKER plus ink text, not coloured text. The hazard ramp is a
        // fill scale with a paired --risk-*-on token; #d67229 as ink on --surface
        // measures 3.33 and fails AA at this size. axe caught it on every card.
        // 01 §4 also prefers form over hue, and a marker is form.
        <p className="flex items-start gap-1.5 text-2xs text-ink-2">
          <span
            aria-hidden="true"
            className="mt-0.5 block h-2 w-2 shrink-0 border border-risk-high-stroke bg-risk-high"
          />
          {t('risk.provisional')}
        </p>
      ) : null}
    </article>
  );
}
