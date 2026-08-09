import type { Geometry } from 'geojson';

/** The falling half of the rain effect — a screen-space canvas overlay
 *  drawn on top of the 3D scene, not real-world geometry. This is a
 *  deliberate, honest step away from "everything in this scene has a real
 *  lon/lat": a raindrop's fall is a few metres in well under a second, which
 *  is sub-pixel and motionless-looking at the kilometre-scale zoom the
 *  "heavy rain" phase's camera holds. No real placement would be visible
 *  as falling at that distance — only screen-space motion reads as motion
 *  here, the same reason a rain-on-window screen effect is drawn in screen
 *  space in every weather app and film, not modelled as physical droplets
 *  at world scale.
 *
 *  It IS confined to real geometry, though: each catchment that measured
 *  real rainfall on the event's peak day (`journey3d.json`'s
 *  `rainfall_by_catchment`, all five real catchments, not just the release
 *  one — 2016-10-27 was a regional storm) gets its own clipped rain patch,
 *  built from that catchment's own real polygon projected to screen space
 *  every frame. A first version covered the whole visible scene regardless
 *  of catchment boundaries, which read as "it is raining everywhere,
 *  including the sea and neighbouring catchments" — wrong on both the
 *  geography and, implicitly, the data (only these five real catchments
 *  have a measured value for this day; nothing else does).
 *
 *  `rain.ts`'s ground ripples remain the separate, finer-grained real
 *  per-lon/lat signal within the release catchment specifically.
 */

export interface RainStreak {
  x: number; // canvas px
  y: number; // canvas px; runs above 0 while "still falling in" from off-screen
  length: number; // px, derived from speed so faster drops read as longer motion blur
  speed: number; // px/second
  drift: number; // px of rightward lean per px fallen (a light prevailing wind)
  width: number; // px
}

export interface ScreenBounds {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

const TRAIL_SECONDS = 0.075; // how long a streak's own motion blur trail is, in time-at-speed

export function createRainStreaks(widthPx: number, heightPx: number, count: number): RainStreak[] {
  const streaks: RainStreak[] = [];
  for (let i = 0; i < count; i++) {
    const speed = 900 + Math.random() * 700;
    streaks.push({
      x: Math.random() * widthPx * 1.15 - widthPx * 0.075,
      y: Math.random() * heightPx - heightPx,
      length: speed * TRAIL_SECONDS,
      speed,
      drift: 0.16 + Math.random() * 0.08,
      width: 1.4 + Math.random() * 1.3,
    });
  }
  return streaks;
}

export function stepRainStreaks(streaks: RainStreak[], widthPx: number, heightPx: number, dtSeconds: number): void {
  for (const s of streaks) {
    s.y += s.speed * dtSeconds;
    s.x += s.drift * s.speed * dtSeconds;
    if (s.y > heightPx + s.length || s.x > widthPx + 40) {
      s.y = -s.length - Math.random() * heightPx * 0.5;
      s.x = Math.random() * widthPx * 1.15 - widthPx * 0.075;
    }
  }
}

//: Real lon/lat ring coordinates -> a canvas Path2D in the same CSS-pixel
//: space `map.project()` returns, which is what the overlay canvas is drawn
//: in (Journey3D.tsx's resize effect sets the same transform). Handles both
//: shapes real catchment geometry can take -- none of the five are actually
//: multi-part, but a real GeoJSON producer is never guaranteed to stay that
//: way, and silently drawing only the first part of a MultiPolygon would be
//: the same "plausible, wrong output with no error" failure mode this
//: project's other layers document by name.
export function geometryToScreenPath(
  geometry: Geometry,
  project: (lon: number, lat: number) => { x: number; y: number },
): { path: Path2D; bounds: ScreenBounds } {
  const path = new Path2D();
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  const addRing = (ring: number[][]) => {
    ring.forEach(([lon, lat], i) => {
      const p = project(lon, lat);
      if (i === 0) path.moveTo(p.x, p.y);
      else path.lineTo(p.x, p.y);
      x0 = Math.min(x0, p.x); y0 = Math.min(y0, p.y);
      x1 = Math.max(x1, p.x); y1 = Math.max(y1, p.y);
    });
    path.closePath();
  };
  if (geometry.type === 'Polygon') {
    geometry.coordinates.forEach(addRing);
  } else if (geometry.type === 'MultiPolygon') {
    geometry.coordinates.forEach((poly) => poly.forEach(addRing));
  }
  return { path, bounds: { x0, y0, x1, y1 } };
}

export function clearRainCanvas(ctx: CanvasRenderingContext2D, widthPx: number, heightPx: number): void {
  ctx.clearRect(0, 0, widthPx, heightPx);
}

//: `intensity` (0-1, this specific catchment's own real measured mm for the
//: event's peak day, over the same reference ceiling `rain.ts`'s ripples
//: use) scales how dark the storm wash and how strong the streaks read, so a
//: catchment with real rainfall data.
//:
//: Colours are fixed rather than theme/accent-derived, same reasoning as
//: rain.ts's ripple stroke: the terrain under it spans real warm sand, brown
//: rock and blue-to-turquoise sea (layers/terrain.ts's colour-relief), so a
//: single mid-tone accent hue is guaranteed to disappear against one of
//: them. A bright near-white stroke over a dark outline reads against any of
//: those grounds, and the dark overhead wash is what a real storm's own
//: light looks like, not app chrome repainting on theme toggle.
const STREAK_COLOR = 'rgba(235, 248, 250, 1)';
const STREAK_OUTLINE_COLOR = 'rgba(10, 22, 28, 1)';
const SKY_WASH_TOP = 'rgba(10, 20, 26, 0.5)';
const SKY_WASH_BOTTOM = 'rgba(10, 20, 26, 0)';

//: Draws into `clipPath` only (`ctx.clip`) -- the caller is responsible for
//: `clearRainCanvas` once per frame *before* looping catchments, since this
//: function itself must not clear what a previous catchment in the same
//: frame already painted.
export function paintRainInClip(
  ctx: CanvasRenderingContext2D,
  canvasWidthPx: number,
  canvasHeightPx: number,
  streaks: RainStreak[],
  clipPath: Path2D,
  intensity: number,
): void {
  // No floor: intensity 0 must mean no visible rain, not "a slightly dimmer
  // storm" -- a catchment with a low real mm value has to actually look like
  // light rain, not heavy rain at 90% strength. A drizzle also uses fewer
  // streaks, not just fainter ones (real light rain is sparse, not just
  // pale), so only a real-mm-proportional slice of the shared pool is drawn
  // at all (see `activeCount` below).
  ctx.save();
  ctx.clip(clipPath);

  const washAlpha = 0.7 * intensity;
  if (washAlpha > 0.01) {
    const gradient = ctx.createLinearGradient(0, 0, 0, canvasHeightPx * 0.6);
    gradient.addColorStop(0, SKY_WASH_TOP);
    gradient.addColorStop(1, SKY_WASH_BOTTOM);
    ctx.globalAlpha = washAlpha;
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, canvasWidthPx, canvasHeightPx);
  }

  ctx.lineCap = 'round';
  const baseAlpha = 0.95 * intensity;
  const activeCount = Math.round(streaks.length * Math.min(1, intensity * 1.3));
  for (const s of streaks.slice(0, activeCount)) {
    const xTop = s.x;
    const yTop = s.y;
    const yBot = yTop + s.length;
    const xBot = xTop + s.length * s.drift;
    if (yBot < 0 || yTop > canvasHeightPx) continue;
    const fadeIn = Math.min(1, (s.y + canvasHeightPx * 0.5) / (canvasHeightPx * 0.25));
    const alpha = baseAlpha * Math.max(0, fadeIn);
    if (alpha <= 0) continue;

    ctx.globalAlpha = alpha * 0.6;
    ctx.strokeStyle = STREAK_OUTLINE_COLOR;
    ctx.lineWidth = s.width + 1.6;
    ctx.beginPath();
    ctx.moveTo(xTop, yTop);
    ctx.lineTo(xBot, yBot);
    ctx.stroke();

    ctx.globalAlpha = alpha;
    ctx.strokeStyle = STREAK_COLOR;
    ctx.lineWidth = s.width;
    ctx.beginPath();
    ctx.moveTo(xTop, yTop);
    ctx.lineTo(xBot, yBot);
    ctx.stroke();
  }
  ctx.restore();
  ctx.globalAlpha = 1;
}

export interface CloudAnchor {
  centerX: number;
  topY: number;
  widthPx: number;
  intensity: number;
}

const CLOUD_COLOR = 'rgba(96, 104, 112, 1)';
const CLOUD_HIGHLIGHT = 'rgba(168, 178, 184, 1)';

//: Not clipped to the catchment polygon -- real clouds sit visibly above and
//: a little beyond the ground footprint they're raining on, so clipping them
//: to the exact polygon edge would look like the cloud was cut with
//: scissors. `timeSec` drives a slow drift so the sky doesn't look painted
//: on; the drift amplitude is deliberately small enough that a cloud stays
//: over its own catchment rather than wandering into a neighbour's.
export function drawClouds(ctx: CanvasRenderingContext2D, anchors: CloudAnchor[], timeSec: number): void {
  for (const a of anchors) {
    // No floor here either: a catchment with barely any real rain gets a
    // thin wisp, not the same dark mass a downpour gets at 70% strength. Size
    // shrinks with intensity too -- a drizzle's cloud is a small, pale patch,
    // not a full-size storm cloud dimmed down.
    if (a.intensity <= 0.02) continue;
    const scale = 0.55 + 0.45 * a.intensity;
    const drift = Math.sin(timeSec * 0.12 + a.centerX * 0.01) * a.widthPx * 0.06;
    const baseY = a.topY - a.widthPx * 0.16 - 20;
    const lobes = [
      { dx: -a.widthPx * 0.26, dy: a.widthPx * 0.05, r: a.widthPx * 0.32 * scale },
      { dx: 0, dy: -a.widthPx * 0.04, r: a.widthPx * 0.4 * scale },
      { dx: a.widthPx * 0.28, dy: a.widthPx * 0.06, r: a.widthPx * 0.3 * scale },
    ];
    for (const lobe of lobes) {
      const x = a.centerX + drift + lobe.dx;
      const y = baseY + lobe.dy;
      const r = Math.max(14, lobe.r);

      // A soft dark base (reads against sky/terrain) with a lighter,
      // smaller highlight offset toward the top-left -- the same two-tone
      // trick that turns a flat grey disc into a shape that reads as a
      // puffy cloud rather than a smudge, without needing a texture asset.
      const base = ctx.createRadialGradient(x, y, 0, x, y, r);
      base.addColorStop(0, CLOUD_COLOR);
      base.addColorStop(1, 'rgba(96, 104, 112, 0)');
      ctx.globalAlpha = 0.85 * a.intensity;
      ctx.fillStyle = base;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();

      const hx = x - r * 0.25;
      const hy = y - r * 0.3;
      const hr = r * 0.55;
      const highlight = ctx.createRadialGradient(hx, hy, 0, hx, hy, hr);
      highlight.addColorStop(0, CLOUD_HIGHLIGHT);
      highlight.addColorStop(1, 'rgba(168, 178, 184, 0)');
      ctx.globalAlpha = 0.65 * a.intensity;
      ctx.fillStyle = highlight;
      ctx.beginPath();
      ctx.arc(hx, hy, hr, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  ctx.globalAlpha = 1;
}
