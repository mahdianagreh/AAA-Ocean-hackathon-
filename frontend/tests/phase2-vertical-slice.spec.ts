import { expect, test } from '@playwright/test';

/** The Phase 2 gate: it runs end to end.
 *
 *  00-master-plan.md calls this the most important milestone in the plan —
 *  "a system integrated on Day 11 has never been tested." So these check
 *  integration rather than components: that one cursor moves the map, the chart
 *  and the cards together, and that the honest states are actually on screen.
 */

async function ready(page: import('@playwright/test').Page, lang = 'en') {
  await page.goto(`/dashboard?theme=light&lang=${lang}`);
  await page.waitForSelector('[data-risk-card]', { timeout: 30_000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1200);
}

const bands = (page: import('@playwright/test').Page) =>
  page.evaluate(() =>
    [...document.querySelectorAll('[data-risk-card]')].map(
      (el) =>
        `${el.getAttribute('data-risk-card')}:${el.querySelector('[data-band]')?.getAttribute('data-band')}`,
    ),
  );

test.describe('the choreography', () => {
  test('one cursor moves the cards, the chart and the map together', async ({ page }) => {
    await ready(page);

    const before = await bands(page);
    const cursorBefore = await page
      .locator('[data-time-handle="true"]')
      .getAttribute('aria-valuenow');

    // Scrub to the flood day.
    await page.locator('[data-time-handle="true"]').focus();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(900);

    const after = await bands(page);
    const cursorAfter = await page
      .locator('[data-time-handle="true"]')
      .getAttribute('aria-valuenow');

    expect(cursorAfter).not.toBe(cursorBefore);
    // The bands must actually change — a cursor that moves without repainting the
    // cards is the failure this test exists for.
    expect(after).not.toEqual(before);

    // And the map's catchment fill must have been repainted from the same source.
    const fill = await page.evaluate(() => {
      const m = (window as unknown as { __map?: { getPaintProperty: (l: string, p: string) => unknown } }).__map;
      return m ? JSON.stringify(m.getPaintProperty('catchments-fill', 'fill-color')) : null;
    });
    expect(fill).toContain('AQ-C01');
  });

  test('the event reads as an arc, not a flat line', async ({ page }) => {
    await ready(page);
    const seen = new Set<string>();
    for (let i = 0; i < 5; i++) {
      if (i) {
        await page.locator('[data-time-handle="true"]').focus();
        await page.keyboard.press('ArrowRight');
        await page.waitForTimeout(600);
      }
      for (const b of await bands(page)) seen.add(b.split(':')[1]!);
    }
    // A ramp where every catchment sits in one band communicates nothing. The
    // first version of the index rated four of five `critical` on the peak day,
    // because all five catchments received rainfall within 10% of each other and
    // the index had no term that could tell them apart.
    expect(seen.size, `only these bands appeared: ${[...seen].join(', ')}`).toBeGreaterThan(2);
  });

  test('Wadi Yutum leads on the flood day', async ({ page }) => {
    await ready(page);
    await page.locator('[data-time-handle="true"]').focus();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(900);

    // AQ-C01 is 4,453 km² and carries 96% of the discharge. If the ranking puts a
    // 65 km² catchment above it, the index is measuring the wrong thing.
    const first = await page.locator('[data-risk-card]').first().getAttribute('data-risk-card');
    expect(first).toBe('AQ-C01');
  });
});

test.describe('honest states are on screen', () => {
  test('runoff probability is model output, or a gap — never a fabricated number', async ({
    page,
  }) => {
    await ready(page);
    // Both halves of this were once one assertion: `expect(a gap)`, correct while
    // data/models/ was empty. A trained artefact is registered now, so the number is
    // real and must be attributed; the gap is still required where nothing computed
    // one. Asserting only the first half would let a fabricated number through, and
    // only the second would fail the moment honesty improved.
    const card = page.locator('[data-risk-card]').first();
    await expect(card.getByText(/runoff_weighted_gbm_\w+/)).toBeVisible();
    await expect(card.locator('[data-missing="true"]')).toHaveCount(0);

    await page.locator('[data-mode="scenario"]').click();
    await page.waitForTimeout(700);
    // The model cannot be re-run in the browser against moved sliders, so what-if
    // reports no probability rather than one nothing computed.
    await expect(card.locator('[data-missing="true"]').first()).toBeVisible();
  });

  test('every card attributes its numbers — a model version or a provisional flag', async ({
    page,
  }) => {
    await ready(page);
    // The invariant, not the state: a card says which of the two it is showing.
    // Never neither (an unattributed number), never both (a claim contradicting
    // itself). This replaces "every card says the index is provisional", which was
    // true only while the index was the only path.
    for (const mode of ['default', 'scenario'] as const) {
      if (mode === 'scenario') {
        await page.locator('[data-mode="scenario"]').click();
        await page.waitForTimeout(700);
      }
      const attribution = await page.evaluate(() =>
        [...document.querySelectorAll('[data-risk-card]')].map((c) => ({
          id: c.getAttribute('data-risk-card'),
          model: /runoff_weighted_gbm_/.test(c.textContent ?? ''),
          provisional: /Provisional index|Stand-in index/.test(c.textContent ?? ''),
        })),
      );
      expect(attribution.length).toBe(5);
      for (const a of attribution) {
        expect(a.model !== a.provisional, `${mode}/${a.id}: model=${a.model} provisional=${a.provisional}`).toBe(true);
      }
    }
  });

  test('the time bar admits the axis is daily', async ({ page }) => {
    await ready(page);
    // 09 rule 8: never claim exactness. The event's own peak was a 3-hour window
    // and the slider steps in days, so the interval must not imply a resolution
    // the repo does not have.
    await expect(page.getByText(/Steps are daily/)).toBeVisible();
    await expect(page.getByText(/Wettest 3 h was 11\.71 mm/)).toBeVisible();
  });

  test('the plume legend says relative density, never probability', async ({ page }) => {
    await ready(page);
    const legend = page.locator('[data-legend="true"]');
    await expect(legend.getByText(/relative density/).first()).toBeVisible();
    await expect(legend.getByText(/not a probability of impact/)).toBeVisible();

    // The overclaim 07 §4 forbids is a *level* labelled as a percentage — "50%
    // chance of impact". Assert on the level rows rather than the prose, because
    // the caveat legitimately contains the word "probability" while saying it is
    // not one. My first version of this check matched its own caveat.
    const levelRows = await legend.locator('li').allInnerTexts();
    for (const row of levelRows) {
      expect(row, `a plume level is labelled as a percentage: ${row}`).not.toMatch(
        /\d\s*%|chance|probability of/i,
      );
    }
  });

  test('the reef legend does not imply zones differ in sensitivity', async ({ page }) => {
    await ready(page);
    await expect(
      page.locator('[data-legend="true"]').getByText(/same sensitivity/),
    ).toBeVisible();
  });
});

test.describe('controls', () => {
  test('the mode switch preserves the time cursor', async ({ page }) => {
    await ready(page);
    await page.locator('[data-time-handle="true"]').focus();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(600);
    const before = await page.locator('[data-time-handle="true"]').getAttribute('aria-valuenow');

    await page.locator('[data-mode="forecast"]').click();
    await page.waitForTimeout(500);

    // 03 §2: preserve where the ranges overlap, clamp otherwise — never reset.
    // Resetting loses the user's place mid-demo.
    expect(await page.locator('[data-time-handle="true"]').getAttribute('aria-valuenow')).toBe(
      before,
    );
  });

  test('a layer toggle actually hides the layer', async ({ page }) => {
    await ready(page);
    await page.locator('[data-layer="reef"]').click();
    await page.waitForTimeout(600);
    const vis = await page.evaluate(() => {
      const m = (window as unknown as { __map?: { getLayoutProperty: (l: string, p: string) => unknown } }).__map;
      return m ? m.getLayoutProperty('reef-fill', 'visibility') : null;
    });
    expect(vis).toBe('none');
  });

  test('the model-grid honesty overlay can be turned on', async ({ page }) => {
    await ready(page);
    await page.locator('[data-layer="modelGrid"]').click();
    await page.waitForTimeout(600);
    const n = await page.evaluate(() => {
      const m = (window as unknown as {
        __map?: { querySourceFeatures: (s: string) => unknown[]; getLayoutProperty: (l: string, p: string) => unknown };
      }).__map;
      return m
        ? { vis: m.getLayoutProperty('model-grid', 'visibility'), cells: m.querySourceFeatures('basemap-grid').length }
        : null;
    });
    expect(n?.vis).toBe('visible');
    // Two to three cells span the whole Gulf — that is the point of showing it.
    expect(n?.cells).toBeGreaterThan(10);
  });

  test('the slider is a real ARIA slider with keyboard support', async ({ page }) => {
    await ready(page);
    const h = page.locator('[data-time-handle="true"]');
    await expect(h).toHaveAttribute('role', 'slider');
    await expect(h).toHaveAttribute('aria-valuemin', '0');
    await h.focus();
    await page.keyboard.press('End');
    await page.waitForTimeout(400);
    const max = await h.getAttribute('aria-valuemax');
    expect(await h.getAttribute('aria-valuenow')).toBe(max);
    await page.keyboard.press('Home');
    await page.waitForTimeout(400);
    expect(await h.getAttribute('aria-valuenow')).toBe('0');
  });

  test('the time axis does not mirror in Arabic', async ({ page }) => {
    await ready(page, 'ar');
    // 06 §3, the subtle one: the control mirrors, the axis it scrubs does not.
    // Earlier stays on the left because the chart beneath it runs left to right,
    // and the two must agree.
    await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
    const trackDir = await page
      .locator('[data-time-handle="true"]')
      .evaluate((el) => el.closest('[dir]')?.getAttribute('dir'));
    expect(trackDir).toBe('ltr');
  });
});
