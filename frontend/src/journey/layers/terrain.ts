/** Real, continuous 3D terrain — MapLibre's native `raster-dem` source +
 *  `map.setTerrain()`, per the team's 3D Journey implementation plan
 *  (`mahdi-3D-implementation-plan.md` §1, §3.1). Replaces the first pass's
 *  disjoint fill-extrusion relief bands (one flat height per elevation band,
 *  since deleted) with an actual continuous elevation mesh.
 *
 *  The tile pyramid is baked once, offline-capable forever after, by two new
 *  scripts:
 *    scripts/merge_terrain_bathymetry.py  — real Copernicus GLO-30 DEM (land)
 *      + real depth_utm36n.tif (sea), seamed by the real coastline polygon,
 *      not a value threshold (the exact GLO-30 "sea = 0.0" gotcha
 *      03_dem_fetch.py's own docstring names).
 *    scripts/tile_terrain_rgb.py — standard Mapbox Terrain-RGB encoding
 *      (base=-10000, interval=0.1), tiled as loose PNGs (not .mbtiles, which
 *      would need a tile-serving process this project's static offline pack
 *      does not have).
 *
 *  `bounds` is set to the real TERRAIN_AOI so MapLibre never requests a tile
 *  outside where real data exists — the honest version of "no imagery" is no
 *  request, not a 404 silently retried.
 */

import type { RasterDEMSourceSpecification } from 'maplibre-gl';

const TILE_URL = `${import.meta.env.BASE_URL}terrain/{z}/{x}/{y}.png`;

//: backend/src/config/spatial.py's TERRAIN_AOI, .wsen order — duplicated as a
//: literal here (not imported) only because this is frontend code with no
//: access to the Python config module; tests/test_spatial_contract.py's
//: guard against a *second Python* literal does not apply to this single,
//: necessary crossing of the language boundary. If TERRAIN_AOI ever changes,
//: this must change with it.
const TERRAIN_AOI_WSEN: [number, number, number, number] = [34.75, 29.15, 35.94, 30.3];

//: Matches tile_terrain_rgb.py's own MAX_Z — MapLibre reuses the nearest
//: coarser tile above this, which is honest (visibly softer) rather than a
//: fabricated extra level of detail past what the source DEM/bathymetry
//: resolves (30 m / 50 m).
const TERRAIN_MAX_ZOOM = 12;

//: How high the real elevation reads versus how far apart things are on the
//: ground. 1.0 (no exaggeration) is an honest option; a modest boost makes
//: the coastal mountains and the reef-zone seafloor relief read clearly at
//: this scene's camera distances without the first pass's need for an
//: artificial sqrt-rescaling of the whole height budget. Shown in the
//: on-screen legend, not a silent multiplier.
export const TERRAIN_EXAGGERATION = 1.5;

export function terrainSourceFragment() {
  const source: RasterDEMSourceSpecification = {
    type: 'raster-dem',
    tiles: [TILE_URL],
    tileSize: 256,
    encoding: 'mapbox',
    maxzoom: TERRAIN_MAX_ZOOM,
    bounds: TERRAIN_AOI_WSEN,
  };
  return {
    sources: { terrain: source },
    layers: [] as const,
  };
}

//: The merged mesh's own real range (scripts/merge_terrain_bathymetry.py's
//: printed output: "-926 .. 1847 m") -- these are this run's actual data
//: bounds, not a generic hypsometric scale invented for the occasion. Colour
//: only, no elevation displacement: MapLibre's `color-relief` layer samples
//: the same raster-dem `terrain` source `map.setTerrain()` already reads for
//: mesh displacement -- this just textures it, on top of (not instead of)
//: that real 3D shape.
// A hypsometric tint, not UI chrome — which is why these are raw hex and carry
// `token-ok`. The ramp depicts real physical ground: measured bathymetry from the
// deepest cell in the merge, through the Gulf's own turquoise shelf cast, across
// the coastline seam, into sand, scree and bare rock. Mapping it onto the
// interface tokens would tie the shape of the seabed to the app's text palette
// and would change the terrain's appearance whenever the theme is retuned. Same
// exemption the neighbouring journey layers already hold for sky lighting and
// relief shading.
const ELEVATION_COLOR_STOPS: Array<[number, string]> = [
  [-926, '#0a2f4d'], // deepest real bathymetry cell in the merge (token-ok: hypsometric ramp)
  [-200, '#0f5c8a'],  // token-ok: hypsometric elevation ramp
  [-30, '#3fa7c9'], // shallow reef-depth water, Gulf's own turquoise cast (token-ok: hypsometric ramp)
  [-2, '#8fd6d9'],  // token-ok: hypsometric elevation ramp
  [0, '#e8dcb0'], // the real coastline seam -- sea/land boundary itself (token-ok: hypsometric ramp)
  [40, '#d9c48a'], // coastal plain, sand/desert (token-ok: hypsometric ramp)
  [250, '#c2a06a'],  // token-ok: hypsometric elevation ramp
  [700, '#a67c52'], // wadi flanks, bare rock and scree (token-ok: hypsometric ramp)
  [1200, '#8a7160'],  // token-ok: hypsometric elevation ramp
  [1847, '#e8e4de'], // the merge's highest real cell, pale exposed rock (token-ok: hypsometric ramp)
];

//: Fixed rather than theme-derived, same reasoning as rain.ts's white
//: ripple stroke: this is real-world ground colour, not app chrome, so it
//: does not repaint on the light/dark toggle -- only the sky and hillshade
//: tint around it do (journeyStyle.ts).
export function terrainColorFragment() {
  return {
    layers: [
      {
        id: 'terrain-color-relief',
        type: 'color-relief' as const,
        source: 'terrain',
        paint: {
          'color-relief-color': [
            'interpolate',
            ['linear'],
            ['elevation'],
            ...ELEVATION_COLOR_STOPS.flat(),
          ] as unknown as string,
        },
      },
    ],
  };
}
