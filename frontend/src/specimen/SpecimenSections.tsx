import { useTranslation } from 'react-i18next';
import { CatchmentGlyph, OutletGlyph, ReefZoneGlyph } from '../icons';
import { HAZARD_BANDS, HAZARD_RANGES } from '../api/types';
import { Canary } from './Canary';
import { specimenEntries } from './registry';

function Section({
  id,
  title,
  note,
  children,
}: {
  id: string;
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} data-specimen={id} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 className="text-md font-semibold">{title}</h2>
        {note ? <p className="text-xs text-ink-3">{note}</p> : null}
      </div>
      {children}
    </section>
  );
}

/** The three glyphs at the sizes they actually get used, so a stroke that only
 *  works at 24px is visible as a problem. */
function Glyphs() {
  const { t } = useTranslation();
  const set = [
    { Icon: CatchmentGlyph, key: 'catchment' },
    { Icon: OutletGlyph, key: 'outlet' },
    { Icon: ReefZoneGlyph, key: 'reefZone' },
  ] as const;

  return (
    <div className="flex flex-wrap gap-6">
      {set.map(({ Icon, key }) => (
        <div key={key} className="flex flex-col items-center gap-2 rule p-3">
          <div className="flex items-end gap-3 text-ink">
            <Icon size={16} label={t(`glyph.${key}`)} />
            <Icon size={24} />
            <Icon size={32} />
          </div>
          <span className="text-2xs text-ink-2">{t(`glyph.${key}`)}</span>
        </div>
      ))}
    </div>
  );
}

/** Literal class names, not `bg-risk-${b}`.
 *
 *  Tailwind scans source statically, so an interpolated class is never a string
 *  in the file and the utility is never generated. The first version of this
 *  component did exactly that: the strokes rendered (they were an inline style)
 *  and every fill silently fell back to the canvas, which looked like a washed
 *  out ramp rather than a missing one. A lookup keeps the classes literal. */
const BAND_CLASS: Record<(typeof HAZARD_BANDS)[number], string> = {
  minimal: 'bg-risk-minimal text-risk-minimal-on border-risk-minimal-stroke',
  low: 'bg-risk-low text-risk-low-on border-risk-low-stroke',
  moderate: 'bg-risk-moderate text-risk-moderate-on border-risk-moderate-stroke',
  high: 'bg-risk-high text-risk-high-on border-risk-high-stroke',
  critical: 'bg-risk-critical text-risk-critical-on border-risk-critical-stroke',
};

/** The hazard ramp with its stroke rule applied, which is the only way to see
 *  that 'minimal' at 1.29 against canvas needs the stroke to exist at all. */
function HazardRamp() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap gap-2">
      {HAZARD_BANDS.map((b) => (
        <div
          key={b}
          data-band={b}
          className={`flex min-w-28 flex-col gap-1 border p-3 ${BAND_CLASS[b]}`}
        >
          <span className="text-sm font-semibold">{t(`hazard.${b}`)}</span>
          {/* Isolated, because a range is a bidi hazard too. `0–20` rendered as
              `20–0` in the first Arabic pane: the en-dash is a neutral character,
              so between two digit runs in an RTL paragraph the order resolves
              backwards. 06 §5 lists measurements and identifiers; ranges belong
              on that list and this is the evidence. */}
          <span
            dir="ltr"
            style={{ unicodeBidi: 'isolate' }}
            className="font-mono num text-2xs"
          >
            {HAZARD_RANGES[b]}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Provenance as FORM, not hue — 01 §4. Rendered in SVG because that is where
 *  it matters: the mooring trace is solid, the model output dashed, the
 *  uncertainty envelope hatched. A judge photographing the screen still sees it. */
function ProvenanceForms() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3">
      <svg viewBox="0 0 240 70" className="w-full max-w-md" role="img" aria-label={t('specimen.sectionProvenance')}>
        <defs>
          <pattern id="hatch" width="6" height="6" patternTransform="rotate(45)" patternUnits="userSpaceOnUse">
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--data-modelled)" strokeWidth="1" />
          </pattern>
        </defs>
        {/* envelope first, so the traces sit on top of it */}
        <path d="M10 44 C60 30, 110 52, 230 22 L230 42 C110 66, 60 46, 10 56 Z" fill="url(#hatch)" opacity="0.5" />
        <path d="M10 50 C60 38, 110 49, 230 32" fill="none" stroke="var(--data-measured)" strokeWidth="1.5" />
        <path d="M10 40 C60 26, 110 44, 230 18" fill="none" stroke="var(--data-modelled)" strokeWidth="1.5" strokeDasharray="4 3" />
      </svg>
      <ul className="flex flex-wrap gap-4 text-xs">
        <li className="flex items-center gap-2">
          <svg width="26" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="26" y2="4" stroke="var(--data-measured)" strokeWidth="1.5" />
          </svg>
          {t('provenance.measured')}
        </li>
        <li className="flex items-center gap-2">
          <svg width="26" height="8" aria-hidden="true">
            <line x1="0" y1="4" x2="26" y2="4" stroke="var(--data-modelled)" strokeWidth="1.5" strokeDasharray="4 3" />
          </svg>
          {t('provenance.modelled')}
        </li>
        <li className="flex items-center gap-2">
          <svg width="26" height="10" aria-hidden="true">
            <rect x="0" y="0" width="26" height="10" fill="url(#hatch)" opacity="0.5" />
          </svg>
          {t('provenance.envelope')}
        </li>
      </ul>
      <p className="text-xs text-ink-3">{t('specimen.provenanceNote')}</p>
    </div>
  );
}

export function SpecimenSections() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-8">
      <Section id="glyphs" title={t('specimen.sectionGlyphs')}>
        <Glyphs />
      </Section>

      <Section id="hazard" title={t('specimen.sectionHazard')} note={t('specimen.hazardNote')}>
        <HazardRamp />
      </Section>

      <Section id="provenance" title={t('specimen.sectionProvenance')}>
        <ProvenanceForms />
      </Section>

      <Section id="canary" title={t('specimen.canaryTitle')}>
        <Canary />
      </Section>

      {/* Anything registered later appears here automatically, so adding a
          primitive to all four panes stays a one-line change. */}
      {specimenEntries().map((e) => (
        <Section key={e.id} id={e.id} title={t(e.titleKey)} note={e.noteKey ? t(e.noteKey) : undefined}>
          {e.render()}
        </Section>
      ))}
    </div>
  );
}
