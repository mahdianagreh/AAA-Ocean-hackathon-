import { BUILDINGS_BASE_M, type Palette } from '../constants';

/** Real OSM building footprints — `buildings.geojson`
 *  (scripts/frontend_basemap.py's `buildings()`), clipped to a small buffer
 *  around each real outlet, height from the real `building:levels` tag where
 *  OSM has it and a documented default (2 storeys) where it doesn't. The
 *  footprint is always real; the height is real-or-assumed, and the fixture
 *  data carries which for every feature (`levels` is the real tag value or the
 *  default, never silently blended).
 *
 *  Based `BUILDINGS_BASE_M` above ground rather than at 0 so a building whose
 *  footprint falls on a taller coastal relief band is never rendered *inside*
 *  that band — see constants.ts's stacking-order docstring.
 */

const url = (name: string) => `${import.meta.env.BASE_URL}basemap/${name}.geojson`;

export function buildingsFragment(c: Palette) {
  return {
    sources: {
      buildings: { type: 'geojson' as const, data: url('buildings') },
    },
    layers: [
      {
        id: 'buildings-extrusion',
        type: 'fill-extrusion' as const,
        source: 'buildings',
        paint: {
          'fill-extrusion-color': c.surface_2,
          'fill-extrusion-base': BUILDINGS_BASE_M,
          'fill-extrusion-height': [
            '+',
            BUILDINGS_BASE_M,
            ['coalesce', ['get', 'height_m'], 6],
          ] as unknown as number,
          'fill-extrusion-opacity': 0.9,
        },
      },
    ],
  };
}
