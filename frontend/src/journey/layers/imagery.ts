/** Real satellite imagery drape — the same real, never-generated Esri World
 *  Imagery this project's 2D plume map uses (`docs/plume_imagery_decision.md`).
 *  Two bakes, not one: `fetch_journey_imagery.py` covers the full
 *  `TERRAIN_AOI` at zoom 12 (~38 m/px) so it survives as one WebGL texture —
 *  a zoom-13 attempt at that extent decoded to 7168x8192px and the browser
 *  refused to load it, a real failure this session hit, not a hypothetical
 *  one. `fetch_journey_corridor_imagery.py` covers just the release outlet's
 *  real area at zoom 14 (~9.5 m/px), sharp for the journey's closer camera
 *  phases (flood, transport, accumulation, impact), and stacked *above* the
 *  full-AOI image in `journeyStyle.ts` — wherever it covers, it simply draws
 *  over the coarser image beneath, no per-phase source-swapping needed.
 *  Never a live Mapbox/Google tile fetch (DoD item 9, "works with wifi off").
 *
 *  A single `image` source per bake, not a tile scheme: each is one JPEG
 *  covering its own real extent (see each sidecar JSON's own
 *  `width_px`/`height_px`/`zoom`) — simpler and sufficient at this scene's
 *  scale, no reason to re-tile an image this project already treats as one
 *  asset per bake.
 *
 *  NOTE ON WHERE THE FILES ACTUALLY LIVE: both fetch scripts write to
 *  `data/processed/basemap/`, same convention as `fetch_basemap_raster.py`.
 *  This scene needs the raw files reachable by the browser directly, so they
 *  must also be copied to `frontend/public/basemap-raster/` — a plain `cp`,
 *  not a second fetch:
 *      cp data/processed/basemap/aqaba_terrain_esri.{jpg,json} \
 *         data/processed/basemap/aqaba_journey_corridor_esri.{jpg,json} \
 *         frontend/public/basemap-raster/
 *  All four files are git-ignored/regenerable; this is not a new data
 *  source, just a second, browser-reachable serving location for the same
 *  two bakes.
 */

export const TERRAIN_STEM = 'aqaba_terrain_esri';
export const CORRIDOR_STEM = 'aqaba_journey_corridor_esri';

const jsonUrl = (stem: string) => `${import.meta.env.BASE_URL}basemap-raster/${stem}.json`;
const imageUrl = (stem: string) => `${import.meta.env.BASE_URL}basemap-raster/${stem}.jpg`;

interface BasemapRasterMeta {
  left: number;
  right: number;
  bottom: number;
  top: number;
  crs: string;
}

//: The sidecar's extent is EPSG:3857 (Web Mercator) metres — MapLibre's `image`
//: source wants the four corners in EPSG:4326 lon/lat. Standard spherical
//: Web Mercator inverse; correct for any axis-aligned Web Mercator rectangle,
//: not specific to either bake.
function webMercatorToLonLat(x: number, y: number): [number, number] {
  const R = 20037508.342789244;
  const lon = (x / R) * 180;
  const lat = (Math.atan(Math.exp((y / R) * Math.PI)) * 360) / Math.PI - 90;
  return [lon, lat];
}

export async function loadImageryCorners(
  stem: string,
): Promise<{ coordinates: [[number, number], [number, number], [number, number], [number, number]] } | null> {
  const res = await fetch(jsonUrl(stem));
  if (!res.ok) return null; // not baked in this environment — degrade honestly, no drape
  const meta = (await res.json()) as BasemapRasterMeta;
  const [westLon, northLat] = webMercatorToLonLat(meta.left, meta.top);
  const [eastLon, southLat] = webMercatorToLonLat(meta.right, meta.bottom);
  // MapLibre ImageSource corner order: top-left, top-right, bottom-right, bottom-left.
  return {
    coordinates: [
      [westLon, northLat],
      [eastLon, northLat],
      [eastLon, southLat],
      [westLon, southLat],
    ],
  };
}

export function imageUrlFor(stem: string): string {
  return imageUrl(stem);
}
