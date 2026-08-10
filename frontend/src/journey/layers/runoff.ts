import type { Feature, FeatureCollection, LineString, Polygon } from 'geojson';
import type { Palette } from '../constants';

/** Runoff — real wadi drainage LineStrings physically inside the release
 *  catchment (`journey3d.json`'s `runoff_lines`, spatially joined against the
 *  real `catchments.geojson`/`wadis.geojson` basemap layers by
 *  scripts/frontend_journey.py — not an invented flow path).
 *
 *  A first version animated a MapLibre dashed line (`line-dasharray`
 *  stepped on a timer) as the flow signal. It read as exactly that — a
 *  dashed line with a marching pattern, not moving water — because a
 *  handful of discrete dash segments cannot carry real turbulent motion at
 *  any cycle speed. The actual flow animation moved to a screen-space
 *  canvas overlay instead (`layers/waterFlowOverlay.ts`, drawn in
 *  `Journey3D.tsx`), same reasoning `rainOverlay.ts` already documents for
 *  rain. This module now only owns the one thing that IS honestly a
 *  MapLibre line at this camera distance: a soft, blurred "wet ground"
 *  halo along the real channel, ramped in by `Journey3D.tsx` over the
 *  flood phase rather than appearing at full strength instantly.
 */

const EMPTY_FC: FeatureCollection<LineString> = { type: 'FeatureCollection', features: [] };
const EMPTY_POLY_FC: FeatureCollection<Polygon> = { type: 'FeatureCollection', features: [] };

export function runoffFeatures(lines: number[][][]): FeatureCollection<LineString> {
  const features: Feature<LineString>[] = lines.map((coords) => ({
    type: 'Feature',
    properties: {},
    geometry: { type: 'LineString', coordinates: coords },
  }));
  return { type: 'FeatureCollection', features };
}

//: `rings` is one exterior ring per disjoint polygon the real buffer/union
//: produced (`_real_runoff_polygon`'s own return contract) -- each becomes
//: its own single-ring Polygon feature, not a MultiPolygon, so a future
//: consumer never has to special-case which shape it got.
export function runoffPolygonFeatures(rings: number[][][]): FeatureCollection<Polygon> {
  const features: Feature<Polygon>[] = rings.map((ring) => ({
    type: 'Feature',
    properties: {},
    geometry: { type: 'Polygon', coordinates: [ring] },
  }));
  return { type: 'FeatureCollection', features };
}

//: Fixed, not theme-derived -- real wet ground has its own real colour
//: regardless of the app's light/dark toggle, same reasoning as
//: rainOverlay.ts's streak colours and waterFlowOverlay.ts's water colour.
const WET_GROUND_COLOR = '#3a2a1c'; // token-ok: real wet-ground colour, not app chrome

export function runoffFragment(_c: Palette) {
  return {
    sources: {
      runoff: { type: 'geojson' as const, data: EMPTY_FC },
      // Real geometry, kept for any future closer-camera use, but NOT what
      // the halo layer below draws from -- see its own comment for why.
      'runoff-fill': { type: 'geojson' as const, data: EMPTY_POLY_FC },
    },
    layers: [
      // Drawn on the CENTRELINE source at a fixed screen-pixel width, not on
      // the real buffered polygon (`runoff-fill`): the real, drainage-
      // density-scaled channel is ~20-80 m wide, and at this phase's real
      // camera zoom (~10.6) that is under one screen pixel -- genuinely
      // invisible, not a styling problem (waterFlowOverlay.ts's own
      // docstring covers this same lesson for the actual flow animation).
      {
        id: 'runoff-wet-ground',
        type: 'line' as const,
        source: 'runoff',
        layout: { 'line-cap': 'round' as const },
        paint: {
          'line-color': WET_GROUND_COLOR,
          'line-width': 22,
          'line-blur': 10,
          'line-opacity': 0,
        },
      },
    ],
  };
}
