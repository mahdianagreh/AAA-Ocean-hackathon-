import { expect, test } from '@playwright/test';

/** DoD item 9, mechanised: **works with wifi off.**
 *
 *  Runs under the `chromium-offline` project, which launches Chromium with
 *  `--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost`. That is a DNS
 *  blackhole at the browser level rather than `page.route()` interception,
 *  deliberately: the MapLibre RTL text plugin is fetched by the **worker**, and
 *  route interception is not a bet worth taking on a requester you do not
 *  control. Blackholing at the resolver covers every one of them.
 *
 *  The gate itself is still the human observation — wifi physically off,
 *  `docker compose --profile frontend up`, open `/?lang=ar`, read the map. This
 *  exists so it never silently regresses between now and the freeze.
 */

const AR = '/dashboard?lang=ar&theme=light';

async function mapReady(page: import('@playwright/test').Page) {
  await page.waitForSelector('[data-map="true"] canvas', { timeout: 30_000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(2500);
}

test('the whole view works with DNS blackholed', async ({ page }) => {
  const failed: string[] = [];
  page.on('requestfailed', (r) => failed.push(r.url()));

  await page.goto(AR);

  // 1. The plugin loaded — from our origin, with no name resolution available.
  await expect
    .poll(() => page.evaluate(() => window.__aqabaAquaAi?.rtlStatus()), { timeout: 25_000 })
    .toBe('loaded');

  await mapReady(page);

  // 2. No fault panel. src/map/rtl.ts renders one on failure rather than warning
  //    to a console nobody is watching during a demo, so its absence is a real
  //    signal here.
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.locator('[data-map="true"] canvas')).toBeVisible();

  // 3. Arabic names are placed, not merely fetched.
  const names = await page.evaluate(() => {
    const m = (window as unknown as { __map?: { queryRenderedFeatures: (o: unknown) => Array<{ properties: Record<string, unknown> }> } }).__map;
    if (!m) return null;
    return m
      .queryRenderedFeatures({ layers: ['label-protected', 'label-wadi', 'label-place'] })
      .map((f) => f.properties.name_ar)
      .filter(Boolean)
      .join(' ');
  });
  expect(names).toContain('متنزه العقبة البحري');

  // 4. Nothing tried and failed. A failed request means something reached outside
  //    the origin — which is precisely the bug this file exists to prevent, and it
  //    would be invisible with the network up.
  expect(failed, `failed requests with DNS blackholed: ${failed.join(', ')}`).toEqual([]);

  // 5. The fonts really loaded, so the labels are glyphs rather than fallbacks.
  const loaded = await page.evaluate(() =>
    [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family),
  );
  expect(loaded).toContain('IBM Plex Sans Arabic');
});

test('the side rail still lists every value with no network', async ({ page }) => {
  // 09 rule 7 / 01 §6.5: the map is never the only path to a fact. If the map
  // fails, the numbers must still be readable — and with the fixture client they
  // come from committed GeoJSON, so there is nothing to be offline from.
  await page.goto(AR);

  // Scoped to the rail. Unscoped, `AQ-C01` matches four nodes — two in the rail
  // and two inside the Arabic prose that explains the coverage boundary — which is
  // itself evidence the textual equivalent is doing its job.
  const rail = page.getByRole('complementary');
  await expect(rail).toBeVisible({ timeout: 20_000 });

  for (const id of ['AQ-C01', 'AQ-C05', 'AQ-O01', 'AQ-O04', 'R-01', 'R-08']) {
    await expect(rail.getByText(id, { exact: true }).first()).toBeVisible();
  }

  // exact:true — "Wadi Yutum" also appears inside AQ-C01's caveat prose, so an
  // inexact match resolves to two nodes.
  await expect(rail.getByText('Wadi Yutum', { exact: true })).toBeVisible();
  await expect(rail.getByText('4453.08', { exact: false }).first()).toBeVisible();
});

test('names truncate at the end in RTL, not the start', async ({ page }) => {
  // Regression. The reef zone names are Latin script inside an RTL container, and
  // with a fixed direction the ellipsis landed at the START — the rail read
  // "…rine Science Station / Cedar Pride", losing the half that identifies it.
  // Losing the end of a name is a cosmetic truncation; losing the beginning is a
  // different zone.
  await page.goto(AR);
  const rail = page.getByRole('complementary');
  await expect(rail).toBeVisible({ timeout: 20_000 });

  const names = await rail.locator('[dir="auto"]').allInnerTexts();
  expect(names.length).toBeGreaterThan(10);
  for (const n of names) {
    expect(n.trimStart().startsWith('…'), `"${n}" is truncated at the start`).toBe(false);
  }
});
