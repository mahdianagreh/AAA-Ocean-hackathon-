# 02 · Design Tokens

**Status:** locked before code · **Owner:** Ali · **Phase:** 0

Every value below was derived and validated by script, not chosen by eye. The validator checks four
things: sRGB gamut, WCAG contrast for every text/ground pair, monotonic lightness across the hazard
ramp, and separation of adjacent hazard bands under simulated deuteranopia, protanopia and tritanopia.

Rationale lives in [`01-design-language.md`](01-design-language.md). This file is the reference you
type from.

---

## 1 · Ground and neutrals

All neutrals carry a small chroma at hue 203–263 — the Gulf's own blues, from the AQABA AQUA AI deep
navy through its aqua. A pure grey would read as unconsidered.

### Light

| Token | OKLCH | Hex | Contrast vs canvas |
|---|---|---|---|
| `--canvas` | `oklch(0.975 0.005 248)` | `#f4f7fa` | — |
| `--surface` | `oklch(1.000 0.000 248)` | `#ffffff` | — |
| `--surface-2` | `oklch(0.964 0.018 209)` | `#e6f7fa` | — |
| `--hairline` | `oklch(0.917 0.014 241)` | `#dce5ec` | — |
| `--hairline-2` | `oklch(0.850 0.020 241)` | `#c3d0da` | — |
| `--ink-3` | `oklch(0.540 0.040 257)` | `#607086` | **4.71** AA |
| `--ink-2` | `oklch(0.449 0.043 257)` | `#46566d` | **6.95** AA |
| `--ink` | `oklch(0.255 0.089 263)` | `#0a1f4d` | **14.85** AA |
| `--accent` | `oklch(0.535 0.100 224)` | `#027998` | **4.67** AA |

### Dark

| Token | OKLCH | Hex | Contrast vs canvas |
|---|---|---|---|
| `--canvas` | `oklch(0.178 0.032 261)` | `#09111f` | — |
| `--surface` | `oklch(0.225 0.036 261)` | `#121c2d` | — |
| `--surface-2` | `oklch(0.270 0.040 261)` | `#1b263a` | — |
| `--hairline` | `oklch(0.330 0.034 259)` | `#2b3647` | — |
| `--hairline-2` | `oklch(0.400 0.036 259)` | `#3c485b` | — |
| `--ink-3` | `oklch(0.620 0.030 250)` | `#798898` | **5.20** AA |
| `--ink-2` | `oklch(0.800 0.024 220)` | `#aec2c8` | **10.18** AA |
| `--ink` | `oklch(0.950 0.014 209)` | `#e4f1f3` | **16.39** AA |
| `--accent` | `oklch(0.710 0.120 203)` | `#08b7c3` | **7.69** AA |

> Both accents were specified a thousandth of a chroma **outside sRGB** and are clamped to the measured
> gamut boundary at their lightness and hue: light 0.101 → 0.100, dark 0.121 → 0.120. Do not raise
> either back. The table above shows the clamped values — what actually renders — not what was asked
> for.

> Light `--accent` sits at lightness 0.535, not the 0.538 of brand Marine Teal `#007A99`. At the brand
> lightness it measures 4.49 on `--surface-2` — one hundredth under AA, on the token that carries link
> text. 0.535 renders `#027998`, two steps of 255 off the brand hex in a single channel and
> indistinguishable on screen, and clears AA on every ground the accent can land on (`--canvas` **4.67**,
> `--surface` 5.02, `--surface-2` 4.55). **`#007A99` is what the token is derived from, not what it
> renders** — quote `#027998` when the swatch itself is the subject.

> Light `--ink-3` sits at lightness 0.540, not the 0.560 first drawn. At 0.560 it measured 4.33 against
> `--canvas` — AA for large text only. The retune brings it to **4.71**, clearing AA for body text on
> every ground the tokens offer (`--surface` 5.05, `--surface-2` 4.58). The validator prints every ink
> against every ground, not against canvas alone, so a shortfall like that is a stated limit rather
> than an axe finding later.

---

## 2 · Hazard ramp

Concept §14.5's five bands. **The ramp darkens with risk on light ground and lightens with risk on
dark ground** — in both cases moving *away* from the canvas, so severity always reads as contrast.

### Light — ramp darkens with risk

| Band | Score | OKLCH | Hex | vs canvas | Text on it |
|---|---|---|---|---|---|
| `minimal` | 0–20 | `oklch(0.900 0.020 95)` | `#e2ded0` | 1.25 | `--ink` (11.85) |
| `low` | 21–40 | `oklch(0.845 0.070 80)` | `#e4c898` | 1.50 | `--ink` (9.88) |
| `moderate` | 41–60 | `oklch(0.755 0.120 68)` | `#e2a055` | 2.08 | `--ink` (7.14) |
| `high` | 61–80 | `oklch(0.655 0.150 52)` | `#d67229` | 3.10 | `--ink` (4.78) |
| `critical` | 81–100 | `oklch(0.535 0.165 32)` | `#b93c27` | 5.21 | **`--ink-inverse`** (4.86) |

### Dark — ramp lightens with risk

| Band | Score | OKLCH | Hex | vs canvas | Text on it |
|---|---|---|---|---|---|
| `minimal` | 0–20 | `oklch(0.420 0.045 95)` | `#554d30` | 2.24 | `--ink` (7.33) |
| `low` | 21–40 | `oklch(0.510 0.080 80)` | `#7e612c` | 3.26 | `--ink` (5.03) |
| `moderate` | 41–60 | `oklch(0.600 0.115 66)` | `#ae7129` | 4.66 | **`--ink-inverse`** (3.93) |
| `high` | 61–80 | `oklch(0.685 0.150 50)` | `#e17a39` | 6.35 | **`--ink-inverse`** (5.37) |
| `critical` | 81–100 | `oklch(0.735 0.150 34)` | `#f98368` | 7.58 | **`--ink-inverse`** (6.40) |

**Text colour flips mid-ramp.** It is not one choice for the whole scale — `critical` in light and
everything from `moderate` up in dark need inverse ink. Hard-coding `--ink` across the ramp fails
contrast on the bands that matter most.

### Validation results

| Check | Result |
|---|---|
| sRGB gamut | All values in gamut (dark accent clamped) |
| Lightness monotonic | Yes, both themes |
| Adjacent-band separation under CVD | Worst case **0.162** (dark / tritanopia, minimal→low). Threshold 0.10. |
| Accent vs any hazard band | Min distance 0.887 light, 0.769 dark |
| Greyscale legibility | Guaranteed by monotonic lightness |

### Fill visibility rule

`minimal` on light ground is 1.25 against canvas — effectively invisible as a bare fill.

> **Every hazard fill carries a 1 px stroke at the next band up.** A fill alone is not a boundary.

---

## 3 · Semantic aliases

Components reference these, never the raw scale. Swapping a theme must never require touching a
component.

```css
--risk-minimal / --risk-low / --risk-moderate / --risk-high / --risk-critical
--risk-*-stroke        /* the next band up, per the fill rule */
--risk-*-on            /* --ink or --ink-inverse, per the table above */

--state-focus          /* --accent */
--state-selected       /* --accent */
--data-measured        /* --ink-2, always solid stroke   */
--data-modelled        /* --ink-3, always dashed stroke  */
--data-envelope        /* --ink-3 at 12% alpha, hatched  */
--data-missing         /* transparent + diagonal hatch — never a zero-valued fill */
```

`--data-*` tokens pair with a **form** rule, never hue alone. See
[`01-design-language.md`](01-design-language.md) §4.

---

## 4 · Type

```css
--font-sans:   "Montserrat", Inter, "IBM Plex Sans Arabic", system-ui, sans-serif;
--font-arabic: "IBM Plex Sans Arabic", "Montserrat", system-ui, sans-serif;
--font-mono:   "IBM Plex Mono", ui-monospace, monospace;
```

**Latin UI text is Montserrat** — weights 400 / 600 / 700, self-hosted under `public/fonts/` and
licensed OFL. It replaces IBM Plex Sans as the Latin face.

**Arabic stays on IBM Plex Sans Arabic, because Montserrat has no Arabic coverage at any weight.** The
brand's Montserrat identity is Latin-only by construction, not by choice; falling back to a system
Arabic face would change shaping and vertical rhythm mid-sentence. Set the Arabic face from the
document language, not per component.

IBM Plex Mono is retained for numerals — it is the only face here with tabular figures we have
verified in the committed file.

Minor-third scale (1.2). Weight carries hierarchy more than size.

| Token | Size | Use |
|---|---|---|
| `--text-2xs` | 0.694 rem | Map labels, axis ticks |
| `--text-xs` | 0.833 rem | Captions, chip labels, units |
| `--text-sm` | 1.000 rem | Body, table cells |
| `--text-md` | 1.200 rem | Panel titles |
| `--text-lg` | 1.440 rem | Section headings |
| `--text-xl` | 1.728 rem | The single focal number per view |

**Every measurement, coordinate, timestamp and identifier sets in `--font-mono` with
`font-variant-numeric: tabular-nums`.** Non-negotiable — numbers that get compared must align.

---

## 5 · Space, line and radius

A 4 px base. Spacing is uneven on purpose: related things sit tight, unrelated things get real air.

```css
--space-1: 4px;   --space-2: 8px;   --space-3: 12px;  --space-4: 16px;
--space-5: 24px;  --space-6: 32px;  --space-7: 48px;  --space-8: 64px;
```

**Hairlines are the container model, not cards.** The signature is contour lines; a border is a
1 px `--hairline`, and elevation is expressed by ground change (`--surface` over `--canvas`), not by
shadow.

```css
--rule:           1px solid var(--hairline);
--rule-strong:    1px solid var(--hairline-2);
--radius-hairline: 2px;   /* chart and map chrome, risk bands */
--radius-sm:       8px;   /* chips, inputs    */
--radius-md:      12px;   /* panels           */
--radius-lg:      16px;   /* dialogs, sheets  */
--radius-card:    20px;   /* brand cards      */
```

The brand radii are 8 / 12 / 16 / 20 px. The instrument surfaces are the exception: map chrome, chart
furniture and the risk bands keep `--radius-hairline` at 2 px, the radius they were drawn with — a
chart is drawn with a pen, not moulded in plastic. `rounded-xl` on everything is still on the
rejected-defaults list.

```css
--shadow-sm: 0 4px 12px rgb(10 31 77 / 0.08);
--shadow-md: 0 10px 30px rgb(10 31 77 / 0.12);
--shadow-lg: 0 20px 60px rgb(10 31 77 / 0.18);
```

Shadows are a three-step brand scale, all keyed to the deep navy `rgb(10 31 77)` — the same value as
`--ink` in light theme. They are used **only** for genuinely floating layers (popover, dialog, map
tooltip), never for inline panels: inline elevation is still a ground change from `--canvas` to
`--surface`.

---

## 6 · Theme switching

Tokens are defined on `:root`, redefined under `@media (prefers-color-scheme: dark)`, then redefined
again under `:root[data-theme="dark"]` and `:root[data-theme="light"]` so an explicit user choice wins
over the OS in both directions.

**Components style through tokens only.** A component that references a raw value inside a media query
is a bug — it will be correct in one theme and wrong in the other.

---

## 7 · Regenerating and re-validating

```bash
python3 scripts/qa_frontend_palette.py
```

If any value changes, re-run the validator and paste the results back into §2 — the contrast and CVD
numbers in this document are claims, and claims in this project carry evidence.

The validator checks:

1. Every colour is inside sRGB.
2. Every text/ground pair reaches WCAG AA.
3. Hazard lightness is monotonic in both themes.
4. Adjacent hazard bands stay ≥ 0.10 apart under all three CVD simulations.
5. The accent stays ≥ 0.25 from every hazard band.
