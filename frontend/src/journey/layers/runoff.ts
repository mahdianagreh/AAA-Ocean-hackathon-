import type { Feature, FeatureCollection, LineString } from 'geojson';
import type { Palette } from '../constants';

/** Runoff — real wadi drainage LineStrings physically inside the release
 *  catchment (`journey3d.json`'s `runoff_lines`, spatially joined against the
 *  real `catchments.geojson`/`wadis.geojson` basemap layers by
 *  scripts/frontend_journey.py — not an invented flow path). Animated with a
 *  "marching dashes" pattern (cycled `line-dasharray` phase, a standard
 *  MapLibre-compatible technique — there is no native animated line offset
 *  property) to read as directional flow rather than a static highlight.
 */

const EMPTY_FC: FeatureCollection<LineString> = { type: 'FeatureCollection', features: [] };

export function runoffFeatures(lines: number[][][]): FeatureCollection<LineString> {
  const features: Feature<LineString>[] = lines.map((coords) => ({
    type: 'Feature',
    properties: {},
    geometry: { type: 'LineString', coordinates: coords },
  }));
  return { type: 'FeatureCollection', features };
}

//: One marching-dash cycle, stepped by tick index — visually reads as flow
//: along the line without a native animated-offset paint property.
const DASH_CYCLE: Array<[number, number, number]> = [
  [0, 4, 3],
  [1, 4, 2],
  [2, 4, 1],
  [3, 4, 0.001],
];

export function runoffDashArray(tick: number): [number, number, number] {
  return DASH_CYCLE[tick % DASH_CYCLE.length];
}

export function runoffFragment(c: Palette) {
  return {
    sources: {
      runoff: { type: 'geojson' as const, data: EMPTY_FC },
    },
    layers: [
      // A static white casing under the animated dash line, wider and
      // partly transparent — the same reasoning as rain.ts's white stroke:
      // a 3 px line in one desaturated teal, this project's "real measured
      // data" token, reads clearly against the old flat relief bands but
      // thins into real satellite imagery's own texture. The casing is
      // fixed white (not theme-derived) for the same reason: it answers the
      // photo's colours, not the app's.
      {
        id: 'runoff-casing',
        type: 'line' as const,
        source: 'runoff',
        layout: { 'line-cap': 'round' as const },
        paint: {
          'line-color': '#ffffff',
          'line-width': 6,
          'line-opacity': 0.55,
        },
      },
      {
        id: 'runoff-flow',
        type: 'line' as const,
        source: 'runoff',
        layout: { 'line-cap': 'round' as const },
        paint: {
          'line-color': c.data_measured,
          'line-width': 3,
          'line-dasharray': DASH_CYCLE[0],
          'line-opacity': 0.95,
        },
      },
    ],
  };
}
