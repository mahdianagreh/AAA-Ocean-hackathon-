/** Real satellite imagery drape — the same baked Esri World Imagery this
 *  project already uses for the 2D plume map (`scripts/fetch_basemap_raster.py`,
 *  `backend/src/rendering/plume_map.py`), reused here rather than a second
 *  fetch/format. Baked once, offline forever after; never a live Mapbox/Google
 *  tile fetch (that would violate DoD item 9, "works with wifi off", the exact
 *  constraint the team's 3D Journey plan calls a hard gate for this feature).
 *
 *  A single `image` source, not a tile scheme: the baked file is one JPEG
 *  covering the whole padded marine AOI (see the sidecar JSON's own
 *  `pad_fraction`), which is simpler and sufficient at this scene's scale —
 *  no reason to re-tile an image this project already treats as one asset.
 *
 *  NOTE ON WHERE THE FILE ACTUALLY LIVES: `fetch_basemap_raster.py` writes to
 *  `data/processed/basemap/`, consumed server-side by `plume_map.py` (baked
 *  into a rendered PNG, never served raw to a browser). This scene needs the
 *  raw file reachable by the browser directly, so it must also be copied to
 *  `frontend/public/basemap-raster/` — a plain `cp`, not a second fetch:
 *      cp data/processed/basemap/aqaba_marine_esri.{jpg,json} \
 *         frontend/public/basemap-raster/
 *  Both copies are git-ignored/regenerable; this is not a new data source,
 *  just a second, browser-reachable serving location for the same one.
 */

const JSON_URL = `${import.meta.env.BASE_URL}basemap-raster/aqaba_marine_esri.json`;
const IMAGE_URL = `${import.meta.env.BASE_URL}basemap-raster/aqaba_marine_esri.jpg`;

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
