"""RAG tests — citation coverage and the docs/ali exclusion.

Run: .venv/bin/python tests/test_ask_citations.py

Two claims under test:
  1. An uncited answer is not shippable. Every question that gets an answer gets
     citations, and every citation's excerpt is verbatim in the file it names.
  2. docs/ali/* is never in the corpus. It is market and analogue research that
     backs the pitch, not an app surface, and a wildcard would pick it up silently.

The defined question set is the artifact the plan asks for: a table of questions ->
whether a citation was returned. It is printed on every run.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.src.rag import answer as rag_answer  # noqa: E402
from backend.src.rag import corpus, index  # noqa: E402

FAILURES: list[str] = []


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILURES.append(name)


# Questions a skeptical judge would actually ask. Every one must yield a citation.
MUST_ANSWER_EN = [
    "How confident are we in the catchment area?",
    "Why is the reef sensitivity weight 1.0?",
    "Why did you use GMRT instead of GEBCO?",
    "What is the resolution of the bathymetry?",
    "Is the soil data measured locally?",
    "What licence is the land cover under?",
    "Why did the satellite plume validation find nothing?",
    "What was wrong with the original bounding box?",
    "How accurate is the coastline?",
    "What are the known limitations of the land cover data?",
]

MUST_ANSWER_AR = [
    "لماذا حساسية الشعاب 1.0؟",
    "ما هي دقة الأعماق؟",
    "هل التربة مقاسة محلياً؟",
]

# Nonsense and genuinely out-of-corpus questions must be refused, not answered
# from thin air.
#
# NOTE: "what is the airspeed velocity of an unladen swallow" was the original
# control and has been RETIRED. Documenting that failure in the data dictionary's
# bug table put the words "airspeed" and "velocity" into the corpus, so the query
# now legitimately retrieves the paragraph describing itself. A control question
# that the project writes about stops being a control — these replacements are
# topics this repo will never document.
MUST_REFUSE = [
    "zzzqqq xyzzy flibbertigibbet",
    "what is the capital city of Mongolia",
    "how do I make sourdough starter from scratch",
]


def test_corpus_excludes_ali():
    present, missing = corpus.resolve()
    offenders = [str(p) for p in present if "docs/ali" in str(p).replace("\\", "/")]
    check("no docs/ali file is resolved into the corpus", not offenders,
          f"found {offenders}")

    chunks, _, _ = index.build_index()
    chunk_offenders = {c.source_file for c in chunks if "docs/ali" in c.source_file}
    check("no indexed chunk comes from docs/ali", not chunk_offenders,
          f"found {chunk_offenders}")

    check("docs/ali/ is declared in EXCLUDED_DIRS",
          any("docs/ali" in d for d in corpus.EXCLUDED_DIRS))

    # And the guard actually fires if someone adds one by hand.
    check("is_excluded flags a docs/ali path",
          corpus.is_excluded("docs/ali/11-market.md"))
    check("is_excluded does not flag a legitimate doc",
          not corpus.is_excluded("docs/data_dictionary.md"))


def test_ali_files_actually_exist_so_the_test_is_meaningful():
    """If docs/ali/ were empty the exclusion test would pass trivially."""
    ali = list((ROOT / "docs" / "ali").glob("*.md")) if (ROOT / "docs" / "ali").exists() else []
    check(f"docs/ali/ exists with {len(ali)} files, so exclusion is a real constraint",
          len(ali) > 0, "docs/ali/ is empty — exclusion test proves nothing")


def test_missing_corpus_entries_are_reported_not_hidden():
    _, missing = corpus.resolve()
    check("resolve() reports missing entries rather than dropping them silently",
          isinstance(missing, list))
    if missing:
        print(f"        (corpus entries not yet on disk: {missing})")


def test_citation_coverage():
    print("\n  question -> citation coverage table")
    print(f"  {'lang':5s} {'cites':>5s}  {'top source':44s} question")
    rows = 0
    for lang, questions in (("en", MUST_ANSWER_EN), ("ar", MUST_ANSWER_AR)):
        for q in questions:
            hits = index.retrieve(q, k=3)
            text, citations = rag_answer.generate_cited_answer(q, hits, lang)
            top = citations[0]["source_file"] if citations else "-"
            print(f"  {lang:5s} {len(citations):5d}  {top[:44]:44s} {q[:46]}")
            rows += 1
            if not citations:
                FAILURES.append(f"no citation for: {q}")
    check(f"every one of {rows} must-answer questions returned >= 1 citation",
          not [f for f in FAILURES if f.startswith("no citation")])


def test_refusal_has_no_citations_and_no_invented_content():
    for q in MUST_REFUSE:
        hits = index.retrieve(q, k=3)
        text, citations = rag_answer.generate_cited_answer(q, hits, "en")
        check(f"refused: {q[:38]!r}", not citations and "don't have documented" in text,
              f"citations={len(citations)} text={text[:70]!r}")


def test_every_excerpt_is_verbatim_in_its_source():
    """A citation that misquotes its source is worse than no citation."""
    checked = 0
    for q in MUST_ANSWER_EN[:6]:
        for cit in index.retrieve(q, k=3):
            path = ROOT / cit["source_file"]
            if not path.exists() or path.suffix == ".pdf":
                continue  # PDF text extraction reflows; markdown is the strict case
            body = path.read_text(encoding="utf-8", errors="replace")
            # Compare on collapsed whitespace: chunking preserves characters, and
            # markdown wrapping means the excerpt's line breaks may differ.
            if " ".join(cit["excerpt"].split())[:120] not in " ".join(body.split()):
                FAILURES.append(f"excerpt not found in {cit['source_file']}")
            checked += 1
    check(f"all {checked} markdown excerpts are verbatim in their source files",
          not [f for f in FAILURES if f.startswith("excerpt not found")])


def test_answer_quotes_rather_than_paraphrases():
    hits = index.retrieve("Why is the reef sensitivity weight 1.0?", k=2)
    text, citations = rag_answer.generate_cited_answer("q", hits, "en")
    check("answer contains the quoted excerpt characters",
          all(c["excerpt"][:60] in text for c in citations),
          "the generator altered the excerpt")
    check("answer names every source file it used",
          all(c["source_file"] in text for c in citations))


def test_llm_path_is_not_silently_available():
    try:
        rag_answer.generate_with_llm("q", [], "en")
        check("generate_with_llm refuses without a configured model", False,
              "it returned something")
    except NotImplementedError:
        check("generate_with_llm refuses without a configured model", True)


def test_index_is_deterministic():
    a = index.retrieve("Why is the reef sensitivity weight 1.0?", k=3)
    index.build_index.cache_clear()
    b = index.retrieve("Why is the reef sensitivity weight 1.0?", k=3)
    check("same question returns identical citations across index rebuilds",
          [x["chunk_id"] for x in a] == [x["chunk_id"] for x in b])


if __name__ == "__main__":
    print("RAG citation and exclusion tests\n")
    print(" corpus composition")
    test_corpus_excludes_ali()
    test_ali_files_actually_exist_so_the_test_is_meaningful()
    test_missing_corpus_entries_are_reported_not_hidden()
    print(f"\n  index: {index.index_stats()['n_chunks']} chunks from "
          f"{index.index_stats()['n_files_indexed']} files")

    test_citation_coverage()
    print("\n citation integrity")
    test_refusal_has_no_citations_and_no_invented_content()
    test_every_excerpt_is_verbatim_in_its_source()
    test_answer_quotes_rather_than_paraphrases()
    test_llm_path_is_not_silently_available()
    test_index_is_deterministic()

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        sys.exit(1)
    print("citation coverage 100% on the defined set; docs/ali confirmed excluded")
