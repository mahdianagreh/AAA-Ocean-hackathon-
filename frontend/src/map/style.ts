import type { StyleSpecification } from 'maplibre-gl';
import { palette, type ThemeName } from '../design/palette.generated';
import type { Lang } from '../app/uiStore';

/** The basemap style, authored against the design tokens.
 *
 *  08-map-rendering.md requires a style "authored against the design tokens, not
 *  a borrowed theme", and 01 §2 makes isobath hairlines the structural system —
 *  the same contour language as the panel dividers and the focus ring. Adopting a
 *  vendor schema would mean fighting it to get there.
 *
 *  Colours come from palette.generated.ts as **hex**, not the OKLCH the DOM uses.
 *  MapLibre's colour parser accepts named colours, hex, rgb() and hsl() and
 *  nothing else, so an oklch() value fails style validation and the layer
 *  silently renders at its property default.
 */

const SRC = 'basemap';

/** No `glyphs`, and that is the other half of the offline-Arabic fix.
 *
 *  Even with the RTL plugin loaded, a style whose `glyphs` points at
 *  demotiles.maplibre.org (the style-spec's own example) renders no labels at all
 *  offline — and that fontstack has no Arabic coverage even online.
 *
 *  Omitting `glyphs` entirely makes MapLibre rasterise every codepoint
 *  client-side with TinySDF from the CSS families named in `text-font`, after
 *  awaiting document.fonts.load(). Zero glyph requests, no PBFs, no fontnik
 *  native build.
 *
 *  This works for Arabic *because* the shaper emits presentation forms and the
 *  committed IBM Plex Sans Arabic face carries them: measured in that exact file,
 *  196 Forms-A + 140 Forms-B + 252 Arabic base + 243 Latin, 1,065 codepoints in
 *  71,904 B. One face covers both scripts, so metrics do not shift on a language
 *  switch.
 *
 *  Two limits, stated rather than discovered: no GPOS mark positioning
 *  (irrelevant for unvocalised place names), and TinySDF sniffs weight out of the
 *  family *name* — so never put a weight word in `text-font`. */
const LABEL_FONT = ['IBM Plex Sans Arabic'];

/** Bilingual labels, with the fallback the docs get half-right.
 *
 *  06 §4 says select `name:ar` and fall back to `name`. Checked against the
 *  extract, `name` is *already Arabic* on many features with the Latin form in
 *  `name:en`, so that fallback shows شارع الملك حسين in English mode. The
 *  derivation script splits both into `name_ar` / `name_en` by script; this
 *  coalesces preferred → other → nothing, so a missing name falls back rather
 *  than rendering blank. */
function label(lang: Lang) {
  const first = lang === 'ar' ? 'name_ar' : 'name_en';
  const second = lang === 'ar' ? 'name_en' : 'name_ar';
  return ['coalesce', ['get', first], ['get', second], ''] as unknown as string;
}

const url = (name: string) => `${import.meta.env.BASE_URL}basemap/${name}.geojson`;

const EMPTY_FC = { type: 'FeatureCollection', features: [] } as const;

/** The mooring, inline because it is one point from one paper.
 *
 *  Coordinate and radius from data/processed/marine/mooring_target_AQ-2016-10-28.json,
 *  where both are tagged provenance "derived" — the paper states only "~250 m
 *  offshore the Kinnet Canal outlet, 13 m depth". The derivation doc is explicit
 *  that this must not be used to more precision than the 1.5 km radius implies,
 *  and that AQ-O01 (Wadi Yutum, Jordan) must not be substituted for it. */
const MOORING = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      properties: { key: 'mooring', depth_m: -13, uncertainty_radius_m: 1500 },
      geometry: { type: 'Point', coordinates: [34.98151, 29.53799] },
    },
  ],
} as const;

/** The ~9 km ocean-model grid — the honesty device from 01 §2.
 *
 *  Two to three cells span the entire Gulf. The coarseness the project keeps
 *  apologising for in prose becomes something a judge can see, which is more
 *  convincing than stating it and converts the biggest weakness into evidence of
 *  rigour. Off by default: it is a thing you turn on to make a point.
 *
 *  0.081° of longitude at 29.5°N is ~7.9 km; 0.081° of latitude is ~9.0 km. The
 *  cell is drawn on that spacing rather than a round number of kilometres, because
 *  the model's own grid is in degrees. */
const GRID_DEG = 0.081;
const MODEL_GRID = {
  type: 'FeatureCollection',
  features: (() => {
    const out: Array<Record<string, unknown>> = [];
    for (let lon = 34.68; lon < 35.2; lon += GRID_DEG) {
      for (let lat = 29.16; lat < 29.72; lat += GRID_DEG) {
        out.push({
          type: 'Feature',
          properties: { role: 'model_cell' },
          geometry: {
            type: 'LineString',
            coordinates: [
              [lon, lat],
              [lon + GRID_DEG, lat],
              [lon + GRID_DEG, lat + GRID_DEG],
              [lon, lat + GRID_DEG],
              [lon, lat],
            ].map(([x, y]) => [Number(x.toFixed(5)), Number(y.toFixed(5))]),
          },
        });
      }
    }
    return out;
  })(),
} as const;

/** Layer order is 03-information-architecture.md §4, "to be fixed in Phase 1 and
 *  not renegotiated later". Bottom to top. The data layers Phase 2 adds
 *  (rainfall, plume, exposure fills) slot in at the marked positions. */
export function buildStyle(theme: ThemeName, lang: Lang): StyleSpecification {
  const c = palette[theme];
  const isDark = theme === 'dark';

  return {
    version: 8,
    name: 'Aqaba Aqua AI hydrographic',
    // explicit, so a future MapLibre default of globe cannot change the view
    projection: { type: 'mercator' },
    // no `glyphs` (see above) and no `sprite` — Phase 1 puts no icons on the map
    sources: {
      [`${SRC}-water`]: { type: 'geojson', data: url('water') },
      [`${SRC}-shoreline`]: { type: 'geojson', data: url('shoreline') },
      [`${SRC}-isobaths`]: { type: 'geojson', data: url('isobaths') },
      [`${SRC}-landuse`]: { type: 'geojson', data: url('landuse') },
      [`${SRC}-roads`]: { type: 'geojson', data: url('roads') },
      [`${SRC}-wadis`]: { type: 'geojson', data: url('wadis') },
      [`${SRC}-protected`]: { type: 'geojson', data: url('protected') },
      [`${SRC}-catchments`]: { type: 'geojson', data: url('catchments') },
      [`${SRC}-reef`]: { type: 'geojson', data: url('reef_zones') },
      [`${SRC}-outlets`]: { type: 'geojson', data: url('outlets') },
      [`${SRC}-places`]: { type: 'geojson', data: url('places') },
      [`${SRC}-admin`]: { type: 'geojson', data: url('admin') },
      [`${SRC}-admin-labels`]: { type: 'geojson', data: url('admin_labels') },
      [`${SRC}-coverage`]: { type: 'geojson', data: url('coverage') },
      // The mooring: one point, the validation target from Kalman et al. 2025,
      // with its 1.5 km uncertainty radius drawn rather than implied. The paper
      // gives only "~250 m offshore the Kinnet Canal outlet, 13 m depth" — no
      // decimal coordinate — so a bare dot would claim precision the source does
      // not support.
      [`${SRC}-mooring`]: { type: 'geojson', data: MOORING },
      // Empty until Abd's per-timestep contours land (OPEN-ISSUES.md item 2). The
      // dependency table allows a static polygon stub; an empty FeatureCollection
      // is the honest version of that — nothing is drawn, and the legend says the
      // layer exists rather than showing a shape we invented.
      [`${SRC}-plume`]: { type: 'geojson', data: EMPTY_FC },
      [`${SRC}-grid`]: { type: 'geojson', data: MODEL_GRID },
    },
    layers: [
      // --- ground -------------------------------------------------------
      { id: 'bg', type: 'background', paint: { 'background-color': c.canvas } },
      {
        id: 'water',
        type: 'fill',
        source: `${SRC}-water`,
        paint: { 'fill-color': isDark ? c.surface : c.surface_2 },
      },

      // --- the signature: isobaths as hairlines --------------------------
      {
        id: 'isobaths',
        type: 'line',
        source: `${SRC}-isobaths`,
        paint: {
          'line-color': c.hairline_2,
          'line-width': [
            // the shelf contours carry more weight than the basin steps, because
            // the reef sits on the shelf and that is where depth is being read
            'interpolate',
            ['linear'],
            ['abs', ['get', 'depth_m']],
            25,
            0.9,
            200,
            0.6,
            800,
            0.4,
          ],
        },
      },
      {
        id: 'shoreline',
        type: 'line',
        source: `${SRC}-shoreline`,
        paint: { 'line-color': c.hairline_2, 'line-width': 1.2 },
      },

      // --- land ----------------------------------------------------------
      {
        id: 'landuse',
        type: 'fill',
        source: `${SRC}-landuse`,
        paint: { 'fill-color': c.surface_2, 'fill-opacity': isDark ? 0.5 : 0.7 },
      },
      {
        id: 'roads',
        type: 'line',
        source: `${SRC}-roads`,
        paint: {
          'line-color': c.hairline,
          'line-width': [
            'interpolate',
            ['linear'],
            ['zoom'],
            10,
            0.4,
            14,
            ['match', ['get', 'highway'], ['motorway', 'trunk', 'primary'], 1.6, 0.8],
            16,
            ['match', ['get', 'highway'], ['motorway', 'trunk', 'primary'], 3, 1.4],
          ],
        },
      },
      {
        // Dashed, because a wadi is dry almost always — the form says
        // "intermittent" without a legend entry. It is also the hazard's own path.
        //
        // Minor drainage fades in from zoom 12. main's re-extract took this layer
        // from 406 features to 2,242, and drawing all of them at basin zoom buries
        // the catchment boundaries under hairlines. The `minor` flag is set by the
        // derivation script at a 1 km length threshold.
        id: 'wadis',
        type: 'line',
        source: `${SRC}-wadis`,
        paint: {
          'line-color': c.ink_3,
          'line-width': ['interpolate', ['linear'], ['zoom'], 10, 0.5, 16, 1.6],
          'line-dasharray': [3, 2],
          'line-opacity': [
            'interpolate',
            ['linear'],
            ['zoom'],
            11.5,
            ['case', ['==', ['get', 'minor'], 1], 0, 1],
            12.5,
            1,
          ],
        },
      },
      {
        id: 'protected-fill',
        type: 'fill',
        source: `${SRC}-protected`,
        paint: { 'fill-color': c.accent, 'fill-opacity': 0.06 },
      },
      {
        id: 'protected-line',
        type: 'line',
        source: `${SRC}-protected`,
        paint: { 'line-color': c.accent, 'line-width': 1, 'line-dasharray': [4, 3] },
      },

      // --- catchments. Phase 2 fills these by runoff risk ----------------
      {
        id: 'catchments-fill',
        type: 'fill',
        source: `${SRC}-catchments`,
        paint: { 'fill-color': c.ink_3, 'fill-opacity': 0.05 },
      },
      {
        id: 'catchments-line',
        type: 'line',
        source: `${SRC}-catchments`,
        paint: { 'line-color': c.ink_3, 'line-width': 1 },
      },

      // --- country borders -----------------------------------------------
      //
      // The Gulf is a four-country basin about 25 km wide, and the whole premise
      // is that one storm system touches several of them at once. Without these
      // the map is a single undifferentiated landmass and that premise is
      // invisible.
      //
      // Above the catchment tint so a border stays crisp through it, below the
      // marine layers so reef and plume still read on top. Long dashes in
      // neutral ink: a border must not be confusable at a glance with a
      // catchment boundary (risk-coloured, solid) or a reef zone (accent), so it
      // differs in BOTH colour and dash pattern rather than only in hue.
      {
        id: 'admin-line',
        type: 'line',
        source: `${SRC}-admin`,
        paint: {
          'line-color': c.ink_2,
          'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.8, 10, 1.4, 14, 2],
          'line-dasharray': [6, 3],
          'line-opacity': 0.75,
        },
      },

      // --- plume: relative-density contours, beneath the reef so exposure
      //     stays readable through them. Empty until Abd's per-timestep contours
      //     land; dashed and hatched because it is modelled, never a trajectory. --
      {
        id: 'plume-fill',
        type: 'fill',
        source: `${SRC}-plume`,
        paint: { 'fill-color': c.ink_3, 'fill-opacity': 0.18 },
      },
      {
        id: 'plume-line',
        type: 'line',
        source: `${SRC}-plume`,
        paint: { 'line-color': c.ink_3, 'line-width': 1, 'line-dasharray': [3, 2] },
      },

      // --- reef zones. Phase 2 fills these by exposure score -------------
      {
        id: 'reef-fill',
        type: 'fill',
        source: `${SRC}-reef`,
        paint: { 'fill-color': c.accent, 'fill-opacity': 0.22 },
      },
      {
        // Every hazard fill carries a 1px stroke at the next band up (02 §2).
        // Until exposure exists these are one flat accent, which is correct:
        // sensitivity_weight is 1.0 on all eight zones, so the legend must not
        // imply they differ.
        id: 'reef-line',
        type: 'line',
        source: `${SRC}-reef`,
        paint: { 'line-color': c.accent, 'line-width': 1 },
      },

      // --- outlets, sized by upstream area ------------------------------
      {
        id: 'outlets',
        type: 'circle',
        source: `${SRC}-outlets`,
        paint: {
          'circle-radius': [
            'interpolate',
            ['linear'],
            ['sqrt', ['coalesce', ['get', 'upstream_km2'], 1]],
            1,
            3,
            67,
            10, // sqrt(4453) — AQ-O01 carries 96% of the discharge
          ],
          'circle-color': c.canvas,
          'circle-stroke-color': c.ink,
          'circle-stroke-width': 1.2,
        },
      },

      // --- the mooring: measured, so it is drawn solid ------------------
      {
        // The uncertainty radius first, as a hatched-equivalent low-opacity fill.
        // 01 §4: an envelope is hatched, and 09 rule 1 says uncertainty renders
        // with the value or the value does not render. A bare dot would claim a
        // precision the source does not give.
        id: 'mooring-uncertainty',
        type: 'circle',
        source: `${SRC}-mooring`,
        paint: {
          // 1500 m at zoom 13 near 29.5°N is roughly 40 px; scaled so the radius
          // stays geographically honest rather than a fixed pixel blob.
          'circle-radius': ['interpolate', ['exponential', 2], ['zoom'], 10, 5, 16, 300],
          'circle-color': c.data_measured,
          'circle-opacity': 0.08,
          'circle-stroke-color': c.data_measured,
          'circle-stroke-width': 0.5,
          'circle-stroke-opacity': 0.4,
        },
      },
      {
        id: 'mooring',
        type: 'circle',
        source: `${SRC}-mooring`,
        paint: {
          'circle-radius': 4,
          'circle-color': c.surface,
          'circle-stroke-color': c.data_measured,
          'circle-stroke-width': 1.6,
        },
      },

      // --- the honesty devices ------------------------------------------
      {
        // The ~9 km ocean-model grid. Two to three cells span the whole Gulf, and
        // our own release point sits on a cell the model masks as land.
        id: 'model-grid',
        type: 'line',
        source: `${SRC}-grid`,
        layout: { visibility: 'none' },
        paint: { 'line-color': c.ink_3, 'line-width': 0.6, 'line-opacity': 0.5 },
      },
      {
        // The OSM extract stops at 35.0 E / 29.55 N while TERRAIN_AOI reaches
        // 35.94 E / 30.30 N, because Wadi Yutum drains 90 km inland. So the
        // basemap ends long before AQ-C01 does. Drawing that boundary is the same
        // move as showing the ~9 km ocean-model grid: cheaper than pretending.
        id: 'coverage',
        type: 'line',
        source: `${SRC}-coverage`,
        paint: {
          'line-color': c.ink_3,
          'line-width': 1,
          'line-dasharray': [2, 4],
          'line-opacity': 0.6,
        },
      },

      // --- labels, last --------------------------------------------------
      {
        // Aqaba and Eilat. The two cities at the head of the Gulf, and the
        // paired sites in this project's own event record — Oct 2016 is
        // documented as the Aqaba-Eilat flood.
        id: 'label-city',
        type: 'symbol',
        source: `${SRC}-admin-labels`,
        filter: ['==', ['get', 'kind'], 'city'],
        layout: {
          'text-field': label(lang),
          'text-font': LABEL_FONT,
          'text-size': ['interpolate', ['linear'], ['zoom'], 7, 11, 12, 14],
          'text-anchor': 'bottom',
          'text-offset': [0, -0.4],
          'text-max-width': 8,
          // Two labels, both load-bearing. Aqaba sits ~6 km from Eilat, which is
          // ~50 px at the opening zoom, and MapLibre was dropping Aqaba to the
          // collision grid even as the highest-priority symbol layer. There are
          // exactly two city labels on this map and they never stack, so opting
          // out of collision here costs nothing and guarantees both appear.
          'text-allow-overlap': true,
          'text-ignore-placement': false,
        },
        paint: {
          'text-color': c.ink,
          'text-halo-color': c.canvas,
          'text-halo-width': 1.6,
        },
      },
      {
        // Country names. Letter-spaced, uppercase, no halo competition with the
        // data labels — this is ground truth for orientation, so it sits quietly
        // underneath everything operational. Fades out past z11, where the view
        // is a single country and the label is just clutter.
        id: 'label-country',
        type: 'symbol',
        source: `${SRC}-admin-labels`,
        filter: ['==', ['get', 'kind'], 'country'],
        layout: {
          'text-field': label(lang),
          'text-font': LABEL_FONT,
          'text-size': ['interpolate', ['linear'], ['zoom'], 6, 11, 10, 14],
          'text-letter-spacing': 0.18,
          'text-transform': 'uppercase',
          'text-max-width': 9,
          'symbol-placement': 'point',
        },
        paint: {
          'text-color': c.ink_3,
          'text-halo-color': c.canvas,
          'text-halo-width': 1.6,
          // The dashboard opens fitted to MARINE_AOI, which lands around z10-11.
          // Fading out at 11.5 meant the country labels were never on screen at
          // the view the app actually opens at. They now hold until the view is
          // tight enough that only one country is in frame.
          'text-opacity': ['interpolate', ['linear'], ['zoom'], 12.5, 1, 13.5, 0],
        },
      },
      {
        // Dive sites at every zoom; everything else only when zoomed in.
        // The marine-park officer is deciding where to send a survey team, so a
        // dive site is operationally relevant and a hotel name is orientation.
        //
        // `coastal` is the load-bearing filter and it is not cosmetic. TERRAIN_AOI
        // reaches ~90 km inland to cover Wadi Yutum, so the OSM extract behind
        // this layer includes the entire Wadi Rum Protected Area. Every rock
        // arch, siq and inscription in it is `tourism=attraction`, which the
        // basemap builder folded into "dive" until 9 Aug — so "Lawrence Face",
        // "Mushroom rock" and "Wadi Rum" rendered as dive-site labels 40 km
        // inland, across the middle of the catchment. The builder now classifies
        // by `sport=scuba_diving` alone and stamps `coastal` (<= 5 km from
        // MARINE_AOI); this filter is the second line of defence, so a future
        // tagging change cannot put the desert back on a marine map.
        id: 'label-place',
        type: 'symbol',
        source: `${SRC}-places`,
        filter: ['==', ['get', 'coastal'], true],
        layout: {
          'text-field': label(lang),
          'text-font': LABEL_FONT,
          'text-size': ['match', ['get', 'kind'], 'dive', 11, 10],
          'text-anchor': 'top',
          'text-offset': [0, 0.6],
          'text-max-width': 8,
        },
        paint: {
          'text-color': ['match', ['get', 'kind'], 'dive', c.ink_2, c.ink_3],
          'text-halo-color': c.canvas,
          'text-halo-width': 1.2,
          // The zoom expression must be TOP-LEVEL in a paint property — MapLibre
          // rejects `['case', …, ['interpolate', ['zoom'], …], …]` with
          // "zoom expression may only be used as input to a top-level step or
          // interpolate expression", and that error aborts the whole style load,
          // so *nothing* renders rather than just this layer. Branch inside the
          // stop outputs instead.
          'text-opacity': [
            'interpolate',
            ['linear'],
            ['zoom'],
            13.5,
            ['case', ['==', ['get', 'kind'], 'dive'], 1, 0],
            14,
            1,
          ],
        },
      },
      {
        id: 'label-wadi',
        type: 'symbol',
        source: `${SRC}-wadis`,
        filter: ['any', ['has', 'name_ar'], ['has', 'name_en']],
        layout: {
          'text-field': label(lang),
          'text-font': LABEL_FONT,
          'text-size': 11,
          'symbol-placement': 'line',
          'text-max-angle': 30,
        },
        paint: { 'text-color': c.ink_3, 'text-halo-color': c.canvas, 'text-halo-width': 1.2 },
      },
      {
        id: 'label-road',
        type: 'symbol',
        source: `${SRC}-roads`,
        minzoom: 13,
        filter: ['any', ['has', 'name_ar'], ['has', 'name_en']],
        layout: {
          'text-field': label(lang),
          'text-font': LABEL_FONT,
          'text-size': 10,
          'symbol-placement': 'line',
          'text-max-angle': 30,
        },
        paint: { 'text-color': c.ink_3, 'text-halo-color': c.canvas, 'text-halo-width': 1.2 },
      },
      {
        // Coastal protected areas only. The polygons for Wadi Rum, Jabel
        // Fashiyya and Petra stay drawn — the Wadi Rum PA genuinely sits inside
        // the Wadi Yutum catchment and seeing that is useful — but labelling
        // them put "Petra" on a reef map, 79 km away.
        id: 'label-protected',
        type: 'symbol',
        source: `${SRC}-protected`,
        filter: ['==', ['get', 'coastal'], true],
        layout: {
          'text-field': label(lang),
          'text-font': LABEL_FONT,
          'text-size': 12,
          'text-max-width': 9,
        },
        paint: { 'text-color': c.accent, 'text-halo-color': c.canvas, 'text-halo-width': 1.4 },
      },
    ],
  } as unknown as StyleSpecification;
}

/** Language changes only need the label layers restyled, which avoids the flash
 *  a full setStyle causes. Theme changes do need setStyle, because every paint
 *  property carries a resolved hex. */
export const LABEL_LAYERS = ['label-place', 'label-wadi', 'label-road', 'label-protected'];

export { label as labelExpression };
