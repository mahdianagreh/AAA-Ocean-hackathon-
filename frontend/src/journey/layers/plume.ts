import { PLUME_HEIGHT_PER_LEVEL_M, type Palette } from '../constants';

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
 *
 *  Base `0` + real terrain (layers/terrain.ts) anchors each contour ring to
 *  the real seafloor depth at its own centroid, extruded upward by a small
 *  probability-scaled amount (PLUME_HEIGHT_PER_LEVEL_M) — a reasonable
 *  approximation for this event's shallow, nearshore release (also the
 *  diffusion-dominated case documented in tasks/phase4/05-abd.md §1a), but
 *  not a claim that sediment plumes physically hug the seafloor everywhere:
 *  a genuinely deep-water release would need a surface-relative rendering
 *  mode this project does not have. MapLibre also samples one elevation per
 *  polygon (avoiding a per-vertex "tilted roof" artifact), so a contour ring
 *  large enough to span a real depth change takes its centroid's depth for
 *  the whole ring, not a per-point drape.
 */

const EMPTY_FC = { type: 'FeatureCollection' as const, features: [] };

//: Fixed, not theme-derived -- the same real Gulf water colour
//: layers/terrain.ts's colour-relief already uses for shallow water, reused
//: here rather than a third invented "water" hue.
const WATER_TINT_COLOR = '#2f7a82'; // token-ok: real shallow-water colour, matches terrain.ts/runoff.ts

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
      // The specimen gallery's own hazard-ramp rule ("every fill carries a
      // 1px stroke at the next band up — a fill alone is not a boundary")
      // applies here too: without this, four overlapping density rings at
      // similar warm tones read as one indistinct blob, especially once
      // draped over real satellite imagery's own texture. A flat outline on
      // the real footprint, not a per-vertex extruded edge (MapLibre has no
      // "outline the extrusion top" primitive) -- still a real boundary,
      // just read at the base rather than at height.
      {
        id: 'plume-outline',
        type: 'line' as const,
        source: 'plume-frame',
        paint: outlinePaint(),
      },
      // Without this, the sediment colours sit at full, dry-land saturation
      // with nothing in the scene suggesting water is between the camera and
      // the seafloor -- it reads as a sticker laid on top of the sea, not a
      // cloud suspended in it. A flat translucent wash over the plume's own
      // real outer footprint (filtered to the probability=0.1 ring, which
      // already contains every denser ring inside it, so this draws once per
      // frame, not four compounding washes) is a visual convention, not a
      // real depth-correct water-column render -- MapLibre has no
      // refraction/attenuation model, and this project does not pretend
      // otherwise anywhere else in this scene either (see this file's own
      // top-of-file note on `base=0`/seafloor placement).
      {
        id: 'plume-water-tint',
        type: 'fill' as const,
        source: 'plume-frame',
        filter: ['==', ['get', 'probability'], DENSITY_STOPS[0]] as unknown as boolean,
        paint: {
          'fill-color': WATER_TINT_COLOR,
          'fill-opacity': 0.38,
        },
      },
    ],
  };
}

//: The four real density levels this event's particle engine actually
//: produced (`journey3d.json`'s `frames[].contours[].probability`:
//: 0.10/0.25/0.50/0.75) -- interpolated at those exact real stops, not a
//: generic 0-1 range, so each real band gets its own real colour rather
//: than being smeared across a two-stop gradient.
const DENSITY_STOPS = [0.1, 0.25, 0.5, 0.75];

//: Floors the real sediment-index ratio (below) at a legibility minimum
//: rather than letting it reach 0 -- the same "sized/floored for legibility,
//: documented as a convention" pattern already used for
//: REEF_HIGHLIGHT_HEIGHT_M and the hotel building-height default. AQ-C02
//: (this journey's own release catchment) has a real formula-computed index
//: of ~9% of the anchor catchment's own -- rendered at literally 9% opacity
//: it would read as "the feature broke", not "this catchment carries real,
//: comparatively low, sediment", so the real ratio still scales the result,
//: just within a floor that keeps it legible.
const SEDIMENT_OPACITY_FLOOR = 0.4;

function clampIntensity(scale: number): number {
  return SEDIMENT_OPACITY_FLOOR + (1 - SEDIMENT_OPACITY_FLOOR) * Math.max(0, Math.min(1, scale));
}

//: Reuses the app's own risk palette rather than an invented brown (real
//: flash-flood sediment is not clear blue, but this project already has one
//: graduated warm ramp and the point is staying inside it, not picking a
//: prettier one). This is density, not hazard — the on-screen caption says
//: "real simulated plume", never "risk" — but colour-wise this is the only
//: graduated ramp in the palette, and `accumulationPaint` already reused it
//: before this change; this just extends the same precedent to `transport`.
//:
//: `sedimentIntensity` (0-1) is this catchment's own real sediment-proxy
//: index for this event, normalised against the real October 2016 anchor
//: (`journey3d.json`'s `sediment_index_normalized`, computed the same way
//: `POST /api/v1/exposure/calculate` would -- see frontend_journey.py's own
//: docstring) -- how much real sediment mass this specific catchment's own
//: formula says it carries, not a fixed constant applied everywhere.
export function transportPaint(c?: Palette, sedimentIntensity = 1) {
  const risk = c?.risk ?? { minimal: '#8a9a7a', low: '#9a8a6a', moderate: '#b07a4a', high: '#8a6a3a' }; // token-ok: unreachable fallback, palette is always supplied
  return {
    'fill-extrusion-color': [
      'interpolate', ['linear'], ['get', 'probability'],
      DENSITY_STOPS[0], risk.minimal,
      DENSITY_STOPS[1], risk.low,
      DENSITY_STOPS[2], risk.moderate,
      DENSITY_STOPS[3], risk.high,
    ] as unknown as string,
    'fill-extrusion-base': 0,
    'fill-extrusion-height': [
      '*', ['get', 'probability'], PLUME_HEIGHT_PER_LEVEL_M,
    ] as unknown as number,
    'fill-extrusion-opacity': 0.78 * clampIntensity(sedimentIntensity),
  };
}

/** One band denser than transport's own ramp (low->critical instead of
 *  minimal->high) — "this has settled", not "this is passing through", read
 *  through colour alone since the real contour geometry doesn't change
 *  between the two phases. Slightly taller too, for the same reason. Same
 *  real `sedimentIntensity` scaling as `transportPaint` — see its own
 *  comment. */
export function accumulationPaint(c: Palette, sedimentIntensity = 1) {
  return {
    'fill-extrusion-color': [
      'interpolate', ['linear'], ['get', 'probability'],
      DENSITY_STOPS[0], c.risk.low,
      DENSITY_STOPS[1], c.risk.moderate,
      DENSITY_STOPS[2], c.risk.high,
      DENSITY_STOPS[3], c.risk.critical,
    ] as unknown as string,
    'fill-extrusion-base': 0,
    'fill-extrusion-height': [
      '*', ['get', 'probability'], PLUME_HEIGHT_PER_LEVEL_M * 1.3,
    ] as unknown as number,
    'fill-extrusion-opacity': 0.92 * clampIntensity(sedimentIntensity),
  };
}

//: The matching stroke, one riskStroke band up from each fill's own colour
//: (the specimen gallery's convention, applied here for the first time).
//: Exported so Journey3D.tsx can switch it live alongside the fill when the
//: phase (and therefore the density->colour mapping) changes.
export function outlinePaint(c?: Palette, mode: 'transport' | 'accumulation' = 'transport') {
  const stroke = c?.riskStroke ?? { minimal: '#5a6a4a', low: '#6a5a3a', moderate: '#8a5a2a', high: '#6a4a1a', critical: '#4a2a1a' }; // token-ok: unreachable fallback, palette is always supplied
  const stops = mode === 'transport'
    ? [stroke.minimal, stroke.low, stroke.moderate, stroke.high]
    : [stroke.low, stroke.moderate, stroke.high, stroke.critical];
  return {
    'line-color': [
      'interpolate', ['linear'], ['get', 'probability'],
      DENSITY_STOPS[0], stops[0],
      DENSITY_STOPS[1], stops[1],
      DENSITY_STOPS[2], stops[2],
      DENSITY_STOPS[3], stops[3],
    ] as unknown as string,
    'line-width': 1.5,
    'line-opacity': 0.9,
  };
}
