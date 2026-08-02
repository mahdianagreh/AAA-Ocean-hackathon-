# 06 · Bilingual AR/EN and RTL

**Status:** locked before code · **Owner:** Ali · **Phase:** 0–1

> **This is the one document that must be right before the first component is written.**
> [`06-ali.md`](../../../tasks/phase2/06-ali.md) is explicit: *"Not a late-stage translation pass —
> build the layout RTL-capable from the first component, or you will rewrite it in the last three
> days."* Definition of done item 8 is bilingual AR/EN with working RTL.

There is **no RTL or i18n skill in the 202-skill registry.** These are our own rules.

---

## 1 · Architecture

`i18next` + `react-i18next`. Language lives in one place and everything derives from it.

```
lang state  ──> <html lang="ar" dir="rtl">  ──> CSS logical properties resolve
            ──> font stack swaps to --font-arabic
            ──> Intl.* formatters re-bind
            ──> MapLibre style switches name field to name:ar
```

Set `lang` and `dir` on `<html>`, not on a wrapper div — form controls, scrollbars and text selection
read the document direction, and a wrapper leaves them behind.

**Language is a URL parameter** (`?lang=ar`), not only a stored preference. The demo must be able to
open straight into Arabic, and a bug report needs to be reproducible.

---

## 2 · Logical properties — the rule that prevents the rewrite

**Never write a physical direction.** Not in a component, not in a one-off fix, not "just this once."

| Never | Always |
|---|---|
| `margin-left` / `margin-right` | `margin-inline-start` / `margin-inline-end` |
| `padding-left` / `padding-right` | `padding-inline-start` / `padding-inline-end` |
| `left` / `right` | `inset-inline-start` / `inset-inline-end` |
| `text-align: left` | `text-align: start` |
| `border-left` | `border-inline-start` |
| `translateX(10px)` | `translateX(calc(10px * var(--dir)))` where `--dir` is `1` or `-1` |

Tailwind v4 emits logical properties for `ms-*` / `me-*` / `ps-*` / `pe-*` / `start-*` / `end-*`.
**Lint for the physical variants** — this is far cheaper to enforce on day one than to find on day nine.

`flex-direction: row` already follows direction. `gap` is direction-agnostic. Grid `column` order
follows direction. Most layout needs no special handling; the failures cluster in absolute positioning
and transforms.

---

## 3 · What mirrors and what does not

Mirroring the wrong things is as broken as mirroring nothing.

| Mirrors | Does **not** mirror |
|---|---|
| Layout, panel order, reading order | **The map.** North stays up, east stays east |
| Navigation chevrons, back/forward | **Compass, north arrow, scale bar** |
| Progress and slider fill direction | **Chart time axes — time always runs left → right** |
| Drawer and popover side | **Latitude/longitude values and their signs** |
| Text alignment | **The isobath/contour rendering** |
| Icons that imply direction | Icons that imply an object (reef, catchment, mooring) |

**The time slider is the subtle one.** The control mirrors — its start edge follows reading direction —
but the *time axis it scrubs* does not. Earlier is always to the left, because the hyetograph beneath
it has time running left to right, and the two must agree. Getting this backwards makes the whole
time-scrub choreography feel wrong in Arabic without anyone being able to say why.

Decision: **in RTL, the slider track keeps left = earlier**, matching the chart. Verify on the
specimen route with a real Arabic speaker before Phase 4.

---

## 4 · MapLibre and Arabic — the failure that only shows up offline

> **MapLibre needs the RTL text plugin to shape Arabic labels. It is registered by URL, and the
> documented examples point at a CDN. That breaks the wifi-off requirement, silently, and only in
> Arabic.**

**The plugin package is `@mapbox/mapbox-gl-rtl-text`** (v0.4.0 at time of writing). MapLibre uses the
Mapbox-authored plugin; there is no `@maplibre/…` equivalent published.

```ts
import maplibregl from "maplibre-gl";

// Bundle the plugin as a local asset. Never a CDN URL — DoD item 9 is "works with wifi off".
const rtlPlugin = new URL(
  "../vendor/mapbox-gl-rtl-text.js",
  import.meta.url,
).toString();

maplibregl.setRTLTextPlugin(rtlPlugin, /* lazy */ false);
```

> **Check the signature against the version you install.** `setRTLTextPlugin` changed across MapLibre
> majors — older releases took a callback, newer ones return a promise — and `maplibre-gl` is on **v6**
> as of writing. Whether v6 still requires the plugin at all is the first thing to confirm in Phase 1.
> Treat the snippet above as intent, not as copy-paste.

Register **once at boot, before the first map instance**, and eagerly. Lazy loading defers the failure
to the moment an Arabic label enters the viewport — which in a demo is on stage.

**Phase 1 gate — this is the load-bearing part, not the snippet:** Arabic map labels render correctly
with the network disabled. Verify it; do not assume it.

**Label fields.** Our vector style selects `name:ar` when the language is Arabic and falls back to
`name` — OSM coverage of `name:ar` around Aqaba is good but not total, and a missing Arabic name must
fall back rather than render blank.

---

## 5 · Numbers, units and bidi

**Western digits (0–9) in both languages.** Scientific and technical convention in Jordan, and it keeps
`tabular-nums` aligned across a language switch. Arabic-Indic numerals would also break column
alignment in the mono face.

**Units and identifiers are bidi-isolated.** Without isolation, RTL reorders `2.18 g/L` into
`g/L 2.18`, and `AQ-C01` can render with the digits leading.

```tsx
// Every measurement goes through this. There is no second way to render a value.
<span dir="ltr" style={{ unicodeBidi: "isolate" }} className="font-mono tabular-nums">
  {value}&nbsp;<span className="unit">{unit}</span>
</span>
```

Prefer the CSS `unicode-bidi: isolate` over manual U+2068/U+2069 characters — the characters end up in
copied text and in screen-reader output.

**Isolate all of:** measurements with units, coordinates, catchment and zone IDs, timestamps,
percentages, file paths, and any English product name inside Arabic prose.

**Dates and times.** `Intl.DateTimeFormat` with the active locale, but a **fixed calendar and
timezone**: Gregorian, UTC, displayed with an explicit `UTC` suffix. The event contract is specified in
UTC and the mooring record is timezone-converted from local — mixing calendars into that would
undermine carry-over rule 5.

---

## 6 · Translation content

Keys are namespaced by surface (`map.layers.*`, `risk.card.*`, `limitations.*`). **No key holds a
sentence assembled from fragments** — Arabic word order is not English word order, so composition must
happen inside the translation string with interpolation.

```json
// Correct — the translator controls order
"risk.confidence": "{{pct}}% of {{n}} members exceed this catchment's {{threshold}}"

// Wrong — cannot be reordered for Arabic
"risk.confidence.prefix": "of members exceed"
```

This is why [`00-master-plan.md`](00-master-plan.md) asks Mahdi and Nizar for SHAP drivers and
confidence as **structured components rather than pre-rendered sentences**. A formatted English string
from the API cannot be translated at render time.

### The item with no technical fallback

> **Who writes and reviews the Arabic limitations and caveat copy?**
>
> Machine-translating scientific caveats is a scientific-integrity risk, and concept §22.4 scores
> exactly that. The limitations page and every risk-card caveat need a human Arabic reviewer.
> **Raise on Day 1.** Every other risk in this project has an engineering mitigation; this one does not.

---

## 7 · Fonts

IBM Plex Sans Arabic, IBM Plex Sans, IBM Plex Mono — self-hosted woff2, `font-display: swap`.

**Arabic subsetting is harder than Latin.** Shaping and ligature coverage limit how aggressively
`unicode-range` can split the face, so the Arabic file cannot be sliced the way a Latin one can.
Budget it as a single subset over the glyphs actually used and **measure it before Phase 5**, rather
than assuming it behaves like the Latin face.

Both language faces are preloaded. A language switch must not flash unstyled text — on a demo screen
that reads as a bug.

---

## 8 · Verification

1. `?lang=ar` produces `<html lang="ar" dir="rtl">` and every panel mirrors.
2. **Arabic map labels render with the network disabled.** Phase 1 gate.
3. Grep the codebase for `margin-left`, `padding-right`, `text-align: left`, `left:` — zero hits
   outside vendor code.
4. The specimen route renders every component in **both themes × both directions** — four
   combinations, one page. Every new primitive lands there the day it is added, not in Phase 5.
5. No measurement renders without bidi isolation. Spot-check `2.18 g/L`, `−1.75 ‰`, `AQ-C01`,
   `34.97073, 29.54560` in RTL.
6. Time axes still run left → right in Arabic, and the slider agrees with the chart beneath it.
7. A native Arabic reader walks all eight storyboard scenes before the freeze.
