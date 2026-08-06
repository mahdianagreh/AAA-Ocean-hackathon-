import type { StyleSpecification } from 'maplibre-gl';
import type { ThemeName } from '../design/palette.generated';
import { palette } from '../design/palette.generated';

/** The 3D Journey's own style — a real fill-extrusion scene, not a screenshot or a
 *  synthetic mesh.
 *
 *  Every extruded layer is real, already-committed data: `relief_bands.geojson`
 *  (scripts/frontend_basemap.py's `relief_bands()`, vectorized straight from
 *  `depth_utm36n.tif` — the same raster `isobaths` contours), `reef_zones.geojson`
 *  (Allen Coral Atlas v2.0, already served to the main map), and the plume frame
 *  fed in per-timestep from the real particle engine's own contour output
 *  (`journey3d.json`, `scripts/frontend_journey.py`). No mesh, no generated
 *  imagery, no synthetic terrain tile.
 *
 *  Sea depth is rendered as upward relief (height = |depth|), not literally sunk
 *  below a sea-level plane — MapLibre fill-extrusion reads most reliably with a
 *  non-negative height, and inverting the sign would be exactly the kind of
 *  well-intentioned "realistic" touch this project's own rules warn against
 *  faking. Colour (blue, darkening with depth) carries which side of the
 *  shoreline a band is on; the legend says so on screen rather than leaving it
 *  to be inferred.
 */

const url = (name: string) => `${import.meta.env.BASE_URL}basemap/${name}.geojson`;

//: Real metres -> visual metres. One number, shown in the on-screen legend, not a
//: silent multiplier — the raw values are small relative to the ~24 x 39 km AOI, so
//: an honest 1:1 vertical scale reads as almost flat from this camera distance.
export const RELIEF_EXAGGERATION = 6;

//: Real plume `probability` (0.10-0.75, kernel_density_contours' own peak-normalized
//: levels — see backend/src/models/particle_engine.py) mapped to a visual extrusion
//: height in metres. Documented the same way: a real number times a stated
//: constant, never an invented shape.
export const PLUME_HEIGHT_PER_LEVEL_M = 250;

const EMPTY_FC = { type: 'FeatureCollection', features: [] } as const;

export function buildJourneyStyle(theme: ThemeName, riskMatch: unknown): StyleSpecification {
  const c = palette[theme];
  const isDark = theme === 'dark';

  return {
    version: 8,
    name: 'ReefShield 3D Journey',
    projection: { type: 'mercator' },
    sources: {
      relief: { type: 'geojson', data: url('relief_bands') },
      reef: { type: 'geojson', data: url('reef_zones') },
      outlets: { type: 'geojson', data: url('outlets') },
      catchments: { type: 'geojson', data: url('catchments') },
      // Populated per-frame from the component via source.setData — the real
      // contour geometry for whichever timestep is currently showing.
      'plume-frame': { type: 'geojson', data: EMPTY_FC },
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': isDark ? '#020a0d' : c.canvas } },

      {
        id: 'catchments-extrusion',
        type: 'fill-extrusion',
        source: 'catchments',
        paint: {
          'fill-extrusion-color': c.surface_2,
          // area_km2 is real (outlets.gpkg/catchments.gpkg) but is an area, not a
          // height — sqrt keeps a huge catchment from swamping the scene while
          // still ordering correctly by real size, and it is shown as a relative
          // silhouette (data_modelled dashed-underline territory), not a claimed
          // elevation. Real relief per catchment lives in relief_bands below,
          // which is a direct DEM read.
          'fill-extrusion-height': ['*', ['sqrt', ['coalesce', ['get', 'area_km2'], 0]], 8],
          'fill-extrusion-opacity': 0.5,
        },
      },

      // --- real terrain/bathymetry relief, one disjoint band at a time --------
      {
        id: 'relief-extrusion',
        type: 'fill-extrusion',
        source: 'relief',
        paint: {
          'fill-extrusion-color': [
            'interpolate', ['linear'], ['get', 'mid_m'],
            -800, isDark ? '#04222c' : '#0d3a4a',
            -25, isDark ? '#0f4a5c' : '#2f7a92',
            0, isDark ? '#1c5a4a' : '#3fa07a',
            150, isDark ? '#4a5a2a' : '#a3924a',
            800, isDark ? '#6a5040' : '#8a6a4a',
            1800, isDark ? '#8a8880' : '#c9c4b8',
          ] as unknown as string,
          // Sea bands rendered as upward relief by magnitude — see module docstring.
          'fill-extrusion-height': ['*', ['abs', ['get', 'mid_m']], RELIEF_EXAGGERATION],
          'fill-extrusion-opacity': 0.92,
        },
      },

      // --- reef zones, coloured by real exposure risk once the run lands ------
      //     Based above the *coastal fringe* relief bands reef zones actually sit
      //     against (-50..150 m real, so <=900 m once exaggerated) -- deliberately
      //     NOT above the far-inland peaks or deep-basin bands, whose exaggerated
      //     height (thousands of metres) would push a based-above-everything
      //     layer out of the camera's frustum at this pitch, which is what
      //     happened at a 1,000 m+ base. A tall enough clearance for the local
      //     footprint, not a global one.
      {
        id: 'reef-extrusion',
        type: 'fill-extrusion',
        source: 'reef',
        paint: {
          'fill-extrusion-color': riskMatch as unknown as string,
          'fill-extrusion-base': 260,
          'fill-extrusion-height': 320,
          'fill-extrusion-opacity': 0.95,
        },
      },

      // --- the release outlet, a small marker column --------------------------
      {
        id: 'outlet-marker',
        type: 'circle',
        source: 'outlets',
        paint: {
          'circle-radius': 5,
          'circle-color': c.canvas,
          'circle-stroke-color': c.accent,
          'circle-stroke-width': 2,
        },
      },

      // --- the plume, one real timestep at a time -----------------------------
      //     Based above the reef layer (not the reverse) so the growing cloud is
      //     always the top-most, unambiguous layer in the stack — relief, then
      //     reef, then plume — regardless of which real footprints happen to
      //     overlap at a given camera angle.
      {
        id: 'plume-extrusion',
        type: 'fill-extrusion',
        source: 'plume-frame',
        paint: {
          'fill-extrusion-color': [
            'interpolate', ['linear'], ['get', 'probability'],
            0.1, c.data_modelled,
            0.75, c.accent,
          ] as unknown as string,
          'fill-extrusion-base': 350,
          'fill-extrusion-height': ['+', 350, ['get', 'height']],
          'fill-extrusion-opacity': 0.75,
        },
      },
    ],
  } as unknown as StyleSpecification;
}
