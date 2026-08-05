import { Glyph, type GlyphProps } from './Glyph';

/** Catchment — a drainage basin.
 *
 *  Drawn as nested contour rings narrowing to a single outflow, which is what a
 *  catchment is on a chart: closed elevation contours plus the one place the
 *  water leaves. Wadi Yutum is 4,453 km² draining from 90 km inland to a single
 *  outlet, so "many contours, one exit" is the honest shape. */
export function CatchmentGlyph(p: GlyphProps) {
  return (
    <Glyph {...p}>
      <path d="M3 6.5c3.2-2.2 6-1.1 9 .4s5.6 2 9-.4" />
      <path d="M4 11c2.8-1.9 5.2-.9 7.8.4S16.6 13 19.6 11" />
      <path d="M6 15.4c2-1.3 3.6-.6 5.4.3s3.2 1 5.2-.3" />
      <path d="M12 16.2V21" />
      <path d="M9.6 19.2 12 21.4l2.4-2.2" />
    </Glyph>
  );
}

/** Coastal outlet — where a wadi meets the sea.
 *
 *  A channel crossing a shoreline, with the shoreline continuing either side.
 *  The channel is the emphasis because the outlet is a point on the coast, not a
 *  river: AQ-O01 carries 96% of the discharge and is the demo path. */
export function OutletGlyph(p: GlyphProps) {
  return (
    <Glyph {...p}>
      <path d="M3 15h5.5" />
      <path d="M15.5 15H21" />
      <path d="M10 4.5c0 3.4-1.5 5-1.5 7.2 0 1.6.7 2.4.7 3.3" />
      <path d="M14 4.5c0 3.4 1.5 5 1.5 7.2 0 1.6-.7 2.4-.7 3.3" />
      <path d="M5.5 19c1.6-1.1 3-1.1 4.6 0s3.3 1.1 4.9 0 3-1.1 4.5 0" />
    </Glyph>
  );
}

/** Reef zone — branching coral on a seabed, with the shoreline alongside.
 *
 *  The first version drew the shoreline plus two parallel offset arcs, which was
 *  conceptually right — a fringing band held metres off the coast — and visually
 *  wrong: at 24px it read as a wifi or broadcast icon. Branching coral rising
 *  from a seabed line is the unambiguous reef signifier, and it still carries the
 *  fringing relationship because the shoreline sits right beside it.
 *
 *  Jordan's reef runs over 25 km of a 27 km coast, so the shoreline belongs in
 *  the glyph: R-01…R-08 are stretches of coast, not offshore points. */
export function ReefZoneGlyph(p: GlyphProps) {
  return (
    <Glyph {...p}>
      {/* shoreline */}
      <path d="M4 2.5c0 4-1 6-1 9.5s1 5.5 1 9.5" />
      {/* seabed */}
      <path d="M7 18.5h14" />
      {/* branching coral, two heads at different heights */}
      <path d="M11 18.5v-5" />
      <path d="M11 15l-2-2" />
      <path d="M11 14.6l2.2-2.4" />
      <path d="M17 18.5v-8" />
      <path d="M17 13.5l-2.4-2.6" />
      <path d="M17 12.2l2.4-2.6" />
    </Glyph>
  );
}

export { Glyph };
