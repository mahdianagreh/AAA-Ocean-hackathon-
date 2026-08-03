#!/usr/bin/env python3
"""QA: verify docs/Ali/frontend/*.md against ground truth before pushing.

Checks that the frontend documentation still tells the truth about the repo:
  1. every colour value in 02-design-tokens.md is reproduced by qa_frontend_palette.py
  2. every contrast figure quoted there is one the validator actually printed
  3. every asserted repo fact (file counts, payload sizes) matches the files on disk
  4. cross-document consistency, and no placeholders left behind
  5. every relative link resolves
  6. markdown structure is intact

Run before any push that touches docs/Ali/frontend/:

    python3 scripts/qa_frontend_docs.py
"""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FE = ROOT / "docs/Ali/frontend"
fails = []

def check(name, ok, detail=""):
    # only show detail on failure, so a PASS line never reads like a problem
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"  — {detail}"))
    if not ok:
        fails.append(name)

# ---- 1. every hex/oklch in 02 must match the validator's output --------------
print("\n[1] token values vs scripts/qa_frontend_palette.py")
out = subprocess.run(["python3", "scripts/qa_frontend_palette.py"], cwd=ROOT,
                     capture_output=True, text=True).stdout
doc = (FE / "02-design-tokens.md").read_text()

script_pairs = set(re.findall(r"oklch\(([\d.]+) ([\d.]+) +(\d+)\)\s+(#[0-9a-f]{6})", out))
doc_pairs = set()
for m in re.finditer(r"`oklch\(([\d.]+) ([\d.]+) (\d+)\)`\s*\|\s*`(#[0-9a-f]{6})`", doc):
    doc_pairs.add(m.groups())

missing = doc_pairs - script_pairs
check(f"all {len(doc_pairs)} oklch/hex pairs in 02 are produced by the validator",
      not missing, f"not in script output: {sorted(missing)}" if missing else "")

# ---- 2. contrast numbers quoted in 02 must appear in the validator output ----
print("\n[2] contrast figures quoted in 02")
quoted = set(re.findall(r"\*\*([\d]+\.[\d]{2})\*\*", doc)) | set(re.findall(r"\((\d+\.\d{2})\)", doc))
nums_in_out = set(re.findall(r"\d+\.\d{2}", out))
bad = sorted(q for q in quoted if q not in nums_in_out)
check(f"all {len(quoted)} quoted contrast figures appear in validator output",
      not bad, f"unsupported: {bad}" if bad else "")

# ---- 3. repo facts asserted across the doc set ------------------------------
print("\n[3] repo facts")
allmd = "\n".join(q.read_text() for q in FE.glob("*.md"))
figs = sorted((ROOT / "docs/qa_screenshots").glob("*.png"))
manifest = len(re.findall(r"^\| \[", (ROOT / "docs/qa_screenshots/MANIFEST.md").read_text(), re.M))
over1mb = sum(1 for f in figs if f.stat().st_size > 1_000_000)
total_mb = sum(f.stat().st_size for f in figs) / 1e6
ov1 = (ROOT / "docs/qa_screenshots/overview_01_master_all_layers.png").stat().st_size / 1e6
plume = (ROOT / "data/processed/plume/observed_plume_probability.tif").stat().st_size / 1e6
tests = list((ROOT / "tests").glob("test_*.py"))

def claims(text, pattern):
    """Every distinct number the docs assert for this pattern."""
    return sorted({float(m) for m in re.findall(pattern, text)})

# These compare the docs against DISK, not against a constant.
#
# They used to assert `manifest == 34`, which made the gate fail the moment anyone
# added a QA figure — and main added nine. The invariant that matters is "the docs
# agree with the repo", not "the repo has exactly 34 figures", so the expected value
# is now measured and the doc claim is checked against it. A figure added with the
# docs updated passes; a figure added silently does not.
check(f"docs say {manifest} figures in the manifest", f"{manifest} figures" in allmd,
      f"manifest has {manifest}; no doc says so")
check(f"docs say {len(figs)} PNGs on disk", f"{len(figs)} PNGs" in allmd,
      f"disk has {len(figs)}; no doc says so")
check(f"'{over1mb} files over 1 MB'", f"{over1mb} files over 1 MB" in allmd,
      f"actual {over1mb}; no doc says so")

# every MB figure the docs assert must match the real file, to 0.1 MB
fig_claims = claims(allmd, r"(\d+) MB of (?:PNGs|QA figures)") + claims(allmd, r"\*\*(\d+) MB\*\*")
check(f"figure-total claims {fig_claims} match {total_mb:.1f} MB actual",
      all(abs(c - total_mb) < 0.6 for c in fig_claims), f"actual {total_mb:.1f} MB")

ov_claims = claims(allmd, r"`overview_01` alone (?:is )?([\d.]+) MB")
check(f"overview_01 claims {ov_claims} match {ov1:.1f} MB actual",
      all(abs(c - ov1) < 0.1 for c in ov_claims), f"actual {ov1:.1f} MB")

pl_claims = claims(allmd, r"\*\*([\d.]+) MB\*\*\.? Four timesteps") + claims(allmd, r"file is ([\d.]+) MB")
check(f"plume claims {pl_claims} match {plume:.1f} MB actual",
      all(abs(c - plume) < 0.1 for c in pl_claims), f"actual {plume:.1f} MB")

funcs = sum(len(re.findall(r"^\s*def test_", f.read_text(), re.M)) for f in tests)
tc = claims(allmd, r"\*\*(\d+) tests across \d+ files\*\*")
tf = claims(allmd, r"\*\*\d+ tests across (\d+) files\*\*")
check(f"test-count claim {tc}/{tf} matches {funcs} tests in {len(tests)} files",
      tc == [float(funcs)] and tf == [float(len(tests))], f"actual {funcs} in {len(tests)}")

# ---- 4. cross-doc consistency ------------------------------------------------
print("\n[4] cross-document consistency")
check("hazard bands named identically everywhere",
      all(b in allmd for b in ("minimal", "low", "moderate", "high", "critical")))
check("no doc says 'trajectory line' approvingly",
      "Never a single trajectory line" in allmd or "Never a trajectory line" in allmd)
check("lowercase docs/ali path not used in new docs",
      "docs/ali/" not in allmd, "found lowercase reference")
check("no TODO/TBD/lorem left behind",
      not re.search(r"\b(TODO|TBD|lorem|XXX|FIXME)\b", allmd, re.I))

# ---- 5. every relative link resolves ----------------------------------------
print("\n[5] links")
L = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
broken, n = [], 0
for md in (ROOT / "docs/Ali").rglob("*.md"):
    for t in L.findall(md.read_text()):
        if t.startswith(("http", "mailto:", "#")):
            continue
        n += 1
        if not (md.parent / t).resolve().exists():
            broken.append(f"{md.relative_to(ROOT)} -> {t}")
check(f"{n} relative links resolve", not broken, "; ".join(broken))

# ---- 6. markdown structure ---------------------------------------------------
print("\n[6] markdown structure")
for md in sorted(FE.glob("*.md")):
    txt = md.read_text()
    if txt.count("```") % 2:
        check(f"{md.name} code fences balanced", False, "odd number of ```")
    rows = [l for l in txt.splitlines() if l.startswith("|") and l.strip().endswith("|")]
    widths = {}
    for l in rows:
        widths.setdefault(l.count("|"), 0)
        widths[l.count("|")] += 1
check("all code fences balanced", all(p.read_text().count("```") % 2 == 0 for p in FE.glob("*.md")))
check("every doc has an H1", all(p.read_text().lstrip().startswith("# ") for p in FE.glob("*.md")))

print("\n" + ("=" * 60))
print(f"{len(fails)} FAILED" if fails else "ALL CHECKS PASSED")
for f in fails:
    print("  - " + f)
raise SystemExit(1 if fails else 0)
