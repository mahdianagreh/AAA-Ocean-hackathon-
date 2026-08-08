import { getRTLTextPluginStatus, setRTLTextPlugin, setWorkerUrl } from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

/** The highest-value catch in the whole frontend plan, in one file.
 *
 *  00-master-plan.md's risk register puts it first: MapLibre needs the RTL text
 *  plugin to shape Arabic labels, it is registered by URL, and every documented
 *  example points at a CDN. That breaks the wifi-off requirement **silently, and
 *  only in Arabic** — the exact failure mode you find on stage.
 *
 *  Three separate things have to be right, and only one of them is in the docs.
 */

/** 1. The worker URL. Absent from every planning document, and a production-only
 *  failure.
 *
 *  MapLibre v6 on Vite needs its worker registered explicitly, and the import
 *  must be `?worker&url`, not `?url`. The dist worker imports a sibling module,
 *  `maplibre-gl-shared.mjs`; plain `?url` emits the worker file verbatim without
 *  it, so the worker dies on its first import and no sources ever load. Dev works
 *  either way, which is what makes it dangerous. */
setWorkerUrl(workerUrl);

/** 2. The plugin, from our own origin, registered once and eagerly.
 *
 *  `public/vendor/`, not `src/vendor/` as 06 §4 suggests: MapLibre resolves the
 *  URL against document.baseURI and then hands it to the **web worker**, which
 *  loads it with importScripts. It has to be same-origin and untransformed, and
 *  `public/` is copied byte-for-byte. Routing a UMD script through Vite's module
 *  graph is precisely what must not happen here.
 *
 *  The vendored file is 133,355 B with its 97 KB ICU WASM inlined as base64 —
 *  one self-contained asset, no `.wasm` sibling to serve. A unit test asserts it
 *  is byte-identical to the npm package, so provenance is checked without the
 *  package being a runtime dependency.
 *
 *  Module scope, not a useEffect: setRTLTextPlugin throws on a second call, and
 *  React 19 StrictMode double-invokes effects.
 *
 *  Eager, never lazy. Lazy defers the failure to the moment an Arabic label
 *  enters the viewport. The worker's own wait is a hard 5 s (TIMEOUT in
 *  rtl_text_plugin_worker.ts), which on a cold demo machine is not much headroom. */
const PLUGIN_URL = `${import.meta.env.BASE_URL}vendor/mapbox-gl-rtl-text.js`;

/** Dev-only escape hatch. `?rtl=off` skips registration so a test can prove the
 *  Arabic canvas actually *differs* with shaping on — every other check can pass
 *  while the glyphs render as tofu. */
const disabled =
  import.meta.env.DEV && new URLSearchParams(window.location.search).get('rtl') === 'off';

export type RtlStatus = 'loaded' | 'disabled' | 'failed';

let status: RtlStatus = 'failed';

/** 3. Failure is visible, not a console warning.
 *
 *  The risk register's whole point is that this breaks quietly. Callers await
 *  this before constructing a map and surface a fault in the UI if it rejects. */
export const rtlReady: Promise<RtlStatus> = disabled
  ? Promise.resolve((status = 'disabled'))
  : setRTLTextPlugin(PLUGIN_URL, /* lazy */ false)
      .then(() => {
        const s = getRTLTextPluginStatus();
        if (s !== 'loaded') {
          throw new Error(
            `RTL text plugin status "${s}" — Arabic map labels will not shape. ` +
              `Expected ${PLUGIN_URL} to be served from this origin.`,
          );
        }
        status = 'loaded';
        return status;
      })
      .catch((err: unknown) => {
        status = 'failed';
        // Rethrow after recording, so a caller can render the fault and a test
        // can assert on it rather than scraping the console.
        throw err instanceof Error ? err : new Error(String(err));
      });

export function rtlStatus(): RtlStatus {
  return status;
}

/** Exposed for the offline-Arabic gate, which has to assert the plugin was
 *  loaded *before* the first map was constructed. */
declare global {
  interface Window {
    __aqabaAquaAi?: { rtlStatus: () => RtlStatus; pluginUrl: string };
  }
}
window.__aqabaAquaAi = { rtlStatus, pluginUrl: PLUGIN_URL };
