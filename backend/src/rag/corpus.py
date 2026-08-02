"""The RAG corpus — an explicit allowlist, never a glob.

WHY AN ALLOWLIST AND NOT `docs/**/*.md`
---------------------------------------
`docs/ali/*` is the MENA and global analogue scan. It is research and pitch
material: it backs the market slide and the "is this only for Aqaba?" answer in
Q&A. It is NOT an app surface, and an answer to a technical question citing a
market-sizing document would be actively misleading.

A recursive glob picks it up silently. So the corpus is a literal list, and
`EXCLUDED_DIRS` is enforced in `resolve()` as a second, independent guard — if
someone adds a path under docs/ali/ to the list by hand, resolution refuses it
rather than trusting that the list was curated correctly.

`tests/test_ask_citations.py` asserts both: that nothing under docs/ali/ is ever
resolved, and that every corpus entry that exists on disk is actually indexed.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

# Exactly these files. Order is stable so chunk ids are reproducible run to run.
CORPUS_FILES: list[str] = [
    "data/raw/literature/kalman_et_al_2025_fulltext_ATC1.pdf",
    "docs/data_dictionary.md",
    "docs/event_dates.md",
    "docs/era5_land_temporal_semantics.md",
    "docs/era5_land_accumulation_semantics.md",
    "docs/pitch_limitations.md",
    "docs/forcing_limitations.md",
    "docs/osm_dem_conflicts.md",
    "docs/qa_screenshots/MANIFEST.md",
    "docs/model_card.md",
    "tasks/00-contracts.md",
    # Added by this workstream: the measured evidence for the AOI correction. A
    # judge asking "how do you know the old box was wrong?" should get the report,
    # not a paraphrase of it.
    "docs/aoi_coverage_report_20260802.txt",
    "docs/README_pulga.md",
]

# Hard exclusions, enforced independently of the list above.
EXCLUDED_DIRS: tuple[str, ...] = (
    "docs/ali/",       # market / analogue research — pitch only, not an app surface
    "docs/schema_proposals/",  # proposals, not decisions
)


class ExcludedFromCorpus(RuntimeError):
    """Raised when something explicitly excluded is asked for."""


def is_excluded(rel_path: str) -> bool:
    norm = str(rel_path).replace("\\", "/").lstrip("./")
    return any(norm.startswith(d) or f"/{d}" in f"/{norm}" for d in EXCLUDED_DIRS)


def resolve() -> tuple[list[Path], list[str]]:
    """(existing files, missing entries).

    Missing entries are RETURNED, not silently dropped — a corpus that quietly
    shrinks because a teammate renamed a doc is how /ask starts answering "I don't
    have documented information" to questions that are in fact documented.
    """
    present: list[Path] = []
    missing: list[str] = []

    for rel in CORPUS_FILES:
        if is_excluded(rel):
            raise ExcludedFromCorpus(
                f"{rel} is under an excluded directory {EXCLUDED_DIRS} and must not be "
                "indexed. Remove it from CORPUS_FILES."
            )
        p = ROOT / rel
        (present if p.exists() else missing).append(p if p.exists() else rel)

    return present, missing


def summary() -> dict:
    present, missing = resolve()
    return {
        "n_files_configured": len(CORPUS_FILES),
        "n_files_present": len(present),
        "missing": missing,
        "excluded_dirs": list(EXCLUDED_DIRS),
    }
