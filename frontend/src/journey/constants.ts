/** The 3D Journey's shared height budget and phase vocabulary.
 *
 *  One file so the "does this layer sit above or inside that one" question has
 *  a single source of truth instead of five magic numbers duplicated across
 *  layer modules. Every constant here is a VISUAL metres value (post-scaling),
 *  not a real one — real values (depth, building height, rainfall) live in the
 *  fixture/basemap data; these constants only decide how that real number maps
 *  onto a legible, non-overlapping 3D stack.
 *
 *  Why sqrt scaling, not linear (the first version of this scene used linear
 *  x6, which put a real -800 m seafloor band at an exaggerated 4,800 m and a
 *  1,800 m mountain band at 10,800 m — both comfortably outside the camera's
 *  frustum at any pitch that also shows the coastline, which is what actually
 *  happened when reef/plume were floated above it). sqrt keeps every band's
 *  *relative* ordering (deeper/higher still reads as taller) while compressing
 *  the outliers enough that the whole real range (-800 m to +1,800 m) fits
 *  under ~600 visual metres — small enough that everything else in the scene
 *  can sit a modest, fixed clearance above the tallest band actually near the
 *  coast, without a repeat of the same problem.
 */

import { palette, type ThemeName } from '../design/palette.generated';

//: One shared alias for "the resolved colour object for a theme" — palette.generated.ts
//: exports the theme map but not this type, and every layer module needs it.
export type Palette = (typeof palette)[ThemeName];

export const RELIEF_HEIGHT_SCALE = 15; // visual metres per sqrt(real metre)

export function reliefVisualHeight(midM: number): number {
  return Math.sqrt(Math.abs(midM)) * RELIEF_HEIGHT_SCALE;
}

//: The tallest relief band actually near the coast (land 50-150 m real, the
//: immediate waterfront/port terrain outlets and buildings sit on) — NOT the
//: tallest band anywhere in the AOI (far-inland peaks reach higher but never
//: spatially coincide with buildings/reef/plume, so they don't need clearance
//: from them). Every layer below is based above this, not above the AOI max.
const COASTAL_RELIEF_CEILING_M = reliefVisualHeight(150); // ~184 m

export const BUILDINGS_BASE_M = COASTAL_RELIEF_CEILING_M + 10;
export const REEF_BASE_M = BUILDINGS_BASE_M + 60;
export const REEF_HEIGHT_M = REEF_BASE_M + 40;
export const PLUME_BASE_M = REEF_HEIGHT_M + 40;
//: Real plume `probability` (0.10-0.75, kernel_density_contours' own
//: peak-normalized levels) x this = visual extrusion height added on top of
//: PLUME_BASE_M.
export const PLUME_HEIGHT_PER_LEVEL_M = 220;

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
