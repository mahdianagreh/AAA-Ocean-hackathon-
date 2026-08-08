import type { Palette } from '../constants';

/** Real OSM building footprints — `buildings.geojson`
 *  (scripts/frontend_basemap.py's `buildings()`), clipped to a small buffer
 *  around each real outlet, height from the real `building:levels` tag where
 *  OSM has it and a documented default (2 storeys) where it doesn't. The
 *  footprint is always real; the height is real-or-assumed, and the fixture
 *  data carries which for every feature (`levels` is the real tag value or the
 *  default, never silently blended).
 *
 *  Base is `0` — with real terrain active (layers/terrain.ts), MapLibre reads
 *  that as the actual ground elevation under each building's own footprint,
 *  not sea level, so a building on the port strip and one on the inland slope
 *  both sit correctly on the real DEM surface without a manual clearance
 *  band.
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
          'fill-extrusion-base': 0,
          'fill-extrusion-height': ['coalesce', ['get', 'height_m'], 6] as unknown as number,
          'fill-extrusion-opacity': 0.9,
        },
      },
    ],
  };
}
