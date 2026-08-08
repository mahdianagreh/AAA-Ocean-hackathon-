/** The 3D Journey's shared phase vocabulary, plus the small legibility
 *  constants layers need now that terrain is real.
 *
 *  With `map.setTerrain()` active (`layers/terrain.ts`), MapLibre adds the
 *  real terrain elevation at a feature's own position to both
 *  `fill-extrusion-base` and `fill-extrusion-height` (confirmed directly in
 *  the installed maplibre-gl bundle's fill-extrusion vertex shader, not
 *  assumed) — so `base: 0` already means "sits on the real ground/seafloor,"
 *  not an abstract zero. That retires the first pass's stacked, sqrt-scaled
 *  height budget entirely: there is no longer a shared "who sits above whom"
 *  problem to solve here, because everything now sits at its own true
 *  position. What is left is only the small, honestly-documented "how tall
 *  should the stylised part be" numbers below, kept per-layer in this file
 *  only so they are easy to find and compare, not because they interact.
 */

import { palette, type ThemeName } from '../design/palette.generated';

//: One shared alias for "the resolved colour object for a theme" — palette.generated.ts
//: exports the theme map but not this type, and every layer module needs it.
export type Palette = (typeof palette)[ThemeName];

export type JourneyPhase =
  | 'normal'
  | 'rain'
  | 'flood'
  | 'transport'
  | 'accumulation'
  | 'impact';

export const PHASE_ORDER: JourneyPhase[] = [
  'normal',
  'rain',
  'flood',
  'transport',
  'accumulation',
  'impact',
];

//: How long the autoplay spends in each non-normal phase before advancing.
//: `transport` is stepped internally (one plume frame at a time) rather than
//: timer-advanced — see usePhaseTimeline.
export const PHASE_DURATION_MS: Record<JourneyPhase, number> = {
  normal: 0,
  rain: 3200,
  flood: 3200,
  transport: 0, // driven by frame count x PLUME_FRAME_MS instead
  accumulation: 2600,
  impact: 3200,
};

export const PLUME_FRAME_MS = 1500;

//: Real reef structure is a thin veneer on the seafloor, nowhere near this
//: tall — this is a legibility convention (a visible raised "chip" at the
//: zone's true depth) so a 1.235 km² real footprint reads as a distinct
//: volume from an oblique camera, not a claim about coral relief.
export const REEF_HIGHLIGHT_HEIGHT_M = 10;

//: Real metres of extrusion per unit of the plume's real contour probability
//: (0.10-0.75, see layers/plume.ts). Chosen small deliberately: the demo
//: release point is shallow/nearshore, and this keeps even the highest-
//: probability core from visually erupting past the sea surface there. A
//: release into genuinely deep water would need a surface-relative rendering
//: mode this project does not have yet — see layers/plume.ts's own
//: docstring for the honest limitation this leaves.
export const PLUME_HEIGHT_PER_LEVEL_M = 30;
