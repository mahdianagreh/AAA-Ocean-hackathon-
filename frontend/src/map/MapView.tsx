import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AttributionControl,
  type DataDrivenPropertyValueSpecification,
  Map as MapLibreMap,
  NavigationControl,
  ScaleControl,
} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { rtlReady } from './rtl';
import { buildStyle, LABEL_LAYERS, labelExpression } from './style';
import { useUi } from '../app/uiStore';
import { AOI } from './aoi';
import { palette } from '../design/palette.generated';

/** The map. 03 §3: the dominant region, never smaller than half the viewport.
 *
 *  Everything the map encodes is also reachable as text (09 rule 7 / 01 §6.5) —
 *  Phase 2 adds the side-rail equivalents. For now the layer list and the
 *  coverage caveat are both stated in the rail rather than only drawn.
 */
export function MapView({ risk }: { risk?: Array<{ catchment_id: string; band: string }> }) {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const { theme, lang, layers } = useUi();
  const [fault, setFault] = useState<string | null>(null);
  /** A monotonic epoch, not a boolean.
   *
   *  A `ready` boolean flapped: `styledata` fires repeatedly during load while
   *  isStyleLoaded() is still false, and one of those firings lands *after*
   *  `load` — so ready went true then back to false, and every effect gated on it
   *  silently stopped running. A layer toggle changed the checkbox and left the
   *  map alone, which looked like a broken toggle rather than a stale flag.
   *
   *  Incrementing only when the style is genuinely loaded means the value can only
   *  move forward, so effects re-run after a restyle and never un-run. */
  const [epoch, setEpoch] = useState(0);
  const ready = epoch > 0;

  // Resolve 'system' to a concrete palette — the style carries baked hex, so it
  // cannot defer to a media query the way the CSS tokens do.
  const resolved =
    theme === 'system'
      ? window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      : theme;

  useEffect(() => {
    if (!container.current || map.current) return;
    let cancelled = false;

    // Await the RTL plugin before the first map exists. Registering after a map
    // is constructed leaves that map's already-shaped labels unshaped, and the
    // failure is invisible in English.
    void rtlReady
      .then(() => {
        if (cancelled || !container.current) return;
        const m = new MapLibreMap({
          container: container.current,
          style: buildStyle(resolved, lang),
          bounds: AOI.marine,
          fitBoundsOptions: { padding: 24 },
          maxBounds: AOI.maxBounds,
          minZoom: 8,
          maxZoom: 16,
          attributionControl: false,
          // 09: keyboard pan and zoom are not optional
          keyboard: true,
        });
        // A single invalid expression aborts the ENTIRE style load, so every layer
        // silently disappears rather than just the offending one. That happened
        // once here — a zoom expression nested inside `case`, which MapLibre only
        // permits at the top level of a paint property — and the map looked merely
        // empty. Surface it, the same way the RTL fault is surfaced.
        m.on('error', (e) => {
          const msg = e.error?.message ?? String(e);
          // Ignore transient source aborts from a style swap; only style/layer
          // validation failures are worth stopping the demo for.
          if (/expression|layers\[|sources\[|Unable to parse/i.test(msg)) setFault(msg);
        });

        m.addControl(new NavigationControl({ visualizePitch: false }), 'top-right');
        // The scale bar does not mirror — 06 §3 lists it with the compass.
        m.addControl(new ScaleControl({ maxWidth: 120, unit: 'metric' }), 'bottom-left');
        m.addControl(
          new AttributionControl({
            compact: false,
            customAttribution: [
              '© OpenStreetMap contributors (ODbL)',
              'Bathymetry: GEBCO / GMRT',
              'Reef zones: PROVISIONAL — not Allen Coral Atlas',
            ],
          }),
          'bottom-right',
        );
        const bump = () => {
          if (m.isStyleLoaded()) setEpoch((n) => n + 1);
        };
        m.on('load', bump);
        m.on('styledata', bump);
        m.on('idle', bump);

        map.current = m;
        // Exposed so the offline-Arabic gate can call queryRenderedFeatures and
        // prove the Arabic names were actually *placed*, not merely requested.
        // Dev and explicit-specimen builds only — not in a production bundle.
        if (import.meta.env.DEV || import.meta.env.VITE_SPECIMEN === '1') {
          (window as unknown as { __map?: MapLibreMap }).__map = m;
        }
      })
      .catch((err: Error) => {
        // 00's risk register: this breaks silently and only in Arabic. Make it loud.
        if (!cancelled) setFault(err.message);
      });

    return () => {
      cancelled = true;
      map.current?.remove();
      map.current = null;
    };
    // Deliberately mount-only. Theme and language are applied by the effects
    // below rather than by rebuilding the map, which would lose the viewport.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Theme: every paint property carries a resolved hex, so this needs a restyle.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    m.setStyle(buildStyle(resolved, lang), { diff: true });
  }, [resolved, lang]);

  // Language: only the label layers change, which avoids a restyle flash.
  useEffect(() => {
    const m = map.current;
    if (!m?.isStyleLoaded()) return;
    for (const id of LABEL_LAYERS) {
      if (m.getLayer(id)) m.setLayoutProperty(id, 'text-field', labelExpression(lang));
    }
  }, [lang, epoch]);

  /** Catchment fill by risk band — the land half of the choreography.
   *
   *  Driven by a `match` on catchment_id rather than by rewriting the GeoJSON, so
   *  a cursor move is one setPaintProperty call instead of a source reload. That is
   *  what lets the time-scrub stay smooth: the geometry never changes, only the
   *  paint expression does.
   */
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !m.getLayer('catchments-fill') || !risk?.length) return;

    // MapLibre cannot read CSS custom properties, so these resolve to hex from
    // the generated palette — the same values, one source.
    const p = palette[resolved];
    type Band = keyof typeof p.risk;

    /** A `match` expression built from a variable-length list.
     *
     *  MapLibre types `match` as a fixed-shape tuple, which a spread cannot
     *  satisfy — the compiler cannot know the arity. The runtime contract (a
     *  flat pair list then a fallback) is exactly what MapLibre validates, and
     *  the style-error listener above surfaces it loudly if it is ever wrong. */
    const matchBy = (pick: (band: Band) => string) =>
      [
        'match',
        ['get', 'catchment_id'],
        ...risk.flatMap((r) => [r.catchment_id, pick(r.band as Band)]),
        p.ink_3,
      ] as unknown as DataDrivenPropertyValueSpecification<string>;

    m.setPaintProperty('catchments-fill', 'fill-color', matchBy((b) => p.risk[b]));
    // 0.22, not 0.35. At 0.35 the fill buried the roads and the wadis — and the
    // wadis are the hazard's own paths, so losing them to the risk colour defeats
    // the point. 02 §5 puts the weight on the boundary anyway: hairlines are the
    // container model, so the stroke carries the signal and the fill only tints.
    m.setPaintProperty('catchments-fill', 'fill-opacity', 0.22);
    // Every hazard fill carries a stroke at the next band up — 02 §2.
    m.setPaintProperty('catchments-line', 'line-color', matchBy((b) => p.riskStroke[b]));
    m.setPaintProperty('catchments-line', 'line-width', 1.4);
  }, [risk, epoch, resolved]);

  /** Layer visibility. One effect, so a toggle cannot get out of sync with the
   *  store, and unknown layers are skipped rather than throwing. */
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const map_: Record<string, string[]> = {
      isobaths: ['isobaths'],
      catchments: ['catchments-fill', 'catchments-line'],
      reef: ['reef-fill', 'reef-line'],
      outlets: ['outlets'],
      coverage: ['coverage'],
      labels: LABEL_LAYERS,
      plume: ['plume-fill', 'plume-line'],
      mooring: ['mooring'],
      modelGrid: ['model-grid'],
      rainfall: [],
    };
    for (const [key, ids] of Object.entries(map_)) {
      const visible = layers[key as keyof typeof layers] ? 'visible' : 'none';
      for (const id of ids) {
        if (m.getLayer(id)) m.setLayoutProperty(id, 'visibility', visible);
      }
    }
  }, [layers, epoch]);

  if (fault) {
    return (
      <div
        role="alert"
        className="flex h-full flex-col items-start justify-center gap-2 rule bg-surface p-6"
      >
        <h2 className="text-md font-semibold text-risk-critical">{t('map.faultTitle')}</h2>
        <p className="max-w-prose text-sm text-ink-2">{t('map.faultBody')}</p>
        <code className="font-mono num text-xs text-ink-3">{fault}</code>
      </div>
    );
  }

  return (
    <div
      ref={container}
      data-map="true"
      className="h-full w-full"
      // The map does not mirror. North stays up and east stays east — 06 §3.
      dir="ltr"
      aria-label={t('map.label')}
    />
  );
}
