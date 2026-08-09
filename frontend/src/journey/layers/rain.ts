import type { Feature, FeatureCollection, Point } from 'geojson';
import type { Palette } from '../constants';

/** Heavy rainfall's ground signal — animated impact ripples at real ground
 *  coordinates. The *falling* half of the effect (rain descending from the
 *  sky) is a separate, deliberately screen-space overlay (`rainOverlay.ts`,
 *  drawn in `Journey3D.tsx`) rather than real-world 3D geometry: an earlier
 *  version placed real lon/lat/height "streak" volumes in the scene, but at
 *  the kilometre-scale zoom this phase's camera holds, a metre-scale object
 *  is sub-pixel or reads as a static blob, not a falling motion — the
 *  camera distance defeats the realism before it can be seen. A screen-space
 *  streak has no such floor.
 *
 *  This module keeps only the honest part geography actually buys: a real
 *  ripple sits at a real lon/lat within the release catchment's bounding
 *  box, spatially real even though its grow-and-fade timing is a stylised
 *  stand-in for "rain is landing here now", not measured impact physics.
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
const RIPPLE_MAX_RADIUS_PX = 6;
const RIPPLE_LIFETIME_MS = 900;

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
          'circle-opacity': ['*', ['get', 'opacity'], 0.85] as unknown as number,
          'circle-color': c.accent,
          // A white edge, not the fill colour again: real satellite imagery
          // (layers/imagery.ts) is a busy, high-frequency backdrop compared to
          // the flat relief bands this was first tuned against, and a same-
          // colour stroke on a 1-2 px ripple disappeared into it. White is
          // fixed rather than theme-derived because it is countering real
          // photo content, not app chrome, so it doesn't shift with the app's
          // own light/dark toggle.
          'circle-stroke-color': '#ffffff', // token-ok: reads against satellite photo, not app chrome
          'circle-stroke-width': 1.5,
          'circle-stroke-opacity': ['*', ['get', 'opacity'], 0.9] as unknown as number,
          'circle-pitch-alignment': 'map',
        },
      },
    ],
  };
}
