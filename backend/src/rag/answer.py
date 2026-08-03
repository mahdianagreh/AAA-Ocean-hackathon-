"""Turn retrieved chunks into a cited answer, in English or Arabic.

THE RULE: an uncited answer is not shippable. This module cannot produce one — it
composes the answer FROM the retrieved excerpts, so if retrieval returns nothing
there is nothing to compose and the caller gets the honest refusal instead.

WHY NO GENERATIVE MODEL BY DEFAULT
----------------------------------
An LLM asked to summarise retrieved text will paraphrase numbers. That breaks the
one property this endpoint exists to have: that every figure shown traces to a
document. The default generator therefore quotes the source and never rewrites it.

`generate_with_llm` is the hook for when a key is configured. It is deliberately
NOT the default, and the number-fidelity test in tests/test_explain_fidelity.py
applies to it too.
"""

from __future__ import annotations

REFUSAL = {
    "en": "I don't have documented information to answer that.",
    "ar": "لا تتوفر لدي معلومات موثقة للإجابة على هذا السؤال.",
}

_LEAD = {
    "en": "Based on the project's own documentation:",
    "ar": "استنادًا إلى وثائق المشروع:",
}

_SOURCE_WORD = {"en": "source", "ar": "المصدر"}

_TRAILER = {
    "en": ("Every statement above is quoted from the file cited beside it. Nothing "
           "here is inferred or rephrased."),
    "ar": ("كل ما ورد أعلاه مقتبس من الملف المذكور بجانبه. لا شيء هنا مستنتج أو "
           "معاد صياغته."),
}


def _tidy(excerpt: str, limit: int = 320) -> str:
    """Collapse whitespace and markdown noise without altering wording or digits."""
    text = " ".join(excerpt.split())
    for ch in ("**", "`", "|", "#"):
        text = text.replace(ch, "")
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Prefer a sentence boundary so a quote never ends mid-number.
    for stop in (". ", "؟ ", "، "):
        idx = cut.rfind(stop)
        if idx > limit * 0.55:
            return cut[: idx + 1].strip()
    return cut.rsplit(" ", 1)[0] + "…"


def generate_cited_answer(
    question: str, chunks: list[dict], language: str = "en"
) -> tuple[str, list[dict]]:
    """(answer_text, citations). Quotes only; never paraphrases."""
    if not chunks:
        return REFUSAL.get(language, REFUSAL["en"]), []

    lang = language if language in _LEAD else "en"
    lines = [_LEAD[lang], ""]
    citations = []

    for i, ch in enumerate(chunks, 1):
        quote = _tidy(ch["excerpt"])
        lines.append(f"[{i}] “{quote}”")
        lines.append(
            f"    — {_SOURCE_WORD[lang]}: {ch['source_file']} § {ch['section']}"
        )
        lines.append("")
        citations.append({
            "source_file": ch["source_file"],
            "section": ch["section"],
            "excerpt": quote,
            "score": ch.get("score"),
        })

    lines.append(_TRAILER[lang])
    return "\n".join(lines).strip(), citations


def generate_with_llm(question, chunks, language="en"):  # pragma: no cover
    """Hook for a configured LLM. Not wired by default, and not required.

    If this is ever enabled, the system prompt must forbid altering any numeral
    from the retrieved text, and the citation list must still be built from
    `chunks` — not from whatever the model claims it used.
    """
    raise NotImplementedError(
        "No LLM is configured. The deterministic generator is the shipped default "
        "precisely because it cannot paraphrase a number. Wire this only with a "
        "number-fidelity test in place."
    )
