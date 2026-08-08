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
