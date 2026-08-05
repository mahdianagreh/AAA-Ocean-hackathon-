#!/usr/bin/env python3
"""QA: the frontend's generated token files must still match their generator.

frontend/src/styles/tokens.generated.css and frontend/src/design/palette.generated.ts
are emitted by qa_frontend_palette.py. Nothing stops someone opening one and
"just fixing" a colour, and nothing about the result would look wrong — the app
would compile, the theme would render, and the value would no longer be one the
validator ever blessed for gamut, contrast or colour-vision separation.

This closes that. Checks, in order:
  1. both generated files exist
  2. both are byte-identical to what the generator emits right now
  3. the CSS carries all four theme scopes, not just light and dark
  4. every expected token name is present in every scope
  5. the CSS is OKLCH-native (zero hex) and the TS is hex-only (zero oklch)
  6. no component references a raw hazard value instead of a semantic alias

Passes with a note before frontend/ exists, so it can join the QA set on day one.

    python3 scripts/qa_frontend_tokens.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "frontend/src/styles/tokens.generated.css"
TS = ROOT / "frontend/src/design/palette.generated.ts"
SRC = ROOT / "frontend/src"

GROUND = ["canvas", "surface", "surface-2", "hairline", "hairline-2",
          "ink-3", "ink-2", "ink", "accent", "ink-inverse"]
BANDS = ["minimal", "low", "moderate", "high", "critical"]

fails = []


def check(name, ok, detail=""):
    # only show detail on failure, so a PASS line never reads like a problem
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"  — {detail}"))
    if not ok:
        fails.append(name)


def emit(flag):
    r = subprocess.run(["python3", "scripts/qa_frontend_palette.py", flag],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  FAIL generator exited {r.returncode} for {flag}\n{r.stderr}")
        sys.exit(1)
    return r.stdout


# ---- 0. nothing to check yet is not a failure --------------------------------
if not SRC.exists():
    print("\n[0] frontend/")
    print("  NOTE frontend/src does not exist yet — nothing to check. "
          "This becomes a real gate the moment Phase 0 lands.")
    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED")
    sys.exit(0)

# ---- 1 & 2. the generated files are exactly what the generator emits ---------
print("\n[1] generated files exist and match scripts/qa_frontend_palette.py")
for path, flag, label in ((CSS, "--emit-css", "tokens.generated.css"),
                          (TS, "--emit-ts", "palette.generated.ts")):
    if not path.exists():
        check(f"{label} exists", False, f"missing: {path.relative_to(ROOT)}")
        continue
    check(f"{label} exists", True)
    want, got = emit(flag), path.read_text()
    if want == got:
        check(f"{label} is byte-identical to {flag} output", True)
    else:
        wl, gl = want.splitlines(), got.splitlines()
        first = next((i for i, (a, b) in enumerate(zip(wl, gl)) if a != b), min(len(wl), len(gl)))
        check(f"{label} is byte-identical to {flag} output", False,
              f"first difference at line {first + 1}. "
              f"Regenerate: python3 scripts/qa_frontend_palette.py {flag} "
              f"> {path.relative_to(ROOT)}")

if not CSS.exists() or not TS.exists():
    print("\n" + "=" * 60)
    print(f"{len(fails)} FAILED")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)

css, ts = CSS.read_text(), TS.read_text()

# ---- 3. four scopes, because an explicit choice must beat the OS both ways ---
print("\n[2] theme scopes")
scopes = {
    ":root": r"^:root \{",
    "@media (prefers-color-scheme: dark)": r"^@media \(prefers-color-scheme: dark\) \{",
    ':root[data-theme="dark"]': r'^:root\[data-theme="dark"\] \{',
    ':root[data-theme="light"]': r'^:root\[data-theme="light"\] \{',
}
for label, pat in scopes.items():
    check(f"scope {label} present", bool(re.search(pat, css, re.M)))

# ---- 4. every token in every scope — a deletion is as bad as a wrong value ---
print("\n[3] token coverage per scope")
blocks = re.split(r"^(?=:root|@media)", css, flags=re.M)[1:]
expected = ([f"--{n}" for n in GROUND]
            + [f"--risk-{b}" for b in BANDS]
            + [f"--risk-{b}-stroke" for b in BANDS]
            + [f"--risk-{b}-on" for b in BANDS])
for blk in blocks:
    label = blk.split("{", 1)[0].strip()
    declared = set(re.findall(r"(--[a-z0-9-]+):", blk))
    missing = [t for t in expected if t not in declared]
    check(f"{label} declares all {len(expected)} theme tokens", not missing,
          f"missing: {missing}")

# the aliases live once on :root and inherit; they are not theme-dependent
print("\n[4] semantic aliases")
for alias in ["--state-focus", "--state-selected", "--data-measured",
              "--data-modelled", "--data-envelope", "--data-missing"]:
    check(f"{alias} declared", f"{alias}:" in css)

# ---- 5. notation stays where it belongs -------------------------------------
print("\n[5] notation")
css_hex = re.findall(r"#[0-9a-fA-F]{3,8}\b", css)
check("tokens.generated.css is OKLCH-native (no hex)", not css_hex,
      f"found {len(css_hex)}: {css_hex[:5]}")
# the header comment explains *why* oklch is absent, so scan code only
ts_code = "\n".join(l for l in ts.splitlines() if not l.lstrip().startswith("//"))
ts_oklch = re.findall(r"oklch\(", ts_code)
check("palette.generated.ts is hex-only (no oklch)", not ts_oklch,
      f"found {len(ts_oklch)} oklch() values — MapLibre cannot parse them")
check("palette.generated.ts carries both themes",
      "light: {" in ts and "dark: {" in ts)

# ---- 6. components must go through the aliases, never the raw ramp -----------
# 02-design-tokens.md §3: "Components reference these, never the raw scale."
# A hex literal outside the two generated files and the map style is the tell.
print("\n[6] components use tokens, not literals")
ALLOWED = {"design/palette.generated.ts", "styles/tokens.generated.css", "map/style.ts"}
offenders = []
for f in sorted(SRC.rglob("*")):
    if not f.is_file() or f.suffix not in {".ts", ".tsx", ".css"}:
        continue
    rel = f.relative_to(SRC).as_posix()
    if rel in ALLOWED:
        continue
    for i, line in enumerate(f.read_text().splitlines(), 1):
        if "token-ok:" in line:
            continue
        # A hex inside a comment is documentation, not a hardcoded colour — and the
        # comments that matter most cite the exact value they are warning about
        # ("#d67229 as ink on --surface measures 3.33"). Flagging those would push
        # people to delete the reason rather than the violation.
        stripped = line.strip()
        if stripped.startswith(("*", "//", "/*", "<!--")):
            continue
        for m in re.finditer(r"#[0-9a-fA-F]{3,8}\b", line):
            if re.match(r"^#[0-9a-fA-F]{3,8}$", m.group()):
                offenders.append(f"{rel}:{i} {m.group()}")
check("no hex literals outside the generated files and the map style",
      not offenders, f"{len(offenders)}: {offenders[:6]}")

print("\n" + "=" * 60)
if fails:
    print(f"{len(fails)} FAILED")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("ALL CHECKS PASSED")
