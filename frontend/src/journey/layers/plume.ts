import { PLUME_BASE_M, PLUME_HEIGHT_PER_LEVEL_M, type Palette } from '../constants';

/** The plume — real particle-engine contours, one real timestep at a time
 *  (`journey3d.json`'s `frames`, from a live run of the same calibrated engine
 *  item 1 wires in). `probability` is the KDE contour's real peak-normalized
 *  density level (0.10-0.75) — see particle_engine.kernel_density_contours —
 *  never a calibrated arrival probability, and the on-screen caption says so.
 *
 *  Two paint modes, same layer, switched live via setPaintProperty rather than
 *  two competing layers: **transport** (turbid, lighter, colour graded by
 *  density — sediment in motion) and **accumulation** (denser, darker,
 *  near-opaque — sediment settling out). The geometry itself doesn't change
 *  between modes; only its visual treatment does, because the real contour
 *  data does not distinguish "still moving" from "has settled" — the particle
 *  engine's own settled/beached tracking exists in `SimulationResult` but is
 *  not yet exposed via the API (see docs/HANDOFF_abd_2026-08-06.md §5's
 *  "what a genuine volumetric cloud would still need"), so accumulation here
 *  is an honest visual convention over the real final-timestep shape, not a
 *  second real signal.
 */

const EMPTY_FC = { type: 'FeatureCollection' as const, features: [] };

export function plumeFragment() {
  return {
    sources: {
      'plume-frame': { type: 'geojson' as const, data: EMPTY_FC },
    },
    layers: [
      {
        id: 'plume-extrusion',
        type: 'fill-extrusion' as const,
        source: 'plume-frame',
        paint: transportPaint(),
      },
    ],
  };
}

export function transportPaint(c?: Palette) {
  return {
    'fill-extrusion-color': [
      'interpolate', ['linear'], ['get', 'probability'],
      0.1, c?.data_modelled ?? '#8a9a7a',
      0.75, c?.accent ?? '#3a8a6a',
    ] as unknown as string,
    'fill-extrusion-base': PLUME_BASE_M,
    'fill-extrusion-height': [
      '+', PLUME_BASE_M, ['*', ['get', 'probability'], PLUME_HEIGHT_PER_LEVEL_M],
    ] as unknown as number,
    'fill-extrusion-opacity': 0.7,
  };
}

/** Muddier, denser, slightly taller — "this has settled," not "this is
 *  passing through." Real colours from the existing risk palette (a desaturated
 *  high-band tone) rather than an invented brown, so the scene's whole colour
 *  system still traces to one palette. */
export function accumulationPaint(c: Palette) {
  return {
    'fill-extrusion-color': [
      'interpolate', ['linear'], ['get', 'probability'],
      0.1, c.riskStroke.moderate,
      0.75, c.riskStroke.high,
    ] as unknown as string,
    'fill-extrusion-base': PLUME_BASE_M,
    'fill-extrusion-height': [
      '+', PLUME_BASE_M, ['*', ['get', 'probability'], PLUME_HEIGHT_PER_LEVEL_M * 1.3],
    ] as unknown as number,
    'fill-extrusion-opacity': 0.92,
  };
}
