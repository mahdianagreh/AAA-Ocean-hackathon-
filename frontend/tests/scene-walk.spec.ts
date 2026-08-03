import { expect, test } from '@playwright/test';

/** The eight-scene walk — 00-master-plan.md's storyboard traceability, and
 *  12-testing-and-demo-safety.md's second load-bearing artefact.
 *
 *  "One test driving all eight storyboard scenes end to end. Runs in CI and again
 *  before the freeze. If the demo can break on stage, this catches it first."
 *
 *  Scene 6 does NOT reveal a satellite plume. Concept §15.3 says it should; that is
 *  superseded, and the panel shows the null result as a finding instead. The walk
 *  asserts the superseded version is absent, because a scene that quietly went
 *  missing is exactly what this is for.
 */

async function ready(page: import('@playwright/test').Page, lang = 'en') {
  await page.goto(`/?theme=light&lang=${lang}`);
  await page.waitForSelector('[data-risk-card]', { timeout: 30_000 });
  await page.waitForSelector('[data-map="true"] canvas', { timeout: 30_000 });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1500);
}

const step = async (page: import('@playwright/test').Page, n: number) => {
  await page.locator('[data-time-handle="true"]').focus();
  for (let i = 0; i < n; i++) {
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(350);
  }
  await page.waitForTimeout(500);
};

for (const lang of ['en', 'ar'] as const) {
  test(`all eight scenes walk end to end (${lang})`, async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await ready(page, lang);

    // --- 1. The problem: narrow coast, steep catchments, reef metres offshore ---
    await expect(page.locator('[data-map="true"] canvas')).toBeVisible();
    const layers = await page.evaluate(() => {
      const m = (window as unknown as { __map?: { getStyle: () => { layers: Array<{ id: string }> } } }).__map;
      return m ? m.getStyle().layers.map((l) => l.id) : [];
    });
    for (const id of ['isobaths', 'catchments-fill', 'reef-fill', 'outlets', 'mooring']) {
      expect(layers, `layer ${id} is missing from the style`).toContain(id);
    }

    // --- 2. A historical storm: AQ-2016-10-28 selected -----------------------
    await expect(page.locator('[data-mode="historical"]')).toHaveAttribute('data-state', 'on');
    await expect(page.getByText(/2016-10-2[68]/).first()).toBeVisible();

    // --- 3. Land prediction: rainfall, exposure, the activated outlet --------
    await expect(page.getByText(/AQ-C01/).first()).toBeVisible();
    await step(page, 2);
    const bands = await page.evaluate(() =>
      [...document.querySelectorAll('[data-risk-card] [data-band]')].map((el) =>
        el.getAttribute('data-band'),
      ),
    );
    expect(bands.length).toBe(5);
    // AQ-C01 leads on the flood day — it carries 96% of the discharge.
    await expect(page.locator('[data-risk-card]').first()).toHaveAttribute(
      'data-risk-card',
      'AQ-C01',
    );

    // --- 4. Marine prediction: the plume layer exists and is contoured -------
    expect(layers).toContain('plume-fill');
    expect(layers).toContain('plume-line');
    // Empty until Abd's per-timestep contours land, and the legend says so rather
    // than the map drawing an invented shape.
    // Bilingual: the walk runs in both languages, so the assertion has to accept
    // either rendering rather than silently only testing English.
    await expect(
      page.locator('[data-legend="true"]').getByText(/relative density|كثافة نسبية/).first(),
    ).toBeVisible();

    // --- 5. Reef exposure: zones and a legend that does not overclaim --------
    await expect(page.locator('[data-legend="true"]').getByText(/same sensitivity|الحساسية نفسها/)).toBeVisible();
    for (const id of ['R-01', 'R-08']) {
      await expect(page.getByRole('complementary').getByText(id, { exact: true }).first()).toBeVisible();
    }

    // --- 6. Validation: measured mooring, and the satellite NULL as a finding -
    await page.locator('[data-open-overlay="validation"]').click();
    const val = page.locator('[data-overlay="validation"]');
    await expect(val).toBeVisible();
    await expect(val.getByText('2.18').first()).toBeVisible();
    await expect(val.getByText('NO-GO')).toBeVisible();
    // Superseded: the walk asserts we do NOT claim a revealed satellite plume.
    await expect(val).not.toContainText(/reveal(s|ed)? the (actual )?satellite plume/i);
    await page.locator('[data-overlay-close="true"]').click();
    await expect(val).toBeHidden();

    // --- 7. What-if: move transmission loss, watch the answer change ---------
    const before = await page.evaluate(
      () =>
        document
          .querySelector('[data-risk-card] [data-band]')
          ?.getAttribute('data-band') ?? '',
    );
    const slider = page.locator('[data-scenario="transmissionLoss"] [role="slider"]');
    await slider.focus();
    // Home, not ArrowLeft. Radix mirrors arrow keys with reading direction — which
    // is correct, and is DirectionProvider doing its job — so in Arabic ArrowLeft
    // RAISES the value. An earlier version of this assertion pressed ArrowLeft and
    // failed only in the ar walk, which was the test assuming a physical direction
    // rather than the app being wrong. Home/End are direction-independent.
    await page.keyboard.press('Home');
    await page.waitForTimeout(700);

    await expect(page.locator('[data-mode="scenario"]')).toHaveAttribute('data-state', 'on');
    const loss = Number(await slider.getAttribute('aria-valuenow'));
    // Home is the minimum of the documented 20–85% range.
    expect(loss).toBe(20);

    const after = await page.evaluate(
      () =>
        document
          .querySelector('[data-risk-card] [data-band]')
          ?.getAttribute('data-band') ?? '',
    );
    const order = ['minimal', 'low', 'moderate', 'high', 'critical'];
    // Less of the flood soaks into the wadi bed, so more reaches the sea and
    // exposure must not fall. This is the physical relationship, asserted.
    expect(
      order.indexOf(after),
      `transmission loss ${loss}% did not raise exposure (${before} -> ${after})`,
    ).toBeGreaterThanOrEqual(order.indexOf(before));

    // --- 8. Recommendation: the alert, with confidence and caveat ------------
    const card = page.locator('[data-risk-card]').first();
    await expect(card.locator('[data-confidence="true"]')).toBeVisible();
    await expect(card.locator('[data-drivers="true"]')).toBeVisible();
    // Every card admits the index is provisional and the probability is absent.
    await expect(card.locator('[data-missing="true"]').first()).toBeVisible();

    expect(errors, `page errors during the walk: ${errors.join(' | ')}`).toEqual([]);
  });
}

test.describe('the honest panels', () => {
  test('provenance shows the figures, the counts and the exclusion', async ({ page }) => {
    await ready(page);
    await page.locator('[data-open-overlay="provenance"]').click();
    const p = page.locator('[data-overlay="provenance"]');
    await expect(p).toBeVisible();
    // 42 of the 43 manifest entries; overview_01 is excluded on purpose. main added
    // nine more QA figures after this panel was first written.
    await expect(p.locator('[data-figure]')).toHaveCount(42);
    await expect(p.getByText(/42 shown, of 43 in the manifest and 46 PNGs/)).toBeVisible();
    await expect(p.getByText(/overview_01_master_all_layers\.png is excluded/)).toBeVisible();
    // And the licence obligation that actually has a condition attached.
    await expect(p.getByText(/share-alike \(ODbL\)/)).toBeVisible();
  });

  test('a figure opens in a lightbox with its own QA caption', async ({ page }) => {
    await ready(page);
    await page.locator('[data-open-overlay="provenance"]').click();

    // The expected caption is read from the derived fixture rather than hardcoded.
    // An earlier version asserted "Exactly one polygon of 397.3" and broke when the
    // sea polygon grew to 615.1 km² on main — the assertion was pinning a measured
    // value, which is the same mistake the docs gate used to make. The invariant is
    // "the lightbox shows the caption the QA run wrote", not any particular number.
    const file = 'coastline_01_single_sea_body.png';
    const expected = await page.evaluate(async (f) => {
      const r = await fetch('/fixtures/provenance.json');
      const j = (await r.json()) as { figures: Array<{ file: string; caption: string }> };
      return j.figures.find((x) => x.file === f)?.caption ?? '';
    }, file);
    expect(expected.length).toBeGreaterThan(40);

    await page.locator(`[data-figure="${file}"]`).click();
    // Radix Dialog nests: the lightbox title is the filename.
    await expect(page.getByText(file).first()).toBeVisible();
    await expect(page.getByText(expected.slice(0, 60), { exact: false })).toBeVisible();
  });

  test('limitations renders all nine, from the documents', async ({ page }) => {
    await ready(page);
    await page.locator('[data-open-overlay="limitations"]').click();
    const l = page.locator('[data-overlay="limitations"]');
    await expect(l).toBeVisible();
    await expect(l.locator('[data-limitation]')).toHaveCount(9);
    await expect(l.getByText(/forcing_limitations\.md/).first()).toBeVisible();
  });

  test('the assistant refuses to answer without a citation', async ({ page }) => {
    await ready(page);
    await page.locator('[data-open-overlay="assistant"]').click();
    const a = page.locator('[data-overlay="assistant"]');

    // A question the corpus genuinely cannot answer: the market research is
    // deliberately excluded, so this must be the distinct no-answer state — not a
    // hedged answer, and not an answer with a weak citation stapled on.
    await a.locator('[data-assistant-input="true"]').fill('what is our expected market value');
    await a.getByRole('button', { name: /Search/ }).click();
    await expect(a.locator('[data-assistant-state="no_sourced_answer"]')).toBeVisible();
    await expect(a.locator('[data-assistant-state="answered"]')).toHaveCount(0);
  });

  test('a question the corpus genuinely does not cover gets no answer', async ({ page }) => {
    // `transmission` and `loss` appear in ZERO corpus sections. That is not a
    // retrieval failure — it confirms the correction already recorded against
    // pitch_limitations.md, that the infiltration problem is missing from it. So
    // the honest response is silence plus the searched list.
    await ready(page);
    await page.locator('[data-open-overlay="assistant"]').click();
    const a = page.locator('[data-overlay="assistant"]');
    await a.locator('[data-assistant-input="true"]').fill('transmission loss');
    await a.getByRole('button', { name: /Search/ }).click();
    await expect(a.locator('[data-assistant-state="no_sourced_answer"]')).toBeVisible();
  });

  test('the assistant cites a real file and section when it does answer', async ({ page }) => {
    await ready(page);
    await page.locator('[data-open-overlay="assistant"]').click();
    const a = page.locator('[data-overlay="assistant"]');
    await a.locator('[data-assistant-input="true"]').fill('satellite validation plume imagery');
    await a.getByRole('button', { name: /Search/ }).click();

    const answered = a.locator('[data-assistant-state="answered"]');
    await expect(answered).toBeVisible();
    // Citations are real paths into this repo, not invented references.
    await expect(answered.locator('[data-citation]').first()).toBeVisible();
    await expect(answered.getByText(/docs\/.+\.md|tasks\/.+\.md/).first()).toBeVisible();
  });
});
