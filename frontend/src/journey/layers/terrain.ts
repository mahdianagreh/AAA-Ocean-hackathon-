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

//: Matches tile_terrain_rgb.py's own MIN_Z -- tiles below this zoom were
//: never baked at all. Stops MapLibre requesting tiles for zoom levels that
//: don't exist on disk, matching MapLibre's own documented *overzoom*
//: behaviour (reuse the nearest baked tile) to the *underzoom* direction.
//:
//: This is necessary but NOT sufficient on its own -- the real AOI is
//: barely one tile column wide even at z7 (`ls public/terrain/7` -> only
//: `76/52.png` and `76/53.png`), so a viewport merely *allowed* down to z7
//: can still pan or zoom to frame area beyond real tile coverage, and
//: `color-relief`/hillshade -- both reading this same `terrain` source --
//: render that void as stretched, streaky garbage rather than nothing.
//: Confirmed two ways: scroll-wheel zoom-out from the app's own default
//: view, and a plain hard drag at z7, both without touching pitch at all.
//:
//: Constraining the *camera* to prevent this (`maxBounds` on the Map) was
//: tried and reverted -- it fights MapLibre's own pitch handling badly
//: enough that an ordinary drag silently jumped the center and changed
//: zoom on its own, which is the worse of the two problems. The fix that
//: actually holds without restricting movement is `terrainVoidMaskFragment`
//: below: a plain fill layer, painted over color-relief/hillshade, that
//: repaints anything outside the real AOI back to the app's own background
//: tone -- so the glitch has nothing left to show regardless of where the
//: camera points.
export const TERRAIN_MIN_ZOOM = 7;

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
    minzoom: TERRAIN_MIN_ZOOM,
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
const ELEVATION_COLOR_STOPS: Array<[number, string]> = [
  [-926, '#0a2f4d'], // deepest real bathymetry cell in the merge
  [-200, '#0f5c8a'],
  [-30, '#3fa7c9'], // shallow reef-depth water, Gulf's own turquoise cast
  [-2, '#8fd6d9'],
  [0, '#e8dcb0'], // the real coastline seam -- sea/land boundary itself
  [40, '#d9c48a'], // coastal plain, sand/desert
  [250, '#c2a06a'],
  [700, '#a67c52'], // wadi flanks, bare rock and scree
  [1200, '#8a7160'],
  [1847, '#e8e4de'], // the merge's highest real cell, pale exposed rock
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

//: Matches fetch_journey_wide_imagery.py's own `--pad` default exactly --
//: that script's real, fetched imagery is what this hole needs to line up
//: with, not the tight TERRAIN_AOI. If that script's default ever changes,
//: this must change with it (same one-necessary-duplication reasoning as
//: TERRAIN_AOI_WSEN above; there is no shared config file across the
//: language boundary for either).
const WIDE_IMAGE_PAD_FRACTION = 1.2;

function widePaddedAoiWsen(): [number, number, number, number] {
  const [w, s, e, n] = TERRAIN_AOI_WSEN;
  const dx = (e - w) * WIDE_IMAGE_PAD_FRACTION;
  const dy = (n - s) * WIDE_IMAGE_PAD_FRACTION;
  return [w - dx, s - dy, e + dx, n + dy];
}

//: One polygon, world-sized outer ring with the wide bake's own real, padded
//: extent cut out as a hole (GeoJSON winding: CCW exterior, CW hole, per
//: spec) -- everywhere beyond even that. Sized to the *wide* image, not the
//: tight TERRAIN_AOI: this layer draws above the imagery layers
//: (journeyStyle.ts / Journey3D.tsx), so a hole any smaller would paint the
//: mask right back over the wide bake's own real ground. -85/85 rather than
//: the poles because this style is `projection: { type: 'mercator' }`, which
//: is undefined past ~85.05 deg.
function terrainVoidGeometry() {
  const [w, s, e, n] = widePaddedAoiWsen();
  return {
    type: 'Feature' as const,
    properties: {},
    geometry: {
      type: 'Polygon' as const,
      coordinates: [
        [
          [-180, -85],
          [180, -85],
          [180, 85],
          [-180, 85],
          [-180, -85],
        ],
        [
          [w, s],
          [w, n],
          [e, n],
          [e, s],
          [w, s],
        ],
      ],
    },
  };
}

//: Drawn above `terrain-color-relief`/`terrain-hillshade` (journeyStyle.ts's
//: layer order), below everything real (imagery, catchments, buildings,
//: reef, plume) -- repaints the glitching void back to the app's own `bg`
//: layer colour, so free camera movement can never expose the streaked
//: artifact layers/terrain.ts's TERRAIN_MIN_ZOOM doc names. Matches `bg`
//: exactly (same isDark ternary) rather than a new colour, so the seam
//: between "real terrain" and "masked void" is invisible, not a visible
//: second background.
export function terrainVoidMaskFragment(isDark: boolean, canvasColor: string) {
  return {
    sources: {
      'terrain-void': { type: 'geojson' as const, data: terrainVoidGeometry() },
    },
    layers: [
      {
        id: 'terrain-void-mask',
        type: 'fill' as const,
        source: 'terrain-void',
        paint: {
          'fill-color': isDark ? '#020a0d' : canvasColor, // token-ok: matches bg exactly, see journeyStyle.ts
        },
      },
    ],
  };
}
