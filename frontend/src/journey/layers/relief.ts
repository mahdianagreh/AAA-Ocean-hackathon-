import { RELIEF_HEIGHT_SCALE, type Palette } from '../constants';

/** Real terrain/bathymetry relief — `relief_bands.geojson`
 *  (scripts/frontend_basemap.py's `relief_bands()`, vectorized from
 *  `depth_utm36n.tif`, the same raster the 2D map's `isobaths` layer already
 *  contours). Sea depth is drawn as upward relief coloured by depth, not sunk
 *  below a surface plane — see the on-screen legend, which says so.
 */

const url = (name: string) => `${import.meta.env.BASE_URL}basemap/${name}.geojson`;

// `Palette` isn't referenced directly (the colour ramp is hand-tuned per
// theme via `isDark`, not derived from palette tokens — there is no
// "land"/"sea" entry in the design system to reuse), but the parameter stays
// for signature consistency with the other layer fragments.
export function reliefFragment(_c: Palette, isDark: boolean) {
  return {
    sources: {
      relief: { type: 'geojson' as const, data: url('relief_bands') },
    },
    layers: [
      {
        id: 'relief-extrusion',
        type: 'fill-extrusion' as const,
        source: 'relief',
        paint: {
          'fill-extrusion-color': [
            'interpolate', ['linear'], ['get', 'mid_m'],
            -800, isDark ? '#04222c' : '#0d3a4a',
            -25, isDark ? '#0f4a5c' : '#2f7a92',
            0, isDark ? '#1c5a4a' : '#3fa07a',
            150, isDark ? '#4a5a2a' : '#a3924a',
            800, isDark ? '#6a5040' : '#8a6a4a',
            1800, isDark ? '#8a8880' : '#c9c4b8',
          ] as unknown as string,
          // sqrt, not linear — see constants.ts's own docstring for why.
          'fill-extrusion-height': [
            '*',
            ['sqrt', ['abs', ['get', 'mid_m']]],
            RELIEF_HEIGHT_SCALE,
          ] as unknown as number,
          'fill-extrusion-opacity': 0.92,
        },
      },
    ],
  };
}
