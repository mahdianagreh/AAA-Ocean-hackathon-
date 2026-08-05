import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

/** Phase 5: hardening. 09-accessibility-and-integrity.md's verification list,
 *  mechanised — plus the integrity rules, which are checkable and therefore should
 *  be checked rather than trusted.
 */

async function ready(page: import('@playwright/test').Page, lang = 'en', theme = 'light') {
  await page.goto(`/?theme=${theme}&lang=${lang}`);
  await page.waitForSelector('[data-risk-card]', { timeout: 30_000 });
  await page.waitForSelector('[data-map="true"] canvas', { timeout: 30_000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1500);
}

test.describe('automated axe pass', () => {
  for (const theme of ['light', 'dark'] as const) {
    for (const lang of ['en', 'ar'] as const) {
      test(`no violations on the main view (${theme}/${lang})`, async ({ page }) => {
        await ready(page, lang, theme);
        const r = await new AxeBuilder({ page })
          // The MapLibre canvas and its controls are third-party DOM we do not
          // author. 09 requires keyboard pan and zoom, which is asserted separately
          // below against the real map rather than through axe.
          .exclude('.maplibregl-map')
          .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
          .analyze();

        const serious = r.violations.filter(
          (v) => v.impact === 'critical' || v.impact === 'serious',
        );
        expect(
          serious,
          serious.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`).join('\n'),
        ).toEqual([]);
      });
    }
  }

  for (const overlay of ['validation', 'provenance', 'limitations', 'assistant'] as const) {
    test(`no violations in the ${overlay} panel`, async ({ page }) => {
      await ready(page);
      await page.locator(`[data-open-overlay="${overlay}"]`).click();
      await expect(page.locator(`[data-overlay="${overlay}"]`)).toBeVisible();
      await page.waitForTimeout(overlay === 'provenance' ? 2500 : 600);

      const r = await new AxeBuilder({ page })
        .exclude('.maplibregl-map')
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze();
      const serious = r.violations.filter(
        (v) => v.impact === 'critical' || v.impact === 'serious',
      );
      expect(
        serious,
        serious.map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`).join('\n'),
      ).toEqual([]);
    });
  }
});

test.describe('keyboard', () => {
  test('every overlay opens, traps focus and returns it on Escape', async ({ page }) => {
    await ready(page);
    const trigger = page.locator('[data-open-overlay="limitations"]');
    await trigger.focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-overlay="limitations"]')).toBeVisible();

    // Focus must be inside the dialog, not left behind on the page underneath.
    const inside = await page.evaluate(() =>
      Boolean(document.activeElement?.closest('[data-overlay]')),
    );
    expect(inside).toBe(true);

    await page.keyboard.press('Escape');
    await expect(page.locator('[data-overlay="limitations"]')).toBeHidden();
    // Focus returns to what opened it — otherwise a keyboard user is dumped at the
    // top of the document after every panel.
    await expect(trigger).toBeFocused();
  });

  test('the map is keyboard pannable', async ({ page }) => {
    await ready(page);
    const before = await page.evaluate(() => {
      const m = (window as unknown as { __map?: { getCenter: () => { lng: number; lat: number } } }).__map;
      return m ? m.getCenter() : null;
    });
    await page.locator('[data-map="true"] canvas').focus();
    for (let i = 0; i < 6; i++) await page.keyboard.press('ArrowUp');
    await page.waitForTimeout(900);
    const after = await page.evaluate(() => {
      const m = (window as unknown as { __map?: { getCenter: () => { lng: number; lat: number } } }).__map;
      return m ? m.getCenter() : null;
    });
    expect(after!.lat).not.toBeCloseTo(before!.lat, 4);
  });

  test('hit areas on the controls are at least 24px', async ({ page }) => {
    await ready(page);
    const small: string[] = [];
    for (const sel of [
      '[data-time-handle="true"]',
      // The checkbox mark is 12px on purpose — 02 §5 keeps controls small. Its hit
      // area is extended by a ::before pseudo-element, which boundingBox() cannot
      // see, so this measures the effective target: what a pointer can actually
      // land on. Measuring the mark was the test being wrong, not the control.
      'label:has([data-layer="reef"])',
      '[data-open-overlay="validation"]',
      '[data-scenario-reset="true"]',
    ]) {
      const box = await page.locator(sel).first().boundingBox();
      if (!box || box.width < 24 || box.height < 24) {
        small.push(`${sel} ${box ? `${Math.round(box.width)}x${Math.round(box.height)}` : 'no box'}`);
      }
    }
    expect(small, `hit areas below 24px: ${small.join(', ')}`).toEqual([]);
  });
});

test.describe('integrity rules, asserted', () => {
  test('no measurement renders without bidi isolation in Arabic', async ({ page }) => {
    await ready(page, 'ar');
    const bad = await page.evaluate(() =>
      [...document.querySelectorAll('[data-provenance]')]
        .filter((el) => {
          const s = getComputedStyle(el);
          return el.getAttribute('dir') !== 'ltr' && s.unicodeBidi !== 'isolate';
        })
        .map((el) => el.textContent ?? ''),
    );
    expect(bad).toEqual([]);
  });

  test('every value on screen carries a provenance or is a declared gap', async ({ page }) => {
    // 09 verification: "Every value on screen traceable to a provenance field."
    await ready(page);
    const n = await page.evaluate(() => ({
      withProvenance: document.querySelectorAll('[data-provenance]').length,
      // A gap must never render a number. That is the whole point of the marker:
      // "missing" and "zero" are different facts, and 09 rule 4 forbids drawing the
      // second when you have the first.
      numericGaps: [...document.querySelectorAll('[data-missing="true"]')]
        .map((el) => el.textContent ?? '')
        .filter((s) => /\d/.test(s)),
    }));
    expect(n.withProvenance).toBeGreaterThan(20);
    expect(n.numericGaps).toEqual([]);

    // This test used to assert `gaps > 0` on the default view, because
    // runoff_probability was null on every card while data/models/ was empty. A
    // registered model now fills it, so zero gaps here is the honest state and the
    // old assertion was pinning a measured value rather than the rule.
    //
    // The rule still needs proving, so it is proven where a gap is still correct:
    // what-if mode cannot re-run the model against moved sliders, so the fallback
    // index reports no probability at all — and says so rather than computing one.
    await page.locator('[data-mode="scenario"]').click();
    await page.waitForTimeout(700);
    const gaps = await page.locator('[data-risk-card] [data-missing="true"]').count();
    expect(gaps, 'what-if mode must declare the probability it cannot compute').toBeGreaterThan(0);
  });

  test('nothing claims a plume probability anywhere in the view', async ({ page }) => {
    await ready(page);
    const text = await page.evaluate(() => document.body.innerText);
    // The one phrase 07 §4 forbids: a density band described as a chance of impact.
    expect(text).not.toMatch(/\d+\s*%\s*(chance|probability)\s+(of\s+)?(impact|flood)/i);
    expect(text).not.toMatch(/probability this location floods/i);
  });

  test('reduced motion is honoured', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await ready(page);
    const d = await page.evaluate(() => {
      const el = document.querySelector('[data-risk-card] [data-band]');
      return el ? getComputedStyle(el).transitionDuration : '';
    });
    // 05: reduced motion must not mean "nothing happens" — the state still changes,
    // it just cuts instead of tweening. So the duration collapses rather than the
    // transition being removed.
    // Chromium reports 0.01ms as "1e-05s", which the first version of this regex
    // did not match — the app was correct and the assertion was not.
    expect(Number.parseFloat(d)).toBeLessThan(0.001);
  });
});

test.describe('the nine component states', () => {
  test('loading, empty, error and stale all exist on the specimen', async ({ page }) => {
    await page.goto('/specimen?solo=1&theme=light&lang=en');
    await page.waitForSelector('[data-specimen="states"]', { timeout: 20_000 });
    for (const s of ['loading', 'empty', 'error', 'stale']) {
      await expect(page.locator(`[data-state="${s}"]`).first()).toBeVisible();
    }
  });

  test('a gap is visibly distinct from a zero', async ({ page }) => {
    await page.goto('/specimen?solo=1&theme=light&lang=en');
    const gap = page.locator('[data-missing="true"]').first();
    await expect(gap).toBeVisible();
    // Not styled as a number: no mono, no tabular figures, different ink.
    const ff = await gap.evaluate((el) => getComputedStyle(el).fontFamily);
    expect(ff).not.toContain('IBM Plex Mono');
    await expect(gap).not.toHaveText(/^-?0/);
  });
});
