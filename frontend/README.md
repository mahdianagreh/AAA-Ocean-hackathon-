# ReefShield frontend

The map is the product. One screen, three modes, built toward the eight-scene
storyboard. Design documents live in [`../docs/Ali/frontend/`](../docs/Ali/frontend/) —
`00-master-plan.md` is the phase plan, and five of them are locked before code. The token
and component contract for this directory is [`DESIGN.md`](DESIGN.md).

## Run it

```bash
npm install
npm run dev            # http://localhost:5173
```

The API is separate, and optional in Phase 0:

```bash
cd .. && docker compose up --build    # api on :8000, worker
```

## Checks

```bash
npm run qa             # typecheck + lint + unit tests
npm run test:e2e       # Playwright, including the phase gates
npm run build
```

Four repo-level gates run from the project root, and every phase re-runs all of them:

```bash
python3 ../scripts/qa_frontend_palette.py   # the colour source of truth
python3 ../scripts/qa_frontend_docs.py      # docs still match the repo
python3 ../scripts/qa_frontend_tokens.py    # generated files match the generator
python3 ../scripts/qa_frontend_rtl.py       # no physical-direction properties
```

## Two files are generated, not written

`src/styles/tokens.generated.css` and `src/design/palette.generated.ts` come from
`scripts/qa_frontend_palette.py`, which validates sRGB gamut, WCAG contrast, monotonic
hazard lightness and colour-vision separation before emitting anything. Editing either
file directly fails `qa_frontend_tokens.py`. Change the generator instead:

```bash
python3 ../scripts/qa_frontend_palette.py --emit-css > src/styles/tokens.generated.css
python3 ../scripts/qa_frontend_palette.py --emit-ts  > src/design/palette.generated.ts
```

They differ in notation on purpose. The DOM reads OKLCH from the CSS; MapLibre reads hex
from the TypeScript, because its colour parser accepts only named, hex, `rgb()` and
`hsl()` — an `oklch()` value fails style validation and the layer silently renders at the
property default.

## `/specimen`

Four iframes: light and dark against left-to-right and right-to-left, each a real
document with its own `<html lang dir data-theme>`. Radix primitives portal to
`document.body`, so a nested direction wrapper would render popovers in the document's
direction and hide the most important RTL bug. Every component lands here the day it is
written; a primitive that is not on it has not been checked.

Add one with `registerSpecimen()` in `src/specimen/registry.ts` — one call puts it on all
four panes.

## Nothing is fetched at runtime

DoD item 9 is "works with wifi off". The fonts, and later the basemap and the MapLibre RTL
text plugin, are committed under `public/` and served same-origin. A CDN reference
anywhere is a bug, and `tests/phase0-language-lock.spec.ts` asserts zero external
requests.

## Conventions worth knowing before the first edit

- **Numbers only reach the screen through `ValueWithUnit`.** It applies bidi isolation,
  slashed-zero tabular figures and the provenance form in one place. Pass `null` for
  missing data — never `0`, which asserts a measurement.
- **No physical directions.** `ms-*`/`me-*`, not `ml-*`/`mr-*`; `text-start`, not
  `text-left`. Genuinely physical cases exist (the compass, a chart's time axis) and are
  declared with an `rtl-ok: <reason>` comment, which the gate counts and prints.
- **Never interpolate a Tailwind class.** `bg-risk-${band}` is not a string in the source,
  so Tailwind never generates it and the fill silently falls back. Use a literal lookup.
- `bg-red-500` and `rounded-xl` do not compile. Those namespaces are cleared on purpose.

## Two Docker gotchas

- `- /app/node_modules` in compose is an **anonymous volume**, populated once from the
  image. After changing `package.json` you must
  `docker compose --profile frontend down -v`, or the container keeps stale modules with no
  error.
- Playwright running *inside* the compose network needs `http://api:8000`, not
  `http://localhost:8000`. `VITE_API_URL` is resolved by the browser on the host, which is
  why the compose value is correctly `localhost`.
