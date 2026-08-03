---
version: alpha
name: ReefShield Aqaba
description: Hydrographic-chart interface for wadi-to-reef sediment forecasting on the Gulf of Aqaba, bilingual Arabic and English.
export: css-tailwind
colors:
  canvas: oklch(0.985 0.006 200)
  surface: oklch(1.000 0.000 200)
  surface-2: oklch(0.960 0.010 200)
  hairline: oklch(0.900 0.014 200)
  hairline-2: oklch(0.840 0.020 200)
  ink: oklch(0.240 0.030 210)
  ink-2: oklch(0.420 0.028 205)
  ink-3: oklch(0.545 0.022 205)
  ink-inverse: oklch(0.940 0.012 202)
  accent: oklch(0.520 0.085 205)
  risk-minimal: oklch(0.900 0.020 95)
  risk-low: oklch(0.845 0.070 80)
  risk-moderate: oklch(0.755 0.120 68)
  risk-high: oklch(0.655 0.150 52)
  risk-critical: oklch(0.535 0.165 32)
  risk-minimal-stroke: "{colors.risk-low}"
  risk-low-stroke: "{colors.risk-moderate}"
  risk-moderate-stroke: "{colors.risk-high}"
  risk-high-stroke: "{colors.risk-critical}"
  risk-critical-stroke: "{colors.ink}"
  risk-minimal-on: "{colors.ink}"
  risk-low-on: "{colors.ink}"
  risk-moderate-on: "{colors.ink}"
  risk-high-on: "{colors.ink}"
  risk-critical-on: "{colors.ink-inverse}"
  state-focus: "{colors.accent}"
  state-selected: "{colors.accent}"
  data-measured: "{colors.ink-2}"
  data-modelled: "{colors.ink-3}"
typography:
  sans:
    fontFamily: IBM Plex Sans
  arabic:
    fontFamily: IBM Plex Sans Arabic
  mono:
    fontFamily: IBM Plex Mono
  2xs:
    fontSize: 0.694rem
    lineHeight: "1.3"
  xs:
    fontSize: 0.833rem
    lineHeight: "1.35"
  sm:
    fontSize: 1rem
    lineHeight: "1.5"
  md:
    fontSize: 1.2rem
    lineHeight: "1.4"
  lg:
    fontSize: 1.44rem
    lineHeight: "1.3"
  xl:
    fontSize: 1.728rem
    lineHeight: "1.2"
rounded:
  sm: 2px
  md: 3px
spacing:
  space-1: 4px
  space-2: 8px
  space-3: 12px
  space-4: 16px
  space-5: 24px
  space-6: 32px
  space-7: 48px
  space-8: 64px
---

## Overview

ReefShield forecasts where flood sediment from desert wadis will reach the coral reef of
the Gulf of Aqaba, so a marine-park officer can decide which reef zone to survey first.
The interface is a survey instrument, not a product dashboard: the Gulf has been charted,
sounded and measured for two centuries, and this belongs to that lineage. Isobath
hairlines are the structural system — the same contour language draws panel dividers, the
focus ring, the loading state and the plume's own density contours, because on a
hydrographic chart chrome and data always spoke one visual language.

## Colors

Every neutral carries a small chroma at hue 200–215, the Gulf's own hue. Use these rather
than a grey scale; a pure grey reads as unconsidered.

`accent` is the only interactive colour and it is never a data colour. It sits at least
0.78 from every hazard band in OKLab, so it cannot be read as a risk level. Do not use it
to encode a value.

The hazard ramp runs pale through sediment ochre to deep vermilion and is monotonic in
lightness, so it survives greyscale, projector gamma and a photograph of the screen. Never
substitute a green-to-red ramp: it fails deuteranopia, and green is wrong for a sediment
hazard.

`minimal` measures 1.29 against `canvas` and is invisible as a bare fill. Every hazard fill
therefore carries a 1px stroke from the matching `risk-*-stroke` token. A fill alone is not
a boundary.

Text on a hazard fill comes from the matching `risk-*-on` token, never a fixed choice. The
required ink flips partway up the ramp, and hard-coding one value fails contrast on the
bands that carry the most urgent information.

Colour values are generated, not transcribed: `scripts/qa_frontend_palette.py --emit-css`
writes the token file and `--emit-ts` writes the hex form the map consumes. Edit the
generator, never the output.

## Themes

Light is the default, encoded above. Dark redefines the same token names — never create
parallel `-dark` tokens.

| Token | Dark value |
| --- | --- |
| `canvas` | `oklch(0.180 0.024 215)` |
| `surface` | `oklch(0.225 0.026 215)` |
| `surface-2` | `oklch(0.270 0.028 215)` |
| `hairline` | `oklch(0.330 0.026 213)` |
| `hairline-2` | `oklch(0.400 0.028 213)` |
| `ink` | `oklch(0.940 0.012 202)` |
| `ink-2` | `oklch(0.780 0.020 205)` |
| `ink-3` | `oklch(0.620 0.022 208)` |
| `ink-inverse` | `oklch(0.240 0.030 210)` |
| `accent` | `oklch(0.780 0.105 200)` |
| `risk-minimal` | `oklch(0.420 0.045 95)` |
| `risk-low` | `oklch(0.510 0.080 80)` |
| `risk-moderate` | `oklch(0.600 0.115 66)` |
| `risk-high` | `oklch(0.685 0.150 50)` |
| `risk-critical` | `oklch(0.735 0.150 34)` |
| `risk-moderate-on` | `{colors.ink-inverse}` |
| `risk-high-on` | `{colors.ink-inverse}` |

The ramp darkens with risk on light ground and lightens with risk on dark ground. In both
cases it moves away from the canvas, so severity always reads as contrast.

Themes switch by `data-theme` on the document root, and an explicit choice must win over
the operating-system preference in both directions. Style components through tokens only —
a component that references a raw value inside a media query will be correct in one theme
and wrong in the other.

`risk-moderate` in dark theme reaches only 4.02 against its best available text colour, so
no text may sit on that band in dark theme. Render moderate chips on `surface` with a
`risk-moderate` stroke instead of a filled ground.

## Typography

`sans` and `arabic` are one superfamily, so Arabic and English share weight, rhythm and
vertical proportion instead of being two typefaces bolted together. Set the Arabic face
from the document language, not per component.

The scale is a minor third. Weight and colour carry more hierarchy than size does — build
from three levers together, never size alone.

Every measurement, coordinate, timestamp and identifier sets in `mono` with tabular
figures. Numbers that will be compared must align in a column, and the alignment must
survive a language switch.

Use Western digits in both languages. Arabic-Indic numerals would break column alignment in
the mono face.

Isolate every measurement, coordinate, identifier, timestamp and percentage with
`unicode-bidi: isolate` and `dir="ltr"`. Without it, right-to-left rendering reorders
`2.18 g/L` into `g/L 2.18`. Prefer the CSS property over U+2068/U+2069 characters, which
end up in copied text and screen-reader output.

## Layout

Write logical properties only — inline-start and inline-end, never left and right. This
applies to one-off fixes as much as to components. Transforms have no logical equivalent, so
multiply a direction-aware translate by `--dir`.

The map is never smaller than half the viewport. Layout mirrors under right-to-left; the map
does not, and neither do the compass, the north arrow, the scale bar, coordinate values or
contour rendering. Chart time axes always run left to right, and a time slider's track must
agree with the chart beneath it rather than with the reading direction.

Space unevenly on purpose: group related controls tightly, then put real air between
groups. Equal spacing everywhere reads as nothing having been decided.

## Elevation & Depth

Hairlines are the container model, not cards. A boundary is a 1px `hairline`, and elevation
is expressed by a ground change from `canvas` to `surface`. Reserve shadow for genuinely
floating layers — popover, dialog, map tooltip — and never apply it to an inline panel.

## Shapes

Radii stay at 2px for chips and inputs and 3px for panels. Larger radii read as moulded
plastic rather than a drawn chart.

## Components

`ValueWithUnit` is the only way a number reaches the screen. It applies bidi isolation,
tabular figures and the provenance form in one place. Do not render a bare numeric value.

Provenance is encoded in form, never in hue: a solid stroke is measured, a dashed stroke is
modelled, a hatched fill is an uncertainty envelope. Form survives colour-blindness,
greyscale and projector gamma; hue does not.

Pass `null` for absent data. A gap renders as a gap, visibly distinct from a measured zero;
coercing missing to `0` asserts a measurement that was never taken.

Every component needs default, hover, focus-visible, active, disabled, loading, empty,
error and stale states designed. Stale is a real state in forecast mode, not a hypothetical.

Every component appears on `/specimen` in light and dark against left-to-right and
right-to-left, as four separate documents. Radix primitives portal to `document.body`, so a
nested direction wrapper would render popovers in the document's direction and hide the
failure.

## Do's and Don'ts

- Do render a plume as a contoured field with its caveats attached. Never draw a single
  trajectory line, and never label a contour level as a percentage chance of impact — the
  levels are peak-normalised relative density.
- Do label provisional data in the interface, not only in the repository.
- Do make every fact the map encodes reachable as text.
- Don't use emoji as a layer or section icon.
- Don't use `rounded-xl` cards floating on a gradient.
- Don't use a navy-and-neon-cyan glassmorphic treatment.
- Don't centre body content; this is a dense tool and it aligns to a grid.
- Don't render an uncited assistant answer as an answer. It is a different state, not a
  badge on the same one.
