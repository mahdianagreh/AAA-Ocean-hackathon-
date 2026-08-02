# 02 · Design Tokens

**Status:** locked before code · **Owner:** Ali · **Phase:** 0

Every value below was derived and validated by script, not chosen by eye. The validator checks four
things: sRGB gamut, WCAG contrast for every text/ground pair, monotonic lightness across the hazard
ramp, and separation of adjacent hazard bands under simulated deuteranopia, protanopia and tritanopia.

Rationale lives in [`01-design-language.md`](01-design-language.md). This file is the reference you
type from.

---

## 1 · Ground and neutrals

All neutrals carry a small chroma at hue 200–215 — the Gulf's own hue. A pure grey would read as
unconsidered.

### Light

| Token | OKLCH | Hex | Contrast vs canvas |
|---|---|---|---|
| `--canvas` | `oklch(0.985 0.006 200)` | `#f6fbfc` | — |
| `--surface` | `oklch(1.000 0.000 200)` | `#ffffff` | — |
| `--surface-2` | `oklch(0.960 0.010 200)` | `#ebf4f4` | — |
| `--hairline` | `oklch(0.900 0.014 200)` | `#d4e1e2` | — |
| `--hairline-2` | `oklch(0.840 0.020 200)` | `#bccfd0` | — |
| `--ink-3` | `oklch(0.545 0.022 205)` | `#627476` | **4.71** AA |
| `--ink-2` | `oklch(0.420 0.028 205)` | `#3b5254` | **8.02** AA |
| `--ink` | `oklch(0.240 0.030 210)` | `#0c2327` | **15.66** AA |
| `--accent` | `oklch(0.520 0.085 205)` | `#117780` | **5.09** AA |

### Dark

| Token | OKLCH | Hex | Contrast vs canvas |
|---|---|---|---|
| `--canvas` | `oklch(0.180 0.024 215)` | `#041418` | — |
| `--surface` | `oklch(0.225 0.026 215)` | `#0c1f23` | — |
| `--surface-2` | `oklch(0.270 0.028 215)` | `#152a2f` | — |
| `--hairline` | `oklch(0.330 0.026 213)` | `#26393d` | — |
| `--hairline-2` | `oklch(0.400 0.028 213)` | `#364c51` | — |
| `--ink-3` | `oklch(0.620 0.022 208)` | `#778a8d` | **5.19** AA |
| `--ink-2` | `oklch(0.780 0.020 205)` | `#a9bbbd` | **9.43** AA |
| `--ink` | `oklch(0.940 0.012 202)` | `#e2eeee` | **15.78** AA |
| `--accent` | `oklch(0.780 0.105 200)` | `#56ccd2` | **9.75** AA |

> The light accent was originally specified at chroma 0.110 and **fell outside sRGB**. It is clamped to
> 0.085, the measured gamut boundary at that lightness and hue. Do not raise it back.

---

## 2 · Hazard ramp

Concept §14.5's five bands. **The ramp darkens with risk on light ground and lightens with risk on
dark ground** — in both cases moving *away* from the canvas, so severity always reads as contrast.

### Light — ramp darkens with risk

| Band | Score | OKLCH | Hex | vs canvas | Text on it |
|---|---|---|---|---|---|
| `minimal` | 0–20 | `oklch(0.900 0.020 95)` | `#e2ded0` | 1.29 | `--ink` (12.12) |
| `low` | 21–40 | `oklch(0.845 0.070 80)` | `#e4c898` | 1.55 | `--ink` (10.11) |
| `moderate` | 41–60 | `oklch(0.755 0.120 68)` | `#e2a055` | 2.14 | `--ink` (7.30) |
| `high` | 61–80 | `oklch(0.655 0.150 52)` | `#d67229` | 3.20 | `--ink` (4.89) |
| `critical` | 81–100 | `oklch(0.535 0.165 32)` | `#b93c27` | 5.37 | **`--ink-inverse`** (4.72) |

### Dark — ramp lightens with risk

| Band | Score | OKLCH | Hex | vs canvas | Text on it |
|---|---|---|---|---|---|
| `minimal` | 0–20 | `oklch(0.420 0.045 95)` | `#554d30` | 2.22 | `--ink` (7.11) |
| `low` | 21–40 | `oklch(0.510 0.080 80)` | `#7e612c` | 3.23 | `--ink` (4.88) |
| `moderate` | 41–60 | `oklch(0.600 0.115 66)` | `#ae7129` | 4.62 | **`--ink-inverse`** (4.02) |
| `high` | 61–80 | `oklch(0.685 0.150 50)` | `#e17a39` | 6.30 | **`--ink-inverse`** (5.49) |
| `critical` | 81–100 | `oklch(0.735 0.150 34)` | `#f98368` | 7.52 | **`--ink-inverse`** (6.55) |

**Text colour flips mid-ramp.** It is not one choice for the whole scale — `critical` in light and
everything from `moderate` up in dark need inverse ink. Hard-coding `--ink` across the ramp fails
contrast on the bands that matter most.

### Validation results

| Check | Result |
|---|---|
| sRGB gamut | All values in gamut (light accent clamped) |
| Lightness monotonic | Yes, both themes |
| Adjacent-band separation under CVD | Worst case **0.162** (dark / tritanopia, minimal→low). Threshold 0.10. |
| Accent vs any hazard band | Min distance **0.78** light, **0.79** dark |
| Greyscale legibility | Guaranteed by monotonic lightness |

### Fill visibility rule

`minimal` on light ground is 1.29 against canvas — effectively invisible as a bare fill.

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
--font-sans:   "IBM Plex Sans", "IBM Plex Sans Arabic", system-ui, sans-serif;
--font-arabic: "IBM Plex Sans Arabic", "IBM Plex Sans", system-ui, sans-serif;
--font-mono:   "IBM Plex Mono", ui-monospace, monospace;
```

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
--rule:        1px solid var(--hairline);
--rule-strong: 1px solid var(--hairline-2);
--radius-sm:   2px;   /* chips, inputs   */
--radius-md:   3px;   /* panels          */
```

Radii stay small. A chart is drawn with a pen, not moulded in plastic — and `rounded-xl` everywhere is
on the rejected-defaults list.

Shadows are used **only** for genuinely floating layers (popover, dialog, map tooltip), never for
inline panels.

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
