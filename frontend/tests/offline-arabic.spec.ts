import { expect, test } from '@playwright/test';

/** The Phase 1 gate: **Arabic map labels render with the network off.**
 *
 *  00-master-plan.md's risk register calls this the highest-value catch in the
 *  plan, because it fails silently and only in Arabic — which in a demo means on
 *  stage. Five layers, cheapest first, because each one can pass while the next
 *  one fails:
 *
 *    1. the plugin registers before any map exists
 *    2. nothing is fetched from outside our origin, worker included
 *    3. the Arabic names are actually placed on the map
 *    4. the Arabic canvas *differs* with shaping disabled — 1-3 can all pass
 *       while every glyph renders as tofu
 *    5. the map still works with DNS blackholed
 */

const AR = '/dashboard?lang=ar&theme=light';

/** Wait for the map to exist and finish its first render. */
async function mapReady(page: import('@playwright/test').Page) {
  await page.waitForSelector('[data-map="true"] canvas', { timeout: 30_000 });
  await page.evaluate(() => document.fonts.ready);
  // MapLibre rasterises glyphs after document.fonts.load resolves, so give the
  // symbol layers a beat to place labels rather than asserting into a blank frame.
  await page.waitForTimeout(2500);
}

test.describe('the RTL plugin', () => {
  test('is loaded before the first map is constructed', async ({ page }) => {
    // Registering after a map exists leaves that map's already-shaped labels
    // unshaped, and the failure is invisible in English.
    await page.goto(AR);
    await expect
      .poll(() => page.evaluate(() => window.__aqabaAquaAi?.rtlStatus()), { timeout: 20_000 })
      .toBe('loaded');
    await mapReady(page);
  });

  test('is served from our own origin, not a CDN', async ({ page }) => {
    const url = await page.goto(AR).then(() =>
      page.evaluate(() => window.__aqabaAquaAi?.pluginUrl),
    );
    expect(url).toBeTruthy();
    expect(url).not.toMatch(/^https?:\/\//);
    expect(url).toContain('vendor/mapbox-gl-rtl-text.js');
  });
});

test.describe('no external requests', () => {
  test('every request stays on the dev origin, including the MapLibre worker', async ({ page }) => {
    const external: string[] = [];
    page.on('request', (r) => {
      const u = new URL(r.url());
      if (u.protocol === 'data:' || u.protocol === 'blob:') return;
      if (u.origin !== 'http://localhost:5173') external.push(r.url());
    });

    await page.goto(AR);
    await mapReady(page);
    // Pan and zoom, because a tile or glyph request that only fires on demand
    // would not show up on a static first paint.
    await page.mouse.move(500, 400);
    await page.mouse.down();
    await page.mouse.move(620, 470, { steps: 8 });
    await page.mouse.up();
    await page.keyboard.press('Equal');
    await page.waitForTimeout(1500);

    expect(external, `external requests: ${external.join(', ')}`).toEqual([]);
  });

  test('the style requests no glyph ranges at all', async ({ page }) => {
    // Omitting `glyphs` is what makes offline Arabic work — MapLibre rasterises
    // client-side with TinySDF from our webfonts instead. Any .pbf request means
    // a glyphs URL crept back into the style.
    const glyphs: string[] = [];
    page.on('request', (r) => {
      if (/\.pbf($|\?)|\/font\//.test(r.url())) glyphs.push(r.url());
    });
    await page.goto(AR);
    await mapReady(page);
    expect(glyphs).toEqual([]);
  });
});

test.describe('Arabic labels are placed and shaped', () => {
  test('the map carries real Arabic place names', async ({ page }) => {
    await page.goto(AR);
    await mapReady(page);

    const r = await page.evaluate(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const m = (window as any).__map;
      if (!m) return null;
      const names = (fn: 'queryRenderedFeatures' | 'querySourceFeatures', arg: unknown) =>
        (m[fn] as (a: unknown) => Array<{ properties: Record<string, unknown> }>)(arg)
          .map((f) => f.properties.name_ar)
          .filter(Boolean)
          .join(' ');
      return {
        // Placed on screen at the current framing.
        rendered: names('queryRenderedFeatures', {
          layers: ['label-protected', 'label-wadi', 'label-place'],
        }),
        // Present in the loaded sources regardless of framing.
        wadis: names('querySourceFeatures', 'basemap-wadis'),
      };
    });

    expect(r, 'window.__map was not exposed').not.toBeNull();

    // Two separate claims, because they fail for different reasons and an
    // earlier version of this test conflated them: وادي اليتيم dropped out when
    // the side rail widened by 1rem and pushed it off the viewport, which looked
    // like a labelling failure but was a framing change.
    //
    // 1. Arabic labels are actually PLACED at this framing.
    expect(r!.rendered).toContain('متنزه العقبة البحري');
    // 2. وادي اليتيم — the demo path — carries a real name:ar in the data.
    expect(r!.wadis).toContain('وادي اليتيم');
  });

  test('shaping visibly changes the canvas — the tofu check', async ({ page }) => {
    // This is the one that catches a silent failure. Layers 1-3 can all pass while
    // every Arabic glyph renders as a hollow box, because placement and shaping are
    // separate steps. If the canvas is byte-identical with the plugin disabled,
    // shaping did nothing.
    await page.goto(AR);
    await mapReady(page);
    const withPlugin = await page.locator('[data-map="true"] canvas').screenshot();

    await page.goto(`${AR}&rtl=off`);
    await mapReady(page);
    const withoutPlugin = await page.locator('[data-map="true"] canvas').screenshot();

    expect(
      Buffer.compare(withPlugin, withoutPlugin),
      'the Arabic map canvas is identical with and without the RTL plugin — shaping is not being applied',
    ).not.toBe(0);
  });
});

// The blackholed run lives in tests/wifi-off.offline.spec.ts, because
// launchOptions force a new worker and Playwright rejects test.use() for them
// inside a describe block. See the `chromium-offline` project in
// playwright.config.ts.
