/** Real satellite imagery drape — the same real, never-generated Esri World
 *  Imagery this project's 2D plume map uses (`docs/plume_imagery_decision.md`),
 *  baked by its own script (`scripts/fetch_journey_imagery.py`) rather than
 *  reusing the 2D map's file: that one covers only `MARINE_AOI` (the sea
 *  strip, ~27x33 km), and this scene's terrain mesh covers the full
 *  `TERRAIN_AOI` (~115x128 km, every mountain in it) — draping the smaller
 *  image here would leave a visible seam between real photo (near the coast)
 *  and the colour-relief fallback (`layers/terrain.ts`) everywhere else. Never
 *  a live Mapbox/Google tile fetch (DoD item 9, "works with wifi off").
 *
 *  A single `image` source, not a tile scheme: one JPEG covering the whole
 *  AOI (see the sidecar JSON's own `width_px`/`height_px`/`zoom`), which is
 *  simpler and sufficient at this scene's scale — no reason to re-tile an
 *  image this project already treats as one asset.
 *
 *  NOTE ON WHERE THE FILE ACTUALLY LIVES: `fetch_journey_imagery.py` writes to
 *  `data/processed/basemap/`, same convention as `fetch_basemap_raster.py`.
 *  This scene needs the raw file reachable by the browser directly, so it
 *  must also be copied to `frontend/public/basemap-raster/` — a plain `cp`,
 *  not a second fetch:
 *      cp data/processed/basemap/aqaba_terrain_esri.{jpg,json} \
 *         frontend/public/basemap-raster/
 *  Both copies are git-ignored/regenerable; this is not a new data source,
 *  just a second, browser-reachable serving location for the same one.
 */

const JSON_URL = `${import.meta.env.BASE_URL}basemap-raster/aqaba_terrain_esri.json`;
const IMAGE_URL = `${import.meta.env.BASE_URL}basemap-raster/aqaba_terrain_esri.jpg`;

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
//: not specific to this one image.
function webMercatorToLonLat(x: number, y: number): [number, number] {
  const R = 20037508.342789244;
  const lon = (x / R) * 180;
  const lat = (Math.atan(Math.exp((y / R) * Math.PI)) * 360) / Math.PI - 90;
  return [lon, lat];
}

export async function loadImageryCorners(): Promise<
  { coordinates: [[number, number], [number, number], [number, number], [number, number]] } | null
> {
  const res = await fetch(JSON_URL);
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

export { IMAGE_URL };
