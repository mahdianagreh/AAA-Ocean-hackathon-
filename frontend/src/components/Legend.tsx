import { useTranslation } from 'react-i18next';
import { HAZARD_BANDS, HAZARD_RANGES } from '../api/types';

const BAND_CLASS = {
  minimal: 'bg-risk-minimal text-risk-minimal-on border-risk-minimal-stroke',
  low: 'bg-risk-low text-risk-low-on border-risk-low-stroke',
  moderate:
    // Correction #10: no AA-compliant text colour exists for this band in dark
    // theme (4.04 measured). So dark drops the fill and keeps the hue as a stroke
    // on --surface, where --ink reaches 14.32. Light theme is unaffected.
    'bg-risk-moderate text-risk-moderate-on border-risk-moderate-stroke ' +
    'dark:bg-surface dark:text-ink dark:border-risk-moderate',
  high: 'bg-risk-high text-risk-high-on border-risk-high-stroke',
  critical: 'bg-risk-critical text-risk-critical-on border-risk-critical-stroke',
} as const;

/** The legend — scenes 4 and 5.
 *
 *  Three constraints, all of them from rules rather than taste:
 *
 *  1. It must NOT imply reef zones differ in sensitivity. All eight carry
 *     sensitivity_weight 1.0 and a PLACEHOLDER_PENDING_MARINE_SCIENTIST status, so
 *     exposure varies only through the hazard term. 01 §6.6.
 *  2. The plume levels read *relative density*, never a percentage chance of
 *     impact. The engine peak-normalises before contouring, so a 0.50 band means
 *     half the peak density of this cloud — a statement about the simulation's own
 *     shape, not about the Gulf. 07 §4 calls mislabelling it the first thing a
 *     judge would press on.
 *  3. Every band carries a visible name and a 1px stroke. The weakest adjacent
 *     pair (minimal↔low) separates by only ΔE 7.2 under deuteranopia, and the
 *     mitigation for that band is mandatory secondary encoding — label, stroke,
 *     and a gap between chips. All three are present.
 */
export function Legend({ plumeLevels }: { plumeLevels?: number[] }) {
  const { t } = useTranslation();

  return (
    <section className="flex flex-col gap-3" data-legend="true">
      <div className="flex flex-col gap-1.5">
        <h3 className="text-xs font-semibold text-ink-2">{t('legend.hazard')}</h3>
        {/* gap-0.5 is the 2px surface gap between adjacent fills — a fill needs
            separating from its neighbour without drawing a line between them. */}
        <ul className="flex flex-col gap-0.5">
          {HAZARD_BANDS.map((b) => (
            <li
              key={b}
              data-legend-band={b}
              className={`flex items-baseline justify-between gap-2 border px-2 py-0.5 ${BAND_CLASS[b]}`}
            >
              <span className="text-2xs font-semibold">{t(`hazard.${b}`)}</span>
              <span
                dir="ltr"
                style={{ unicodeBidi: 'isolate' }}
                className="font-mono num text-2xs"
              >
                {HAZARD_RANGES[b]}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {plumeLevels?.length ? (
        <div className="flex flex-col gap-1.5">
          <h3 className="text-xs font-semibold text-ink-2">{t('legend.plume')}</h3>
          <ul className="flex flex-col gap-0.5">
            {plumeLevels.map((lv) => (
              <li key={lv} className="flex items-center justify-between gap-2 text-2xs">
                <span className="flex items-center gap-2">
                  <svg width="18" height="10" aria-hidden="true">
                    {/* Contours, never a trajectory line — 01 §6.1. Dashed,
                        because the plume is modelled. */}
                    <rect
                      x="0.5"
                      y="0.5"
                      width="17"
                      height="9"
                      fill="var(--data-envelope)"
                      stroke="var(--data-modelled)"
                      strokeWidth="1"
                      strokeDasharray="3 2"
                      opacity={0.35 + lv * 0.65}
                    />
                  </svg>
                  {t('legend.relativeDensity')}
                </span>
                <span
                  dir="ltr"
                  style={{ unicodeBidi: 'isolate' }}
                  className="font-mono num text-2xs text-ink-2"
                >
                  {lv.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
          {/* The caveat travels with the geometry, not in a footer. */}
          <p className="text-2xs text-ink-3">{t('legend.densityCaveat')}</p>
        </div>
      ) : null}

      <div className="flex flex-col gap-1.5">
        <h3 className="text-xs font-semibold text-ink-2">{t('legend.reef')}</h3>
        <p className="text-2xs text-ink-3">{t('legend.reefEqualSensitivity')}</p>
      </div>
    </section>
  );
}
