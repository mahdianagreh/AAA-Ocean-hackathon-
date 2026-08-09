import { test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

/** Screenshot evidence for the Phase 8 design pass — every page in light + dark
 *  and EN + AR, filed under tasks/phase8/evidence/<route>/.
 *
 *  NOT part of the normal suite: it is skipped unless SCREENSHOTS=1, so a plain
 *  `playwright test` stays fast. Run it with:
 *    SCREENSHOTS=1 npx playwright test tests/evidence.spec.ts
 *
 *  ?lang / ?theme seed the UI store on load (the same channel the specimen and
 *  the other specs use), so each combination renders on first paint. */

const ROUTES: Array<{ slug: string; path: string }> = [
  { slug: 'home', path: '/' },
  { slug: 'login', path: '/login' },
  { slug: 'signup', path: '/signup' },
  { slug: 'dashboard', path: '/dashboard' },
  { slug: 'replay', path: '/dashboard/replay' },
  { slug: 'reef-zones', path: '/reef-zones' },
  { slug: 'reef-zone', path: '/reef-zones/R-01' },
  { slug: 'alerts', path: '/alerts' },
  { slug: 'reports', path: '/reports' },
  { slug: 'assistant', path: '/assistant' },
  { slug: 'validation', path: '/dashboard/validation' },
  { slug: 'provenance', path: '/dashboard/provenance' },
  { slug: 'site-score', path: '/sites/score' },
  { slug: 'limitations', path: '/limitations' },
  { slug: 'system-health', path: '/system-health' },
  { slug: 'data-explorer', path: '/data-explorer' },
  { slug: 'events', path: '/events' },
  { slug: 'account', path: '/account' },
];

const COMBOS: Array<{ lang: 'en' | 'ar'; theme: 'light' | 'dark' }> = [
  { lang: 'en', theme: 'light' },
  { lang: 'en', theme: 'dark' },
  { lang: 'ar', theme: 'light' },
  { lang: 'ar', theme: 'dark' },
];

const OUT = join(process.cwd(), '..', 'tasks', 'phase8', 'evidence');

test.describe('phase 8 screenshot evidence', () => {
  test.skip(!process.env.SCREENSHOTS, 'set SCREENSHOTS=1 to capture evidence');

  for (const { slug, path } of ROUTES) {
    test(`evidence: ${slug}`, async ({ page }) => {
      const dir = join(OUT, slug);
      mkdirSync(dir, { recursive: true });
      for (const { lang, theme } of COMBOS) {
        const sep = path.includes('?') ? '&' : '?';
        await page.goto(`${path}${sep}lang=${lang}&theme=${theme}`);
        // Let fonts and first data settle; the map screen needs its canvas.
        await page.evaluate(() => document.fonts.ready);
        await page.waitForTimeout(1200);
        await page.screenshot({
          path: join(dir, `${lang}-${theme}.png`),
          fullPage: true,
        });
      }
    });
  }
});
