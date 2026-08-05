import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { palette } from './palette.generated';

const read = (p: string) => readFileSync(resolve(import.meta.dirname, p), 'utf8');

/** A perfect generated token file that nothing imports still gives you an
 *  unstyled app, and nothing about that failure points at the cause. These tests
 *  are cheap and they catch exactly that class of mistake.
 *
 *  Value correctness is not tested here — scripts/qa_frontend_tokens.py proves
 *  the files are byte-identical to the generator, and the generator itself
 *  validates gamut, contrast, monotonicity and CVD separation. Duplicating that
 *  in TypeScript would create a second source of truth, which is the thing the
 *  whole arrangement exists to prevent.
 */
describe('token layer wiring', () => {
  const entry = read('../styles/index.css');
  // Parse the @import statements rather than searching the whole file — the
  // header comment names these files too, and a substring search finds the prose
  // first, which is how the first version of this test lied.
  const imports = [...entry.matchAll(/@import\s+"([^"]+)"/g)].map((m) => m[1]);

  it('imports the generated tokens before the Tailwind bridge', () => {
    const tokens = imports.indexOf('./tokens.generated.css');
    const theme = imports.indexOf('./theme.css');
    expect(tokens).toBeGreaterThan(-1);
    expect(theme).toBeGreaterThan(-1);
    // theme.css's `@theme inline` block references the custom properties that
    // tokens.generated.css declares, so the order is load-bearing.
    expect(tokens).toBeLessThan(theme);
  });

  it('imports tailwind first, then the font faces', () => {
    expect(imports[0]).toBe('tailwindcss');
    expect(imports).toContain('./fonts.css');
  });

  it('bridges every token the components use into Tailwind', () => {
    const theme = read('../styles/theme.css');
    for (const name of ['canvas', 'surface', 'hairline', 'ink', 'ink-2', 'ink-3', 'accent']) {
      expect(theme).toContain(`--color-${name}: var(--${name});`);
    }
    for (const band of ['minimal', 'low', 'moderate', 'high', 'critical']) {
      expect(theme).toContain(`--color-risk-${band}: var(--risk-${band});`);
      expect(theme).toContain(`--color-risk-${band}-on: var(--risk-${band}-on);`);
    }
  });

  it('uses @theme inline for colours, so nested scopes resolve correctly', () => {
    const theme = read('../styles/theme.css');
    // Without `inline`, Tailwind computes --color-canvas once against :root and a
    // nested [data-theme="dark"] region inherits the substituted light value.
    const inlineBlock = theme.slice(theme.indexOf('@theme inline'));
    expect(inlineBlock).toContain('--color-canvas: var(--canvas)');
  });

  it('clears the rejected default namespaces', () => {
    const theme = read('../styles/theme.css');
    // 01 §3's rejected defaults become build errors rather than review notes.
    expect(theme).toContain('--color-*: initial;');
    expect(theme).toContain('--radius-*: initial;');
  });
});

describe('map palette', () => {
  it('carries both themes as hex, which is all MapLibre can parse', () => {
    for (const theme of ['light', 'dark'] as const) {
      expect(palette[theme].canvas).toMatch(/^#[0-9a-f]{6}$/);
      for (const band of ['minimal', 'low', 'moderate', 'high', 'critical'] as const) {
        expect(palette[theme].risk[band]).toMatch(/^#[0-9a-f]{6}$/);
        expect(palette[theme].riskStroke[band]).toMatch(/^#[0-9a-f]{6}$/);
      }
    }
  });

  it('keeps the hazard ramp monotonic in lightness, in both directions', () => {
    // The ramp must darken with risk on light ground and lighten on dark, so
    // severity always reads as contrast against the canvas — and so it survives
    // greyscale, a bad projector, and a photograph of the screen (01 §4).
    const lum = (hex: string) => {
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const bands = ['minimal', 'low', 'moderate', 'high', 'critical'] as const;

    const light = bands.map((b) => lum(palette.light.risk[b]));
    const dark = bands.map((b) => lum(palette.dark.risk[b]));

    for (let i = 1; i < bands.length; i++) {
      expect(light[i]).toBeLessThan(light[i - 1]);
      expect(dark[i]).toBeGreaterThan(dark[i - 1]);
    }
  });

  it('never lets the accent read as a risk level', () => {
    // 01 §4: one accent, and it is not a data colour. The validator measures
    // ≥0.78 separation in OKLab; this is the cheap sRGB sanity check that the
    // emitted hex did not land on top of a band.
    const bands = ['minimal', 'low', 'moderate', 'high', 'critical'] as const;
    for (const theme of ['light', 'dark'] as const) {
      for (const b of bands) {
        expect(palette[theme].accent).not.toBe(palette[theme].risk[b]);
      }
    }
  });
});
