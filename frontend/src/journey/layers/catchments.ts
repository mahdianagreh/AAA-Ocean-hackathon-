import type { Palette } from '../constants';

/** Catchment boundaries — real geometry from `catchments.gpkg`, carrying real
 *  per-catchment soil texture (`soil_by_catchment.parquet`, SoilGrids) and
 *  terrain stats (`catchment_terrain.parquet`, DEM-derived) joined in by
 *  `scripts/frontend_basemap.py`. The fill colour is a real, measured number
 *  (topsoil sand fraction), not a stand-in tint — this is the same "no
 *  invented number" bar every other layer in this project holds to.
 *
 *  `AQ-C01` (Wadi Yutum) is 4,453 km² — most of the terrain AOI — against
 *  ~35-65 km² for the other four, so a strong fill would blot out the real
 *  terrain relief underneath it. Kept low-opacity with a solid outline and a
 *  label instead of a solid tint, so the shape reads without hiding the
 *  ground it sits on.
 */

const url = (name: string) => `${import.meta.env.BASE_URL}basemap/${name}.geojson`;

//: Real observed range across the five catchments (25.5-37.9%, see
//: soil_by_catchment.parquet) -- the interpolation stops are this project's
//: actual data span, not an invented 0-100 texture scale.
const SAND_PCT_MIN = 25;
const SAND_PCT_MAX = 38;

export function catchmentsFragment(c: Palette) {
  return {
    sources: {
      catchments: { type: 'geojson' as const, data: url('catchments') },
    },
    layers: [
      {
        id: 'catchment-fill',
        type: 'fill' as const,
        source: 'catchments',
        paint: {
          'fill-color': [
            'interpolate',
            ['linear'],
            ['coalesce', ['get', 'sand_pct'], SAND_PCT_MIN],
            SAND_PCT_MIN, c.surface_2,
            SAND_PCT_MAX, c.data_measured,
          ] as unknown as string,
          'fill-opacity': 0.22,
        },
      },
      {
        id: 'catchment-outline',
        type: 'line' as const,
        source: 'catchments',
        paint: {
          'line-color': c.ink,
          'line-width': 1.5,
          'line-opacity': 0.8,
        },
      },
      {
        id: 'catchment-label',
        type: 'symbol' as const,
        source: 'catchments',
        layout: {
          'text-field': [
            'concat',
            ['get', 'catchment_id'],
            '\n',
            ['to-string', ['round', ['get', 'area_km2']]],
            ' km²  ·  ',
            ['to-string', ['get', 'slope_mean_deg']],
            '° slope',
          ] as unknown as string,
          'text-size': 11,
          'text-justify': 'center' as const,
          'text-line-height': 1.2,
        },
        paint: {
          'text-color': c.ink,
          'text-halo-color': c.canvas,
          'text-halo-width': 1.3,
        },
      },
    ],
  };
}

//: Full during 'normal'/'rain'/'flood' (the catchment IS the story there);
//: faded once the story moves to the plume/reef so the boundary still reads
//: as context without competing with the sediment cloud or reef colour.
export function catchmentOpacity(phase: string): { fill: number; line: number; text: number } {
  const dim = phase === 'transport' || phase === 'accumulation' || phase === 'impact';
  return dim ? { fill: 0.08, line: 0.35, text: 0 } : { fill: 0.22, line: 0.8, text: 1 };
}
