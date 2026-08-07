import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { loadValidation, type Validation } from '../api/panels';
import { ValueWithUnit } from '../components/ValueWithUnit';

/** Scene 6. Modelled versus measured — and the satellite null result as a finding.
 *
 *  The concept doc's Scene 6 says "reveal the actual post-event satellite plume."
 *  That is superseded, and this panel exists to say why rather than quietly drop
 *  it: the project's own audit returns a pixel-level NO-GO because the plume
 *  dispersed 2.5–3.5 days before any accessible pass, confirmed independently by
 *  Sentinel-2 and Landsat 8. A physical null, not bad luck with clouds.
 *
 *  Showing that is stronger than hiding it. A team that can say "we looked, here
 *  is exactly why it was impossible, and here is the better target we pivoted to"
 *  is more credible than one with a picture.
 *
 *  The measured column is real and published. The modelled column is empty,
 *  because no simulation run computes those same magnitudes (sediment g/L,
 *  salinity PSU) — the particle engine was never built to. What it does
 *  compute — a timing-only fit (onset/duration/peak) from the calibration
 *  grid search in `data/models/plume_calibration.json` — gets its own section
 *  below instead of forcing a fabricated match into these rows.
 */
export function ValidationPanel() {
  const { t } = useTranslation();
  const [v, setV] = useState<Validation | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void loadValidation()
      .then((d) => live && setV(d))
      .catch((e: Error) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, []);

  if (err) return <p role="alert" className="text-xs text-risk-critical">{err}</p>;
  if (!v) return <p className="text-xs text-ink-3">{t('rail.loading')}</p>;

  const m = v.mooring_target.magnitude as Record<string, number>;
  const timing = v.mooring_target.timing_utc as Record<string, string | number>;

  const rows: Array<{ key: string; value: number; unit: string; digits: number }> = [
    { key: 'peakSediment', value: m.peak_suspended_sediment_g_l, unit: 'g/L', digits: 2 },
    { key: 'salinityMinimum', value: m.salinity_minimum_psu, unit: 'PSU', digits: 2 },
    { key: 'salinityAnomaly', value: m.salinity_anomaly_delta_psu, unit: '‰', digits: 2 },
    { key: 'sedimentMass', value: m.sediment_mass_total_t, unit: 't', digits: 0 },
    {
      key: 'elevatedDuration',
      value: Number(timing.elevated_duration_hours),
      unit: 'h',
      digits: 2,
    },
  ];

  return (
    <div className="flex flex-col gap-5" data-panel="validation">
      {/* The comparison. Two columns, and the empty one is the point. */}
      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold">{t('validation.comparison')}</h3>
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr className="border-b border-hairline-2 text-2xs text-ink-3">
              <th scope="col" className="py-1 text-start font-normal">
                {t('validation.quantity')}
              </th>
              {/* Solid = measured, dashed = modelled. The form rule from 01 §4,
                  applied to a table header so the distinction is visible before
                  any number is read. */}
              <th scope="col" className="py-1 text-end font-normal">
                <span className="border-b border-data-measured pb-0.5">
                  {t('validation.measured')}
                </span>
              </th>
              <th scope="col" className="py-1 text-end font-normal">
                <span className="border-b border-dashed border-data-modelled pb-0.5">
                  {t('validation.modelled')}
                </span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className="border-b border-hairline">
                <th scope="row" className="py-1 text-start font-normal text-ink-2">
                  {t(`mooring.${r.key}`)}
                </th>
                <td className="py-1 text-end">
                  <ValueWithUnit
                    value={r.value}
                    unit={r.unit}
                    digits={r.digits}
                    provenance="reported"
                  />
                </td>
                <td className="py-1 text-end">
                  {/* null, so it renders as a gap. There is no simulation run. */}
                  <ValueWithUnit value={null} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <p className="text-2xs text-ink-3">
          {t('validation.notComputed')}{' '}
          <code className="font-mono num">{v.modelled_blocked_on}</code>
        </p>
      </section>

      {/* The one comparison the particle engine CAN make: timing, not magnitude.
          Kept separate from the table above rather than forced into its rows —
          the engine never computes sediment g/L or salinity PSU, so filling
          those cells from this data would be a fabricated match. */}
      {v.calibration_fit ? (
        <section className="flex flex-col gap-2 rule bg-surface-2 p-3">
          <h3 className="text-sm font-semibold">{t('validation.calibrationTitle')}</h3>
          <p className="text-xs text-ink-2">
            {t('validation.calibrationIntro', { n: v.calibration_fit.n_trials })}
          </p>
          <table className="w-full border-collapse text-xs">
            <tbody>
              <tr className="border-b border-hairline">
                <th scope="row" className="py-1 text-start font-normal text-ink-2">
                  {t('validation.arrivalError')}
                </th>
                <td className="py-1 text-end">
                  <ValueWithUnit
                    value={v.calibration_fit.arrival_time_error_hours}
                    unit="h"
                    digits={2}
                    provenance="modelled"
                  />
                </td>
              </tr>
              <tr className="border-b border-hairline">
                <th scope="row" className="py-1 text-start font-normal text-ink-2">
                  {t('validation.durationError')}
                </th>
                <td className="py-1 text-end">
                  <ValueWithUnit
                    value={v.calibration_fit.duration_error_hours}
                    unit="h"
                    digits={2}
                    provenance="modelled"
                  />
                </td>
              </tr>
              <tr className="border-b border-hairline">
                <th scope="row" className="py-1 text-start font-normal text-ink-2">
                  {t('validation.peakTimingError')}
                </th>
                <td className="py-1 text-end">
                  <ValueWithUnit
                    value={v.calibration_fit.peak_timing_error_hours}
                    unit="h"
                    digits={2}
                    provenance="modelled"
                  />
                </td>
              </tr>
            </tbody>
          </table>
          <p className="text-2xs text-ink-2">
            {t('validation.regimeVerdict')}:{' '}
            <code className="font-mono num">{v.calibration_fit.selected_regime_verdict}</code>
          </p>
          {/* Caveats rendered verbatim from the calibration record, same treatment
              as the citation/excerpt fields below — sourced prose, not UI chrome,
              so it is not run through i18n. */}
          <p className="text-2xs text-ink-2">{v.calibration_fit.peak_timing_caveat}</p>
          <p className="text-2xs text-ink-2">{v.calibration_fit.windage_caveat}</p>
          {v.calibration_fit.forcing_is_placeholder ? (
            <p className="text-2xs text-risk-high-on">
              {v.calibration_fit.forcing_placeholder_reason}
            </p>
          ) : null}
          <p className="text-2xs text-ink-2">
            {t('validation.source')}{' '}
            <code className="font-mono num">{v.calibration_fit.source}</code>
          </p>
        </section>
      ) : null}

      {/* The null result, stated as a finding rather than omitted. */}
      <section className="flex flex-col gap-2 rule bg-surface-2 p-3">
        <h3 className="flex items-baseline gap-2 text-sm font-semibold">
          {t('validation.satelliteTitle')}
          <span className="border border-risk-high-stroke bg-risk-high px-1.5 text-2xs text-risk-high-on">
            {v.satellite.verdict}
          </span>
        </h3>
        <p className="text-xs text-ink-2">{t('validation.satelliteBody')}</p>
        {v.satellite.is_physical_null ? (
          <p className="text-xs">
            <strong className="font-semibold">{t('validation.physicalNull')}</strong>{' '}
            <span className="text-ink-2">{t('validation.physicalNullBody')}</span>
          </p>
        ) : null}
        <p className="text-2xs text-ink-2">
          {t('validation.source')}{' '}
          <code className="font-mono num">{v.satellite.source}</code>
        </p>
      </section>

      {/* Where the measured numbers come from, in full. A validation panel whose
          own source is vague is not a validation panel. */}
      <section className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold">{t('validation.target')}</h3>
        <p className="text-2xs text-ink-2">{v.mooring_target.citation}</p>
        <p className="text-2xs text-ink-3">
          <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">
            doi:{v.mooring_target.doi}
          </span>
        </p>
        <p className="text-2xs text-ink-3">
          {t('validation.positionNote', {
            radius: (v.mooring_target.position as Record<string, number>).uncertainty_radius_m,
          })}
        </p>
      </section>
    </div>
  );
}
