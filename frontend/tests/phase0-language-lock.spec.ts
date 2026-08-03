import { expect, test } from '@playwright/test';

/** Phase 0 gate, mechanised.
 *
 *  The gate itself is an observation — "read a screenshot with the product name
 *  removed; could someone identify what it is for?" — but everything underneath
 *  it is checkable, and a check that runs is worth more than a check someone
 *  remembers to do.
 */

const COMBOS = [
  { theme: 'light', lang: 'en', dir: 'ltr' },
  { theme: 'light', lang: 'ar', dir: 'rtl' },
  { theme: 'dark', lang: 'en', dir: 'ltr' },
  { theme: 'dark', lang: 'ar', dir: 'rtl' },
] as const;

test.describe('document chrome', () => {
  for (const { theme, lang, dir } of COMBOS) {
    test(`${theme}/${lang} sets lang, dir and data-theme on <html>`, async ({ page }) => {
      await page.goto(`/specimen?solo=1&theme=${theme}&lang=${lang}`);

      const html = page.locator('html');
      // On <html>, not a wrapper: form controls, scrollbars and text selection
      // read the document direction.
      await expect(html).toHaveAttribute('lang', lang);
      await expect(html).toHaveAttribute('dir', dir);
      await expect(html).toHaveAttribute('data-theme', theme);
    });
  }

  test('language is reachable by URL alone', async ({ page }) => {
    // The demo must be able to open straight into Arabic, and a bug report has
    // to be reproducible by pasting a link.
    await page.goto('/?lang=ar');
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    await expect(page.locator('html')).toHaveAttribute('lang', 'ar');
  });

  test('theme=system leaves data-theme off so the media query decides', async ({ page }) => {
    // Writing data-theme="system" would match neither selector and silently pin
    // the page to the :root light values.
    await page.goto('/');
    await expect(page.locator('html')).not.toHaveAttribute('data-theme', /.*/);
  });
});

test.describe('tokens resolve per theme', () => {
  for (const { theme, lang } of COMBOS) {
    test(`${theme}/${lang} resolves canvas and ink from the right scope`, async ({ page }) => {
      await page.goto(`/specimen?solo=1&theme=${theme}&lang=${lang}`);
      const { canvas, ink } = await page.evaluate(() => {
        const s = getComputedStyle(document.documentElement);
        return {
          canvas: s.getPropertyValue('--canvas').trim(),
          ink: s.getPropertyValue('--ink').trim(),
        };
      });
      // Asserting the exact value would duplicate the generator, so assert the
      // direction: light canvas is bright with dark ink, dark is the inverse.
      const L = (v: string) => Number(/oklch\(([\d.]+)/.exec(v)?.[1] ?? NaN);
      expect(L(canvas)).toBeGreaterThan(0);
      if (theme === 'light') {
        expect(L(canvas)).toBeGreaterThan(0.9);
        expect(L(ink)).toBeLessThan(0.4);
      } else {
        expect(L(canvas)).toBeLessThan(0.3);
        expect(L(ink)).toBeGreaterThan(0.8);
      }
    });
  }
});

test.describe('bidi isolation', () => {
  for (const lang of ['en', 'ar'] as const) {
    test(`values keep number before unit in ${lang}`, async ({ page }) => {
      await page.goto(`/specimen?solo=1&theme=light&lang=${lang}`);
      const row = page.locator('tr', { has: page.getByText('Turbidity peak') });
      const text = (await row.locator('td').innerText()).replace(/\s+/g, ' ').trim();
      // Without isolation, RTL renders this as `g/L 2.18`.
      expect(text).toBe('2.18 g/L');
    });
  }

  test('every measurement is isolated, not just the first', async ({ page }) => {
    await page.goto('/specimen?solo=1&theme=light&lang=ar');
    const values = page.locator('[data-provenance]');
    const n = await values.count();
    expect(n).toBeGreaterThan(4);
    for (let i = 0; i < n; i++) {
      await expect(values.nth(i)).toHaveAttribute('dir', 'ltr');
      await expect(values.nth(i)).toHaveCSS('unicode-bidi', 'isolate');
    }
  });

  test('missing renders as a gap, never as zero', async ({ page }) => {
    await page.goto('/specimen?solo=1&theme=light&lang=en');
    const gap = page.locator('[data-missing="true"]').first();
    await expect(gap).toBeVisible();
    await expect(gap).not.toHaveText(/^0/);
  });

  test('missing text is not set in the Latin mono face', async ({ page }) => {
    // Regression: "No data" used font-mono, and in Arabic (لا توجد بيانات) that
    // face has no Arabic coverage, so it fell back mid-string with broken
    // spacing. Only numbers get mono.
    await page.goto('/specimen?solo=1&theme=light&lang=ar');
    const gap = page.locator('[data-missing="true"]').first();
    const ff = await gap.evaluate((el) => getComputedStyle(el).fontFamily);
    expect(ff).not.toContain('IBM Plex Mono');
  });

  test('score ranges do not reverse in Arabic', async ({ page }) => {
    // Regression: `0–20` rendered as `20–0` in the RTL pane. The en-dash is a
    // neutral character, so between two digit runs in an RTL paragraph the order
    // resolves backwards unless the span is isolated.
    for (const lang of ['en', 'ar'] as const) {
      await page.goto(`/specimen?solo=1&theme=light&lang=${lang}`);
      // Scoped to the ramp: the risk cards carry data-band too, so an unscoped
      // selector is a strict-mode violation rather than a real failure.
      const ramp = page.locator('#hazard');
      await expect(ramp.locator('[data-band="minimal"]')).toContainText('0–20');
      await expect(ramp.locator('[data-band="critical"]')).toContainText('81–100');
    }
  });

  test('every mono run in the RTL pane is isolated', async ({ page }) => {
    // Anything in the mono face is a measurement, identifier, coordinate,
    // timestamp or range — 06 §5 says all of those isolate. A mono run without
    // dir="ltr" is a bidi bug waiting for the right value.
    await page.goto('/specimen?solo=1&theme=light&lang=ar');
    const unisolated = await page.evaluate(() =>
      [...document.querySelectorAll('span')]
        .filter((el) => getComputedStyle(el).fontFamily.includes('IBM Plex Mono'))
        .filter((el) => {
          const s = getComputedStyle(el);
          // isolated either directly, or by an isolated ancestor
          return !el.closest('[dir="ltr"]') && s.unicodeBidi !== 'isolate';
        })
        .map((el) => el.textContent?.trim() ?? ''),
    );
    expect(unisolated).toEqual([]);
  });
});

test.describe('the specimen matrix', () => {
  test('renders four real documents, one per combination', async ({ page }) => {
    await page.goto('/specimen');
    const frames = page.locator('iframe[data-pane]');
    await expect(frames).toHaveCount(4);

    for (const { theme, lang, dir } of COMBOS) {
      const f = page.frameLocator(`iframe[data-pane="${theme}-${lang}"]`);
      // Each pane is its own document with its own root attributes — which is
      // the whole reason for iframes rather than nested wrappers.
      await expect(f.locator(`html[dir="${dir}"][data-theme="${theme}"]`)).toBeAttached();
      await expect(f.locator('[data-specimen="glyphs"]')).toBeVisible();
      await expect(f.locator('[data-specimen="hazard"]')).toBeVisible();
    }
  });

  test('the hazard ramp renders all five bands with a stroke', async ({ page }) => {
    await page.goto('/specimen?solo=1&theme=light&lang=en');
    // Scoped to the ramp section: the risk cards carry `data-band` too, and every
    // band now appears in both places. Unscoped this is a strict-mode violation
    // rather than a failure — the ramp is fine, the selector was not.
    const ramp = page.locator('#hazard');
    for (const b of ['minimal', 'low', 'moderate', 'high', 'critical']) {
      const chip = ramp.locator(`[data-band="${b}"]`);
      await expect(chip).toBeVisible();
      // A fill alone is not a boundary — minimal measures 1.29 against canvas.
      const w = await chip.evaluate((el) => getComputedStyle(el).borderTopWidth);
      expect(w).toBe('1px');
    }
  });

  test('the three glyphs render as line art at every used size', async ({ page }) => {
    await page.goto('/specimen?solo=1&theme=light&lang=en');
    const svgs = page.locator('[data-specimen="glyphs"] svg');
    await expect(svgs).toHaveCount(9); // three glyphs × 16/24/32px
    for (let i = 0; i < 9; i++) {
      await expect(svgs.nth(i)).toHaveAttribute('stroke-width', '1');
    }
  });
});

test.describe('no CDN anywhere', () => {
  test('nothing is fetched from outside the dev origin', async ({ page }) => {
    // DoD item 9 is "works with wifi off". Fonts are the usual leak.
    const external: string[] = [];
    page.on('request', (r) => {
      const u = new URL(r.url());
      if (u.origin !== 'http://localhost:5173' && u.protocol !== 'data:') external.push(r.url());
    });
    await page.goto('/specimen?solo=1&theme=dark&lang=ar');
    await page.waitForLoadState('networkidle');
    expect(external).toEqual([]);
  });

  test('the Arabic face actually loads and is used', async ({ page }) => {
    await page.goto('/?lang=ar');
    await page.evaluate(() => document.fonts.ready);
    const loaded = await page.evaluate(() =>
      [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family),
    );
    expect(loaded).toContain('IBM Plex Sans Arabic');
  });
});
