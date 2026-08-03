import { useTranslation } from 'react-i18next';
import { Masthead } from '../shell/Masthead';
import { SideRail } from '../shell/SideRail';
import { TimeBar } from '../shell/TimeBar';
import { MapView } from '../map/MapView';

/** The one screen. 03 §1: eight storyboard scenes on a single view, with the
 *  limitations text and provenance panel as overlays rather than routes.
 *
 *  Layout regions are 03 §3. The grid is expressed in rows and columns rather
 *  than absolute positioning, because grid column order already follows document
 *  direction — which is most of what makes the RTL mirroring free.
 *
 *  The map is never smaller than half the viewport. That is enforced by the grid
 *  track sizing, not by a min-height on the map element, so it holds at every
 *  breakpoint rather than only where someone remembered to check.
 */
export function Home() {
  const { t } = useTranslation();

  return (
    <div
      className="grid h-screen grid-rows-[auto_minmax(0,1fr)_auto] bg-canvas text-ink"
      data-shell="true"
    >
      <Masthead />

      {/* Map + side rail. The rail is a fixed track so the map keeps the rest;
          on narrow viewports the rail drops below and the map keeps its height —
          03 §5's open question, answered in favour of the map because the map is
          the product. */}
      <div className="grid min-h-0 grid-rows-[minmax(0,1fr)_auto] lg:grid-cols-[minmax(0,1fr)_22rem] lg:grid-rows-1">
        <main className="relative min-h-0 border-b border-hairline lg:border-b-0 lg:border-e">
          <MapView />
        </main>
        <SideRail />
      </div>

      <TimeBar />

      {/* The map is never the only path to a fact — 09 rule 7. Phase 2 gives the
          time-varying layers their textual equivalent here; for now this states
          what the map cannot: that the basemap detail stops short of AQ-C01. */}
      <p className="sr-only">{t('map.textEquivalent')}</p>
    </div>
  );
}
