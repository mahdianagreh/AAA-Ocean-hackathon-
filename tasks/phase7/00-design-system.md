# Phase 7 — The AQABA AQUA AI Design System

**Read this before writing any component in this phase.** Everyone builds against it;
Ali is its custodian. Every value below is copied from
`python3 scripts/qa_frontend_palette.py`, which is the source of truth. If this
document and that script ever disagree, **the script is right and this file is stale**.

---

## 1. Brand essence

> **Marine Intelligence · Environmental AI · Ocean Technology**

Scientific · Innovative · Trustworthy · Minimal · Premium · Sustainable · Data-driven
· Calm.

The visual job of this product is unusual and worth stating plainly: it must look
**premium enough to be believed** and **honest enough to be trusted**. Those pull
against each other. A dashboard that looks like a trading terminal implies a
precision this system does not have. A dashboard that looks like a lab notebook
implies it is not ready. The resolution is: **calm surfaces, generous space,
confident type — and every uncomfortable number stated out loud, in the same
typeface as the comfortable ones.**

---

## 2. Colour — and the one rule that is machine-enforced

**You never write a colour.** `scripts/qa_frontend_tokens.py` check [6] fails the
build on any `#rrggbb` in `frontend/src/`. Colours come from tokens, always.

```bash
python3 scripts/qa_frontend_tokens.py   # must exit 0 before you push
```

### The brand palette (guidelines §3)

| Name | Hex | Role |
|---|---|---|
| Deep Navy | `#0A1F4D` | Primary brand · `--ink` in light theme · the nav rail |
| Ocean Blue | `#0D3D7A` | Secondary · gradient stop |
| Marine Teal | `#007A99` | Charts & data · the light-theme accent |
| Aqua | `#00B7C3` | Accent & AI · the dark-theme accent · live indicators |
| Foam White | `#E6F7FA` | Recessed background · `--surface-2` in light |
| Pure White | `#FFFFFF` | Main surface |
| Dark | `#09111F` | `--canvas` in dark theme |
| Slate | `#46566D` | `--ink-2` in light theme |
| Border | `#DCE5EC` | `--hairline` in light theme |
| Surface | `#F4F7FA` | `--canvas` in light theme |

### The tokens you actually use

**Light theme**

| Token | OKLCH | Renders | Contrast vs canvas |
|---|---|---|---|
| `--canvas` | `oklch(0.975 0.005 248)` | `#f4f7fa` | — |
| `--surface` | `oklch(1.000 0.000 248)` | `#ffffff` | — |
| `--surface-2` | `oklch(0.964 0.018 209)` | `#e6f7fa` | — |
| `--hairline` | `oklch(0.917 0.014 241)` | `#dce5ec` | — |
| `--hairline-2` | `oklch(0.850 0.020 241)` | `#c3d0da` | — |
| `--ink-3` | `oklch(0.540 0.040 257)` | `#607086` | 4.71 AA |
| `--ink-2` | `oklch(0.449 0.043 257)` | `#46566d` | 6.95 AA |
| `--ink` | `oklch(0.255 0.089 263)` | `#0a1f4d` | 14.85 AA |
| `--accent` | `oklch(0.535 0.100 224)` | `#027998` | 4.67 AA |

**Dark theme**

| Token | OKLCH | Renders | Contrast vs canvas |
|---|---|---|---|
| `--canvas` | `oklch(0.178 0.032 261)` | `#09111f` | — |
| `--surface` | `oklch(0.225 0.036 261)` | `#121c2d` | — |
| `--surface-2` | `oklch(0.270 0.040 261)` | `#1b263a` | — |
| `--hairline` | `oklch(0.330 0.034 259)` | `#2b3647` | — |
| `--hairline-2` | `oklch(0.400 0.036 259)` | `#3c485b` | — |
| `--ink-3` | `oklch(0.620 0.030 250)` | `#798898` | 5.20 AA |
| `--ink-2` | `oklch(0.800 0.024 220)` | `#aec2c8` | 10.18 AA |
| `--ink` | `oklch(0.950 0.014 209)` | `#e4f1f3` | 16.39 AA |
| `--accent` | `oklch(0.710 0.120 203)` | `#08b7c3` | 7.69 AA |

> **Two notes that will bite you.**
> The accent is `#027998`, not the brand's `#007A99` — two steps of 255 in one
> channel. At the exact brand lightness it measured 4.49 on `--surface-2`, one
> hundredth under AA, and this token carries link text.
> **`--ink-3` is for text on `--canvas` and `--surface` only.** On `--surface-2` in
> dark theme it measures 4.17 and axe fails the build. This has already happened
> once, on the masthead's data-source badge.

### The hazard ramp — never restyled, never rebranded

Risk colour is **functional**, not decorative. It is validated for monotonic
lightness (so it reads in greyscale) and for adjacent-band separation under
deuteranopia, protanopia and tritanopia. **Do not make it blue to match the brand.**

| Band | Score | Light | Dark |
|---|---|---|---|
| minimal | 0–20 | `#e2ded0` | `#554d30` |
| low | 21–40 | `#e4c898` | `#7e612c` |
| moderate | 41–60 | `#e2a055` | `#ae7129` |
| high | 61–80 | `#d67229` | `#e17a39` |
| critical | 81–100 | `#b93c27` | `#f98368` |

Every hazard fill carries a **1px stroke at the next band up** — `minimal` on light
canvas measures 1.25 and a fill alone is not a boundary. Use `BAND_CLASS` from
`src/api/types.ts`; never hand-map a band to a colour.

### The gradient

```css
linear-gradient(135deg, #0A1F4D 0%, #0D3D7A 35%, #007A99 65%, #00B7C3 100%)
```

Available as the `brand-gradient` utility and `var(--brand-gradient)`. **Hero
sections, the logo, CTAs, selected segments and visual highlights only.** Never
behind a number, a chart or a map layer — a value read against a moving ground
cannot be compared to the value beside it.

It does **not** invert with the theme. So type on it is a fixed white with a
`token-ok` comment, never `--ink-inverse` (which resolves to navy in dark theme and
would be navy-on-navy).

---

## 3. Type

**Montserrat** 400/600/700, self-hosted from `public/fonts/`, OFL.

**Arabic is IBM Plex Sans Arabic**, and this is not a shortcut: **Montserrat has no
Arabic coverage at any weight.** The brand typeface is Latin-only by construction.
Do not "fix" this by letting Arabic fall back to a system face — shaping and vertical
rhythm would change mid-sentence.

**Numbers are IBM Plex Mono**, via the `num` utility (slashed zero, tabular figures).
Every measurement, coordinate, timestamp and identifier sets in it, because numbers
that get compared must align.

| Style | Size | Weight |
|---|---|---|
| Hero | 64px | 700 |
| H1 | 48px | 700 |
| H2 | 36px | 700 |
| H3 | 28px | 600 |
| H4 | 24px | 600 |
| Body | 16px | 400 |
| Small | 14px | 400 |

In-app the scale is a minor third exposed as `text-2xs … text-xl`. The marketing
pages use the display sizes above.

---

## 4. Space, radius, elevation, motion

**Spacing** — 8-point grid: 4, 8, 12, 16, 24, 32, 48, 64, 96, 128.
Tailwind derives from `--spacing: 4px`, so **`--space-5` (24px) is `p-6`, not `p-5`.**

**Radius** — `--radius-hairline: 2px` (chart and map chrome only) · `sm 8px` ·
`md 12px` · `lg 16px` · `card 20px`.

**Elevation** — three steps, all keyed to Deep Navy:

```
--shadow-sm: 0 4px 12px rgb(10 31 77 / .08)
--shadow-md: 0 10px 30px rgb(10 31 77 / .12)
--shadow-lg: 0 20px 60px rgb(10 31 77 / .18)
```

**Motion** — 200–350ms, `ease-in-out`, "calm water". Three orchestrated moments only:
the time-scrub choreography, the plume bloom, the mode transition. Everything else is
≤150ms, opacity and transform only. `prefers-reduced-motion` is already honoured
globally — do not add an animation that carries meaning on its own.

---

## 5. Component patterns

Use these. Do not re-invent them per page — that is how eleven pages end up looking
like eleven products.

| Component | Where | Contract |
|---|---|---|
| `<Logo>` / `<LogoMark>` | `components/Logo.tsx` | `variant: gradient \| navy \| white`. Never re-draw the mark inline. Min 32px. |
| `<Link>` | `components/Link.tsx` | Renders a real `<a href>`. Intercepts only unmodified left-clicks, so Cmd-click still opens a tab. |
| `<PageShell>` `<Section>` `<Card>` `<CardGrid>` | `shell/PageShell.tsx` | Title + lede + actions; all-caps eyebrow sections; 20px-radius white cards with hairline border and 24px padding. |
| `<Segmented>` | `components/Segmented.tsx` | Recessed track, one raised gradient pill. Used by mode, language and theme. Selection is never colour alone — the pill also raises and goes bold. |
| `<ValueWithUnit>` | `components/ValueWithUnit.tsx` | **The only way a number reaches the screen.** Bidi isolation, tabular figures, provenance as border form, null renders as a gap. |
| `<DashboardChrome>` | `shell/DashboardChrome.tsx` | The navy rail. Fixed `--brand-navy` in both themes, so nothing inside it may use `--ink`. |
| `Loading / Empty / ErrorState / Stale` | `components/States.tsx` | The three states every data surface owes the reader. |

### Buttons

- **Primary** — Deep Navy ground, white label, `--radius-md`
- **Accent** — Aqua ground, hover Marine Teal
- **Secondary** — white ground, navy border
- **Gradient** — the brand gradient, for the single most important action on a page

Inputs are 48px tall, `--radius-md`, `--hairline` border, focus ring `--accent`.
Icons are outline, 2px stroke, rounded caps, minimal geometric — and `currentColor`,
so one icon serves every state.

---

## 6. The honesty patterns — this product's real signature

These are what make the UI *this* product rather than a generic dashboard. They are
not optional polish.

1. **A gap is not a zero.** Null renders as a visible, labelled absence.
2. **Provenance is form, not hue.** Measured is a solid rule; modelled is dashed
   (`stroke-measured` / `stroke-modelled`). Survives greyscale and a photograph of
   a projector.
3. **Caveats travel with the number.** Render `caveats[]` next to the value it
   qualifies, not in a footer nobody scrolls to.
4. **A placeholder is labelled at the point of use.** `sensitivity_weight` is an
   unreviewed `1.0`; every screen showing a score derived from it says so.
5. **A proposal is never confusable with a live value.** The coral-health panel keeps
   the proposed weight and the in-use weight visually separate, with an
   `IN USE` / `NOT IN USE` chip. This is the single most important safeguard in the app.
6. **No false precision.** Reef area affected is a *fraction of the named zone*, never
   a bare km². `hardening.spec.ts` greps for `\d+% chance of impact` and fails on it.
7. **Say which mode is real.** Historical has data; Forecast and Scenario say what
   they do not have.

---

## 7. Layout language

- **Marketing** (`/`, `/login`, `/signup`) — full-bleed gradient hero, generous 96px
  section rhythm, centred max-width 1200px, cards on Foam White.
- **Dashboard** — navy rail (240px on `lg`) + content. The map screen owns its full
  viewport grid; every other page uses `PageShell` at max-width 82rem.
- **Masthead** — two tiers. Identity and session settings on top; the controls that
  change what the map shows underneath. A 2px gradient rule along the top edge as the
  one piece of pure brand.
- **Density** — this is an instrument, not an editorial page. Weight carries hierarchy
  more than size does.

---

## 8. What "wow" means here, and what it does not

**It does mean:** confident type, real generous whitespace, the gradient used once per
screen with intent, motion that settles like water, a map that fills the frame, and
numbers that are beautiful *because* they are legible and aligned.

**It does not mean:** glassmorphism (`--blur-*` is deliberately cleared to `initial`),
neon on navy, drop shadows on inline panels, `rounded-xl` on everything, a green→red
risk ramp, animated counters on numbers that are measurements, or a hero video.

The single most impressive thing this interface can do in front of a judge is show a
real measured number next to a real modelled one and **be visibly honest about which
is which**. Design toward that, not away from it.
