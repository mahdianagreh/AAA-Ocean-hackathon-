import { useTranslation } from 'react-i18next';
import { ValueWithUnit } from '../components/ValueWithUnit';

/** The bidi canary.
 *
 *  Every value here is a real number from this project, not a lorem figure:
 *  the mooring's turbidity peak and salinity anomaly, a catchment id, the
 *  mooring coordinate, and a forecast offset. If any of them renders with its
 *  unit leading in the RTL panes, bidi isolation is broken — and 06 §8.5 asks
 *  for exactly these four to be spot-checked.
 *
 *  They are also the numbers the demo will show, so a formatting bug surfaces
 *  here rather than on stage.
 */
export function Canary() {
  const { t } = useTranslation();

  // Data, not JSX — so the table owns the keys and each row stays one readable
  // line. Every figure is real: the mooring record for AQ-2016-10-28.
  const rows: Array<{
    label: string;
    value: number | null;
    unit?: string;
    digits?: number;
    provenance?: 'measured' | 'reported' | 'converted' | 'modelled';
  }> = [
    { label: 'Turbidity peak', value: 2.18, unit: 'g/L', digits: 2, provenance: 'reported' },
    { label: 'Salinity anomaly', value: -1.75, unit: '‰', digits: 2, provenance: 'reported' },
    { label: 'Salinity minimum', value: 38.75, unit: 'PSU', digits: 2, provenance: 'reported' },
    { label: 'Sediment mass', value: 24400, unit: 't', provenance: 'reported' },
    { label: 'Elevated duration', value: 31.42, unit: 'h', digits: 2, provenance: 'converted' },
    { label: 'Runoff probability', value: 0.7213, digits: 4, provenance: 'modelled' },
    // The gap case. 09 rule 4: missing is never zero, and it must look different.
    { label: 'Sediment class', value: null },
  ];

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-ink-2">{t('specimen.canaryNote')}</p>

      <table className="w-full border-collapse text-sm">
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className="border-b border-hairline">
              <th scope="row" className="py-1 text-start font-normal text-ink-2">
                {r.label}
              </th>
              <td className="py-1 text-end">
                <ValueWithUnit
                  value={r.value}
                  unit={r.unit}
                  digits={r.digits}
                  provenance={r.provenance}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Identifiers and coordinates isolate too — 06 §5 lists both. An
          unisolated AQ-C01 can render with its digits leading in RTL. */}
      <div className="flex flex-wrap gap-4 text-xs">
        <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">
          AQ-C01
        </span>
        <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">
          AQ-O01
        </span>
        <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">
          R-04
        </span>
        <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">
          34.97073, 29.54560
        </span>
        <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">
          2016-10-28T06:50:00Z
        </span>
        <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">
          T+06:00
        </span>
      </div>

      {/* Column alignment is the reason mono + tabular-nums is non-negotiable in
          02 §4 — these must line up on the decimal in both languages. */}
      <div className="flex flex-col rule p-3">
        {[2.18, 38.75, -1.75, 24400, 0.7213].map((n) => (
          <ValueWithUnit key={n} value={n} digits={4} className="text-end" />
        ))}
      </div>
    </div>
  );
}
