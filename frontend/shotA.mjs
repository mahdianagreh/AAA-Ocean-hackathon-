import { chromium } from 'playwright';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
await page.goto('http://localhost:5180/dashboard', { waitUntil: 'networkidle' });
await page.waitForSelector('[data-map="true"] canvas', { timeout: 15000 });
await page.click('[data-open-overlay="journey"]');
await page.waitForSelector('[data-journey-map="true"] canvas', { timeout: 15000 });
await page.waitForTimeout(3000);

// Check the mask layer actually exists in the live style.
const layerInfo = await page.evaluate(() => {
  const m = window.__journeyMap;
  const style = m.getStyle();
  const ids = style.layers.map((l) => l.id);
  return {
    hasMaskLayer: ids.includes('terrain-void-mask'),
    order: ids,
    terrainActive: !!m.getTerrain(),
  };
});
console.log('mask layer present:', layerInfo.hasMaskLayer);
console.log('terrain active:', layerInfo.terrainActive);
console.log('layer order:', JSON.stringify(layerInfo.order));

// Now click the UI zoom-out button repeatedly, exactly like a real user would.
const zoomOutBtn = page.locator('[data-journey-map="true"]').locator('..').locator('button').filter({ hasText: '' });
for (let i = 0; i < 15; i++) {
  await page.mouse.click(1189, 187); // approximate zoom-out button coords from the report
  await page.waitForTimeout(80);
}
await page.waitForTimeout(600);
const zoomAfter = await page.evaluate(() => window.__journeyMap.getZoom());
console.log('zoom after clicking zoom-out button 15x:', zoomAfter);
await page.screenshot({ path: '/private/tmp/claude-501/-Users-mahdi-Desktop-AAA/a6e1d1b4-4bb0-4aea-93b2-7f01e064190e/scratchpad/repro-userreport.png' });
await browser.close();
