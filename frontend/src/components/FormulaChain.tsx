import { useTranslation } from 'react-i18next';
import { ValueWithUnit } from './ValueWithUnit';
import { PlaceholderNote } from './PlaceholderNote';

/** A single factor in the exposure formula's product chain. */
export interface Factor {
  /** The formula_terms key, e.g. 'plume_probability' */
  key: string;
  /** i18n'd human label */
  label: string;
  /** The numeric value of this factor */
  value: number;
  /** Provenance string from the payload, if any */
  source?: string;
  /** e.g. 'PLACEHOLDER_PENDING_MARINE_SCIENTIST' */
  placeholder?: string;
}

interface Props {
  factors: Factor[];
  /** raw_score from formula_terms */
  product: number;
  /** score_scale from formula_terms (typically 100) */
  scale: number;
  /** risk_score from formula_terms */
  result: number;
}

/** Renders the exposure formula as an inspectable product chain:
 *  a × b × c × d × e = raw, then raw × scale = score.
 *
 *  Self-checks that the factors multiply to raw_score within 1e-9. If they
 *  disagree, renders a loud mismatch state rather than silently showing wrong
 *  arithmetic — this mirrors the backend's own number-fidelity guard. */
export function FormulaChain({ factors, product, scale, result }: Props) {
  const { t } = useTranslation('tools');

  // Self-check: do the factors actually multiply to the product?
  const computed = factors.reduce((acc, f) => acc * f.value, 1);
  const mismatch = Math.abs(computed - product) > 1e-9;

  if (mismatch) {
    return (
      <div className="flex flex-col gap-2 rule border-risk-high-stroke bg-surface-2 p-4" data-formula-mismatch="true">
        <p className="m-0 text-xs font-semibold text-risk-high-on">
          {t('formula.mismatchTitle')}
        </p>
        <p className="m-0 text-2xs text-ink-2">
          {t('formula.mismatchBody', {
            computed: computed.toFixed(12),
            expected: product.toFixed(12),
          })}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4" data-formula-chain="true">
      {/* The product chain: factor × factor × … = raw_score */}
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-3">
        {factors.map((f, i) => (
          <span key={f.key} className="flex items-baseline gap-2">
            {i > 0 ? <span className="text-ink-3">×</span> : null}
            <span className="flex flex-col gap-0.5">
              <ValueWithUnit value={f.value} digits={4} provenance="modelled" />
              <span className="text-2xs text-ink-3">{f.label}</span>
            </span>
          </span>
        ))}
        <span className="flex items-baseline gap-2">
          <span className="text-ink-3">=</span>
          <span className="flex flex-col gap-0.5">
            <ValueWithUnit value={product} digits={6} provenance="modelled" />
            <span className="text-2xs text-ink-3">{t('formula.rawScore')}</span>
          </span>
        </span>
      </div>

      {/* The scale step: raw × scale = risk_score */}
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-3">
        <span className="flex flex-col gap-0.5">
          <ValueWithUnit value={product} digits={6} provenance="modelled" />
          <span className="text-2xs text-ink-3">{t('formula.rawScore')}</span>
        </span>
        <span className="text-ink-3">×</span>
        <span className="flex flex-col gap-0.5">
          <ValueWithUnit value={scale} digits={0} provenance="modelled" />
          <span className="text-2xs text-ink-3">{t('formula.scale')}</span>
        </span>
        <span className="text-ink-3">=</span>
        <span className="flex flex-col gap-0.5">
          <ValueWithUnit value={result} digits={2} provenance="modelled" className="text-sm font-semibold" />
          <span className="text-2xs text-ink-3">{t('formula.riskScore')}</span>
        </span>
      </div>

      {/* Per-factor provenance and placeholders */}
      <dl className="m-0 flex flex-col gap-3">
        {factors.map((f) => (
          <div key={f.key} className="flex flex-col gap-1 rule bg-surface-2 p-3">
            <dt className="m-0 text-2xs font-semibold text-ink-2">{f.label}</dt>
            <dd className="m-0 flex flex-col gap-1">
              <ValueWithUnit value={f.value} digits={6} provenance="modelled" />
              {f.source ? (
                <p className="m-0 text-2xs text-ink-3">{f.source}</p>
              ) : null}
              {f.placeholder ? <PlaceholderNote flag={f.placeholder} /> : null}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
