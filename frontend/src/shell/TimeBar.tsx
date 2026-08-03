import { useTranslation } from 'react-i18next';

/** Time bar: full width beneath the map, drives every time-varying layer — 03 §3.
 *
 *  Phase 1 reserves the region and states what it will do. The slider itself is
 *  Phase 2 and is bespoke rather than a Radix Slider, because of the one subtlety
 *  06 §3 calls "the subtle one": the control mirrors under RTL, but the time axis
 *  it scrubs does not. Earlier stays on the left, because the hyetograph beneath
 *  it runs left to right and the two must agree. Getting that backwards makes the
 *  whole time-scrub choreography feel wrong in Arabic without anyone being able to
 *  say why.
 *
 *  Reserving the space now rather than adding it in Phase 2 means the map's height
 *  does not change when the slider lands — and the map-never-below-half-viewport
 *  rule is measured against this layout, not a layout without it.
 */
export function TimeBar() {
  const { t } = useTranslation();

  return (
    <footer
      className="flex items-center justify-between gap-4 border-t border-hairline bg-surface px-4 py-2"
      aria-label={t('time.label')}
    >
      <p className="text-2xs text-ink-3">{t('time.phase2')}</p>

      {/* Attribution is a licence obligation for OSM, MapLibre, GMRT and Allen
          Coral Atlas, and 00's risk register scores it. The map carries its own
          non-collapsible control; this repeats the ODbL share-alike one, because
          it is the obligation with an actual condition attached. */}
      <p className="text-2xs text-ink-3">{t('time.attribution')}</p>
    </footer>
  );
}
