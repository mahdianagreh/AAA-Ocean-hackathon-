import { useTranslation } from 'react-i18next';
import { Masthead } from '../shell/Masthead';
import { SideRail } from '../shell/SideRail';
import { TimeBar } from '../shell/TimeBar';
import { MapView } from '../map/MapView';
import { useEventData, useRiskCards } from '../app/useEventData';
import { useLiveExposure } from '../app/useLiveExposure';
import { OverlayHost } from '../panels/OverlayHost';

/** The operational screen, at /dashboard.
 *
 *  03 §1 originally put eight storyboard scenes on a single view at `/`, with
 *  the limitations text and provenance panel as overlays rather than routes.
 *  The brand rebuild moved `/` to the marketing home and gave those panels real
 *  URLs, but the overlays still work from here — a judge mid-demo should not
 *  have to leave the map to check provenance and then find their way back.
 *
 *  Data is loaded ONCE here and passed down, so the map, the hyetograph and the
 *  risk cards read the same cursor and the same values. 01 §7: a judge dragging
 *  the slider and watching rainfall, runoff and exposure move in lockstep
 *  understands the system in three seconds — and lockstep needs a single source.
 *
 *  Layout regions are 03 §3. The grid is rows and columns rather than absolute
 *  positioning, because grid column order already follows document direction,
 *  which is most of what makes the RTL mirroring free. The map is never smaller
 *  than half the viewport, enforced by track sizing rather than a min-height
 *  someone has to remember to check.
 */
export function Dashboard() {
  const { t } = useTranslation();
  const { data, error } = useEventData();
  const risk = useRiskCards(data);
  // Loaded independently of `data` — see the hook's own docstring for why a
  // failed live call must not block the historical/offline path from rendering.
  const live = useLiveExposure(data?.series.event_id);

  return (
    <div
      className="grid h-screen grid-rows-[auto_minmax(0,1fr)_auto] bg-canvas text-ink"
      data-shell="true"
    >
      <Masthead steps={data?.steps ?? []} />

      <div className="grid min-h-0 grid-rows-[minmax(0,1fr)_auto] lg:grid-cols-[minmax(0,1fr)_23rem] lg:grid-rows-1">
        <main className="relative min-h-0 border-b border-hairline lg:border-b-0 lg:border-e">
          <MapView risk={risk} />
        </main>
        <SideRail data={data} risk={risk} error={error} live={live} />
      </div>

      <TimeBar data={data} />

      <OverlayHost />

      {/* The map is never the only path to a fact — 09 rule 7. The rail carries
          the values; this carries what the map cannot say at all. */}
      <p className="sr-only">{t('map.textEquivalent')}</p>
    </div>
  );
}
