import type { StyleSpecification } from 'maplibre-gl';
import { palette, type ThemeName } from '../design/palette.generated';
import { reliefFragment } from './layers/relief';
import { buildingsFragment } from './layers/buildings';
import { reefFragment } from './layers/reef';
import { plumeFragment } from './layers/plume';
import { rainFragment } from './layers/rain';
import { runoffFragment } from './layers/runoff';

/** The 3D Journey's own style, composed from one fragment per concern
 *  (`layers/relief.ts`, `buildings.ts`, `reef.ts`, `plume.ts`, `rain.ts`,
 *  `runoff.ts`) rather than one monolithic source/layer list — each fragment
 *  owns its own real data source and paint logic, and this file only decides
 *  draw order.
 *
 *  Every extruded layer is real, already-committed data — no mesh, no
 *  generated imagery, no synthetic terrain tile. See each layer module's own
 *  docstring for its specific source and the honesty constraints that apply
 *  to it (sea depth drawn as upward relief, plume height as a real probability
 *  level times a stated constant, building height real-or-documented-default,
 *  runoff/rain as real geography with a stylised temporal treatment).
 */

const url = (name: string) => `${import.meta.env.BASE_URL}basemap/${name}.geojson`;

export function buildJourneyStyle(theme: ThemeName): StyleSpecification {
  const c = palette[theme];
  const isDark = theme === 'dark';

  const relief = reliefFragment(c, isDark);
  const buildings = buildingsFragment(c);
  const reef = reefFragment(c);
  const plume = plumeFragment();
  const rain = rainFragment(c);
  const runoff = runoffFragment(c);

  return {
    version: 8,
    name: 'ReefShield 3D Journey',
    projection: { type: 'mercator' },
    sources: {
      outlets: { type: 'geojson', data: url('outlets') },
      ...relief.sources,
      ...runoff.sources,
      ...buildings.sources,
      ...reef.sources,
      ...plume.sources,
      ...rain.sources,
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': isDark ? '#020a0d' : c.canvas } },
      ...relief.layers,
      ...runoff.layers,
      ...buildings.layers,
      ...reef.layers,
      {
        id: 'outlet-marker',
        type: 'circle',
        source: 'outlets',
        paint: {
          'circle-radius': 5,
          'circle-color': c.canvas,
          'circle-stroke-color': c.accent,
          'circle-stroke-width': 2,
        },
      },
      ...plume.layers,
      ...rain.layers,
    ],
  } as unknown as StyleSpecification;
}
