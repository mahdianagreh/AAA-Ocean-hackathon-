import { expect, test, type Page } from '@playwright/test';

/** Smoke coverage for the AQABA AQUA AI rebuild.
 *
 *  It answers three questions the older specs cannot, because they all predate
 *  the router: does every new route render at all, does it render without a
 *  console error, and does it show real backend data rather than an untranslated
 *  i18n key.
 *
 *  The unresolved-key assertion is the load-bearing one. A missing translation
 *  does not throw — react-i18next renders the key itself — so `reports.title`
 *  would sit on screen looking almost like a heading. Only a test catches that. */

const ROUTES: Array<{ path: string; expect: RegExp }> = [
  { path: '/', expect: /See the flood before it reaches the reef/i },
  { path: '/login', expect: /Welcome back/i },
  { path: '/signup', expect: /Request Access/i },
  { path: '/dashboard', expect: /Aqaba/i },
  { path: '/events', expect: /Event catalogue/i },
  { path: '/alerts', expect: /Alerts/i },
  { path: '/reef-zones', expect: /Reef zones/i },
  { path: '/reef-zones/R-03', expect: /Sensitivity weight/i },
  { path: '/dashboard/replay', expect: /Event replay/i },
  { path: '/dashboard/validation', expect: /Validation/i },
  { path: '/dashboard/provenance', expect: /Provenance/i },
  { path: '/limitations', expect: /Honest limits/i },
  { path: '/assistant', expect: /Explain \/ Ask/i },
  { path: '/reports', expect: /Reports/i },
  { path: '/sites/score', expect: /Site scoring/i },
  { path: '/account', expect: /Preferences/i },
  { path: '/no-such-page', expect: /No such page/i },
];

/** Any t() key that reached the DOM untranslated. i18next echoes the key, and
 *  every namespace here uses dotted lowerCamelCase, so the shape is findable. */
async function unresolvedKeys(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const text = document.body.innerText;
    const re = /\b(validation|provenance|limitations|assistant|reports|sites|account|notFound|alerts|events|reefZones|reefZone|replay|nav|landing|auth)\.[a-z][A-Za-z0-9]*(\.[A-Za-z0-9]+)*\b/g;
    return Array.from(new Set(text.match(re) ?? []));
  });
}

for (const route of ROUTES) {
  test(`renders ${route.path}`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    page.on('console', (m) => {
      if (m.type() === 'error') errors.push(m.text());
    });

    await page.goto(`${route.path}?theme=light&lang=en`);
    await expect(page.locator('body')).toContainText(route.expect, { timeout: 20_000 });

    expect(await unresolvedKeys(page), `untranslated keys on ${route.path}`).toEqual([]);
    expect(errors, `page errors on ${route.path}`).toEqual([]);
  });
}

test('Arabic flips direction and resolves its own keys', async ({ page }) => {
  await page.goto('/reef-zones?theme=light&lang=ar');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.locator('html')).toHaveAttribute('lang', 'ar');
  await expect(page.locator('body')).toContainText(/مناطق الشعاب/, { timeout: 20_000 });
  expect(await unresolvedKeys(page)).toEqual([]);
});

test('alerts page reports the feed honestly, whichever state it is in', async ({ page }) => {
  /** This deliberately does NOT assert a particular zone appears.
   *
   *  `/alerts` is derived from the single most recent stored exposure run, and
   *  that run is global mutable state this page does not own. Two things move
   *  it: several pages trigger a calculation on the default outlet AQ-O01, which
   *  reaches no named reef zone at 24 h and therefore empties the feed; and
   *  exposure results are TTL-cached, so re-posting identical parameters returns
   *  the ORIGINAL run_id and never becomes "latest" again. An earlier version of
   *  this test asserted R-03 and failed for exactly that reason — the assertion
   *  was about ambient state, not about the page.
   *
   *  The page's actual contract is narrower and is what is checked here: it
   *  shows either real alert rows or the documented empty state, and it never
   *  invents a row. Anything with a reef-zone id must look like a real one. */
  await page.goto('/alerts?theme=light&lang=en');
  const body = page.locator('body');
  await expect(body).toContainText(/Alerts/i, { timeout: 20_000 });

  const text = await body.innerText();
  const zoneIds = text.match(/\bR-\d{2}\b/g) ?? [];

  if (zoneIds.length === 0) {
    // The honest empty state must explain itself, not just render nothing.
    expect(text).toMatch(/No alert is stored|stored exposure run/i);
  } else {
    // Only R-01..R-08 exist. Anything else would be fabricated.
    for (const id of zoneIds) {
      expect(Number(id.slice(2))).toBeGreaterThanOrEqual(1);
      expect(Number(id.slice(2))).toBeLessThanOrEqual(8);
    }
  }
});

test('login does not fake a session', async ({ page }) => {
  await page.goto('/login?theme=light&lang=en');
  await page.getByLabel(/email/i).fill('someone@example.org');
  await page.getByLabel(/password/i).first().fill('hunter2hunter2');
  await page.getByRole('button', { name: /sign in/i }).click();
  // It must stay put. Navigating to /dashboard here would be the exact lie the
  // no-auth notice exists to prevent.
  await expect(page).toHaveURL(/\/login/);
});
