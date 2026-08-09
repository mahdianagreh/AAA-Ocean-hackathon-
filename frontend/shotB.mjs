import { chromium } from 'playwright';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
await page.goto('http://localhost:5180/dashboard', { waitUntil: 'networkidle' });
await page.waitForSelector('[data-map="true"] canvas', { timeout: 15000 });
await page.click('[data-open-overlay="journey"]');
await page.waitForSelector('[data-journey-map="true"] canvas', { timeout: 15000 });
await page.waitForTimeout(3500);

const box = await page.locator('[data-journey-map="true"] canvas').first().boundingBox();
const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
await page.mouse.move(cx, cy);
for (let i = 0; i < 25; i++) await page.mouse.wheel(0, 200);
await page.waitForTimeout(600);
const z1 = await page.evaluate(() => window.__journeyMap.getZoom());
console.log('zoom after wheel-out:', z1);
await page.screenshot({ path: '/private/tmp/claude-501/-Users-mahdi-Desktop-AAA/a6e1d1b4-4bb0-4aea-93b2-7f01e064190e/scratchpad/wide-fix-wheelout.png' });

// Hard diagonal drag at min zoom, same as the worst-case repro before.
await page.mouse.move(cx, cy);
await page.mouse.down();
for (let i = 1; i <= 15; i++) await page.mouse.move(cx - i * 30, cy - i * 15, { steps: 2 });
await page.mouse.up();
await page.waitForTimeout(600);
await page.screenshot({ path: '/private/tmp/claude-501/-Users-mahdi-Desktop-AAA/a6e1d1b4-4bb0-4aea-93b2-7f01e064190e/scratchpad/wide-fix-harddrag.png' });

// Free small drag -- confirm still not fighting the camera.
const before = await page.evaluate(() => window.__journeyMap.getZoom());
await page.mouse.move(cx, cy);
await page.mouse.down();
for (let i = 1; i <= 10; i++) await page.mouse.move(cx, cy - i * 15, { steps: 2 });
await page.mouse.up();
await page.waitForTimeout(400);
const after = await page.evaluate(() => window.__journeyMap.getZoom());
console.log('zoom stable through small drag:', before.toFixed(3), '->', after.toFixed(3));

await browser.close();
