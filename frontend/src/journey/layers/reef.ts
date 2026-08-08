import { REEF_HIGHLIGHT_HEIGHT_M, type Palette } from '../constants';

/** Reef zones — real Allen Coral Atlas geometry, coloured by the real
 *  exposure result for this run. Neutral (one flat, uncoloured tone) until the
 *  "impact" phase reveals the real risk colour — the before/after the user
 *  asked for, built from one already-real fixture field
 *  (`reef_exposure`) rather than two different data sources.
 *
 *  A zone the plume never reached carries no colour at reveal either (falls
 *  through the `match` to the same neutral tone) — never a fabricated
 *  zero-risk tint for "not measured."
 *
 *  Base `0` + real terrain (layers/terrain.ts) means this sits at the zone's
 *  own true seafloor depth, not an abstract stacked height — see
 *  REEF_HIGHLIGHT_HEIGHT_M's own docstring for why the extrusion is taller
 *  than real coral relief.
 */

const url = (name: string) => `${import.meta.env.BASE_URL}basemap/${name}.geojson`;

export function reefFragment(c: Palette) {
  return {
    sources: {
      reef: { type: 'geojson' as const, data: url('reef_zones') },
    },
    layers: [
      {
        id: 'reef-extrusion',
        type: 'fill-extrusion' as const,
        source: 'reef',
        paint: {
          'fill-extrusion-color': c.ink_3,
          'fill-extrusion-base': 0,
          'fill-extrusion-height': REEF_HIGHLIGHT_HEIGHT_M,
          'fill-extrusion-opacity': 0.95,
        },
      },
      // Every hazard fill carries a stroke at the next band up — the same
      // convention the 2D map's reef-line layer already uses (map/style.ts).
      // A small footprint (reef zones total 1.235 km²) reads as a coloured
      // smudge without this; the outline is what makes "this specific real
      // polygon changed colour" legible against the relief underneath it.
      {
        id: 'reef-outline',
        type: 'line' as const,
        source: 'reef',
        paint: {
          'line-color': c.ink,
          'line-width': 2,
        },
      },
    ],
  };
}

/** The impact-phase reveal: a real `match` on `reef_zone_id` -> the real
 *  risk-band colour, applied via `setPaintProperty` rather than rebuilt into
 *  the style — so this is a live transition, not a restyle flash. */
export function reefRiskColorExpression(
  c: Palette,
  exposure: Array<{ reef_zone_id: string; risk_level: string }>,
): string {
  const bands = c.risk as Record<string, string>;
  if (exposure.length === 0) return c.ink_3;
  return [
    'match',
    ['get', 'reef_zone_id'],
    ...exposure.flatMap((r) => [r.reef_zone_id, bands[r.risk_level] ?? c.ink_3]),
    c.ink_3,
  ] as unknown as string;
}

export function reefStrokeExpression(
  c: Palette,
  exposure: Array<{ reef_zone_id: string; risk_level: string }>,
): string {
  const strokes = c.riskStroke as Record<string, string>;
  if (exposure.length === 0) return c.ink;
  return [
    'match',
    ['get', 'reef_zone_id'],
    ...exposure.flatMap((r) => [r.reef_zone_id, strokes[r.risk_level] ?? c.ink]),
    c.ink,
  ] as unknown as string;
}
