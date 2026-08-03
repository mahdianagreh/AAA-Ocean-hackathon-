import { useTranslation } from 'react-i18next';
import type { Provenance, Value } from '../api/types';

/** Every measurement on screen goes through this. There is no second way.
 *
 *  Two rules meet here, and both are structural rather than stylistic.
 *
 *  1. Bidi isolation — 06 §5. Without it, RTL reorders `2.18 g/L` into
 *     `g/L 2.18` and `AQ-C01` can render with its digits leading. The CSS
 *     property is used rather than U+2068/U+2069 characters, because those end
 *     up in copied text and in screen-reader output.
 *
 *  2. Missing is null, never zero — 07 §2 and 09 rule 4. A gap renders as a
 *     gap, visibly distinct from a measured zero. Passing `null` is the correct
 *     way to say "no data"; passing 0 asserts a measurement.
 *
 *  Western digits in both languages — 06 §5. Scientific convention in Jordan,
 *  and Arabic-Indic numerals would break column alignment in the mono face
 *  across a language switch.
 */

const FORM: Record<Provenance, string> = {
  // 01 §4: measured vs modelled is encoded in FORM, not hue.
  measured: 'border-b border-data-measured',
  reported: 'border-b border-data-measured',
  converted: 'border-b border-dashed border-data-measured',
  modelled: 'border-b border-dashed border-data-modelled',
};

interface Props {
  /** null means no data. It must not be coerced to 0 anywhere upstream. */
  value: number | null;
  unit?: string;
  /** Decimal places. Omitted means show the number as given. */
  digits?: number;
  /** When present, the value carries its provenance as an underline form. */
  provenance?: Provenance;
  className?: string;
}

export function ValueWithUnit({ value, unit, digits, provenance, className }: Props) {
  const { t } = useTranslation();

  if (value === null || Number.isNaN(value)) {
    // No mono here. "No data" is prose, not a measurement — and in Arabic
    // (لا توجد بيانات) the Latin mono face has no Arabic coverage, so it fell
    // back mid-string and rendered with broken spacing. Only numbers get mono.
    return (
      <span
        className={`text-ink-3 ${className ?? ''}`}
        data-missing="true"
        title={t('value.missingLong')}
      >
        {t('value.missing')}
      </span>
    );
  }

  const shown = digits === undefined ? String(value) : value.toFixed(digits);

  return (
    <span
      dir="ltr"
      // isolate, not embed: embed would leak the direction into neighbouring text
      style={{ unicodeBidi: 'isolate' }}
      className={`font-mono num ${provenance ? FORM[provenance] : ''} ${className ?? ''}`}
      data-provenance={provenance}
    >
      {shown}
      {unit ? (
        <>
          {' '}
          <span className="text-ink-2">{unit}</span>
        </>
      ) : null}
    </span>
  );
}

/** Convenience for a whole `Value` from the API, which always carries its unit
 *  and provenance — 07 §2 makes a Value without provenance a type error, so an
 *  unlabelled number cannot reach the screen. */
export function ValueField({
  v,
  digits,
  className,
}: {
  v: Value | null;
  digits?: number;
  className?: string;
}) {
  if (!v) return <ValueWithUnit value={null} className={className} />;
  return (
    <ValueWithUnit
      value={v.value}
      unit={v.unit}
      digits={digits}
      provenance={v.provenance}
      className={className}
    />
  );
}
