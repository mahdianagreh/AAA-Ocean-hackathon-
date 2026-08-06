import type { Feature, FeatureCollection, Point } from 'geojson';
import type { Palette } from '../constants';

/** Heavy rainfall, rendered as animated impact ripples at real ground
 *  coordinates — not a screen-space overlay, not literal raindrop physics.
 *  Spatially real (every ripple sits at a real lon/lat within the release
 *  catchment's bounding box); temporally stylised (a repeating grow-and-fade
 *  cycle standing in for "rain is falling here now").
 *
 *  A fixed-size pool of seeds, generated once, is reused every tick —
 *  `rainFrameFeatures` never allocates a new seed, only a new (small) feature
 *  array from the same pool, so a long-running animation does not grow memory
 *  or trigger GC churn the way spawning-and-discarding particle objects would.
 *  `intensity` (0-1, driven by the real measured rainfall mm for this
 *  catchment — see journey3d.json's `rainfall` field) controls how many of
 *  the pool's slots are active, not the pool size itself.
 */

export const RAIN_POOL_SIZE = 220;
const RIPPLE_MAX_RADIUS_PX = 7;
const RIPPLE_LIFETIME_MS = 1400;

export interface RainSeed {
  lon: number;
  lat: number;
  phaseMs: number;
}

export function makeRainSeeds(bbox: [number, number, number, number], count = RAIN_POOL_SIZE): RainSeed[] {
  const [minLon, minLat, maxLon, maxLat] = bbox;
  const seeds: RainSeed[] = [];
  for (let i = 0; i < count; i++) {
    seeds.push({
      lon: minLon + Math.random() * (maxLon - minLon),
      lat: minLat + Math.random() * (maxLat - minLat),
      phaseMs: Math.random() * RIPPLE_LIFETIME_MS,
    });
  }
  return seeds;
}

export function rainFrameFeatures(
  seeds: RainSeed[],
  tMs: number,
  activeCount: number,
): FeatureCollection<Point, { radius: number; opacity: number }> {
  const features: Feature<Point, { radius: number; opacity: number }>[] = [];
  const n = Math.min(activeCount, seeds.length);
  for (let i = 0; i < n; i++) {
    const seed = seeds[i];
    const age = (tMs + seed.phaseMs) % RIPPLE_LIFETIME_MS;
    const progress = age / RIPPLE_LIFETIME_MS;
    features.push({
      type: 'Feature',
      properties: {
        radius: progress * RIPPLE_MAX_RADIUS_PX,
        opacity: 1 - progress,
      },
      geometry: { type: 'Point', coordinates: [seed.lon, seed.lat] },
    });
  }
  return { type: 'FeatureCollection', features };
}

const EMPTY_FC: FeatureCollection = { type: 'FeatureCollection', features: [] };

export function rainFragment(c: Palette) {
  return {
    sources: {
      rain: { type: 'geojson' as const, data: EMPTY_FC },
    },
    layers: [
      {
        id: 'rain-ripples',
        type: 'circle' as const,
        source: 'rain',
        paint: {
          'circle-radius': ['get', 'radius'] as unknown as number,
          'circle-opacity': ['*', ['get', 'opacity'], 0.75] as unknown as number,
          'circle-color': c.data_measured,
          // A white edge, not the fill colour again: real satellite imagery
          // (layers/imagery.ts) is a busy, high-frequency backdrop compared to
          // the flat relief bands this was first tuned against, and a same-
          // colour stroke on a 1-2 px ripple disappeared into it. White is
          // fixed rather than theme-derived because it is countering real
          // photo content, not app chrome, so it doesn't shift with the app's
          // own light/dark toggle.
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 1.5,
          'circle-stroke-opacity': ['*', ['get', 'opacity'], 0.9] as unknown as number,
          'circle-pitch-alignment': 'map',
        },
      },
    ],
  };
}
