import type { LngLatBoundsLike } from 'maplibre-gl';

/** Areas of interest, mirroring scripts/config.py rather than reinventing them.
 *
 *  These are the only coordinate literals in the frontend, and they exist because
 *  the browser cannot import a Python module. If config.py's AOIs change, these
 *  change with them — the derivation script prints both, so a mismatch shows up in
 *  its output rather than as a map that opens on the wrong water.
 */
export const AOI = {
  /** MARINE_AOI — the Gulf frontage the demo opens on: bathymetry, coastline,
   *  reef zones. Where the product actually looks. */
  marine: [
    [34.8, 29.25],
    [35.05, 29.6],
  ] as LngLatBoundsLike,

  /** TERRAIN_AOI, padded. Reaches 35.94 E / 30.30 N because Wadi Yutum drains
   *  90 km inland — so panning east is legitimate even though the basemap has no
   *  OSM detail out there. coverage.geojson draws where the detail stops. */
  maxBounds: [
    [34.6, 29.0],
    [36.1, 30.45],
  ] as LngLatBoundsLike,
} as const;
