"""Chunk, index and retrieve over the technical corpus.

NO EXTERNAL EMBEDDING SERVICE. Retrieval is BM25-style lexical scoring computed
locally. Three reasons, in order of importance:

  1. Every citation must be exact. Lexical retrieval returns the literal chunk it
     scored, so the `excerpt` in a citation is verbatim source text and can be
     checked character-for-character against the file.
  2. It is deterministic. The same question returns the same citations on the demo
     laptop, offline, on conference wifi, with no API key and no rate limit.
  3. It has no failure mode that produces a confident answer from nothing.

The cost is honest: lexical retrieval misses paraphrase. A question about "how sure
are you about catchment size" will not match "area uncertainty" on wording alone,
so `SYNONYMS` bridges the vocabulary this corpus actually uses. That is a stated
limitation, not a hidden one — see `docs/rag_limitations.md`.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .corpus import ROOT, resolve

# Chunking: markdown sections, split further if a section is long. Section headings
# are kept because they become the `section` field of a citation.
MAX_CHUNK_CHARS = 1400
MIN_CHUNK_CHARS = 80

# BM25 parameters — standard defaults; not tuned, and saying so matters more than
# a tuned number nobody can justify.
BM25_K1 = 1.5
BM25_B = 0.75

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "was", "were",
    "for", "on", "with", "as", "at", "by", "it", "this", "that", "from", "be",
    "we", "our", "i", "you", "what", "how", "why", "does", "do", "can", "not",
    "but", "if", "than", "then", "so", "its", "has", "have", "had", "will",
}

# Question vocabulary -> corpus vocabulary. Each entry exists because the corpus
# genuinely uses different words than a person would ask with.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "sure": ("uncertainty", "confidence", "limitation"),
    "confident": ("uncertainty", "confidence", "limitation"),
    "accurate": ("uncertainty", "resolution", "limitation"),
    "size": ("area", "km2"),
    "big": ("area", "km2"),
    "sensitivity": ("sensitivity_weight", "placeholder", "marine"),
    "reef": ("reef_zone", "reef", "coral", "habitat"),
    "depth": ("bathymetry", "depth", "gebco", "gmrt"),
    "soil": ("soilgrids", "soil", "clay", "erodibility"),
    "rain": ("rainfall", "imerg", "precipitation"),
    "rainfall": ("rainfall", "imerg", "precipitation"),
    "flood": ("event", "flood", "storm"),
    "wrong": ("limitation", "error", "bug", "caveat"),
    "missing": ("nodata", "gap", "coverage"),
    "coastline": ("coastline", "shoreline", "coast"),
    "aoi": ("aoi", "bounding", "extent", "terrain_aoi"),
    "box": ("bounding", "bbox", "extent", "aoi"),
    "placeholder": ("placeholder", "provisional", "assumption"),
    "licence": ("licence", "license", "cc", "odbl"),
    "license": ("licence", "license", "cc", "odbl"),
}


# THE CORPUS IS ENTIRELY ENGLISH. Every document in it is written in English, so an
# Arabic question tokenizes to terms that appear nowhere and retrieval returns
# nothing — which /ask then honestly reports as "no documented information", giving
# an Arabic speaker a worse answer than an English speaker for the same question.
#
# This bridge maps the Arabic terms a user would actually ask with onto the English
# vocabulary the corpus uses. It is a translation of QUERY TERMS ONLY: the retrieved
# excerpt, and therefore the citation, is still the verbatim English source text.
# Answering in Arabic ABOUT an English document is a real limitation and is stated
# in docs/rag_limitations.md rather than hidden behind partial coverage.
ARABIC_QUERY_BRIDGE: dict[str, tuple[str, ...]] = {
    "الشعاب": ("reef", "coral", "reef_zone"),
    "حساسية": ("sensitivity", "sensitivity_weight", "placeholder"),
    "عمق": ("depth", "bathymetry"),
    "الأعماق": ("depth", "bathymetry", "gebco"),
    "التربة": ("soil", "soilgrids", "clay"),
    "المطر": ("rainfall", "precipitation", "imerg"),
    "الأمطار": ("rainfall", "precipitation", "imerg"),
    "مساحة": ("area", "km2"),
    "الحوض": ("catchment", "basin"),
    "الأحواض": ("catchment", "basin"),
    "دقة": ("resolution", "accuracy", "uncertainty"),
    "الثقة": ("confidence", "uncertainty"),
    "خطأ": ("error", "bug", "limitation"),
    "قيود": ("limitation", "caveat"),
    "الترخيص": ("licence", "license"),
    "مصدر": ("source", "provenance"),
    "لماذا": (),          # "why" — a stopword, carries no retrieval signal
    "ما": (),
    "هل": (),
    "كيف": (),
}


def tokenize(text: str) -> list[str]:
    raw = re.findall(r"[a-z0-9_]+", text.lower())
    return [t for t in raw if t not in STOPWORDS and len(t) > 1]


def _arabic_terms(text: str) -> list[str]:
    """English query terms bridged from an Arabic question."""
    out: list[str] = []
    for word in re.findall(r"[؀-ۿ]+", text):
        out.extend(ARABIC_QUERY_BRIDGE.get(word, ()))
        if word not in ARABIC_QUERY_BRIDGE:
            # Try without the definite article "ال", which is how most of these
            # words appear when a question is phrased naturally.
            out.extend(ARABIC_QUERY_BRIDGE.get(word.removeprefix("ال"), ()))
            out.extend(ARABIC_QUERY_BRIDGE.get(f"ال{word}", ()))
    return out


def expand_query(tokens: list[str], raw_text: str = "") -> list[str]:
    out = list(tokens)
    for t in tokens:
        out.extend(SYNONYMS.get(t, ()))
    out.extend(_arabic_terms(raw_text))
    return out


@dataclass
class Chunk:
    chunk_id: str
    source_file: str
    section: str
    text: str
    tokens: list[str] = field(default_factory=list)


def _read_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:  # pragma: no cover
            return ""
        try:
            reader = PdfReader(str(path))
            return "\n\n".join((pg.extract_text() or "") for pg in reader.pages)
        except Exception:
            return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _split_sections(text: str, source: str) -> list[tuple[str, str]]:
    """(section_heading, body). Markdown headings define sections; PDFs get pages."""
    if not text.strip():
        return []

    if source.endswith(".pdf"):
        pages = [p for p in text.split("\n\n") if p.strip()]
        return [(f"p.{i + 1}", p) for i, p in enumerate(pages)]

    parts: list[tuple[str, str]] = []
    current_heading = "(preamble)"
    buf: list[str] = []
    for line in text.splitlines():
        if re.match(r"^#{1,6}\s+\S", line):
            if buf:
                parts.append((current_heading, "\n".join(buf)))
                buf = []
            current_heading = line.lstrip("#").strip()
        else:
            buf.append(line)
    if buf:
        parts.append((current_heading, "\n".join(buf)))
    return parts


def _window(body: str) -> list[str]:
    """Split an over-long section on paragraph boundaries, never mid-sentence."""
    if len(body) <= MAX_CHUNK_CHARS:
        return [body]
    out, cur = [], ""
    for para in body.split("\n\n"):
        if len(cur) + len(para) + 2 > MAX_CHUNK_CHARS and cur:
            out.append(cur)
            cur = para
        else:
            cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        out.append(cur)
    return out


@lru_cache(maxsize=1)
def build_index() -> tuple[list[Chunk], dict[str, float], float]:
    """(chunks, idf, avg_len). Memoised — built once per process."""
    present, _missing = resolve()

    chunks: list[Chunk] = []
    for path in present:
        rel = str(path.relative_to(ROOT))
        text = _read_text(path)
        for heading, body in _split_sections(text, rel):
            for piece in _window(body):
                if len(piece.strip()) < MIN_CHUNK_CHARS:
                    continue
                toks = tokenize(f"{heading} {piece}")
                if not toks:
                    continue
                chunks.append(Chunk(
                    chunk_id=f"{rel}#{heading[:60]}#{len(chunks)}",
                    source_file=rel,
                    section=heading,
                    text=piece.strip(),
                    tokens=toks,
                ))

    n = len(chunks) or 1
    df = Counter()
    for c in chunks:
        df.update(set(c.tokens))
    idf = {
        t: math.log(1 + (n - freq + 0.5) / (freq + 0.5))
        for t, freq in df.items()
    }
    avg_len = sum(len(c.tokens) for c in chunks) / n
    return chunks, idf, avg_len


MIN_TERM_COVERAGE = 0.4


def retrieve(
    question: str,
    k: int = 5,
    min_score: float = 0.6,
    min_term_coverage: float = MIN_TERM_COVERAGE,
) -> list[dict]:
    """Top-k chunks by BM25, gated on score AND term coverage.

    `min_score` alone is not enough. A question whose only match is one common word
    can still clear a score floor: "airspeed velocity of an unladen swallow" matched
    a chunk about ocean current *velocity* and produced a properly-cited but
    completely irrelevant answer. The citation was real; the answer was not
    responsive, which is its own kind of dishonesty.

    So a chunk must also cover at least `min_term_coverage` of the question's
    ORIGINAL content terms — counted before synonym expansion, with a term treated
    as covered if it or any of its synonyms appears. Expanding first and then
    measuring coverage would let the expansion inflate its own score.

    Returning [] makes /ask say it has no documented answer, which is the correct
    response to a question this corpus cannot address.
    """
    chunks, idf, avg_len = build_index()
    if not chunks:
        return []

    base_tokens = tokenize(question)
    q_tokens = expand_query(base_tokens, raw_text=question)
    if not q_tokens:
        return []
    q_counts = Counter(q_tokens)

    # term -> the set of forms that count as covering it
    coverage_groups: list[set[str]] = []
    for t in base_tokens:
        coverage_groups.append({t, *SYNONYMS.get(t, ())})
    bridged = _arabic_terms(question)
    if bridged and not base_tokens:
        # An all-Arabic question has no Latin base tokens; its bridged terms are
        # the content terms.
        coverage_groups = [{b} for b in set(bridged)]
    n_groups = len(coverage_groups) or 1

    scored: list[tuple[float, Chunk]] = []
    for c in chunks:
        tf = Counter(c.tokens)
        dl = len(c.tokens)
        score = 0.0
        for term, qf in q_counts.items():
            f = tf.get(term)
            if not f:
                continue
            w = idf.get(term, 0.0)
            denom = f + BM25_K1 * (1 - BM25_B + BM25_B * dl / avg_len)
            score += w * (f * (BM25_K1 + 1) / denom) * (1 + math.log(qf))
        if score <= 0:
            continue

        covered = sum(1 for group in coverage_groups if group & tf.keys())
        if covered / n_groups < min_term_coverage:
            continue
        scored.append((score, c))

    scored.sort(key=lambda x: -x[0])
    top = [(s, c) for s, c in scored[:k] if s >= min_score]

    return [
        {
            "source_file": c.source_file,
            "section": c.section,
            "excerpt": c.text[:600],
            "score": round(s, 4),
            "chunk_id": c.chunk_id,
        }
        for s, c in top
    ]


def index_stats() -> dict:
    chunks, idf, avg_len = build_index()
    by_file = Counter(c.source_file for c in chunks)
    return {
        "n_chunks": len(chunks),
        "n_files_indexed": len(by_file),
        "vocab_size": len(idf),
        "avg_chunk_tokens": round(avg_len, 1),
        "chunks_per_file": dict(by_file),
    }
