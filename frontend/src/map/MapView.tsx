import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AttributionControl, Map as MapLibreMap, NavigationControl, ScaleControl } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { rtlReady } from './rtl';
import { buildStyle, LABEL_LAYERS, labelExpression } from './style';
import { useUi } from '../app/uiStore';
import { AOI } from './aoi';

/** The map. 03 §3: the dominant region, never smaller than half the viewport.
 *
 *  Everything the map encodes is also reachable as text (09 rule 7 / 01 §6.5) —
 *  Phase 2 adds the side-rail equivalents. For now the layer list and the
 *  coverage caveat are both stated in the rail rather than only drawn.
 */
export function MapView() {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const { theme, lang } = useUi();
  const [fault, setFault] = useState<string | null>(null);

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
  }, [lang]);

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
