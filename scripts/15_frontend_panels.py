#!/usr/bin/env python3
"""Derive the honest panels from the repo's own documents.

Phase 3's gate is that every panel renders from real repo artefacts, not mockups.
So nothing here is authored: the provenance figures come from the QA manifest, the
limitations from the limitation documents, the data sources from the data
dictionary, and the assistant corpus from the technical docs themselves.

Four outputs:
  provenance.json  34 figures with captions, plus WebP thumbnails
  limitations.json the numbered limitations, parsed from their own headings
  sources.json     the data-source table with licences
  corpus.json      a searchable index for the assistant, with real citations

Thumbnails use `sips`, which is a macOS built-in — so this script runs on the
host rather than in the worker container. It needs no geospatial stack.

    python3 scripts/15_frontend_panels.py --out frontend/public/fixtures
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SHOTS = DOCS / "qa_screenshots"

# 07 §6: overview_01 is excluded from the provenance panel. Its own burned-in
# caption reads "CATCHMENTS ARE A LOCAL TEST FIXTURE… 5 latitude bands, not a
# watershed delineation." Best-looking figure, wrong catchments — so showing it
# would put a known-false image in the panel whose entire job is provenance.
EXCLUDED_FIGURES = {"overview_01_master_all_layers.png"}

THUMB_MAX = 480  # px on the long edge


def thumbnails(out_dir: Path, names: list[str]) -> dict[str, dict]:
    """Generate thumbnails with sips, and report what each one cost.

    Day-1 ask #3 (figure delivery) is still undecided — 27 MB of PNGs, eleven of
    them over 1 MB, overview_01 alone 5.4 MB. Committing that into the frontend is
    not an option when the offline pack has to carry it, so the panel ships
    thumbnails and links the full-resolution file in the repo.

    JPEG, not WebP. 10-performance-and-offline.md asks for WebP, but sips on this
    macOS answers "Can't write format: org.webmproject.webp" — so the doc's plan
    is not available without adding cwebp as a dependency. Measured on one figure:
    original 96,193 B, JPEG at q82 20,396 B, PNG 30,799 B. JPEG wins and these are
    lightbox thumbnails, not the artefact of record; the full-resolution PNG stays
    in the repo and the panel links to it.
    """
    tdir = out_dir / "figures"
    tdir.mkdir(parents=True, exist_ok=True)
    made: dict[str, dict] = {}

    for n in names:
        src = SHOTS / n
        if not src.exists():
            print(f"    MISSING {n}")
            continue
        dst = tdir / (Path(n).stem + ".jpg")
        r = subprocess.run(
            [
                "sips", "-s", "format", "jpeg", "-s", "formatOptions", "82",
                "-Z", str(THUMB_MAX), str(src), "--out", str(dst),
            ],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0 or not dst.exists():
            print(f"    FAILED  {n}: {r.stderr.strip()[:120]}")
            continue
        made[n] = {
            "thumb": f"figures/{dst.name}",
            "thumb_bytes": dst.stat().st_size,
            "full_bytes": src.stat().st_size,
            "full_path": f"docs/qa_screenshots/{n}",
        }
    return made


def provenance(out_dir: Path) -> dict:
    manifest = json.loads((SHOTS / "manifest.json").read_text())
    on_disk = sorted(p.name for p in SHOTS.glob("*.png"))

    # 07 §6: the manifest lists 34 while 36 PNGs exist, and driving the panel off
    # the manifest silently omits two. That is a decision, not an accident — the
    # extras are later plume figures — so it is recorded rather than papered over.
    omitted = [n for n in on_disk if n not in manifest]

    keep = [n for n in manifest if n not in EXCLUDED_FIGURES]
    thumbs = thumbnails(out_dir, keep)

    figures = []
    for n in keep:
        m = manifest[n]
        t = thumbs.get(n, {})
        figures.append(
            {
                "file": n,
                "caption": m.get("caption", ""),
                "generated": m.get("generated"),
                "source": m.get("source"),
                **t,
            }
        )

    return {
        "figures": figures,
        "manifest_count": len(manifest),
        "on_disk_count": len(on_disk),
        "omitted_from_manifest": omitted,
        "excluded": sorted(EXCLUDED_FIGURES),
        "excluded_reason_key": "provenance.excludedReason",
    }


def split_sections(text: str, level: int = 2) -> list[dict]:
    """Split markdown on headings of one level, keeping the body."""
    pat = re.compile(rf"^{'#' * level} +(.+)$", re.M)
    marks = list(pat.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.end() : end].strip()
        out.append({"heading": m.group(1).strip(), "body": body})
    return out


def limitations() -> dict:
    """The limitations page — 04's LimitationsPage, from its own sources.

    pitch_limitations.md is numbered 1..9 with a one-line version at the top.
    forcing_limitations.md is the ~9 km ocean-model statement, which the map shows
    as the grid overlay — so the text and the honesty device say the same thing.
    """
    pitch = (DOCS / "pitch_limitations.md").read_text()
    forcing = (DOCS / "forcing_limitations.md").read_text()

    numbered = []
    for s in split_sections(pitch, 2):
        m = re.match(r"^(\d+)\.\s*(.+)$", s["heading"])
        if m:
            numbered.append({"n": int(m.group(1)), "title": m.group(2), "body": s["body"]})

    one_line = next(
        (s["body"] for s in split_sections(pitch, 2) if "one-line" in s["heading"].lower()), ""
    )
    forcing_stmt = next(
        (s["body"] for s in split_sections(forcing, 2) if "one-paragraph" in s["heading"].lower()),
        "",
    )

    return {
        "one_line": one_line,
        "items": numbered,
        "forcing": {
            "statement": forcing_stmt,
            "source": "docs/forcing_limitations.md",
        },
        "sources": ["docs/pitch_limitations.md", "docs/forcing_limitations.md"],
    }


def validation() -> dict:
    """The validation panel: the measured target, and the null result as a finding.

    Concept §15.3 Scene 6 says "reveal the actual post-event satellite plume."
    That is superseded and the panel has to say why: docs/event_audit.md returns a
    pixel-level NO-GO because the plume dispersed 2.5-3.5 days before any
    accessible pass, confirmed independently by Sentinel-2 and Landsat 8. A
    physical null, not a data-quality problem — which is a finding worth showing,
    not a gap to hide.
    """
    audit = (DOCS / "event_audit.md").read_text()
    verdict = next(
        (s for s in split_sections(audit, 2) if "go / no-go" in s["heading"].lower()), None
    )
    mooring = json.loads(
        (ROOT / "data/processed/marine/mooring_target_AQ-2016-10-28.json").read_text()
    )

    return {
        "satellite": {
            "verdict": "NO-GO",
            "heading": verdict["heading"] if verdict else "Go / no-go",
            # First few lines only: the panel links out rather than inlining 402 lines.
            "excerpt": "\n".join((verdict["body"] if verdict else "").splitlines()[:14]),
            "source": "docs/event_audit.md",
            "is_physical_null": True,
        },
        "mooring_target": {
            "citation": mooring["source_citation"],
            "doi": mooring["source_doi"],
            "timing_utc": mooring["timing_utc"],
            "magnitude": mooring["magnitude"],
            "position": mooring["position"],
            "calibration_use": mooring.get("calibration_use"),
        },
        # There is no simulated arrival to compare against yet: the particle engine
        # exists but no run has been registered. The panel shows the measured
        # target and an explicit "not yet computed" rather than a fabricated match.
        "modelled": None,
        "modelled_blocked_on": "no registered simulation run (data/outputs/<run_id>/ has never been created)",
    }


def sources() -> dict:
    """The data-sources table, from the data dictionary that already tracks licence."""
    text = (DOCS / "data_dictionary.md").read_text()
    rows = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set("".join(cells)) <= set("-: "):
            continue
        # Licence-bearing rows are the ones the attribution obligation attaches to.
        if re.search(r"CC BY|ODbL|public domain|Copernicus|NASA|open", line, re.I):
            rows.append(cells)

    return {
        "rows": rows[:40],
        "source": "docs/data_dictionary.md",
        # 13-economics.md §6: OSM is share-alike, and that is the one that needs a
        # decision before a paid contract. Surfaced in the panel because attribution
        # is a licence obligation and concept §22.4 scores integrity.
        "share_alike_note_key": "provenance.odblNote",
    }


# The assistant's corpus. Technical and operational documentation only —
# 07 §4 is explicit that docs/Ali/research/* is NOT in it.
CORPUS_FILES = [
    "docs/event_dates.md",
    "docs/event_audit.md",
    "docs/pitch_limitations.md",
    "docs/forcing_limitations.md",
    "docs/data_dictionary.md",
    "docs/mooring_coordinate_derivation.md",
    "docs/osm_dem_conflicts.md",
    "docs/era5_land_temporal_semantics.md",
    "docs/pipeline_capability_report.md",
    "docs/MASTER_TASK_SUMMARY.md",
    "tasks/00-contracts.md",
]


def corpus() -> dict:
    """A retrieval index the assistant can search offline, with real citations.

    07 §4 makes an uncited answer structurally impossible: the response is a union
    whose answered branch carries a non-empty citation tuple. That only means
    something if the citations are real, so this indexes actual sections of actual
    files and the client cites file + heading.

    Deliberately keyword retrieval rather than embeddings. It runs offline with no
    model, and — more importantly — it cannot paraphrase. The assistant returns
    passages it found and names where they came from; it does not generate prose
    that could drift from the source.
    """
    chunks = []
    for rel in CORPUS_FILES:
        p = ROOT / rel
        if not p.exists():
            print(f"    corpus MISSING {rel}")
            continue
        text = p.read_text()
        for sec in split_sections(text, 2):
            body = re.sub(r"\n{3,}", "\n\n", sec["body"]).strip()
            if len(body) < 60:
                continue
            chunks.append(
                {
                    "file": rel,
                    "section": sec["heading"],
                    # Capped: the panel shows an excerpt and links to the file.
                    "text": body[:1200],
                }
            )
    return {
        "chunks": chunks,
        "files": CORPUS_FILES,
        "excludes": ["docs/Ali/research/*"],
        "retrieval": "keyword",
    }


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("ReefShield frontend panels")
    print("=" * 62)

    print("  provenance")
    prov = provenance(out)
    (out / "provenance.json").write_text(json.dumps(prov, ensure_ascii=False, indent=1))
    tb = sum(f.get("thumb_bytes", 0) for f in prov["figures"])
    fb = sum(f.get("full_bytes", 0) for f in prov["figures"])
    print(f"    {len(prov['figures'])} figures of {prov['manifest_count']} in the manifest"
          f" ({prov['on_disk_count']} PNGs on disk)")
    print(f"    excluded: {', '.join(prov['excluded'])}")
    print(f"    omitted from manifest: {len(prov['omitted_from_manifest'])}")
    print(f"    thumbnails {tb:,} B  vs  full-res {fb:,} B  "
          f"({100 * tb / max(1, fb):.1f}% of the originals)")

    print("  limitations")
    lim = limitations()
    (out / "limitations.json").write_text(json.dumps(lim, ensure_ascii=False, indent=1))
    print(f"    {len(lim['items'])} numbered limitations + the forcing statement")

    print("  validation")
    val = validation()
    (out / "validation.json").write_text(json.dumps(val, ensure_ascii=False, indent=1))
    print(f"    satellite verdict {val['satellite']['verdict']}"
          f" (physical null: {val['satellite']['is_physical_null']})")
    print(f"    modelled arrival: {val['modelled'] or 'not computed — ' + val['modelled_blocked_on']}")

    print("  sources")
    src = sources()
    (out / "sources.json").write_text(json.dumps(src, ensure_ascii=False, indent=1))
    print(f"    {len(src['rows'])} licence-bearing rows")

    print("  corpus")
    cor = corpus()
    (out / "corpus.json").write_text(json.dumps(cor, ensure_ascii=False, indent=1))
    print(f"    {len(cor['chunks'])} sections from {len(cor['files'])} files"
          f"  (research docs excluded)")

    total = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print()
    print("=" * 62)
    print(f"  fixtures total {total:,} B ({total / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
