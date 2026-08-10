/** The flood phase's actual "this is flowing water" signal — a screen-space
 *  canvas animation of particles travelling along the real wadi centrelines
 *  (`journey3d.json`'s `runoff_lines`), not a MapLibre dashed line. A dashed
 *  line reads as "a line with a marching pattern"; real moving water reads
 *  as turbulent surface texture with real direction and real speed, which a
 *  handful of discrete dash segments cannot fake no matter how fast they
 *  cycle. Same reasoning `rainOverlay.ts` already documents for rain: some
 *  motion only reads as motion in screen space, at a resolution finer than
 *  the map's own real geometry can carry at this camera distance.
 *
 *  Direction is real, not assumed: each line's own two endpoints are
 *  compared by real distance to the release outlet, and the closer one is
 *  downstream — particles always travel toward the outlet, never away from
 *  it, without relying on OSM's own arbitrary digitisation direction for the
 *  wadi geometry (which carries no guaranteed upstream/downstream order).
 */

export interface FlowPath {
  points: { x: number; y: number }[]; // screen px, ordered upstream -> downstream
  cumulative: number[]; // cumulative arc length in px, same length as points
  totalLength: number;
}

export function buildFlowPaths(
  lines: number[][][],
  project: (lon: number, lat: number) => { x: number; y: number },
  downstreamLonLat: [number, number],
): FlowPath[] {
  const dist = (a: number[], b: [number, number]) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  return lines
    .filter((coords) => coords.length >= 2)
    .map((coords) => {
      const first = coords[0];
      const last = coords[coords.length - 1];
      const ordered = dist(last, downstreamLonLat) <= dist(first, downstreamLonLat) ? coords : [...coords].reverse();
      const points = ordered.map(([lon, lat]) => project(lon, lat));
      const cumulative = [0];
      for (let i = 1; i < points.length; i++) {
        cumulative.push(cumulative[i - 1] + Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y));
      }
      return { points, cumulative, totalLength: Math.max(1, cumulative[cumulative.length - 1]) };
    });
}

interface PathPoint {
  x: number;
  y: number;
  tx: number; // unit tangent x (downstream direction)
  ty: number; // unit tangent y
}

function pointAtDistance(path: FlowPath, distPx: number): PathPoint {
  const d = ((distPx % path.totalLength) + path.totalLength) % path.totalLength;
  let i = 1;
  while (i < path.cumulative.length - 1 && path.cumulative[i] < d) i++;
  const i0 = Math.max(0, i - 1);
  const i1 = Math.min(path.points.length - 1, i);
  const segLen = path.cumulative[i1] - path.cumulative[i0] || 1;
  const t = (d - path.cumulative[i0]) / segLen;
  const p0 = path.points[i0];
  const p1 = path.points[i1];
  const dx = p1.x - p0.x;
  const dy = p1.y - p0.y;
  const len = Math.hypot(dx, dy) || 1;
  return { x: p0.x + dx * t, y: p0.y + dy * t, tx: dx / len, ty: dy / len };
}

export interface FlowParticle {
  pathIndex: number;
  dist: number; // px along its path
  speed: number; // px/second at intensity 1
  length: number; // streak length, px
  width: number;
  lateralOffset: number; // px, perpendicular jitter so particles don't all ride the exact centreline
}

export function createFlowParticles(paths: FlowPath[], perPath: number): FlowParticle[] {
  const particles: FlowParticle[] = [];
  paths.forEach((path, pathIndex) => {
    for (let i = 0; i < perPath; i++) {
      particles.push({
        pathIndex,
        dist: Math.random() * path.totalLength,
        speed: 70 + Math.random() * 60,
        length: 10 + Math.random() * 14,
        width: 1.6 + Math.random() * 1.8,
        lateralOffset: (Math.random() - 0.5) * 7,
      });
    }
  });
  return particles;
}

export function stepFlowParticles(particles: FlowParticle[], paths: FlowPath[], dtSeconds: number, speedScale: number): void {
  for (const p of particles) {
    const path = paths[p.pathIndex];
    if (!path) continue;
    p.dist = (p.dist + p.speed * speedScale * dtSeconds) % path.totalLength;
  }
}

//: Fixed, not theme-derived -- same reasoning as rainOverlay.ts's streak
//: colours and runoff.ts's water/wet-ground colours: real flowing water
//: doesn't repaint on the app's light/dark toggle.
const RIBBON_COLOR = 'rgba(47, 122, 130, 1)'; // matches runoff.ts's WATER_FILL_COLOR
const FOAM_COLOR = 'rgba(232, 248, 250, 1)';

export function drawWaterFlow(
  ctx: CanvasRenderingContext2D,
  paths: FlowPath[],
  particles: FlowParticle[],
  intensity: number,
): void {
  if (intensity <= 0.01) return;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  // The water body itself: a continuous ribbon along the real path, real
  // direction, screen-pixel width (the actual metres-wide channel is
  // sub-pixel at this camera distance -- see runoff.ts's own docstring for
  // why fixed-pixel is the honest choice here, not a styling preference).
  ctx.globalAlpha = 0.5 * intensity;
  ctx.strokeStyle = RIBBON_COLOR;
  ctx.lineWidth = 9;
  for (const path of paths) {
    if (path.points.length < 2) continue;
    ctx.beginPath();
    path.points.forEach((p, i) => (i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y)));
    ctx.stroke();
  }

  // Surface turbulence: short bright streaks riding the ribbon, each moving
  // downstream at its own real-direction tangent -- this is what actually
  // reads as "flowing", not the static ribbon underneath it.
  const activeCount = Math.round(particles.length * Math.min(1, intensity * 1.3));
  ctx.strokeStyle = FOAM_COLOR;
  for (const particle of particles.slice(0, activeCount)) {
    const path = paths[particle.pathIndex];
    if (!path) continue;
    const head = pointAtDistance(path, particle.dist);
    // Clamped, not wrapped: a particle near the start of its path has
    // nothing behind it to trail from, and wrapping the tail to the far end
    // of the path drew a long spurious diagonal streak across the whole
    // channel every time a particle re-entered near distance 0.
    const tail = pointAtDistance(path, Math.max(0, particle.dist - particle.length));
    const nx = -head.ty;
    const ny = head.tx;
    const ox = nx * particle.lateralOffset;
    const oy = ny * particle.lateralOffset;
    ctx.globalAlpha = 0.75 * intensity;
    ctx.lineWidth = particle.width;
    ctx.beginPath();
    ctx.moveTo(head.x + ox, head.y + oy);
    ctx.lineTo(tail.x + ox, tail.y + oy);
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}
