import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { loadModelInfo, type ModelInfo } from '../api/panels';
import { ValueWithUnit } from '../components/ValueWithUnit';

/** p4-09 "AI Never Saw This Storm" + p4-11 "Simple vs Smart Guess", built as one
 *  model-honesty panel, per `tasks/phase7/02-mahdi.md`.
 *
 *  Same derive-and-commit pattern as every other honest panel (`ValidationPanel`,
 *  `ProvenancePanel`): `scripts/frontend_panels.py` bakes the served model's own
 *  `model_versions.jsonl` record into `fixtures/models.json` offline, so this
 *  never makes a live call — DoD item 9 ("works with wifi off") is a hard gate.
 *
 *  The one thing this panel exists to prevent is conflating three genuinely
 *  different numbers under one claim of "the model's accuracy":
 *
 *    metrics.mean_AP                          leave-one-catchment-out —
 *                                              generalises to an unseen CATCHMENT
 *    metrics.temporal_holdout_AP               trained on data through 2014 —
 *                                              generalises to an unseen TIME PERIOD
 *    label_leakage_ablation.defensible_mean_AP a DIFFERENT, never-shipped model —
 *                                              the only defensible number for
 *                                              "predicts from independent inputs"
 *
 *  Root CLAUDE.md is explicit that the served model's own mean_AP (0.7474) must
 *  never be quoted for that third claim: any ERA5-sourced feature it uses leaks
 *  the same atmosphere its label was generated from.
 */
export function ModelHonestyPanel() {
  const { t } = useTranslation();
  const [m, setM] = useState<ModelInfo | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void loadModelInfo()
      .then((d) => live && setM(d))
      .catch((e: Error) => live && setErr(e.message));
    return () => {
      live = false;
    };
  }, []);

  if (err) return <p role="alert" className="text-xs text-risk-critical">{err}</p>;
  if (!m) return <p className="text-xs text-ink-3">{t('rail.loading')}</p>;

  const ablation = m.label_leakage_ablation;
  const split = m.metrics.temporal_holdout_split;
  const anchor = m.metrics.temporal_holdout_anchor_check;

  return (
    <div className="flex flex-col gap-5" data-panel="model">
      <section className="flex flex-col gap-1">
        <p className="text-2xs text-ink-3">{t('modelHonesty.servedModel')}</p>
        <code dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num text-sm text-ink-2">
          {m.id}
        </code>
        <p className="text-2xs text-ink-3">
          {t('modelHonesty.trainedOn', {
            n: m.n_training_events,
            date: m.trained_at.slice(0, 10),
            features: m.features.length,
          })}
        </p>
      </section>

      {/* p4-11 — Simple vs Smart Guess. */}
      <section className="flex flex-col gap-2 rule bg-surface-2 p-3">
        <h3 className="text-sm font-semibold">{t('modelHonesty.guessTitle')}</h3>
        <p className="text-xs text-ink-2">{t('modelHonesty.guessIntro')}</p>
        <table className="w-full border-collapse text-xs">
          <tbody>
            <tr className="border-b border-hairline">
              <th scope="row" className="py-1 text-start font-normal text-ink-2">
                {t('modelHonesty.naiveBaseline')}
              </th>
              <td className="py-1 text-end">
                <ValueWithUnit value={m.metrics.baseline_mean_AP} unit="AP" digits={4} provenance="modelled" />
              </td>
            </tr>
            <tr className="border-b border-hairline">
              <th scope="row" className="py-1 text-start font-normal text-ink-2">
                {t('modelHonesty.thisModel')}
              </th>
              <td className="py-1 text-end">
                <ValueWithUnit value={m.metrics.mean_AP} unit="AP" digits={4} provenance="modelled" />
              </td>
            </tr>
          </tbody>
        </table>
        <p className="text-2xs text-ink-3">{t('modelHonesty.locoLabel')}</p>
      </section>

      {/* p4-09 — AI Never Saw This Storm. */}
      <section className="flex flex-col gap-2 rule bg-surface-2 p-3">
        <h3 className="text-sm font-semibold">{t('modelHonesty.stormTitle')}</h3>
        <p className="text-xs text-ink-2">
          {t('modelHonesty.stormIntro', { year: split.cutoff_year })}
        </p>
        <table className="w-full border-collapse text-xs">
          <tbody>
            <tr className="border-b border-hairline">
              <th scope="row" className="py-1 text-start font-normal text-ink-2">
                {t('modelHonesty.naiveBaseline')}
              </th>
              <td className="py-1 text-end">
                <ValueWithUnit value={m.metrics.temporal_holdout_baseline_AP} unit="AP" digits={4} provenance="modelled" />
              </td>
            </tr>
            <tr className="border-b border-hairline">
              <th scope="row" className="py-1 text-start font-normal text-ink-2">
                {t('modelHonesty.thisModel')}
              </th>
              <td className="py-1 text-end">
                <ValueWithUnit value={m.metrics.temporal_holdout_AP} unit="AP" digits={4} provenance="modelled" />
              </td>
            </tr>
          </tbody>
        </table>
        <p className="text-2xs text-ink-3">
          {t('modelHonesty.temporalLabel', {
            trainRows: split.train_rows,
            testRows: split.test_rows,
            year: split.cutoff_year,
          })}
        </p>
        <p className="text-2xs text-ink-2">
          {t('modelHonesty.anchorNote', {
            catchment: anchor.anchor_catchment,
            pct: anchor.anchor_percentile,
            n: anchor.anchor_n_days_in_catchment_test_set,
          })}
        </p>
      </section>

      {/* The reconciliation — the panel's actual point. */}
      <section className="flex flex-col gap-2 rule bg-surface-2 p-3">
        <h3 className="text-sm font-semibold">{t('modelHonesty.reconcileTitle')}</h3>
        <p className="text-xs text-ink-2">{t('modelHonesty.reconcileWarning')}</p>
        <table className="w-full border-collapse text-xs">
          <tbody>
            <tr className="border-b border-hairline">
              <th scope="row" className="py-1 text-start font-normal text-ink-2">
                {t('modelHonesty.claimCatchment')}
              </th>
              <td className="py-1 text-end">
                <ValueWithUnit value={m.metrics.mean_AP} unit="AP" digits={4} provenance="modelled" />
              </td>
            </tr>
            <tr className="border-b border-hairline">
              <th scope="row" className="py-1 text-start font-normal text-ink-2">
                {t('modelHonesty.claimTime')}
              </th>
              <td className="py-1 text-end">
                <ValueWithUnit value={m.metrics.temporal_holdout_AP} unit="AP" digits={4} provenance="modelled" />
              </td>
            </tr>
            <tr className="border-b border-hairline">
              <th scope="row" className="py-1 text-start font-normal text-ink-2">
                {t('modelHonesty.claimIndependent')}
              </th>
              <td className="py-1 text-end">
                <ValueWithUnit value={ablation.defensible_mean_AP} unit="AP" digits={4} provenance="modelled" />
              </td>
            </tr>
          </tbody>
        </table>
        <p className="text-2xs text-ink-2">
          {t('modelHonesty.independentNote', {
            shipped: ablation.shipped_mean_AP,
            defensible: ablation.defensible_mean_AP,
          })}
        </p>
        <p className="text-2xs text-ink-3">{ablation.why_shipped_is_not_defensible}</p>
        <p className="text-2xs text-ink-3">
          {t('modelHonesty.source')}{' '}
          <code className="font-mono num">{ablation.source}</code>
        </p>
      </section>
    </div>
  );
}
