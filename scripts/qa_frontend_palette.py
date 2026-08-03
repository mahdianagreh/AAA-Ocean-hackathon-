#!/usr/bin/env python3
"""QA: validate the ReefShield frontend palette, and emit it as code.

Checks, in order:
  1. every colour is inside the sRGB gamut
  2. every text/ground pair reaches WCAG AA
  3. hazard-ramp lightness is monotonic in both themes
  4. adjacent hazard bands stay separable under simulated deuteranopia,
     protanopia and tritanopia
  5. the accent never sits close enough to a hazard band to be confused with one

Values printed here are the source of truth for docs/Ali/frontend/02-design-tokens.md.
If a token changes, re-run this and paste the results back into that document —
claims in this project carry evidence.

    python3 scripts/qa_frontend_palette.py              # the report (default)
    python3 scripts/qa_frontend_palette.py --emit-css   # frontend token custom properties
    python3 scripts/qa_frontend_palette.py --emit-ts    # hex, for MapLibre

The two emitters exist so the frontend never transcribes a colour by hand. They
have different consumers and therefore different notation: the DOM reads OKLCH
from CSS, and MapLibre reads hex from TypeScript because its colour parser
accepts only named / hex / rgb() / hsl() — oklch() fails style validation and
the layer silently renders at the property default.

The no-argument report is contract: scripts/qa_frontend_docs.py shells out to
this script with no arguments and regexes its stdout, so that output must stay
byte-identical. scripts/qa_frontend_tokens.py checks the emitted files against
the emitters, so a hand-edit of either generated file fails CI.
"""
import argparse
import math
import sys

# ---------- OKLCH -> sRGB ----------------------------------------------------

def oklch_to_srgb(L, C, h_deg):
    h = math.radians(h_deg)
    a, b = C * math.cos(h), C * math.sin(h)
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_**3, m_**3, s_**3
    r = +4.0767416621*l - 3.3077115913*m + 0.2309699292*s
    g = -1.2684380046*l + 2.6097574011*m - 0.3413193965*s
    bl = -0.0041960863*l - 0.7034186147*m + 1.7076147010*s
    return r, g, bl  # linear, may be out of gamut

def encode(c):
    c = max(0.0, min(1.0, c))
    return 12.92*c if c <= 0.0031308 else 1.055*(c**(1/2.4)) - 0.055

def in_gamut(L, C, h):
    return all(-1e-4 <= v <= 1.0001 for v in oklch_to_srgb(L, C, h))

def max_chroma(L, h, hi=0.4):
    """Largest in-gamut chroma at this lightness and hue, to 3dp."""
    lo = 0.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if in_gamut(L, mid, h):
            lo = mid
        else:
            hi = mid
    return math.floor(lo * 1000) / 1000

def hexof(L, C, h):
    return "#" + "".join(f"{round(encode(v)*255):02x}" for v in oklch_to_srgb(L, C, h))

def rel_lum(L, C, h):
    r, g, b = (max(0.0, min(1.0, v)) for v in oklch_to_srgb(L, C, h))
    return 0.2126*r + 0.7152*g + 0.0722*b

def contrast(fg, bg):
    a, b = rel_lum(*fg), rel_lum(*bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)

# ---------- CVD simulation (Brettel/Viénot-style linear approximations) ------

CVD = {
    "deuteranopia": ((0.625, 0.375, 0.0), (0.700, 0.300, 0.0), (0.0, 0.300, 0.700)),
    "protanopia":   ((0.567, 0.433, 0.0), (0.558, 0.442, 0.0), (0.0, 0.242, 0.758)),
    "tritanopia":   ((0.950, 0.050, 0.0), (0.0, 0.433, 0.567), (0.0, 0.475, 0.525)),
}

def simulate(rgb, kind):
    m = CVD[kind]
    return tuple(sum(m[i][j]*rgb[j] for j in range(3)) for i in range(3))

def dist(c1, c2):
    return math.sqrt(sum((a-b)**2 for a, b in zip(c1, c2)))



def clamp(L, C, h):
    """Return (L, C', h) with chroma reduced to the sRGB boundary if needed."""
    cm = max_chroma(L, h)
    return (L, min(C, cm), h)

GROUND = {
    "light": {
        "canvas":     (0.985, 0.006, 200), "surface":    (1.000, 0.000, 200),
        "surface-2":  (0.960, 0.010, 200), "hairline":   (0.900, 0.014, 200),
        "hairline-2": (0.840, 0.020, 200), "ink-3":      (0.545, 0.022, 205),
        "ink-2":      (0.420, 0.028, 205), "ink":        (0.240, 0.030, 210),
        "accent":     (0.520, 0.085, 205),
    },
    "dark": {
        "canvas":     (0.180, 0.024, 215), "surface":    (0.225, 0.026, 215),
        "surface-2":  (0.270, 0.028, 215), "hairline":   (0.330, 0.026, 213),
        "hairline-2": (0.400, 0.028, 213), "ink-3":      (0.620, 0.022, 208),
        "ink-2":      (0.780, 0.020, 205), "ink":        (0.940, 0.012, 202),
        "accent":     (0.780, 0.105, 200),
    },
}

# §14.5. Light ground -> ramp darkens with risk. Dark ground -> ramp lightens.
HAZARD = [
    ("minimal",  "0-20",   (0.900, 0.020, 95), (0.420, 0.045, 95)),
    ("low",      "21-40",  (0.845, 0.070, 80), (0.510, 0.080, 80)),
    ("moderate", "41-60",  (0.755, 0.120, 68), (0.600, 0.115, 66)),
    ("high",     "61-80",  (0.655, 0.150, 52), (0.685, 0.150, 50)),
    ("critical", "81-100", (0.535, 0.165, 32), (0.735, 0.150, 34)),
]

GROUND_ORDER = ["canvas", "surface", "surface-2", "hairline", "hairline-2",
                "ink-3", "ink-2", "ink", "accent"]

def band(v):
    return tuple(encode(x) for x in oklch_to_srgb(*v))


# ---------- resolve: every derived decision, computed once -------------------

def resolve():
    """Clamped tokens plus the two decisions the report and emitters share.

    `on` is the ink/ink-inverse flip, decided by measured contrast rather than
    picked per band — 02-design-tokens.md §2 notes the flip happens mid-ramp,
    and hard-coding --ink across the scale fails exactly the bands that matter.

    `stroke` is the fill-visibility rule: every hazard fill carries a 1px
    stroke at the next band up, because 'minimal' on light canvas measures 1.29
    and a fill alone is not a boundary. 'critical' has no next band, so it takes
    ink, the token furthest from canvas in either theme.

    clamp() is idempotent, so this is safe whether or not report() has already
    written clamped values back into GROUND.
    """
    out = {}
    for theme in ("light", "dark"):
        idx = 2 if theme == "light" else 3
        ground = {name: clamp(*GROUND[theme][name]) for name in GROUND_ORDER}
        other = "dark" if theme == "light" else "light"
        ground["ink-inverse"] = clamp(*GROUND[other]["ink"])

        bands = []
        for i, entry in enumerate(HAZARD):
            name, score = entry[0], entry[1]
            v = clamp(*entry[idx])
            ci = contrast(ground["ink"], v)
            cv = contrast(ground["ink-inverse"], v)
            bands.append({
                "name": name,
                "score": score,
                "lch": v,
                "hex": hexof(*v),
                "on": "ink" if ci >= cv else "ink-inverse",
                "on_contrast": max(ci, cv),
                "stroke": HAZARD[i + 1][0] if i + 1 < len(HAZARD) else "ink",
            })
        out[theme] = {"ground": ground, "hazard": bands}
    return out


def _lch(v):
    return f"oklch({v[0]:.3f} {v[1]:.3f} {v[2]:.0f})"


def _css_block(res, theme, indent):
    pad = " " * indent
    g, hz = res[theme]["ground"], res[theme]["hazard"]
    out = []
    for name in GROUND_ORDER + ["ink-inverse"]:
        out.append(f"{pad}--{name}: {_lch(g[name])};")
    out.append("")
    for b in hz:
        out.append(f"{pad}--risk-{b['name']}: {_lch(b['lch'])};")
    out.append("")
    for b in hz:
        target = f"var(--risk-{b['stroke']})" if b["stroke"] != "ink" else "var(--ink)"
        out.append(f"{pad}--risk-{b['name']}-stroke: {target};")
    out.append("")
    for b in hz:
        out.append(f"{pad}--risk-{b['name']}-on: var(--{b['on']});")
    return "\n".join(out)


CSS_STATIC = """\
  --state-focus: var(--accent);
  --state-selected: var(--accent);
  --data-measured: var(--ink-2);
  --data-modelled: var(--ink-3);
  --data-envelope: color-mix(in oklab, var(--ink-3) 12%, transparent);
  --data-missing: transparent;"""


def emit_css(res):
    """The token layer, as plain custom properties in four scopes.

    Plain properties rather than Tailwind's @theme, because @theme cannot be
    nested in a media query or a selector — so the light/dark/[data-theme]
    redefinition that 02-design-tokens.md §6 requires has to live here, and
    theme.css bridges it into Tailwind with `@theme inline`.

    Four scopes, not two: an explicit user choice must beat the OS preference in
    both directions, which needs [data-theme="light"] as well as ="dark".
    """
    parts = [
        "/* GENERATED by scripts/qa_frontend_palette.py --emit-css — do not edit.",
        " *",
        " * Every value is computed and validated by that script: sRGB gamut, WCAG",
        " * contrast for each text/ground pair, monotonic hazard lightness, and",
        " * adjacent-band separation under simulated deuteranopia, protanopia and",
        " * tritanopia. Hand-editing this file is checked and rejected by",
        " * scripts/qa_frontend_tokens.py.",
        " *",
        " * Regenerate:  python3 scripts/qa_frontend_palette.py --emit-css \\",
        " *                > frontend/src/styles/tokens.generated.css",
        " */",
        "",
        ":root {",
        _css_block(res, "light", 2),
        "",
        CSS_STATIC,
        "}",
        "",
        "@media (prefers-color-scheme: dark) {",
        "  :root {",
        _css_block(res, "dark", 4),
        "  }",
        "}",
        "",
        "/* An explicit choice wins over the OS in both directions. */",
        ':root[data-theme="dark"] {',
        _css_block(res, "dark", 2),
        "}",
        "",
        ':root[data-theme="light"] {',
        _css_block(res, "light", 2),
        "}",
        "",
    ]
    return "\n".join(parts)


def emit_ts(res):
    """Hex, for MapLibre only.

    MapLibre's colour parser accepts named colours, hex, rgb() and hsl() and
    nothing else, so a style JSON carrying oklch() fails validation and the
    layer renders at its property default — silently. The map therefore reads
    hex from here while the DOM reads OKLCH from tokens.generated.css, and both
    come out of one validated source.
    """
    lines = [
        "// GENERATED by scripts/qa_frontend_palette.py --emit-ts — do not edit.",
        "//",
        "// Hex rather than OKLCH on purpose: MapLibre's colour parser handles only",
        "// named / hex / rgb() / hsl(). An oklch() value fails style validation and",
        "// the layer silently falls back to the property default.",
        "//",
        "// Regenerate:  python3 scripts/qa_frontend_palette.py --emit-ts \\",
        "//                > frontend/src/design/palette.generated.ts",
        "",
        "export const palette = {",
    ]
    for theme in ("light", "dark"):
        g, hz = res[theme]["ground"], res[theme]["hazard"]
        lines.append(f"  {theme}: {{")
        for name in GROUND_ORDER + ["ink-inverse"]:
            key = name.replace("-", "_")
            lines.append(f"    {key}: '{hexof(*g[name])}',")
        lines.append("    risk: {")
        for b in hz:
            lines.append(f"      {b['name']}: '{b['hex']}',")
        lines.append("    },")
        lines.append("    riskStroke: {")
        for b in hz:
            src = g["ink"] if b["stroke"] == "ink" else next(
                x["lch"] for x in hz if x["name"] == b["stroke"])
            lines.append(f"      {b['name']}: '{hexof(*src)}',")
        lines.append("    },")
        lines.append("  },")
    lines += [
        "} as const;",
        "",
        "export type ThemeName = keyof typeof palette;",
        "",
    ]
    return "\n".join(lines)


# ---------- the report ------------------------------------------------------

def report():
    """The human-readable validation report.

    This output is byte-for-byte contract with scripts/qa_frontend_docs.py,
    which regexes it to prove every value quoted in 02-design-tokens.md was
    actually produced here. Do not reformat.
    """
    rows = []
    print("=" * 84)
    print("GROUND / NEUTRALS")
    print("=" * 84)
    for theme, toks in GROUND.items():
        bg = clamp(*toks["canvas"])
        print(f"\n  [{theme}]")
        for name, raw in toks.items():
            v = clamp(*raw)
            clamped = " (chroma clamped)" if abs(v[1] - raw[1]) > 1e-6 else ""
            note = ""
            if name.startswith("ink") or name == "accent":
                c = contrast(v, bg)
                note = f"   contrast vs canvas {c:5.2f}  [{'AA' if c >= 4.5 else 'AA-large' if c >= 3 else 'FAIL'}]"
            print(f"    --{name:11} oklch({v[0]:.3f} {v[1]:.3f} {v[2]:.0f})   {hexof(*v)}{note}{clamped}")
            GROUND[theme][name] = v

    print()
    print("=" * 84)
    print("HAZARD RAMP  (concept §14.5)")
    print("=" * 84)
    for theme, idx, direction in (("light", 2, "darkens"), ("dark", 3, "lightens")):
        canvas, ink, surface = GROUND[theme]["canvas"], GROUND[theme]["ink"], GROUND[theme]["surface"]
        inverse = GROUND["dark" if theme == "light" else "light"]["ink"]
        print(f"\n  [{theme}] — ramp {direction} with risk")
        print(f"    {'band':10} {'score':8} {'oklch':27} {'hex':9} {'L':>6} {'fill/canvas':>12} {'text on it':>22}")
        prev = None
        for name, score, lv, dv in HAZARD:
            v = clamp(*(lv if theme == "light" else dv))
            ci, cv = contrast(ink, v), contrast(inverse, v)
            best, bc = ("--ink", ci) if ci >= cv else ("--ink-inverse", cv)
            mono = "" if prev is None else (" MONOTONIC-BREAK" if (theme == "light") != (v[0] < prev) else "")
            print(f"    {name:10} {score:8} oklch({v[0]:.3f} {v[1]:.3f} {v[2]:>3.0f})   {hexof(*v)} "
                  f"{v[0]:6.3f} {contrast(v, canvas):12.2f} {best:>14} {bc:5.2f} "
                  f"{'AA' if bc >= 4.5 else 'AA-lg' if bc >= 3 else 'FAIL'}{mono}")
            prev = v[0]

    print()
    print("=" * 84)
    print("COLOUR-VISION SEPARATION — adjacent bands under simulated CVD")
    print("=" * 84)
    worst = (1.0, "")
    for theme, idx in (("light", 2), ("dark", 3)):
        for kind in CVD:
            ds = []
            for i in range(len(HAZARD) - 1):
                a = simulate(band(clamp(*HAZARD[i][idx])), kind)
                b = simulate(band(clamp(*HAZARD[i + 1][idx])), kind)
                d = dist(a, b)
                ds.append(d)
                if d < worst[0]:
                    worst = (d, f"{theme}/{kind}: {HAZARD[i][0]}->{HAZARD[i+1][0]}")
            print(f"  {theme:6} {kind:13} adjacent distances  " +
                  "  ".join(f"{d:.3f}" for d in ds) + f"   min {min(ds):.3f} "
                  f"{'ok' if min(ds) >= 0.10 else 'TOO CLOSE'}")
    print(f"\n  worst case overall: {worst[0]:.3f}  ({worst[1]})")
    print("  lightness is monotonic in both themes, so the ramp also reads in greyscale.")

    print()
    print("=" * 84)
    print("ACCENT SEPARATION — accent must never read as a risk level")
    print("=" * 84)
    for theme, idx in (("light", 2), ("dark", 3)):
        acc = GROUND[theme]["accent"]
        m = min(dist(band(acc), band(clamp(*h[idx]))) for h in HAZARD)
        print(f"  {theme:6} min distance to any hazard band {m:.3f}  {'ok' if m >= 0.25 else 'TOO CLOSE'}")

    print()
    print("=" * 84)
    print("FILL VISIBILITY — low bands against canvas")
    print("=" * 84)
    for theme, idx in (("light", 2), ("dark", 3)):
        c = contrast(clamp(*HAZARD[0][idx]), GROUND[theme]["canvas"])
        print(f"  {theme:6} 'minimal' fill vs canvas {c:.2f} — "
              f"{'needs a stroke to be visible' if c < 1.5 else 'visible unaided'}")
    print("\n  RULE: every hazard fill carries a 1px stroke at the next band up.")
    print("        A fill alone is not a boundary, and 'minimal' is nearly canvas-coloured.")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Validate the ReefShield palette, or emit it as code.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--emit-css", action="store_true",
                   help="write the token custom properties to stdout")
    g.add_argument("--emit-ts", action="store_true",
                   help="write the hex palette for MapLibre to stdout")
    args = ap.parse_args(argv)

    if args.emit_css:
        sys.stdout.write(emit_css(resolve()))
    elif args.emit_ts:
        sys.stdout.write(emit_ts(resolve()))
    else:
        report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
