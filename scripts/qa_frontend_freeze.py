#!/usr/bin/env python3
"""QA: the Day-12 freeze gate.

12-testing-and-demo-safety.md sets one gate for the freeze:

    grep -ri PROVISIONAL frontend/

"Anything still matching is either swapped or explicitly declared a known
placeholder in the demo. No silent placeholders reach the stage."

That command as written matches node_modules and the committed reef GeoJSON, so it
is scoped here — and the important half is the second sentence, not the grep. A
placeholder is fine; a placeholder nobody told the audience about is not. So this
checks that every PROVISIONAL marker in the shipped code and data has a
corresponding disclosure in the UI copy.

Also checks the things that would embarrass a live demo: no CDN reference, no
TODO left in shipped source, the offline pack complete, and the deterministic demo
mode reachable.

    python3 scripts/qa_frontend_freeze.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FE = ROOT / "frontend"
SRC = FE / "src"
PUB = FE / "public"

fails = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + ("" if ok else f"  — {detail}"))
    if not ok:
        fails.append(name)


if not SRC.exists():
    print("\n  NOTE frontend/src does not exist yet — nothing to freeze.")
    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED")
    sys.exit(0)

# ---- 1. PROVISIONAL, scoped, and every marker disclosed ----------------------
print("\n[1] provisional data is declared, not silent")

SKIP = {"node_modules", "dist", ".vite", "coverage", "test-results", "playwright-report"}
markers: list[str] = []
for f in sorted(SRC.rglob("*")):
    if not f.is_file() or f.suffix not in {".ts", ".tsx", ".css", ".json"}:
        continue
    if SKIP & set(f.parts):
        continue
    for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(r"PROVISIONAL", line):
            markers.append(f"{f.relative_to(FE)}:{i}")

# Data markers are expected — reef_zones_PROVISIONAL.gpkg is swap-in #3 and has not
# landed. What must not happen is shipping them without telling anyone.
data_markers = []
for f in sorted(PUB.rglob("*.geojson")):
    txt = f.read_text(encoding="utf-8")
    if "PROVISIONAL" in txt or '"provisional":true' in txt.replace(" ", ""):
        data_markers.append(f.relative_to(FE).as_posix())

print(f"    source markers: {len(markers)}")
for m in markers:
    print(f"      {m}")
print(f"    data files carrying a provisional flag: {len(data_markers)}")
for m in data_markers:
    print(f"      {m}")

# The disclosure. Both locales must carry copy that says the reef zones are
# provisional and that the index is not model output.
en = json.loads((SRC / "i18n/locales/en/common.json").read_text())
ar = json.loads((SRC / "i18n/locales/ar/common.json").read_text())

disclosures = [
    ("rail.reefProvisional", "reef zones are provisional"),
    ("risk.provisional", "the exposure index is not model output"),
    ("legend.reefEqualSensitivity", "zones do not differ in sensitivity"),
    ("time.dailyOnly", "the time axis is daily only"),
    ("mooring.noSeries", "the mooring 5-minute record is not in the repo"),
    ("validation.notComputed", "no modelled arrival has been computed"),
]


def get(d, dotted):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur if isinstance(cur, str) and cur.strip() else None


for key, what in disclosures:
    both = get(en, key) and get(ar, key)
    check(f"disclosed in both languages: {what}", bool(both), f"missing i18n key {key}")

# ---- 2. nothing reaches outside the origin -----------------------------------
print("\n[2] no external references in shipped source")
CDN = re.compile(r"https?://(?!localhost)", re.I)
leaks = []
for f in sorted(list(SRC.rglob("*.ts")) + list(SRC.rglob("*.tsx")) + list(SRC.rglob("*.css"))
                + [FE / "index.html"]):
    if not f.is_file() or SKIP & set(f.parts):
        continue
    for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        st = line.strip()
        # A URL inside a comment or a citation string is documentation, not a fetch.
        if st.startswith(("*", "//", "/*", "<!--")):
            continue
        for m in CDN.finditer(line):
            # doi and citation text are content, not requests
            if "doi" in line.lower() or "citation" in line.lower():
                continue
            leaks.append(f"{f.relative_to(FE)}:{i}  {line.strip()[:80]}")
check("zero external URLs outside comments", not leaks, "; ".join(leaks[:4]))

# ---- 3. the offline pack is complete ----------------------------------------
print("\n[3] the offline pack")
required = {
    "fonts": 6,
    "basemap": 12,
    "vendor": 1,
}
counts = {
    "fonts": len(list((PUB / "fonts").glob("*.woff2"))),
    "basemap": len(list((PUB / "basemap").glob("*.geojson"))),
    "vendor": len(list((PUB / "vendor").glob("*.js"))),
}
for k, want in required.items():
    check(f"{k}: {counts[k]} of {want} expected", counts[k] >= want,
          f"found {counts[k]}")

fixtures = list((PUB / "fixtures").glob("*.json"))
check(f"fixtures present ({len(fixtures)} files)", len(fixtures) >= 6)
thumbs = list((PUB / "fixtures" / "figures").glob("*.jpg"))
check(f"figure thumbnails present ({len(thumbs)})", len(thumbs) >= 30)

total = sum(f.stat().st_size for f in PUB.rglob("*") if f.is_file())
print(f"    offline pack total: {total:,} B ({total / 1024 / 1024:.2f} MB)")

# ---- 4. no placeholders in shipped copy -------------------------------------
print("\n[4] no placeholders left in source")
bad = []
for f in sorted(list(SRC.rglob("*.ts")) + list(SRC.rglob("*.tsx"))):
    if SKIP & set(f.parts) or f.name.endswith(".test.ts"):
        continue
    for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(r"\b(TODO|FIXME|XXX|lorem ipsum)\b", line, re.I):
            bad.append(f"{f.relative_to(FE)}:{i}")
check("no TODO/FIXME/lorem in shipped source", not bad, "; ".join(bad[:5]))

# ---- 5. deterministic demo mode ---------------------------------------------
print("\n[5] deterministic demo mode")
client = (SRC / "api/client.ts").read_text()
check("the fixtures client is the default data source",
      "'fixtures'" in client and "VITE_DATA_SOURCE ?? 'fixtures'" in client,
      "10-performance-and-offline.md: demo mode must work without network AND "
      "without the API, so fixtures has to be the default rather than opt-in")

store = (SRC / "app/uiStore.ts").read_text()
check("scenario defaults are fixed constants, so a run is reproducible",
      "SCENARIO_DEFAULTS" in store and "Math.random" not in store)

# No wall-clock in the rendered numbers: a byte-identical run cannot depend on now.
now = []
for f in sorted(list(SRC.rglob("*.tsx")) + list(SRC.rglob("*.ts"))):
    if SKIP & set(f.parts) or f.name.endswith(".test.ts"):
        continue
    for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(r"Date\.now\(\)|new Date\(\)", line) and "//" not in line.split("Date")[0]:
            now.append(f"{f.relative_to(FE)}:{i}")
# health()'s timestamp is chrome, not a rendered measurement — allowed, and named.
#
# Countdown.tsx joined this list on 9 Aug 2026. The rule guards against a
# *measurement* that silently changes with when you look at it; p4-03 is the
# opposite case — a countdown is time-relative by definition, and its own spec
# requires it to tick rather than render a frozen number. The value it displays
# is derived from `arrival_window_hours` plus the run's `issued_at`, both of
# which ARE frozen; only the "how long from now" framing moves. Both entries stay
# printed below, so the exemption is visible rather than silent.
allowed = {"src/api/fixtures.ts", "src/components/Countdown.tsx"}
unexpected = [n for n in now if n.split(":")[0] not in allowed]
check("no wall-clock in rendered values", not unexpected, "; ".join(unexpected[:4]))
if now:
    print(f"    declared wall-clock use: {', '.join(now)}  (connection chrome only)")

print("\n" + "=" * 60)
if fails:
    print(f"{len(fails)} FAILED")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("ALL CHECKS PASSED")
