#!/usr/bin/env python3
"""Derive the honest panels from the repo's own documents.

Phase 3's gate is that every panel renders from real repo artefacts, not mockups.
So nothing here is authored: the provenance figures come from the QA manifest, the
limitations from the limitation documents, the data sources from the data
dictionary, and the assistant corpus from the technical docs themselves.

Six outputs (the docstring said "four" before this pass and had already fallen
behind validation.json; corrected while models.json was added):
  provenance.json  34 figures with captions, plus WebP thumbnails
  limitations.json the numbered limitations, parsed from their own headings
  validation.json  the measured mooring target vs. the modelled/null comparison
  sources.json     the data-source table with licences
  corpus.json      a searchable index for the assistant, with real citations
  models.json      the served model's own record, for the model-honesty panel

Thumbnails use `sips`, which is a macOS built-in — so this script runs on the
host rather than in the worker container. It needs no geospatial stack.

    python3 scripts/frontend_panels.py --out frontend/public/fixtures
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

# For models() only — the honest panels below it read repo documents directly and
# need no import. tests/conftest.py does the same insert for the same reason
# (config import root, root CLAUDE.md's gotcha table).
sys.path.insert(0, str(ROOT / "backend" / "src"))

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

    pitch_limitations.md is numbered (13 as of this pass) with a one-line version
    at the top. forcing_limitations.md is the ~9 km ocean-model statement, which
    the map shows as the grid overlay — so the text and the honesty device say the
    same thing.
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
        # p4-17's chart. Frozen historical findings from a one-off analysis
        # (reports/model/label_problem.md SS1 and SS3), not live-computed here --
        # same category as sediment_proxy.py's ANCHOR_MASS_T. Item 13 above states
        # the same numbers in prose; this is the structured form the chart needs.
        # No total day count is invented for the 3.21%/0.156% shares -- the source
        # states shares directly, not a raw denominator.
        "label_frequency_gap": {
            "target_fires_pct": 3.21,
            "target_fires_days": 288,
            "target_fires_per_year": 11.7,
            "documented_floods_pct": 0.156,
            "documented_floods_count": 13,
            "documented_floods_per_year": 0.57,
            "gap_multiple_optimistic": 21,
            "gap_multiple_sampled": 78,
            "era5_dry_pct_of_imerg_wet_days": 35,
            "era5_dry_pct_of_heaviest_imerg_days": 20,
            "checked_catchment_days": 276,
            "checked_catchment_days_positive": 1,
            "anchor_event": {
                "era5_mm": 0.77,
                "era5_percentile": 92.6,
                "imerg_mm": 9.58,
                "imerg_percentile": 99.5,
            },
            "source": "reports/model/label_problem.md; root CLAUDE.md label rule section",
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

    # The particle engine's calibration grid search (scripts/28_calibrate_plume_engine.py)
    # against this same mooring record -- a genuinely different comparison than the
    # magnitude rows above. It fits TIMING (onset, duration, peak) via a concentration
    # proxy, never sediment g/L or salinity PSU, which the engine does not model at all.
    # Reported as errors (simulated - observed), exactly as calibration.py computed them --
    # no back-derived "modelled value" is invented for a number that was never stored.
    calibration_path = ROOT / "data/models/plume_calibration.json"
    calibration_fit = None
    if calibration_path.exists():
        cal = json.loads(calibration_path.read_text())
        calibration_fit = {
            "event_id": cal["event_id"],
            "selected_regime_verdict": cal["selected_regime_verdict"],
            "params": cal["params"],
            "arrival_time_error_hours": cal["arrival_time_error_hours"],
            "duration_error_hours": cal["duration_error_hours"],
            "peak_timing_error_hours": cal["peak_timing_error_hours"],
            "n_trials": cal["n_trials"],
            "forcing_is_placeholder": cal["forcing_is_placeholder"],
            "forcing_placeholder_reason": cal["forcing_placeholder_reason"],
            "windage_caveat": cal["windage_caveat"],
            "peak_timing_caveat": cal["peak_timing_caveat"],
            "source": "data/models/plume_calibration.json (scripts/28_calibrate_plume_engine.py)",
        }

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
        "calibration_fit": calibration_fit,
    }


def models() -> dict:
    """The model-honesty panel (p4-09 / p4-11): what is served, and which number
    answers which claim.

    Same derive-and-commit pattern as scripts/frontend_predictions.py, for the
    same reason: DoD item 9 ("works with wifi off") means the panel cannot make a
    live call, so the served model's own record is baked into a fixture instead.

    Three numbers, three different claims — root CLAUDE.md and
    docs/model_card.md are both explicit that none of these substitute for each
    other:
      mean_AP                 (LOCO)             generalises to an unseen CATCHMENT
      temporal_holdout_AP     (train <=2014)     generalises to an unseen TIME PERIOD
      label_leakage_ablation  (a DIFFERENT model) predicts from independent inputs
    Trimmed here to what the panel needs: training_event_ids (2,362 entries) and
    hyperparams are real but irrelevant to a reader asking "can I trust this
    number", so they are left out of the fixture rather than shipped unread.
    """
    from models.runoff_model import model_info

    info = model_info()
    m = info["metrics"]
    return {
        "id": info["id"],
        "algorithm": info["algorithm"],
        "trained_at": info["trained_at"],
        "n_training_events": info["n_training_events"],
        "features": info["features"],
        "metrics": {
            "mean_AP": m["mean_AP"],
            "baseline_mean_AP": m["baseline_mean_AP"],
            "pooled_AP": m["pooled_AP"],
            "temporal_holdout_AP": m["temporal_holdout_AP"],
            "temporal_holdout_baseline_AP": m["temporal_holdout_baseline_AP"],
            "temporal_holdout_split": m["temporal_holdout_split"],
            "temporal_holdout_anchor_check": m["temporal_holdout_anchor_check"],
            "_note": m["_note"],
        },
        "label_leakage_ablation": info["label_leakage_ablation"],
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
    if val["calibration_fit"]:
        cf = val["calibration_fit"]
        print(f"    calibration fit: {cf['selected_regime_verdict']}"
              f" | arrival {cf['arrival_time_error_hours']:+.2f}h"
              f" | duration {cf['duration_error_hours']:+.2f}h"
              f" | peak {cf['peak_timing_error_hours']:+.2f}h"
              f" ({cf['n_trials']} trials)")
    else:
        print("    calibration fit: not computed — no data/models/plume_calibration.json")

    print("  models")
    mdl = models()
    (out / "models.json").write_text(json.dumps(mdl, ensure_ascii=False, indent=1))
    print(f"    {mdl['id']}")
    print(f"    LOCO mean_AP {mdl['metrics']['mean_AP']} vs baseline {mdl['metrics']['baseline_mean_AP']}"
          f"  |  temporal_holdout_AP {mdl['metrics']['temporal_holdout_AP']}"
          f" vs baseline {mdl['metrics']['temporal_holdout_baseline_AP']}")
    print(f"    independent-inputs claim: {mdl['label_leakage_ablation']['defensible_mean_AP']}"
          f" (not {mdl['label_leakage_ablation']['shipped_mean_AP']})")

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
