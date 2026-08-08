import type { StyleSpecification } from 'maplibre-gl';
import { palette, type ThemeName } from '../design/palette.generated';
import { terrainSourceFragment } from './layers/terrain';
import { buildingsFragment } from './layers/buildings';
import { reefFragment } from './layers/reef';
import { plumeFragment } from './layers/plume';
import { rainFragment } from './layers/rain';
import { runoffFragment } from './layers/runoff';

/** The 3D Journey's own style, composed from one fragment per concern
 *  (`layers/terrain.ts`, `buildings.ts`, `reef.ts`, `plume.ts`, `rain.ts`,
 *  `runoff.ts`) rather than one monolithic source/layer list — each fragment
 *  owns its own real data source and paint logic, and this file only decides
 *  draw order.
 *
 *  Terrain is real, continuous 3D relief (`layers/terrain.ts`'s baked
 *  Terrain-RGB mesh — real Copernicus DEM + real bathymetry, merged), applied
 *  outside the style tree via `map.setTerrain()` once this style has loaded
 *  (see Journey3D.tsx) — the source is declared here, the terrain *effect* is
 *  not a style-spec layer. Everything else (buildings, reef, plume) is real
 *  data draped or extruded relative to that real terrain surface, not a
 *  second, disjoint relief system — no mesh, no generated imagery, no
 *  synthetic terrain tile. See each layer module's own docstring for its
 *  specific source and honesty constraints.
 */

const url = (name: string) => `${import.meta.env.BASE_URL}basemap/${name}.geojson`;

export function buildJourneyStyle(theme: ThemeName): StyleSpecification {
  const c = palette[theme];
  const isDark = theme === 'dark';

  const terrain = terrainSourceFragment();
  const buildings = buildingsFragment(c);
  const reef = reefFragment(c);
  const plume = plumeFragment();
  const rain = rainFragment(c);
  const runoff = runoffFragment(c);

  return {
    version: 8,
    name: 'Aqaba Aqua AI 3D Journey',
    projection: { type: 'mercator' },
    sky: { 'sky-color': isDark ? '#020a0d' : '#bfe3ea', 'horizon-color': isDark ? '#0c2327' : c.surface_2 }, // token-ok: 3D sky lighting, no UI token exists
    sources: {
      outlets: { type: 'geojson', data: url('outlets') },
      ...terrain.sources,
      ...runoff.sources,
      ...buildings.sources,
      ...reef.sources,
      ...plume.sources,
      ...rain.sources,
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': isDark ? '#020a0d' : c.canvas } }, // token-ok: matches sky, no horizon seam
      {
        id: 'terrain-hillshade',
        type: 'hillshade',
        source: 'terrain',
        paint: {
          // Neutral, not land/sea-tinted: the real Esri imagery drape
          // (added in Journey3D.tsx once its async corners resolve) now
          // carries true colour, so hillshade's only job left is relief
          // *shading* — a colour cast here would discolour a real photo.
          'hillshade-shadow-color': isDark ? '#05070a' : '#14181a', // token-ok: relief shading
          'hillshade-highlight-color': isDark ? '#3d434a' : '#fdfbf3', // token-ok: relief shading
          'hillshade-exaggeration': 0.45,
        },
      },
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
