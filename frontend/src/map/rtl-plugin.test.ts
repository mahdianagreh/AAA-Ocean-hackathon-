import { describe, expect, it } from 'vitest';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const require = createRequire(import.meta.url);
const ROOT = resolve(import.meta.dirname, '../..');
const VENDORED = resolve(ROOT, 'public/vendor/mapbox-gl-rtl-text.js');
const PACKAGED = resolve(ROOT, 'node_modules/@mapbox/mapbox-gl-rtl-text/dist/mapbox-gl-rtl-text.js');

const sha = (p: string) => createHash('sha256').update(readFileSync(p)).digest('hex');

/** The flagged risk, made mechanical.
 *
 *  00-master-plan.md's risk register calls the MapLibre RTL plugin the
 *  highest-value catch in the whole plan, because it breaks silently and only in
 *  Arabic. Most of that risk is checkable in about fifty milliseconds with no
 *  browser, which is worth far more than a note telling someone to remember.
 */
describe('the vendored RTL text plugin', () => {
  it('is byte-identical to the npm package', () => {
    // @mapbox/mapbox-gl-rtl-text is a devDependency for exactly this assertion.
    // Nothing imports it at runtime — the browser loads the committed copy from
    // our own origin — so this is how provenance gets checked without turning a
    // vendored asset into a runtime dependency that could silently drift.
    expect(sha(VENDORED)).toBe(sha(PACKAGED));
  });

  it('is self-contained, with its ICU data inline', () => {
    // 133,355 B with the ~97 KB WASM embedded as base64. If a future version
    // splits the WASM into a sibling file, this catches it — because MapLibre
    // hands the URL to a web worker and a missing sibling fails there, offline
    // and in Arabic only.
    const bytes = readFileSync(VENDORED);
    expect(bytes.byteLength).toBeGreaterThan(100_000);
    expect(bytes.toString('utf8', 0, 400)).toMatch(/base64|wasm|function/);
  });
});

interface RtlPlugin {
  applyArabicShaping: (s: string) => string;
  processBidirectionalText: (s: string, breaks: number[]) => string[];
  processStyledBidirectionalText: (s: string, scale: number[], breaks: number[]) => unknown;
}

/** Load the plugin the way MapLibre does.
 *
 *  The UMD returns its API object synchronously but populates it only after
 *  `WebAssembly.instantiate` resolves — so `Object.keys()` on the fresh export is
 *  empty and there is no promise on the module to await. What it does do is call
 *  `self.registerRTLTextPlugin(api)` once the WASM is live, which is exactly the
 *  handshake MapLibre's worker relies on.
 *
 *  Testing through that handshake rather than around it means this test exercises
 *  the real integration contract. It also means a future version that changed the
 *  handshake would fail here rather than in Arabic, offline, on stage.
 */
let loading: Promise<RtlPlugin> | null = null;

function loadPlugin(): Promise<RtlPlugin> {
  // Memoised, because `registerRTLTextPlugin` fires exactly once. The second
  // `require()` is served from Node's module cache without re-running the IIFE,
  // so a per-test load would hang forever waiting for a callback that already
  // happened. Same reason src/map/rtl.ts registers at module scope.
  loading ??= new Promise<RtlPlugin>((resolveApi, reject) => {
    const g = globalThis as unknown as {
      self?: unknown;
      registerRTLTextPlugin?: (api: RtlPlugin) => void;
    };
    g.self ??= globalThis;
    const timer = setTimeout(
      () => reject(new Error('registerRTLTextPlugin was never called — WASM did not instantiate')),
      15_000,
    );
    g.registerRTLTextPlugin = (api) => {
      clearTimeout(timer);
      resolveApi(api);
    };
    require(VENDORED);
  });
  return loading;
}

describe('Arabic shaping', () => {
  it('converts base letters into presentation forms', async () => {
    const rtl = await loadPlugin();

    // وادي اليتيم — Wadi Yutum, the demo path, and a real label on this map.
    const input = 'وادي اليتيم';
    const shaped = rtl.applyArabicShaping(input);

    expect(shaped).not.toBe(input);

    // This is the assertion that matters. The shaper emits presentation forms,
    // and TinySDF then rasterises those codepoints one at a time from the webfont.
    // If any base-block letter survives unshaped, the font would be asked for a
    // glyph the shaper did not produce — which is how Arabic map labels end up
    // rendering as tofu while every other check passes.
    for (const ch of shaped) {
      const cp = ch.codePointAt(0)!;
      const isArabicBaseLetter = cp >= 0x0620 && cp <= 0x064a;
      expect(
        isArabicBaseLetter,
        `U+${cp.toString(16).toUpperCase()} came back unshaped from applyArabicShaping`,
      ).toBe(false);
    }
  });

  it('reorders bidirectional text', async () => {
    const rtl = await loadPlugin();
    // متنزه العقبة البحري — Aqaba Marine Park, labelled on the map.
    const input = 'متنزه العقبة البحري';
    const lines = rtl.processBidirectionalText(input, [input.length]);
    expect(lines).toHaveLength(1);
    expect(lines[0]).not.toBe(input);
  });

  it('emits codepoints the committed face actually covers', async () => {
    const rtl = await loadPlugin();
    const shaped = rtl.applyArabicShaping('متنزه العقبة البحري');
    // Every shaped Arabic glyph must land in Presentation Forms-A (U+FB50-FDFF)
    // or Forms-B (U+FE70-FEFF) — the two blocks measured present in
    // IBMPlexSansArabic-Regular.woff2 at 196 and 140 codepoints. This is the
    // link between "the shaper works" and "the map can draw it".
    const arabicish = [...shaped].filter((ch) => {
      const cp = ch.codePointAt(0)!;
      return cp >= 0x0600 && cp <= 0xfeff && cp !== 0x0020;
    });
    expect(arabicish.length).toBeGreaterThan(5);
    for (const ch of arabicish) {
      const cp = ch.codePointAt(0)!;
      const inFormsA = cp >= 0xfb50 && cp <= 0xfdff;
      const inFormsB = cp >= 0xfe70 && cp <= 0xfeff;
      expect(
        inFormsA || inFormsB,
        `U+${cp.toString(16).toUpperCase()} is outside the presentation-form blocks the font covers`,
      ).toBe(true);
    }
  });
});

describe('the committed Arabic face can render what the shaper emits', () => {
  it('is present and large enough to carry the presentation forms', () => {
    // Measured with fontTools on this exact file: 252 Arabic base, 48 Arabic
    // Supplement, 196 Presentation Forms-A, 140 Forms-B, 243 Latin — 1,065
    // codepoints in 71,904 B. That coverage is the reason omitting `glyphs` from
    // the style works at all, so a subset that dropped the forms would break map
    // labels while leaving UI Arabic looking perfect.
    const face = readFileSync(resolve(ROOT, 'public/fonts/IBMPlexSansArabic-Regular.woff2'));
    expect(face.byteLength).toBe(71_904);
  });
});
