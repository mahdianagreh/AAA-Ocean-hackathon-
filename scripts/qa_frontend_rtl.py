#!/usr/bin/env python3
"""QA: no physical-direction properties in the frontend.

06-bilingual-rtl.md §2 is the rule that prevents the last-three-days rewrite:
never write a physical direction, "not in a component, not in a one-off fix, not
just this once". §8.3 asks for a grep proving it. This is that grep, mechanised.

It is the third of three layers, and it exists because the other two cannot see
everything:
  - stylelint covers hand-written .css, but not JSX class strings
  - oxlint covers TS/TSX correctness, but has NO no-restricted-syntax rule, so it
    cannot match a physical Tailwind class at all
This script sees both, plus template literals and inline style objects.

    python3 scripts/qa_frontend_rtl.py

Exceptions are allowed, counted and printed — never hidden. A line carrying
`rtl-ok: <reason>` is permitted, because some things are genuinely physical and
06 §3 says so explicitly: the map does not mirror, the compass and scale bar do
not mirror, and chart time axes always run left to right. A zero-hit grep would
be a lie about those. MAX_EXCEPTIONS makes adding one a deliberate edit.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FE = ROOT / "frontend"
SCAN_DIRS = [FE / "src"]
SCAN_FILES = [FE / "index.html"]
SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".css", ".html"}

SKIP_PARTS = {"node_modules", "dist", ".vite", "coverage", "test-results",
              "playwright-report", "blob-report"}
SKIP_NAMES = {"tokens.generated.css", "palette.generated.ts"}

# Raising this is a decision, not a formality. Every entry should be a thing
# 06 §3 lists as genuinely not mirroring.
MAX_EXCEPTIONS = 12

CSS_PATTERNS = [
    (r"\bmargin-(?:left|right)\b", "margin-inline-start / -end"),
    (r"\bpadding-(?:left|right)\b", "padding-inline-start / -end"),
    (r"\bborder-(?:left|right)\b", "border-inline-start / -end"),
    (r"(?<![-\w])(?:left|right)\s*:", "inset-inline-start / -end"),
    (r"text-align\s*:\s*(?:left|right)", "text-align: start / end"),
    (r"\bfloat\s*:\s*(?:left|right)", "float has no logical form — use flex/grid"),
]

# Tailwind class forms. Word-boundary anchored so `small-print` does not match
# `ml-`, and `pr` in `pre` does not match `pr-`.
CLASS_PATTERNS = [
    (r"(?<![\w-])m[lr]-[\w.[\]/]+", "ms-* / me-*"),
    (r"(?<![\w-])p[lr]-[\w.[\]/]+", "ps-* / pe-*"),
    (r"(?<![\w-])border-[lr]-[\w.[\]/]+", "border-s-* / border-e-*"),
    # The trailing boundary matters: without it this matched `rounded-lg`, whose
    # `l` is Tailwind's LARGE radius, not `left`. It stayed latent only because
    # nothing in src/ used rounded-lg until Phase 8. Every true positive is still
    # caught — `rounded-l`, `rounded-l-md`, `rounded-r-xl` all match.
    (r"(?<![\w-])rounded-[lr](?:-[\w.[\]/]+)?(?![\w-])", "rounded-s-* / rounded-e-*"),
    (r"(?<![\w-])(?:left|right)-[\w.[\]/]+", "start-* / end-*"),
    (r"(?<![\w-])inset-[lr]-[\w.[\]/]+", "inset-s-* / inset-e-*"),
    (r"(?<![\w-])text-(?:left|right)(?![\w-])", "text-start / text-end"),
    (r"(?<![\w-])float-(?:left|right)(?![\w-])", "flex/grid ordering"),
    (r"(?<![\w-])origin-(?:left|right)(?![\w-])", "origin-inline-start-ish, or rtl-ok"),
]

# Inline style objects in TSX.
JS_PATTERNS = [
    (r"\b(?:marginLeft|marginRight|paddingLeft|paddingRight|borderLeft|borderRight)\b",
     "the logical camelCase form (marginInlineStart, …)"),
    (r"\btextAlign\s*:\s*['\"](?:left|right)['\"]", "textAlign: 'start' / 'end'"),
    # A bare `left:` / `right:` inside a style object was slipping through: the
    # class patterns need a trailing hyphen (`left-1/2`), so `{ left: '50%' }` was
    # invisible to this gate while being exactly the thing it exists to catch.
    (r"(?<![\w-])(?:left|right)\s*:\s*['\"`{]", "insetInlineStart / insetInlineEnd"),
]

fails = []
exceptions = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"  — {detail}"))
    if not ok:
        fails.append(name)


def targets():
    out = []
    for d in SCAN_DIRS:
        if not d.exists():
            continue
        for f in sorted(d.rglob("*")):
            if not f.is_file() or f.suffix not in SUFFIXES:
                continue
            if SKIP_PARTS & set(f.parts) or f.name in SKIP_NAMES:
                continue
            out.append(f)
    out += [f for f in SCAN_FILES if f.exists()]
    return out


if not FE.exists():
    print("\n[0] frontend/")
    print("  NOTE frontend/ does not exist yet — nothing to scan. This becomes a "
          "real gate the moment Phase 0 lands.")
    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED")
    sys.exit(0)

files = targets()
print(f"\n[1] physical-direction scan — {len(files)} files")

hits = []
for f in files:
    rel = f.relative_to(ROOT).as_posix()
    is_style = f.suffix in {".css"}
    lines = f.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # A comment explaining the rule is not a violation of it. This file's own
        # patterns appear in prose all over the codebase.
        if stripped.startswith(("*", "//", "/*", "<!--")):
            continue

        # The marker is honoured on the same line OR the one immediately above.
        # In JSX a style prop routinely sits on its own line with the justification
        # in a comment above it, and forcing the reason onto the same line would
        # mean truncating the reason — which defeats the point of requiring one.
        prev = lines[i - 2] if i >= 2 else ""
        allowed = "rtl-ok:" in line or "rtl-ok:" in prev
        found = []
        for pat, fix in (CSS_PATTERNS if is_style else CLASS_PATTERNS + JS_PATTERNS):
            for m in re.finditer(pat, line):
                found.append((m.group(), fix))
        if not found:
            continue
        for token, fix in found:
            if allowed:
                src = line if "rtl-ok:" in line else prev
                reason = src.split("rtl-ok:")[1].strip().rstrip("*/ ").strip()
                exceptions.append(f"{rel}:{i}  {token!r:<12} {reason}")
            else:
                hits.append(f"{rel}:{i}  {token}  -> use {fix}")

check("zero unexcepted physical-direction properties or classes", not hits,
      f"{len(hits)} found:\n      " + "\n      ".join(hits[:15]))

print(f"\n[2] declared exceptions — {len(exceptions)} of {MAX_EXCEPTIONS} allowed")
for e in exceptions:
    print(f"    {e}")
check(f"exception count within budget ({len(exceptions)} <= {MAX_EXCEPTIONS})",
      len(exceptions) <= MAX_EXCEPTIONS,
      "raise MAX_EXCEPTIONS deliberately, and only for something 06 §3 lists as "
      "genuinely not mirroring")

# ---- lang/dir must be set on <html>, not on a wrapper ------------------------
print("\n[3] direction is applied to the document, not a wrapper")
chrome = FE / "src/app/useDocumentChrome.ts"
if chrome.exists():
    t = chrome.read_text()
    check("lang and dir are set on documentElement",
          "documentElement" in t and "'dir'" in t and "'lang'" in t,
          "06 §1: form controls, scrollbars and text selection read the document "
          "direction, and a wrapper leaves them behind")
else:
    check("useDocumentChrome.ts exists", False, "expected at src/app/useDocumentChrome.ts")

# Radix reads direction from context, never the DOM — verified in
# node_modules/@radix-ui/react-direction: `localDir || useContext(...) || 'ltr'`.
app = FE / "src/App.tsx"
if app.exists():
    check("Radix DirectionProvider wraps the app",
          "DirectionProvider" in app.read_text(),
          "without it, Slider arrow keys, Select/Menu popper alignment and "
          "ScrollArea all compute LTR under <html dir=\"rtl\">")

# ---- measurements must be bidi-isolated -------------------------------------
print("\n[4] values are bidi-isolated")
vwu = FE / "src/components/ValueWithUnit.tsx"
if vwu.exists():
    t = vwu.read_text()
    check("ValueWithUnit isolates via CSS unicode-bidi",
          "unicodeBidi" in t and "isolate" in t,
          "06 §5: without isolation RTL reorders `2.18 g/L` into `g/L 2.18`")
    check("ValueWithUnit renders null as a gap, not a zero",
          "value === null" in t,
          "09 rule 4: missing is never zero")
else:
    check("ValueWithUnit.tsx exists", False,
          "04 calls it the only way a number reaches the screen")

print("\n" + "=" * 60)
if fails:
    print(f"{len(fails)} FAILED")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("ALL CHECKS PASSED")
